# Harness 补全计划

**目标**：为 a-stock-trading 补齐 9 项软件工程基础设施缺口

**原则**：每个 task 独立可验证，先基础设施后代码改造

---

### Task 1: 项目级 .env.example + Makefile

**文件**: `.env.example`, `Makefile`

```
.env.example  — 所有可配置项的文档化模板
Makefile      — make dev / make test / make lint / make clean
```

### Task 2: 统一错误处理中间件

**文件**: `error_handler.py`, `api_server.py`

```
@dataclass AppError  — 结构化错误
@app.errorhandler   — 全局异常 → JSON {"error","type","detail"}
```

### Task 3: 外部 API 重试装饰器

**文件**: `retry.py`, `data_fetchers.py`

```
@retry_on_failure(max_attempts=3, backoff=2)  — 腾讯/Sina/akshare 调用自动重试
```

### Task 4: AI 密钥从 DB 迁移到环境变量

**文件**: `ai_service.py`, `api_routes.py`, `.env.example`

```
DB config 表 → os.environ 读取，DB 仅作 UI 回写
```

### Task 5: 结构化日志

**文件**: `logging_config.py`, `api_server.py`

```
python-json-logger → JSON 格式日志，含 timestamp/level/module/message
```

### Task 6: API 集成测试

**文件**: `tests/test_api.py`, `tests/conftest.py`

```
pytest + Flask test_client → 关键端点请求-响应验证
```

### Task 7: pre-commit hooks

**文件**: `.pre-commit-config.yaml`

```
ruff lint + pytest 快速模式
```

### Task 8: Docker 容器化

**文件**: `Dockerfile`, `docker-compose.yml`

```
python:3.11-slim + node:20-alpine 多阶段构建
```

### Task 9: 覆盖率报告

**文件**: `pyproject.toml`, `Makefile`

```
pytest-cov → HTML 报告，make cov 一键运行
```
