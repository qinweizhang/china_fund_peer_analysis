"""Flask 应用入口与路由。

四个模块页面：
  /            模块一：同业业绩及规模概况
  /holdings    模块二：同业持仓及变动分析
  /scale       模块三：同业规模及变动分析
  /company     模块四：公司专题分析

数据集（只读终端：数据在后端 input_data 目录维护，自动取最新文件，网页不上传、不切换）：
  /api/company/<corp>  公司画像数据接口（供模块四 AJAX 局部刷新）
"""
from __future__ import annotations

import json
import os

from flask import Flask, render_template, request, url_for

from . import data_loader as dl
from . import metrics
from . import ai_analyzer

app = Flask(__name__)
# session 签名密钥（用于保存当前激活数据集 id）。生产部署应改为环境变量。
app.secret_key = os.environ.get("PEER_SECRET", "peer-analysis-dev-secret")


def _q_label(qstr: str | None) -> str:
    """'2026-03-31' -> '2026Q1'；空值返回 '—'。"""
    if not qstr:
        return "—"
    try:
        y, m, _ = qstr.split("-")
        return f"{y}Q{(int(m) - 1) // 3 + 1}"
    except Exception:
        return qstr


@app.context_processor
def inject_globals():
    latest = dl.latest_q()
    prev = dl.prev_q()
    year_start = dl.year_start_q()
    latest_year = int(latest[:4]) if latest else None
    ret_3y_label = f"{latest_year - 2}-{latest_year}" if latest_year else "—"
    return {
        "OUR_COMPANY": dl.OUR_COMPANY,
        "LATEST_Q": latest,
        "PREV_Q": prev,
        "LATEST_Q_LABEL": _q_label(latest),
        "PREV_Q_LABEL": _q_label(prev),
        "YEAR_START_Q": year_start,
        "YEAR_START_Q_LABEL": _q_label(year_start),
        "LATEST_YEAR": latest_year,
        "RET_3Y_LABEL": ret_3y_label,
        "BOARDS": metrics.BOARDS,
        "MARKETS": metrics.MARKETS,
        "CORPS": dl.peer_corps(),
        "DATASETS": dl.datasets(),
        "ACTIVE_LABEL": dl.active_label(),
    }


@app.route("/")
def module1():
    rows, kpi = metrics.company_overview()
    # AI 分析：公司规模及业绩总览（暂注释，保留代码待恢复）
    # analysis_data = {
    #     "quarter": dl.latest_q()[:7] if dl.latest_q() else "",
    #     "companies": [
    #         {
    #             "corp": r["corp"], "scale_q4": r["scale_q4"], "scale_q1": r["scale_q1"],
    #             "chg_pct": r["chg_pct"], "perf_contrib": r["perf_contrib"],
    #             "holding": r["holding"], "new_issue": r["new_issue"],
    #             "ret_q": r["ret_q"], "rank_q": r["rank_q"],
    #             "ret_3y": r["ret_3y"], "is_us": r["is_us"],
    #         } for r in rows
    #     ],
    # }
    # ai_insight = ai_analyzer.generate_analysis(
    #     "company_overview", analysis_data,
    #     {"quarter": analysis_data["quarter"]},
    # )
    return render_template(
        "module1.html",
        active="m1",
        rows=rows,
        kpi=kpi,
        # ai_insight=ai_insight,
    )


@app.route("/holdings")
def module2():
    board_rows, board_extra = metrics.board_table()
    bmarket_rows, bmarket_extra = metrics.board_table_by_market()
    change_rows = metrics.board_change_table()
    change_market_rows = metrics.board_change_table_by_market()
    top10 = metrics.top10_holdings()
    conc = metrics.concentration_series()
    pos = metrics.position_series()
    # latest_q = dl.latest_q()[:7] if dl.latest_q() else ""  # 仅供 AI 分析使用

    # AI 分析（每表独立）——暂注释，保留代码待恢复
    # board_2_1_data = [{"corp": r["corp"], "is_us": r["is_us"],
    #       **{b: round(r[b]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药","A股","港股"]}}
    #      for r in board_rows]
    # ai_2_1 = ai_analyzer.generate_analysis("board_2_1", board_2_1_data, {"quarter": latest_q})
    #
    # bmarket_2_2_data = [{"corp": r["corp"], "is_us": r["is_us"],
    #       **{f"A股_{b}": round(r[f"A股_{b}"]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药"]},
    #       **{f"港股_{b}": round(r[f"港股_{b}"]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药"]}}
    #      for r in bmarket_rows]
    # ai_2_2 = ai_analyzer.generate_analysis("board_2_2", bmarket_2_2_data, {"quarter": latest_q})
    #
    # change_2_3_data = [{"corp": r["corp"], "is_us": r.get("is_us", False),
    #       **{b: round(r[b]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药","A股","港股"]},
    #       "adjust": round(r["adjust"]*100, 2)}
    #      for r in change_rows]
    # ai_2_3 = ai_analyzer.generate_analysis("board_2_3", change_2_3_data, {"quarter": latest_q})
    #
    # cmarket_2_4_data = [{"corp": r["corp"], "is_us": r.get("is_us", False),
    #       **{f"A股_{b}": round(r[f"A股_{b}"]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药"]},
    #       **{f"港股_{b}": round(r[f"港股_{b}"]*100, 2) for b in ["TMT","金融地产","消费","新能源及制造","周期","医药"]}}
    #      for r in change_market_rows]
    # ai_2_4 = ai_analyzer.generate_analysis("board_2_4", cmarket_2_4_data, {"quarter": latest_q})
    #
    # ai_2_5 = ai_analyzer.generate_analysis("top10_holdings", top10, {"quarter": latest_q})
    # ai_conc = ai_analyzer.generate_analysis("concentration_position", conc, {"quarter": latest_q})
    # ai_pos = ai_analyzer.generate_analysis("position_trend", pos, {"quarter": latest_q})

    return render_template(
        "module2.html",
        active="m2",
        board_rows=board_rows,
        board_extra=board_extra,
        bmarket_rows=bmarket_rows,
        bmarket_extra=bmarket_extra,
        change_rows=change_rows,
        change_market_rows=change_market_rows,
        top10=top10,
        concentration_json=json.dumps(conc, ensure_ascii=False),
        position_json=json.dumps(pos, ensure_ascii=False),
        # ai_2_1=ai_2_1, ai_2_2=ai_2_2, ai_2_3=ai_2_3, ai_2_4=ai_2_4,
        # ai_2_5=ai_2_5, ai_conc=ai_conc, ai_pos=ai_pos,
    )


