"""Flask 应用入口与路由。

三个模块页面：
  /            模块一：同业业绩及规模概况
  /holdings    模块二：同业持仓及变动分析
  /scale       模块三：同业规模及变动分析
"""
from __future__ import annotations

import json

from flask import Flask, render_template

from . import metrics

app = Flask(__name__)


@app.context_processor
def inject_globals():
    return {"OUR_COMPANY": "工银瑞信", "LATEST_Q": "2026-03-31"}


@app.route("/")
def module1():
    return render_template(
        "module1.html",
        active="m1",
        rows=metrics.company_overview(),
    )


@app.route("/holdings")
def module2():
    rows, extra = metrics.board_table()
    change_rows = metrics.board_change_table()
    top10 = metrics.top10_holdings()
    return render_template(
        "module2.html",
        active="m2",
        board_rows=rows,
        board_extra=extra,
        change_rows=change_rows,
        top10=top10,
        concentration_json=json.dumps(metrics.concentration_series(), ensure_ascii=False),
        position_json=json.dumps(metrics.position_series(), ensure_ascii=False),
    )


@app.route("/scale")
def module3():
    growth, decline = metrics.product_top10()
    return render_template(
        "module3.html",
        active="m3",
        scale=metrics.scale_history(),
        growth=growth,
        decline=decline,
        rvd=metrics.return_vs_drawdown(),
        yongying=metrics.yongying_products(),
        layout_json=json.dumps(metrics.product_layout(), ensure_ascii=False),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
