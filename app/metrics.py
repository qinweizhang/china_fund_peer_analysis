"""业务指标计算层。

将 data_loader 的原始数据加工为三大模块所需的展示数据。
所有口径在 docstring 中标注；与报告 PDF 不完全一致处均注明“demo 近似”。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd

from . import data_loader as dl

BOARDS = ["TMT", "金融地产", "消费", "新能源及制造", "周期", "医药"]
MARKETS = ["A股", "港股"]


def _q() -> tuple[list[str], str, str]:
    """(全部季度, 最新季度, 上一季度) —— 从激活数据集派生，跨季度通用。"""
    qs = dl.quarters()
    return qs, (qs[-1] if qs else None), (qs[-2] if len(qs) > 1 else None)


def _fc_key(code) -> str | None:
    """归一化基金代码：'000001.OF' / '000001' / '1' -> '1'。用于跨表匹配。"""
    if code is None:
        return None
    s = str(code).strip().replace(".OF", "").replace(".of", "")
    try:
        return str(int(s))
    except (ValueError, TypeError):
        return s


# ============================================================
# 模块一：同业业绩及规模概况
# ============================================================

def company_overview() -> list[dict]:
    """十五家公司权益规模及业绩总览表。

    口径（demo 近似）：
    - 规模：产品规模表 TOTAL_NAV 按公司求和（亿元，全口径，未按偏股过滤）。
    - 业绩：权益银河排名表 POINTRATE（2026 当年 / 2024-2026 三年）。
    - 规模变动拆分：Δ = Q1-Q4；新发 = 当季新成立基金 Q1 规模；
      业绩贡献 = Q4规模 × 当季收益率；持营 = Δ - 新发 - 业绩贡献（剩余归持营）。
    """
    rk = dl.ranking()
    ps = dl.product_scale()
    _, LATEST_Q, PREV_Q = _q()

    # 规模（亿元）—— TOTAL_NAV 本身即亿元单位
    scale = ps.groupby(["corp", "pub_date"])["total_nav"].sum().unstack("pub_date").round(0)
    # 当季新发规模（亿元）：发行日期落在最新季度内的基金，取其最新季末规模
    latest_per = pd.Period(LATEST_Q, freq="Q")
    _issue_q = pd.PeriodIndex(ps["issue_date"], freq="Q")
    new_issue = (
        ps[ps["issue_date"].notna() & (_issue_q == latest_per)]
        .groupby("corp")["total_nav"].sum()
    ).round(0)

    def _ret_by_end(corp: str, end_q: str) -> tuple[float | None, int | None, int | None]:
        """取排名表 end == end_q 的行（最新季度收益率，跨季度通用）。"""
        sub = rk[(rk["corp"] == corp) & (rk["end"].astype(str) == end_q)]
        if sub.empty:
            return None, None, None
        r = sub.iloc[0]
        return float(r["return"]), int(r["rank"]) if pd.notna(r["rank"]) else None, \
               int(r["rank_total"]) if pd.notna(r["rank_total"]) else None

    def _ret_by_begin(corp: str, begin: str) -> tuple[float | None, int | None, int | None]:
        sub = rk[(rk["corp"] == corp) & (rk["begin"].astype(str) == begin)]
        if sub.empty:
            return None, None, None
        r = sub.iloc[0]
        return float(r["return"]), int(r["rank"]) if pd.notna(r["rank"]) else None, \
               int(r["rank_total"]) if pd.notna(r["rank_total"]) else None

    rows = []
    for corp in dl.FIFTEEN:
        q4 = scale.loc[corp, pd.Timestamp(PREV_Q)] if corp in scale.index and pd.Timestamp(PREV_Q) in scale.columns else None
        q1 = scale.loc[corp, pd.Timestamp(LATEST_Q)] if corp in scale.index and pd.Timestamp(LATEST_Q) in scale.columns else None
        if q4 is None or q1 is None:
            continue
        delta = q1 - q4
        chg_pct = (delta / q4) if q4 else 0
        ret_q, rk_q, tot_q = _ret_by_end(corp, LATEST_Q)
        # 多年收益率：取 begin 早于最新季度初 2 年以上的行（默认数据为 2024-01-01）
        begin_3y = f"{pd.Timestamp(LATEST_Q).year - 2}-01-01"
        ret_3y, rk3_rank, tot_3y = _ret_by_begin(corp, begin_3y)
        perf_contrib = (q4 * ret_q) if (q4 and ret_q is not None) else 0
        new = float(new_issue.get(corp, 0) or 0)
        holding = delta - new - perf_contrib
        rows.append({
            "corp": corp,
            "is_us": corp == dl.OUR_COMPANY,
            "scale_q4": round(q4),
            "scale_q1": round(q1),
            "chg_pct": round(chg_pct * 100, 1),
            "perf_contrib": round(perf_contrib),
            "holding": round(holding),
            "new_issue": round(new),
            "ret_q": ret_q,
            "rank_q": f"{int(rk_q)}/{int(tot_q)}" if rk_q and tot_q else "-",
            "ret_3y": ret_3y,
            "rank_3y": f"{int(rk3_rank)}/{int(tot_3y)}" if rk3_rank and tot_3y else "-",
        })
    # 按最新季度业绩降序
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

    口径：持仓个股按行业→板块映射；市场依证券代码后缀（.HK 为港股，其余 A股）。
    """
    h = dl.holdings(exclude_industry=exclude_industry)
    h = h[h["pub_date"] == pub_date].copy()
    bmap = dl.industry_board_map()
    h["board"] = h["industry"].map(bmap)
    h = h.dropna(subset=["board"])
    def _market(sec: str) -> str:
        s = str(sec)
        if s.endswith(".HK") or "(港)" in s:
            return "港股"
        return "A股"
    h["market"] = h["sec_no"].map(_market)
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
    """单公司 12 值：A股/港股各自六板块占比（分母为该市场市值合计，和为 100%）。"""
    sub = alloc[alloc["corp"] == corp]
    if sub.empty:
        return None
    row = {"corp": corp}
    for m in MARKETS:
        msub = sub[sub["market"] == m]
        mtot = msub["pos_mkt_val"].sum()
        for b in BOARDS:
            row[f"{m}_{b}"] = float(msub.loc[msub["board"] == b, "pos_mkt_val"].sum() / mtot) if mtot else 0
    return row


