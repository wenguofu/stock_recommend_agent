# frontend delta — StockDetail 3 Tabs 增强

## ADDED Requirements

### Requirement: 基本面 tab 财务趋势图

基本面 tab **MUST** 在原有静态数值卡 (PE/PB/ROE/行业/主营/题材/竞争力/机构预测) 之后, 追加显示近 5 年财务趋势图, 以 4 条归一化曲线 (营收/净利润/ROE/毛利率) 回答"成长性如何".

#### Scenario: 历史数据 ≥ 2 期

- **WHEN** 调 `GET /api/fundamentals/<code>/history?limit=8` 返回 history 数组长度 ≥ 2
- **THEN** 基本面 tab **MUST** 渲染 `FundamentalTrendChart` 组件
- **AND** 4 条曲线共享 X 轴 (报告期), Y 轴以首期为基准归一化 (= 100)
- **AND** hover 跨图显示同步提示线

#### Scenario: 历史数据 < 2 期

- **WHEN** history 数组长度 < 2 (新上市 / 数据缺失)
- **THEN** **MUST** 隐藏趋势图 Card, 展示 `Alert type="info" message="历史数据不足, 无法绘制趋势"`

### Requirement: 基本面 tab DCF 估值

基本面 tab **MUST** 提供 DCF 简易估值交互卡, 允许用户调整 3 个假设参数, 实时显示公允价值与上行空间.

#### Scenario: 加载与默认值

- **WHEN** 用户进入基本面 tab
- **THEN** 调 `GET /api/valuation/dcf/<code>?growth=0.15&discount=0.10&terminal=0.03`
- **AND** 展示: 公允价值 / 当前价 / 上行空间 %
- **AND** 3 个 Slider 默认值: 增速 15%, 折现率 10%, 永续增速 3%

#### Scenario: 用户调整假设

- **WHEN** 用户拖动任一 Slider
- **THEN** **MUST** 防抖 300ms 后重新调 DCF API
- **AND** 更新公允价值 / 上行空间显示
- **AND** 提示: "假设: 5 年显式预测 + Gordon 永续, 仅适合成长股"

#### Scenario: EPS ≤ 0 或折现率 ≤ 永续增速

- **WHEN** 后端返回 `error: 'EPS 必须 > 0 且折现率 > 永续增速'`
- **THEN** 卡片 **MUST** 显示该错误提示, 不显示数值

### Requirement: K线图 tab 基准叠加

K线图 tab **MUST** 在主图下方副图叠加基准指数 (默认沪深300) 归一化曲线, 以快速判断"个股相对大盘强弱".

#### Scenario: 加载基准数据

- **WHEN** 用户进入 K线图 tab
- **THEN** 调 `GET /api/sina/daily/with_benchmark/<code>?index=sh000300&count=240`
- **AND** 主图保留现有 K 线 / 均线
- **AND** 副图 **MUST** 渲染基准指数归一化曲线 (起点 = 0%, 终点 = 累计涨跌 %)

#### Scenario: 切换基准

- **WHEN** 用户选择其他基准 (上证指数 sh000001 / 创业板指 sz399006)
- **THEN** **MUST** 重新调 API 替换基准数据
- **AND** 副图重新归一化渲染

### Requirement: K线图 tab 形态标注

K线图 tab **MUST** 在主图上以 markPoint 标注 5 类自动识别的 K 线形态.

#### Scenario: 后端检测形态

- **WHEN** 后端 `/api/sina/daily/with_benchmark/<code>` 返回 `patterns` 字段
- **THEN** **MUST** 包含 5 类: gap_up / gap_down / doji / upper_shadow / lower_shadow
- **AND** 每条标注含 date / type / note
- **AND** 主图 **MUST** 在对应 K 线上方显示类型对应颜色的图标
- **AND** 鼠标悬停显示 note tooltip

#### Scenario: 无形态数据

- **WHEN** patterns 数组为空
- **THEN** **MUST** 不渲染任何 markPoint (不报错)

### Requirement: 舆情 tab 情绪指数曲线

舆情 tab **MUST** 在现有新闻/帖子列表**之前**展示 30 日情绪指数曲线, 让用户判断舆论温度.

#### Scenario: 加载与渲染

- **WHEN** 用户进入舆情 tab
- **THEN** 调 `GET /api/sentiment/analytics/<code>?days=30`
- **AND** `SentimentIndexChart` **MUST** 渲染 30 日折线, 0 为基准线
- **AND** score > 0 用红色 (#cf1322), < 0 用绿色 (#389e0d)
- **AND** hover 显示 date + score

#### Scenario: 数据不足

- **WHEN** 索引数组 < 3 个数据点
- **THEN** **MUST** 隐藏图表 Card, 展示 `Alert message="舆情数据不足, 无法绘制情绪曲线"`

### Requirement: 舆情 tab 关键词云

舆情 tab **MUST** 展示 30 日 top 20 关键词, 用 CSS 字号权重可视化 (不引第三方词云库).

#### Scenario: 渲染

- **WHEN** 调 `/api/sentiment/analytics/<code>?days=30&top=20` 返回 keywords 数组
- **AND** 数组长度 ≥ 1
- **THEN** `KeywordCloud` **MUST** 用 CSS flex-wrap 布局, count 越大字号越大 (12px~32px)
- **AND** 颜色用 HSL 随机 (避免全部黑色)
- **AND** hover 显示 count tooltip

#### Scenario: 空数据

- **WHEN** keywords 数组为空
- **THEN** **MUST** 展示 `Alert message="暂无关键词数据"`
