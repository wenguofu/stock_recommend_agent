#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""盯盘任务调度器 + 自动跟踪规则执行"""

import json
import threading
import time
from datetime import datetime, timedelta, date
from models import SessionLocal, MonitorTask, TaskLog, PaperAutoRule
from data_fetchers import get_realtime_data
import traceback

# 调度间隔定义（秒）
SCHEDULE_MAP = {
    'every_5m': 300,
    'every_15m': 900,
    'every_30m': 1800,
    'every_1h': 3600,
    'every_4h': 14400,
}

_scheduler_thread = None
_running = False

# 全局通知队列（内存中保存最近50条提醒）
_recent_alerts = []

# 已触发的规则记录（防重复执行）
_triggered_rules = set()


def is_trading_time() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hour = now.hour
    minute = now.minute
    if (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute <= 30):
        return True
    if (hour == 13) or (hour == 14):
        return True
    if hour == 15 and minute == 0:
        return True
    return False


def get_interval_seconds(schedule: str) -> int:
    return SCHEDULE_MAP.get(schedule, 300)


def _check_price_alert(task: MonitorTask, task_config: dict) -> dict:
    """检查价格提醒"""
    codes = json.loads(task.codes) if isinstance(task.codes, str) else task.codes
    price_up = task_config.get('price_up', 0)
    price_down = task_config.get('price_down', 0)
    
    alerts = []
    for code in codes:
        try:
            data = get_realtime_data(code.strip())
            if not data or not data.get('current_price'):
                continue
            price = data['current_price']
            change_pct = data.get('change_percent', 0)
            name = data.get('name', code)
            if price_up > 0 and change_pct >= price_up:
                alerts.append({
                    'code': code, 'name': name, 'type': 'price_up',
                    'price': price, 'value': change_pct, 'threshold': price_up,
                    'message': f"{name}({code}) 涨幅 {change_pct:.2f}%，超过阈值 {price_up}%"
                })
            if price_down > 0 and change_pct <= -price_down:
                alerts.append({
                    'code': code, 'name': name, 'type': 'price_down',
                    'price': price, 'value': change_pct, 'threshold': price_down,
                    'message': f"{name}({code}) 跌幅 {change_pct:.2f}%，超过阈值 {price_down}%"
                })
        except Exception as e:
            print(f"[调度器] {code} 检查失败: {e}")
    return {'alerts': alerts, 'checked_codes': len(codes), 'triggered': len(alerts)}


