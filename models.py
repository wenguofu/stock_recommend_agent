#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库模型定义"""

import logging
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime, Float
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# 自动加载 .env 文件
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(_env_path)
except ImportError:
    pass

Base = declarative_base()

# ═══════════════════════════════════════════════════════════════
# 数据库引擎工厂 — 仅支持 MySQL
# ═══════════════════════════════════════════════════════════════

def get_database_url():
    """获取 MySQL DSN，未设置或非 MySQL 时 fail-fast (RuntimeError)。"""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL 未设置。本项目仅支持 MySQL，请设置环境变量，例如:\n"
            "  export DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/stock_trading'"
        )
    if not url.startswith("mysql"):
        raise RuntimeError(
            f"DATABASE_URL 必须是 MySQL DSN (以 mysql:// 开头)，当前: {url[:40]}..."
        )
    return url


def get_engine(database_url=None):
    """创建 MySQL 引擎 (本项目唯一支持的 DB 引擎)。

    Args:
        database_url: MySQL DSN，为 None 时从环境变量读取

    Returns:
        sqlalchemy.engine.Engine
    """
    url = database_url or get_database_url()  # 内部已校验 MySQL

    return create_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,  # MySQL 默认 8h wait_timeout，一小时回收避免断开
    )


# 全局引擎和会话工厂
engine = get_engine()
SessionLocal = sessionmaker(bind=engine)


def reset_engine(database_url=None):
    """重新初始化引擎和会话工厂（用于运行时切换数据库）

    Args:
        database_url: 新的数据库连接 URL
    """
    global engine, SessionLocal
    old_engine = engine
    engine = get_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    # 关闭旧引擎的所有连接
    old_engine.dispose()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    code = Column(String(500), nullable=False)  # 单股代码或多股逗号分隔列表(最长~202字符)
    name = Column(Text, nullable=False)  # 任务名称，多股时可能很长
    status = Column(String(20), default='queued')  # queued/running/completed/failed/canceled
    progress = Column(Integer, default=0)
    agent_ids = Column(Text)  # JSON
    steps = Column(Text(length=16777215))  # MEDIUMTEXT: 可能有 ~300KB 的大数据
    progress_detail = Column(Text)  # JSON: [{phase, agent_name, round, detail}]
    report_md = Column(Text(length=16777215))  # MEDIUMTEXT: 分析报告可能很大
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
    client_order_id = Column(String(64), index=True)  # 客户端幂等键(防双提交)
    created_at = Column(DateTime, default=datetime.now, index=True)

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

class SchedulerRunLog(Base):
    """内置调度器执行日志表"""
    __tablename__ = 'scheduler_run_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False, index=True)
    task_type = Column(String(20))
    schedule = Column(String(50))
    status = Column(String(20), nullable=False)
    output = Column(Text)
    error = Column(Text)
    started_at = Column(DateTime, nullable=False, index=True)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    trigger_source = Column(String(20))

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
    rank = Column('rank', Integer)  # 'rank' 是 MySQL 保留字，需要显式指定列名
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


class LLMUsage(Base):
    """LLM 调用 token 消耗记录 — Sprint3 修复 ai_service 不记账"""
    __tablename__ = 'llm_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False, index=True)
    model = Column(String(64), nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)               # 估算成本
    job_id = Column(String(64), index=True)            # 可选: 关联辩论 job
    called_at = Column(DateTime, default=datetime.now, index=True)


class ModelVersion(Base):
    """Sprint4: 模型注册表 (Model Registry)
    - 记录每个训练产出的版本: sha256/mtime/metrics/dataset_hash
    - 标记 active 版本供 ml_predictor.load() 选择
    - A/B 影子模式: 第二个 active_shadow 字段
    """
    __tablename__ = 'model_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(64), nullable=False, index=True)  # e.g. "short_term", "mid_term", "regime"
    version = Column(String(32), nullable=False)               # e.g. "v20250607-001"
    file_path = Column(String(255), nullable=False)            # checkpoint path
    sha256 = Column(String(64), nullable=False, index=True)
    file_size = Column(Integer, default=0)
    num_features = Column(Integer)
    metrics_json = Column(Text)                                # {"acc":0.6, "ic":0.04, ...}
    dataset_hash = Column(String(64))                          # 训练集指纹
    is_active = Column(Boolean, default=False, index=True)     # 当前生产版本
    is_shadow = Column(Boolean, default=False, index=True)     # 影子版本(只记录不决策)
    created_at = Column(DateTime, default=datetime.now, index=True)
    promoted_at = Column(DateTime)
    notes = Column(Text)



# ═══════════════════════════════════════════════════════════════
# 紫苏叶理论 (Shiso Leaf Theory) — 产业链 + 瓶颈点
# ═══════════════════════════════════════════════════════════════