def board_returns() -> dict:
    """各板块季度涨跌幅：行业收益率表中该板块所属行业的算术平均。"""
    bmap = dl.industry_board_map()
    iret = dl.industry_return()
    out = {}
    for b in BOARDS:
        vals = [iret[ind] for ind, bb in bmap.items() if bb == b and ind in iret and iret[ind] is not None]
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
    for corp in dl.FIFTEEN:
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
    for corp in dl.FIFTEEN:
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
    br = board_returns()
    brow = {"corp": "板块季度涨跌幅", "is_excl": False}
    for m in MARKETS:
        for b in BOARDS:
            brow[f"{m}_{b}"] = br.get(b)
    return rows, [avg, rank, us_excl, brow]


# ---- 表 2.3：基金公司较上季度板块变化（剔除涨跌幅）----
def board_change_table() -> list[dict]:
    """六板块 + A股/港股 的占比变化 + 行业调整比例；末行追加工银瑞信（剔除行业基金）。"""
    _, LATEST_Q, PREV_Q = _q()
    cur = _board_allocation(LATEST_Q); prev = _board_allocation(PREV_Q)
    cur_e = _board_allocation(LATEST_Q, True); prev_e = _board_allocation(PREV_Q, True)

    def _change(cur_a, prev_a, corp):
        c = _board_row(cur_a, corp) or {b: 0 for b in BOARDS + MARKETS}
        p = _board_row(prev_a, corp) or {b: 0 for b in BOARDS + MARKETS}
        row = {"corp": corp}
        diffs = []
        for b in BOARDS + MARKETS:
            d = (c.get(b, 0) or 0) - (p.get(b, 0) or 0)
            row[b] = d
            diffs.append(abs(d))
        row["adjust"] = sum(diffs)
        return row

    rows = []
    for corp in dl.FIFTEEN:
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
    """A股/港股各六板块的占比变化；末两行追加 工银瑞信（剔除行业基金）/ 板块涨跌幅。"""
    _, LATEST_Q, PREV_Q = _q()
    cur = _board_allocation(LATEST_Q); prev = _board_allocation(PREV_Q)
    cur_e = _board_allocation(LATEST_Q, True); prev_e = _board_allocation(PREV_Q, True)
    keys = [f"{m}_{b}" for m in MARKETS for b in BOARDS]

    def _change(cur_a, prev_a, corp):
        c = _board_row_market(cur_a, corp) or {k: 0 for k in keys}
        p = _board_row_market(prev_a, corp) or {k: 0 for k in keys}
        row = {"corp": corp}
        for k in keys:
            row[k] = (c.get(k, 0) or 0) - (p.get(k, 0) or 0)
        return row

    rows = []
    for corp in dl.FIFTEEN:
        r = _change(cur, prev, corp)
        r["is_us"] = corp == dl.OUR_COMPANY
        rows.append(r)
    us_excl = _change(cur_e, prev_e, dl.OUR_COMPANY)
    us_excl["corp"] = "工银瑞信（剔除行业基金）"
    us_excl["is_us"] = True
    us_excl["is_excl"] = True
    rows.append(us_excl)
    br = board_returns()
    brow = {"corp": "板块涨跌幅", "is_excl": False}
    for m in MARKETS:
        for b in BOARDS:
            brow[f"{m}_{b}"] = br.get(b)
    rows.append(brow)
    return rows


