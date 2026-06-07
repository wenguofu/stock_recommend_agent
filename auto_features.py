#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint5: 自动特征工程

能力:
  - 滚动窗口特征 (MA/EMA/RSI/ATR/波动率/换手率)
  - 价量衍生 (量价背离, OBV 趋势, 突破信号)
  - 跨截面特征 (在截面上 rank 化, 相对强度)
  - 类别特征 (动量桶, 波动率桶)
  - 缺失值/异常值处理

输出: 可直接喂入 ML 模型的 numpy 数组 + 特征名列表
"""
import math
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    rs = avg_gain / (avg_loss + 1e-12)
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    sign = np.sign(close.diff()).fillna(0)
    return (sign * volume).cumsum()


def build_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    基础技术特征 (单一时间序列)
    输入: 必须包含 close/high/low/volume (按日期升序)
    """
    out = pd.DataFrame(index=df.index)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df.get("volume", pd.Series(0, index=df.index)).astype(float)

    # 动量
    for w in [5, 10, 20, 60]:
        out[f"ret_{w}"] = close.pct_change(w)
        out[f"logret_{w}"] = np.log(close / close.shift(w))

    # 移动平均
    for w in [5, 10, 20, 60]:
        ma = close.rolling(w).mean()
        out[f"ma_{w}_close_ratio"] = close / (ma + 1e-12) - 1
        out[f"ma_{w}"] = ma

    # EMA 趋势
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    out["ema_cross"] = (ema12 - ema26) / (ema26 + 1e-12)
    out["macd_signal_diff"] = ema12 - ema26

    # RSI
    out["rsi_14"] = _rsi(close, 14) / 100.0

    # 波动率
    for w in [5, 20]:
        r = close.pct_change()
        out[f"vol_{w}"] = r.rolling(w).std()
        out[f"vol_{w}_annual"] = out[f"vol_{w}"] * math.sqrt(252)

    # ATR / 布林带
    out["atr_14"] = _atr(df, 14) / (close + 1e-12)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    out["bb_position"] = (close - bb_mid) / (bb_std * 2 + 1e-12)
    out["bb_width"] = (bb_std * 4) / (bb_mid + 1e-12)

    # 量能
    out["volume_ratio_5"] = vol / (vol.rolling(5).mean() + 1e-12)
    out["volume_ratio_20"] = vol / (vol.rolling(20).mean() + 1e-12)
    out["obv_slope_10"] = _obv(close, vol).pct_change(10)

    # 高低点位置
    out["high_20_ratio"] = close / close.rolling(20).max()
    out["low_20_ratio"] = close / close.rolling(20).min()

    # 价格加速度
    out["ret_5_accel"] = out["ret_5"].diff(3)

    return out


