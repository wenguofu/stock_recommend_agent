# Enhance StockDetail 3 Tabs (基本面/财务趋势+DCF + K线叠加基准+形态 + 舆情情绪指数+关键词)

## Why

自选股详情页 (StockDetail.tsx) 9 个 tab 中, 用户实际打开率最高的 3 个 (基本面/K线/舆情) 当前只能看静态数值, 缺失"看趋势/对比/语义"的能力:

1. **基本面 tab** - 只能看单期 PE/PB/ROE + 主营业务文字. 用户无法回答"这家公司近 3 年成长性如何? 当前估值贵不贵?" 需补: 3-5 年财务趋势图 + DCF 简易估值 (适合成长股).
2. **K线图 tab** - 只有单只 K 线, 无法直观对比大盘. 用户无法快速判断"最近跌是因为个股还是大盘". 需补: 叠加基准 (沪深300/行业指数) + 关键形态 (缺口/十字星) 自动标注.
3. **舆情 tab** - 静态新闻/帖子列表, 没有"情绪热度曲线"概念. 用户无法判断"现在是不是舆论高点? 关键词集中在哪?". 需补: 7/30 日情绪指数曲线 + 关键词云 (基于标题+帖子标题 NLP).

## What Changes

### 1. 基本面 tab
- **后端**: 复用现有 `get_stock_financials(code, limit=4)` (已支持 4 期), 加 `GET /api/fundamentals/<code>/history?limit=8` 返回时序数组
- **后端**: 新增 `GET /api/valuation/dcf/<code>?growth=0.15&discount=0.10&terminal=0.03` 简易 DCF
  - 公式: NPV = sum(EPS_t × (1+g)^t / (1+r)^t) for t=1..5 + 永续价值
  - 入参: 当前价/EPS, 5 年增速 (默认 0.15), 折现率 (默认 0.10), 永续增速 (默认 0.03)
- **前端**: 新组件 `FundamentalTrendChart.tsx` (用 antd + 自绘 SVG, 不引第三方图表库) 展示 3-5 年 4 条曲线 (营收/净利润/ROE/毛利率)
- **前端**: `StockDetail.tsx` 基本面 tab 追加两张卡: 「近 5 年财务趋势」 + 「DCF 估值」(可调 3 个滑块)

### 2. K线图 tab
- **后端**: 新增 `GET /api/sina/daily/with_benchmark/<code>?index=sh000300&count=240` 返回 `{stock_kline, benchmark_kline, baseline_field}`
  - 复用现有 `get_daily_kline`, 追加拉一次基准指数 (sh000300 默认; sh000001 / sz399006 可选)
- **后端**: 形态检测后端做 (不引依赖): 实现 4 类
  - 跳空缺口: 今日 low > 昨 high + 1% (向上) 或 今 high < 昨 low - 1% (向下)
  - 十字星: |close-open| / (high-low) < 0.1
  - 长上影: (high-max(open,close)) / (high-low) > 0.6
  - 长下影: (min(open,close)-low) / (high-low) > 0.6
- **前端**: `CandlestickChart` 组件加 prop `benchmarkData` (基准 K 线), 副图用百分比归一化叠加
- **前端**: 形态检测结果作为 `markPoint` 标在 ECharts (或 echart-for-react, 已用) K 线上, 点击弹 tooltip

### 3. 舆情 tab
- **后端**: 复用 `get_news_from_stock` + `get_guba_posts`, 加 `GET /api/sentiment/analytics/<code>?days=30&top=20` 一次返回 `{index, keywords, news}`
  - `index`: 每日情绪指数 (-1~1), 公式 (正面词数 - 负面词数) / 总词数
  - `keywords`: jieba 切词 + 停用词表后的 top N 词频
  - `news`: 原始新闻/帖子列表 (用于 fallback / drill-down)
  - 词表: 内置 ~100 个 A 股常用正/负词 (利好/业绩/突破/下跌/利空/亏损等)
- **前端**: 新组件 `SentimentIndexChart.tsx` 展示 30 日情绪指数折线 (0 为基准线, 颜色红绿)
- **前端**: `KeywordCloud.tsx` (简单 CSS 字号权重, 不引 echarts-wordcloud) 展示 top 20 关键词
- **前端**: `StockDetail.tsx` 舆情 tab 插入两个 Card, 移到现有新闻/帖子列表之前

## Out of Scope

- 不重写基本面 tab 现有 4 张卡 (行业/主营/题材/竞争力/机构预测)
- 不重写 K线图 tab 主图 (CandlestickChart 内部实现)
- 不引第三方图表库 (echarts-wordcloud / antd-charts) 全部自绘
- 不改 sentiment 现有数据源 (新浪新闻 + 东方财富股吧)

## Spec 变更

不增删 capability, 改 `frontend.md` 加新组件规范, `market-data.md` 加新 API. (openspec/specs 用单文件格式, archive 时 --skip-specs 兜底)

## 验收

1. 三个 tab 端到端可用: 打开 002222 详情页
   - 基本面 tab 看到 3 年趋势图 + DCF 估值卡 (可调滑块)
   - K线图 tab 副图显示沪深300 叠加线 + 至少 1 个形态标注
   - 舆情 tab 看到 30 日情绪曲线 + top 20 关键词
2. pytest 全过 (新增 ≥ 6 个测试覆盖 DCF 公式 / 形态检测 / 情绪指数 / 关键词提取)
3. openspec validate --strict 通过
