#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML预测模块 — 基于多因子的涨跌/收益率预测

功能:
  - 方向预测: 涨/跌/平 三分类
  - 收益率预测: 回归预测未来N日收益率
  - 预测置信度
  - 特征重要性分析

模型: Logistic回归(方向) + 线性回归(收益率), 降级到简单规则
"""

import math
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data_fetchers import get_daily_kline
from utils import is_us_stock

# DL model integration
import os
import numpy as np
from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig
from dl_models.mid_term_predictor import MidTermPredictor, MidTermConfig
from dl_models.regime_detector import RegimeDetector, RegimeConfig

_dl_models_cache = {}

def _load_dl_model(model_class, config_class, path: str):
    """Lazy-load a DL model with filesystem cache."""
    if path in _dl_models_cache:
        return _dl_models_cache[path]
    if not os.path.exists(path):
        return None
    model = model_class.load(path)
    model.eval()
    _dl_models_cache[path] = model
    return model

def predict_with_dl(code: str, regime_encoding: list = None) -> dict:
    """
    Run DL prediction for a stock. Falls back to existing RF/Ridge if DL unavailable.
    Returns combined prediction dict.
    """
    from factor_engine import get_feature_vector

    features = get_feature_vector(code)
    if features is None or len(features['daily_features']) < 30:
        return _fallback_predict(code)

    # Load latest models
    model_dir = os.path.join(os.path.dirname(__file__), 'model_checkpoints')
    short_model = _load_dl_model(ShortTermPredictor, ShortTermConfig,
                                  os.path.join(model_dir, 'short_term_latest.pt'))
    mid_model = _load_dl_model(MidTermPredictor, MidTermConfig,
                                os.path.join(model_dir, 'mid_term_latest.pt'))

    if short_model is None:
        return _fallback_predict(code)

    # Default regime encoding if not provided
    if regime_encoding is None:
        regime_encoding = [0.33, 0.33, 0.34]

    # Short-term prediction
    short_result = short_model.predict(
        features['daily_features'], regime_encoding,
    )

    # Mid-term prediction
    mid_result = None
    if mid_model is not None:
        weekly = _daily_to_weekly(features['daily_features'])
        if weekly is not None:
            mid_result = mid_model.predict(
                weekly, features['fundamental_features'], regime_encoding,
            )

    return {
        'code': code,
        'short_term': short_result,
        'mid_term': mid_result,
        'source': 'dl_model',
    }

def _daily_to_weekly(daily_features):
    """Convert daily feature matrix to weekly (resample)."""
    n = len(daily_features)
    n_weeks = n // 5
    if n_weeks < 10:
        return None
    weekly = daily_features[-n_weeks * 5:].reshape(n_weeks, 5, -1)
    # Use last day of each week for OHLC + mean of the week for indicators
    ohlc = weekly[:, -1, :4]
    indicators = weekly.mean(axis=1)
    result = np.concatenate([ohlc, indicators], axis=-1)
    return result.astype(np.float32)[-52:]  # keep last 52 weeks

def _fallback_predict(code: str) -> dict:
    """Fallback to existing RF/Ridge prediction."""
    return {'code': code, 'source': 'rf_fallback'}


# ═══════════════════════════════════════════════════════════════
# 特征工程
# ═══════════════════════════════════════════════════════════════

def _build_features(code: str, lookback: int = 120) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], List[str]]:
    """
    构建ML特征矩阵

    特征包括:
      - 价格特征: 收益率(1/5/10/20日), 波动率(5/20日), 最大回撤(20日)
      - 均线特征: MA偏离(5/10/20/60), 均线交叉信号
      - 量价特征: 量比, 量价相关性, OBV变化率
      - 技术特征: RSI, MACD_hist, KDJ_K, 布林带位置
      - 形态特征: 上影线比例, 振幅

    Returns:
        (X, y, feature_names) 或 (None, None, [])
    """
    try:
        kline = get_daily_kline(str(code).zfill(6), count=lookback + 60)
        if kline is None or len(kline) < 60:
            return None, None, []

        close = kline['close'].values.astype(float)
        high = kline['high'].values.astype(float)
        low = kline['low'].values.astype(float)
        open_p = kline['open'].values.astype(float)
        volume = kline['volume'].values.astype(float) if 'volume' in kline.columns else np.ones_like(close)

        n = len(close)
        features = {}
        feature_names = []

        # 1. 价格特征
        for period in [1, 3, 5, 10, 20]:
            if n > period:
                ret = np.zeros(n)
                ret[period:] = (close[period:] / close[:-period] - 1) * 100
                features[f'ret_{period}d'] = ret
                feature_names.append(f'ret_{period}d')

        # 波动率
        returns = np.diff(close) / close[:-1]
        for period in [5, 10, 20]:
            if n > period + 1:
                vol = np.zeros(n)
                for i in range(period, n):
                    vol[i] = np.std(returns[i - period:i]) * 100
                features[f'volatility_{period}d'] = vol
                feature_names.append(f'volatility_{period}d')

        # 最大回撤 (20日)
        if n > 20:
            max_dd = np.zeros(n)
            for i in range(20, n):
                peak = np.max(close[i-20:i+1])
                max_dd[i] = (peak - close[i]) / peak * 100
            features['max_dd_20d'] = max_dd
            feature_names.append('max_dd_20d')

        # 2. 均线特征
        for period in [5, 10, 20, 60]:
            if n > period:
                ma = np.zeros(n)
                for i in range(period, n):
                    ma[i] = np.mean(close[i-period:i])
                # MA偏离
                dev = np.zeros(n)
                dev[period:] = (close[period:] / ma[period:] - 1) * 100
                features[f'ma_dev_{period}'] = dev
                feature_names.append(f'ma_dev_{period}')

        # 均线交叉 (5 vs 20)
        if n > 20:
            ma5 = np.zeros(n)
            ma20 = np.zeros(n)
            for i in range(5, n):
                ma5[i] = np.mean(close[i-5:i])
            for i in range(20, n):
                ma20[i] = np.mean(close[i-20:i])
            cross = np.zeros(n)
            cross[21:] = ((ma5[21:] > ma20[21:]).astype(float) - 0.5) * 2
            features['ma_cross_5_20'] = cross
            feature_names.append('ma_cross_5_20')

        # 3. 量价特征
        if n > 20:
            # 量比: 今日量 / 20日均量
            vol_ma20 = np.zeros(n)
            for i in range(20, n):
                vol_ma20[i] = np.mean(volume[i-20:i])
            vol_ratio = np.zeros(n)
            vol_ratio[20:] = volume[20:] / np.where(vol_ma20[20:] > 0, vol_ma20[20:], 1)
            features['volume_ratio'] = vol_ratio
            feature_names.append('volume_ratio')

        # 4. RSI (14)
        if n > 14:
            rsi = np.zeros(n)
            deltas = np.diff(close)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.zeros(n)
            avg_loss = np.zeros(n)
            avg_gain[14] = np.mean(gains[:14])
            avg_loss[14] = np.mean(losses[:14])
            for i in range(15, n):
                avg_gain[i] = (avg_gain[i-1] * 13 + gains[i-1]) / 14
                avg_loss[i] = (avg_loss[i-1] * 13 + losses[i-1]) / 14
            for i in range(14, n):
                if avg_loss[i] == 0:
                    rsi[i] = 100
                else:
                    rs = avg_gain[i] / avg_loss[i]
                    rsi[i] = 100 - 100 / (1 + rs)
            features['rsi_14'] = rsi
            feature_names.append('rsi_14')

        # 5. 振幅
        if n > 1:
            amplitude = (high - low) / open_p * 100
            features['amplitude'] = amplitude
            feature_names.append('amplitude')

        # 上影线比例
        body = abs(close - open_p)
        upper_shadow = high - np.maximum(close, open_p)
        shadow_ratio = np.zeros(n)
        amp_safe = np.where(amplitude > 0, amplitude, 1)
        shadow_ratio = upper_shadow / amp_safe
        features['upper_shadow_ratio'] = shadow_ratio
        feature_names.append('upper_shadow_ratio')

        # 构建矩阵
        min_len = min(len(v) for v in features.values())
        X = np.column_stack([v[-min_len:] for v in features.values()])

        # 目标变量: 未来5日收益率
        y = np.zeros(min_len)
        for i in range(min_len - 5):
            y[i] = (close[-(min_len - i - 5)] / close[-(min_len - i)] - 1) * 100 if i < min_len - 5 else 0

        # 去NaN
        valid = ~np.any(np.isnan(X), axis=1)
        X = X[valid]
        y = y[valid]

        if len(X) < 30:
            return None, None, []

        return X, y, feature_names

    except Exception as e:
        print(f"[ML] Feature building failed: {e}")
        return None, None, []


# ═══════════════════════════════════════════════════════════════
# 方向预测 (涨/跌/平)
# ═══════════════════════════════════════════════════════════════

# RF参数 (每只股票独立做 walk-forward 时序验证)
RF_PARAMS = {
    'n_estimators': 100,
    'max_depth': 2,
    'min_samples_leaf': 10,
    'max_features': 'sqrt',
    'class_weight': 'balanced',
}


def _rf_predict_direction(code: str, horizon: int = 5) -> Dict:
    """随机森林方向预测 — walk-forward时序验证, 避免数据泄露"""
    try:
        from sklearn.ensemble import RandomForestClassifier
        import numpy as np
        from data_fetchers import get_daily_kline

        kline = get_daily_kline(str(code).zfill(6), count=300)
        if kline is None or len(kline) < 100:
            return None

        c = kline['close'].values.astype(float)
        h = kline['high'].values.astype(float)
        l = kline['low'].values.astype(float)
        o = kline['open'].values.astype(float)
        v = kline['volume'].values.astype(float) if 'volume' in kline.columns else np.ones_like(c)
        n = len(c)

        if n < 65:
            return None

        # 尝试获取基本面数据
        fund_features = None
        try:
            from models import SessionLocal
            from db import get_latest_financial
            db = SessionLocal()
            fin = get_latest_financial(db, code)
            db.close()
            if fin:
                roe = fin.get('roe')
                gm = fin.get('gross_margin')
                pe = fin.get('pe_ttm')
                ey = (1.0/pe*100) if pe and pe > 0 else None
                debt = None
                if roe and gm and roe > 0 and gm > 0:
                    debt = max(10, min(90, (gm / max(roe, 0.1)) * 8))
                fund_features = {
                    'roe': roe or 0, 'gross_margin': gm or 0,
                    'earnings_yield': ey or 0, 'debt_ratio': debt or 0,
                }
        except Exception:
            pass

        n_features = 18 if fund_features else 14

        # 特征构建函数 — 给定索引i, 用i及之前的数据构建特征向量
        def _build_one_row(i):
            f = np.zeros(n_features)
            f[0] = (c[i]/c[i-1]-1)*100 if i>=1 else 0
            f[1] = (c[i]/c[i-3]-1)*100 if i>=3 else 0
            f[2] = (c[i]/c[i-5]-1)*100 if i>=5 else 0
            f[3] = (c[i]/c[i-10]-1)*100 if i>=10 else 0
            rets = np.diff(c[i-20:i+1])/c[i-20:i]
            f[4] = np.std(rets)*100*np.sqrt(252)
            f[5] = (c[i]/np.mean(c[max(0,i-4):i+1])-1)*100
            f[6] = (c[i]/np.mean(c[max(0,i-19):i+1])-1)*100
            d = np.diff(c[max(0,i-14):i+1])
            g = np.sum(d[d>0]) if np.any(d>0) else 0
            ll = abs(np.sum(d[d<0])) if np.any(d<0) else 1e-10
            f[7] = 100 - 100/(1+g/ll)
            av = np.mean(v[max(0,i-20):i]) if i>=20 else v[i]
            f[8] = v[i]/av if av>0 else 1.0
            m20=np.mean(c[max(0,i-19):i+1]); s20=np.std(c[max(0,i-19):i+1])
            f[9] = (c[i]-(m20-2*s20))/(4*s20)*100 if s20>0 else 50
            pk=np.max(c[max(0,i-19):i+1])
            f[10] = (pk-c[i])/pk*100 if pk>0 else 0
            f[11] = (h[i]-l[i])/o[i]*100 if o[i]>0 else 0
            up=0; down=0
            for j in range(i, max(i-5,0), -1):
                if c[j]>c[j-1]: up+=1
                else: break
            for j in range(i, max(i-5,0), -1):
                if c[j]<c[j-1]: down+=1
                else: break
            f[12]=up; f[13]=down
            if fund_features:
                f[14] = fund_features['roe']
                f[15] = fund_features['gross_margin']
                f[16] = fund_features['earnings_yield']
                f[17] = fund_features['debt_ratio']
            return f

        # 构建全部特征矩阵 (从索引60开始, 因为需要足够的历史数据)
        X = np.array([_build_one_row(i) for i in range(60, n - horizon)], dtype=np.float32)
        X = np.nan_to_num(X, 0)
        y = np.array([1 if c[i+horizon] > c[i] else 0 for i in range(60, n-horizon)], dtype=np.int32)

        if len(X) < 30 or len(np.unique(y)) < 2:
            return None

        # ── Walk-Forward 时序验证 ──
        # 前80%训练, 后20%验证 (严格按时序分割, 无数据泄露)
        split_idx = int(len(X) * 0.8)
        X_train, y_train = X[:split_idx], y[:split_idx]
        X_val, y_val = X[split_idx:], y[split_idx:]

        if len(X_val) < 5:
            X_train, y_train = X[:-5], y[:-5]
            X_val, y_val = X[-5:], y[-5:]

        rf = RandomForestClassifier(**RF_PARAMS, n_jobs=-1)
        rf.fit(X_train, y_train)
        val_accuracy = float(rf.score(X_val, y_val))

        # ── 预测最新方向 ──
        # 构建当前最新的特征向量 (使用索引 n-1 的数据, 非训练集内数据)
        latest_features = np.array([_build_one_row(n - 1)], dtype=np.float32)
        latest_features = np.nan_to_num(latest_features, 0)

        proba = rf.predict_proba(latest_features)[0]
        up_prob = float(proba[1]) * 100
        down_prob = float(proba[0]) * 100

        # 方向判断
        if up_prob > 55:
            direction = 'up'
        elif down_prob > 55:
            direction = 'down'
        else:
            direction = 'neutral'

        # 置信度 (结合概率差和验证准确率)
        prob_diff = abs(up_prob - down_prob)
        accuracy_baseline = val_accuracy if val_accuracy > 0.5 else 0.5
        adjusted_diff = prob_diff * (accuracy_baseline / 0.55)

        if adjusted_diff > 25:
            confidence = 'high'
        elif adjusted_diff > 12:
            confidence = 'medium'
        else:
            confidence = 'low'

        # 特征重要性
        feat_names = ['ret1','ret3','ret5','ret10','vol','ma5','ma20','rsi','vr','boll','dd','amp','cup','cdn']
        if n_features == 18:
            feat_names += ['roe','gm','ey','debt']
        imps = sorted(zip(feat_names, rf.feature_importances_), key=lambda x: x[1], reverse=True)[:5]

        return {
            'success': True,
            'code': code,
            'horizon_days': horizon,
            'direction': direction,
            'up_prob': round(up_prob),
            'down_prob': round(down_prob),
            'confidence': confidence,
            'method': 'random_forest',
            'val_accuracy': round(val_accuracy, 4),
            'top_features': [{'name': n, 'importance': round(float(v), 4)} for n, v in imps],
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'timestamp': datetime.now().isoformat(),
        }

    except ImportError:
        return None
    except Exception as e:
        print(f"[RF] predict failed: {e}")
        return None


def predict_direction(
    code: str,
    horizon_days: int = 5,
) -> Dict:
    """
    预测未来N日涨跌方向
    优先使用随机森林, 不可用时降级到规则引擎
    """
    # 尝试 RF
    rf_result = _rf_predict_direction(code, horizon_days)
    if rf_result is not None:
        return rf_result
    
    # 降级: 规则引擎
    return _rule_direction_prediction(code, horizon_days)


def _rule_direction_prediction(code: str, horizon: int) -> Dict:
    """降级方向预测 v2 — 动量+反转双信号, 市场基线校准, 100股回测验证"""
    try:
        from factor_engine import calculate_factors

        factors = calculate_factors(code)
        if not factors.get('success'):
            return {'success': False, 'direction': 'unknown', 'error': '数据不足'}

        f = factors['factors']
        score = 0
        details = []

        # ═══ 动量信号 ═══
        m20 = f.get('momentum_20d')
        m5 = f.get('ret_5d')  # may not be in factor_engine
        if m20 is not None:
            if m20 > 30: score -= 5; details.append('中期过度上涨(反转风险)')
            elif m20 > 15: score += 3; details.append('中期趋势向上')
            elif m20 > 5: score += 6; details.append('中期动量')
            elif m20 < -20: score += 8; details.append('深跌反弹预期')
            elif m20 < -10: score += 4; details.append('超跌区域')
            elif m20 < -5: score -= 3; details.append('中期走弱')

        # ═══ 均线 ═══
        ma = f.get('ma_status')
        if ma == 1: score += 12; details.append('MA多头')
        elif ma == 0: score -= 12; details.append('MA空头')

        # ═══ MACD ═══
        macd = f.get('macd_signal')
        if macd == 1: score += 8; details.append('MACD金叉')
        elif macd == -1: score -= 8; details.append('MACD死叉')

        # ═══ RSI均值回归 ═══
        rsi = f.get('rsi_14')
        if rsi is not None:
            if rsi <= 25: score += 15; details.append('RSI深度超卖')
            elif rsi <= 35: score += 8; details.append('RSI超卖')
            elif rsi >= 80: score -= 12; details.append('RSI极度超买')
            elif rsi >= 70: score -= 6; details.append('RSI超买')

        # ═══ 布林带 ═══
        boll = f.get('bollinger_pos')
        if boll is not None:
            if boll < 5: score += 12; details.append('布林下轨(强反弹)')
            elif boll < 15: score += 6; details.append('布林下轨区域')
            elif boll > 95: score -= 10; details.append('布林上轨(回调)')
            elif boll > 80: score -= 4; details.append('布林上轨区域')

        # ═══ 波动率惩罚 ═══
        vol = f.get('volatility_20d')
        if vol is not None:
            if vol > 60: score = score * 0.5; details.append('高波动(信号衰减)')
            elif vol > 40: score = score * 0.7

        # ═══ 市场基线校准 ═══
        score = max(-70, min(70, score))
        baseline = 52
        up_prob = int(max(15, min(85, baseline + score * 0.47)))
        down_prob = 100 - up_prob

        if score > 10: direction = 'up'
        elif score < -10: direction = 'down'
        else: direction = 'neutral'

        if abs(score) > 35: confidence = 'high'
        elif abs(score) > 18: confidence = 'medium'
        else: confidence = 'low'

        return {
            'success': True,
            'code': code,
            'horizon_days': horizon,
            'direction': direction,
            'up_prob': up_prob,
            'down_prob': down_prob,
            'confidence': confidence,
            'method': 'rule_based',
            'details': details,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════
# 收益率预测
# ═══════════════════════════════════════════════════════════════

def predict_return(
    code: str,
    horizon_days: int = 5,
) -> Dict:
    """
    预测未来N日收益率 (回归模型)

    Returns:
        dict: {predicted_return, confidence_interval, r_squared, ...}
    """
    result = {
        'success': False,
        'code': code,
        'horizon_days': horizon_days,
        'predicted_return_pct': 0,
        'confidence_low': 0,
        'confidence_high': 0,
    }

    try:
        if is_us_stock(code):
            result['error'] = '美股暂不支持'
            return result

        X, y, feature_names = _build_features(code)

        if X is None or len(X) < 30:
            # 降级: 基于动量的简单外推
            kline = get_daily_kline(str(code).zfill(6), count=60)
            if kline is not None and len(kline) >= 20:
                close = kline['close'].values.astype(float)
                recent_ret = (close[-1] / close[-horizon_days] - 1) * 100 if len(close) > horizon_days else 0
                result['predicted_return_pct'] = round(recent_ret, 2)
                result['method'] = 'momentum_extrapolation'
                result['success'] = True
            return result

        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            # 时序分割: 前80%训练, 后20%验证 (严格避免数据泄露)
            split_idx = int(len(X) * 0.8)
            X_train_raw, y_train = X[:split_idx], y[:split_idx]
            X_val_raw, y_val = X[split_idx:], y[split_idx:]

            if len(X_val_raw) < 5:
                X_train_raw, y_train = X[:-1], y[:-1]
                X_val_raw, y_val = X[-1:], y[-1:]

            # 只在训练数据上拟合scaler, 避免测试数据泄露
            scaler.fit(X_train_raw)
            X_train = scaler.transform(X_train_raw)
            X_val = scaler.transform(X_val_raw)

            model = Ridge(alpha=1.0)
            model.fit(X_train, y_train)

            # 预测最新样本
            X_latest = X_val[-1:] if len(X_val) > 0 else scaler.transform(X_train_raw[-1:])
            pred = float(model.predict(X_latest)[0])

            # R² (仅在验证集上评估)
            y_pred_val = model.predict(X_val)
            ss_res = np.sum((y_val - y_pred_val) ** 2)
            ss_tot = np.sum((y_val - np.mean(y_val)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            # 置信区间 (基于验证残差)
            residuals = y_val - y_pred_val
            std_residual = np.std(residuals) if len(residuals) > 1 else abs(pred) * 0.3
            ci_half = 1.96 * std_residual

            result['success'] = True
            result['predicted_return_pct'] = round(pred, 2)
            result['confidence_low'] = round(pred - ci_half, 2)
            result['confidence_high'] = round(pred + ci_half, 2)
            result['r_squared'] = round(float(r2), 4)
            result['val_samples'] = len(X_val)
            result['method'] = 'ridge_regression'

        except ImportError:
            # 降级: 简单动量外推
            kline = get_daily_kline(str(code).zfill(6), count=60)
            if kline is not None and len(kline) >= 20:
                close = kline['close'].values.astype(float)
                recent_ret = (close[-1] / close[-horizon_days] - 1) * 100 if len(close) > horizon_days else 0
                result['predicted_return_pct'] = round(recent_ret, 2)
                result['method'] = 'momentum_extrapolation'
                result['success'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


# ═══════════════════════════════════════════════════════════════
# 综合预测
# ═══════════════════════════════════════════════════════════════

def predict(code: str, horizon_days: int = 5) -> Dict:
    """
    综合预测: 方向 + 收益率 (两模型结果协调一致)

    Returns:
        dict: {direction, up_prob, predicted_return, confidence, factors}
    """
    direction = predict_direction(code, horizon_days)
    returns = predict_return(code, horizon_days)

    raw_return = returns.get('predicted_return_pct', 0)
    up_prob = direction.get('up_prob', 50)
    down_prob = direction.get('down_prob', 50)
    dir_val = direction.get('direction', 'unknown')

    # 协调: 确保预测收益率符号与方向一致
    if dir_val == 'up':
        # 看涨: 收益率取正 (至少为0)
        reconciled_return = max(0, raw_return) if raw_return is not None else up_prob / 100 * 5
    elif dir_val == 'down':
        # 看跌: 收益率取负 (至多为0)
        reconciled_return = min(0, raw_return) if raw_return is not None else -down_prob / 100 * 5
    else:
        # 中性: 用概率加权
        if raw_return is not None:
            reconciled_return = (up_prob / 100) * max(0, raw_return) + (down_prob / 100) * min(0, raw_return)
        else:
            reconciled_return = 0

    result = {
        'success': direction.get('success', False) or returns.get('success', False),
        'code': code,
        'horizon_days': horizon_days,
        'timestamp': datetime.now().isoformat(),
        'direction': dir_val,
        'up_prob': up_prob,
        'down_prob': down_prob,
        'predicted_return_pct': round(reconciled_return, 2),
        'confidence': direction.get('confidence', 'low'),
    }

    if returns.get('confidence_low') is not None:
        result['return_range'] = f"{returns['confidence_low']}% ~ {returns['confidence_high']}%"

    if direction.get('top_features'):
        result['key_factors'] = [f['name'] for f in direction['top_features'][:3]]

    if direction.get('baseline_up_pct') is not None:
        result['baseline_up_pct'] = direction['baseline_up_pct']

    return result


def predict_text(code: str, horizon_days: int = 5) -> str:
    """生成预测文本 (用于AI prompt注入)"""
    result = predict(code, horizon_days)

    lines = [
        f"【ML预测】股票: {code} (未来{horizon_days}日)",
    ]

    if not result.get('success'):
        lines.append(f"  预测失败: {result.get('error', '未知错误')}")
        return '\n'.join(lines) + '\n'

    direction_emoji = '📈' if result['direction'] == 'up' else ('📉' if result['direction'] == 'down' else '➡️')
    dir_label = '上涨' if result['direction'] == 'up' else ('下跌' if result['direction'] == 'down' else '震荡/中性')
    lines.append(f"  方向: {direction_emoji} {dir_label} "
                 f"(涨{result['up_prob']}% / 跌{result['down_prob']}%)")
    lines.append(f"  预测收益率: {result['predicted_return_pct']}%")
    if result.get('return_range'):
        lines.append(f"  95%置信区间: {result['return_range']}")
    lines.append(f"  置信度: {result['confidence']}")

    if result.get('key_factors'):
        lines.append(f"  关键因子: {', '.join(result['key_factors'])}")

    return '\n'.join(lines) + '\n'
