# Tasks — StockDetail 3 Tabs 增强

## 1. TDD Red — 写复现 + 期望测试
- [ ] 1.1 `tests/test_dcf.py` — dcf_valuation() 公式正确性 (5 年显式 + Gordon 永续)
  - 1.1.a 正常公式: EPS=1, g=0.15, r=0.10, term=0.03 验算 fair_value 与 upside_pct
  - 1.1.b 错误路径: discount <= terminal 时返回 `{'error': ...}` (Spec Scenario spec.md:39-42 强制 UI 处理)
- [ ] 1.2 `tests/test_pattern_detect.py` — detect_patterns() 5 类形态 (gap_up/gap_down/doji/upper_shadow/lower_shadow)
- [ ] 1.3 `tests/test_text_mining.py` — extract_keywords() 词频排序, 停用词过滤
- [ ] 1.4 `tests/test_text_mining.py` — sentiment_index() 正负词打分 (-1~1)
- [ ] 1.5 `tests/test_fundamentals_history.py` — `/api/fundamentals/<code>/history` 返回多期时序
  - 1.5.a 正常: 返回 history 长度 ≥ 2
  - 1.5.b 空态: history 长度 < 2 时返回 `{code, history: []}` (UI 侧 spec.md:18-20 隐藏趋势图 + Alert; 后端只负责如实返回)
- [ ] 1.6 `tests/test_sentiment_analytics.py` — `/api/sentiment/analytics/<code>` 返回 {index, keywords, news}

## 2. TDD Green — 后端
- [ ] 2.1 `services/dcf.py` dcf_valuation()
- [ ] 2.2 `api_routes.py` 加 `/api/fundamentals/<code>/history` 路由
- [ ] 2.3 `api_routes.py` 加 `/api/valuation/dcf/<code>` 路由
- [ ] 2.4 `services/pattern_detect.py` detect_patterns()
- [ ] 2.5 `api_routes.py` 加 `/api/sina/daily/with_benchmark/<code>` (含 patterns)
- [ ] 2.6 `services/text_mining.py` POSITIVE/NEGATIVE/STOPWORDS + extract_keywords() + sentiment_index()
- [ ] 2.7 `api_routes.py` 加 `/api/sentiment/analytics/<code>` 合并接口
- [ ] 2.8 (可选) jieba 引入; 失败则降级

## 3. TDD Green — 前端
- [ ] 3.1 `components/charts/FundamentalTrendChart.tsx` 自绘 SVG
- [ ] 3.2 `components/DCFValuation.tsx` 3 Slider + 显示结果
- [ ] 3.3 `components/SentimentIndexChart.tsx` 自绘 SVG
- [ ] 3.4 `components/KeywordCloud.tsx` CSS 字号权重
- [ ] 3.5 `components/charts/CandlestickChart.tsx` 加 benchmarkData / patterns props
- [ ] 3.6 `pages/StockDetail.tsx` 3 tab 各插入新组件

## 4. 验证
- [ ] 4.1 `pytest -q tests/test_dcf.py tests/test_pattern_detect.py tests/test_text_mining.py tests/test_fundamentals_history.py tests/test_sentiment_analytics.py` 全绿
- [ ] 4.2 全量 `pytest -q --no-cov tests/` 不挂 (除 pre-existing)
- [ ] 4.3 `openspec validate --strict` 通过
- [ ] 4.4 手动打开 002222 详情页, 三个 tab 都看到新能力
