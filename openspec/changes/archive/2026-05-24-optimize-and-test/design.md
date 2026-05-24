## Why

系统经审计发现多处可优化点，需建立测试体系保障后续变更安全。

## What Changes

### 优化
- `db.py`: 修复 `search_etf_replacement()` 类型不一致（return dict vs ORM）
- `db.py`: 清理 `create_paper_account()` 死代码
- `scheduler.py`: `task_check_stada` 改用 config.API_BASE 而非直接调腾讯API

### 测试
- 后端 pytest: `tests/` 目录
  - `test_config.py` — 配置模块
  - `test_scheduler.py` — 调度器逻辑
  - `test_db.py` — ORM 模型
- 前端 vitest: `stock_frontend/src/__tests__/`
  - `sectorEtfs.test.ts` — ETF 映射逻辑
  - `api.test.ts` — API 服务类

## Impact

- 纯增量（新增测试文件），不影响现有功能
- `search_etf_replacement()` 行为可能有微小变化（统一返回类型）
