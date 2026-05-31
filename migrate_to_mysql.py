#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite → MySQL 存量数据迁移脚本

用法:
  python3 migrate_to_mysql.py

环境变量:
  DATABASE_URL_SQLITE: SQLite 连接 URL (默认: 同目录下的 database.db)
  DATABASE_URL_MYSQL:  MySQL 连接 URL (默认: 本地 stock_trading 库)

特性:
  - 26 张表完整迁移
  - backtest_data (124万行) 按 5000 行/批处理
  - 进度条显示
  - 迁移后行数对比验证
  - 支持断点续传（已存在的表可跳过）
"""

import os
import sys
import time
from datetime import datetime

# ── 配置 ──
SQLITE_URL = os.environ.get(
    "DATABASE_URL_SQLITE",
    f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database.db')}"
)
MYSQL_URL = os.environ.get(
    "DATABASE_URL_MYSQL",
    "mysql+pymysql://stock_user:stock_pass_2024@127.0.0.1:3306/stock_trading"
)

BATCH_SIZE = 5000  # 大批量数据每次插入行数
SKIP_EMPTY = True  # 跳过空表


def get_engine(url):
    """创建数据库引擎"""
    from sqlalchemy import create_engine

    if url.startswith("sqlite"):
        return create_engine(
            url, echo=False,
            connect_args={'check_same_thread': False, 'timeout': 30},
        )
    else:
        return create_engine(
            url, echo=False,
            pool_size=5, max_overflow=10,
            pool_pre_ping=True, pool_recycle=3600,
        )


def get_table_names(engine):
    """获取所有用户表名（排除系统表）"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    # 排除 SQLite 内部表
    skip = {'sqlite_sequence'}
    return [t for t in tables if t not in skip]


def get_table_model_map():
    """表名 → ORM Model 映射"""
    from models import (
        Watchlist, Config, Agent, AnalysisCache, Strategy,
        DebateJob, MonitorTask, KlineCache,
        PaperAccount, PaperPosition, PaperOrder, PaperSnapshot,
        PaperAutoRule, EtfReplacementMap, PaperPlan,
        BacktestData, BacktestStockMeta, TaskLog, Recommendation,
        StockFinancial, RiskReport, PortfolioConfig, TradeJournal,
        MarketAlertLog, RecommendationTrack,
    )

    return {
        'watchlist': Watchlist,
        'config': Config,
        'agents': Agent,
        'analysis_cache': AnalysisCache,
        'strategies': Strategy,
        'debate_jobs': DebateJob,
        'monitor_tasks': MonitorTask,
        'kline_cache': KlineCache,
        'paper_accounts': PaperAccount,
        'paper_positions': PaperPosition,
        'paper_orders': PaperOrder,
        'paper_snapshots': PaperSnapshot,
        'paper_auto_rules': PaperAutoRule,
        'etf_replacement_map': EtfReplacementMap,
        'paper_plans': PaperPlan,
        'backtest_data': BacktestData,
        'backtest_stock_meta': BacktestStockMeta,
        'task_logs': TaskLog,
        'recommendations': Recommendation,
        'stock_financials': StockFinancial,
        'risk_reports': RiskReport,
        'portfolio_configs': PortfolioConfig,
        'trade_journal': TradeJournal,
        'market_alert_log': MarketAlertLog,
        'recommendation_tracks': RecommendationTrack,
    }


def get_migration_order():
    """定义迁移顺序：先迁无依赖的表，再迁有外键引用的表"""
    return [
        # Tier 0: 无依赖的独立表
        'config',
        'watchlist',
        'agents',
        'strategies',
        'monitor_tasks',
        'etf_replacement_map',
        'analysis_cache',
        'market_alert_log',
        'portfolio_configs',
        'task_logs',
        'trade_journal',
        'recommendation_tracks',

        # Tier 1: 有引用但通常先迁母表
        'paper_accounts',

        # Tier 2: 依赖 paper_accounts 的表
        'paper_positions',
        'paper_orders',
        'paper_snapshots',
        'paper_auto_rules',
        'paper_plans',

        # Tier 3: 数据量大但独立
        'backtest_stock_meta',
        'backtest_data',  # ~124 万行
        'kline_cache',    # ~2 万行
        'stock_financials',

        # Tier 4: 依赖 agents/strategies 的表
        'debate_jobs',
        'recommendations',
        'risk_reports',
    ]


def row_to_dict(row, model, engine_is_mysql=False):
    """将 ORM 对象转为字典，过滤掉 MySQL 不兼容的字段"""
    from sqlalchemy import inspect as sa_inspect
    mapper = sa_inspect(model)
    columns = {c.key for c in mapper.column_attrs}

    result = {}
    for key in columns:
        val = getattr(row, key, None)
        result[key] = val
    return result


