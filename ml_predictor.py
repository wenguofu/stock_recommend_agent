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

def predict_direction(
    code: str,
    horizon_days: int = 5,
) -> Dict:
    """
    预测未来N日涨跌方向

    方法: 多因子线性评分 + 历史胜率加权

    Returns:
        dict: {direction, up_prob, down_prob, confidence, features_used}
    """
    result = {
        'success': False,
        'code': code,
        'horizon_days': horizon_days,
        'timestamp': datetime.now().isoformat(),
        'direction': 'unknown',
        'up_prob': 0,
        'down_prob': 0,
        'confidence': 'low',
    }

    try:
        if is_us_stock(code):
            result['error'] = '美股暂不支持'
            return result

        X, y, feature_names = _build_features(code)

        if X is None or len(X) < 30:
            # 降级: 使用简单规则
            return _fallback_direction_prediction(code, horizon_days)

        # 二分类: 上涨(return>0) vs 下跌(return<=0)
        y_binary = (y > 0).astype(int)

        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # 留出最近一期做预测
            X_train = X_scaled[:-1]
            y_train = y_binary[:-1]

            if len(np.unique(y_train)) < 2:
                up_prob = 0.55 if np.mean(y_train) > 0.5 else 0.45
                result['up_prob'] = round(up_prob * 100)
                result['down_prob'] = 100 - result['up_prob']
                result['direction'] = 'up' if up_prob > 0.5 else 'down'
                result['confidence'] = 'low'
                result['success'] = True
                return result

            model = LogisticRegression(max_iter=1000, C=1.0, class_weight='balanced')
            model.fit(X_train, y_train)

            # 基线: 训练集中上涨的比例
            baseline_up = float(np.mean(y_train))
            result['baseline_up_pct'] = round(baseline_up * 100, 1)

            # 预测
            X_latest = X_scaled[-1:]

            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X_latest)[0]
                if len(proba) == 2:
                    down_prob = float(proba[0])
                    up_prob = float(proba[1])
                else:
                    up_prob = 0.5
                    down_prob = 0.5
            else:
                pred = model.predict(X_latest)[0]
                up_prob = 0.7 if pred == 1 else 0.3
                down_prob = 1 - up_prob

            # 计算训练集准确率
            train_acc = float(np.mean(model.predict(X_train) == y_train))

            # 特征重要性
            importance = {}
            for i, name in enumerate(feature_names):
                importance[name] = round(float(abs(model.coef_[0][i])), 4)

            top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]

            result['up_prob'] = round(up_prob * 100)
            result['down_prob'] = round(down_prob * 100)
            result['direction'] = 'up' if up_prob > down_prob else 'down'
            result['train_accuracy'] = round(train_acc * 100, 1)
            result['top_features'] = [{'name': n, 'importance': v} for n, v in top_features]

            # 置信度
            prob_diff = abs(up_prob - down_prob)
            if prob_diff > 0.3 and train_acc > 0.6:
                result['confidence'] = 'high'
            elif prob_diff > 0.15:
                result['confidence'] = 'medium'
            else:
                result['confidence'] = 'low'

            result['success'] = True

        except ImportError:
            # 无sklearn, 降级到规则
            return _fallback_direction_prediction(code, horizon_days)

    except Exception as e:
        result['error'] = str(e)

    return result


