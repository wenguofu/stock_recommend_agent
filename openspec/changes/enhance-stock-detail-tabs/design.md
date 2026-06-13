# Design — StockDetail 3 Tabs 增强

## 1. 基本面 tab (财务趋势 + DCF)

### 后端

#### `GET /api/fundamentals/<code>/history?limit=8`
复用 `db.get_stock_financials(db, code, limit=8)` 已在 db.py:729 实现, 加新路由:
```python
@app.route('/api/fundamentals/<code>/history')
def fundamentals_history(code):
    limit = int(request.args.get('limit', 8))
    db = SessionLocal()
    rows = get_stock_financials(db, code, limit=limit)
    return jsonify({'code': code, 'history': rows})
```

#### `GET /api/valuation/dcf/<code>?growth=0.15&discount=0.10&terminal=0.03`
新建 `services/dcf.py` (或直接在 api_routes.py 内):
```python
def dcf_valuation(eps: float, current_price: float,
                  growth: float = 0.15,
                  discount: float = 0.10,
                  terminal: float = 0.03,
                  years: int = 5) -> dict:
    """5 年显式预测 + 永续年金 (Gordon Growth)
    返回: {fair_value_per_share, current_price, upside_pct,
            assumptions: {growth, discount, terminal, years}}
    """
    if not eps or eps <= 0 or not discount or discount <= terminal:
        return {'error': 'EPS 必须 > 0 且折现率 > 永续增速'}
    cashflows = []
    for t in range(1, years + 1):
        cf = eps * (1 + growth) ** t / (1 + discount) ** t
        cashflows.append(cf)
    # 永续价值: 第 N 年 EPS × (1+g_t) / (r - g_t), 折现到 t=0
    terminal_value = (eps * (1 + growth) ** years * (1 + terminal)
                      / (discount - terminal))
    terminal_pv = terminal_value / (1 + discount) ** years
    fair = sum(cashflows) + terminal_pv
    return {
        'fair_value_per_share': round(fair, 2),
        'current_price': current_price,
        'upside_pct': round((fair - current_price) / current_price * 100, 2) if current_price else None,
        'assumptions': {
            'growth': growth, 'discount': discount,
            'terminal': terminal, 'years': years,
        },
    }
```

**命名约定 (canonical, short)**: query 参数、Python 形参、返回 `assumptions` 键、JSON 字段统一使用 `growth` / `discount` / `terminal`.

### 前端

新建 `components/charts/FundamentalTrendChart.tsx`:
- props: `history: Array<{report_date, revenue, net_profit, roe, gross_margin}>`
- 自绘 SVG: 4 个 subplot 共享 X 轴 (报告期), Y 轴归一化到首期 = 100
- 鼠标 hover 跨图同步提示线

新建 `components/DCFValuation.tsx`:
- 3 个 Slider (增速 0-30%, 折现率 5-20%, 永续 0-5%)
- 默认值从 DCF API 拿
- 显示: 公允价值 / 当前价 / 上行空间 %

修改 `pages/StockDetail.tsx` 基本面 tab: 在 4 卡 (PE/PB/行业/主营/题材/竞争力/机构预测) 之后, 追加:
- Card "近 5 年财务趋势" → `<FundamentalTrendChart>`
- Card "DCF 简易估值" → `<DCFValuation code={code}>`

## 2. K线图 tab (基准叠加 + 形态标注)

### 后端

#### `GET /api/sina/daily/with_benchmark/<code>?index=sh000300&count=240`
```python
@app.route('/api/sina/daily/with_benchmark/<code>')
def daily_with_benchmark(code):
    index = request.args.get('index', 'sh000300')
    count = int(request.args.get('count', 240))
    stock = get_daily_kline(code, count=count)
    # 基准: 用同一函数 (指数 code 透传)
    benchmark = get_daily_kline(index, count=count) if index else []
    return jsonify({
        'stock': stock, 'benchmark': benchmark,
        'benchmark_field': index, 'count': len(stock),
    })
```

#### 形态检测 `services/pattern_detect.py`
```python
def detect_patterns(klines: List[dict]) -> List[dict]:
    """返回 [{date, type, direction, note}, ...]
    type: gap_up / gap_down / doji / upper_shadow / lower_shadow
    类型枚举与 frontend spec (specs/frontend/spec.md:67-72) 完全对齐,
    前端 markPoint 颜色映射依赖此契约.
    """
    out = []
    for i, k in enumerate(klines):
        if i == 0: continue
        prev = klines[i-1]
        # 跳空缺口
        if k['low'] > prev['high'] * 1.01:
            out.append({'date': k['date'], 'type': 'gap_up', 'note': '向上跳空缺口'})
        elif k['high'] < prev['low'] * 0.99:
            out.append({'date': k['date'], 'type': 'gap_down', 'note': '向下跳空缺口'})
        # 十字星
        body = abs(k['close'] - k['open'])
        rng = k['high'] - k['low']
        if rng > 0 and body / rng < 0.1:
            out.append({'date': k['date'], 'type': 'doji', 'note': '十字星'})
        # 长上影
        if rng > 0 and (k['high'] - max(k['open'], k['close'])) / rng > 0.6:
            out.append({'date': k['date'], 'type': 'upper_shadow', 'note': '长上影线'})
        # 长下影
        if rng > 0 and (min(k['open'], k['close']) - k['low']) / rng > 0.6:
            out.append({'date': k['date'], 'type': 'lower_shadow', 'note': '长下影线'})
    return out
```

