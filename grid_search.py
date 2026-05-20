#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""网格搜索 — 策略参数优化器

基于回测引擎, 在参数空间中进行网格搜索,
找到夏普比率/收益率最优的参数组合。

支持策略: ma_cross, rsi_reversal, macd_cross, bollinger_break
"""

import traceback
from datetime import datetime
from itertools import product
from typing import Dict, Any, List, Optional

import numpy as np

from data_fetchers import get_daily_kline


def _generate_param_grid(strategy_type: str, param_grid: dict = None) -> List[dict]:
    """根据策略类型生成参数网格

    Args:
        strategy_type: 策略类型
        param_grid: 用户自定义参数网格 (可选)

    Returns:
        list[dict]: 参数组合列表
    """
    from backtest_engine import STRATEGY_PRESETS

    if strategy_type not in STRATEGY_PRESETS:
        return []

    preset = STRATEGY_PRESETS[strategy_type]
    preset_params = preset.get('params', [])

    # 构建搜索网格
    grid = {}

    if param_grid:
        # 使用用户自定义网格
        for p in preset_params:
            key = p['key']
            if key in param_grid:
                grid[key] = param_grid[key]
            else:
                # 使用默认值
                grid[key] = [p['default']]
    else:
        # 自动生成合理网格
        for p in preset_params:
            key = p['key']
            ptype = p.get('type', 'int')
            default = p['default']
            min_val = p.get('min', default)
            max_val = p.get('max', default)

            if ptype == 'int':
                # 生成3个值: min, default, max
                vals = sorted(set([int(min_val), int(default), int(max_val)]))
                # 如果范围较大, 增加中间点
                if max_val - min_val > 10:
                    mid1 = int((min_val + default) // 2)
                    mid2 = int((default + max_val) // 2)
                    vals = sorted(set(vals + [mid1, mid2]))
                grid[key] = [v for v in vals if min_val <= v <= max_val]
            elif ptype == 'float':
                vals = set()
                vals.add(float(min_val))
                vals.add(float(default))
                vals.add(float(max_val))
                if max_val - min_val > 1.0:
                    mid = round((min_val + max_val) / 2, 1)
                    vals.add(mid)
                grid[key] = sorted(vals)
            else:
                grid[key] = [default]

    # 生成笛卡尔积
    keys = list(grid.keys())
    combinations = list(product(*[grid[k] for k in keys]))

    param_list = []
    for combo in combinations:
        param_dict = {}
        for i, key in enumerate(keys):
            param_dict[key] = combo[i]
        param_list.append(param_dict)

    return param_list


def _generate_default_grid(strategy_type: str) -> dict:
    """生成默认搜索参数"""
    from backtest_engine import STRATEGY_PRESETS

    preset = STRATEGY_PRESETS.get(strategy_type, {})
    default_params = {}
    for p in preset.get('params', []):
        default_params[p['key']] = p['default']
    return default_params


def grid_search(code: str, strategy_type: str,
                param_grid: dict = None,
                start_date: str = None, end_date: str = None,
                initial_capital: float = 100000,
                max_data_days: int = 720,
                metric: str = 'sharpe_ratio',
                top_n: int = 5) -> dict:
    """策略参数网格搜索优化

    Args:
        code: 股票代码
        strategy_type: 策略类型 (ma_cross | rsi_reversal | macd_cross | bollinger_break)
        param_grid: 自定义参数网格, 如 {'fast_period': [3,5,10], 'slow_period': [15,20,30]}
                    不传则自动生成
        start_date: 回测起始日期 YYYY-MM-DD (可选)
        end_date: 回测截止日期 YYYY-MM-DD (可选)
        initial_capital: 初始资金 (默认100000)
        max_data_days: 最大获取天数 (默认720)
        metric: 排序指标 (sharpe_ratio | total_return | win_rate | max_drawdown)
        top_n: 返回前N个最佳结果 (默认5)

    Returns:
        dict: {
            success, best_params, best_metrics, all_results (排名表), meta
        }
    """
    from backtest_engine import run_backtest, STRATEGY_PRESETS

    result = {
        'success': False,
        'code': code,
        'strategy_type': strategy_type,
        'timestamp': datetime.now().isoformat(),
        'best_params': {},
        'best_metrics': {},
        'all_results': [],
        'meta': {
            'total_combinations': 0,
            'completed': 0,
            'failed': 0,
            'metric': metric,
            'strategy_name': STRATEGY_PRESETS.get(strategy_type, {}).get('name', strategy_type),
        },
        'error': None,
    }

    try:
        if strategy_type not in STRATEGY_PRESETS:
            result['error'] = f'未知策略类型: {strategy_type}，支持的: {list(STRATEGY_PRESETS.keys())}'
            return result

        # 1. 生成参数网格
        grid = _generate_param_grid(strategy_type, param_grid)
        if not grid:
            result['error'] = '参数网格为空'
            return result

        result['meta']['total_combinations'] = len(grid)

        # 2. 预先获取数据 (避免重复请求)
        print(f"[GridSearch] 获取 {code} 历史K线 ({max_data_days}天)...")
        df = get_daily_kline(code, count=max_data_days)
        if df is None or df.empty:
            result['error'] = f'无法获取 {code} 的历史K线数据'
            return result

        if start_date:
            df = df[df['date'] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df['date'] <= pd.Timestamp(end_date)]
        if len(df) < 30:
            result['error'] = f'数据不足30个交易日 (当前{len(df)}天)'
            return result

        # 3. 遍历参数组合, 执行回测
        all_results = []
        import pandas as pd

        for idx, params in enumerate(grid):
            try:
                bt_result = run_backtest(
                    code=code,
                    strategy_type=strategy_type,
                    params=params,
                    initial_capital=initial_capital,
                    start_date=start_date,
                    end_date=end_date,
                    max_data_days=max_data_days,
                )

                if bt_result.get('success') and bt_result.get('metrics'):
                    metrics = bt_result['metrics']
                    entry = {
                        'rank': 0,
                        'params': params,
                        'metrics': metrics,
                    }
                    all_results.append(entry)
                    result['meta']['completed'] += 1
                else:
                    result['meta']['failed'] += 1

                # 进度输出
                if (idx + 1) % 5 == 0 or idx == len(grid) - 1:
                    print(f"[GridSearch] 进度: {idx + 1}/{len(grid)}  完成: {result['meta']['completed']}  失败: {result['meta']['failed']}")

            except Exception as e:
                result['meta']['failed'] += 1
                print(f"[GridSearch] 参数 {params} 回测异常: {e}")

        # 4. 排序
        if not all_results:
            result['error'] = '所有参数组合回测失败'
            return result

        # 确定排序方向和提取字段
        metric_reverse_map = {
            'sharpe_ratio': True,    # 越高越好
            'total_return': True,
            'win_rate': True,
            'max_drawdown': False,   # 越低越好
        }
        reverse = metric_reverse_map.get(metric, True)

        def _extract_metric(metrics_dict):
            """安全提取指标值"""
            val = metrics_dict.get(metric, 0)
            if val is None:
                return 0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0

        # 按指定指标排序
        all_results.sort(key=lambda x: _extract_metric(x['metrics']), reverse=reverse)

        # 分配排名
        for i, entry in enumerate(all_results):
            entry['rank'] = i + 1

        # 前N个
        top_results = all_results[:top_n]

        # 5. 构建返回
        best = top_results[0]
        result['success'] = True
        result['best_params'] = best['params']
        result['best_metrics'] = best['metrics']
        result['all_results'] = all_results
        result['meta']['top_n'] = min(top_n, len(all_results))

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def format_grid_search_result(gs_result: dict) -> str:
    """格式化网格搜索结果文本

    Args:
        gs_result: grid_search() 返回结果

    Returns:
        str: 格式化文本
    """
    if not gs_result.get('success'):
        return f"网格搜索失败: {gs_result.get('error', '未知')}"

    meta = gs_result['meta']
    lines = [
        f"=== 网格搜索结果 ===",
        f"股票: {gs_result['code']}",
        f"策略: {meta['strategy_name']} ({gs_result['strategy_type']})",
        f"排序指标: {meta['metric']}",
        f"参数组合数: {meta['total_combinations']}  完成: {meta['completed']}  失败: {meta['failed']}",
        "",
        "最优参数:",
    ]

    for k, v in gs_result['best_params'].items():
        lines.append(f"  {k}: {v}")

    lines.append("")
    lines.append("最优表现:")

    metrics = gs_result['best_metrics']
    metric_labels = {
        'total_return': '总收益率(%)',
        'sharpe_ratio': '夏普比率',
        'max_drawdown': '最大回撤(%)',
        'win_rate': '胜率(%)',
        'total_trades': '交易次数',
        'annual_return': '年化收益率(%)',
    }
    for key, label in metric_labels.items():
        val = metrics.get(key)
        if val is not None:
            if isinstance(val, float):
                lines.append(f"  {label}: {val:.2f}")
            else:
                lines.append(f"  {label}: {val}")

    # 排名表
    lines.append("")
    lines.append(f"--- Top {meta.get('top_n', 5)} 排名 ---")

    top_results = gs_result['all_results'][:meta.get('top_n', 5)]
    for entry in top_results:
        params_str = ', '.join(f"{k}={v}" for k, v in entry['params'].items())
        metric_val = entry['metrics'].get(meta['metric'], 'N/A')
        if isinstance(metric_val, float):
            metric_str = f"{metric_val:.3f}"
        else:
            metric_str = str(metric_val)
        lines.append(f"  #{entry['rank']} [{metric_str}] 参数: {params_str}")

    return "\n".join(lines) + "\n"


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '603290'
    strategy = sys.argv[2] if len(sys.argv) > 2 else 'ma_cross'

    print(f"网格搜索: {code} ({strategy})")
    result = grid_search(code, strategy_type=strategy, max_data_days=360)
    print(format_grid_search_result(result))
