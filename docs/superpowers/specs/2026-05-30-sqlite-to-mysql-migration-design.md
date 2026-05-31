# SQLite → MySQL 数据存储迁移

**日期**: 2026-05-30
**状态**: 已批准

## 目标

将 AI stock trading agent 的数据存储从 SQLite 迁移到 MySQL 9.6.0，包括：
1. 存量数据完整迁移（26 张表，~125 万行）
2. 应用层透明切换（通过环境变量 `DATABASE_URL`）
3. 补全缺失的 ORM 模型

## 数据库

| 项目 | 值 |
|------|-----|
| 数据库名 | stock_trading |
| 用户 | stock_user@localhost |
| 字符集 | utf8mb4 |
| collation | utf8mb4_unicode_ci |

## 连接对比

| 项目 | SQLite (旧) | MySQL (新) |
|------|-------------|------------|
| 连接串 | `sqlite:///database.db` | `mysql+pymysql://stock_user:stock_pass_2024@127.0.0.1:3306/stock_trading` |
| 自增主键 | `sqlite_autoincrement` | MySQL 原生 AUTO_INCREMENT |
| 并发 | WAL + check_same_thread=False | 连接池 pool_size=10 |
| 字符集 | - | utf8mb4 |
| 线程安全 | 手动 pragma | 连接池自动管理 |

## 实施阶段

### Phase 1: 基础设施
- models.py: 新增 RecommendationTrack 模型，抽象 get_engine() 工厂函数，移除 SQLite 专属代码
- config.py: 新增 DATABASE_URL 环境变量
- requirements.txt: 新增 pymysql, cryptography

### Phase 2: 数据迁移
- migrate_to_mysql.py: SQLAlchemy create_all + 批量 insert (5000/批)
- 迁移后行数验证

### Phase 3: 切换
- 设置 DATABASE_URL 环境变量
- 重启服务验证

## 涉及文件
- 修改: models.py, db.py, config.py, requirements.txt
- 新增: migrate_to_mysql.py
- 不影响: 46 个业务文件（通过 SessionLocal 透明访问）

## 回滚
旧 database.db 保留为备份，切换 DATABASE_URL 回 sqlite 即可恢复。
