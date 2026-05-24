## 1. 后端优化

- [x] 1.1 `db.py`: search_etf_replacement 保持兼容（调用方已处理两种类型）
- [x] 1.2 `db.py`: 清理 create_paper_account 死代码
- [x] 1.3 `scheduler.py`: task_check_stada 用外部腾讯API，不需config.API_BASE

## 2. 后端测试 (11 passed, 7 skipped)

- [x] 2.1 `tests/test_config.py` — 4 passed ✅
- [x] 2.2 `tests/test_scheduler.py` — 7 passed ✅
- [x] 2.3 `tests/test_db.py` — 7 skipped (sqlalchemy 未装)

## 3. 前端测试 (代码就绪，待 npm install vitest)

- [x] 3.1 `src/__tests__/sectorEtfs.test.ts`
- [x] 3.2 `src/__tests__/api.test.ts`
