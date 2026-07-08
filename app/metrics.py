"""业务指标计算层。

将 data_loader 的原始数据加工为三大模块所需的展示数据。
所有口径在 docstring 中标注；与报告 PDF 不完全一致处均注明“demo 近似”。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd

from . import data_loader as dl

QUARTERS = ["2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30",
            "2025-12-31", "2026-03-31"]
LATEST_Q = "2026-03-31"
PREV_Q = "2025-12-31"

BOARDS = ["TMT", "金融地产", "消费", "新能源及制造", "周期", "医药"]
MARKETS = ["A股", "港股"]


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

    # 规模（亿元）—— TOTAL_NAV 本身即亿元单位
    scale = ps.groupby(["corp", "pub_date"])["total_nav"].sum().unstack("pub_date").round(0)
    # 当季新发规模（亿元）
    new_issue = (
        ps[(ps["issue_date"] >= "2026-01-01") & (ps["issue_date"] <= "2026-03-31")]
        .groupby("corp")["total_nav"].sum()
    ).round(0)

    def _ret(corp: str, begin: str) -> tuple[float | None, str | None, int | None, int | None]:
        sub = rk[(rk["corp"] == corp) & (rk["begin"] == begin)]
        if sub.empty:
            return None, None, None, None
        r = sub.iloc[0]
        return float(r["return"]), r["ranking"], int(r["rank"]), int(r["rank_total"])

    rows = []
    for corp in dl.FIFTEEN:
        q4 = scale.loc[corp, pd.Timestamp(PREV_Q)] if corp in scale.index and pd.Timestamp(PREV_Q) in scale.columns else None
        q1 = scale.loc[corp, pd.Timestamp(LATEST_Q)] if corp in scale.index and pd.Timestamp(LATEST_Q) in scale.columns else None
        if q4 is None or q1 is None:
            continue
        delta = q1 - q4
        chg_pct = (delta / q4) if q4 else 0
        ret_q, _, rk_q, tot_q = _ret(corp, "2026-01-01")
        ret_3y, rk_3y, rk3_rank, tot_3y = _ret(corp, "2024-01-01")
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
    # 按 2026Q1 业绩降序
    rows.sort(key=lambda r: r["ret_q"] if r["ret_q"] is not None else -999, reverse=True)
    for i, r in enumerate(rows, 1):
        r["seq"] = i
    return rows


# ============================================================
# 模块二：同业持仓及变动分析
# ============================================================

def _board_allocation(pub_date: str, exclude_industry: bool = False) -> pd.DataFrame:
    """计算某季末各公司板块配置占比。

    口径：各公司持仓个股按行业→板块映射，市值求和后归一化为占比。
    A股/港股拆分依据证券代码后缀（.SH/.SZ 为 A股，.HK 为港股）。
    """
    h = dl.holdings(exclude_industry=exclude_industry)
    h = h[h["pub_date"] == pub_date].copy()
    bmap = dl.industry_board_map()
    h["board"] = h["industry"].map(bmap)
    h = h.dropna(subset=["board"])
    # 市场判定
    def _market(sec: str) -> str:
        s = str(sec)
        if s.endswith(".HK") or "(港)" in s:
            return "港股"
        return "A股"
    h["market"] = h["sec_no"].map(_market)
    corp_total = h.groupby("corp")["pos_mkt_val"].transform("sum")
    h["share"] = h["pos_mkt_val"] / corp_total
    return h


def board_table(pub_date: str = LATEST_Q, exclude_industry: bool = False) -> tuple[list[dict], list[str]]:
    """板块配置表：行=公司，列=各板块+A股/港股。返回 (rows, 平均值行)。"""
    h = _board_allocation(pub_date, exclude_industry)
    if h.empty:
        return [], []
    pivot = h.groupby(["corp", "board"])["share"].sum().unstack("board").fillna(0)
    market_pivot = h.groupby(["corp", "market"])["share"].sum().unstack("market").fillna(0)

    rows = []
    for corp in dl.FIFTEEN:
        if corp not in pivot.index:
            continue
        row = {"corp": corp, "is_us": corp == dl.OUR_COMPANY}
        for b in BOARDS:
            row[b] = pivot.loc[corp, b] if b in pivot.columns else 0
        row["A股"] = market_pivot.loc[corp, "A股"] if "A股" in market_pivot.columns else 0
        row["港股"] = market_pivot.loc[corp, "港股"] if "港股" in market_pivot.columns else 0
        rows.append(row)
    # 平均值
    avg = {"corp": "平均值", "is_us": False}
    for b in BOARDS + MARKETS:
        vals = [r[b] for r in rows]
        avg[b] = sum(vals) / len(vals) if vals else 0
    # 我司排名
    rank_row = {"corp": "我司排名", "is_us": False}
    for b in BOARDS + MARKETS:
        vals = sorted([r[b] for r in rows], reverse=True)
        rank_row[b] = vals.index(next(r[b] for r in rows if r["corp"] == dl.OUR_COMPANY)) + 1
    return rows, [avg, rank_row]


def board_change_table() -> list[dict]:
    """板块较上季度变化（剔除涨跌幅，demo 近似：直接做市值占比差）。"""
    cur = _board_allocation(LATEST_Q)
    prev = _board_allocation(PREV_Q)
    cur_p = cur.groupby(["corp", "board"])["share"].sum().unstack("board").fillna(0)
    prev_p = prev.groupby(["corp", "board"])["share"].sum().unstack("board").fillna(0)
    cur_m = cur.groupby(["corp", "market"])["share"].sum().unstack("market").fillna(0)
    prev_m = prev.groupby(["corp", "market"])["share"].sum().unstack("market").fillna(0)

    rows = []
    for corp in dl.FIFTEEN:
        if corp not in cur_p.index:
            continue
        row = {"corp": corp, "is_us": corp == dl.OUR_COMPANY}
        diffs = []
        for b in BOARDS:
            c = cur_p.loc[corp, b] if b in cur_p.columns else 0
            p = prev_p.loc[corp, b] if b in prev_p.columns and corp in prev_p.index else 0
            row[b] = c - p
            diffs.append(abs(c - p))
        for m in MARKETS:
            c = cur_m.loc[corp, m] if m in cur_m.columns else 0
            p = prev_m.loc[corp, m] if m in prev_m.columns and corp in prev_m.index else 0
            row[m] = c - p
        row["adjust"] = sum(diffs)
        rows.append(row)
    return rows


def top10_holdings() -> list[dict]:
    """各公司季末前十大重仓股 + 季度收益率。

    口径（demo 近似）：按公司持仓明细市值降序取前 10；收益来自个股收益率表。
    报告口径为“各基金前十大重仓股加总”，本 demo 以公司持仓明细直接取。
    """
    h = dl.holdings()[dl.holdings()["pub_date"] == LATEST_Q].copy()
    sret = dl.stock_return()
    rows = []
    for corp in dl.FIFTEEN:
        sub = h[h["corp"] == corp].sort_values("pos_mkt_val", ascending=False).head(10)
        if sub.empty:
            continue
        stocks = []
        rets = []
        for _, r in sub.iterrows():
            ret = sret.get(str(r["sec_no"]))
            stocks.append({"name": r["sec_name"], "ret": ret})
            if ret is not None:
                rets.append(ret)
        avg_ret = sum(rets) / len(rets) if rets else None
        rows.append({
            "corp": corp, "is_us": corp == dl.OUR_COMPANY,
            "stocks": stocks, "avg_ret": avg_ret,
        })
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

def scale_history() -> dict:
    """各公司逐季规模（亿元）时间序列 + 一季度变动拆分。"""
    ps = dl.product_scale()
    scale = (ps.groupby(["corp", "pub_date"])["total_nav"].sum().unstack("pub_date")).round(1)
    new_issue = (
        ps[(ps["issue_date"] >= "2026-01-01") & (ps["issue_date"] <= "2026-03-31")]
        .groupby("corp")["total_nav"].sum()
    ).round(1)
    rk = dl.ranking()
    ret_map = {r["corp"]: float(r["return"]) for _, r in rk[rk["begin"] == "2026-01-01"].iterrows()}

    rows = []
    for corp in dl.FIFTEEN:
        if corp not in scale.index:
            continue
        q_series = {}
        for q in QUARTERS:
            ts = pd.Timestamp(q)
            if ts in scale.columns:
                q_series[q] = float(scale.loc[corp, ts]) if pd.notna(scale.loc[corp, ts]) else None
        q4 = q_series.get(PREV_Q)
        q1 = q_series.get(LATEST_Q)
        if q4 is None or q1 is None:
            continue
        delta = q1 - q4
        chg = round(delta / q4 * 100, 1) if q4 else 0
        perf = q4 * ret_map.get(corp, 0) if q4 else 0
        new = float(new_issue.get(corp, 0) or 0)
        hold = delta - new - perf
        rows.append({
            "corp": corp, "is_us": corp == dl.OUR_COMPANY,
            "quarters": q_series, "chg_pct": chg,
            "perf": round(perf), "holding": round(hold), "new_issue": round(new),
        })
    rows.sort(key=lambda r: r["quarters"].get(LATEST_Q, 0), reverse=True)
    return {"rows": rows, "quarters": QUARTERS}


def product_top10() -> tuple[list[dict], list[dict]]:
    """一季度规模增长 TOP10 / 缩减 TOP10 产品。

    口径（demo 近似）：按 2025Q4→2026Q1 规模变动排序。
    收益率与最大回撤基于产品复权净值表计算（仅在该表内有净值的产品）。
    """
    ps = dl.product_scale()
    pc = dl.post_classify()
    # 事后分类：取最新一条作为产品类型
    pc_latest = pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].to_dict()

    nav = dl.nav_adjusted()
    # 仅取 2026Q1 区间内净值用于计算收益率与回撤，按归一化基金代码分组
    nav_q1 = nav[(nav["pub_date"] >= "2025-12-31") & (nav["pub_date"] <= "2026-03-31")].copy()
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
    ret_map = {r["corp"]: float(r["return"]) for _, r in rk[rk["begin"] == "2026-01-01"].iterrows()}
    nav = dl.nav_adjusted()
    nav_q1 = nav[(nav["pub_date"] >= "2025-12-31") & (nav["pub_date"] <= "2026-03-31")]

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
    pc_latest = pc.sort_values("pub_date").groupby("fund_code").last()["industries_name"].to_dict()
    nav = dl.nav_adjusted()
    nav_q1 = nav[(nav["pub_date"] >= "2025-12-31") & (nav["pub_date"] <= "2026-03-31")].copy()
    nav_q1["fc_key"] = nav_q1["fund_code"].map(_fc_key)
    nav_groups = {k: g.sort_values("pub_date")["nav"].values for k, g in nav_q1.groupby("fc_key")}
    pc_key_map = {_fc_key(k): v for k, v in pc_latest.items()}

    q4 = corp_ps[corp_ps["pub_date"] == pd.Timestamp(PREV_Q)].set_index("fund_code")["total_nav"]
    q1 = corp_ps[corp_ps["pub_date"] == pd.Timestamp(LATEST_Q)].set_index("fund_code")["total_nav"]
    common = q1.index.intersection(q4.index)
    delta = (q1.loc[common] - q4.loc[common])

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
        rows.append({
            "name": name_map.get(fc, ""), "code": fc,
            "estab": str(estab_map.get(fc, ""))[:10] if pd.notna(estab_map.get(fc)) else "",
            "type": pc_key_map.get(_fc_key(fc), "-"),
            "q4": round(float(q4.loc[fc]), 1),
            "q1": round(float(q1.loc[fc]), 1),
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
    ov = company_overview()
    print(f"overview: {len(ov)} rows; top={ov[0]['corp']} ret={ov[0]['ret_q']}")
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
