#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块 + 主线预判 + 股票画像路由模块 — 修复 ARCH-01: 拆 api_routes.py

从 api_routes.py 抽离的端点:
  - GET  /api/sector-prediction       主线预判数据
  - POST /api/sector-prediction/run   触发主线预判脚本
  - GET  /api/breakout-scan           突破扫描结果
  - POST /api/breakout-scan/run       触发突破扫描
  - GET  /api/stock/profile/<code>    股票画像(主营/题材/核心竞争力/行业背景)

依赖:
  - subprocess (uv 沙箱执行, BUG-11 待沙箱化)
  - models.get_db, sqlalchemy.text
"""
from flask import jsonify, request
import os
import json
import glob
import logging
import subprocess
from sqlalchemy import text
from models import get_db

logger = logging.getLogger(__name__)

# 项目根
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def register_sector_routes(app):
    """注册板块预判 + 股票画像路由"""

    @app.route("/api/sector-prediction", methods=["GET"])
    def get_sector_prediction():
        """获取主线预判数据"""
        try:
            import os, json, glob
            eval_dir = os.path.join(os.path.dirname(__file__), "eval_result")
            pattern = os.path.join(eval_dir, "主线预判_*.md")
            all_files = sorted(glob.glob(pattern), reverse=True)

            date_param = request.args.get("date", "")
            show_all = request.args.get("all", "false").lower() == "true"

            if date_param:
                target = os.path.join(eval_dir, f"主线预判_{date_param}.md")
                if os.path.exists(target):
                    with open(target, encoding="utf-8") as f:
                        return jsonify({"success": True, "data": {"date": date_param, "report": f.read()}})
                return jsonify({"success": False, "error": f"无{date_param}的预判数据"}), 404

            results = []
            for fpath in all_files[:30]:
                fname = os.path.basename(fpath)
                date_str = fname.replace("主线预判_", "").replace(".md", "")
                with open(fpath, encoding="utf-8") as f:
                    report = f.read()
                if show_all:
                    results.append({"date": date_str, "report": report})
                else:
                    # 只返回最新
                    return jsonify({"success": True, "data": {"date": date_str, "report": report}})

            return jsonify({"success": True, "data": results})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/sector-prediction/run", methods=["POST"])
    def run_sector_prediction():
        """手动触发主线预判 (修复 BUG-11: 模块化调用, 移除 subprocess)"""
        try:
            import sys
            import sector_prediction
            data = request.get_json(silent=True) or {}
            # 可选参数: target_sector 单板块分析
            if data.get("target_sector"):
                sys.argv = ["sector_prediction.py", "--sector", data["target_sector"]]
            else:
                sys.argv = ["sector_prediction.py"]
            result = sector_prediction.main()
            status = 200 if result.get("success") else 500
            return jsonify(result), status
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ═══════════ 突破扫描 API ═══════════
    @app.route("/api/breakout-scan", methods=["GET"])
    def get_breakout_scan():
        """获取突破扫描结果 (修复 BUG-11: 模块化调用)"""
        try:
            import sys
            import breakout_scanner
            data = request.args
            top = data.get("top", "15")
            sys.argv = ["breakout_scanner.py", "--top", top]
            result = breakout_scanner.main()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/breakout-scan/run", methods=["POST"])
    def run_breakout_scan():
        """手动触发突破扫描 (修复 BUG-11: 模块化调用)"""
        try:
            import sys
            import breakout_scanner
            data = request.get_json(silent=True) or {}
            args = ["breakout_scanner.py"]
            if data.get("top_n"):
                args += ["--top", str(data["top_n"])]
            if data.get("code"):
                args += ["--code", str(data["code"])]
            sys.argv = args
            result = breakout_scanner.main()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ─── 股票画像与机构预测 ───

    @app.route('/api/stock/profile/<code>')
    def get_stock_profile(code):
        """获取股票画像（主营、题材、核心竞争力、行业背景）"""
        try:
            code_str = str(code).strip()
            from sqlalchemy import text
            from models import get_db
            db = next(get_db())
            try:
                row = db.execute(
                    text("SELECT * FROM stock_profiles WHERE code = :code"), {"code": code_str}
                ).fetchone()
                if not row:
                    return jsonify({})
                return jsonify(dict(row._mapping))
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analyst/predictions/<code>')
    def get_analyst_predictions(code):
        """获取机构预测汇总"""
        try:
            code_str = str(code).strip()
            from sqlalchemy import text
            from models import get_db
            db = next(get_db())
            try:
                agg = db.execute(
                    text("SELECT * FROM prediction_aggregates WHERE code = :code"), {"code": code_str}
                ).fetchone()
                if not agg:
                    return jsonify({})

                rows = db.execute(
                    text("SELECT * FROM analyst_predictions WHERE code = :code ORDER BY report_date DESC"),
                    {"code": code_str}
                ).fetchall()

                return jsonify({
                    **dict(agg._mapping),
                    "details": [dict(r._mapping) for r in rows]
                })
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': str(e)}), 500


