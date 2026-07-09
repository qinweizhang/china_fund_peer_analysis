"""Flask 应用入口与路由。

三个模块页面：
  /            模块一：同业业绩及规模概况
  /holdings    模块二：同业持仓及变动分析
  /scale       模块三：同业规模及变动分析

数据集管理：
  /dataset     切换当前激活数据集（POST ?id=...）
  /upload      上传新的季度 Excel 文件并切换为激活数据集（POST multipart）
"""
from __future__ import annotations

import json
import os

from flask import Flask, redirect, render_template, request, session, url_for

from . import data_loader as dl
from . import metrics

app = Flask(__name__)
# session 签名密钥（用于保存当前激活数据集 id）。生产部署应改为环境变量。
app.secret_key = os.environ.get("PEER_SECRET", "peer-analysis-dev-secret")


@app.context_processor
def inject_globals():
    return {
        "OUR_COMPANY": dl.OUR_COMPANY,
        "LATEST_Q": dl.latest_q(),
        "BOARDS": metrics.BOARDS,
        "MARKETS": metrics.MARKETS,
        "DATASETS": dl.datasets(),
        "ACTIVE_LABEL": dl.active_label(),
        "ACTIVE_ID": session.get("dataset_id"),
    }


@app.route("/")
def module1():
    return render_template(
        "module1.html",
        active="m1",
        rows=metrics.company_overview(),
    )


@app.route("/holdings")
def module2():
    board_rows, board_extra = metrics.board_table()
    bmarket_rows, bmarket_extra = metrics.board_table_by_market()
    change_rows = metrics.board_change_table()
    change_market_rows = metrics.board_change_table_by_market()
    top10 = metrics.top10_holdings()
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


@app.route("/dataset", methods=["POST"])
def switch_dataset():
    """切换激活数据集。"""
    ds_id = request.form.get("id")
    if ds_id:
        dl.set_active_id(ds_id)
    # 切换后清缓存（确保新数据集重新读取）
    dl.clear_cache()
    return redirect(request.referrer or url_for("module1"))


@app.route("/upload", methods=["POST"])
def upload():
    """上传新的季度 Excel 并切换为激活数据集。"""
    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(request.referrer or url_for("module1"))
    try:
        ds_id = dl.save_upload(f)
        dl.set_active_id(ds_id)
        dl.clear_cache()
    except ValueError as e:
        return f"上传失败：{e}", 400
    return redirect(request.referrer or url_for("module1"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
