#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""信号融合引擎 — 多源信号加权融合

融合来源及默认权重:
  - Agent debate (debate):    25% — AI多专家辩论评分
  - Factor score (factor):    20% — 8因子量化评分
  - Money flow (money):       15% — 资金流信号
  - Technical indicators (tech): 15% — 技术指标信号
  - Sector heat (sector):     10% — 行业热度信号
  - Risk management (risk):   15% — 风险管理信号 (VaR/CVaR/回撤/夏普/凯利)

输出: combined_score, confidence, recommendation, signals breakdown
"""

import traceback
import time
from datetime import datetime

from data_fetchers import get_sector_info, get_money_flow_history, get_realtime_data
from utils import is_us_stock


# 默认融合权重
DEFAULT_FUSION_WEIGHTS = {
    'debate': 0.25,
    'factor': 0.20,
    'money': 0.15,
    'tech': 0.15,
    'sector': 0.10,
    'risk': 0.15,
}


def _get_debate_signal(db, code: str):
    """从数据库获取最近一次辩论任务的结果信号"""
    try:
        if db is None:
            return {'score': 50, 'confidence': 'low', 'source': None}
        from models import DebateJob

        job = db.query(DebateJob).filter(
            DebateJob.code == code,
            DebateJob.status == 'completed'
        ).order_by(DebateJob.updated_at.desc()).first()

        if not job or not job.report_md:
            return {'score': 50, 'confidence': 'low', 'source': None}

        # 从报告中简单提取情绪
        report = job.report_md.lower()
        bullish_keywords = ['买入', '强烈推荐', '看多', '上涨', '利好', '金叉', '买入信号']
        bearish_keywords = ['卖出', '回避', '看空', '下跌', '利空', '死叉', '卖出信号', '风险']

        bull_count = sum(1 for kw in bullish_keywords if kw in report)
        bear_count = sum(1 for kw in bearish_keywords if kw in report)

        if bull_count > bear_count + 2:
            score = 80
            confidence = 'high'
        elif bull_count > bear_count:
            score = 65
            confidence = 'medium'
        elif bear_count > bull_count + 2:
            score = 20
            confidence = 'high'
        elif bear_count > bull_count:
            score = 35
            confidence = 'medium'
        else:
            score = 50
            confidence = 'low'

        return {
            'score': score,
            'confidence': confidence,
            'source': job.job_id,
            'bull_matches': bull_count,
            'bear_matches': bear_count,
        }
    except Exception as e:
        print(f"[Fusion] debate signal extraction failed: {e}")
        return {'score': 50, 'confidence': 'low', 'source': None}


def _get_factor_signal(code: str):
    """获取因子评分信号"""
    try:
        from factor_engine import get_stock_rating
        rating = get_stock_rating(code)
        if rating.get('success') and rating.get('score'):
            score = rating['score'].get('total_score', 50)
            return {
                'score': score,
                'rating': rating.get('rating', 'C'),
                'source': 'factor_engine',
            }
        return {'score': 50, 'source': 'factor_engine'}
    except Exception as e:
        print(f"[Fusion] factor signal failed: {e}")
        return {'score': 50, 'source': 'factor_engine'}


def _get_money_flow_signal(code: str):
    """获取资金流信号"""
    try:
        if is_us_stock(code):
            return {'score': 50, 'source': 'money_flow'}

        flow = get_money_flow_history(code, days=5)
        if not flow or len(flow) == 0:
            return {'score': 50, 'source': 'money_flow'}

        # 近5日主力净流入趋势
        main_inflows = []
        for item in flow[:5]:
            main_in = item.get('main_net_inflow')
            if main_in is not None:
                try:
                    main_inflows.append(float(main_in))
                except (ValueError, TypeError):
                    pass

        if len(main_inflows) < 3:
            return {'score': 50, 'source': 'money_flow'}

        recent_avg = sum(main_inflows[:2]) / min(2, len(main_inflows[:2]))
        earlier_avg = sum(main_inflows[-3:]) / min(3, len(main_inflows[-3:]))

        # 趋势判断
        if recent_avg > 0 and recent_avg > earlier_avg:
            score = 75  # 主力增加净流入
        elif recent_avg > 0:
            score = 60  # 主力净流入但减速
        elif recent_avg < 0 and recent_avg > earlier_avg:
            score = 45  # 净流出但减轻
        elif recent_avg < 0:
            score = 25  # 主力持续流出
        else:
            score = 50

        return {
            'score': score,
            'source': 'money_flow',
            'recent_avg': round(recent_avg, 2),
            'earlier_avg': round(earlier_avg, 2),
        }
    except Exception as e:
        print(f"[Fusion] money flow signal failed: {e}")
        return {'score': 50, 'source': 'money_flow'}


def _get_tech_signal(code: str):
    """获取技术指标融合信号"""
    try:
        if is_us_stock(code):
            return {'score': 50, 'source': 'tech'}

        from factor_engine import calculate_factors
        factor_result = calculate_factors(code)
        if not factor_result.get('success'):
            return {'score': 50, 'source': 'tech'}

        f = factor_result['factors']

        # 从因子中提取纯技术信号
        tech_score = 50.0
        signals = 0

        # MACD
        macd = f.get('macd_signal', 0)
        if macd == 1:
            tech_score += 15
        elif macd == -1:
            tech_score -= 15
        signals += 1

        # MA 排列
        ma = f.get('ma_status', -1)
        if ma == 1:
            tech_score += 20
        elif ma == 0:
            tech_score -= 20
        signals += 1

        # RSI
        rsi = f.get('rsi_14', 50)
        if 40 <= rsi <= 60:
            tech_score += 10
        elif 30 <= rsi < 40:
            tech_score += 5   # 超卖区潜在反弹
        elif 60 < rsi <= 70:
            tech_score -= 5
        elif rsi > 70:
            tech_score -= 10
        signals += 1

        # 量比
        vol = f.get('volume_ratio', 1.0)
        if 1.2 <= vol <= 2.0:
            tech_score += 10
        elif vol < 0.5:
            tech_score -= 10
        signals += 1

        tech_score = max(0, min(100, tech_score))

        return {
            'score': round(tech_score, 2),
            'source': 'tech',
            'details': {
                'macd': macd,
                'ma_status': ma,
                'rsi': rsi,
                'volume_ratio': vol,
            }
        }
    except Exception as e:
        print(f"[Fusion] tech signal failed: {e}")
        return {'score': 50, 'source': 'tech'}


def _get_sector_signal(code: str):
    """获取行业热度信号"""
    try:
        if is_us_stock(code):
            return {'score': 50, 'source': 'sector'}

        sector_info = get_sector_info(code)
        if not sector_info:
            return {'score': 50, 'source': 'sector'}

        # 板块涨跌幅
        sector_pct = sector_info.get('sector_change_pct') or sector_info.get('board_change_pct')
        if sector_pct is not None:
            try:
                sector_pct = float(sector_pct)
            except (ValueError, TypeError):
                sector_pct = 0
        else:
            sector_pct = 0

        # 个股相对板块的相对强度
        realtime = get_realtime_data(code)
        stock_pct = 0
        if realtime and realtime.get('change_percent') is not None:
            stock_pct = realtime['change_percent']

        relative_strength = stock_pct - sector_pct

        # 综合评分
        base = 50
        if sector_pct > 2:
            base += 15
        elif sector_pct > 0:
            base += 8
        elif sector_pct < -2:
            base -= 15
        elif sector_pct < 0:
            base -= 8

        # 个股相对板块的强度
        if relative_strength > 2:
            base += 15
        elif relative_strength > 0:
            base += 8
        elif relative_strength < -2:
            base -= 15
        elif relative_strength < 0:
            base -= 8

        score = max(0, min(100, base))

        return {
            'score': score,
            'source': 'sector',
            'sector_pct': round(sector_pct, 2),
            'stock_pct': round(stock_pct, 2),
            'relative_strength': round(relative_strength, 2),
        }
    except Exception as e:
        print(f"[Fusion] sector signal failed: {e}")
        return {'score': 50, 'source': 'sector'}


def _get_risk_signal(code: str):
    """获取风险管理信号 — 从风险指标转为评分"""
    try:
        if is_us_stock(code):
            return {'score': 50, 'source': 'risk'}

        from risk_management import risk_report
        report = risk_report(code)

        if report.get('risk_grade') in ('data_insufficient', 'data_error'):
            return {'score': 50, 'source': 'risk', 'available': False}

        score = 50.0  # 中性起始

        # VaR 维度: VaR越低越安全
        var_pct = report.get('var_95', {}).get('var_pct')
        if var_pct and var_pct is not None:
            if var_pct <= 2:
                score += 10
            elif var_pct <= 4:
                score += 5
            elif var_pct >= 8:
                score -= 10
            elif var_pct >= 6:
                score -= 5

        # 回撤维度
        max_dd = report.get('max_drawdown', {}).get('max_drawdown_pct', 0)
        if max_dd <= 15:
            score += 10
        elif max_dd <= 25:
            score += 5
        elif max_dd >= 40:
            score -= 10
        elif max_dd >= 30:
            score -= 5

        # 夏普维度
        sharpe = report.get('sharpe', {}).get('sharpe_ratio')
        if sharpe is not None:
            if sharpe >= 1.5:
                score += 10
            elif sharpe >= 0.8:
                score += 5
            elif sharpe <= -0.5:
                score -= 10

        # 波动率维度
        vol = report.get('volatility', {}).get('annual_pct', 0)
        if vol <= 25:
            score += 5
        elif vol >= 60:
            score -= 10
        elif vol >= 45:
            score -= 5

        # 风险等级
        risk_grade = report.get('risk_grade', '中等风险')
        if risk_grade == '低风险':
            score += 10
        elif risk_grade == '极高风险':
            score -= 10
        elif risk_grade == '高风险':
            score -= 5

        score = max(0, min(100, score))

        return {
            'score': round(score, 2),
            'source': 'risk',
            'risk_grade': risk_grade,
            'var_95_pct': var_pct,
            'sharpe': sharpe,
            'max_dd_pct': max_dd,
            'kelly_pct': report.get('kelly_position', {}).get('fractional_pct'),
        }
    except Exception as e:
        print(f"[Fusion] risk signal failed: {e}")
        return {'score': 50, 'source': 'risk', 'available': False}


def fuse_signals(code: str, db=None, weights: dict = None) -> dict:
    """多源信号融合

    Args:
        code: 股票代码
        db: SQLAlchemy 数据库会话 (用于获取辩论结果)
        weights: 自定义权重, 不传则使用默认权重

    Returns:
        dict: {
            success, code, timestamp,
            combined_score, confidence, recommendation,
            signals (breakdown),
            weights
        }
    """
    if weights is None:
        weights = DEFAULT_FUSION_WEIGHTS.copy()

    result = {
        'success': False,
        'code': code,
        'timestamp': datetime.now().isoformat(),
        'combined_score': 0,
        'confidence': 'low',
        'recommendation': '',
        'signals': {},
        'weights': weights,
        'error': None,
    }

    try:
        # 并行获取所有信号
        debate_signal = _get_debate_signal(db, code)
        time.sleep(0.05)

        factor_signal = _get_factor_signal(code)
        time.sleep(0.05)

        money_signal = _get_money_flow_signal(code)
        time.sleep(0.05)

        tech_signal = _get_tech_signal(code)
        time.sleep(0.05)

        sector_signal = _get_sector_signal(code)
        time.sleep(0.05)

        risk_signal = _get_risk_signal(code)

        # 存储各信号
        signals = {
            'debate': debate_signal,
            'factor': factor_signal,
            'money': money_signal,
            'tech': tech_signal,
            'sector': sector_signal,
            'risk': risk_signal,
        }

        # 加权融合
        combined_score = 0.0
        available_weight = 0.0

        for key, signal_data in signals.items():
            _score = signal_data.get('score', 50)
            _weight = weights.get(key, 0)

            # 如果某信号不可用(如美股无资金流), 权重重分配
            if signal_data.get('confidence') == 'none':
                continue

            combined_score += _score * _weight
            available_weight += _weight

        # 归一化
        if available_weight > 0:
            combined_score = combined_score / available_weight

        combined_score = round(combined_score, 2)

        # 置信度评估 (修复: 平均分≈50且低方差 不应产生高置信度)
        signal_scores = [s['score'] for s in signals.values()]
        score_std = 0
        avg_score = 0
        if len(signal_scores) > 1:
            import numpy as np
            score_std = float(np.std(signal_scores))
            avg_score = float(np.mean(signal_scores))

        # 高置信度 = 偏离中性 + 信号一致, 低置信度 = 均值附近 (无论多一致)
        if avg_score >= 65 and score_std < 10:
            confidence = 'high'
        elif avg_score >= 55 and score_std < 15:
            confidence = 'medium'
        elif avg_score <= 35 and score_std < 10:
            confidence = 'high'
        elif avg_score <= 45 and score_std < 15:
            confidence = 'medium'
        else:
            confidence = 'low'       # 分歧较大

        # 推荐
        if combined_score >= 75:
            recommendation = '强烈买入'
        elif combined_score >= 65:
            recommendation = '买入'
        elif combined_score >= 50:
            recommendation = '中性/持有'
        elif combined_score >= 35:
            recommendation = '减仓'
        else:
            recommendation = '卖出'

        result['success'] = True
        result['combined_score'] = combined_score
        result['confidence'] = confidence
        result['recommendation'] = recommendation
        result['signals'] = signals

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def fuse_signals_text(code: str, db=None) -> str:
    """生成信号融合文本 (用于AI prompt注入)

    Args:
        code: 股票代码
        db: 数据库会话

    Returns:
        str: 格式化文本
    """
    result = fuse_signals(code, db)

    if not result.get('success'):
        return f"【信号融合】股票: {code}\n  数据获取失败: {result.get('error', '未知')}\n"

    signals = result['signals']

    lines = [
        f"【信号融合】股票: {code}",
        f"  融合得分: {result['combined_score']:.1f}/100  置信度: {result['confidence']}",
        f"  综合建议: {result['recommendation']}",
        "",
        "  各信号源明细:",
    ]

    source_labels = {
        'debate': 'AI辩论',
        'factor': '量化因子',
        'money': '资金流',
        'tech': '技术指标',
        'sector': '行业热度',
        'risk': '风险管理',
    }

    for key in ['debate', 'factor', 'money', 'tech', 'sector', 'risk']:
        sig = signals.get(key, {})
        label = source_labels.get(key, key)
        score = sig.get('score', 50)
        weight = result['weights'].get(key, 0)
        conf = sig.get('confidence', '')
        conf_str = f" 置信={conf}" if conf else ""
        lines.append(f"    {label}: {score:.1f}分 (权重 {weight:.0%}){conf_str}")

    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '300433'
    print(fuse_signals_text(code))