集成到 with_benchmark 路由一并返回 `patterns` 字段。

### 前端

修改 `components/charts/CandlestickChart.tsx`:
- props 加 `benchmarkData?: Array<{date, close}>`, `patterns?: Array<{date, type, note}>`
- 主图保留; 副图加百分比归一化基准线 (Y 轴 = 0%, 起点 = 第一根 close 归 0)
- 形态用 markPoint (不同 type 不同颜色, tooltip 显示 note)

修改 `pages/StockDetail.tsx` K线图 tab:
- 调 `/api/sina/daily/with_benchmark/<code>?index=sh000300&count=240`
- 把 benchmarkData / patterns 传给 CandlestickChart

## 3. 舆情 tab (情绪指数 + 关键词)

### 后端

#### `GET /api/sentiment/keywords/<code>?days=30&top=20`
新建 `services/text_mining.py`:
```python
POSITIVE = {'利好','业绩','突破','增长','上涨','新高','受益','订单','回购','分红','中标','合作','签约','扩产','放量','龙头','独家','优势','强劲','创新'}
NEGATIVE = {'利空','亏损','下跌','下滑','减持','减仓','风险','下调','问询','处罚','停牌','违规','诉讼','退市','下调评级','下调目标','不及预期','风险提示','暴跌','跌停'}

STOPWORDS = {'的','了','和','是','在','有','我','你','他','我们','你们','他们','这','那','就','也','都','与','及','或','为','与','以','其','于','上','下','中','对','从'}

import jieba
def extract_keywords(items: List[str], top: int = 20) -> List[dict]:
    counter = {}
    for text in items:
        for w in jieba.cut(text):
            w = w.strip()
            if len(w) < 2 or w in STOPWORDS: continue
            counter[w] = counter.get(w, 0) + 1
    return [{'word': w, 'count': c} for w, c in
            sorted(counter.items(), key=lambda x: -x[1])[:top]]
```

#### `GET /api/sentiment/analytics/<code>?days=30&top=20` (合并接口)
```python
def sentiment_index(items: List[dict], days: int = 30) -> List[dict]:
    """返回 [{date, score, news_count}, ...] score = (pos - neg) / total
    items 形如 [{date, title, source}, ...]
    空标题 (title='') 跳过 (避免 POSITIVE/NEGATIVE 命中空串);
    当日 total=0 时 score=0 兜底, 避免 ZeroDivisionError.
    """
    by_date = {}
    for it in items:
        d = (it.get('date', '') or '')[:10]
        if not d: continue
        title = (it.get('title') or '').strip()
        if not title: continue  # 跳过空标题
        pos = sum(1 for w in POSITIVE if w in title)
        neg = sum(1 for w in NEGATIVE if w in title)
        total = pos + neg
        score = (pos - neg) / total if total > 0 else 0
        by_date.setdefault(d, []).append(score)
    return [{'date': d, 'score': round(sum(s)/len(s), 3), 'count': len(s)}
            for d, s in sorted(by_date.items())]
```

合并路由 `GET /api/sentiment/analytics/<code>?days=30&top=20` 一次返回 `{index, keywords, news}`.

**`news` 字段契约**:
- 形状: `Array<{date: 'YYYY-MM-DD HH:MM:SS', title: str, source: 'sina'|'guba'}>`
- 来源: `get_news_from_stock(code, days)` + `get_guba_posts(code, days)` 拼接 (按时间倒序, 上限各 100 条)
- 日期窗口: 严格 `now - days` 之内; 超出窗口的过滤掉
- 用途: 前端 fallback / drill-down (若 index 与 keywords 已能回答问题, 列表仍可点开看原文)

### 前端

新建 `components/SentimentIndexChart.tsx`:
- props: `index: Array<{date, score}>` (score 范围 -1~1)
- 自绘 SVG 折线, 0 为基准线, >0 红 / <0 绿
- 鼠标 hover 显示日期 + score

新建 `components/KeywordCloud.tsx`:
- props: `keywords: Array<{word, count}>` (top 20)
- 简单 CSS 布局: count 越大字号越大, 颜色随机 (HSL)
- 不引第三方 wordcloud 库

修改 `pages/StockDetail.tsx` 舆情 tab: 在现有 news/posts 列表**之前**插入两卡:
- Card "30 日情绪指数" → `<SentimentIndexChart>`
- Card "热门关键词" → `<KeywordCloud>`

## 4. 数据契约 spec

不改, 通过 archive --skip-specs 兜底.

## 风险

- jieba 体积: ~10MB, 已在 venv 内 (验证); 失败可降级到无 jieba 的简易 split
- DCF 假设极简 (固定增速 5 年), 适合成长股, 不适合周期股 (产品形态/周期股可在 UI 上提示)
- 形态检测是简单规则, 准确率有限, 标"自动识别"提示用户
