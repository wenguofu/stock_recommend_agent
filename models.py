#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库模型定义"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Watchlist(Base):
    """自选股表"""
    __tablename__ = 'watchlist'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(6), unique=True, nullable=False, index=True)
    name = Column(String(50))
    cost_price = Column(Float, nullable=True)  # 持仓成本价
    shares = Column(Integer, nullable=True)    # 持股数量
    added_at = Column(DateTime, default=datetime.now)
    sort_order = Column(Integer, default=0)

class Config(Base):
    """配置表"""
    __tablename__ = 'config'
    
    key = Column(String(50), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Agent(Base):
    """Agent配置表"""
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # 'default', 'intraday_t', 'review'
    prompt = Column(Text)
    enabled = Column(Boolean, default=True)
    ai_provider = Column(String(20))  # 'openai', 'deepseek', 'qwen', 'gemini', 'grok'
    model = Column(String(50))
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

class AnalysisCache(Base):
    """分析结果缓存表"""
    __tablename__ = 'analysis_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(6), nullable=False, index=True)
    analysis_type = Column(String(20), nullable=False)  # 'intraday_t', 'review', 'comprehensive'
    data = Column(Text)  # JSON格式
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class Strategy(Base):
    """策略预设表"""
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # 'youzi', 'jiangu', 'jichang', 'lianghua'
    doc_md = Column(Text)  # 详细的文案/说明文档
    agent_configs = Column(Text)  # JSON: 包含全部Agent prompt配置
    enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

class DebateJob(Base):
    """多Agent辩论任务表"""
    __tablename__ = 'debate_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    code = Column(String(6), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default='queued')  # queued/running/completed/failed/canceled
    progress = Column(Integer, default=0)
    agent_ids = Column(Text)  # JSON
    steps = Column(Text)  # JSON
    progress_detail = Column(Text)  # JSON: [{phase, agent_name, round, detail}]
    report_md = Column(Text)
    error = Column(Text)
    canceled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class MonitorTask(Base):
    """盯盘任务表"""
    __tablename__ = 'monitor_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    task_type = Column(String(20), nullable=False, default='price_alert')  # price_alert, technical_alert, ai_analysis
    codes = Column(Text, nullable=False)  # JSON
    schedule = Column(String(20), nullable=False, default='5m')  # '5m', '15m', '30m', '1h', 'daily'
    agent_ids = Column(Text)  # JSON
    config = Column(Text)  # JSON
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class KlineCache(Base):
    """K线数据缓存表"""
    __tablename__ = 'kline_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    cached_at = Column(DateTime, default=datetime.now)

class PaperAccount(Base):
    """模拟盘账户表"""
    __tablename__ = 'paper_accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    strategy_id = Column(Integer, nullable=True)
    initial_capital = Column(Float, default=100000)
    cash_balance = Column(Float, default=100000)
    total_market_value = Column(Float, default=0)
    total_profit_pct = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    win_rate = Column(Float, default=0)
    snapshot_interval = Column(Integer, default=60)  # 快照间隔(分钟)
    include_etf_replacement = Column(Boolean, default=False)
    auto_trade = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PaperPosition(Base):
    """模拟盘持仓表"""
    __tablename__ = 'paper_positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    code = Column(String(6), nullable=False)
    name = Column(String(50))
    shares = Column(Integer, default=0)
    avg_cost = Column(Float, default=0)
    current_price = Column(Float, default=0)
    market_value = Column(Float, default=0)
    profit_pct = Column(Float, default=0)
    today_profit_pct = Column(Float, default=0)
    etf_replaced = Column(Boolean, default=False)
    original_code = Column(String(6))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PaperOrder(Base):
    """模拟盘订单表"""
    __tablename__ = 'paper_orders'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    code = Column(String(6), nullable=False)
    name = Column(String(50))
    direction = Column(String(4), nullable=False)  # 'buy' or 'sell'
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    tax = Column(Float, default=0)
    order_type = Column(String(10), default='market')  # 'market', 'limit'
    strategy_run_id = Column(String(64))
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class PaperSnapshot(Base):
    """模拟盘快照表"""
    __tablename__ = 'paper_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    snapshot_time = Column(DateTime, default=datetime.now)
    total_value = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    daily_pnl = Column(Float, default=0)
    daily_pnl_pct = Column(Float, default=0)

class PaperAutoRule(Base):
    """模拟盘自动交易规则表"""
    __tablename__ = 'paper_auto_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    code = Column(String(6), nullable=False)
    name = Column(String(50))
    enabled = Column(Boolean, default=True)
    buy_enabled = Column(Boolean, default=False)
    buy_price_low = Column(Float)
    buy_price_high = Column(Float)
    buy_quantity = Column(Integer)
    buy_strategy = Column(String(20))
    sell_enabled = Column(Boolean, default=False)
    sell_target_price = Column(Float)
    sell_stop_loss = Column(Float)
    max_position = Column(Integer)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class EtfReplacementMap(Base):
    """ETF替代映射表"""
    __tablename__ = 'etf_replacement_map'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_code = Column(String(6), nullable=False)
    original_name = Column(String(50))
    etf_code = Column(String(6), nullable=False)
    etf_name = Column(String(50))
    ratio = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.now)

