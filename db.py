#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库操作函数"""

from models import SessionLocal, Watchlist, Config, Agent, AnalysisCache, DebateJob, Strategy, PaperAccount, PaperPosition, PaperOrder, PaperSnapshot, EtfReplacementMap, PaperAutoRule, Recommendation
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json

# ==================== 自选股操作 ====================

def get_watchlist(db: Session):
    """获取所有自选股"""
    return db.query(Watchlist).order_by(Watchlist.sort_order, Watchlist.added_at).all()

def add_to_watchlist(db: Session, code: str, name: str = None, cost_price: float = None, shares: int = None):
    """添加自选股"""
    existing = db.query(Watchlist).filter(Watchlist.code == code).first()
    if existing:
        # 更新名称和持仓信息
        if name:
            existing.name = name
        if cost_price is not None:
            existing.cost_price = cost_price
        if shares is not None:
            existing.shares = shares
        db.commit()
        db.refresh(existing)
        return existing
    
    watchlist_item = Watchlist(code=code, name=name, cost_price=cost_price, shares=shares)
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)
    return watchlist_item

def remove_from_watchlist(db: Session, code: str):
    """移除自选股"""
    item = db.query(Watchlist).filter(Watchlist.code == code).first()
    if item:
        db.delete(item)
        db.commit()
        return True
    return False

def update_watchlist_position(db: Session, code: str, cost_price: float = None, shares: int = None):
    """更新自选股持仓信息"""
    item = db.query(Watchlist).filter(Watchlist.code == code).first()
    if not item:
        return None
    if cost_price is not None:
        item.cost_price = cost_price
    if shares is not None:
        item.shares = shares
    db.commit()
    db.refresh(item)
    return item

def update_watchlist_order(db: Session, orders: list):
    """更新自选股排序"""
    for code, sort_order in orders:
        item = db.query(Watchlist).filter(Watchlist.code == code).first()
        if item:
            item.sort_order = sort_order
    db.commit()

# ==================== 配置操作 ====================

def get_config(db: Session, key: str, default=None):
    """获取配置"""
    config = db.query(Config).filter(Config.key == key).first()
    return config.value if config else default

def set_config(db: Session, key: str, value: str):
    """设置配置"""
    config = db.query(Config).filter(Config.key == key).first()
    if config:
        config.value = value
        config.updated_at = datetime.now()
    else:
        config = Config(key=key, value=value)
        db.add(config)
    db.commit()
    return config

def get_all_configs(db: Session):
    """获取所有配置"""
    configs = db.query(Config).all()
    return {c.key: c.value for c in configs}

# ==================== Agent操作 ====================

def get_agents(db: Session, enabled_only: bool = False):
    """获取所有Agent"""
    query = db.query(Agent)
    if enabled_only:
        query = query.filter(Agent.enabled == True)
    return query.order_by(Agent.sort_order, Agent.created_at).all()

def get_agent(db: Session, agent_id: int):
    """获取单个Agent"""
    return db.query(Agent).filter(Agent.id == agent_id).first()