class ShisoChain(Base):
    """产业链定义表 — 自上而下的反推路径 (Toro → Chokepoint)

    紫苏叶理论核心：从最终需求逐层反推物理瓶颈。
    每条 chain 是一条"金枪鱼→紫苏叶"的产业链路径。
    """
    __tablename__ = 'shiso_chains'

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_name = Column(String(50), nullable=False, unique=True, index=True)  # 'AI光通信'
    sector_tag = Column(String(50))  # 板块归类, 如 '通信'
    customer = Column(String(100))  # 终端客户, 如 'SpaceX' / 'NVIDIA' / 'Apple'. 区分供应链映射vs行业主题
    toro_layer = Column(String(200))  # 金枪鱼层描述, 如 'GPU/光模块'
    chokepoint_layer = Column(String(200))  # 瓶颈层描述, 如 'InP衬底/DFB激光器'
    top_down_path = Column(Text)  # 完整反推路径(自由文本), 例: 'AI→GPU→光模块→InP衬底'
    enabled = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ShisoChokepoint(Base):
    """紫苏叶候选标的表 — 卡位公司 + 手工标注属性

    由产业链 → 映射到的 A 股具体上市公司。
    行业地位/垄断度/不可替代性等需要人工/研究维护的字段都放这里。
    """
    __tablename__ = 'shiso_chokepoints'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)  # 股票代码
    name = Column(String(50))
    chain_name = Column(String(50), nullable=False, index=True)  # 所属产业链
    layer = Column(String(100))  # 卡位层级, 如 'InP衬底' / 'DFB激光器'
    monopoly_score = Column(Float, default=50.0)  # 行业地位 0-100, 越高越垄断
    player_count = Column(Integer, default=3)  # 全球/国内可比玩家数 (1-2 = 重点)
    moat_note = Column(String(500))  # 护城河简述
    extra_score = Column(Float, default=0.0)  # 额外加分(产业链卡位独特性)
    supply_chain_verified = Column(Boolean, default=False)  # 是否经核实的供应链环节(非行业映射)
    enabled = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ShisoPick(Base):
    """紫苏叶选股结果表 — 每日跑批的产出

    字段含义与 Recommendation 类似, 但 zisuye 独立表, 不耦合。
    """
    __tablename__ = 'shiso_picks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pick_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    rank = Column(Integer)  # 排序
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))
    price = Column(Float)
    change_pct = Column(Float)
    turnover = Column(Float)  # 换手率%
    amount = Column(Float)  # 成交额
    market_cap = Column(Float)  # 总市值(亿)
    chain_name = Column(String(50))  # 所属产业链
    layer = Column(String(100))  # 卡位层级
    # 五问漏斗分项得分
    industry_score = Column(Float)   # 行业地位 0-100
    elasticity_score = Column(Float)  # 财务弹性 0-100
    mispricing_score = Column(Float)  # 定价错误 0-100
    extra_score = Column(Float)      # 额外加分
    total_score = Column(Float)       # 加权总分
    # 风控参数 (默认: -5%止损, +50%减仓1/3, 市值≤200亿, 成交≥5000万)
    stop_loss_pct = Column(Float, default=-5.0)
    trim_pct = Column(Float, default=50.0)  # +50% 触发减仓
    trim_size = Column(Float, default=lambda: 1.0/3)  # 减仓 1/3 (lambda 避免类加载时固化)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════════════════════════
# 初始化：创建所有表
# ═══════════════════════════════════════════════════════════════
Base.metadata.create_all(engine)


def ensure_schema():
    """
    启动时检查并补充缺失的列(轻量级 alembic 替代,生产 MySQL 必备)
    Sprint3: 新增 paper_orders.client_order_id + llm_usage 表
    """
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    try:
        cols = {c["name"] for c in inspector.get_columns("paper_orders")}
        if "client_order_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE paper_orders ADD COLUMN client_order_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX ix_paper_orders_client_order_id ON paper_orders (client_order_id)"))
            logger.info("[Schema] 已补 paper_orders.client_order_id 列")
    except Exception as e:
        logger.warning(f"[Schema] 检查 paper_orders 失败: {e}")
    try:
        cols = {c["name"] for c in inspector.get_columns("paper_orders")}
        if "created_at" in cols:
            # 检查是否有索引
            idx = {i["name"] for i in inspector.get_indexes("paper_orders")}
            if "ix_paper_orders_created_at" not in idx:
                with engine.begin() as conn:
                    conn.execute(text("CREATE INDEX ix_paper_orders_created_at ON paper_orders (created_at)"))
    except Exception:
        pass


ensure_schema()
