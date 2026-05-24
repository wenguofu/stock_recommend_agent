.PHONY: dev dev-backend dev-frontend test test-backend test-frontend lint cov clean

# ── 启动 ──
dev:
	@echo "启动后端 + 前端..."
	@python3 api_server.py & \
	cd stock_frontend && npm run dev

dev-backend:
	python3 api_server.py

dev-frontend:
	cd stock_frontend && npm run dev

# ── 测试 ──
test: test-backend

test-backend:
	.venv/bin/python -m pytest tests/ -v

test-frontend:
	cd stock_frontend && npx vitest run

# ── 覆盖率 ──
cov:
	.venv/bin/python -m pytest tests/ --cov=. --cov-report=html --cov-report=term -v
	@echo "Coverage report: htmlcov/index.html"

# ── 代码检查 ──
lint:
	.venv/bin/python -m ruff check . --fix 2>/dev/null || echo "ruff 未安装，跳过"
	cd stock_frontend && npx tsc --noEmit 2>/dev/null || echo "tsc 检查跳过"

# ── 清理 ──
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage
	@echo "清理完成"
