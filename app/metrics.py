"""业务指标计算层。

将 data_loader 的原始数据加工为三大模块所需的展示数据。
所有口径在 docstring 中标注；与报告 PDF 不完全一致处均注明“demo 近似”。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd

from . import data_loader as dl

BOARDS = ["TMT", "金融地产", "消费", "新能源及制造", "周期", "医药"]   # 展示顺序（固定）；行业→板块映射仍取自 sheet
MARKETS = ["A股", "港股"]


def _q() -> tuple[list[str], str, str]:
    """(全部季度, 最新季度, 上一季度) —— 从激活数据集派生，跨季度通用。"""
    qs = dl.quarters()
    return qs, (qs[-1] if qs else None), (qs[-2] if len(qs) > 1 else None)


def _fc_key(code) -> str | None:
    """归一化基金代码：去掉所有后缀(.OF/.SZ/.SH/.HK 等)再转整数串。
    '000001.OF' / '160910.SZ' / '000001' / '1' -> '1' / '160910' / '1' / '1'。用于跨表匹配。"""
    if code is None:
        return None
    s = str(code).strip().split(".")[0]   # 去掉 .OF/.SZ/.SH/.HK 等所有后缀
    try:
        return str(int(s))
    except (ValueError, TypeError):
        return s


# ============================================================
# 模块一：同业业绩及规模概况
# ============================================================

def peer_order() -> list[str]:
    """01 板块十五大的显示顺序：按当年YTD收益率降序（None 居末）。

    与 company_overview 的 ret_q 降序一致；02 所有表格自上而下跟随此顺序。
    """
    rk = dl.ranking()
    peer = dl.peer_corps()
    latest = dl.latest_q()
    begin = f"{int(latest[:4])}-01-01" if latest else ""
    rets = {}
    for corp in peer:
        sub = rk[(rk["corp"] == corp) & (rk["begin"].astype(str) == begin)]
        rets[corp] = float(sub.iloc[0]["return"]) if (not sub.empty and pd.notna(sub.iloc[0]["return"])) else None
    return sorted(peer, key=lambda c: rets[c] if rets[c] is not None else -999, reverse=True)


def company_overview() -> list[dict]:
    """十五家公司权益规模及业绩总览表（最新季自适应，基金级资金流分解）。

    口径（年初=上一年度年末 YEAR_START_Q，季末=最新季 LATEST_Q；YTD 从年初累计）：
    - 规模 = 产品规模表 TOTAL_NAV 按公司求和（亿元，全口径）。
    - Δ = 季末规模 − 年初规模；规模变动幅度 = Δ / 年初规模（年初至今 YTD）。
    - 收益率上涨（业绩贡献）= Σ_f [年初规模_f × 涨跌幅_f]，年初规模取自"产品规模"sheet TOTAL_NAV；
      涨跌幅优先用"产品复权净值"sheet FUQUAN_UNIT_NAV 的(季末−年初)/年初，复权净值缺失的基金回退用
      "产品规模"sheet UNIT_NAV 的(季末−年初)/年初。
    - 新发 = 最新季在、年初不在的基金的季末 TOTAL_NAV（YTD 新发）。
    - 持营 = Δ − 收益率上涨 − 新发（倒挤；吸收申赎净额等）。
    - 三项之和 = Δ（季末 − 年初）。
    - 投资收益率列 = 权益银河排名表 begin=年内初 的 YTD 行（公司口径，独立于拆分）。
    """
    rk = dl.ranking(keep_all=True)
    ps = dl.product_scale(keep_all=True)
    peer = dl.peer_corps()
    _, LATEST_Q, _ = _q()
    YEAR_START_Q = dl.year_start_q()
    LATEST_YEAR = int(LATEST_Q[:4])
    prev_ts, latest_ts = pd.Timestamp(YEAR_START_Q), pd.Timestamp(LATEST_Q)

    # 年初 = 上一年度年末(YEAR_START_Q)，季末 = 最新季度(LATEST_Q)；从产品规模表取每基金 TOTAL_NAV / UNIT_NAV
    cols = ["fund_code", "corp", "total_nav", "unit_nav"]
    prev = ps[ps["pub_date"] == prev_ts][cols]
    late = ps[ps["pub_date"] == latest_ts][cols]

    # 业绩贡献（收益率上涨）：基金级 季初规模 × 涨跌幅；涨跌幅优先用复权净值，缺失则回退单位净值
    # 复权净值涨跌幅 = (季末 FUQUAN_UNIT_NAV − 季初 FUQUAN_UNIT_NAV) / 季初 FUQUAN_UNIT_NAV （产品复权净值 sheet）
    # 单位净值回退 = (季末 UNIT_NAV − 季初 UNIT_NAV) / 季初 UNIT_NAV （产品规模 sheet，用于复权净值缺失的基金）
    nav = dl.nav_adjusted()
    nav_q = nav[(nav["pub_date"] >= prev_ts) & (nav["pub_date"] <= latest_ts)]
    nav_q = nav_q.copy()
    nav_q["fc_key"] = nav_q["fund_code"].map(_fc_key)
    fuquan_ret: dict[str, float] = {}
    for fc, sub in nav_q.groupby("fc_key"):
        vals = sub.sort_values("pub_date")["nav"].values
        if len(vals) >= 2 and vals[0] > 0:
            fuquan_ret[fc] = float(vals[-1] / vals[0] - 1)   # (季末−季初)/季初
    # 单位净值回退涨跌幅
    unav = prev[["fund_code", "unit_nav"]].merge(
        late[["fund_code", "unit_nav"]], on="fund_code", how="left", suffixes=("_p", "_l"))
    unav["fc_key"] = unav["fund_code"].map(_fc_key)
    unav = unav[(unav["unit_nav_p"].notna()) & (unav["unit_nav_p"] > 0) & (unav["unit_nav_l"].notna())]
    unit_ret = {r["fc_key"]: float((r["unit_nav_l"] - r["unit_nav_p"]) / r["unit_nav_p"])
                for _, r in unav.iterrows()}

    def _pick_ret(fc: str) -> float | None:
        if fc in fuquan_ret:
            return fuquan_ret[fc]              # 优先复权净值
        return unit_ret.get(fc)                # 回退单位净值

    prev_perf = prev.copy()
    prev_perf["fc_key"] = prev_perf["fund_code"].map(_fc_key)
    prev_perf["fund_ret"] = prev_perf["fc_key"].map(_pick_ret)
    prev_perf = prev_perf[prev_perf["fund_ret"].notna()]
    prev_perf["perf"] = prev_perf["total_nav"] * prev_perf["fund_ret"]   # 季初规模 × 涨跌幅
    perf_by_corp = prev_perf.groupby("corp")["perf"].sum()

    # 新发：最新季在、年初不在的基金，取其最新季 TOTAL_NAV（YTD 新发）
    new_funds = late[~late["fund_code"].isin(prev["fund_code"])]
    new_by_corp = new_funds.groupby("corp")["total_nav"].sum()

    # 公司年初/季末规模（亿元）= 旗下全部基金 TOTAL_NAV 求和；Δ = 季末 − 年初
    prev_sum = prev.groupby("corp")["total_nav"].sum()
    late_sum = late.groupby("corp")["total_nav"].sum()

    def _ret_by_begin(corp: str, begin: str) -> tuple[float | None, int | None, int | None]:
        sub = rk[(rk["corp"] == corp) & (rk["begin"].astype(str) == begin)]
        if sub.empty:
            return None, None, None
        r = sub.iloc[0]
        return float(r["return"]), int(r["rank"]) if pd.notna(r["rank"]) else None, \
               int(r["rank_total"]) if pd.notna(r["rank_total"]) else None

    rows = []
    for corp in peer:
        if corp not in late_sum.index:
            continue
        q1 = late_sum.get(corp)
        q4 = prev_sum.get(corp)
        if q1 is None or q4 is None or q4 == 0:
            continue
        delta = q1 - q4                       # 规模变化（亿元）
        chg_pct = (delta / q4) * 100          # 规模变动幅度
        perf = float(perf_by_corp.get(corp, 0) or 0)        # 收益率上涨（业绩贡献）
        new = float(new_by_corp.get(corp, 0) or 0)          # 新发
        holding = delta - perf - new                         # 持营（倒挤）
        ret_q, rk_q, tot_q = _ret_by_begin(corp, f"{LATEST_YEAR}-01-01")   # 当年YTD收益率（银河）
        begin_3y = f"{LATEST_YEAR - 2}-01-01"
        ret_3y, rk3_rank, tot_3y = _ret_by_begin(corp, begin_3y)
        rows.append({
            "corp": corp,
            "is_us": corp == dl.OUR_COMPANY,
            "scale_q4": round(q4) if q4 is not None else None,
            "scale_q1": round(q1),
            "chg_pct": round(chg_pct),   # 规模变动幅度：四舍五入到整数（对齐报告）
            "perf_contrib": round(perf),
            "holding": round(holding),
            "new_issue": round(new),
            "ret_q": ret_q,
            "rank_q": f"{int(rk_q)}/{int(tot_q)}" if rk_q and tot_q else "-",
            "ret_3y": ret_3y,
            "rank_3y": f"{int(rk3_rank)}/{int(tot_3y)}" if rk3_rank and tot_3y else "-",
        })
    # 按当年业绩降序
    rows.sort(key=lambda r: r["ret_q"] if r["ret_q"] is not None else -999, reverse=True)
    for i, r in enumerate(rows, 1):
        r["seq"] = i
    return rows, _overview_kpi(rows)


def _overview_kpi(rows: list[dict]) -> dict:
    """模块一 KPI 行：我司规模排名、规模涨幅最大、业绩夺冠 —— 全部由 rows 派生。"""
    if not rows:
        return {"sample": 0}
    us = next((r for r in rows if r["is_us"]), None)
    scale_sorted = sorted(rows, key=lambda r: r["scale_q1"] or 0, reverse=True)
    growth = max(rows, key=lambda r: r["chg_pct"] if r["chg_pct"] is not None else -999)
    perf = rows[0]  # rows 已按 ret_q 降序
    return {
        "sample": len(rows),
        "our_rank": (scale_sorted.index(us) + 1) if us else None,
        "our_scale": us["scale_q1"] if us else None,
        "our_chg": us["chg_pct"] if us else None,
        "growth_corp": growth["corp"],
        "growth_pct": growth["chg_pct"],
        "growth_scale": growth["scale_q1"],
        "perf_corp": perf["corp"],
        "perf_ret": perf["ret_q"],
        "perf_3y": perf["ret_3y"],
    }


# ============================================================
# 模块二：同业持仓及变动分析
# ============================================================

def _board_allocation(pub_date: str, exclude_industry: bool = False) -> pd.DataFrame:
    """某季末各公司持仓，附加 board / market 列（未归一化，保留 pos_mkt_val）。

    口径：
    - 行业→板块严格取自"行业板块对应关系"sheet；行业为空的持仓**保留在分母**（left-join 语义），
      只是 board 为 NaN、不计入任一板块 → 六板块和 < 100%（与报告一致，未分类部分留白）。
    - 市场：港股 = .HK / 含"(港)"；其余(含 .SZ/.SH/.BJ 及海外如 .KS/.TW)→ A股。
      即 A股 = 全部非港股（海外因无申万行业不进六大板块，但计入 A股分母，与报告口径一致）。
    """
    h = dl.holdings(exclude_industry=exclude_industry)
    h = h[h["pub_date"] == pub_date].copy()
    bmap = dl.industry_board_map()
    h["board"] = h["industry"].map(bmap)               # 行业为空 → board=NaN，保留在分母
    def _market(sec: str) -> str:
        s = str(sec)
        if s.endswith(".HK") or "(港)" in s:
            return "港股"
        return "A股"                                    # 其余(含海外)→ A股
    h["market"] = h["sec_no"].map(_market)
    return h
    return h


def _board_row(alloc: pd.DataFrame, corp: str) -> dict | None:
    """单公司 8 值：六板块（占该公司股票市值合计，和为 100%）+ A股 + 港股。"""
    sub = alloc[alloc["corp"] == corp]
    total = sub["pos_mkt_val"].sum()
    if not total:
        return None
    row = {"corp": corp}
    for b in BOARDS:
        row[b] = float(sub.loc[sub["board"] == b, "pos_mkt_val"].sum() / total)
    for m in MARKETS:
        row[m] = float(sub.loc[sub["market"] == m, "pos_mkt_val"].sum() / total)
    return row


def _board_row_market(alloc: pd.DataFrame, corp: str) -> dict | None:
    """单公司 12 值：A股/港股各六板块占比，分母为全部权益(与 2.1 同口径，"拆分"语义)。
    A股六板块和 = A股占总权益比；港股六板块和 = 港股占总权益比。"""
    sub = alloc[alloc["corp"] == corp]
    if sub.empty:
        return None
    total = sub["pos_mkt_val"].sum()           # 与 2.1 同分母（全部权益，含空行业、仅剔海外）
    row = {"corp": corp}
    for m in MARKETS:
        for b in BOARDS:
            cell = sub[(sub["market"] == m) & (sub["board"] == b)]["pos_mkt_val"].sum()
            row[f"{m}_{b}"] = float(cell / total) if total else 0
    return row


def board_returns(market: str) -> dict:
    """各板块季度涨跌幅(指定市场)：行业收益率表中该市场下该板块所属行业的算术平均。

    market="A股" 用 CI0050* 中信A股行业；market="港股" 用 CIHK* 中信港股行业。
    """
    bmap = dl.industry_board_map()
    iret = dl.industry_return()          # {(市场, 行业名): 收益率}
    out = {}
    for b in BOARDS:
        vals = [iret[(market, ind)] for ind, bb in bmap.items()
                if bb == b and (market, ind) in iret and iret[(market, ind)] is not None]
        out[b] = (sum(vals) / len(vals)) if vals else None
    return out


# ---- 表 2.1：基金公司季度板块配置 ----
def board_table(pub_date: str | None = None) -> tuple[list[dict], list[dict]]:
    """六板块 + A股/港股，15 行 + 平均值 / 我司排名 / 工银瑞信（剔除行业基金）。"""
    _, LATEST_Q, _ = _q()
    pd_ = pub_date or LATEST_Q
    alloc = _board_allocation(pd_, exclude_industry=False)
    alloc_excl = _board_allocation(pd_, exclude_industry=True)
    rows = []
    for corp in peer_order():
        r = _board_row(alloc, corp)
        if r is None:
            continue
        r["is_us"] = corp == dl.OUR_COMPANY
        rows.append(r)
    if not rows:
        return [], []
    avg = {"corp": "平均值"}
    rank = {"corp": "我司排名"}
    for b in BOARDS + MARKETS:
        vals = [r[b] for r in rows]
        avg[b] = sum(vals) / len(vals)
        sorted_vals = sorted(vals, reverse=True)
        ours = next((r[b] for r in rows if r["corp"] == dl.OUR_COMPANY), None)
        rank[b] = sorted_vals.index(ours) + 1 if ours is not None else "-"
    us_excl = _board_row(alloc_excl, dl.OUR_COMPANY) or {b: 0 for b in BOARDS + MARKETS}
    us_excl["corp"] = "工银瑞信（剔除行业基金）"
    us_excl["is_us"] = True
    us_excl["is_excl"] = True
    return rows, [avg, rank, us_excl]


# ---- 表 2.2：基金公司季度板块配置（A股、港股拆分）----
def board_table_by_market(pub_date: str | None = None) -> tuple[list[dict], list[dict]]:
    """A股/港股各六板块，15 行 + 平均值 / 我司排名 / 工银瑞信（剔除行业基金）/ 板块季度涨跌幅。"""
    _, LATEST_Q, _ = _q()
    pd_ = pub_date or LATEST_Q
    alloc = _board_allocation(pd_, exclude_industry=False)
    alloc_excl = _board_allocation(pd_, exclude_industry=True)
    keys = [f"{m}_{b}" for m in MARKETS for b in BOARDS]
    rows = []
    for corp in peer_order():
        r = _board_row_market(alloc, corp)
        if r is None:
            continue
        r["is_us"] = corp == dl.OUR_COMPANY
        rows.append(r)
    if not rows:
        return [], []
    avg = {"corp": "平均值"}
    rank = {"corp": "我司排名"}
    for k in keys:
        vals = [r[k] for r in rows]
        avg[k] = sum(vals) / len(vals)
        sorted_vals = sorted(vals, reverse=True)
        ours = next((r[k] for r in rows if r["corp"] == dl.OUR_COMPANY), None)
        rank[k] = sorted_vals.index(ours) + 1 if ours is not None else "-"
    us_excl = _board_row_market(alloc_excl, dl.OUR_COMPANY) or {k: 0 for k in keys}
    us_excl["corp"] = "工银瑞信（剔除行业基金）"
    us_excl["is_us"] = True
    us_excl["is_excl"] = True
    brow = {"corp": "板块季度涨跌幅", "is_excl": False}
    for m in MARKETS:
        br = board_returns(m)                       # A股/港股 各自的板块涨跌幅
        for b in BOARDS:
            brow[f"{m}_{b}"] = br.get(b)
    return rows, [avg, rank, us_excl, brow]


# ---- 表 2.3：基金公司较上季度板块变化（剔除涨跌幅）----
def _corp_group_ret(prev_c: pd.DataFrame, iret: dict, group_col: str, groups: list[str]) -> dict:
    """公司上季各分组的收益率：组内个股所属行业收益率(行业收益率表, 按(市场,行业)查)的算术平均。"""
    ac = prev_c.copy()
    ac["gret"] = [iret.get((str(m), str(i))) for m, i in zip(ac["market"], ac["industry"])]
    out = {}
    for g in groups:
        sub = ac[ac[group_col] == g].dropna(subset=["gret"])
        out[g] = float(sub["gret"].mean()) if len(sub) else None
    return out


def _active(cur_c: pd.DataFrame, prev_c: pd.DataFrame, group_col: str, groups: list[str],
            sret: dict | None = None, gret: dict | None = None) -> dict | None:
    """剔除涨跌幅的占比变化（单组维度）。

    收益率来源：
    - gret 提供(外部板块收益率字典, 键=组)时直接用之(2.4 用市场板块收益率 board_returns)；
    - 否则用公司持仓个股收益加权 _corp_group_ret(2.3 板块/市场列, 已对齐报告)。
    分母全量(含 NaN/未分类资产): exp_tot = 各组预期市值 + 其余资产(收益0)；
    预期占比 = 预期市值 / exp_tot；剔除变动 = 实际季末占比(cv/cur_tot) − 预期占比。
    """
    if prev_c.empty or cur_c.empty:
        return None
    prev_tot = prev_c["pos_mkt_val"].sum()
    cur_tot = cur_c["pos_mkt_val"].sum()
    if prev_tot == 0 or cur_tot == 0:
        return None
    if gret is None:
        gret = _corp_group_ret(prev_c, sret, group_col, groups)
    exp_tot = 0.0
    for g in groups:
        pv = prev_c[prev_c[group_col] == g]["pos_mkt_val"].sum()
        r = gret.get(g)
        exp_tot += pv * (1 + r) if r is not None else pv
    # 其余(不在 groups 内的 NaN/未分类/海外)资产按收益0计入预期总市值
    pv_others = prev_c[~prev_c[group_col].isin(groups)]["pos_mkt_val"].sum()
    exp_tot += pv_others
    out = {}
    for g in groups:
        pv = prev_c[prev_c[group_col] == g]["pos_mkt_val"].sum()
        cv = cur_c[cur_c[group_col] == g]["pos_mkt_val"].sum()
        r = gret.get(g)
        exp_share = (pv * (1 + r) if r is not None else pv) / exp_tot if exp_tot else 0
        out[g] = (cv / cur_tot if cur_tot else 0) - exp_share
    return out


def _adjust_industry(cur_c: pd.DataFrame, prev_c: pd.DataFrame, iret: dict) -> float:
    """行业调整比例：(市场,行业) 复合分组，用市场行业收益率(行业收益率表 CI0050/CIHK)剔除涨跌幅，
    Σ|实际占比−预期占比| ÷2（换手率口径）。

    分母为全量股票市值(含行业为空的资产)，避免 notna 裁剪导致占比被动放大：
    - ct = 当期全部持仓市值；exp_tot = 上季有效行业按行业收益率再估 + 上季无行业资产(收益0)。
    - 预期季末 (市场,行业) 市值 = 上季该组市值 × (1 + 该市场该行业收益率)；
      预期占比 = 预期市值 / exp_tot；剔除变动 = 实际季末占比(cv/ct) − 预期占比。
    - 无行业资产(现金/未分类/海外)变动也计入调仓(视为一个特殊"行业")。
    A股行业与港股行业分开(复合键)，避免跨市场抵消。"""
    pt_total = prev_c["pos_mkt_val"].sum()
    ct = cur_c["pos_mkt_val"].sum()
    if pt_total == 0 or ct == 0:
        return 0.0
    pc_valid = prev_c[prev_c["industry"].notna()].copy()
    cc_valid = cur_c[cur_c["industry"].notna()].copy()
    pc_valid["mi"] = pc_valid["market"] + "_" + pc_valid["industry"].astype(str)
    cc_valid["mi"] = cc_valid["market"] + "_" + cc_valid["industry"].astype(str)
    mi = list(set(cc_valid["mi"]) | set(pc_valid["mi"]))
    # 预期总市值：有效行业按行业收益率再估 + 无行业资产按原值(收益0)
    exp_tot = 0.0
    pv_map, r_map = {}, {}
    for i in mi:
        m, ind = i.split("_", 1)
        pv = pc_valid[pc_valid["mi"] == i]["pos_mkt_val"].sum()
        r = iret.get((m, ind))
        pv_map[i] = pv; r_map[i] = r
        exp_tot += pv * (1 + r) if r is not None else pv
    pv_nan = prev_c[prev_c["industry"].isna()]["pos_mkt_val"].sum()
    exp_tot += pv_nan
    # 有效行业的占比变动
    s = 0.0
    for i in mi:
        cv = cc_valid[cc_valid["mi"] == i]["pos_mkt_val"].sum()
        cur_sh = cv / ct
        r = r_map[i]; pv = pv_map[i]
        exp_sh = pv * (1 + r) / exp_tot if r is not None and exp_tot else (pv / exp_tot if exp_tot else 0)
        s += abs(cur_sh - exp_sh)
    # 无行业资产(现金/未分类/海外)的变动也计入调仓
    cv_nan = cur_c[cur_c["industry"].isna()]["pos_mkt_val"].sum()
    s += abs(cv_nan / ct - (pv_nan / exp_tot if exp_tot else 0))
    return s / 2


def board_change_table() -> list[dict]:
    """六板块 + A股/港股 的剔除涨跌幅占比变化 + 行业调整比例；末行追加工银瑞信（剔除行业基金）。

    计算顺序：先在(市场,行业)层面算剔除变动(每个行业用自己的行业收益率 iret)，
    再按 bmap 汇总(签名和)到六大板块 / A股/港股。行业涨跌幅与公司持仓无关。"""
    _, LATEST_Q, PREV_Q = _q()
    cur = _board_allocation(LATEST_Q); prev = _board_allocation(PREV_Q)
    cur_e = _board_allocation(LATEST_Q, True); prev_e = _board_allocation(PREV_Q, True)
    iret = dl.industry_return()
    bmap = dl.industry_board_map()
    for df in (cur, prev, cur_e, prev_e):
        df["mi"] = df["market"].astype(str) + "_" + df["industry"].astype(str)
    gret_mi = {f"{m}_{ind}": v for (m, ind), v in iret.items() if v is not None}
    mi_keys = sorted(set(cur["mi"].dropna()) | set(prev["mi"].dropna()))
    board_inds = {b: [ind for ind, bb in bmap.items() if bb == b] for b in BOARDS}

    def _change(ca, pa, corp):
        prev_c = pa[pa["corp"] == corp]; cur_c = ca[ca["corp"] == corp]
        ai = _active(cur_c, prev_c, "mi", mi_keys, gret=gret_mi) or {}
        row = {"corp": corp}
        for b in BOARDS:
            row[b] = sum(ai.get(f"{m}_{ind}", 0) for m in MARKETS for ind in board_inds[b])
        row["adjust"] = _adjust_industry(cur_c, prev_c, iret)
        for m in MARKETS:
            row[m] = sum(ai.get(f"{m}_{ind}", 0) for ind in bmap.keys())
        return row

    rows = []
    for corp in peer_order():
        r = _change(cur, prev, corp)
        r["is_us"] = corp == dl.OUR_COMPANY
        rows.append(r)
    us_excl = _change(cur_e, prev_e, dl.OUR_COMPANY)
    us_excl["corp"] = "工银瑞信（剔除行业基金）"
    us_excl["is_us"] = True
    us_excl["is_excl"] = True
    rows.append(us_excl)
    return rows


# ---- 表 2.4：基金公司较上季度板块变化（A股、港股拆分）----
def board_change_table_by_market() -> list[dict]:
    """A股/港股各六板块的剔除涨跌幅占比变化；末两行追加 工银瑞信（剔除行业基金）/ 板块涨跌幅。
    行业层面计算: 先在(市场,行业)层面算剔除变动, 再按 bmap 汇总到(市场,板块)。"""
    _, LATEST_Q, PREV_Q = _q()
    cur = _board_allocation(LATEST_Q).copy(); prev = _board_allocation(PREV_Q).copy()
    cur_e = _board_allocation(LATEST_Q, True).copy(); prev_e = _board_allocation(PREV_Q, True).copy()
    iret = dl.industry_return()
    bmap = dl.industry_board_map()
    for df in (cur, prev, cur_e, prev_e):
        df["mi"] = df["market"].astype(str) + "_" + df["industry"].astype(str)
    gret_mi = {f"{m}_{ind}": v for (m, ind), v in iret.items() if v is not None}
    mi_keys = sorted(set(cur["mi"].dropna()) | set(prev["mi"].dropna()))
    board_inds = {b: [ind for ind, bb in bmap.items() if bb == b] for b in BOARDS}

    def _change(ca, pa, corp):
        prev_c = pa[pa["corp"] == corp]; cur_c = ca[ca["corp"] == corp]
        ai = _active(cur_c, prev_c, "mi", mi_keys, gret=gret_mi) or {}
        row = {"corp": corp}
        for m in MARKETS:
            for b in BOARDS:
                row[f"{m}_{b}"] = sum(ai.get(f"{m}_{ind}", 0) for ind in board_inds[b])
        return row

    rows = []
    for corp in peer_order():
        r = _change(cur, prev, corp)
        r["is_us"] = corp == dl.OUR_COMPANY
        rows.append(r)
    us_excl = _change(cur_e, prev_e, dl.OUR_COMPANY)
    us_excl["corp"] = "工银瑞信（剔除行业基金）"
    us_excl["is_us"] = True
    us_excl["is_excl"] = True
    rows.append(us_excl)
    brow = {"corp": "板块涨跌幅", "is_excl": False}
    for m in MARKETS:
        br = board_returns(m)                         # A股/港股 各自的板块涨跌幅
        for b in BOARDS:
            brow[f"{m}_{b}"] = br.get(b)
    rows.append(brow)
    return rows


def top10_holdings() -> list[dict]:
    """各公司季末前十大重仓股 + 季度收益率；末行追加工银瑞信（剔除行业基金）。

    口径（demo 近似）：按公司持仓明细市值降序取前 10；收益来自个股收益率表。
    报告口径为“各基金前十大重仓股加总”，本 demo 以公司持仓明细直接取。
    新进重仓：当季 top-10 中、上一季度(PREV_Q)公司持仓明细里未出现的个股（新建立的重仓仓位），
    模板中标红显示。仅有单季数据时无法判定，全部视为非新进。
    """
    _, LATEST_Q, PREV_Q = _q()
    sret = dl.stock_return()

    def _prev_secs(prev_hold: pd.DataFrame, corp: str) -> set[str]:
        if prev_hold is None or prev_hold.empty:
            return set()
        return set(prev_hold[prev_hold["corp"] == corp]["sec_no"].astype(str))

    def _row_for(hold: pd.DataFrame, corp: str, prev_hold: pd.DataFrame,
                 label: str | None = None, is_excl: bool = False) -> dict | None:
        sub = hold[hold["corp"] == corp].sort_values("pos_mkt_val", ascending=False).head(10)
        if sub.empty:
            return None
        prev_secs = _prev_secs(prev_hold, corp)
        stocks, rets = [], []
        for _, r in sub.iterrows():
            sno = str(r["sec_no"])
            ret = sret.get(sno)
            stocks.append({"name": r["sec_name"], "ret": ret, "is_new": sno not in prev_secs})
            if ret is not None:
                rets.append(ret)
        avg_ret = sum(rets) / len(rets) if rets else None
        return {
            "corp": label or corp, "is_us": corp == dl.OUR_COMPANY,
            "is_excl": is_excl,
            "stocks": stocks, "avg_ret": avg_ret,
        }

    h = dl.holdings()[dl.holdings()["pub_date"] == LATEST_Q].copy()
    h_excl = dl.holdings(exclude_industry=True)
    h_excl = h_excl[h_excl["pub_date"] == LATEST_Q].copy()
    # 上一季持仓，用于判定"新进重仓"
    prev_h = dl.holdings()
    prev_h = prev_h[prev_h["pub_date"].astype(str) == str(PREV_Q)].copy() if PREV_Q else prev_h.iloc[0:0]
    prev_h_excl = dl.holdings(exclude_industry=True)
    prev_h_excl = prev_h_excl[prev_h_excl["pub_date"].astype(str) == str(PREV_Q)].copy() if PREV_Q else prev_h_excl.iloc[0:0]
    rows = []
    for corp in peer_order():
        r = _row_for(h, corp, prev_h)
        if r is not None:
            rows.append(r)
    # 末行：工银瑞信（剔除行业基金）
    us_excl = _row_for(h_excl, dl.OUR_COMPANY, prev_h_excl,
                       label="工银瑞信（剔除行业基金）", is_excl=True)
    if us_excl is not None:
        us_excl["is_us"] = True
        rows.append(us_excl)
    return rows


def concentration_series() -> dict:
    """TOP20 个股 / TOP3 行业集中度时间序列。"""
    c = dl.concentration()
    out = {"top20": {}, "top3": {}}
    for t in ("top20", "top3_industry"):
        key = "top20" if t == "top20" else "top3"
        sub = c[c["type"] == t]
        for corp in peer_order():
            s = sub[sub["corp"] == corp].sort_values("pub_date")
            if s.empty:
                continue
            out[key][corp] = {
                "dates": list(s["pub_date"].astype(str)),
                "values": [round(float(v) * 100, 2) for v in s["value"]],
            }
    return out


def position_series() -> dict:
    """仓位时间序列：算术平均 / 规模加权。"""
    p = dl.position()
    out = {"arith": {}, "weighted": {}}
    for corp in peer_order():
        s = p[p["corp"] == corp].sort_values("pub_date")
        if s.empty:
            continue
        dates = list(s["pub_date"].astype(str))
        out["arith"][corp] = {"dates": dates, "values": [round(float(v) * 100, 2) for v in s["arith"]]}
        out["weighted"][corp] = {"dates": dates, "values": [round(float(v) * 100, 2) for v in s["weighted"]]}
    return out


# ============================================================
# 模块三：同业规模及变动分析
# ============================================================

def _fund_returns() -> tuple[pd.DataFrame, pd.DataFrame]:
    """基金逐季收益率与逐季规模（index=fund_code, columns=pub_date Timestamp）。

    收益率由单位净值 pct_change 得到；用于历史季度的业绩贡献估算。
    """
    ps = dl.product_scale()
    scale_fund = ps.pivot_table(index="fund_code", columns="pub_date", values="total_nav")
    nav = ps.pivot_table(index="fund_code", columns="pub_date", values="unit_nav").sort_index(axis=1)
    ret_fund = nav.pct_change(axis=1)
    return ret_fund, scale_fund


def scale_history() -> dict:
    """各公司逐季规模（亿元）+ 近五季度规模变动拆分（收益率上涨/持营/新发）。

    口径（同表 1.1）：
    - 规模 = 产品规模表 TOTAL_NAV 按公司求和（亿元）。季初 = 上一季度末。
    - 收益率上涨（业绩贡献）= Σ_f [季初规模_f × 涨跌幅_f]，涨跌幅优先用复权净值
      FUQUAN_UNIT_NAV 的(季末−季初)/季初（仅最新季可得），缺失回退单位净值 UNIT_NAV。
    - 新发 = 最新季在、上一季不在的基金，取其季末 TOTAL_NAV。
    - 持营 = Δ − 收益率上涨 − 新发（倒挤）。Δ = 季末 − 季初。
    """
    ps = dl.product_scale()
    all_q, LATEST_Q, PREV_Q = _q()
    all_q = all_q[-6:]          # 规模（亿元）列只保留最新 6 个季末，不随新数据叠加
    split_qs = all_q[-5:]
    scale = ps.groupby(["corp", "pub_date"])["total_nav"].sum().unstack("pub_date")
    ret_fund, scale_fund = _fund_returns()          # unit_nav pct_change, total_nav pivot
    corp_of_fund = ps.drop_duplicates("fund_code").set_index("fund_code")["corp"].to_dict()
    # 复权净值涨跌幅（仅最新季，nav_adjusted [PREV_Q, LATEST_Q]）
    fuquan_ret: dict[str, float] = {}
    nav = dl.nav_adjusted()
    nav_q = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)].copy()
    nav_q["fc_key"] = nav_q["fund_code"].map(_fc_key)
    for fc, sub in nav_q.groupby("fc_key"):
        vals = sub.sort_values("pub_date")["nav"].values
        if len(vals) >= 2 and vals[0] > 0:
            fuquan_ret[fc] = float(vals[-1] / vals[0] - 1)

    def _perf(corp, prev_ts, q_ts, is_latest):
        """Σ_f 季初规模 × 涨跌幅；涨跌幅 fuquan优先(仅latest)、回退 unit_nav。"""
        if prev_ts not in scale_fund.columns or q_ts not in ret_fund.columns:
            return None
        funds = [fc for fc in scale_fund.index if corp_of_fund.get(fc) == corp]
        sp = scale_fund.loc[funds, prev_ts].dropna()
        if sp.empty:
            return None
        r_unit = ret_fund.loc[sp.index, q_ts].dropna()
        perf, has = 0.0, False
        for fc in sp.index:
            nv = sp.loc[fc]
            fr = fuquan_ret.get(_fc_key(fc)) if is_latest else None
            if fr is None:
                fr = r_unit.get(fc)
            if fr is not None and pd.notna(fr) and pd.notna(nv):
                perf += float(nv) * float(fr)
                has = True
        return perf if has else None

    def _new(corp, prev_ts, q_ts):
        """新发：最新季在、上一季不在的基金，取其季末规模。"""
        funds = [fc for fc in scale_fund.index if corp_of_fund.get(fc) == corp]
        prev_f = set(scale_fund.loc[funds, prev_ts].dropna().index) if prev_ts in scale_fund.columns else set()
        cur_f = set(scale_fund.loc[funds, q_ts].dropna().index) if q_ts in scale_fund.columns else set()
        new_f = list(cur_f - prev_f)
        return float(scale_fund.loc[new_f, q_ts].sum()) if new_f else 0.0

    rows = []
    for corp in peer_order():
        if corp not in scale.index:
            continue
        q_series = {}
        for q in all_q:
            ts = pd.Timestamp(q)
            if ts in scale.columns and pd.notna(scale.loc[corp, ts]):
                q_series[q] = round(float(scale.loc[corp, ts]), 1)
            else:
                q_series[q] = None
        if not q_series.get(LATEST_Q):
            continue
        q_prev = q_series.get(PREV_Q)
        q_cur = q_series.get(LATEST_Q)
        chg = round((q_cur - q_prev) / q_prev * 100, 1) if q_prev else 0

        splits = {}
        for qstr in split_qs:
            pstr = all_q[all_q.index(qstr) - 1]
            s_q = q_series.get(qstr)
            s_p = q_series.get(pstr)
            is_latest = (qstr == LATEST_Q)
            new = _new(corp, pd.Timestamp(pstr), pd.Timestamp(qstr))
            if s_q is None or s_p is None:
                splits[qstr] = {"perf": None, "holding": None, "new": round(new)}
                continue
            delta = s_q - s_p
            perf = _perf(corp, pd.Timestamp(pstr), pd.Timestamp(qstr), is_latest)
            if perf is None:
                splits[qstr] = {"perf": None, "holding": None, "new": round(new)}
                continue
            hold = delta - new - perf
            splits[qstr] = {"perf": round(perf), "holding": round(hold), "new": round(new)}
        rows.append({
            "corp": corp, "is_us": corp == dl.OUR_COMPANY,
            "quarters": q_series, "chg_pct": chg, "splits": splits,
        })
    rows.sort(key=lambda r: r["quarters"].get(LATEST_Q, 0) or 0, reverse=True)
    return {"rows": rows, "quarters": all_q, "split_quarters": split_qs}


def scale_bin_chart() -> dict:
    """图3.1：各规模变化区间下基金数量 + 平均收益率。

    口径：仅取最新季与上一季均在的产品（上一季规模>0），按规模变动幅度(%)分箱；
    柱=基金数量，折线=箱内基金平均季度收益率（unit_nav 基金级口径）。
    """
    ps = dl.product_scale()
    _, LATEST_Q, PREV_Q = _q()
    ret_fund, _ = _fund_returns()
    latest_ts, prev_ts = pd.Timestamp(LATEST_Q), pd.Timestamp(PREV_Q)
    q4 = ps[ps["pub_date"] == prev_ts].set_index("fund_code")["total_nav"]
    q1 = ps[ps["pub_date"] == latest_ts].set_index("fund_code")["total_nav"]
    common = q1.index.intersection(q4.index)
    common = [fc for fc in common if pd.notna(q4[fc]) and q4[fc] > 0]
    if not common:
        return {"labels": [], "counts": [], "returns": []}
    chg = ((q1.loc[common] - q4.loc[common]) / q4.loc[common] * 100)
    fret = ret_fund[latest_ts] if latest_ts in ret_fund.columns else pd.Series(dtype=float)

    bins = [-1e9, -50, -30, -10, 0, 10, 30, 50, 100, 1e9]
    labels = ["<-50%", "-50~-30%", "-30~-10%", "-10~0%", "0~10%",
              "10~30%", "30~50%", "50~100%", ">100%"]
    cat = pd.cut(chg, bins=bins, labels=labels, right=True, include_lowest=True)
    counts, rets = [], []
    for lab in labels:
        fc_in = chg[cat == lab].index
        rv = [fret.get(fc) for fc in fc_in]
        rv = [float(v) for v in rv if pd.notna(v)]
        counts.append(int(len(fc_in)))
        rets.append(round(sum(rv) / len(rv) * 100, 2) if rv else None)
    return {"labels": labels, "counts": counts, "returns": rets}


def type_scale_change() -> dict:
    """图3.2：各类型产品最新季度规模变动（按事后分类，亿元）。

    口径：最新季与上一季均在的产品，按事后分类汇总 (q1−q4)，降序。
    """
    ps = dl.product_scale()
    pc = dl.post_classify()
    _, LATEST_Q, PREV_Q = _q()
    pc_latest = {_fc_key(k): v for k, v in
                 pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].items()}
    q4 = ps[ps["pub_date"] == pd.Timestamp(PREV_Q)].set_index("fund_code")["total_nav"]
    q1 = ps[ps["pub_date"] == pd.Timestamp(LATEST_Q)].set_index("fund_code")["total_nav"]
    common = q1.index.intersection(q4.index)
    delta = q1.loc[common] - q4.loc[common]
    types = [pc_latest.get(_fc_key(fc)) for fc in delta.index]
    df = pd.DataFrame({"type": types, "delta": delta.values}, index=delta.index).dropna(subset=["type"])
    grp = df.groupby("type")["delta"].sum().sort_values(ascending=False)
    return {"types": list(grp.index), "deltas": [round(float(v), 1) for v in grp.values]}


def product_top10() -> tuple[list[dict], list[dict]]:
    """一季度规模增长 TOP10 / 缩减 TOP10 产品。

    口径（demo 近似）：按 2025Q4→2026Q1 规模变动排序。
    收益率与最大回撤基于产品复权净值表计算（仅在该表内有净值的产品）。
    """
    ps = dl.product_scale()
    pc = dl.post_classify()
    _, LATEST_Q, PREV_Q = _q()
    # 事后分类：取最新一条作为产品类型
    pc_latest = pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].to_dict()

    nav = dl.nav_adjusted()
    # 仅取最新季度区间内净值用于计算收益率与回撤，按归一化基金代码分组
    nav_q1 = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)].copy()
    nav_q1["fc_key"] = nav_q1["fund_code"].map(_fc_key)
    nav_groups = {k: g.sort_values("pub_date")["nav"].values for k, g in nav_q1.groupby("fc_key")}

    def _fund_metrics(fund_code: str) -> tuple[float | None, float | None]:
        vals = nav_groups.get(_fc_key(fund_code))
        if vals is None or len(vals) < 2:
            return None, None
        ret = vals[-1] / vals[0] - 1
        peak = vals[0]
        max_dd = 0.0
        for v in vals:
            if v > peak:
                peak = v
            dd = v / peak - 1
            if dd < max_dd:
                max_dd = dd
        return ret, max_dd

    q4 = ps[ps["pub_date"] == pd.Timestamp(PREV_Q)].set_index("fund_code")["total_nav"]
    q1 = ps[ps["pub_date"] == pd.Timestamp(LATEST_Q)].set_index("fund_code")["total_nav"]
    common = q1.index.intersection(q4.index)
    delta = (q1.loc[common] - q4.loc[common])

    ps_u = ps.drop_duplicates("fund_code")
    name_map = ps_u.set_index("fund_code")["fund_name"].to_dict()
    corp_map = ps_u.set_index("fund_code")["corp"].to_dict()
    estab_map = ps_u.set_index("fund_code")["estab_date"].to_dict()
    # 事后分类键归一化
    pc_key_map = {_fc_key(k): v for k, v in pc_latest.items()}

    def _build(fc) -> dict:
        ret, dd = _fund_metrics(fc)
        return {
            "corp": corp_map.get(fc, ""),
            "name": name_map.get(fc, ""),
            "estab": str(estab_map.get(fc, ""))[:10] if pd.notna(estab_map.get(fc)) else "",
            "type": pc_key_map.get(_fc_key(fc), "-"),
            "delta": round(float(delta.loc[fc]), 1),
            "q4": round(float(q4.loc[fc]), 1),
            "q1": round(float(q1.loc[fc]), 1),
            "ret": round(ret * 100, 2) if ret is not None else None,
            "max_dd": round(dd * 100, 2) if dd is not None else None,
        }

    growth = [ _build(fc) for fc in delta.nlargest(10).index ]
    decline = [ _build(fc) for fc in delta.nsmallest(10).index ]
    return growth, decline


def return_vs_drawdown() -> list[dict]:
    """各公司最新季 规模加权收益率 vs 规模加权最大回撤 散点。

    口径（期初规模加权，基金级，两轴同池）：
      权重 w_f = 该基金期初规模 = 产品规模表 PREV_Q 行的 TOTAL_NAV。
      基金收益 ret_f = nav_末 / nav_初 − 1（最新季区间复权净值首末比）。
      基金回撤 max_dd_f = min_t (nav_t / peak_t − 1)，peak_t 为截至 t 的历史最高。
      公司加权收益率 ret_c = Σ(ret_f · w_f) / Σ w_f
      公司加权回撤 dd_c    = Σ(max_dd_f · w_f) / Σ w_f
    ret_f 与 max_dd_f 取自同一只基金同一区间序列，成分股一致；仅含期初规模>0 的产品。
    """
    _, LATEST_Q, PREV_Q = _q()
    nav = dl.nav_adjusted()
    nav_q1 = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)].copy()

    ps = dl.product_scale()
    prev_nav = ps[ps["pub_date"] == pd.Timestamp(PREV_Q)].set_index("fund_code")["total_nav"]
    fund_nav = {_fc_key(fc): float(v) for fc, v in prev_nav.items() if pd.notna(v) and v > 0}
    fund_corp = {_fc_key(fc): corp for fc, corp in
                 ps.drop_duplicates("fund_code").set_index("fund_code")["corp"].items()}
    nav_q1["fc_key"] = nav_q1["fund_code"].map(_fc_key)

    corp_w = defaultdict(lambda: {"w_dd": 0.0, "w_ret": 0.0, "w": 0.0})
    for fc, sub in nav_q1.groupby("fc_key"):
        corp = fund_corp.get(fc)
        if corp not in dl.peer_set():
            continue
        w = fund_nav.get(fc)
        if not w or w <= 0:
            continue
        vals = sub.sort_values("pub_date")["nav"].values
        if len(vals) < 2:
            continue
        ret_f = vals[-1] / vals[0] - 1
        peak = vals[0]; max_dd = 0.0
        for v in vals:
            if v > peak: peak = v
            dd = v / peak - 1
            if dd < max_dd: max_dd = dd
        corp_w[corp]["w_ret"] += ret_f * w
        corp_w[corp]["w_dd"] += max_dd * w
        corp_w[corp]["w"] += w

    rows = []
    for corp in peer_order():
        m = corp_w.get(corp)
        if not m or m["w"] == 0:
            continue
        rows.append({
            "corp": corp, "is_us": corp == dl.OUR_COMPANY,
            "ret": round(m["w_ret"] / m["w"] * 100, 2),
            "dd": round(m["w_dd"] / m["w"] * 100, 2),
        })
    return rows


def yongying_products() -> list[dict]:
    """永赢产品规模变动及业绩情况表（demo 近似）。"""
    ps = dl.product_scale()
    corp_ps = ps[ps["corp"] == "永赢"].copy()
    pc = dl.post_classify()
    _, LATEST_Q, PREV_Q = _q()
    pc_latest = pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].to_dict()
    nav = dl.nav_adjusted()
    nav_q1 = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)].copy()
    nav_q1["fc_key"] = nav_q1["fund_code"].map(_fc_key)
    nav_groups = {k: g.sort_values("pub_date")["nav"].values for k, g in nav_q1.groupby("fc_key")}
    pc_key_map = {_fc_key(k): v for k, v in pc_latest.items()}

    q4 = corp_ps[corp_ps["pub_date"] == pd.Timestamp(PREV_Q)].set_index("fund_code")["total_nav"]
    q1 = corp_ps[corp_ps["pub_date"] == pd.Timestamp(LATEST_Q)].set_index("fund_code")["total_nav"]
    # 较年初变动：年初 = 最新季度所在年的上一年 12-31；该季不在数据中时退化为最早可得季度
    all_q = dl.quarters()
    year_start_q = f"{int(LATEST_Q[:4]) - 1}-12-31"
    if year_start_q not in all_q:
        year_start_q = all_q[0] if all_q else PREV_Q
    q0 = corp_ps[corp_ps["pub_date"] == pd.Timestamp(year_start_q)].set_index("fund_code")["total_nav"]
    delta = q1.sub(q0, fill_value=0)  # 对齐 q1；年初不存在的基金视作从 0 增长

    corp_u = corp_ps.drop_duplicates("fund_code")
    name_map = corp_u.set_index("fund_code")["fund_name"].to_dict()
    estab_map = corp_u.set_index("fund_code")["estab_date"].to_dict()

    rows = []
    for fc in delta.sort_values(ascending=False).index:
        vals = nav_groups.get(_fc_key(fc))
        ret = dd = None
        if vals is not None and len(vals) >= 2:
            ret = vals[-1] / vals[0] - 1
            peak = vals[0]; max_dd = 0.0
            for v in vals:
                if v > peak: peak = v
                d = v / peak - 1
                if d < max_dd: max_dd = d
            dd = max_dd
        q4v = q4.get(fc)
        rows.append({
            "name": name_map.get(fc, ""), "code": fc,
            "estab": str(estab_map.get(fc, ""))[:10] if pd.notna(estab_map.get(fc)) else "",
            "type": pc_key_map.get(_fc_key(fc), "-"),
            "q4": round(float(q4v), 1) if pd.notna(q4v) else None,
            "q1": round(float(q1.get(fc)), 1) if pd.notna(q1.get(fc)) else None,
            "delta": round(float(delta.loc[fc]), 1),
            "ret": round(ret * 100, 2) if ret is not None else None,
            "dd": round(dd * 100, 2) if dd is not None else None,
        })
    return rows[:15]  # 取变动较大的前 15 只


def product_layout() -> dict:
    """永赢 vs 工银瑞信 产品布局规模变化（按事后分类堆叠，demo 近似）。

    口径：按产品事后分类汇总各季规模。
    """
    ps = dl.product_scale()
    pc = dl.post_classify()
    # fund_code -> 事后分类（归一化键匹配）
    pc_latest = {_fc_key(k): v for k, v in
                 pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].items()}
    ps = ps.copy()
    ps["post_type"] = ps["fund_code"].map(_fc_key).map(pc_latest)
    ps = ps.dropna(subset=["post_type"])

    out = {}
    for corp in ("永赢", "工银瑞信"):
        sub = ps[ps["corp"] == corp]
        pivot = (sub.groupby(["pub_date", "post_type"])["total_nav"].sum().unstack("post_type").fillna(0))
        # 按总量排序类型
        types = pivot.sum().sort_values(ascending=False).index.tolist()
        out[corp] = {
            "quarters": [str(d.date()) for d in pivot.index],
            "types": types,
            "series": {t: [round(float(v), 1) for v in pivot[t]] for t in types},
        }
    return out


if __name__ == "__main__":
    ov, kpi = company_overview()
    print(f"overview: {len(ov)} rows; top={ov[0]['corp']} ret={ov[0]['ret_q']}")
    print(f"kpi: {kpi}")
    bt, extra = board_table()
    print(f"board_table: {len(bt)} corps")
    tc = board_change_table()
    print(f"board_change: {len(tc)} corps")
    t10 = top10_holdings()
    print(f"top10: {len(t10)} corps; first={t10[0]['corp']} stocks={len(t10[0]['stocks'])}")
    cs = concentration_series()
    print(f"concentration corps(top20)={len(cs['top20'])}")
    sh = scale_history()
    print(f"scale_history corps={len(sh['rows'])}")
    g, d = product_top10()
    print(f"top10 growth={len(g)} decline={len(d)}; g0={g[0]['name']} delta={g[0]['delta']}")
    rvd = return_vs_drawdown()
    print(f"return_vs_drawdown={len(rvd)}")
    yy = yongying_products()
    print(f"yongying={len(yy)}")
    pl = product_layout()
    print(f"layout: 永赢 types={len(pl['永赢']['types'])}, 工银 types={len(pl['工银瑞信']['types'])}")


# ============================================================
# 模块三 3.4：公司通用分析模板（General Template）
# ============================================================

def company_profile(corp: str) -> dict:
    """3.4 公司通用分析（本季度）。"""
    ps = dl.product_scale()
    pc = dl.post_classify()
    nav = dl.nav_adjusted()
    _, LATEST_Q, PREV_Q = _q()
    return _company_profile_internal(corp, ps, pc, nav, LATEST_Q, PREV_Q)


def _company_profile_internal(corp, ps, pc, nav, LATEST_Q, PREV_Q) -> dict:
    """公司通用分析内部实现，供 company_profile 和工银瑞信对比调用。"""
    sub = ps[(ps["corp"] == corp) & (ps["pub_date"] == pd.Timestamp(LATEST_Q))].copy()
    if sub.empty:
        return {"corp": corp, "total": 0}

    total = float(sub["total_nav"].sum())
    sub_q4 = ps[(ps["corp"] == corp) & (ps["pub_date"] == pd.Timestamp(PREV_Q))].copy()

    # 事后分类映射
    pc_latest = {_fc_key(k): v for k, v in
                 pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].items()}

    # ===== 板块A：产品规模画像 =====
    top = sub.sort_values("total_nav", ascending=False).head(15)
    top_products = [{
        "name": r["fund_name"], "code": str(r["fund_code"]),
        "scale": round(float(r["total_nav"]), 2),
        "pct": round(float(r["total_nav"]) / total * 100, 2) if total else 0,
    } for _, r in top.iterrows()]

    sorted_scales = sub.sort_values("total_nav", ascending=False)["total_nav"].tolist()
    def cr(n):
        return round(sum(sorted_scales[:n]) / total * 100, 1) if total and len(sorted_scales) >= n else None
    concentration = {"cr1": cr(1), "cr5": cr(5), "cr10": cr(10),
                     "product_count": len(sub), "total": round(total, 2)}

    sub["pc_key"] = sub["fund_code"].map(_fc_key)
    sub["ptype"] = sub["pc_key"].map(pc_latest)
    grp = sub.dropna(subset=["ptype"]).groupby("ptype")["total_nav"].sum().sort_values(ascending=False)
    type_composition = [{
        "type": t, "scale": round(float(v), 2),
        "pct": round(float(v) / total * 100, 2) if total else 0,
    } for t, v in grp.items()]

    # ===== 板块B：产品增长来源 =====
    q4_map = sub_q4.set_index("fund_code")["total_nav"]
    sub["q4_scale"] = sub["fund_code"].map(q4_map).fillna(0)
    sub["delta"] = sub["total_nav"] - sub["q4_scale"]
    sub["delta_pct"] = sub.apply(
        lambda r: round(float(r["delta"]) / r["q4_scale"] * 100, 2) if r["q4_scale"] and r["q4_scale"] > 0 else None, axis=1)

    # 复权净值算收益率和最大回撤（最新季区间）
    nav_q = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)].copy()
    nav_q["fc_key"] = nav_q["fund_code"].map(_fc_key)
    fund_metrics = {}
    for fc, s in nav_q.groupby("fc_key"):
        vals = s.sort_values("pub_date")["nav"].values
        if len(vals) >= 2 and vals[0] > 0:
            ret = float(vals[-1] / vals[0] - 1)
            peak = vals[0]; max_dd = 0.0
            for v in vals:
                if v > peak: peak = v
                dd = v / peak - 1
                if dd < max_dd: max_dd = dd
            fund_metrics[fc] = {"ret": ret, "dd": max_dd}
    sub["ret"] = sub["fund_code"].map(_fc_key).map(lambda k: fund_metrics.get(k, {}).get("ret"))
    sub["dd"] = sub["fund_code"].map(_fc_key).map(lambda k: fund_metrics.get(k, {}).get("dd"))

    growth = sub[sub["q4_scale"] > 0].sort_values("delta", ascending=False).head(10)
    def _prod_row(r):
        return {
            "name": r["fund_name"], "corp": corp,
            "scale": round(float(r["total_nav"]), 2),
            "q4": round(float(r["q4_scale"]), 2),
            "delta": round(float(r["delta"]), 2),
            "delta_pct": float(r["delta_pct"]) if pd.notna(r["delta_pct"]) else None,
            "ret": round(float(r["ret"]) * 100, 2) if pd.notna(r["ret"]) else None,
        }
    growth_products = [_prod_row(r) for _, r in growth.iterrows()]

    scatter_data = sub[(sub["q4_scale"] > 0) & sub["ret"].notna() & sub["dd"].notna()][["fund_name", "ret", "dd"]].copy()
    scatter_points = [{"name": r["fund_name"],
                       "ret": round(float(r["ret"]) * 100, 2),
                       "dd": round(float(r["dd"]) * 100, 2)}
                      for _, r in scatter_data.iterrows()]

    # ===== 板块C：产品布局分析 =====
    corp_all_q = ps[ps["corp"] == corp].copy()
    corp_all_q["pc_key"] = corp_all_q["fund_code"].map(_fc_key)
    corp_all_q["ptype"] = corp_all_q["pc_key"].map(pc_latest)
    corp_all_q = corp_all_q.dropna(subset=["ptype"])
    layout_pivot = corp_all_q.groupby(["pub_date", "ptype"])["total_nav"].sum().unstack("ptype").fillna(0)
    layout_types = layout_pivot.sum().sort_values(ascending=False).index.tolist()
    layout = {
        "quarters": [str(d.date()) for d in layout_pivot.index],
        "types": layout_types,
        "series": {t: [round(float(v), 2) for v in layout_pivot[t]] for t in layout_types},
    }
    # 类型变动明细表
    type_change = []
    for t in layout_types:
        q4_val = layout_pivot[t].iloc[-2] if len(layout_pivot) >= 2 else 0
        q1_val = layout_pivot[t].iloc[-1]
        delta = q1_val - q4_val
        type_change.append({
            "type": t, "q4": round(float(q4_val), 2), "q1": round(float(q1_val), 2),
            "delta": round(float(delta), 2),
            "pct": round(float(delta / q4_val * 100), 2) if q4_val and q4_val > 0 else None,
        })

    # ===== 板块D：产品特征分析 =====
    sub["estab_years"] = sub.apply(
        lambda r: round((pd.Timestamp(LATEST_Q) - r["estab_date"]).days / 365.25, 1)
        if pd.notna(r["estab_date"]) else None, axis=1)
    sub["ptype_short"] = sub["ptype"]
    scatter_age = sub[sub["estab_years"].notna()][["fund_name", "estab_years", "total_nav", "ptype_short"]].copy()
    scatter_age_points = [{"name": r["fund_name"], "years": float(r["estab_years"]),
                           "scale": round(float(r["total_nav"]), 2), "type": r["ptype_short"]}
                          for _, r in scatter_age.iterrows()]

    bins = [0, 10, 50, 100, 1e9]
    bin_labels = ["<10亿", "10-50亿", "50-100亿", ">100亿"]
    sub["bin"] = pd.cut(sub["total_nav"], bins=bins, labels=bin_labels, right=True, include_lowest=True)
    hist = sub.groupby("bin", observed=False).size().reindex(bin_labels, fill_value=0)
    histogram = [{"label": l, "count": int(hist[l])} for l in bin_labels]

    # ===== 板块E：总结 =====
    insights = []
    # 1. 产品结构
    cr5 = concentration["cr5"]
    if cr5 and cr5 > 50:
        insights.append(f"CR5={cr5}%，高度依赖前5大产品，产品集中度高")
    elif cr5 and cr5 < 30:
        insights.append(f"CR5={cr5}%，产品分散均衡，无单一依赖")
    else:
        insights.append(f"CR5={cr5}%，头部产品有一定集中度")
    # 2. 增长来源
    if growth_products:
        g0 = growth_products[0]
        driver = "业绩驱动" if g0["ret"] and g0["ret"] > 0 else "非业绩驱动"
        insights.append(f"增长TOP1：{g0['name']}（+{g0['delta']}亿），属{driver}")
    # 3. 布局方向
    if type_change:
        tc_sorted = sorted(type_change, key=lambda x: x["delta"], reverse=True)
        biggest = tc_sorted[0]
        insights.append(f"布局变化最大：{biggest['type']}（变动{biggest['delta']:+.1f}亿）")
    # 4. 增长持续性
    big_count = sum(1 for s in sorted_scales if s and s > 50)
    insights.append(f">50亿产品{big_count}只，腰部力量{'强' if big_count >= 3 else '弱'}")

    # 工银瑞信对比数据（始终显示）
    us_data = {}
    if corp != dl.OUR_COMPANY:
        us_data = _company_profile_internal(dl.OUR_COMPANY, ps, pc, nav, LATEST_Q, PREV_Q)

    return {
        "corp": corp,
        "total": round(total, 2),
        "product_count": len(sub),
        "latest_q_label": LATEST_Q[:7],
        # 板块A
        "top_products": top_products,
        "concentration": concentration,
        "type_composition": type_composition,
        # 板块B
        "growth_products": growth_products,
        "scatter_points": scatter_points,
        # 板块C
        "layout": layout,
        "type_change": type_change,
        # 板块D
        "scatter_age_points": scatter_age_points,
        "histogram": histogram,
        "us_histogram": us_data.get("histogram") if us_data else histogram,
        # 板块E
        "insights": insights,
        # 工银瑞信对比
        "us_type_composition": us_data.get("type_composition") if us_data else type_composition,
        "us_scatter_points": us_data.get("scatter_points") if us_data else scatter_points,
        "us_layout": us_data.get("layout") if us_data else layout,
    }