def _fallback_direction_prediction(code: str, horizon: int) -> Dict:
    """降级方向预测 (无sklearn时) — 基于技术指标加权双面对称评分"""
    try:
        from factor_engine import calculate_factors

        factors = calculate_factors(code)
        if not factors.get('success'):
            return {'success': False, 'direction': 'unknown', 'error': '数据不足'}

        f = factors['factors']

        # 对称双向评分: 正=看涨, 负=看跌
        score = 0
        details = []

        # 动量 (对称)
        m20 = f.get('momentum_20d')
        if m20 is not None:
            if m20 > 10:
                score += 15; details.append('强短期动量向上')
            elif m20 > 3:
                score += 8; details.append('短期动量偏上')
            elif m20 < -10:
                score -= 15; details.append('强短期动量向下')
            elif m20 < -3:
                score -= 8; details.append('短期动量偏下')
            # -3~3: 中性, 不加分

        # 均线
        ma = f.get('ma_status')
        if ma == 1:
            score += 20; details.append('均线多头排列')
        elif ma == 0:
            score -= 20; details.append('均线空头排列')
        # -1(混乱): 不加分

        # MACD
        macd = f.get('macd_signal')
        if macd == 1:
            score += 10; details.append('MACD金叉')
        elif macd == -1:
            score -= 10; details.append('MACD死叉')

        # RSI
        rsi = f.get('rsi_14')
        if rsi is not None:
            if rsi <= 30:
                score += 15; details.append('RSI超卖(反弹机会)')
            elif rsi >= 80:
                score -= 15; details.append('RSI极度超买(回调风险)')
            elif rsi >= 70:
                score -= 8; details.append('RSI超买')

        # MA偏离
        ma_dist = f.get('ma_distance')
        if ma_dist is not None:
            if ma_dist > 20:
                score -= 10; details.append('价格过度高于均线')
            elif ma_dist < -15:
                score += 10; details.append('价格深度低于均线')

        # 布林带
        boll = f.get('bollinger_pos')
        if boll is not None:
            if boll > 90:
                score -= 8; details.append('触及布林上轨')
            elif boll < 10:
                score += 8; details.append('触及布林下轨')

        # 波动率 (高波动→降低置信度)
        vol = f.get('volatility_20d')
        high_volatility = vol is not None and vol > 50

        score = max(-60, min(60, score))

        # 映射到概率: score=0→50%, score=±60→80%/20%
        up_prob = int(50 + score * 0.5)
        down_prob = 100 - up_prob

        # 方向判断(加入中性区间)
        if score > 12:
            direction = 'up'
        elif score < -12:
            direction = 'down'
        else:
            direction = 'neutral'

        # 置信度
        if abs(score) > 30 and not high_volatility:
            confidence = 'high'
        elif abs(score) > 15:
            confidence = 'medium'
        else:
            confidence = 'low'

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
            X_scaled = scaler.fit_transform(X)

            X_train = X_scaled[:-1]
            y_train = y[:-1]

            model = Ridge(alpha=1.0)
            model.fit(X_train, y_train)

            X_latest = X_scaled[-1:]
            pred = float(model.predict(X_latest)[0])

            # R²
            y_pred_train = model.predict(X_train)
            ss_res = np.sum((y_train - y_pred_train) ** 2)
            ss_tot = np.sum((y_train - np.mean(y_train)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            # 置信区间 (基于训练残差)
            residuals = y_train - y_pred_train
            std_residual = np.std(residuals)
            ci_half = 1.96 * std_residual  # 95% CI

            result['success'] = True
            result['predicted_return_pct'] = round(pred, 2)
            result['confidence_low'] = round(pred - ci_half, 2)
            result['confidence_high'] = round(pred + ci_half, 2)
            result['r_squared'] = round(float(r2), 4)
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

    direction_emoji = '📈' if result['direction'] == 'up' else '📉'
    lines.append(f"  方向: {direction_emoji} {'上涨' if result['direction'] == 'up' else '下跌'} "
                 f"(涨{result['up_prob']}% / 跌{result['down_prob']}%)")
    lines.append(f"  预测收益率: {result['predicted_return_pct']}%")
    if result.get('return_range'):
        lines.append(f"  95%置信区间: {result['return_range']}")
    lines.append(f"  置信度: {result['confidence']}")

    if result.get('key_factors'):
        lines.append(f"  关键因子: {', '.join(result['key_factors'])}")

    return '\n'.join(lines) + '\n'
