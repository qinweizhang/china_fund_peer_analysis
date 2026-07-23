"""Excel 数据加载与清洗层。

负责将 Excel 输入文件读入 DataFrame 并做基础规整，供 metrics.py 与路由层使用。
本系统为只读终端展示：数据集在后端 input_data 目录维护，网页不再支持上传；
当前激活数据集保存在 Flask session 中，按绝对路径缓存工作簿。
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

import pandas as pd

# 项目根目录（app/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "input_data")
DEFAULT_FILE = "2副本竞争对手分析-基础数据20260331.xlsx"
DEFAULT_PATH = os.path.join(DATA_DIR, DEFAULT_FILE)

# 报告样本：2026Q1 偏股规模前十五大基金公司 + 我司（工银瑞信已在内）
FIFTEEN = [
    "大成", "兴证全球", "华夏", "易方达", "南方", "嘉实", "富国",
    "广发", "华安", "工银瑞信", "中欧", "景顺长城", "汇添富", "永赢", "鹏华",
]
OUR_COMPANY = "工银瑞信"
FIFTEEN_SET = set(FIFTEEN)

# 产品规模表中公司名带“基金”后缀，需归一化到与持仓/排名一致的公司简称
_COMPANY_SUFFIX = "基金"


def normalize_corp(name: str, keep_all: bool = True) -> str | None:
    """把 '大成基金' -> '大成'（仅去后缀，保留全部公司）。

    名单过滤改由 product_scale/ranking 等访问器在 DataFrame 层用 peer_set() 完成，
    这里只做公司名归一化。keep_all 参数保留以兼容旧调用，已无实际作用。
    """
    if not name:
        return None
    n = name.strip()
    if n.endswith(_COMPANY_SUFFIX):
        n = n[: -len(_COMPANY_SUFFIX)]
    return n if n else None


# ============================================================
# 数据集注册与切换（支持上传新季度数据）
# ============================================================

def _label(filename: str) -> str:
    """从文件名解析展示标签：优先识别末尾 8 位日期 20260331 -> 2026-03-31。"""
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return os.path.splitext(filename)[0]


def datasets() -> list[dict]:
    """扫描后端数据目录（input_data），返回全部可用数据集。

    每项：{id, label, path, source}。id 取文件名（去扩展名），label 取解析后的日期。
    本系统为只读终端展示——数据集在后端维护，不再支持网页上传。
    """
    out: list[dict] = []
    if not os.path.isdir(DATA_DIR):
        return out
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.lower().endswith(".xlsx") or fn.startswith("~$"):
            continue
        out.append({
            "id": os.path.splitext(fn)[0],
            "label": _label(fn),
            "path": os.path.join(DATA_DIR, fn),
            "source": "后端",
        })
    return out


def _active_dataset() -> dict | None:
    """当前数据集：取 input_data 目录下 mtime 最新的文件（终端始终展示最新后端数据）。"""
    ds = datasets()
    if not ds:
        return None
    return max(ds, key=lambda d: os.path.getmtime(d["path"]))


def active_path() -> str:
    """当前激活数据集的绝对路径（最新 mtime 的后端文件；无文件时回退 DEFAULT_PATH）。"""
    a = _active_dataset()
    return a["path"] if a else DEFAULT_PATH


def active_label() -> str:
    """当前激活数据集的展示标签。"""
    a = _active_dataset()
    return a["label"] if a else "—"


# ============================================================
# 工作簿缓存（按绝对路径）
# ============================================================

_CACHE: dict[str, dict[str, pd.DataFrame]] = {}


def _workbook(path: str | None = None) -> dict[str, pd.DataFrame]:
    """读取并缓存某路径下 Excel 的全部 sheet。path 缺省取激活数据集。"""
    p = path or active_path()
    p = os.path.abspath(p)
    if p not in _CACHE:
        _CACHE[p] = pd.read_excel(p, sheet_name=None)
    return _CACHE[p]


def _sheet(*aliases: str) -> pd.DataFrame:
    """按别名子串匹配工作簿 sheet，兼容季度间 sheet 命名差异。

    顺序：先精确名命中，再按子串包含命中；都找不到时抛 KeyError。
    例：个股收益率 / 行业收益率 在新季度改为 个股季度收益率 / 行业季度收益率，
    传入多别名即可自动匹配。
    """
    sheets = _workbook()
    for a in aliases:
        if a in sheets:
            return sheets[a]
    for a in aliases:
        for name, df in sheets.items():
            if a in name:
                return df
    raise KeyError(f"未找到匹配 sheet（别名 {list(aliases)}）；可用：{list(sheets)}")


def clear_cache(path: str | None = None) -> None:
    """清除缓存（上传新数据或切换后调用）。path=None 清全部。"""
    if path is None:
        _CACHE.clear()
        _PEER_CACHE.clear()
    else:
        _CACHE.pop(os.path.abspath(path), None)
        _PEER_CACHE.pop(os.path.abspath(path), None)


# ============================================================
# 派生：可用季度、最新/上一季度（用于跨季度通用化）
# ============================================================

def quarters() -> list[str]:
    """产品规模表中所有季末时点（升序，YYYY-MM-DD 字符串）。

    用 keep_all=True 取全量（季度集合与公司过滤无关），避免与 peer_set 循环依赖。
    """
    qs = product_scale(keep_all=True)["pub_date"].dt.strftime("%Y-%m-%d").unique().tolist()
    return sorted(qs)


def latest_q() -> str | None:
    qs = quarters()
    return qs[-1] if qs else None


def prev_q() -> str | None:
    qs = quarters()
    return qs[-2] if len(qs) > 1 else None


_PEER_CACHE: dict[str, list[str]] = {}


def peer_corps(top_n: int = 15) -> list[str]:
    """数据驱动的同业前 N 家公司：最新季按权益规模(TOTAL_NAV)降序取前 N。

    替代固定 FIFTEEN 名单——随激活数据集自适应，作为全站统一的"十五大"口径。
    结果按激活数据集绝对路径缓存；切换/上传数据后 clear_cache() 会清掉。
    """
    p = os.path.abspath(active_path())
    if p in _PEER_CACHE:
        return _PEER_CACHE[p]
    latest = latest_q()
    if not latest:
        _PEER_CACHE[p] = list(FIFTEEN)
        return _PEER_CACHE[p]
    ps = product_scale(keep_all=True)
    sub = ps[ps["pub_date"] == pd.Timestamp(latest)]
    g = sub.groupby("corp")["total_nav"].sum().sort_values(ascending=False)
    corps = list(g.head(top_n).index)
    # 不足 N 家（数据偏少）时回退固定名单，保证始终有可比口径
    _PEER_CACHE[p] = corps if len(corps) >= min(top_n, len(g)) else list(FIFTEEN)
    return _PEER_CACHE[p]


def peer_set() -> set[str]:
    """动态十五大公司集合（供访问器过滤用）。"""
    return set(peer_corps())


def year_start_q() -> str | None:
    """年初（上一年度年末）季末时点：LATEST_Q 所在年的上一年 12-31。

    用于模块一 YTD 口径（规模/变动拆分从年初累计）。数据缺失时回退到
    <= 该日的最近季末；都没有则回退到上一季度 prev_q()。
    """
    latest = latest_q()
    if not latest:
        return None
    target = f"{int(latest[:4]) - 1}-12-31"
    qs = quarters()
    if target in qs:
        return target
    cand = [q for q in qs if q <= target]
    if cand:
        return cand[-1]
    return prev_q()


# ============================================================
# 各 sheet 的规整化访问器
# ============================================================

def ranking(keep_all: bool = False) -> pd.DataFrame:
    """权益银河排名。POINTRATE 为文本百分比，需解析。

    keep_all=True 时保留全部公司（仅去"基金"后缀），用于数据驱动派生前 N 名；
    keep_all=False（默认）按动态 peer_set() 过滤到当前十五大。
    """
    df = _sheet("权益银河排名").copy()
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
    df["corp"] = df["corp"].map(normalize_corp)
    df = df[df["corp"].notna()].copy()
    if not keep_all:
        df = df[df["corp"].isin(peer_set())].copy()
    return df


def product_scale(keep_all: bool = False) -> pd.DataFrame:
    """产品规模。规整公司名、数值列、日期。

    keep_all=True 时保留全部公司（仅去"基金"后缀），用于数据驱动派生前 N 名；
    keep_all=False（默认）按动态 peer_set() 过滤到当前十五大。
    """
    raw = _sheet("产品规模")
    raw = raw.iloc[:, :10]  # 前 10 列为有效字段，其后为注释
    raw.columns = [
        "pub_date", "company", "fund_code", "fund_name", "estab_date",
        "issue_date", "classify_label", "unit_nav", "total_nav", "total_shares",
    ]
    df = raw.copy()
    df["corp"] = df["company"].map(normalize_corp)
    df = df[df["corp"].notna()].copy()
    if not keep_all:
        df = df[df["corp"].isin(peer_set())].copy()
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    df["total_nav"] = pd.to_numeric(df["total_nav"], errors="coerce")
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["estab_date"] = pd.to_datetime(df["estab_date"], errors="coerce")
    df["unit_nav"] = pd.to_numeric(df["unit_nav"], errors="coerce")
    return df


def _post_classify_type(clabel: str) -> str:
    """事后分类类型：由 CLASSIFY_LABEL 按规则派生（替代可能为空的 INDUSTRIESNAME）。

      全市场基金 / 全市场基金（股票比例50%以下） -> 宽基基金(事后)
      医药行业基金                            -> 医药行业基金(事后)
      TMT行业基金                            -> 科技行业基金(事后)
      消费行业基金 / 农业主题行业基金          -> 消费行业基金(事后)
      其余                                   -> 周期制造行业基金(事后)
    """
    if clabel in ("全市场基金", "全市场基金（股票比例50%以下）"):
        return "宽基基金(事后)"
    if clabel == "医药行业基金":
        return "医药行业基金(事后)"
    if clabel == "TMT行业基金":
        return "科技行业基金(事后)"
    if clabel in ("消费行业基金", "农业主题行业基金"):
        return "消费行业基金(事后)"
    return "周期制造行业基金(事后)"


def post_classify() -> pd.DataFrame:
    """产品事后分类。

    INDUSTRIESNAME 列可能为空，故 INDUSTRIESNAME 改由 CLASSIFY_LABEL 按规则派生
    （见 _post_classify_type）。TOTAL_NAV 经 left join 取自"产品规模"sheet
    （按 fund_code + pub_date），更准更全；缺失时回退原表值。
    """
    df = _sheet("产品事后分类").copy()
    df.columns = ["pub_date", "fund_code", "fund_name", "industries_name", "classify_label", "total_nav"]
    df["industries_name"] = df["classify_label"].map(_post_classify_type)
    # left join 产品规模 的 total_nav（按 fund_code + pub_date）
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    ps = product_scale(keep_all=True)
    psv = ps[["fund_code", "pub_date", "total_nav"]].copy()
    df = df.merge(psv, on=["fund_code", "pub_date"], how="left", suffixes=("_pc", "_ps"))
    df["total_nav"] = df["total_nav_ps"].fillna(df["total_nav_pc"])
    df = df.drop(columns=["total_nav_pc", "total_nav_ps"])
    return df


# 空 industry 的港股/特殊股手动补录申万一级行业（数据源 S_I_NAME1 缺失），用于行业调整比例等口径
# 海外/退市/不明确（000660.KS、2330.TW、2788.HK、2698.HK、920045.BJ）保留 NaN
_SEC_INDUSTRY_OVERRIDE = {
    "1179.HK": "消费者服务",      # 华住集团-S（酒店）
    "2259.HK": "有色金属",        # 紫金黄金国际
    "2513.HK": "计算机",          # 智谱（AI）
    "688796.SH": "医药",          # 百奥赛图
    "2315.HK": "医药",            # 百奥赛图-B
    "0100.HK": "计算机",          # MINIMAX-W（AI）
    "9911.HK": "传媒",            # 赤子城科技
    "9999.HK": "传媒",            # 网易
    "3858.HK": "有色金属",        # 佳鑫国际资源
    "6082.HK": "电子",            # 壁仞科技（GPU）
    "3696.HK": "医药",            # 英矽智能（AI制药）
    "1133.HK": "电力设备及新能源",  # 哈尔滨电气
    "2590.HK": "机械",            # 极智嘉-W（机器人）
    "2696.HK": "医药",            # 复宏汉霖
    "6938.HK": "医药",            # 瑞博生物-B
    "1768.HK": "食品饮料",        # 鸣鸣很忙（零食）
    "3330.HK": "有色金属",        # 灵宝黄金
    "9888.HK": "传媒",            # 百度集团-SW
    "9903.HK": "电子",            # 天数智芯（AI芯片）
    "2595.HK": "医药",            # 劲方医药-B
    "1651.HK": "机械",            # 津上机床中国
    "1672.HK": "医药",            # 歌礼制药-B
    "2643.HK": "消费者服务",      # 曹操出行
    "1617.HK": "通信",            # 南方通信
    "2383.TW": "传媒",            # TOM集团
    "2256.HK": "医药",            # 和誉-B
    "9961.HK": "消费者服务",      # 携程集团-S
}


def holdings(exclude_industry: bool = False) -> pd.DataFrame:
    """公司持仓明细（或剔除行业基金版本）。"""
    if exclude_industry:
        raw = _sheet("公司明细剔除行业基金", "剔除行业基金").iloc[:, :6]
    else:
        raw = _sheet("公司持仓明细").iloc[:, :6]
    raw.columns = ["corp", "pub_date", "sec_no", "sec_name", "industry", "pos_mkt_val"]
    df = raw.copy()
    df["pos_mkt_val"] = pd.to_numeric(df["pos_mkt_val"], errors="coerce")
    df = df.dropna(subset=["pos_mkt_val"])
    return df


def industry_board_map() -> dict[str, str]:
    """行业 -> 板块 映射字典。"""
    df = _sheet("行业板块对应关系")
    df.columns = ["industry", "board"]
    return {str(r["industry"]).strip(): str(r["board"]).strip()
            for _, r in df.iterrows() if pd.notna(r["industry"])}


def boards() -> list[str]:
    """六大板块名称，按"行业板块对应关系"sheet 的出现顺序去重。"""
    df = _sheet("行业板块对应关系")
    seen: list[str] = []
    for v in df.iloc[:, 1].dropna().astype(str):
        v = v.strip()
        if v and v not in seen:
            seen.append(v)
    return seen


def concentration() -> pd.DataFrame:
    """集中度：前二十大个股 / 前三大行业，长表。

    兼容两种工作簿布局：
    - 新季度：拆成两个 sheet「集中度前二十大个股」「集中度前三大行业」，
      各为干净的 3 列表 (FUND_CORP, PUB_DATE, SUM(S_PER))，分别读取后拼接；
    - 旧季度：单个「集中度」sheet，左半区(cols 0..3)为前二十大个股、
      右半区(cols 6..9)为前三大行业，左右半区分别取 4 列后拼接。
    """
    sheets = _workbook()
    has_split = any("前二十大个股" in n or "前三大行业" in n for n in sheets)
    if has_split:
        # 新格式：两个独立 sheet，各 3 列
        left = _sheet("前二十大个股").iloc[:, :3].copy()
        left.columns = ["corp", "pub_date", "value"]
        left["type"] = "top20"
        right = _sheet("前三大行业").iloc[:, :3].copy()
        right.columns = ["corp", "pub_date", "value"]
        right["type"] = "top3_industry"
    else:
        # 旧格式：单 sheet 左右半区
        raw = _sheet("集中度")
        left = raw.iloc[:, :4].copy()
        left.columns = ["type", "corp", "pub_date", "value"]
        left["type"] = "top20"
        right = raw.iloc[:, 6:10].copy()
        right.columns = ["type", "corp", "pub_date", "value"]
        right["type"] = "top3_industry"
    df = pd.concat([left, right], ignore_index=True)
    df = df.dropna(subset=["corp", "pub_date"]).copy()
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def position() -> pd.DataFrame:
    """仓位：算术平均 / 规模加权（按动态十五大过滤）。"""
    df = _sheet("仓位").copy()
    df.columns = ["corp", "pub_date", "arith", "weighted"]
    df = df.dropna(subset=["corp"]).copy()
    df = df[df["corp"].isin(peer_set())].copy()
    return df


def nav_adjusted() -> pd.DataFrame:
    """产品复权净值（每日）。"""
    df = _sheet("产品复权净值").copy()
    df.columns = ["pub_date", "fund_code", "fund_name", "nav"]
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    return df


def stock_return() -> dict[str, float]:
    """个股收益率 -> dict[sec_no] = return。"""
    df = _sheet("个股收益率", "个股季度收益率").copy()
    df.columns = ["sec_no", "return_"]
    df["return_"] = pd.to_numeric(df["return_"], errors="coerce")
    return dict(zip(df["sec_no"].astype(str), df["return_"]))


def industry_return() -> dict[tuple[str, str], float]:
    """行业收益率 -> {(市场, 行业名): 收益率}。

    市场由 INDEX_CODE 前缀判定：CI0050* 为 A股(中信A股行业)，CIHK* 为 港股(中信港股行业)。
    同名行业在 A股/港股 各有一条，故用 (市场, 行业名) 复合键避免后者覆盖前者。
    """
    df = _sheet("行业收益率", "行业季度收益率").copy()
    df.columns = ["index_code", "index_name", "return_"]
    df["return_"] = pd.to_numeric(df["return_"], errors="coerce")
    out: dict[tuple[str, str], float] = {}
    for _, r in df.iterrows():
        code = str(r["index_code"])
        market = "A股" if code.startswith("CI005") else "港股"
        if pd.notna(r["return_"]):
            out[(market, str(r["index_name"]))] = float(r["return_"])
    return out


def stock_balance() -> dict[str, float]:
    """个股收益金额 -> dict[seccode] = balance。"""
    df = _sheet("收益金额").copy()
    df.columns = ["seccode", "balance"]
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    return dict(zip(df["seccode"].astype(str), df["balance"]))


if __name__ == "__main__":
    # 自检
    print("datasets:", [(d["id"], d["label"], d["source"]) for d in datasets()])
    print("active:", active_label(), "->", active_path())
    print("quarters:", quarters(), "latest:", latest_q(), "prev:", prev_q())
    print("ranking:", ranking().shape)
    print("product_scale:", product_scale().shape)
    print("holdings:", holdings().shape)
    print("board map sample:", list(industry_board_map().items())[:3])
