# Proposal: Market Trend Monitor

## Why

现有 `/api/market/outlook` 仅做静态评分（牛熊判定），缺少：
1. 实时趋势方向监控
2. 多维度恶化信号检测
3. 历史模式匹配预判
4. 分级预警推送

## What

新增 `market_monitor.py` 模块，6维技术指标综合评分（ADX/MA/MACD/量价/动量/RSI），输出4级预警（正常→关注→警惕→危险），仅🟠🔴时推送微信。

## Impact

- 新增文件: `market_monitor.py`, `tests/test_market_monitor.py`, `scripts/market_alert.py`
- 修改: `api_routes.py` (3个端点), `scheduler.py` (1个任务)
- 无破坏性变更，纯增量功能
- 不依赖新第三方库（纯Python+numpy）
