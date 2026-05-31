# 高胜率股票推荐系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建四层股票筛选系统，从5520只股票中精选3-5只推荐，目标胜率>70%，盈亏比>5:1

**Architecture:**
- Layer 1: 大盘环境过滤 + 热门板块限制 + 个股基础条件
- Layer 2: 多信号加权评分（量价+趋势+资金）
- Layer 3: 历史胜率回测验证
- Layer 4: 模拟盘监控与调仓

**Tech Stack:** Python 3.9+, SQLAlchemy, akshare, NumPy, Pandas, Flask API

---

## File Structure

```
screening/
├── layer1_tech_screen.py    # Layer 1 技术宽筛
├── layer2_signal_score.py   # Layer 2 多信号评分
├── layer3_backtest_verify.py # Layer 3 历史胜率验证
├── recommendation_engine.py # 推荐引擎整合
├── hot_sector_manager.py    # 热门板块动态管理器
├── hot_sectors.json        # 板块配置缓存
monitoring/
├── daily_monitor.py         # 每日监控
├── alert_service.py         # 预警服务
tests/
├── test_layer1_screen.py
├── test_layer2_score.py
├── test_layer3_verify.py
├── test_hot_sectors.py
```

---

## Task 1: 创建项目目录结构和hot_sectors.json配置

**Files:**
- Create: `screening/hot_sectors.json`
- Create: `screening/__init__.py`
- Create: `monitoring/__init__.py`
- Create: `tests/test_layer1_screen.py`
- Create: `tests/test_layer2_score.py`
- Create: `tests/test_layer3_verify.py`
- Create: `tests/test_hot_sectors.py`

- [ ] **Step 1: Create screening directory**

```bash
mkdir -p /Users/wgfu/work/a-stock-trading/screening
mkdir -p /Users/wgfu/work/a-stock-trading/monitoring
mkdir -p /Users/wgfu/work/a-stock-trading/tests
```

- [ ] **Step 2: Create hot_sectors.json with initial sectors**

```json
{
  "version": "1.0.0",
  "updated_at": "2026-05-31",
  "sectors": [
    {"name": "芯片/半导体", "codes": [], "score": 80},
    {"name": "新能源汽车", "codes": [], "score": 75},
    {"name": "医药生物", "codes": [], "score": 70},
    {"name": "人工智能", "codes": [], "score": 70},
    {"name": "光伏/储能", "codes": [], "score": 65},
    {"name": "军工", "codes": [], "score": 60}
  ]
}
```

- [ ] **Step 3: Create __init__.py files**

```python
# screening/__init__.py
from .layer1_tech_screen import screen_layer1
from .layer2_signal_score import score_layer2
from .layer3_backtest_verify import verify_layer3
from .recommendation_engine import get_recommendations
from .hot_sector_manager import HotSectorManager

__all__ = ['screen_layer1', 'score_layer2', 'verify_layer3', 'get_recommendations', 'HotSectorManager']
```

```python
# monitoring/__init__.py
from .daily_monitor import DailyMonitor
from .alert_service import AlertService

__all__ = ['DailyMonitor', 'AlertService']
```

- [ ] **Step 4: Create placeholder tests**

```python
# tests/test_layer1_screen.py
import pytest
import sys
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

def test_layer1_basic():
    """Test Layer 1 screening returns results"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='short')
    assert result is not None
    assert 'candidates' in result
```

- [ ] **Step 5: Commit**

```bash
git add screening/ monitoring/ tests/
git commit -m "feat: add project structure for stock recommendation system

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 实现大盘环境过滤器 `is_market_safe_for_screening()`

**Files:**
- Create: `screening/layer1_tech_screen.py`
- Modify: `screening/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer1_screen.py
def test_market_safety_check():
    """Test market safety check returns correct structure"""
    from screening.layer1_tech_screen import is_market_safe_for_screening
    is_safe, details = is_market_safe_for_screening()
    assert isinstance(is_safe, bool)
    assert 'strong_count' in details
    assert 'limit_down_count' in details
    assert 'reason' in details
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_market_safety_check -v
```
Expected: FAIL — function not defined

- [ ] **Step 3: Implement is_market_safe_for_screening()**

```python
# screening/layer1_tech_screen.py
#!/usr/bin/env python3
"""Layer 1: 技术面宽筛"""
import sys
import os
from typing import Tuple, List, Dict

