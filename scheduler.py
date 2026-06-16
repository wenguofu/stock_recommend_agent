#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
a-stock-trading 内置任务调度器
替代 Hermes cron，在 API 服务内以后台线程运行

用法：api_server.py 自动启动，无需手动调用
提供 /api/scheduler/status 查看任务状态
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
from datetime import datetime, date

# 共享配置
from config import API_BASE

logger = logging.getLogger('scheduler')

# 项目根
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ─── 交易日判断 ───
def is_trading_day():
    return datetime.now().weekday() < 5

def is_trading_hours():
    """判断当前是否在交易时段（9:30-11:30, 13:00-15:00）"""
    now = datetime.now()
    h, m = now.hour, now.minute
    if not is_trading_day():
        return False
    if h == 9 and m >= 30: return True
    if 10 <= h <= 11: return True
    if h == 11 and m <= 30: return True
    if 13 <= h <= 14: return True
    if h == 15 and m == 0: return True
    return False

def is_market_close_period():
    """收盘后时段（15:00后）"""
    now = datetime.now()
    return is_trading_day() and now.hour >= 15

# ─── cron 表达式匹配 ───
def match_cron(minute, hour, day_of_month, month, day_of_week):
    """匹配单个 cron 字段，支持 '*' 和 ','"""
    def match_field(value, pattern):
        if pattern == '*':
            return True
        for part in pattern.split(','):
            if '-' in part:
                lo, hi = part.split('-')
                if int(lo) <= value <= int(hi):
                    return True
            elif int(part) == value:
                return True
        return False

    n = datetime.now()
    return (match_field(n.minute, minute) and
            match_field(n.hour, hour) and
            match_field(n.day, day_of_month) and
            match_field(n.month, month) and
            match_field((n.weekday() + 1) % 7, day_of_week))


# ═══════════════════════════════════════════
# 任务函数
# ═══════════════════════════════════════════

def task_check_alerts():
    """盯盘预警 - 每5分钟"""
    if not is_trading_hours():
        return None
    sys.path.insert(0, PROJECT_ROOT)
    from scripts.alert_check import main
    # alert_check.py 的 main() 直接 print 输出
    # 我们需要捕获 stdout
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        main()
    output = buf.getvalue().strip()
    return output if output else None

def task_check_stada():
    """斯达半导价格监控 - 每30分钟"""
    if not is_trading_hours():
        return None
    import urllib.request
    try:
        req = urllib.request.urlopen("http://qt.gtimg.cn/q=sh603290", timeout=8)
        raw = req.read().decode("gbk")
        parts = raw.split("~")
        if len(parts) < 4:
            return None
        current = float(parts[3])
        if current <= 110:
            return f"🚨 斯达半导(603290)价格已到达买入区！\n当前价: {current:.2f} 元\n推荐买入区: ≤110元"
        elif current <= 119:
            return f"📊 斯达半导(603290)价格接近买入区\n当前价: {current:.2f} 元\n推荐买入区: ≤110元"
    except Exception:
        pass
    return None

