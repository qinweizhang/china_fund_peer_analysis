"""Excel 数据加载与清洗层。

负责将 input_data 下的 Excel 文件读入 DataFrame 并做基础规整，
供 metrics.py 与路由层使用。读取结果在进程内缓存。
"""
from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

# 项目根目录（app/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "input_data", "竞争对手分析-基础数据20260331.xlsx")

# 报告样本：2026Q1 偏股规模前十五大基金公司 + 我司（工银瑞信已在内）
FIFTEEN = [
    "大成", "兴证全球", "华夏", "易方达", "南方", "嘉实", "富国",
    "广发", "华安", "工银瑞信", "中欧", "景顺长城", "汇添富", "永赢", "鹏华",
]
OUR_COMPANY = "工银瑞信"
FIFTEEN_SET = set(FIFTEEN)

# 产品规模表中公司名带“基金”后缀，需归一化到与持仓/排名一致的公司简称
_COMPANY_SUFFIX = "基金"


def normalize_corp(name: str) -> str | None:
    """把 '大成基金' -> '大成'；不在十五大名单内返回 None。"""
    if not name:
        return None
    n = name.strip()
    if n.endswith(_COMPANY_SUFFIX):
        n = n[: -len(_COMPANY_SUFFIX)]
    return n if n in FIFTEEN_SET else None


@lru_cache(maxsize=1)
def _workbook() -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = pd.read_excel(DATA_PATH, sheet_name=None)
    return sheets


# ---- 各 sheet 的规整化访问器 ----

def ranking() -> pd.DataFrame:
    """权益银河排名。POINTRATE 为文本百分比，需解析。"""
    df = _workbook()["权益银河排名"].copy()
    df.columns = ["corp", "begin", "end", "return_text", "ranking"]
    # 0.2508% -> 0.002508
    df["return"] = (
        df["return_text"].astype(str).str.replace("%", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce") / 100.0
    )
    # ranking "41/126" -> 拆分
    parts = df["ranking"].astype(str).str.split("/", expand=True)
    df["rank"] = pd.to_numeric(parts[0], errors="coerce")
    df["rank_total"] = pd.to_numeric(parts[1], errors="coerce")
    df["corp"] = df["corp"].map(normalize_corp).fillna(df["corp"])
    df = df[df["corp"].isin(FIFTEEN_SET)].copy()
    return df


def product_scale() -> pd.DataFrame:
    """产品规模。规整公司名、数值列、日期。"""
    raw = _workbook()["产品规模"]
    raw = raw.iloc[:, :10]  # 前 10 列为有效字段，其后为注释
    raw.columns = [
        "pub_date", "company", "fund_code", "fund_name", "estab_date",
        "issue_date", "classify_label", "unit_nav", "total_nav", "total_shares",
    ]
    df = raw.copy()
    df["corp"] = df["company"].map(normalize_corp)
    df = df[df["corp"].notna()].copy()
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    df["total_nav"] = pd.to_numeric(df["total_nav"], errors="coerce")
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["estab_date"] = pd.to_datetime(df["estab_date"], errors="coerce")
    return df


def post_classify() -> pd.DataFrame:
    """产品事后分类。"""
    df = _workbook()["产品事后分类"].copy()
    df.columns = ["pub_date", "fund_code", "fund_name", "industries_name", "classify_label", "total_nav"]
    return df


def holdings(exclude_industry: bool = False) -> pd.DataFrame:
    """公司持仓明细（或剔除行业基金版本）。"""
    sheet = "公司明细剔除行业基金" if exclude_industry else "公司持仓明细"
    raw = _workbook()[sheet].iloc[:, :6]
    raw.columns = ["corp", "pub_date", "sec_no", "sec_name", "industry", "pos_mkt_val"]
    df = raw.copy()
    df["pos_mkt_val"] = pd.to_numeric(df["pos_mkt_val"], errors="coerce")
    df = df.dropna(subset=["pos_mkt_val"])
    return df


def industry_board_map() -> dict[str, str]:
    """行业 -> 板块 映射字典。"""
    df = _workbook()["行业板块对应关系"]
    df.columns = ["industry", "board"]
    return {str(r["industry"]).strip(): str(r["board"]).strip()
            for _, r in df.iterrows() if pd.notna(r["industry"])}


def concentration() -> pd.DataFrame:
    """集中度：前二十大个股 / 前三大行业，长表。"""
    raw = _workbook()["集中度"]
    # 左半区: 前二十大个股  cols [0..3] -> type,corp,date,value
    # 右半区: 前三大行业    cols [6..9]
    left = raw.iloc[:, :4].copy()
    left.columns = ["type", "corp", "pub_date", "value"]
    left["type"] = "top20"
    right = raw.iloc[:, 6:10].copy()
    right.columns = ["type", "corp", "pub_date", "value"]
    right["type"] = "top3_industry"
    df = pd.concat([left, right], ignore_index=True)
    df = df.dropna(subset=["corp", "pub_date"]).copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def position() -> pd.DataFrame:
    """仓位：算术平均 / 规模加权。"""
    df = _workbook()["仓位"].copy()
    df.columns = ["corp", "pub_date", "arith", "weighted"]
    df = df.dropna(subset=["corp"]).copy()
    df = df[df["corp"].isin(FIFTEEN_SET | {"东方证券资管", "交银施罗德"})].copy()
    return df


def nav_adjusted() -> pd.DataFrame:
    """产品复权净值（每日）。"""
    df = _workbook()["产品复权净值"].copy()
    df.columns = ["pub_date", "fund_code", "fund_name", "nav"]
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    return df


def stock_return() -> dict[str, float]:
    """个股收益率 -> dict[sec_no] = return。"""
    df = _workbook()["个股收益率"].copy()
    df.columns = ["sec_no", "return_"]
    df["return_"] = pd.to_numeric(df["return_"], errors="coerce")
    return dict(zip(df["sec_no"].astype(str), df["return_"]))


def industry_return() -> dict[str, float]:
    """行业收益率 -> dict[index_name] = return。"""
    df = _workbook()["行业收益率"].copy()
    df.columns = ["index_code", "index_name", "return_"]
    df["return_"] = pd.to_numeric(df["return_"], errors="coerce")
    return dict(zip(df["index_name"].astype(str), df["return_"]))


def stock_balance() -> dict[str, float]:
    """个股收益金额 -> dict[seccode] = balance。"""
    df = _workbook()["收益金额"].copy()
    df.columns = ["seccode", "balance"]
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    return dict(zip(df["seccode"].astype(str), df["balance"]))


if __name__ == "__main__":
    # 自检
    print("ranking:", ranking().shape)
    print("product_scale:", product_scale().shape)
    print("holdings:", holdings().shape)
    print("concentration corps:", concentration()["corp"].unique()[:5])
    print("position corps:", position()["corp"].unique()[:5])
    print("board map sample:", list(industry_board_map().items())[:3])