def create_agent(db: Session, name: str, type: str, prompt: str, 
                 ai_provider: str = None, model: str = None, enabled: bool = True, sort_order: int = 0):
    """创建Agent"""
    agent = Agent(
        name=name,
        type=type,
        prompt=prompt,
        ai_provider=ai_provider,
        model=model,
        enabled=enabled,
        sort_order=sort_order
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

def update_agent(db: Session, agent_id: int, **kwargs):
    """更新Agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return None
    
    for key, value in kwargs.items():
        if hasattr(agent, key):
            setattr(agent, key, value)
    
    db.commit()
    db.refresh(agent)
    return agent

def delete_agent(db: Session, agent_id: int):
    """删除Agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent:
        db.delete(agent)
        db.commit()
        return True
    return False

# ==================== 缓存操作 ====================

def get_cached_analysis(db: Session, code: str, analysis_type: str, max_age_minutes: int = 30):
    """获取缓存的分析结果"""
    cache = db.query(AnalysisCache).filter(
        AnalysisCache.code == code,
        AnalysisCache.analysis_type == analysis_type
    ).first()
    
    if cache:
        age = datetime.now() - cache.created_at
        if age < timedelta(minutes=max_age_minutes):
            return json.loads(cache.data)
    
    return None

def save_analysis_cache(db: Session, code: str, analysis_type: str, data: dict):
    """保存分析结果到缓存"""
    # 删除旧缓存
    db.query(AnalysisCache).filter(
        AnalysisCache.code == code,
        AnalysisCache.analysis_type == analysis_type
    ).delete()
    
    # 添加新缓存
    cache = AnalysisCache(
        code=code,
        analysis_type=analysis_type,
        data=json.dumps(data, ensure_ascii=False)
    )
    db.add(cache)
    db.commit()

# ==================== 策略操作 ====================

def get_strategies(db: Session, category: str = None, enabled_only: bool = False):
    """获取所有策略"""
    query = db.query(Strategy)
    if category:
        query = query.filter(Strategy.category == category)
    if enabled_only:
        query = query.filter(Strategy.enabled == True)
    return query.order_by(Strategy.sort_order, Strategy.created_at.desc()).all()

def get_strategy(db: Session, strategy_id: int):
    """获取单个策略"""
    return db.query(Strategy).filter(Strategy.id == strategy_id).first()

def create_strategy(db: Session, name: str, description: str = None, category: str = None,
                    doc_md: str = None, agent_configs: str = None, sort_order: int = 0):
    """创建策略"""
    strategy = Strategy(
        name=name, description=description, category=category,
        doc_md=doc_md, agent_configs=agent_configs,
        enabled=True, sort_order=sort_order
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy

def update_strategy(db: Session, strategy_id: int, **kwargs):
    """更新策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return None
    for key, value in kwargs.items():
        if hasattr(strategy, key):
            setattr(strategy, key, value)
    db.commit()
    db.refresh(strategy)
    return strategy

def delete_strategy(db: Session, strategy_id: int):
    """删除策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if strategy:
        db.delete(strategy)
        db.commit()
        return True
    return False

def apply_strategy_to_agents(db: Session, strategy_id: int):
    """将策略的Agent配置应用到当前Agent列表（创建/更新Agent）"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy or not strategy.agent_configs:
        return None
    
    import json
    configs = json.loads(strategy.agent_configs)
    results = []
    
    existing_names = {a.name: a for a in db.query(Agent).all()}
    
    for cfg in configs:
        name = cfg.get('name', '')
        if name in existing_names:
            # 更新已有Agent
            agent = existing_names[name]
            agent.prompt = cfg.get('prompt', agent.prompt)
            agent.type = cfg.get('type', agent.type)
            agent.sort_order = cfg.get('sort_order', agent.sort_order)
            results.append({'action': 'updated', 'id': agent.id, 'name': name})
        else:
            # 创建新Agent
            agent = Agent(
                name=name,
                type=cfg.get('type', 'default'),
                prompt=cfg.get('prompt', ''),
                sort_order=cfg.get('sort_order', 0),
                enabled=True
            )
            db.add(agent)
            db.flush()
            results.append({'action': 'created', 'id': agent.id, 'name': name})
    
    db.commit()
    return results

# ==================== 辩论任务操作 ====================

def create_debate_job(db: Session, job_id: str, code: str, name: str, agent_ids: list,
                     analysis_rounds: int, debate_rounds: int, meta: dict = None):
    """创建辩论任务"""
    payload = {
        'agent_ids': agent_ids,
        'analysis_rounds': analysis_rounds,
        'debate_rounds': debate_rounds,
        'meta': meta or {}
    }
    job = DebateJob(
        job_id=job_id,
        code=code,
        name=name,
        status='queued',
        progress=0,
        agent_ids=json.dumps(payload, ensure_ascii=False),
        steps=json.dumps([], ensure_ascii=False),
        progress_detail=json.dumps([], ensure_ascii=False),
        report_md='',
        error=None,
        canceled=False
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def update_debate_job(db: Session, job_id: str, **kwargs):
    """更新辩论任务"""
    job = db.query(DebateJob).filter(DebateJob.job_id == job_id).first()
    if not job:
        return None
    for key, value in kwargs.items():
        if hasattr(job, key):
            setattr(job, key, value)
    job.updated_at = datetime.now()
    db.commit()
    db.refresh(job)
    return job

def get_debate_job(db: Session, job_id: str):
    """获取辩论任务"""
    return db.query(DebateJob).filter(DebateJob.job_id == job_id).first()

def list_debate_jobs(db: Session, status: str = None, limit: int = 50):
    """列出辩论任务"""
    query = db.query(DebateJob)
    if status == 'active':
        query = query.filter(DebateJob.status.in_(['queued', 'running']))
    elif status:
        query = query.filter(DebateJob.status == status)
    return query.order_by(DebateJob.updated_at.desc()).limit(limit).all()

def cancel_debate_job(db: Session, job_id: str):
    """终止辩论任务"""
    job = db.query(DebateJob).filter(DebateJob.job_id == job_id).first()
    if not job:
        return None
    job.canceled = True
    if job.status in ['queued', 'running']:
        job.status = 'canceled'
    job.updated_at = datetime.now()
    db.commit()
    db.refresh(job)
    return job

def delete_debate_job(db: Session, job_id: str):
    """删除辩论任务"""
    job = db.query(DebateJob).filter(DebateJob.job_id == job_id).first()
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True

# ==================== 模拟盘账户操作 ====================

def get_paper_accounts(db: Session, enabled_only: bool = False):
    """获取所有模拟盘账户"""
    query = db.query(PaperAccount)
    if enabled_only:
        query = query.filter(PaperAccount.enabled == True)
    return query.order_by(PaperAccount.created_at.desc()).all()

def get_paper_account(db: Session, account_id: int):
    """获取单个模拟盘账户"""
    return db.query(PaperAccount).filter(PaperAccount.id == account_id).first()

def create_paper_account(db: Session, name: str, initial_capital: float = 1000000,
                        strategy_id: int = None, snapshot_interval: int = 60,
                        include_etf_replacement: bool = True, auto_trade: bool = False):
    """创建模拟盘账户"""
    account = PaperAccount(
        name=name, initial_capital=initial_capital, cash_balance=initial_capital,
        strategy_id=strategy_id, snapshot_interval=snapshot_interval,
        include_etf_replacement=include_etf_replacement, enabled=True
    )
    # 支持auto_trade参数
    if "auto_trade" in kwargs:
        account.auto_trade = kwargs["auto_trade"]
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

def update_paper_account(db: Session, account_id: int, **kwargs):
    """更新模拟盘账户"""
    account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
    if not account:
        return None
    allowed_fields = {"name", "snapshot_interval", "include_etf_replacement", "enabled", "auto_trade"}
    for key, value in kwargs.items():
        if key in allowed_fields and hasattr(account, key):
            setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account

def delete_paper_account(db: Session, account_id: int):
    """删除模拟盘账户（级联删除持仓/订单/快照）"""
    account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
    if not account:
        return False
    # 级联删除
    db.query(PaperPosition).filter(PaperPosition.account_id == account_id).delete()
    db.query(PaperOrder).filter(PaperOrder.account_id == account_id).delete()
    db.query(PaperSnapshot).filter(PaperSnapshot.account_id == account_id).delete()
    db.delete(account)
    db.commit()
    return True

# ==================== 模拟盘持仓操作 ====================

def get_paper_positions(db: Session, account_id: int):
    """获取指定模拟盘的所有持仓"""
    return db.query(PaperPosition).filter(
        PaperPosition.account_id == account_id
    ).order_by(PaperPosition.updated_at.desc()).all()

# ==================== 模拟盘订单操作 ====================

def get_paper_orders(db: Session, account_id: int, page: int = 1, per_page: int = 20):
    """获取指定模拟盘的订单列表（分页）"""
    query = db.query(PaperOrder).filter(
        PaperOrder.account_id == account_id
    ).order_by(PaperOrder.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page}

# ==================== 模拟盘快照操作 ====================

def get_paper_snapshots(db: Session, account_id: int, limit: int = 200):
    """获取指定模拟盘的快照列表"""
    return db.query(PaperSnapshot).filter(
        PaperSnapshot.account_id == account_id
    ).order_by(PaperSnapshot.snapshot_time.desc()).limit(limit).all()

# ==================== ETF映射操作 ====================

def get_etf_maps(db: Session):
    """获取所有ETF映射"""
    return db.query(EtfReplacementMap).order_by(EtfReplacementMap.original_code).all()

def get_etf_map(db: Session, map_id: int):
    """获取单个ETF映射"""
    return db.query(EtfReplacementMap).filter(EtfReplacementMap.id == map_id).first()

def create_etf_map(db: Session, original_code: str, original_name: str,
                   etf_code: str, etf_name: str, ratio: float = 1.0):
    """创建ETF映射"""
    mapping = EtfReplacementMap(
        original_code=original_code, original_name=original_name,
        etf_code=etf_code, etf_name=etf_name, ratio=ratio
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping

def delete_etf_map(db: Session, map_id: int):
    """删除ETF映射"""
    mapping = db.query(EtfReplacementMap).filter(EtfReplacementMap.id == map_id).first()
    if not mapping:
        return False
    db.delete(mapping)
    db.commit()
    return True

def search_etf_replacement(db: Session, code: str):
    """搜索指定股票代码的ETF替代"""
    # 先查已有映射
    mapping = db.query(EtfReplacementMap).filter(
        EtfReplacementMap.original_code == code
    ).first()
    if mapping:
        return mapping
    
    # 688开头但没有映射的，推荐默认值
    if code.startswith("688"):
        return {
            "original_code": code,
            "etf_code": "588000",
            "etf_name": "科创50ETF",
            "ratio": 1.0
        }

    return None

# ==================== 自动跟踪规则操作 ====================

def get_auto_rules(db: Session, account_id: int = None, enabled_only: bool = False):
    """获取自动跟踪规则"""
    query = db.query(PaperAutoRule)
    if account_id:
        query = query.filter(PaperAutoRule.account_id == account_id)
    if enabled_only:
        query = query.filter(PaperAutoRule.enabled == True)
    return query.order_by(PaperAutoRule.created_at.desc()).all()

def get_auto_rule(db: Session, rule_id: int):
    """获取单个规则"""
    return db.query(PaperAutoRule).filter(PaperAutoRule.id == rule_id).first()

def create_auto_rule(db: Session, account_id: int, code: str, name: str = None,
                     buy_price_low: float = None, buy_price_high: float = None,
                     buy_quantity: int = 100, buy_enabled: bool = True,
                     sell_target_price: float = None, sell_stop_loss: float = None,
                     sell_enabled: bool = True, max_position: int = 0, note: str = None):
    """创建自动跟踪规则"""
    rule = PaperAutoRule(
        account_id=account_id, code=code, name=name,
        buy_price_low=buy_price_low, buy_price_high=buy_price_high,
        buy_quantity=buy_quantity, buy_enabled=buy_enabled,
        sell_target_price=sell_target_price, sell_stop_loss=sell_stop_loss,
        sell_enabled=sell_enabled, max_position=max_position,
        note=note, enabled=True
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

def update_auto_rule(db: Session, rule_id: int, **kwargs):
    """更新自动跟踪规则"""
    rule = db.query(PaperAutoRule).filter(PaperAutoRule.id == rule_id).first()
    if not rule:
        return None
    allowed = {"enabled", "buy_enabled", "buy_price_low", "buy_price_high",
               "buy_quantity", "sell_enabled", "sell_target_price",
               "sell_stop_loss", "max_position", "note", "name"}
    for k, v in kwargs.items():
        if k in allowed and hasattr(rule, k):
            setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule

def delete_auto_rule(db: Session, rule_id: int):
    """删除自动跟踪规则"""
    rule = db.query(PaperAutoRule).filter(PaperAutoRule.id == rule_id).first()
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True

# ==================== 股票推荐操作 ====================

def save_recommendations(db: Session, rec_type: str, strategy: str, picks: list):
    """保存批量推荐结果（先清理同类型旧数据）"""
    # 先删除该类型+策略的所有旧推荐
    db.query(Recommendation).filter(
        Recommendation.rec_type == rec_type,
        Recommendation.strategy == strategy
    ).delete()
    db.flush()
    
    created = []
    for p in picks:
        rec = Recommendation(
            rec_type=rec_type, strategy=strategy,
            code=p['code'], name=p.get('name', ''),
            price=p.get('price'), change_pct=p.get('change_pct'),
            turnover=p.get('turnover'), score=p.get('score'),
            reason=p.get('reason'), rank=p.get('rank'),
        )
        db.add(rec)
        db.flush()
        created.append(rec.id)
    db.commit()
    return created

def get_recommendations(db: Session, rec_type: str = None, strategy: str = None,
                        limit: int = 50, offset: int = 0):
    """获取推荐列表"""
    query = db.query(Recommendation)
    if rec_type:
        query = query.filter(Recommendation.rec_type == rec_type)
    if strategy:
        query = query.filter(Recommendation.strategy == strategy)
    total = query.count()
    items = query.order_by(Recommendation.created_at.desc()).limit(limit).offset(offset).all()
    return total, items

def get_latest_recommendations(db: Session, rec_type: str = 'daily', limit_per_strategy: int = 10):
    """获取每种策略最新的推荐"""
    import json
    from sqlalchemy import func
    
    results = {}
    for s in ['youzi', 'lianghua', 'jichang']:
        items = db.query(Recommendation).filter(
            Recommendation.rec_type == rec_type,
            Recommendation.strategy == s,
            Recommendation.created_at >= func.date('now', '-7 days')
        ).order_by(Recommendation.rank.asc()).limit(limit_per_strategy).all()
        if items:
            results[s] = items
    return results


# ═══════════════════════════════════════════
# 买卖计划 (PaperPlan)
# ═══════════════════════════════════════════

def get_paper_plans(db: Session, account_id: int, code: str = None, status: str = None):
    """获取买卖计划"""
    query = db.query(PaperPlan).filter(PaperPlan.account_id == account_id)
    if code:
        query = query.filter(PaperPlan.code == code)
    if status:
        query = query.filter(PaperPlan.status == status)
    return query.order_by(PaperPlan.created_at.desc()).all()

def create_paper_plan(db: Session, account_id: int, code: str, name: str = None,
                      direction: str = 'buy', target_price: float = 0,
                      quantity: int = 0, reason: str = None):
    """创建买卖计划"""
    plan = PaperPlan(
        account_id=account_id, code=code, name=name,
        direction=direction, target_price=target_price,
        quantity=quantity, reason=reason, status='pending'
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

def update_plan_status(db: Session, plan_id: int, status: str):
    """更新计划状态"""
    plan = db.query(PaperPlan).filter(PaperPlan.id == plan_id).first()
    if plan:
        plan.status = status
        db.commit()
        db.refresh(plan)
    return plan


# ==================== 财务数据操作 (StockFinancial) ====================

def save_stock_financial(db: Session, data: dict):
    """保存或更新财务数据

    Args:
        db: 数据库会话
        data: 财务数据字典, 需包含 code 和 report_date

    Returns:
        StockFinancial 对象
    """
    from models import StockFinancial

    code = data.get('code', '')
    report_date = data.get('report_date', '')

    if not code or not report_date:
        return None

    # 查找是否已存在条记录
    existing = db.query(StockFinancial).filter(
        StockFinancial.code == code,
        StockFinancial.report_date == report_date
    ).first()

    if existing:
        # 更新已有记录
        for field in ['report_type', 'revenue', 'net_profit', 'gross_profit',
                       'eps', 'roe', 'gross_margin', 'net_margin',
                       'pe_ttm', 'pb', 'pe_industry', 'pb_industry',
                       'revenue_yoy', 'profit_yoy', 'total_assets']:
            if field in data and data[field] is not None:
                setattr(existing, field, data[field])
        db.commit()
        db.refresh(existing)
        return existing

    # 创建新纪录
    fin = StockFinancial(
        code=code,
        report_date=report_date,
        report_type=data.get('report_type', '年报'),
        revenue=data.get('revenue'),
        net_profit=data.get('net_profit'),
        gross_profit=data.get('gross_profit'),
        eps=data.get('eps'),
        roe=data.get('roe'),
        gross_margin=data.get('gross_margin'),
        net_margin=data.get('net_margin'),
        pe_ttm=data.get('pe_ttm'),
        pb=data.get('pb'),
        pe_industry=data.get('pe_industry'),
        pb_industry=data.get('pb_industry'),
        revenue_yoy=data.get('revenue_yoy'),
        profit_yoy=data.get('profit_yoy'),
        total_assets=data.get('total_assets'),
    )
    db.add(fin)
    db.commit()
    db.refresh(fin)
    return fin


def get_latest_financial(db: Session, code: str):
    """获取指定股票的最新财务数据

    Args:
        db: 数据库会话
        code: 股票代码

    Returns:
        dict 或 None
    """
    from models import StockFinancial

    row = db.query(StockFinancial).filter(
        StockFinancial.code == code
    ).order_by(StockFinancial.report_date.desc()).first()

    if not row:
        return None

    return {
        'code': row.code,
        'report_date': row.report_date,
        'report_type': row.report_type,
        'revenue': row.revenue,
        'net_profit': row.net_profit,
        'gross_profit': row.gross_profit,
        'eps': row.eps,
        'roe': row.roe,
        'gross_margin': row.gross_margin,
        'net_margin': row.net_margin,
        'pe_ttm': row.pe_ttm,
        'pb': row.pb,
        'pe_industry': row.pe_industry,
        'pb_industry': row.pb_industry,
        'revenue_yoy': row.revenue_yoy,
        'profit_yoy': row.profit_yoy,
        'total_assets': row.total_assets,
    }


def get_stock_financials(db: Session, code: str, limit: int = 4):
    """获取指定股票的多期财务数据

    Args:
        db: 数据库会话
        code: 股票代码
        limit: 最多返回条数 (默认4)

    Returns:
        list[dict]
    """
    from models import StockFinancial

    rows = db.query(StockFinancial).filter(
        StockFinancial.code == code
    ).order_by(StockFinancial.report_date.desc()).limit(limit).all()

    results = []
    for row in rows:
        results.append({
            'code': row.code,
            'report_date': row.report_date,
            'report_type': row.report_type,
            'revenue': row.revenue,
            'net_profit': row.net_profit,
            'gross_profit': row.gross_profit,
            'eps': row.eps,
            'roe': row.roe,
            'gross_margin': row.gross_margin,
            'net_margin': row.net_margin,
            'pe_ttm': row.pe_ttm,
            'pb': row.pb,
            'pe_industry': row.pe_industry,
            'pb_industry': row.pb_industry,
            'revenue_yoy': row.revenue_yoy,
            'profit_yoy': row.profit_yoy,
            'total_assets': row.total_assets,
        })
    return results


# ==================== K线缓存操作 (KlineCache) ====================

def save_kline_cache_batch(db: Session, code: str, records: list):
    """批量保存K线数据到本地缓存(去重)

    Args:
        db: 数据库会话
        code: 股票代码
        records: K线记录列表, 每条包含 date/open/high/low/close/volume/amount

    Returns:
        int: 实际插入的记录数
    """
    from models import KlineCache

    if not records:
        return 0

    # 获取已有日期集合,避免重复插入
    dates = [r.get('date', '') for r in records if r.get('date')]
    existing_dates = set()
    if dates:
        existing = db.query(KlineCache.date).filter(
            KlineCache.code == code,
            KlineCache.date.in_(dates)
        ).all()
        existing_dates = {e[0] for e in existing}

    inserted = 0
    for rec in records:
        rec_date = rec.get('date', '')
        if not rec_date or rec_date in existing_dates:
            continue

        kline = KlineCache(
            code=code,
            date=rec_date,
            open=rec.get('open'),
            high=rec.get('high'),
            low=rec.get('low'),
            close=rec.get('close'),
            volume=rec.get('volume'),
            amount=rec.get('amount'),
        )
        db.add(kline)
        inserted += 1

    if inserted > 0:
        db.commit()

    return inserted


def get_kline_cache(db: Session, code: str, start_date: str = None,
                    end_date: str = None, limit: int = 240):
    """从本地缓存查询K线数据

    Args:
        db: 数据库会话
        code: 股票代码
        start_date: 起始日期 YYYY-MM-DD (可选)
        end_date: 结束日期 YYYY-MM-DD (可选)
        limit: 最大返回条数 (默认240)

    Returns:
        list[dict]: 按日期升序排列
    """
    from models import KlineCache

    query = db.query(KlineCache).filter(KlineCache.code == code)

    if start_date:
        query = query.filter(KlineCache.date >= start_date)
    if end_date:
        query = query.filter(KlineCache.date <= end_date)

    rows = query.order_by(KlineCache.date.asc()).limit(limit).all()

    results = []
    for row in rows:
        results.append({
            'code': row.code,
            'date': row.date,
            'open': row.open,
            'high': row.high,
            'low': row.low,
            'close': row.close,
            'volume': row.volume,
            'amount': row.amount,
        })
    return results


def clear_kline_cache(db: Session, code: str = None):
    """清空K线缓存

    Args:
        db: 数据库会话
        code: 股票代码, 为None时清空全网缓存

    Returns:
        int: 删除的记录数
    """
    from models import KlineCache

    query = db.query(KlineCache)
    if code:
        query = query.filter(KlineCache.code == code)

    deleted = query.delete()
    db.commit()
    return deleted


# ═══════════════════════════════════════════════
# 回测数据缓存操作
# ═══════════════════════════════════════════════

def save_backtest_data_batch(db: Session, code: str, records: list):
    """批量保存回测日K数据

    Args:
        db: 数据库会话
        code: 股票代码
        records: [{date, open, close, high, low, volume, amount, change_pct, turnover}, ...]
    """
    from models import BacktestData

    saved = 0
    for rec in records:
        try:
            existing = db.query(BacktestData).filter(
                BacktestData.code == code,
                BacktestData.date == rec['date'],
            ).first()
            if existing:
                # 更新已有记录
                for key in ('open', 'close', 'high', 'low', 'volume', 'amount', 'change_pct', 'turnover'):
                    if key in rec:
                        setattr(existing, key, float(rec[key]))
                existing.source = rec.get('source', 'akshare')
                existing.cached_at = datetime.now()
            else:
                entry = BacktestData(
                    code=code,
                    date=rec['date'],
                    open=float(rec.get('open', 0)),
                    close=float(rec.get('close', 0)),
                    high=float(rec.get('high', 0)),
                    low=float(rec.get('low', 0)),
                    volume=float(rec.get('volume', 0)),
                    amount=float(rec.get('amount', 0)),
                    change_pct=float(rec.get('change_pct', 0)),
                    turnover=float(rec.get('turnover', 0)),
                    source=rec.get('source', 'akshare'),
                )
                db.add(entry)
            saved += 1
        except Exception:
            pass

    db.commit()
    return saved


def get_backtest_data(db: Session, code: str, start_date: str = None, end_date: str = None) -> list:
    """获取回测数据

    Args:
        db: 数据库会话
        code: 股票代码
        start_date: YYYY-MM-DD (可选)
        end_date: YYYY-MM-DD (可选)

    Returns:
        list[dict]: 按日期升序的日线数据
    """
    from models import BacktestData

    query = db.query(BacktestData).filter(BacktestData.code == code).order_by(BacktestData.date)
    if start_date:
        query = query.filter(BacktestData.date >= start_date)
    if end_date:
        query = query.filter(BacktestData.date <= end_date)

    records = []
    for row in query.all():
        records.append({
            'date': row.date,
            'open': row.open,
            'close': row.close,
            'high': row.high,
            'low': row.low,
            'volume': row.volume,
            'amount': row.amount,
            'change_pct': row.change_pct,
            'turnover': row.turnover,
            'source': row.source,
        })
    return records


def get_backtest_meta(db: Session) -> list:
    """获取所有已缓存股票元信息"""
    from models import BacktestStockMeta
    return db.query(BacktestStockMeta).order_by(BacktestStockMeta.last_updated.desc()).all()


def save_backtest_meta(db: Session, code: str, name: str, sector: str,
                       data_start: str, data_end: str, total_days: int):
    """保存/更新股票元信息"""
    from models import BacktestStockMeta

    meta = db.query(BacktestStockMeta).filter(BacktestStockMeta.code == code).first()
    if meta:
        meta.name = name
        meta.sector = sector
        meta.data_start = data_start
        meta.data_end = data_end
        meta.total_days = total_days
        meta.last_updated = datetime.now()
    else:
        meta = BacktestStockMeta(
            code=code, name=name, sector=sector,
            data_start=data_start, data_end=data_end,
            total_days=total_days,
        )
        db.add(meta)
    db.commit()
    return meta


def clear_backtest_data(db: Session, code: str = None):
    """清空回测缓存数据"""
    from models import BacktestData, BacktestStockMeta

    if code:
        db.query(BacktestData).filter(BacktestData.code == code).delete()
        db.query(BacktestStockMeta).filter(BacktestStockMeta.code == code).delete()
    else:
        db.query(BacktestData).delete()
        db.query(BacktestStockMeta).delete()
    db.commit()