def task_market_monitor():
    """大盘趋势监控 - 每5分钟 (OpenSpec: market-trend-monitor)"""
    if not is_trading_hours():
        return None
    import urllib.request, json
    try:
        req = urllib.request.Request(
            f"{API_BASE}/api/market/monitor/quick",
            headers={'User-Agent': 'scheduler/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    level = data.get('warning_level', 'normal')
    if level in ('alert', 'danger'):
        score = data.get('total_score', 0)
        lines = [
            f"⚠️ 大盘预警 {data.get('verdict', '')} 评分:{score}",
            data.get('suggest', ''),
        ]
        signals = data.get('signals', [])
        if signals:
            for s in signals[:3]:
                lines.append(f"• {s}")
        return "\n".join(lines)
    return None

def task_update_sectors():
    """板块成分股每日更新 - 9:00"""
    import urllib.request
    try:
        req = urllib.request.urlopen(f"{API_BASE}/api/sectors/update", timeout=60)
        data = json.loads(req.read())
        if data.get("success"):
            sector_count = len(data.get("sectors", data.get("data", [])))
            return f"✅ 板块数据更新成功 ({sector_count}个板块)"
        return f"⚠️ 板块更新失败: {data.get('message', '未知错误')}"
    except Exception as e:
        return f"❌ 板块更新失败: {e}"

def task_sector_analysis():
    """板块盘后交叉分析 - 15:30 (收盘后)"""
    if not is_market_close_period():
        return None
    try:
        result = subprocess.run(
            [sys.executable, 'sector_analysis.py'],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_ROOT
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output += f"\n⚠️ stderr: {result.stderr.strip()[:200]}"
        return output if output else None
    except Exception as e:
        return f"❌ 板块交叉分析失败: {e}"

def task_sector_hotspot():
    """板块热点挖掘 - 每30分钟"""
    if not is_trading_hours():
        return None
    sys.path.insert(0, PROJECT_ROOT)
    from scripts.sector_hotspot import main as scan_main
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        scan_main()
    output = buf.getvalue().strip()
    return output if output else None

def task_auto_trade():
    """自动跟踪交易执行 - 9:00/11:00/13:00/15:00"""
    if not is_trading_hours():
        return None
    sys.path.insert(0, PROJECT_ROOT)
    from scripts.auto_trade import execute_auto_trades
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        execute_auto_trades()
    output = buf.getvalue().strip()
    return output if output else None

def task_generate_recommendations():
    """股票推荐每日生成 - 16:00"""
    if not is_market_close_period():
        return None
    import urllib.request
    data = json.dumps({"type": "daily", "strategies": ["youzi", "lianghua", "jichang"], "top_n": 10}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/recommendations/generate",
        data=data, headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        if result.get("success") and result.get("count", 0) > 0:
            return f"📊 每日推荐生成: {result['count']}条推荐, {result['total_unique']}只个股\n策略: {', '.join(result['strategies'])}"
    except Exception as e:
        return f"❌ 每日推荐失败: {e}"
    return None

def task_daily_prefetch():
    """全A股每日数据刷新 - 10:00"""
    if not is_trading_hours():
        return None
    try:
        result = subprocess.run(
            [sys.executable, 'batch_prefetch_all.py', '--daily'],
            capture_output=True, text=True, timeout=600,
            cwd=PROJECT_ROOT
        )
        output = result.stdout.strip()[-500:] if len(result.stdout) > 500 else result.stdout.strip()
        return f"📥 全A股增量刷新\n{output}" if output else None
    except subprocess.TimeoutExpired:
        return "⏰ 全A股增量刷新超时（10分钟），可能仍在后台执行"
    except Exception as e:
        return f"❌ 全A股增量刷新失败: {e}"

def task_eod_prefetch():
    """全A股收盘后刷新 - 15:30"""
    if not is_market_close_period():
        return None
    try:
        result = subprocess.run(
            [sys.executable, 'batch_prefetch_all.py', '--daily'],
            capture_output=True, text=True, timeout=600,
            cwd=PROJECT_ROOT
        )
        output = result.stdout.strip()[-500:] if len(result.stdout) > 500 else result.stdout.strip()
        return f"📥 收盘刷新\n{output}" if output else None
    except subprocess.TimeoutExpired:
        return "⏰ 收盘刷新超时，可能仍在后台执行"
    except Exception as e:
        return f"❌ 收盘刷新失败: {e}"


def task_evaluate_tracks():
    """推荐跟踪自动评估 — 每日收盘后评估到期的推荐记录"""
    try:
        from recommendation_tracker import evaluate_tracks
        result = evaluate_tracks()
        checked = result.get('checked', 0)
        if checked > 0:
            return f"📊 推荐跟踪评估: {checked}条记录已评估"
        return None
    except Exception as e:
        return f"❌ 推荐跟踪评估失败: {e}"


def task_watchlist_refresh():
    """自选股数据刷新"""
    script = os.path.join(PROJECT_ROOT, 'scripts', 'refresh_watchlist.py')
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT
        )
        output = result.stdout.strip()
        return f"📊 自选股刷新\n{output}" if output else None
    except subprocess.TimeoutExpired:
        return "⏰ 自选股刷新超时"
    except Exception as e:
        return f"❌ 自选股刷新失败: {e}"


def task_daily_pipeline():
    """Post-close AI pipeline — runs at 15:05 on trading days"""
    if not is_market_close_period():
        return None
    from pipeline.daily_pipeline import run_daily_pipeline
    return run_daily_pipeline()


def task_evaluate_recommendations():
    """Evaluate matured recommendations — daily post-close"""
    if not is_market_close_period():
        return None
    from recommendation_tracker import evaluate_tracks
    return evaluate_tracks()


# ═══════════════════════════════════════════
# 调度器核心
# ═══════════════════════════════════════════

# 任务类型：'interval' (按秒循环) 或 'cron' (按cron表达式)
TASKS = [
    # 高频任务（interval 模式）
    {
        'name': '盯盘提醒推送',
        'func': task_check_alerts,
        'type': 'interval',
        'interval': 300,
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '大盘趋势监控',
        'func': task_market_monitor,
        'type': 'interval',
        'interval': 300,
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '板块热点挖掘',
        'func': task_sector_hotspot,
        'type': 'interval',
        'interval': 1800,  # 30分钟
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '斯达半导体价格监控',
        'func': task_check_stada,
        'type': 'interval',
        'interval': 1800,  # 30分钟
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    # ── 定时任务（cron 模式）──
    {
        'name': '板块成分股每日更新',
        'func': task_update_sectors,
        'type': 'cron',
        'cron': '0 9 * * 1-5',
        'last_date': '',  # 日期去重：一天只跑一次
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '自动跟踪交易执行',
        'func': task_auto_trade,
        'type': 'cron',
        'cron': '0 9,11,13,15 * * 1-5',
        'last_run_at': '',  # 格式: YYYY-MM-DD HH:MM
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '全A股每日数据刷新',
        'func': task_daily_prefetch,
        'type': 'cron',
        'cron': '0 10 * * 1-5',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '板块盘后交叉分析',
        'func': task_sector_analysis,
        'type': 'cron',
        'cron': '30 15 * * 1-5',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '股票推荐每日生成',
        'func': task_generate_recommendations,
        'type': 'cron',
        'cron': '0 16 * * 1-5',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '自选股数据刷新',
        'func': task_watchlist_refresh,
        'type': 'cron',
        'cron': '*/30 9-15 * * 1-5',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': '推荐跟踪自动评估',
        'func': task_evaluate_tracks,
        'type': 'cron',
        'cron': '30 16 * * 1-5',  # 收盘后16:30评估
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    # ── AI 收盘后任务 ──
    {
        'name': 'AI Daily Pipeline',
        'cron': '5 15 * * 1-5',  # 15:05 on weekdays
        'func': task_daily_pipeline,
        'type': 'cron',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
    {
        'name': 'Evaluate Recommendations',
        'cron': '10 15 * * 1-5',  # 15:10 on weekdays
        'func': task_evaluate_recommendations,
        'type': 'cron',
        'last_date': '',
        'last_run': 0,
        'run_count': 0,
        'last_output': '',
        'last_error': '',
    },
]


class TaskScheduler:
    """内置任务调度器"""

    def __init__(self):
        self.tasks = [dict(t) for t in TASKS]  # 深拷贝
        self.running = False
        self._thread = None
        self._log_dir = os.path.join(PROJECT_ROOT, 'logs')
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_file = os.path.join(self._log_dir, 'scheduler.log')
        self._output_file = os.path.join(self._log_dir, 'scheduler_outputs.json')

    def _log(self, msg):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{ts}] {msg}'
        logger.info(msg)
        with open(self._log_file, 'a') as f:
            f.write(line + '\n')

    def _save_output(self, task_name, output):
        """保存任务输出到JSON文件，供API查询"""
        records = []
        if os.path.exists(self._output_file):
            try:
                with open(self._output_file) as f:
                    records = json.load(f)
            except (json.JSONDecodeError, ValueError):
                records = []
        records.append({
            'task': task_name,
            'time': datetime.now().isoformat(),
            'output': output[:1000],  # 截断避免过大
        })
        # 只保留最近200条
        records = records[-200:]
        with open(self._output_file, 'w') as f:
            json.dump(records, f, ensure_ascii=False)

    def _save_run_log(self, task, started_at, status, output, error, trigger_source):
        """持久化一次调度器任务执行记录到 scheduler_run_log 表"""
        from models import SchedulerRunLog, SessionLocal
        finished_at = datetime.now()
        db = SessionLocal()
        try:
            row = SchedulerRunLog(
                task_name=task['name'],
                task_type=task.get('type'),
                schedule=(
                    str(task.get('interval', '')) if task.get('type') == 'interval'
                    else task.get('cron', '')
                ),
                status=status,
                output=(output or '')[:10000],
                error=error,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                trigger_source=trigger_source,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def get_recent_outputs(self, limit=20):
        """获取最近任务输出"""
        if not os.path.exists(self._output_file):
            return []
        try:
            with open(self._output_file) as f:
                records = json.load(f)
            return records[-limit:]
        except Exception:
            return []

    def get_status(self):
        """获取所有任务状态"""
        result = []
        for t in self.tasks:
            result.append({
                'name': t['name'],
                'type': t['type'],
                'schedule': str(t.get('interval', '')) if t['type'] == 'interval' else t.get('cron', ''),
                'run_count': t['run_count'],
                'last_run': datetime.fromtimestamp(t['last_run']).strftime('%Y-%m-%d %H:%M:%S') if t['last_run'] else '从未运行',
                'last_output': str(t['last_output'])[:200] if t['last_output'] else '',
                'last_error': t['last_error'],
                'in_flight': bool(t.get('_in_flight')),
                'current_started_at': t.get('_current_started_at'),
            })
        return result

    def _match_cron(self, task):
        """检查cron任务是否到时间运行"""
        try:
            parts = task['cron'].split()
            if len(parts) != 5:
                return False
            minute, hour, dom, month, dow = parts
            return match_cron(minute, hour, dom, month, dow)
        except Exception:
            return False

    def _should_run_cron(self, task):
        """判断cron任务是否应执行（走防止重复逻辑）"""
        if not self._match_cron(task):
            return False

        now = datetime.now()

        # 根据去重字段类型判断
        if 'last_date' in task:  # 一天一次
            today = now.strftime('%Y-%m-%d')
            if task['last_date'] == today:
                return False
            task['last_date'] = today
            return True

        if 'last_run_at' in task:  # 按小时去重 (9,11,13,15)
            key = now.strftime('%Y-%m-%d %H:%M')
            minute_key = now.strftime('%Y-%m-%d %H')  # 同一小时内不再重复
            if task.get('_last_hour') == minute_key:
                return False
            task['_last_hour'] = minute_key
            return True

        # 兜底：60秒防重复
        if time.time() - task['last_run'] < 60:
            return False
        return True

    def _run_task(self, task, trigger_source='auto'):
        """执行单个任务(带 in-flight 锁 + 日志落库)"""
        task_name = task['name']
        if task.get('_in_flight'):
            self._log(f"⏸ {task_name}: 已在执行中,跳过本次触发")
            return False
        task['_in_flight'] = True
        task['_current_started_at'] = datetime.now().isoformat()
        started_at = datetime.now()
        self._log(f"▶ 开始执行: {task_name}")
        self._save_run_log(
            task=task, started_at=started_at, status='running',
            output=None, error=None, trigger_source=trigger_source,
        )
        try:
            output = task['func']()
            if output:
                task['last_output'] = output
                self._log(f"✅ {task_name}: {output[:100]}")
                self._save_output(task_name, output)
                self._save_run_log(
                    task=task, started_at=started_at, status='success',
                    output=output, error=None, trigger_source=trigger_source,
                )
            else:
                self._log(f"⏭ {task_name}: 跳过（非执行时段或无输出）")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            task['last_error'] = err
            self._log(f"❌ {task_name} 失败: {err}")
            self._save_run_log(
                task=task, started_at=started_at, status='failed',
                output=None, error=err, trigger_source=trigger_source,
            )
        finally:
            task['last_run'] = time.time()
            task['run_count'] += 1
            task['_in_flight'] = False
            task['_current_started_at'] = None
        return True

    def _loop(self):
        """主循环"""
        self._log("🚀 调度器已启动")
        
        # 启动时检查：是否错过了某些cron任务（服务重启后补跑）
        self._catchup_missed_cron()
        
        while self.running:
            try:
                now = time.time()
                for task in self.tasks:
                    if task['type'] == 'interval':
                        if now - task['last_run'] >= task['interval']:
                            self._run_task(task, trigger_source='auto')
                    elif task['type'] == 'cron':
                        if self._should_run_cron(task):
                            self._run_task(task, trigger_source='auto')
            except Exception as e:
                self._log(f"🛑 循环异常: {e}")
            time.sleep(30)  # 每30秒检查一次

    def _catchup_missed_cron(self):
        """启动时补跑错过的cron任务（服务重启/启动晚了的情况）"""
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        self._log(f"检查错过的cron任务 (当前时间 {now.strftime('%H:%M')})")
        for task in self.tasks:
            if task['type'] != 'cron':
                continue
            if 'last_date' not in task or task.get('last_date') == today:
                continue  # 已经跑过今天的不重复
            parts = task['cron'].split()
            if len(parts) != 5:
                continue
            try:
                cron_hour = int(parts[1])
                cron_min = int(parts[0])
            except ValueError:
                # 范围/步进表达式 (如 9-15, */30) 无法判断"是否错过" → 跳过补跑
                continue
            # 当前时间已过cron时间点，且今天还没跑过
            if now.hour > cron_hour or (now.hour == cron_hour and now.minute >= cron_min):
                # 但也要检查时间段限制（交易时段/收盘后）
                task_name = task['name']
                self._log(f"⏰ 补跑错过的cron任务: {task_name} ({parts[0]}:{parts[1]})")
                self._run_task(task, trigger_source='auto')
                # 标记今天已跑
                task['last_date'] = today

    def run_task(self, name_or_index):
        """手动触发执行某个任务（供API调用）"""
        for task in self.tasks:
            if task['name'] == name_or_index:
                # 修复 BUG-05: 手动触发时若任务正在执行,返 409 而非并发重入
                if task.get('_in_flight'):
                    return {
                        "success": False,
                        "error": f"任务 {task['name']} 正在执行中,请稍后再试",
                        "in_flight": True,
                    }
                result = self._run_task(task, trigger_source='manual')
                if result is False:
                    return {"success": False, "error": "任务被跳过(并发或时段限制)"}
                return {"success": True, "name": task['name']}
        return {"success": False, "error": f"未找到任务: {name_or_index}"}

    def get_task_names(self):
        return [t['name'] for t in self.tasks]

    def start(self):
        """在后台线程启动调度器"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='task-scheduler')
        self._thread.start()
        self._log("调度器线程已创建")

    def stop(self):
        """停止调度器"""
        self.running = False
        self._log("🛑 调度器已停止")


# 全局单例
_scheduler_instance = None

def get_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
    return _scheduler_instance

def start_scheduler():
    """启动调度器（供 api_server.py 调用）"""
    sched = get_scheduler()
    sched.start()
    return sched

def get_scheduler_status():
    return get_scheduler().get_status()

def get_scheduler_outputs(limit=20):
    return get_scheduler().get_recent_outputs(limit=limit)


if __name__ == '__main__':
    # 测试运行
    logging.basicConfig(level=logging.INFO)
    sched = get_scheduler()
    sched.start()
    try:
        while True:
            time.sleep(10)
            # 每10秒打印一次状态
            import os
            os.system('clear')
            print("=== 调度器状态 ===")
            for s in sched.get_status():
                print(f"  {s['name']}: 运行{s['run_count']}次 | 最后: {s['last_run']}")
    except KeyboardInterrupt:
        sched.stop()
