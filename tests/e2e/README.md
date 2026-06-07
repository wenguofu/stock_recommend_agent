# E2E 浏览器自动化测试

基于 Playwright 的 portal 端到端测试, 覆盖所有 25 个页面 + 主要交互。

## 目录结构

```
tests/e2e/
├── README.md                  ← 本文件
├── conftest.py                ← BasePageTest 框架 (smoke/apis/clicks)
├── portal_e2e.py              ← 主入口 CLI
├── page_tests/                ← 25 个页面的测试定义
│   ├── __init__.py            ← ALL_TESTS 列表
│   ├── home.py
│   ├── watchlist.py
│   ├── stock_detail.py
│   ├── tasks.py
│   ├── strategy.py
│   ├── strategy_library.py
│   ├── strategy_run.py
│   ├── strategy_recommend.py
│   ├── strategy_config.py
│   ├── ai_debate.py
│   ├── paper_accounts.py
│   ├── paper_detail.py
│   ├── paper_rankings.py
│   ├── paper_breakdown.py
│   ├── recommendations.py
│   ├── high_win_recommend.py
│   ├── backtest.py
│   ├── sector_prediction.py
│   ├── sensitivity_scan.py
│   ├── portfolio.py
│   ├── ml_monitoring.py
│   ├── alert_center.py
│   ├── settings.py
│   ├── midline.py
│   └── not_found.py
├── reports/                   ← JSON + Markdown 报告 (按时间戳)
└── screenshots/               ← 失败截图
```

## 快速开始

### 前置条件

1. Flask 服务运行中 (`http://localhost:35000`)
2. 前端 dist 已构建 (`stock_frontend/dist/index.html` 存在)
3. Playwright + Chromium 已安装:
   ```bash
   .venv/bin/python -m pip install playwright
   .venv/bin/python -m playwright install chromium
   ```

### 一键运行

```bash
# Smoke 测试 (25 个页面, 26 秒)
.venv/bin/python tests/e2e/portal_e2e.py

# API 测试 (抓所有 /api/ 调用, 检查 5xx)
.venv/bin/python tests/e2e/portal_e2e.py --mode apis

# Full 测试 (含 click 交互)
.venv/bin/python tests/e2e/portal_e2e.py --mode full

# 单页面
.venv/bin/python tests/e2e/portal_e2e.py --page /monitoring

# 报告输出
.venv/bin/python tests/e2e/portal_e2e.py --output-format both
```

## 三种测试模式

### 1. smoke (默认, 26 秒)

- 打开页面, 等待 React 渲染
- 检查 `.ant-layout / .ant-card / .ant-table` 存在
- 截图保存
- 验证没有 404 错误

### 2. apis (~80 秒)

- 监听所有 `/api/` 网络请求
- 累计统计 API 调用数
- 报告任何 **5xx** 错误 (服务器异常)
- 4xx 客户端错误视为正常 (例如数据不存在)

### 3. full (~120 秒)

- smoke + apis + 实际 click 测试
- 触发每个 interactive 元素 (button, tab, form)
- 等待目标元素出现

## 测试用例清单 (25 个页面)

| # | 页面 | 路径 | 关键交互 | API |
|---|------|------|----------|-----|
| 1 | 首页 | `/` | 卡片渲染 | 大盘/板块/AI 辩论 |
| 2 | 自选股 | `/watchlist` | 添加/编辑 | watchlist / agents |
| 3 | 股票详情 | `/stock/000001` | Tab 切换 | 综合/实时/情绪 |
| 4 | 任务 | `/tasks` | 新建/执行/编辑 | tasks / alerts |
| 5 | 策略 | `/strategy` | 批量/辩论 | 强股 / 辩论 |
| 6 | 策略库 | `/strategies` | 卡片/运行 | strategies |
| 7 | 策略运行 | `/strategies/:id/run` | 运行 | sectors / run |
| 8 | 策略推荐 | `/strategy` | 添加/创建 | 强股 / 辩论 |
| 9 | 策略配置 | `/strategy-config` | 保存/重置 | (纯前端) |
| 10 | AI 辩论 | `/ai-debate` | 启动/停止 | debate |
| 11 | 模拟盘 | `/paper` | 新建账户 | paper |
| 12 | 模拟盘详情 | `/paper/:id` | 下单/查看 | paper |
| 13 | 收益排名 | `/paper/rankings` | 排名 | paper |
| 14 | 盈亏分解 | `/paper/breakdown/:id` | 查看 | paper |
| 15 | 股票推荐 | `/recommendations` | 列表 | recs |
| 16 | 高胜率推荐 | `/high-win-recommend` | 列表 | recs |
| 17 | 回测 | `/backtest` | 运行回测 | presets / run |
| 18 | 主线预判 | `/sector-prediction` | 分析/刷新 | 板块预测 |
| 19 | 敏感度扫描 | `/sensitivity` | 开始扫描 | scan |
| 20 | 组合优化 | `/portfolio` | Markowitz/前沿 | portfolio |
| 21 | ML 监控 | `/monitoring` | Tab 切换 | ML 监控 |
| 22 | 告警 | `/alerts` | 发送/清空 | alerts / cache |
| 23 | 系统配置 | `/settings` | 保存/测试 | config |
| 24 | 自选池健康度 | `/midline` | 查看 | midline |
| 25 | 404 | `/nonexistent-route-12345` | (反向) | midline |

## 测试发现的历史 Bug

跑 E2E 过程中发现并修复了 2 个真实 bug:

### Bug 1: SPA 路由 404
**问题**: Flask errorhandler 对所有未匹配路径返回 JSON 404, 导致 React Router 客户端导航失效。
**修复**: `error_handler.py` 区分 `/api/` 和 SPA 路由, 后者返回 `index.html`。

### Bug 2: SQLAlchemy 2.0 raw SQL
**问题**: `midline_routes.py` 使用 `db.execute("SELECT ...")` 不被 SQLAlchemy 2.0 接受, 返回 500。
**修复**: 用 `text("...")` 包裹, 并用命名参数 `{"limit": ..., "offset": ...}` 替换 `?` 占位符。

## 报告示例

`tests/e2e/reports/report_full_20260607_102816.md`:

```markdown
# E2E 测试报告 (full)
**时间**: 2026-06-07T10:28:16Z
**耗时**: 104.0s

- ✅ 通过: 54
- ❌ 失败: 0
- ⏭️  跳过: 43

## 详情
### ✅ / :: smoke.layout
- 状态: pass
- 耗时: 1234ms
- 详情: 页面布局渲染成功
...
```

## 已知问题 (非 bug)

- `/api/ml/predict/000001` 在缺 torch 环境返回 500
  - 解决方法: `pip install torch` 或在生产环境运行
- 部分 scheduler 触发的 ML 任务会调用上述端点
  - 视为"环境问题", 不影响应用功能

## 添加新页面测试

```python
# tests/e2e/page_tests/my_page.py
from conftest import BasePageTest

class MyPageTest(BasePageTest):
    path = "/my-page"
    title = "我的页面"
    interactive = [
        # 必须存在的元素 (会 fail if missing)
        {"selector": "button:has-text('确定')", "description": "确定按钮"},
        # 可选元素 (missing = skip)
        {"selector": ".my-icon", "description": "图标", "optional": True},
        # 仅等待, 不点击
        {"description": "数据加载", "action": "wait",
         "wait_for": ".ant-table, .ant-empty"},
    ]
```

然后在 `page_tests/__init__.py` 添加到 `ALL_TESTS` 列表。