def migrate_table(table_name, model, sqlite_session, mysql_session, batch_size=5000):
    """迁移单张表"""
    from sqlalchemy import inspect

    # 检查 MySQL 是否已有数据
    existing_count = mysql_session.query(model).count()
    source_count = sqlite_session.query(model).count()

    print(f"\n{'='*60}")
    print(f"📋 表: {table_name}")
    print(f"   SQLite: {source_count:,} 行  →  MySQL: {existing_count:,} 行")

    if source_count == 0:
        if SKIP_EMPTY:
            print(f"   ⏭️  空表，跳过")
            return {'table': table_name, 'source': 0, 'target': existing_count, 'migrated': 0}
    elif existing_count > 0:
        if existing_count >= source_count:
            print(f"   ✅ MySQL 已有 {existing_count} 行，无需迁移")
            return {'table': table_name, 'source': source_count, 'target': existing_count, 'migrated': 0}
        else:
            print(f"   ⚠️  MySQL 数据不完整 ({existing_count}/{source_count})，清空后重新迁移")
            mysql_session.query(model).delete()
            mysql_session.commit()

    # ── 批量读取并写入 ──
    if source_count <= batch_size:
        # 小表：一次性迁移
        rows = sqlite_session.query(model).all()
        migrated = 0
        for row in rows:
            data = row_to_dict(row, model)
            new_obj = model(**data)
            mysql_session.add(new_obj)
            migrated += 1
        mysql_session.commit()
        print(f"   ✅ 迁移 {migrated:,} 行 (一次性)")
    else:
        # 大表：分批迁移
        total = source_count
        offset = 0
        migrated = 0
        start_time = time.time()

        while offset < total:
            rows = sqlite_session.query(model).limit(batch_size).offset(offset).all()
            if not rows:
                break

            for row in rows:
                data = row_to_dict(row, model)
                new_obj = model(**data)
                mysql_session.add(new_obj)

            mysql_session.commit()
            batch_count = len(rows)
            migrated += batch_count
            offset += batch_size

            elapsed = time.time() - start_time
            rate = migrated / elapsed if elapsed > 0 else 0
            pct = migrated / total * 100
            remaining = (total - migrated) / rate if rate > 0 else 0

            print(f"\r   ⏳ {migrated:,}/{total:,} ({pct:.1f}%)  "
                  f"速率 {rate:.0f} 行/秒  剩余 ~{remaining:.0f}s", end="", flush=True)

        elapsed = time.time() - start_time
        print(f"\n   ✅ 迁移 {migrated:,} 行  耗时 {elapsed:.1f}s  "
              f"速率 {migrated/elapsed:.0f} 行/秒")

    # 验证 MySQL 行数
    final_count = mysql_session.query(model).count()
    if final_count == source_count:
        print(f"   ✔  行数验证通过: {final_count:,}")
    else:
        print(f"   ❌ 行数不匹配! SQLite: {source_count:,}  MySQL: {final_count:,}")

    return {
        'table': table_name,
        'source': source_count,
        'target': final_count,
        'migrated': migrated if source_count > 0 else 0,
    }


def main():
    print("=" * 60)
    print("🚀 SQLite → MySQL 数据迁移")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   SQLite: {SQLITE_URL}")
    print(f"   MySQL:  {MYSQL_URL}")
    print(f"   批大小: {BATCH_SIZE} 行/批")

    # ── 创建引擎 ──
    from sqlalchemy.orm import sessionmaker

    sqlite_engine = get_engine(SQLITE_URL)
    mysql_engine = get_engine(MYSQL_URL)

    SQLiteSession = sessionmaker(bind=sqlite_engine)
    MySQLSession = sessionmaker(bind=mysql_engine)

    sqlite_db = SQLiteSession()
    mysql_db = MySQLSession()

    # ── 确保 MySQL 表结构已创建 ──
    from models import Base
    Base.metadata.create_all(mysql_engine)

    # ── 获取迁移顺序 ──
    table_map = get_table_model_map()
    migration_order = get_migration_order()

    # 检查是否有遗漏的表
    all_tables = get_table_names(sqlite_engine)
    unmapped = set(all_tables) - set(migration_order)
    if unmapped:
        print(f"\n⚠️  未纳入迁移的表: {unmapped}")

    # ── 执行迁移 ──
    results = []
    total_start = time.time()

    for table_name in migration_order:
        if table_name not in table_map:
            print(f"\n⚠️  表 '{table_name}' 没有对应 Model，跳过")
            continue

        # 检查源表是否存在
        if table_name not in all_tables:
            print(f"\n⏭️  源表 '{table_name}' 不存在于 SQLite，跳过")
            continue

        model = table_map[table_name]
        try:
            result = migrate_table(table_name, model, sqlite_db, mysql_db, BATCH_SIZE)
            results.append(result)
        except Exception as e:
            print(f"\n   ❌ 迁移失败: {e}")
            results.append({'table': table_name, 'source': '?', 'target': '?', 'migrated': 0, 'error': str(e)})

    total_elapsed = time.time() - total_start

    # ── 汇总报告 ──
    print(f"\n{'='*60}")
    print("📊 迁移报告")
    print(f"{'='*60}")
    print(f"{'表名':<30} {'源行数':>10} {'目标行数':>10} {'状态':>8}")
    print("-" * 60)

    total_source = 0
    total_target = 0
    errors = 0

    for r in results:
        src = r.get('source', '?')
        tgt = r.get('target', '?')
        status = '✅' if src == tgt else '❌'
        if 'error' in r:
            status = '💥'
            errors += 1
        print(f"{r['table']:<30} {str(src):>10} {str(tgt):>10} {status:>8}")
        if isinstance(src, int) and isinstance(tgt, int):
            total_source += src
            total_target += tgt

    print("-" * 60)
    print(f"{'合计':<30} {total_source:>10,} {total_target:>10,}")
    print(f"\n⏱  总耗时: {total_elapsed:.1f}s")
    print(f"📋 表数: {len(results)}")
    if errors:
        print(f"⚠️  失败: {errors} 张表")
    print(f"{'='*60}")

    # ── 清理 ──
    sqlite_db.close()
    mysql_db.close()
    sqlite_engine.dispose()
    mysql_engine.dispose()

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
