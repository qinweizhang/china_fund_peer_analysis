"""AI 驱动的分析报告生成模块。

调用大模型，根据图表的结构化数据自动生成
类似 reference 报告风格的专业分析文字。

特性：
- 发送结构化 JSON 数据（非图片），让模型生成分析语言
- 按数据内容缓存，同一份数据不重复调用
- 错误处理 + Token 控制
- 为每种图表设计专属 Prompt
- SSL 自动禁用验证（兼容代理环境）
"""
from __future__ import annotations

import json
import os
import ssl
import hashlib
import urllib.request
from typing import Any

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".ai_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# API 配置（从环境变量读取，兼容 Claude Code 的 settings）
ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY",
    os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic",
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "glm-5.2")
MAX_OUTPUT_TOKENS = 2048


def _ssl_context() -> ssl.SSLContext:
    """SSL context（禁用验证，兼容代理环境）。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _cache_key(chart_type: str, data: dict) -> str:
    raw = json.dumps({"type": chart_type, "data": data}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _read_cache(key: str) -> str | None:
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _write_cache(key: str, text: str) -> None:
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _call_llm(system_prompt: str, user_content: str) -> str:
    """调用 Anthropic 兼容 API（支持阿里云代理 / GLM 等）。"""
    if not ANTHROPIC_API_KEY:
        return _fallback("未配置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN")

    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300, context=_ssl_context()) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    # 提取 text block（跳过 thinking block）
    for block in result.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    # 如果没有 text block，取最后一个 block 的内容
    if result.get("content"):
        last = result["content"][-1]
        return last.get("text", last.get("thinking", ""))
    return _fallback("API 返回空内容")


def _fallback(reason: str) -> str:
    return f"[AI 分析待生成] 原因：{reason}。请配置环境变量后重新加载页面。"


# ============================================================
# 通用生成函数
# ============================================================

def generate_analysis(chart_type: str, data: dict, context: dict | None = None) -> str:
    """为指定图表类型生成 AI 分析。

    参数：
        chart_type: 图表类型标识（如 "company_overview"）
        data: 图表的结构化数据（JSON 可序列化）
        context: 额外上下文（如公司名、季度等）

    返回：
        分析文字（2-3 段专业报告语言）
    """
    # 1. 检查缓存（跳过失败的缓存，允许重试）
    key = _cache_key(chart_type, data)
    cached = _read_cache(key)
    if cached and "[AI 分析待生成]" not in cached and "API 调用失败" not in cached:
        return cached

    # 2. 获取 Prompt
    prompt_config = PROMPTS.get(chart_type)
    if not prompt_config:
        return f"[未定义图表类型: {chart_type}]"

    # 3. 构建 LLM 输入
    ctx = context or {}
    system_prompt = prompt_config["system"]
    user_content = prompt_config["template"].format(
        data_json=json.dumps(data, ensure_ascii=False, indent=2),
        **ctx,
    )

    # 4. 调用 LLM（失败时不缓存，允许下次重试）
    try:
        result = _call_llm(system_prompt, user_content)
    except Exception as e:
        return _fallback(f"API 调用失败: {e}")

    # 5. 写入缓存（仅缓存成功结果）
    _write_cache(key, result)
    return result


# ============================================================
# 各图表的专属 Prompt
# ============================================================

PROMPTS: dict[str, dict[str, str]] = {
    "company_overview": {
        "system": (
            "你是基金公司风险管理部的资深分析师，负责撰写权益竞争对手季度分析报告。"
            "你将收到结构化的基金公司业绩及规模数据（JSON 格式），请根据数据生成专业的分析文字。\n\n"
            "要求：\n"
            "1. 生成 2-3 段专业分析，类似券商研报风格；\n"
            "2. 不要简单罗列数字，要解释数据变化的原因和含义；\n"
            "3. 重点关注：规模格局、增长驱动因素（业绩/持营/新发）、业绩排名特点；\n"
            "4. 对比同业表现，指出我司（工银瑞信）的相对位置和特点；\n"
            "5. 使用第三人称，语气客观专业；\n"
            "6. 中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 同业十五家基金公司权益规模及业绩情况的结构化数据：\n\n"
            "{data_json}\n\n"
            "数据字段说明：\n"
            "- scale_q4: 上季末规模(亿元), scale_q1: 本季末规模\n"
            "- chg_pct: 规模变动幅度(%)\n"
            "- perf_contrib: 收益率上涨(亿元), holding: 持营(亿元), new_issue: 新发(亿元)\n"
            "- ret_q: 当季投资收益率, rank_q: 同业排名(如 78/126)\n"
            "- ret_3y: 三年投资收益率, is_us: 是否为我司(工银瑞信)\n\n"
            "请根据以上数据，撰写该表的分析文字。"
        ),
    },
    "board_allocation": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各基金公司板块配置数据（六板块+A股/港股），请分析配置特点和差异。\n"
            "要求：2-3段专业分析，不罗列数字，关注：各板块配置中枢、集中度、我司与同业差异、港股配置特点。中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 基金公司季度板块配置数据：\n\n{data_json}\n\n"
            "字段：TMT/金融地产/消费/新能源及制造/周期/医药为各板块占股票市值比，A股/港股为市场占比。\n"
            "corp=公司名, is_us=是否我司(工银瑞信)。请分析板块配置特点和我司差异。"
        ),
    },
    "board_change": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司板块变动数据（剔除涨跌幅后的主动调仓），请分析调仓方向。\n"
            "要求：2-3段专业分析，关注：整体调仓方向、各板块分歧、我司操作特点、行业调整比例。中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 基金公司板块变化（剔除涨跌幅）数据：\n\n{data_json}\n\n"
            "字段：六板块+A股/港股为占比变化(pp), adjust=行业调整比例(各板块变动绝对值之和)。\n"
            "正值=增持, 负值=减持。请分析调仓方向和我司特点。"
        ),
    },
    "top10_holdings": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司前十大重仓股数据，请分析重仓股特征。\n"
            "要求：2-3段专业分析，关注：共识持仓(CPO等)、差异化配置、重仓股表现、我司特点。中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 基金公司前十大重仓股数据：\n\n{data_json}\n\n"
            "每家公司有 stocks(10只重仓股, 含name和ret个股收益率) 和 avg_ret(季度平均涨跌幅)。\n"
            "请分析共识持仓、差异化和我司重仓股特点。"
        ),
    },
    "concentration_position": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司集中度和仓位的时间序列数据，请分析变化趋势。\n"
            "要求：2-3段专业分析，关注：集中度排名和变化趋势、仓位水平和趋势、我司特点。中文撰写。"
        ),
        "template": (
            "以下是各基金公司 TOP20个股集中度与 TOP3行业集中度时间序列数据：\n\n{data_json}\n\n"
            "请分析集中度排名、变化趋势和我司特点。"
        ),
    },
    "position_trend": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司仓位时间序列（规模加权/算术平均），请分析仓位水平趋势。\n"
            "要求：2段专业分析，关注：仓位中枢水平、变化趋势、高低差异、我司特点。中文撰写。"
        ),
        "template": (
            "以下是各基金公司仓位（规模加权/算术平均）时间序列数据：\n\n{data_json}\n\n"
            "请分析仓位水平和趋势、我司特点。"
        ),
    },
    "scale_history": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司逐季规模及变动拆分数据，请分析规模变动趋势。\n"
            "要求：2-3段专业分析，关注：规模格局、增长驱动（业绩/持营/新发）趋势、我司特点。中文撰写。"
        ),
        "template": (
            "以下是各基金公司逐季规模及变动拆分（亿元）数据：\n\n{data_json}\n\n"
            "quarters=各季末规模, splits=各季拆分(perf=收益率上涨, holding=持营, new=新发)。\n"
            "请分析规模变动趋势和我司特点。"
        ),
    },
    "scale_bin_type": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到两个图表的数据：\n"
            "1) 各规模变化区间下基金数量及平均收益率；\n"
            "2) 各类型产品规模变动。\n"
            "请综合分析产品维度规模变动特征。\n"
            "要求：2段专业分析，关注：收益率与规模变动关系、产品类型变化方向、科技/消费等赛道特征。中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 产品维度规模变动数据：\n\n{data_json}\n\n"
            "bin_chart=各规模变动区间的基金数量和平均收益率, type_change=各产品类型的规模变动。\n"
            "请综合分析收益率与规模变动的关系、产品类型变化方向。"
        ),
    },
    "product_top10": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到一季度规模增长TOP10和缩减TOP10产品数据，请分析产品层面的规模变动。\n"
            "要求：2-3段专业分析，关注：增长TOP10产品特征（类型/公司集中度/业绩关联）、缩减TOP10产品原因、异常变动。中文撰写。"
        ),
        "template": (
            "以下是 {quarter} 规模增长TOP10及缩减TOP10产品数据：\n\n{data_json}\n\n"
            "growth=增长TOP10, decline=缩减TOP10, 每个含name/corp/type/delta(规模变动亿)/ret(收益率)/max_dd(最大回撤)。\n"
            "请分析增长和缩减产品的特征。"
        ),
    },
    "return_vs_drawdown": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到各公司加权收益率与最大回撤数据，请分析风险收益特征。\n"
            "要求：2段专业分析，关注：收益率与回撤的分布、哪家公司在风险收益上表现最优、我司定位。中文撰写。"
        ),
        "template": (
            "以下是各公司 {quarter} 加权收益率与最大回撤数据：\n\n{data_json}\n\n"
            "ret=加权收益率(%), dd=加权最大回撤(%), is_us=是否我司。\n"
            "请分析风险收益特征和我司定位。"
        ),
    },
    "company_profile_a": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到某公司产品规模画像数据，请总结该公司产品结构特征。\n"
            "要求：2段专业分析，关注：产品集中度(CR)、头部产品依赖度、类型构成特点。中文撰写。"
        ),
        "template": (
            "以下是 {corp} 产品规模画像数据：\n\n{data_json}\n\n"
            "请总结产品结构特征、集中度风险和类型布局。"
        ),
    },
    "company_profile_b": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到某公司产品增长来源数据，请总结增长驱动因素。\n"
            "要求：2段专业分析，关注：增长TOP产品、业绩与规模关联、增长驱动类型。中文撰写。"
        ),
        "template": (
            "以下是 {corp} 产品增长来源数据：\n\n{data_json}\n\n"
            "请总结增长驱动因素和业绩关联。"
        ),
    },
    "company_profile_c": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到某公司产品布局分析数据，请总结布局特征。\n"
            "要求：2段专业分析，关注：类型规模变化、布局演变方向、战略特征。中文撰写。"
        ),
        "template": (
            "以下是 {corp} 产品布局分析数据：\n\n{data_json}\n\n"
            "请总结产品布局演变和战略方向。"
        ),
    },
    "company_profile_d": {
        "system": (
            "你是基金公司风险管理部的资深分析师。你将收到某公司产品特征分析数据，请总结产品生命周期特征。\n"
            "要求：2段专业分析，关注：产品年限分布、规模分布形态、增长持续性评估。中文撰写。"
        ),
        "template": (
            "以下是 {corp} 产品特征分析数据：\n\n{data_json}\n\n"
            "请总结产品生命周期特征和增长持续性。"
        ),
    },
}


if __name__ == "__main__":
    print(f"Cache dir: {CACHE_DIR}")
    print(f"Base URL: {ANTHROPIC_BASE_URL}")
    print(f"Model: {ANTHROPIC_MODEL}")
    print(f"API key: {'configured' if ANTHROPIC_API_KEY else 'NOT set'}")
    print(f"Prompts: {list(PROMPTS.keys())}")


# 追加 2.1-2.4 各表独立 Prompt
PROMPTS["board_2_1"] = {
    "system": "你是基金公司风险管理部的资深分析师。分析板块配置表（六板块+A股/港股占比），关注配置中枢、集中度、我司差异。2段，中文。",
    "template": "以下是 {quarter} 基金公司季度板块配置（表2.1）数据：\n\n{data_json}\n\n六板块占比之和100%，A股/港股为市场占比。请分析配置特点和我司(工银瑞信)差异。",
}
PROMPTS["board_2_2"] = {
    "system": "你是基金公司风险管理部的资深分析师。分析A股/港股板块配置拆分表，关注各市场内板块配置差异、港股特点。2段，中文。",
    "template": "以下是 {quarter} A股/港股板块配置拆分（表2.2）数据：\n\n{data_json}\n\nA股和港股各自六板块占比之和100%。请分析各市场配置差异和我司特点。",
}
PROMPTS["board_2_3"] = {
    "system": "你是基金公司风险管理部的资深分析师。分析板块变动表（剔除涨跌幅），关注调仓方向、分歧、我司操作。2段，中文。",
    "template": "以下是 {quarter} 板块变动（表2.3，剔除涨跌幅）数据：\n\n{data_json}\n\n正值=增持，负值=减持，adjust=行业调整比例。请分析调仓方向和我司特点。",
}
PROMPTS["board_2_4"] = {
    "system": "你是基金公司风险管理部的资深分析师。分析A股/港股板块变动拆分，关注各市场调仓差异。2段，中文。",
    "template": "以下是 {quarter} A股/港股板块变动拆分（表2.4）数据：\n\n{data_json}\n\n各市场内六板块占比变化。请分析各市场调仓差异和我司特点。",
}
