#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务配置中心 — 修复 Sprint3 配置分散问题

把所有硬编码的 magic number 集中到一处, 支持:
  - YAML 文件加载 (默认 business_config.yaml)
  - 环境变量覆盖 (前缀 BUSINESS_)
  - 运行时动态刷新 (不需重启进程)

配置项:
  - 交易费率: 佣金/印花税/过户费/最低佣金
  - 批量限额: 回测股票数/AI 并发数/AI 单日预算
  - 大盘阈值: 牛熊判定/强势股阈值/涨停判定
  - 策略阈值: 各策略的 min_score/参数
"""
import os
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 默认值(若 YAML 缺失某字段, 兜底)
_DEFAULTS = {
    "trading": {
        "commission_rate": 0.00025,       # 万 2.5 佣金
        "commission_min": 5.0,             # 最低 5 元
        "stamp_tax_rate": 0.001,           # 印花税 万 10 (卖出)
        "transfer_fee_rate": 0.00001,      # 过户费 万 0.1
    },
    "batch_limits": {
        "backtest_max_codes": 50,          # 单次批量回测股票数
        "ai_concurrent_jobs": 4,            # AI 辩论最大并发
        "ai_daily_budget_usd": 20.0,       # 单日 AI 调用预算
        "screening_top_n": 30,              # 筛选 TopN
    },
    "market_thresholds": {
        "bull_bear_score": 60,             # 牛熊分界(>60 牛, <40 熊)
        "strong_stock_change_pct": 5.0,    # 强势股日内涨幅阈值
        "limit_up_change_pct": 9.5,        # 涨停判定阈值(主板)
        "limit_down_change_pct": -9.5,     # 跌停判定阈值
    },
    "strategy": {
        "ma_cross_fast": 5,                # 短期均线
        "ma_cross_slow": 20,               # 长期均线
        "jichang_min_score": 60,           # 击掌策略最低分
        "youzi_min_score": 70,             # 游资策略最低分
    },
}


class BusinessConfig:
    """
    单例业务配置, 第一次访问时加载, 之后缓存。
    业务代码应当 `from business_config import cfg; cfg.trading.commission_rate`
    """

    _instance: Optional["BusinessConfig"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._data = {k: dict(v) for k, v in _DEFAULTS.items()}
        # 加载 YAML(如存在)
        self._yaml_path = Path(__file__).parent / "business_config.yaml"
        if self._yaml_path.exists():
            try:
                import yaml
                with open(self._yaml_path, encoding="utf-8") as f:
                    user_cfg = yaml.safe_load(f) or {}
                for section, values in user_cfg.items():
                    if section in self._data and isinstance(values, dict):
                        self._data[section].update(values)
                    else:
                        self._data[section] = values
                logger.info(f"Loaded business config from {self._yaml_path}")
            except Exception as e:
                logger.warning(f"Failed to load {self._yaml_path}: {e}; using defaults")
        # 环境变量覆盖(BUSINESS_TRADING_COMMISSION_RATE 等)
        self._apply_env_overrides()

    def _apply_env_overrides(self):
        for section in self._data:
            for key in list(self._data[section].keys()):
                env_key = f"BUSINESS_{section.upper()}_{key.upper()}"
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    try:
                        # 尝试数值转换
                        original = self._data[section][key]
                        if isinstance(original, bool):
                            self._data[section][key] = env_val.lower() in ("1", "true", "yes")
                        elif isinstance(original, int):
                            self._data[section][key] = int(env_val)
                        elif isinstance(original, float):
                            self._data[section][key] = float(env_val)
                        else:
                            self._data[section][key] = env_val
                    except ValueError as e:
                        logger.warning(f"Invalid env {env_key}={env_val}: {e}")

    def reload(self):
        """热重载(供配置文件 watch dog 调用)"""
        self._data = {k: dict(v) for k, v in _DEFAULTS.items()}
        self._init()
        logger.info("Business config reloaded")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def __getattr__(self, name: str):
        # 支持 cfg.trading.commission_rate 形式
        if name.startswith("_"):
            raise AttributeError(name)
        data = self.__dict__.get("_data", {})
        if name in data:
            return _SectionProxy(data[name])
        raise AttributeError(f"Unknown config section: {name}")


class _SectionProxy:
    """支持 cfg.trading.commission_rate 链式访问"""
    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Unknown config key: {name}")

    def __repr__(self):
        return f"ConfigSection({self._data})"


# 全局单例
cfg = BusinessConfig()


if __name__ == "__main__":
    # 自检
    print("Trading commission_rate:", cfg.trading.commission_rate)
    print("Batch backtest max codes:", cfg.batch_limits.backtest_max_codes)
    print("Bull/bear threshold:", cfg.market_thresholds.bull_bear_score)
    print("Strategy jichang min score:", cfg.strategy.jichang_min_score)