def top10_holdings() -> list[dict]:
    """各公司季末前十大重仓股 + 季度收益率；末行追加工银瑞信（剔除行业基金）。

    口径（demo 近似）：按公司持仓明细市值降序取前 10；收益来自个股收益率表。
    报告口径为“各基金前十大重仓股加总”，本 demo 以公司持仓明细直接取。
    """
    _, LATEST_Q, _ = _q()
    sret = dl.stock_return()

    def _row_for(hold: pd.DataFrame, corp: str, label: str | None = None,
                 is_excl: bool = False) -> dict | None:
        sub = hold[hold["corp"] == corp].sort_values("pos_mkt_val", ascending=False).head(10)
        if sub.empty:
            return None
        stocks, rets = [], []
        for _, r in sub.iterrows():
            ret = sret.get(str(r["sec_no"]))
            stocks.append({"name": r["sec_name"], "ret": ret})
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
    rows = []
    for corp in dl.FIFTEEN:
        r = _row_for(h, corp)
        if r is not None:
            rows.append(r)
    # 末行：工银瑞信（剔除行业基金）
    us_excl = _row_for(h_excl, dl.OUR_COMPANY, label="工银瑞信（剔除行业基金）", is_excl=True)
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
        for corp in dl.FIFTEEN:
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
    for corp in dl.FIFTEEN:
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


def _perf_fundlevel(corp, prev_ts, q_ts, ret_fund, scale_fund, corp_of_fund) -> float | None:
    """基金级业绩贡献：Σ_f (上季规模_f × 当季收益率_f)，仅限该公司旗下基金。"""
    if q_ts not in ret_fund.columns or prev_ts not in scale_fund.columns:
        return None
    funds = [fc for fc in scale_fund.index if corp_of_fund.get(fc) == corp]
    if not funds:
        return None
    sp = scale_fund.loc[funds, prev_ts].dropna()
    r = ret_fund.loc[sp.index, q_ts].dropna() if q_ts in ret_fund.columns else None
    if r is None:
        return None
    common = sp.index.intersection(r.index)
    if not len(common):
        return None
    return float((sp.loc[common] * r.loc[common]).sum())