@app.route("/scale")
def module3():
    growth, decline = metrics.product_top10()
    sh = metrics.scale_history()
    rvd = metrics.return_vs_drawdown()
    scale_bin = metrics.scale_bin_chart()
    type_change = metrics.type_scale_change()
    # latest_q = dl.latest_q()[:7] if dl.latest_q() else ""  # 仅供 AI 分析使用

    # AI 分析——暂注释，保留代码待恢复
    # ai_scale = ai_analyzer.generate_analysis("scale_history", sh, {"quarter": latest_q})
    # ai_bin_type = ai_analyzer.generate_analysis("scale_bin_type",
    #     {"bin_chart": scale_bin, "type_change": type_change}, {"quarter": latest_q})
    # ai_top10 = ai_analyzer.generate_analysis("product_top10",
    #     {"growth": growth, "decline": decline}, {"quarter": latest_q})
    # ai_rvd = ai_analyzer.generate_analysis("return_vs_drawdown", rvd, {"quarter": latest_q})

    return render_template(
        "module3.html",
        active="m3",
        scale=sh,
        growth=growth,
        decline=decline,
        rvd=rvd,
        yongying=metrics.yongying_products(),
        layout_json=json.dumps(metrics.product_layout(), ensure_ascii=False),
        scale_bin_json=json.dumps(scale_bin, ensure_ascii=False),
        type_change_json=json.dumps(type_change, ensure_ascii=False),
        # ai_scale=ai_scale, ai_bin_type=ai_bin_type, ai_top10=ai_top10, ai_rvd=ai_rvd,
    )


@app.route("/company")
def module4():
    """模块四：公司专题分析。"""
    corp = request.args.get("corp") or dl.OUR_COMPANY
    return render_template(
        "module4.html",
        active="m4",
        selected_corp=corp,
    )


@app.route("/api/company/<corp>")
def api_company(corp):
    """公司通用分析 API：返回选中公司的产品规模画像 + 四板块 AI 分析。

    供 module4 前端 AJAX 局部刷新使用——切换公司只重跑这一板块，不重载整页。
    """
    from flask import jsonify
    import math

    def _sanitize(obj):
        """递归把 NaN/Inf 转成 None，避免 jsonify 输出非法 JSON token
        （浏览器 Response.json() 严格解析，NaN 会报 'did not match expected pattern'）。"""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    profile = metrics.company_profile(corp)
    # AI 分析四板块——暂注释，保留代码待恢复（注释后 API 秒回，04 局部刷新不受 AI 耗时影响）
    # profile["ai_pa"] = ai_analyzer.generate_analysis("company_profile_a",
    #     {"total": profile["total"], "product_count": profile["product_count"],
    #      "concentration": profile["concentration"],
    #      "top_products": profile["top_products"][:10],
    #      "type_composition": profile["type_composition"]},
    #     {"corp": corp})
    # profile["ai_pb"] = ai_analyzer.generate_analysis("company_profile_b",
    #     {"growth_products": profile.get("growth_products", []),
    #      "scatter_points": profile.get("scatter_points", [])},
    #     {"corp": corp})
    # profile["ai_pc"] = ai_analyzer.generate_analysis("company_profile_c",
    #     {"layout": profile.get("layout", {}), "type_change": profile.get("type_change", [])},
    #     {"corp": corp})
    # profile["ai_pd"] = ai_analyzer.generate_analysis("company_profile_d",
    #     {"scatter_age_points": profile.get("scatter_age_points", []),
    #      "histogram": profile.get("histogram", [])},
    #     {"corp": corp})
    return jsonify(_sanitize(profile))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
