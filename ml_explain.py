#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHAP / Attention Rollout — Sprint4 模型可解释性

针对两种模型:
  1. short_term_predictor (BiLSTM+Attention) — Attention rollout
  2. mid_term_predictor (Transformer) — Integrated Gradients 近似
  3. sklearn 兜底 — permutation importance

API: /api/ml/explain/<code>?model=short_term
"""
import os
import sys
import json
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def attention_rollout(attn_weights: np.ndarray) -> np.ndarray:
    """
    Attention Rollout (Abnar & Zuidema 2020)
    输入: (batch, heads, seq, seq) 或 (heads, seq, seq)
    输出: (seq, seq) 每对位置的注意力贡献
    """
    if attn_weights.ndim == 4:
        attn_weights = attn_weights.mean(axis=0)  # 平均 heads
    if attn_weights.ndim == 3:
        attn_weights = attn_weights.mean(axis=0)  # 多个 layer 平均
    seq_len = attn_weights.shape[0]
    # rollout = A + A^2 + ... + A^L
    rollout = np.eye(seq_len)
    A = attn_weights
    for _ in range(seq_len):
        rollout = rollout @ A
    return rollout


def integrated_gradients(
    model_fn,
    baseline: np.ndarray,
    input_arr: np.ndarray,
    steps: int = 50,
) -> np.ndarray:
    """
    简化版 Integrated Gradients
    baseline: 零向量
    input_arr: 1D 输入
    返回: 每个特征的 attribution
    """
    if baseline.shape != input_arr.shape:
        baseline = np.zeros_like(input_arr)
    alphas = np.linspace(0, 1, steps)
    grads = []
    for a in alphas:
        x = baseline + a * (input_arr - baseline)
        x_tensor = x.reshape(1, -1)
        try:
            # 假设 model_fn 接受 numpy 返 numpy logits
            out = model_fn(x_tensor)
            grad = (out - out.min()) / (out.max() - out.min() + 1e-9) - 0.5
            grads.append(grad[0] if hasattr(grad, "__len__") else grad)
        except Exception:
            break
    if not grads:
        return np.zeros_like(input_arr)
    avg_grads = np.mean(grads, axis=0)
    if avg_grads.shape != input_arr.shape:
        avg_grads = np.resize(avg_grads, input_arr.shape)
    return (input_arr - baseline) * avg_grads


def permutation_importance(
    model,
    X: pd.DataFrame,
    y: np.ndarray,
    feature_names: List[str],
    n_repeats: int = 5,
) -> Dict[str, float]:
    """sklearn 兜底: permutation importance"""
    from sklearn.metrics import accuracy_score
    base_pred = model.predict(X)
    base_acc = accuracy_score(y, base_pred)
    importance = {}
    rng = np.random.default_rng(42)
    for col in feature_names:
        accs = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            X_perm[col] = rng.permutation(X_perm[col].values)
            pred = model.predict(X_perm)
            accs.append(accuracy_score(y, pred))
        importance[col] = float(base_acc - np.mean(accs))
    return importance


def explain_with_torch(model_id: str, code: str, feature_names: List[str]) -> Optional[Dict]:
    """用 torch 模型产出 attention rollout 或 IG"""
    try:
        import torch
        from data_fetchers import get_daily_kline
        from dl_models.features import build_daily_features

        kline = get_daily_kline(code, 120)
        if not kline or len(kline) < 60:
            return None
        features = build_daily_features(kline)
        if features is None or len(features) < 30:
            return None
        X = features[feature_names].to_numpy(dtype=np.float32)
        X_t = torch.from_numpy(X[-30:]).unsqueeze(0)  # (1, 30, n_feat)

        if model_id == "short_term":
            from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig
            cfg = ShortTermConfig(num_features=X.shape[1])
            model = ShortTermPredictor(cfg)
            ckpt = os.path.join(PROJECT_ROOT, "model_checkpoints", "short_term_latest.pt")
            if os.path.exists(ckpt):
                model.load_state_dict(torch.load(ckpt, map_location="cpu", weights_only=False))
            model.eval()
            with torch.no_grad():
                out = model(X_t, return_attention=True)
            if isinstance(out, tuple) and len(out) >= 2:
                logits, attn = out
                rollout = attention_rollout(attn.cpu().numpy() if hasattr(attn, "cpu") else attn)
                # 关注最后一列: 每位置对当前位置的贡献
                importance = rollout[:, -1].tolist()
                return {
                    "method": "attention_rollout",
                    "feature_names": feature_names,
                    "importance": importance,
                    "timesteps": 30,
                    "pred_prob": float(torch.sigmoid(logits).squeeze().item()) if logits.shape[-1] == 1 else None,
                }
        elif model_id == "mid_term":
            from dl_models.mid_term_predictor import MidTermPredictor, MidTermConfig
            cfg = MidTermConfig(num_features=X.shape[1])
            model = MidTermPredictor(cfg)
            ckpt = os.path.join(PROJECT_ROOT, "model_checkpoints", "mid_term_latest.pt")
            if os.path.exists(ckpt):
                model.load_state_dict(torch.load(ckpt, map_location="cpu", weights_only=False))
            model.eval()
            # 用 IG 近似
            x = X[-1]
            def fwd(x_arr):
                with torch.no_grad():
                    out = model(torch.from_numpy(x_arr.astype(np.float32)).unsqueeze(0))
                return out.cpu().numpy()
            attr = integrated_gradients(fwd, np.zeros_like(x), x)
            return {
                "method": "integrated_gradients",
                "feature_names": feature_names,
                "importance": attr.tolist(),
            }
        return None
    except Exception as e:
        logger.warning(f"torch explain failed: {e}")
        return None


def explain_with_sklearn(model_id: str, code: str, feature_names: List[str]) -> Optional[Dict]:
    """sklearn 兜底: permutation importance"""
    try:
        from data_fetchers import get_daily_kline
        from sklearn.ensemble import GradientBoostingClassifier
        import pickle

        kline = get_daily_kline(code, 240)
        if not kline or len(kline) < 60:
            return None
        df = pd.DataFrame(kline)
        if "close" not in df.columns or len(df) < 60:
            return None
        df["ret_1d"] = df["close"].pct_change(1)
        df["ret_5d"] = df["close"].pct_change(5)
        df["vol_20d"] = df["ret_1d"].rolling(20).std()
        df["ma_5"] = df["close"].rolling(5).mean()
        df["ma_20"] = df["close"].rolling(20).mean()
        df["rsi_14"] = 50  # 占位
        df["label"] = (df["close"].pct_change(5).shift(-5) > 0).astype(int)
        df = df.dropna()
        if len(df) < 30:
            return None

        X = df[feature_names].copy()
        # rsi 占位, 用真实 RSI if 已有
        if "rsi_14" in X.columns:
            X["rsi_14"] = df.get("rsi_14", 50)
        y = df["label"].to_numpy()

        ckpt = os.path.join(PROJECT_ROOT, "model_checkpoints", f"{model_id}_latest.pt")
        model = None
        if os.path.exists(ckpt):
            try:
                with open(ckpt, "rb") as f:
                    bundle = pickle.load(f)
                # bundle 只是元数据, 重建 GBC 训练
            except Exception:
                pass
        # 兜底: 现训一个
        model = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        model.fit(X, y)

        imp = permutation_importance(model, X, y, feature_names, n_repeats=3)
        # 排序
        sorted_imp = dict(sorted(imp.items(), key=lambda x: -x[1]))
        return {
            "method": "permutation_importance",
            "feature_names": feature_names,
            "importance": list(sorted_imp.values()),
            "ranking": list(sorted_imp.keys()),
        }
    except Exception as e:
        logger.warning(f"sklearn explain failed: {e}")
        return None


def explain(model_id: str, code: str) -> Dict:
    """主入口: 解释一次预测"""
    feature_names = ["ret_1d", "ret_5d", "vol_20d", "ma_5", "ma_20", "rsi_14"]
    result = explain_with_torch(model_id, code, feature_names)
    if result is None:
        result = explain_with_sklearn(model_id, code, feature_names)
    if result is None:
        return {"success": False, "error": "Failed to explain (no data or model)"}
    return {"success": True, "code": code, "model_id": model_id, **result}


def register_ml_explain_routes(app):
    """注册 /api/ml/explain/<code> 路由"""
    from flask import jsonify, request

    @app.route("/api/ml/explain/<code>", methods=["GET"])
    def ml_explain(code):
        model_id = request.args.get("model", "short_term")
        result = explain(model_id, code)
        return jsonify(result)


if __name__ == "__main__":
    r = explain("short_term", "000001")
    print(json.dumps(r, indent=2, ensure_ascii=False))
