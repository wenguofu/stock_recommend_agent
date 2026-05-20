#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量回测模块 - 支持多股票批量回测和对比"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pandas as pd


def batch_backtest(codes, strategy_type, params=None, max_workers=3):
    """批量回测多只股票
    
    Args:
        codes: list of stock codes
        strategy_type: 'ma_cross', 'rsi_reversal', 'macd_cross', 'bollinger_break'
        params: dict of strategy params (or None for defaults)
        max_workers: parallel workers
    
    Returns:
        {
            'results': [{'code': '...', 'metrics': {...}}, ...],
            'summary': {'average_return': ..., 'best': ..., 'worst': ...},
            'ranking': [...]
        }
    """
    from backtest_engine import run_backtest, STRATEGY_PRESETS
    
    results = []
    
    def run_single(code):
        try:
            result = run_backtest(code, strategy_type, params)
            if result and result.get('metrics'):
                return {
                    'code': code,
                    'name': result.get('stock_name', code),
                    'metrics': result['metrics'],
                    'summary': result.get('trade_summary', {})
                }
        except Exception as e:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass
    
    if not results:
        return {'results': [], 'summary': {}, 'ranking': []}
    
    # 按夏普比率排序
    results.sort(key=lambda r: r['metrics'].get('sharpe_ratio', -999), reverse=True)
    
    # 排名
    ranking = []
    for i, r in enumerate(results):
        ranking.append({
            'rank': i + 1,
            'code': r['code'],
            'name': r.get('name', r['code']),
            'total_return': r['metrics'].get('total_return', 0),
            'annual_return': r['metrics'].get('annual_return', 0),
            'sharpe_ratio': r['metrics'].get('sharpe_ratio', 0),
            'max_drawdown': r['metrics'].get('max_drawdown', 0),
            'win_rate': r['metrics'].get('win_rate', 0),
            'trade_count': r['metrics'].get('total_trades', 0),
        })
    
    # 汇总
    returns = [r['metrics'].get('total_return', 0) for r in results]
    sharpes = [r['metrics'].get('sharpe_ratio', 0) for r in results if r['metrics'].get('sharpe_ratio') is not None]
    
    summary = {
        'total_stocks': len(codes),
        'succeeded': len(results),
        'average_return': sum(returns) / len(returns) if returns else 0,
        'average_sharpe': sum(sharpes) / len(sharpes) if sharpes else 0,
        'positive_return_count': sum(1 for r in returns if r > 0),
        'best': ranking[0] if ranking else None,
        'worst': ranking[-1] if ranking else None,
    }
    
    return {
        'results': results,
        'summary': summary,
        'ranking': ranking,
        'strategy_type': strategy_type,
        'params': params,
    }


def format_batch_result(result: dict) -> str:
    """格式化批量回测结果为文本"""
    if not result or not result.get('ranking'):
        return "批量回测暂无结果"
    
    lines = [
        f"## 批量回测结果",
        f"策略: {result['strategy_type']}",
        f"股票数: {result['summary']['succeeded']}/{result['summary']['total_stocks']} 成功",
        f"正收益数: {result['summary']['positive_return_count']}",
        f"平均收益率: {result['summary']['average_return']:.2%}",
        f"平均夏普: {result['summary']['average_sharpe']:.2f}",
        "",
        "### 排名",
        f"| 排名 | 代码 | 收益率 | 夏普 | 最大回撤 | 胜率 |",
        f"|------|------|--------|------|----------|------|",
    ]
    
    for r in result['ranking']:
        lines.append(
            f"| {r['rank']} | {r['name']}({r['code']}) | "
            f"{r['total_return']:.1%} | {r['sharpe_ratio']:.2f} | "
            f"{r['max_drawdown']:.1%} | {r['win_rate']:.1%} |"
        )
    
    if result['summary'].get('best'):
        lines.append("")
        b = result['summary']['best']
        lines.append(f"最佳: {b['name']}({b['code']}) 收益{b['total_return']:.1%} 夏普{b['sharpe_ratio']:.2f}")
    
    if result['summary'].get('worst'):
        w = result['summary']['worst']
        lines.append(f"最差: {w['name']}({w['code']}) 收益{w['total_return']:.1%} 夏普{w['sharpe_ratio']:.2f}")
    
    return "\n".join(lines)


if __name__ == '__main__':
    import sys
    codes = sys.argv[1].split(',') if len(sys.argv) > 1 else ['300433', '000001']
    strategy = sys.argv[2] if len(sys.argv) > 2 else 'ma_cross'
    result = batch_backtest(codes, strategy)
    print(format_batch_result(result))