def _execute_auto_rules():
    """执行自动跟踪规则（检查价格条件→下单）"""
    db = SessionLocal()
    try:
        today_str = date.today().strftime('%Y-%m-%d')
        rules = db.query(PaperAutoRule).filter(
            PaperAutoRule.enabled == True
        ).all()
        
        for rule in rules:
            rule_key = f"{rule.id}_{today_str}"
            if rule_key in _triggered_rules:
                continue
            
            try:
                # 获取实时价格
                rt = get_realtime_data(rule.code.strip())
                if not rt or not rt.get('current_price'):
                    continue
                current_price = rt['current_price']
                
                from paper_trading import create_order
                
                # 买入检查
                if rule.buy_enabled:
                    buy_ok = False
                    buy_reason = ''
                    if rule.buy_price_low is not None and rule.buy_price_high is not None:
                        if rule.buy_price_low <= current_price <= rule.buy_price_high:
                            buy_ok = True
                            buy_reason = f"价格{current_price:.2f}在买入区间[{rule.buy_price_low}-{rule.buy_price_high}]"
                    elif rule.buy_price_low is not None and current_price >= rule.buy_price_low:
                        buy_ok = True
                        buy_reason = f"价格{current_price:.2f}≥买入下限{rule.buy_price_low}"
                    elif rule.buy_price_high is not None and current_price <= rule.buy_price_high:
                        buy_ok = True
                        buy_reason = f"价格{current_price:.2f}≤买入上限{rule.buy_price_high}"
                    
                    if buy_ok:
                        qty = max(100, rule.buy_quantity // 100 * 100)
                        try:
                            result = create_order(
                                account_id=rule.account_id,
                                code=rule.code.strip(),
                                name=rule.name or rule.code,
                                direction='buy',
                                price=current_price,
                                quantity=qty,
                                order_type='signal',
                                note=f"自动跟踪: {buy_reason}"
                            )
                            msg = f"🤖 [{rule.name}]({rule.code}) 自动买入{qty}股 价格{current_price:.2f} {buy_reason}"
                            _recent_alerts.insert(0, {
                                'task_id': 0, 'task_name': '自动跟踪',
                                'timestamp': datetime.now().isoformat(),
                                'code': rule.code, 'name': rule.name,
                                'type': 'auto_buy', 'price': current_price,
                                'value': 0, 'message': msg,
                            })
                            print(f"[自动跟踪] ✅ 买入成功: {msg}")
                            _triggered_rules.add(rule_key)
                        except Exception as e:
                            print(f"[自动跟踪] ❌ 买入失败 {rule.code}: {e}")
                
                # 卖出检查（持有检查）
                if rule.sell_enabled:
                    sell_ok = False
                    sell_reason = ''
                    from models import PaperPosition
                    pos = db.query(PaperPosition).filter(
                        PaperPosition.account_id == rule.account_id,
                        PaperPosition.code == rule.code.strip()
                    ).first()
                    if pos and pos.shares > 0:
                        if rule.sell_target_price and current_price >= rule.sell_target_price:
                            sell_ok = True
                            sell_reason = f"触止盈: 价格{current_price:.2f}≥目标{rule.sell_target_price}"
                        elif rule.sell_stop_loss and current_price <= rule.sell_stop_loss:
                            sell_ok = True
                            sell_reason = f"触止损: 价格{current_price:.2f}≤止损{rule.sell_stop_loss}"
                    
                    if sell_ok:
                        try:
                            result = create_order(
                                account_id=rule.account_id,
                                code=rule.code.strip(),
                                name=rule.name or rule.code,
                                direction='sell',
                                price=current_price,
                                quantity=pos.shares,
                                order_type='signal',
                                note=f"自动跟踪: {sell_reason}"
                            )
                            msg = f"🤖 [{rule.name}]({rule.code}) 自动卖出{pos.shares}股 价格{current_price:.2f} {sell_reason}"
                            _recent_alerts.insert(0, {
                                'task_id': 0, 'task_name': '自动跟踪',
                                'timestamp': datetime.now().isoformat(),
                                'code': rule.code, 'name': rule.name,
                                'type': 'auto_sell', 'price': current_price,
                                'value': 0, 'message': msg,
                            })
                            print(f"[自动跟踪] ✅ 卖出成功: {msg}")
                            _triggered_rules.add(rule_key)
                        except Exception as e:
                            print(f"[自动跟踪] ❌ 卖出失败 {rule.code}: {e}")
            
            except Exception as e:
                print(f"[自动跟踪] 规则{rule.id}执行异常: {e}")
        
        # 清理过期记录
        old_keys = [k for k in _triggered_rules if not k.endswith(today_str)]
        for k in old_keys:
            _triggered_rules.discard(k)
            
    except Exception as e:
        print(f"[自动跟踪] 总体异常: {e}")
        traceback.print_exc()
    finally:
        db.close()


def _run_single_task(task_id: int):
    """执行单个盯盘任务"""
    db = SessionLocal()
    try:
        task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
        if not task or not task.enabled:
            return
        
        task_config = json.loads(task.config) if task.config else {}
        log = TaskLog(task_id=task.id, task_name=task.name, task_type=task.task_type,
                      status='running', started_at=datetime.now())
        db.add(log)
        db.commit()
        db.refresh(log)
        
        result = {'alerts': [], 'error': None}
        try:
            if task.task_type == 'price_alert':
                result = _check_price_alert(task, task_config)
            elif task.task_type == 'ai_analysis':
                result = {'message': 'AI分析任务需手动触发', 'skipped': True}
            
            for alert in result.get('alerts', []):
                _recent_alerts.insert(0, {
                    'task_id': task.id, 'task_name': task.name,
                    'timestamp': datetime.now().isoformat(), **alert
                })
            while len(_recent_alerts) > 50:
                _recent_alerts.pop()
            
            log.status = 'completed'
            log.result = json.dumps(result, ensure_ascii=False)
            log.triggered_count = result.get('triggered', 0)
        except Exception as e:
            log.status = 'failed'
            log.result = json.dumps({'error': str(e)}, ensure_ascii=False)
        
        log.finished_at = datetime.now()
        task.last_run = datetime.now()
        task.next_run = datetime.now() + timedelta(seconds=get_interval_seconds(task.schedule))
        db.commit()
    except Exception as e:
        print(f"[调度器] 任务 {task_id} 执行异常: {e}")
        traceback.print_exc()
    finally:
        db.close()


def _scheduler_loop():
    """调度器主循环"""
    global _running
    _running = True
    
    auto_rule_counter = 0
    
    while _running:
        try:
            db = SessionLocal()
            try:
                now = datetime.now()
                if not is_trading_time():
                    db.commit()
                    for _ in range(30):
                        if not _running:
                            break
                        time.sleep(1)
                    continue
                
                # 执行盯盘任务
                tasks = db.query(MonitorTask).filter(
                    MonitorTask.enabled == True
                ).all()
                
                for task in tasks:
                    if task.next_run and task.next_run > now:
                        continue
                    t = threading.Thread(
                        target=_run_single_task,
                        args=(task.id,),
                        daemon=True
                    )
                    t.start()
                    interval = get_interval_seconds(task.schedule)
                    task.next_run = now + timedelta(seconds=interval)
                
                db.commit()
            finally:
                db.close()
            
            # 每30秒执行一次自动跟踪规则检查
            auto_rule_counter += 1
            if auto_rule_counter >= 1:
                _execute_auto_rules()
                auto_rule_counter = 0
            
            for _ in range(30):
                if not _running:
                    break
                time.sleep(1)
        except Exception as e:
            print(f"[调度器] 循环异常: {e}")
            time.sleep(5)


def start_scheduler():
    """启动调度器"""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        print("[调度器] 已在运行")
        return
    
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    print("[调度器] 已启动")


def stop_scheduler():
    """停止调度器"""
    global _running
    _running = False
    print("[调度器] 已停止")

def get_recent_alerts(limit=20):
    """获取最近的提醒"""
    return _recent_alerts[:limit]