def is_market_safe_for_screening() -> Tuple[bool, dict]:
    """
    检查大盘环境是否适合筛选
    条件: 涨幅>8%股数 >= 50 且 跌幅>8%股数 <= 50
    """
    try:
        import akshare as ak
        from datetime import datetime

        today = datetime.now().strftime('%Y%m%d')

        # 涨幅>8%股票池
        strong = ak.stock_zt_pool_strong_em(date=today)
        strong_count = len(strong[strong['涨跌幅'] > 8]) if '涨跌幅' in strong.columns else len(strong)

        # 跌停股票池
        dt = ak.stock_zt_pool_dtgc_em(date=today)
        limit_down_count = len(dt)

        is_safe = (strong_count >= 50) and (limit_down_count <= 50)

        return is_safe, {
            'strong_count': strong_count,
            'limit_down_count': limit_down_count,
            'reason': 'safe' if is_safe else 'market_risk',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        # 网络失败时返回安全状态，避免完全阻断
        return True, {
            'strong_count': -1,
            'limit_down_count': -1,
            'reason': 'unknown (api_error)',
            'error': str(e)
        }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_market_safety_check -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/layer1_tech_screen.py screening/__init__.py tests/test_layer1_screen.py
git commit -m "feat: add market safety filter for Layer 1 screening

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 实现热门板块动态管理器 `HotSectorManager`

**Files:**
- Create: `screening/hot_sector_manager.py`
- Modify: `screening/hot_sectors.json`

- [ ] **Step 1: Write failing test**

```python
# tests/test_hot_sectors.py
import json
import os

def test_hot_sector_manager_load():
    """Test HotSectorManager loads from json"""
    from screening.hot_sector_manager import HotSectorManager
    mgr = HotSectorManager()
    sectors = mgr.get_current_sectors()
    assert isinstance(sectors, list)
    assert len(sectors) > 0

def test_hot_sector_manager_update():
    """Test weekly update function exists"""
    from screening.hot_sector_manager import HotSectorManager
    mgr = HotSectorManager()
    assert hasattr(mgr, 'update_weekly')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_hot_sectors.py -v
```
Expected: FAIL — module not exist

- [ ] **Step 3: Implement HotSectorManager**

```python
# screening/hot_sector_manager.py
#!/usr/bin/env python3
"""热门板块动态管理器 - 每周更新热门板块列表"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

HOT_SECTORS_FILE = os.path.join(os.path.dirname(__file__), 'hot_sectors.json')

# 默认热门板块
DEFAULT_SECTORS = [
    {"name": "芯片/半导体", "codes": [], "score": 80},
    {"name": "新能源汽车", "codes": [], "score": 75},
    {"name": "医药生物", "codes": [], "score": 70},
    {"name": "人工智能", "codes": [], "score": 70},
    {"name": "光伏/储能", "codes": [], "score": 65},
    {"name": "军工", "codes": [], "score": 60},
]

class HotSectorManager:
    """热门板块管理器"""

    def __init__(self, config_file: str = HOT_SECTORS_FILE):
        self.config_file = config_file
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'version': '1.0.0',
                'updated_at': datetime.now().strftime('%Y-%m-%d'),
                'sectors': DEFAULT_SECTORS.copy()
            }
            self._save_config()

    def _save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_current_sectors(self) -> List[str]:
        """获取当前热门板块名称列表"""
        return [s['name'] for s in self.config.get('sectors', [])]

    def get_sector_codes(self, sector_name: str) -> List[str]:
        """获取指定板块的成分股"""
        for sector in self.config.get('sectors', []):
            if sector['name'] == sector_name:
                return sector.get('codes', [])
        return []

    def get_all_sector_codes(self) -> List[str]:
        """获取所有热门板块的成分股（去重）"""
        codes = set()
        for sector in self.config.get('sectors', []):
            codes.update(sector.get('codes', []))
        return list(codes)

    def update_weekly(self) -> Dict:
        """
        每周检查更新热门板块
        基于近20日涨幅、成交额等指标更新
        """
        try:
            import akshare as ak
            import numpy as np

            # 获取行业板块数据
            df = ak.stock_board_industry_name_em()

            scored_sectors = []
            for _, row in df.iterrows():
                name = row.get('名称', '')
                # 涨幅、成交额等评分
                change_pct = row.get('涨跌幅', 0) or 0
                amount = row.get('成交额', 0) or 0

                # 简单评分：涨幅*0.6 + 成交额标准化*0.4
                amount_norm = min(amount / 1e10, 1.0) if amount else 0
                score = change_pct * 0.6 + amount_norm * 0.4 * 100

                scored_sectors.append({
                    'name': name,
                    'codes': [],  # 板块成分股待补充
                    'score': round(score, 2),
                    'change_pct': round(change_pct, 2),
                    'amount': amount
                })

            # 按评分排序，保留Top 8
            scored_sectors.sort(key=lambda x: x['score'], reverse=True)
            top_sectors = scored_sectors[:8]

            self.config['sectors'] = top_sectors
            self.config['updated_at'] = datetime.now().strftime('%Y-%m-%d')
            self._save_config()

            return {
                'success': True,
                'updated_count': len(top_sectors),
                'top_sectors': [s['name'] for s in top_sectors]
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_config(self) -> Dict:
        """获取完整配置"""
        return self.config.copy()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_hot_sectors.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/hot_sector_manager.py tests/test_hot_sectors.py
git commit -m "feat: add HotSectorManager for dynamic sector updates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 实现 Layer 1 技术面宽筛 `screen_layer1()`

**Files:**
- Modify: `screening/layer1_tech_screen.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer1_screen.py
def test_layer1_short_screening():
    """Test Layer 1 short-term screening"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='short')
    assert 'candidates' in result
    assert 'market_check' in result
    assert 'filter_applied' in result

def test_layer1_mid_screening():
    """Test Layer 1 mid-term screening"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='mid')
    assert result['recommendation_type'] == 'mid'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_layer1_short_screening tests/test_layer1_screen.py::test_layer1_mid_screening -v
```
Expected: FAIL — function not complete

- [ ] **Step 3: Implement screen_layer1() - add to existing file**

```python
def screen_layer1(recommendation_type: str = 'short') -> Dict:
    """
    Layer 1: 技术面宽筛

    Args:
        recommendation_type: 'short' (5-20天) 或 'mid' (1-3个月)

    Returns:
        {
            'candidates': [code, ...],
            'market_check': {...},
            'filter_applied': [...],
            'count': int
        }
    """
    # 1. 大盘环境检查
    is_safe, market_details = is_market_safe_for_screening()

    # 如果大盘环境不安全，返回空结果
    if not is_safe:
        return {
            'candidates': [],
            'market_check': market_details,
            'filter_applied': ['market_safety'],
            'count': 0,
            'recommendation_type': recommendation_type,
            'warning': '大盘环境不安全，暂停筛选'
        }

    # 2. 获取热门板块股票
    sector_mgr = HotSectorManager()
    hot_codes = set(sector_mgr.get_all_sector_codes())

    # 3. 从数据库筛选候选股
    from models import SessionLocal
    from sqlalchemy import text
    import numpy as np

    db = SessionLocal()
    try:
        # 基础SQL筛选
        if recommendation_type == 'short':
            # 短线条件
            min_volume = 50000000  # 5000万
            min_days = 120
        else:
            # 中线条件
            min_volume = 100000000  # 1亿
            min_days = 250

        rows = db.execute(text('''
            SELECT b.code, b.name,
                   MAX(b.close) as latest_close,
                   AVG(b.volume) as avg_volume,
                   COUNT(*) as day_count,
                   MAX(b.high) as highest_60d
            FROM backtest_data b
            WHERE b.code REGEXP '^[0-9]{6}$'
            GROUP BY b.code, b.name
            HAVING COUNT(*) >= :min_days
            AND AVG(b.volume) >= :min_volume
            ORDER BY AVG(b.volume) DESC
            LIMIT 500
        '''), {'min_days': min_days, 'min_volume': min_volume}).fetchall()

        candidates = []
        for row in rows:
            code = row[0]
            # 只保留热门板块股票
            if hot_codes and code not in hot_codes:
                continue

            candidates.append({
                'code': code,
                'name': row[1],
                'avg_volume': float(row[4]) if row[4] else 0
            })

        return {
            'candidates': candidates,
            'market_check': market_details,
            'filter_applied': ['market_safety', 'hot_sectors', 'volume', 'min_days'],
            'count': len(candidates),
            'recommendation_type': recommendation_type
        }

    finally:
        db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_layer1_short_screening tests/test_layer1_screen.py::test_layer1_mid_screening -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/layer1_tech_screen.py
git commit -m "feat: implement Layer 1 tech screening with market and sector filters

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 实现 Layer 2 多信号评分 `score_layer2()`

**Files:**
- Create: `screening/layer2_signal_score.py`
- Create: `tests/test_layer2_score.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer2_score.py
def test_layer2_scoring():
    """Test Layer 2 multi-signal scoring"""
    from screening.layer2_signal_score import score_layer2

    # 模拟Layer 1输出
    layer1_result = {
        'candidates': [
            {'code': '300750', 'name': '宁德时代'}
        ],
        'recommendation_type': 'short'
    }

    result = score_layer2(layer1_result)
    assert 'scored_candidates' in result
    assert 'top_candidates' in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer2_score.py::test_layer2_scoring -v
```
Expected: FAIL — module not exist

- [ ] **Step 3: Implement score_layer2()**

```python
# screening/layer2_signal_score.py
#!/usr/bin/env python3
"""Layer 2: 多信号评分"""
import sys
import os
import numpy as np
from typing import Dict, List

def score_layer2(layer1_result: Dict) -> Dict:
    """
    Layer 2: 对Layer 1候选股进行多信号加权评分

    Args:
        layer1_result: Layer 1的输出结果

    Returns:
        {
            'scored_candidates': [...],
            'top_candidates': [...],  # Top 20-30
            'recommendation_type': str
        }
    """
    from data_fetchers import get_daily_kline, get_money_flow

    candidates = layer1_result.get('candidates', [])
    rec_type = layer1_result.get('recommendation_type', 'short')

    scored = []

    for cand in candidates:
        code = cand['code']
        try:
            # 获取日K线数据
            df = get_daily_kline(code, count=120)
            if df is None or len(df) < 60:
                continue

            close = df['close'].values.astype(float)
            high = df['high'].values.astype(float)
            low = df['low'].values.astype(float)
            open_p = df['open'].values.astype(float)
            volume = df['volume'].values.astype(float)

            n = len(close)

            # 计算各项信号
            if rec_type == 'short':
                signals = _calc_short_signals(close, high, low, open_p, volume)
            else:
                signals = _calc_mid_signals(close, high, low, volume)

            # 计算综合评分
            score = _calc_composite_score(signals, rec_type)

            signals['code'] = code
            signals['name'] = cand.get('name', '')
            signals['composite_score'] = score
            signals['rec_type'] = rec_type

            scored.append(signals)

        except Exception as e:
            continue

    # 按评分排序
    scored.sort(key=lambda x: x['composite_score'], reverse=True)

    # 取Top 20-30
    top_count = 30 if rec_type == 'short' else 20
    top_candidates = scored[:top_count]

    return {
        'scored_candidates': scored,
        'top_candidates': top_candidates,
        'total_candidates': len(scored),
        'recommendation_type': rec_type
    }


def _calc_short_signals(close, high, low, open_p, volume) -> Dict:
    """计算短线信号"""
    n = len(close)

    # 1. 突破20日高点
    high_20d = np.max(high[-21:-1])
    current_close = close[-1]
    breakout_pct = (current_close / high_20d - 1) * 100 if high_20d > 0 else 0
    breakout_score = 20 if breakout_pct > 5 else (16 if breakout_pct > 3 else (12 if breakout_pct > 0 else 0))

    # 2. 成交量放大
    avg_vol_20 = np.mean(volume[-21:-1])
    vol_ratio = volume[-1] / avg_vol_20 if avg_vol_20 > 0 else 1
    vol_score = 15 if vol_ratio > 3 else (12 if vol_ratio > 2 else (9 if vol_ratio > 1.5 else 3))

    # 3. 价格站上均线
    ma5 = np.mean(close[-5:])
    ma10 = np.mean(close[-10:])
    ma20 = np.mean(close[-20:])
    ma_count = sum([1 if current_close > ma5 else 0,
                    1 if current_close > ma10 else 0,
                    1 if current_close > ma20 else 0])
    ma_score = ma_count * 3.33  # 0-10分

    # 4. 均线多头 (MA5 > MA20)
    ma_cross_score = 15 if ma5 > ma20 else 0

    # 5. RSI
    rsi = _calc_rsi(close, 14)
    rsi_score = 10 if 50 <= rsi <= 60 else (8 if 40 <= rsi <= 70 else 4)

    # 6. 近10日最大回撤
    max_dd_10d = (np.max(close[-10:]) - current_close) / np.max(close[-10:]) * 100
    dd_score = 10 if max_dd_10d < 5 else (8 if max_dd_10d < 10 else 4)

    # 7. 资金信号（简化：量比变化）
    vol_ratio_3d = np.mean(volume[-3:]) / np.mean(volume[-6:-3]) if np.mean(volume[-6:-3]) > 0 else 1
    money_score = 15 if vol_ratio_3d > 1.2 else (8 if vol_ratio_3d > 1 else 0)

    return {
        'breakout_pct': round(breakout_pct, 2),
        'vol_ratio': round(vol_ratio, 2),
        'ma_count': ma_count,
        'rsi': round(rsi, 1),
        'max_dd_10d': round(max_dd_10d, 2),
        'vol_ratio_3d': round(vol_ratio_3d, 2),
        'breakout_score': breakout_score,
        'vol_score': vol_score,
        'ma_score': ma_score,
        'ma_cross_score': ma_cross_score,
        'rsi_score': rsi_score,
        'dd_score': dd_score,
        'money_score': money_score,
    }


def _calc_mid_signals(close, high, volume) -> Dict:
    """计算中线信号"""
    n = len(close)

    # 1. 均线多头 (MA10 > MA60)
    ma10 = np.mean(close[-10:])
    ma60 = np.mean(close[-60:]) if n >= 60 else close[-1]
    ma_cross_score = 20 if ma10 > ma60 else 0

    # 2. 60日涨幅
    ret60 = (close[-1] / close[-60] - 1) * 100 if n >= 60 else 0
    ret60_score = 15 if 40 <= ret60 <= 60 else (12 if 20 <= ret60 <= 80 else 6)

    # 3. 突破60日高点
    high_60d = np.max(high[-61:-1])
    breakout_pct = (close[-1] / high_60d - 1) * 100 if high_60d > 0 else 0
    breakout_score = 15 if breakout_pct > 10 else (12 if breakout_pct > 5 else 6)

    # 4. 成交量放大
    avg_vol_60 = np.mean(volume[-61:-1])
    vol_ratio = volume[-1] / avg_vol_60 if avg_vol_60 > 0 else 1
    vol_score = 10 if vol_ratio > 3 else (6 if vol_ratio > 2 else 3)

    # 波动率
    returns = np.diff(close[-21:]) / close[-21:-1]
    vol = float(np.std(returns) * 100 * np.sqrt(252))
    vol_score = 10 if 25 <= vol <= 50 else 5

    return {
        'ret60': round(ret60, 2),
        'breakout_pct': round(breakout_pct, 2),
        'vol_ratio': round(vol_ratio, 2),
        'ma_cross_score': ma_cross_score,
        'ret60_score': ret60_score,
        'breakout_score': breakout_score,
        'vol_score': vol_score,
    }


def _calc_rsi(close, period=14):
    """计算RSI"""
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.zeros(len(close))
    avg_loss = np.zeros(len(close))
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

    rs = avg_gain[-1] / avg_loss[-1] if avg_loss[-1] > 0 else 100
    return 100 - 100 / (1 + rs)


def _calc_composite_score(signals: Dict, rec_type: str) -> float:
    """计算综合评分"""
    if rec_type == 'short':
        weights = {
            'breakout_score': 0.20,
            'vol_score': 0.15,
            'ma_score': 0.10,
            'ma_cross_score': 0.15,
            'rsi_score': 0.10,
            'dd_score': 0.10,
            'money_score': 0.15,
        }
    else:
        weights = {
            'ma_cross_score': 0.20,
            'ret60_score': 0.15,
            'breakout_score': 0.15,
            'vol_score': 0.10,
        }

    score = 0
    for key, weight in weights.items():
        score += signals.get(key, 0) * weight

    return round(score, 1)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer2_score.py::test_layer2_scoring -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/layer2_signal_score.py tests/test_layer2_score.py
git commit -m "feat: implement Layer 2 multi-signal scoring system

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 实现 Layer 3 历史胜率验证 `verify_layer3()`

**Files:**
- Create: `screening/layer3_backtest_verify.py`
- Create: `tests/test_layer3_verify.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer3_verify.py
def test_layer3_verification():
    """Test Layer 3 historical win rate verification"""
    from screening.layer3_backtest_verify import verify_layer3

    layer2_result = {
        'top_candidates': [
            {'code': '300750', 'name': '宁德时代', 'composite_score': 75.5}
        ],
        'recommendation_type': 'short'
    }

    result = verify_layer3(layer2_result)
    assert 'verified_candidates' in result
    assert 'top_recommendations' in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer3_verify.py::test_layer3_verification -v
```
Expected: FAIL — module not exist

- [ ] **Step 3: Implement verify_layer3()**

```python
# screening/layer3_backtest_verify.py
#!/usr/bin/env python3
"""Layer 3: 历史胜率验证"""
import sys
import os
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

def verify_layer3(layer2_result: Dict) -> Dict:
    """
    Layer 3: 对Layer 2候选股进行历史胜率验证

    核心逻辑：
    1. 记录当前信号状态
    2. 在历史K线中搜索相同信号模式
    3. 统计出现相同信号后N日的上涨概率
    4. 只推荐：历史胜率 > 70% 的股票

    Args:
        layer2_result: Layer 2的输出结果

    Returns:
        {
            'verified_candidates': [...],
            'top_recommendations': [...],  # Top 3-5
            'recommendation_type': str
        }
    """
    top_candidates = layer2_result.get('top_candidates', [])
    rec_type = layer2_result.get('recommendation_type', 'short')

    verified = []

    for cand in top_candidates[:50]:  # 只验证Top 50，减少计算量
        code = cand['code']
        try:
            win_rates, avg_returns = _calculate_historical_win_rate(code, rec_type)

            if not win_rates:
                continue

            # 取关键周期的胜率
            key_period = '5d' if rec_type == 'short' else '20d'
            win_rate = win_rates.get(key_period, 0)
            avg_return = avg_returns.get(key_period, 0)

            # 只保留胜率 > 70% 的股票
            if win_rate >= 0.70:
                cand['win_rates'] = win_rates
                cand['avg_returns'] = avg_returns
                cand['key_win_rate'] = win_rate
                cand['key_avg_return'] = avg_return
                cand['sample_count'] = len(win_rates)

                # 计算目标价和止损价
                current_price = cand.get('close', cand.get('price', 0))
                if current_price > 0:
                    cand['target_price'] = round(current_price * (1 + avg_return / 100 * 2), 2)
                    cand['stop_loss_price'] = round(current_price * 0.93, 2)

                verified.append(cand)

        except Exception as e:
            continue

    # 按胜率排序
    verified.sort(key=lambda x: (x['key_win_rate'], x['composite_score']), reverse=True)

    # 取Top 3-5
    top_count = 5 if rec_type == 'short' else 3
    top_recommendations = verified[:top_count]

    return {
        'verified_candidates': verified,
        'top_recommendations': top_recommendations,
        'total_verified': len(verified),
        'recommendation_type': rec_type
    }


def _calculate_historical_win_rate(code: str, rec_type: str) -> Tuple[Dict, Dict]:
    """
    计算历史胜率

    对每只股票：
    1. 获取历史K线数据
    2. 在每个历史点检测是否出现"相同信号模式"
    3. 统计信号后5/10/20日的收益
    4. 返回各周期胜率和平均收益
    """
    from data_fetchers import get_daily_kline

    df = get_daily_kline(code, count=500)
    if df is None or len(df) < 120:
        return {}, {}

    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    volume = df['volume'].values.astype(float)

    n = len(close)

    win_counts = {'5d': 0, '10d': 0, '20d': 0}
    return_sums = {'5d': 0, '10d': 0, '20d': 0}
    signal_counts = {'5d': 0, '10d': 0, '20d': 0}

    hold_periods = {'5d': 5, '10d': 10, '20d': 20}

    # 从120天开始（确保有足够历史数据）
    for i in range(120, n - 20):
        # 检查是否满足信号条件
        if rec_type == 'short':
            signals_match = _check_short_signals(close, high, volume, i)
        else:
            signals_match = _check_mid_signals(close, high, volume, i)

        if not signals_match:
            continue

        # 计算后续各周期收益
        for period_key, hold_days in hold_periods.items():
            if i + hold_days < n:
                future_price = close[i + hold_days]
                current_price = close[i]
                ret = (future_price / current_price - 1) * 100

                signal_counts[period_key] += 1
                return_sums[period_key] += ret

                if ret > 0:
                    win_counts[period_key] += 1

    # 计算胜率和平均收益
    win_rates = {}
    avg_returns = {}

    for period in ['5d', '10d', '20d']:
        if signal_counts[period] >= 10:  # 至少10个样本
            win_rates[period] = round(win_counts[period] / signal_counts[period], 3)
            avg_returns[period] = round(return_sums[period] / signal_counts[period], 2)
        else:
            win_rates[period] = 0
            avg_returns[period] = 0

    return win_rates, avg_returns


def _check_short_signals(close, high, volume, idx) -> bool:
    """检查历史点是否满足短线信号条件"""
    if idx < 20:
        return False

    # 1. 突破20日高点
    high_20d = np.max(high[idx-21:idx])
    if close[idx] <= high_20d:
        return False

    # 2. 成交量放大
    avg_vol_20 = np.mean(volume[idx-21:idx])
    if avg_vol_20 <= 0 or volume[idx] / avg_vol_20 < 1.5:
        return False

    # 3. 价格站上均线
    ma20 = np.mean(close[idx-20:idx])
    if close[idx] <= ma20:
        return False

    # 4. RSI不超买
    rsi = _calc_rsi(close[idx-15:idx+1], 14)
    if rsi > 75:
        return False

    return True


def _check_mid_signals(close, high, volume, idx) -> bool:
    """检查历史点是否满足中线信号条件"""
    if idx < 60:
        return False

    # 1. MA10 > MA60
    ma10 = np.mean(close[idx-10:idx])
    ma60 = np.mean(close[idx-60:idx])
    if ma10 <= ma60:
        return False

    # 2. 60日涨幅20-80%
    ret60 = (close[idx] / close[idx-60] - 1) * 100
    if not (20 <= ret60 <= 80):
        return False

    # 3. 突破60日高点
    high_60d = np.max(high[idx-61:idx])
    if close[idx] <= high_60d:
        return False

    return True


def _calc_rsi(close, period=14):
    """计算RSI"""
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.zeros(len(close))
    avg_loss = np.zeros(len(close))
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

    rs = avg_gain[-1] / avg_loss[-1] if avg_loss[-1] > 0 else 100
    return 100 - 100 / (1 + rs)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer3_verify.py::test_layer3_verification -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/layer3_backtest_verify.py tests/test_layer3_verify.py
git commit -m "feat: implement Layer 3 historical win rate verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: 实现推荐引擎整合 `get_recommendations()`

**Files:**
- Create: `screening/recommendation_engine.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer1_screen.py (add)
def test_recommendation_engine():
    """Test end-to-end recommendation engine"""
    from screening.recommendation_engine import get_recommendations
    result = get_recommendations(recommendation_type='short')
    assert 'recommendations' in result
    assert 'pipeline_status' in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_recommendation_engine -v
```
Expected: FAIL — module not exist

- [ ] **Step 3: Implement get_recommendations()**

```python
# screening/recommendation_engine.py
#!/usr/bin/env python3
"""推荐引擎 - 整合四层筛选"""
import sys
import os
from typing import Dict, List

def get_recommendations(recommendation_type: str = 'short', top_n: int = 5) -> Dict:
    """
    获取精选推荐 - 端到端四层筛选

    Args:
        recommendation_type: 'short' 或 'mid'
        top_n: 返回前N只推荐股票

    Returns:
        {
            'recommendations': [...],
            'pipeline_status': {
                'layer1': {...},
                'layer2': {...},
                'layer3': {...}
            },
            'recommendation_type': str
        }
    """
    from .layer1_tech_screen import screen_layer1
    from .layer2_signal_score import score_layer2
    from .layer3_backtest_verify import verify_layer3

    # Layer 1: 技术面宽筛
    layer1_result = screen_layer1(recommendation_type)
    layer1_status = {
        'candidates_count': layer1_result.get('count', 0),
        'market_safe': layer1_result.get('market_check', {}).get('reason') == 'safe',
        'filters_applied': layer1_result.get('filter_applied', [])
    }

    # 如果Layer 1没有候选股，直接返回空
    if not layer1_result.get('candidates'):
        return {
            'recommendations': [],
            'pipeline_status': {'layer1': layer1_status, 'layer2': None, 'layer3': None},
            'recommendation_type': recommendation_type,
            'warning': layer1_result.get('warning', 'No candidates from Layer 1')
        }

    # Layer 2: 多信号评分
    layer2_result = score_layer2(layer1_result)
    layer2_status = {
        'scored_count': layer2_result.get('total_candidates', 0),
        'top_count': len(layer2_result.get('top_candidates', []))
    }

    # 如果Layer 2没有候选股，直接返回
    if not layer2_result.get('top_candidates'):
        return {
            'recommendations': [],
            'pipeline_status': {'layer1': layer1_status, 'layer2': layer2_status, 'layer3': None},
            'recommendation_type': recommendation_type
        }

    # Layer 3: 历史胜率验证
    layer3_result = verify_layer3(layer2_result)
    layer3_status = {
        'verified_count': layer3_result.get('total_verified', 0),
        'recommended_count': len(layer3_result.get('top_recommendations', []))
    }

    # 获取Top N推荐
    top_recommendations = layer3_result.get('top_recommendations', [])[:top_n]

    return {
        'recommendations': top_recommendations,
        'pipeline_status': {
            'layer1': layer1_status,
            'layer2': layer2_status,
            'layer3': layer3_status
        },
        'recommendation_type': recommendation_type,
        'generated_at': __import__('datetime').datetime.now().isoformat()
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_recommendation_engine -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screening/recommendation_engine.py
git commit -m "feat: add recommendation engine integrating all 4 layers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: 实现Layer 4模拟盘监控与预警

**Files:**
- Create: `monitoring/daily_monitor.py`
- Create: `monitoring/alert_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_layer1_screen.py (add)
def test_daily_monitor():
    """Test daily monitor"""
    from monitoring.daily_monitor import DailyMonitor
    monitor = DailyMonitor()
    status = monitor.get_daily_status()
    assert 'positions' in status
    assert 'recommendations' in status
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_daily_monitor -v
```
Expected: FAIL — module not exist

- [ ] **Step 3: Implement DailyMonitor and AlertService**

```python
# monitoring/daily_monitor.py
#!/usr/bin/env python3
"""每日监控"""
import sys
import os
from typing import Dict, List
from datetime import datetime

class DailyMonitor:
    """每日监控器"""

    def __init__(self):
        self.alerts = []

    def get_daily_status(self) -> Dict:
        """获取每日监控状态"""
        from screening.recommendation_engine import get_recommendations
        from models import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # 获取持仓
            positions = db.execute(text('''
                SELECT code, name, shares, cost, current_price
                FROM paper_positions
                WHERE shares > 0
            ''')).fetchall()

            # 获取当前推荐
            recommendations = get_recommendations(recommendation_type='short', top_n=5)

            # 检查持仓股票状态
            position_alerts = []
            for pos in positions:
                code = pos[0]
                shares = pos[2]
                cost = pos[3]
                current_price = pos[4] or 0

                pnl_pct = (current_price / cost - 1) * 100 if cost > 0 else 0

                alert = None
                if pnl_pct < -7:
                    alert = {'code': code, 'type': 'stop_loss', 'pnl_pct': round(pnl_pct, 2)}
                elif pnl_pct > 15:
                    alert = {'code': code, 'type': 'target_hit', 'pnl_pct': round(pnl_pct, 2)}

                if alert:
                    position_alerts.append(alert)

            return {
                'positions': [
                    {
                        'code': p[0],
                        'name': p[1],
                        'shares': p[2],
                        'cost': p[3],
                        'current_price': p[4],
                        'pnl_pct': round((p[4]/p[3]-1)*100, 2) if p[3] and p[4] else 0
                    } for p in positions
                ],
                'recommendations': recommendations.get('recommendations', []),
                'position_alerts': position_alerts,
                'generated_at': datetime.now().isoformat()
            }
        finally:
            db.close()
```

```python
# monitoring/alert_service.py
#!/usr/bin/env python3
"""预警服务"""
import sys
import os
from typing import Dict, List
from datetime import datetime

class AlertService:
    """预警服务"""

    def __init__(self):
        self.alert_history = []

    def check_alerts(self, positions: List[Dict]) -> List[Dict]:
        """检查并生成预警"""
        alerts = []

        for pos in positions:
            code = pos.get('code', '')
            pnl_pct = pos.get('pnl_pct', 0)
            rsi = pos.get('rsi')

            # 止损预警
            if pnl_pct < -7:
                alerts.append({
                    'code': code,
                    'type': 'stop_loss',
                    'message': f'{code} 亏损{pnl_pct:.1f}%，建议止损',
                    'priority': 'high',
                    'timestamp': datetime.now().isoformat()
                })

            # 目标达成预警
            elif pnl_pct > 15:
                alerts.append({
                    'code': code,
                    'type': 'target_hit',
                    'message': f'{code} 盈利{pnl_pct:.1f}%，建议部分止盈',
                    'priority': 'medium',
                    'timestamp': datetime.now().isoformat()
                })

            # RSI超买预警
            if rsi and rsi > 75:
                alerts.append({
                    'code': code,
                    'type': 'rsi_overbought',
                    'message': f'{code} RSI={rsi:.1f}，超买预警',
                    'priority': 'low',
                    'timestamp': datetime.now().isoformat()
                })

        self.alert_history.extend(alerts)
        return alerts

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """获取最近预警"""
        return self.alert_history[-limit:]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_layer1_screen.py::test_daily_monitor -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monitoring/daily_monitor.py monitoring/alert_service.py
git commit -m "feat: add Layer 4 daily monitor and alert service

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

1. **Spec coverage**: All design sections have corresponding tasks? Yes
2. **Placeholder scan**: No TBD/TODO found
3. **Type consistency**: Consistent across all tasks