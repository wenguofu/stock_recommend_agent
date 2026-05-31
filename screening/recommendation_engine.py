#!/usr/bin/env python3
"""推荐引擎 - 整合四层筛选"""
import sys
import os
from typing import Dict, List

def get_recommendations(recommendation_type: str = 'short', top_n: int = 5) -> Dict:
    """
    获取精选推荐 - 端到端四层筛选

    Args:
        recommendation_type: 'short' 或 'mid'
        top_n: 返回前N只推荐股票

    Returns:
        {
            'recommendations': [...],
            'pipeline_status': {
                'layer1': {...},
                'layer2': {...},
                'layer3': {...}
            },
            'recommendation_type': str
        }
    """
    from screening.layer1_tech_screen import screen_layer1
    from screening.layer2_signal_score import score_layer2
    from screening.layer3_backtest_verify import verify_layer3

    # Layer 1: 技术面宽筛
    layer1_result = screen_layer1(recommendation_type)
    layer1_status = {
        'candidates_count': layer1_result.get('count', 0),
        'market_safe': layer1_result.get('market_check', {}).get('reason') == 'safe',
        'filters_applied': layer1_result.get('filter_applied', [])
    }

    # 如果Layer 1没有候选股，直接返回空
    if not layer1_result.get('candidates'):
        return {
            'recommendations': [],
            'pipeline_status': {'layer1': layer1_status, 'layer2': None, 'layer3': None},
            'recommendation_type': recommendation_type,
            'warning': layer1_result.get('warning', 'No candidates from Layer 1')
        }

    # Layer 2: 多信号评分
    layer2_result = score_layer2(layer1_result)
    layer2_status = {
        'scored_count': layer2_result.get('total_candidates', 0),
        'top_count': len(layer2_result.get('top_candidates', []))
    }

    # 如果Layer 2没有候选股，直接返回
    if not layer2_result.get('top_candidates'):
        return {
            'recommendations': [],
            'pipeline_status': {'layer1': layer1_status, 'layer2': layer2_status, 'layer3': None},
            'recommendation_type': recommendation_type
        }

    # Layer 3: 历史胜率验证
    layer3_result = verify_layer3(layer2_result)
    layer3_status = {
        'verified_count': layer3_result.get('total_verified', 0),
        'recommended_count': len(layer3_result.get('top_recommendations', []))
    }

    # 获取Top N推荐
    top_recommendations = layer3_result.get('top_recommendations', [])[:top_n]

    return {
        'recommendations': top_recommendations,
        'pipeline_status': {
            'layer1': layer1_status,
            'layer2': layer2_status,
            'layer3': layer3_status
        },
        'recommendation_type': recommendation_type,
        'generated_at': __import__('datetime').datetime.now().isoformat()
    }