def scale_history() -> dict:
    """各公司逐季规模（亿元）+ 近五季度规模变动拆分（收益率上涨/持营/新发）。

    口径：
    - 规模 = 产品规模表 TOTAL_NAV 按公司求和（亿元）。
    - 拆分覆盖近 5 个季度。Δ = 当季 − 上季；新发 = 当季发行基金当季末规模；
      业绩贡献 = 上季规模 × 当季收益率；持营 = Δ − 新发 − 业绩贡献。
    - 最新季度收益率取银河排名公司口径（与报告一致）；历史季度用 unit_nav 基金级收益率估算。
    """
    ps = dl.product_scale()
    all_q, LATEST_Q, PREV_Q = _q()
    split_qs = all_q[-5:]
    scale = ps.groupby(["corp", "pub_date"])["total_nav"].sum().unstack("pub_date")
    ret_fund, scale_fund = _fund_returns()
    corp_of_fund = ps.drop_duplicates("fund_code").set_index("fund_code")["corp"].to_dict()
    rk = dl.ranking()
    latest_ret = {r["corp"]: float(r["return"]) for _, r in rk[rk["end"].astype(str) == LATEST_Q].iterrows()}

    # 新发规模：发行日期落在该季的基金，规模取该季末
    psi = ps.dropna(subset=["issue_date"]).copy()
    psi["issue_q"] = pd.PeriodIndex(psi["issue_date"], freq="Q")
    new_issue: dict[tuple[str, str], float] = {}
    for qstr in split_qs:
        per = pd.Period(qstr, freq="Q")
        sub_q = psi[(psi["issue_q"] == per) & (psi["pub_date"] == pd.Timestamp(qstr))]
        for corp, v in sub_q.groupby("corp")["total_nav"].sum().items():
            new_issue[(corp, qstr)] = float(v)

    rows = []
    for corp in dl.FIFTEEN:
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
            new = new_issue.get((corp, qstr), 0.0)
            if s_q is None or s_p is None:
                splits[qstr] = {"perf": None, "holding": None, "new": round(new)}
                continue
            delta = s_q - s_p
            if qstr == LATEST_Q and corp in latest_ret:
                perf = s_p * latest_ret[corp]
            else:
                perf = _perf_fundlevel(corp, pd.Timestamp(pstr), pd.Timestamp(qstr),
                                       ret_fund, scale_fund, corp_of_fund)
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
    """各公司一季度加权收益率 vs 最大回撤散点（demo 近似）。

    收益率用银河排名公司口径；最大回撤用公司旗下产品复权净值等权平均。
    """
    rk = dl.ranking()
    _, LATEST_Q, PREV_Q = _q()
    ret_map = {r["corp"]: float(r["return"]) for _, r in rk[rk["end"].astype(str) == LATEST_Q].iterrows()}
    nav = dl.nav_adjusted()
    nav_q1 = nav[(nav["pub_date"] >= PREV_Q) & (nav["pub_date"] <= LATEST_Q)]

    # 把复权净值产品映射到公司：用产品规模表（按归一化基金代码匹配）
    ps = dl.product_scale()
    fund_corp = {_fc_key(fc): corp for fc, corp in
                 ps.drop_duplicates("fund_code").set_index("fund_code")["corp"].items()}

    nav_q1 = nav_q1.copy()
    nav_q1["fc_key"] = nav_q1["fund_code"].map(_fc_key)

    corp_dds = defaultdict(list)
    for fc, sub in nav_q1.groupby("fc_key"):
        corp = fund_corp.get(fc)
        if corp not in dl.FIFTEEN_SET:
            continue
        vals = sub.sort_values("pub_date")["nav"].values
        if len(vals) < 2:
            continue
        peak = vals[0]; max_dd = 0.0
        for v in vals:
            if v > peak: peak = v
            dd = v / peak - 1
            if dd < max_dd: max_dd = dd
        corp_dds[corp].append(max_dd)

    rows = []
    for corp in dl.FIFTEEN:
        dds = corp_dds.get(corp, [])
        ret = ret_map.get(corp)
        if ret is None or not dds:
            continue
        rows.append({
            "corp": corp, "is_us": corp == dl.OUR_COMPANY,
            "ret": round(ret * 100, 2),
            "dd": round(sum(dds) / len(dds) * 100, 2),
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