class PaperPlan(Base):
    """模拟盘买卖计划表"""
    __tablename__ = 'paper_plans'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    direction = Column(String(4), nullable=False)  # 'buy' or 'sell'
    target_price = Column(Float, nullable=False)
    quantity = Column(Integer)
    reason = Column(Text)
    status = Column(String(10), default='pending')  # pending/partial/executed/cancelled
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class BacktestData(Base):
    """回测数据缓存表"""
    __tablename__ = 'backtest_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    change_pct = Column(Float)
    turnover = Column(Float)
    source = Column(String(10))
    cached_at = Column(DateTime, default=datetime.now)

class BacktestStockMeta(Base):
    """回测数据股票元信息——记录缓存了哪些股票、时间范围"""
    __tablename__ = 'backtest_stock_meta'

    code = Column(String(10), primary_key=True)  # 股票代码
    name = Column(String(50))  # 股票名称
    sector = Column(String(100))  # 所属板块（逗号分隔）
    data_start = Column(String(10))  # 缓存数据起始日期
    data_end = Column(String(10))  # 缓存数据截至日期
    total_days = Column(Integer, default=0)  # 缓存天数
    last_updated = Column(DateTime, default=datetime.now)  # 最后更新时间

class TaskLog(Base):
    """任务执行日志表"""
    __tablename__ = 'task_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=False)
    task_name = Column(String(100))
    task_type = Column(String(20))
    status = Column(String(20))  # success/failed/timeout
    result = Column(Text)
    triggered_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

class Recommendation(Base):
    """推荐结果表"""
    __tablename__ = 'recommendations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rec_type = Column(String(10), nullable=False)  # 'daily'/'strategy'
    strategy = Column(String(20), nullable=False)
    code = Column(String(6), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    change_pct = Column(Float)
    turnover = Column(Float)
    score = Column(Float)
    reason = Column(Text)
    rank = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)


class StockFinancial(Base):
    """基本面财务数据表"""
    __tablename__ = 'stock_financials'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    report_date = Column(String(10), nullable=False)
    report_type = Column(String(10))
    revenue = Column(Float)
    net_profit = Column(Float)
    gross_profit = Column(Float)
    eps = Column(Float)
    roe = Column(Float)
    gross_margin = Column(Float)
    net_margin = Column(Float)
    pe_ttm = Column(Float)
    pb = Column(Float)
    pe_industry = Column(Float)
    pb_industry = Column(Float)
    revenue_yoy = Column(Float)
    profit_yoy = Column(Float)
    total_assets = Column(Float)
    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════════════════════════
# 新增: 风险管理模型
# ═══════════════════════════════════════════════════════════════

class RiskReport(Base):
    """风险报告缓存表"""
    __tablename__ = 'risk_reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    report_json = Column(Text)  # JSON: 完整风险报告
    var_95 = Column(Float)  # VaR 95%
    cvar_95 = Column(Float)  # CVaR 95%
    max_dd = Column(Float)  # 最大回撤(%)
    sharpe = Column(Float)  # 夏普比率
    kelly_pct = Column(Float)  # 凯利建议仓位(%)
    stop_loss = Column(Float)  # 建议止损价
    risk_grade = Column(String(20))  # 风险等级
    created_at = Column(DateTime, default=datetime.now)

class PortfolioConfig(Base):
    """组合配置记录表"""
    __tablename__ = 'portfolio_configs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 配置名称
    config_json = Column(Text)  # JSON: 完整配置
    risk_profile = Column(String(20), default='moderate')  # conservative/moderate/aggressive
    total_capital = Column(Float, default=100000)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TradeJournal(Base):
    """中长线交易日志表"""
    __tablename__ = 'trade_journal'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    direction = Column(String(10), default='long')  # long/short
    entry_date = Column(String(10))
    entry_price = Column(Float)
    shares = Column(Integer)
    stop_loss = Column(Float)
    target_price = Column(Float)
    exit_date = Column(String(10))
    exit_price = Column(Float)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    reason_entry = Column(Text)
    reason_exit = Column(Text)
    notes = Column(Text)
    tags = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class MarketAlertLog(Base):
    """大盘预警日志 — 熊市确认用 (OpenSpec: market-trend-monitor)"""
    __tablename__ = 'market_alert_log'

    date = Column(String(10), primary_key=True)       # YYYY-MM-DD
    level = Column(String(20), nullable=False)          # normal/watch/alert/danger
    score = Column(Integer, default=0)
    signals = Column(Text)                              # JSON array of signal strings
    created_at = Column(DateTime, default=datetime.now)


# 数据库初始化
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