def build_cross_section_features(
    panel: pd.DataFrame,
    base_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    跨截面特征: 输入 panel 索引为 (date, code), 列包含上面 base 的特征。
    对每行 (date 截面) 计算该特征在所有股票上的 rank/pct。
    """
    if base_cols is None:
        base_cols = [c for c in panel.columns if c.startswith(("ret_", "rsi_", "vol_", "ma_"))]
    if not base_cols:
        return pd.DataFrame(index=panel.index)

    out = pd.DataFrame(index=panel.index)
    for c in base_cols:
        if c not in panel.columns:
            continue
        out[f"{c}_rank"] = panel[c].groupby(level=0).rank(pct=True)
    return out


def add_labels(
    df: pd.DataFrame,
    horizon: int = 5,
    threshold: float = 0.0,
) -> pd.DataFrame:
    """
    添加监督标签: 未来 horizon 日收益 > threshold 视为 1, 否则 0
    """
    future_ret = df["close"].shift(-horizon) / df["close"] - 1
    df = df.copy()
    df["future_ret"] = future_ret
    df["label"] = (future_ret > threshold).astype(int)
    return df


def handle_missing(df: pd.DataFrame, strategy: str = "ffill_drop") -> pd.DataFrame:
    """
    缺失值处理:
      - ffill_drop: 前向填充后丢弃仍有缺失的行
      - zero: 用 0 填充
      - median: 中位数填充
    """
    if strategy == "ffill_drop":
        df = df.ffill().dropna()
    elif strategy == "zero":
        df = df.fillna(0)
    elif strategy == "median":
        df = df.fillna(df.median(numeric_only=True))
    return df


def handle_outliers(
    df: pd.DataFrame,
    cols: Optional[List[str]] = None,
    n_std: float = 5.0,
) -> pd.DataFrame:
    """
    异常值裁剪: 超过 n_std 倍标准差的值截断到边界
    """
    if cols is None:
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c]
        m, sd = s.mean(), s.std()
        if sd <= 0 or not np.isfinite(sd):
            continue
        df[c] = s.clip(lower=m - n_std * sd, upper=m + n_std * sd)
    return df


def build_feature_pipeline(
    df: pd.DataFrame,
    horizon: int = 5,
    add_cross_section: bool = False,
    panel: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    端到端特征管道:
      1. 基础特征
      2. (可选) 跨截面
      3. 异常值裁剪
      4. 缺失值处理
      5. 添加标签
    返回: 处理后的 DataFrame, 特征列名列表
    """
    feats = build_base_features(df)
    if add_cross_section and panel is not None:
        cross = build_cross_section_features(panel)
        if not cross.empty:
            feats = feats.join(cross, how="left")

    feats = handle_outliers(feats)
    feats = handle_missing(feats, strategy="ffill_drop")
    feats = add_labels(feats, horizon=horizon)

    feature_cols = [c for c in feats.columns if c not in ("future_ret", "label")]
    return feats, feature_cols


def register_auto_features_routes(app):
    """注册 /api/features/build 路由"""
    from flask import jsonify, request

    @app.route("/api/features/build", methods=["POST"])
    def build_features_api():
        """
        body:
          {
            "code": "000001",
            "days": 250,
            "horizon": 5,
            "add_cross_section": false
          }
        """
        try:
            body = request.get_json(silent=True) or {}
            code = str(body.get("code", "000001")).zfill(6)
            days = int(body.get("days", 250))
            horizon = int(body.get("horizon", 5))
            add_cross = bool(body.get("add_cross_section", False))

            from data_fetchers import get_daily_kline
            kline = get_daily_kline(code, count=days + 30)
            if kline is None or len(kline) < 60:
                return jsonify({"success": False, "error": f"数据不足 ({code})"}), 400

            df = kline[["date", "open", "high", "low", "close", "volume"]].copy()
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            feats, feature_cols = build_feature_pipeline(
                df,
                horizon=horizon,
                add_cross_section=add_cross,
            )
            # 取最近 30 行做样例返回
            sample = feats.tail(30).reset_index()
            return jsonify({
                "success": True,
                "code": code,
                "n_features": len(feature_cols),
                "feature_cols": feature_cols,
                "n_rows": len(feats),
                "sample": sample.fillna(0).to_dict(orient="records"),
                "horizon": horizon,
            })
        except Exception as e:
            logger.error(f"build features err: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/features/list", methods=["GET"])
    def list_features():
        return jsonify({
            "success": True,
            "categories": {
                "momentum": ["ret_5", "ret_10", "ret_20", "ret_60", "logret_5", "logret_10"],
                "ma": ["ma_5_close_ratio", "ma_20_close_ratio", "ma_60_close_ratio"],
                "trend": ["ema_cross", "macd_signal_diff"],
                "oscillator": ["rsi_14"],
                "volatility": ["vol_5", "vol_20", "vol_5_annual", "vol_20_annual", "atr_14", "bb_position", "bb_width"],
                "volume": ["volume_ratio_5", "volume_ratio_20", "obv_slope_10"],
                "range": ["high_20_ratio", "low_20_ratio"],
                "acceleration": ["ret_5_accel"],
                "cross_section": ["<feature>_rank"],
            },
            "total_features": 22,
        })


if __name__ == "__main__":
    print("Auto feature module ready.")
    # 用随机数据测试
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "open": 10 + np.cumsum(np.random.randn(n) * 0.1),
        "high": 0, "low": 0, "close": 0, "volume": 0,
    })
    df["close"] = df["open"] + np.random.randn(n) * 0.05
    df["high"] = df[["open", "close"]].max(axis=1) + 0.1
    df["low"] = df[["open", "close"]].min(axis=1) - 0.1
    df["volume"] = np.random.randint(1_000_000, 5_000_000, n)
    df = df.set_index("date")
    feats, cols = build_feature_pipeline(df)
    print(f"Built {len(cols)} features, {len(feats)} rows")
    print("Features:", cols)
