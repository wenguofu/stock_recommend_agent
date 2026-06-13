#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定量估值模型 — 针对已大幅上涨标的的成长调整估值

核心逻辑：
  1. 如果行业利润半年翻倍 → Forward PE = 当前PE / 2
  2. PEG = PE / 盈利增速 → PEG < 1 可能仍被低估
  3. 成长调整公允价值 = 当前EPS × 合理PE × (1 + 增速调整)
  4. DCF简化版: 3年现金流折现 + 终值

行业展望增速由用户输入或从板块预测数据自动推断。
"""

import math
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValuationInput:
    """估值输入参数"""
    code: str
    name: str = ""
    current_price: float = 0.0
    eps_ttm: float = 0.0          # 每股收益(TTM)
    pe_ttm: float = 0.0           # 当前PE(TTM)
    pb: float = 0.0               # 市净率
    roe: float = 0.0              # ROE(%)
    revenue_yoy: float = 0.0      # 营收同比增速(%)
    profit_yoy: float = 0.0       # 利润同比增速(%)
    gross_margin: float = 0.0     # 毛利率(%)
    debt_ratio: float = 0.0       # 资产负债率(%)

    # 行业展望参数（用户输入或自动推断）
    industry_growth_6m: float = 0.0    # 半年行业利润增速预估(%)
    industry_growth_1y: float = 0.0    # 一年行业利润增速预估(%)
    industry_growth_2y: float = 0.0    # 两年行业利润增速预估(%)
    sector_outlook: str = ""           # 行业展望评级 S/A/B/C

    # 可选：板块名称用于自动推断
    sector_name: str = ""

    # Sprint 7: 成长股分类
    growth_class: str = ""            # "growth" / "value" / "cyclical" / "" (待推断)
    growth_class_reason: str = ""     # 分类理由, 供前端展示

    # 机构预测元数据 (Sprint 6 优化: 自动使用机构预测净利润)
    forecast_source: str = ""        # "institutional" / "user" / "none"
    forecast_net_profit_2025a: float = 0.0   # 机构预测: 2025A 实际净利润(亿)
    forecast_net_profit_2026e: float = 0.0   # 机构预测: 2026E 净利润(亿)
    forecast_net_profit_2027e: float = 0.0   # 机构预测: 2027E 净利润(亿)
    forecast_eps_2026e: float = 0.0
    forecast_eps_2027e: float = 0.0
    forecast_analyst_count: int = 0
    forecast_rating_label: str = ""
    forecast_updated_at: str = ""


@dataclass
class ValuationResult:
    """估值结果"""
    # 核心指标
    current_pe: float = 0.0
    forward_pe_6m: float = 0.0      # 半年后Forward PE
    forward_pe_1y: float = 0.0      # 一年后Forward PE
    forward_pe_2y: float = 0.0      # 两年后Forward PE
    peg_ratio: float = 0.0          # PEG = PE / 增速
    peg_verdict: str = ""           # PEG判断

    # 公允价值
    fair_value_current: float = 0.0  # 当前合理估值
    fair_value_growth: float = 0.0   # 成长调整后公允价值
    margin_of_safety: float = 0.0    # 安全边际(%)

    # DCF简化版
    dcf_value: float = 0.0
    dcf_upside: float = 0.0         # DCF相对当前价格的上行空间(%)
    dcf_margin: float = 0.0         # Sprint 7: DCF安全边际 (DCF-price)/DCF

    # 综合评分
    composite_score: float = 0.0     # 0-100
    rating: str = ""                # 强烈推荐/推荐/持有/谨慎/回避
    summary: str = ""               # 一句话总结

    # 明细
    detail: Dict = field(default_factory=dict)


def _safe_float(v, default=0.0):
    """安全转换浮点数"""
    try:
        return float(v) if v is not None else default
    except (ValueError, TypeError):
        return default


# ── 成长股分类 (Sprint 7 P0 + P1.1 扩展) ──────────────────────────────
# 行业关键词: 命中 → 倾向 growth
GROWTH_SECTOR_KEYWORDS = [
    "AI", "人工智能", "光模块", "光通信", "CPO", "光器件",
    "半导体", "芯片", "集成电路", "IC设计", "存储", "封测",
    "创新药", "生物医药", "CXO", "医疗器械", "疫苗",
    "新能源", "锂电池", "光伏", "储能", "氢能", "钠电",
    "机器人", "减速器", "机器视觉",
    "卫星", "商业航天", "低空",
    "数字经济", "数据要素", "信创", "网络安全", "鸿蒙",
    "PCB", "先进封装",
    "无人驾驶", "智能驾驶", "车路云",
    "固态电池",
    "量子",
    "AR", "VR", "XR", "折叠屏",
    # 消费电子/智能终端 (蓝思/立讯/歌尔/欧菲光/长盈精密)
    "消费电子", "果链", "苹果概念", "华为概念", "小米概念",
    "玻璃盖板", "玻璃外壳", "陶瓷外观", "结构件", "连接器", "声学",
    "摄像头", "镜头", "CIS", "光学元件", "指纹识别", "Face ID",
    "智能穿戴", "TWS", "智能手表", "AI眼镜", "智能耳机",
    "PCB", "FPC", "软板", "硬板", "IC载板",
    "封装", "封测", "测试设备",
    "代工", "ODM", "OEM",
    # 生物医药/医疗器械
    "CRO", "CDMO", "原料药", "仿制药", "化学药", "中药",
    "体外诊断", "IVD", "基因测序", "精准医疗", "细胞治疗",
    "医美", "口腔医疗", "眼科医疗", "辅助生殖",
    "医疗器械", "医疗设备", "高值耗材", "低值耗材",
    # 新能源车产业链
    "锂电材料", "正极材料", "负极材料", "电解液", "隔膜", "锂电设备",
    "电池", "动力电池", "储能电池", "BMS",
    "电控", "电机", "热管理", "轻量化", "一体化压铸",
    "充电桩", "换电站", "充电桩",
    "汽车电子", "智能座舱", "HUD", "激光雷达", "毫米波雷达",
    "车联网", "V2X",
    # 工业母机/机器人
    "工业母机", "数控机床", "CNC", "刀具",
    "工业机器人", "协作机器人", "服务机器人", "扫地机器人",
    "机器狗", "四足机器人",
    # 通信
    "5G", "6G", "通信设备", "光通信", "光器件", "光模块", "CPO",
    "光芯片", "光器件", "连接器",
    "卫星互联网", "北斗", "导航",
    "运营商", "通信服务",
    # 半导体
    "晶圆", "晶圆厂", "代工", "设备", "光刻机", "刻蚀机", "薄膜沉积",
    "EDA", "IP授权", "IC设计", "模拟芯片", "射频", "电源管理",
    "存储芯片", "DRAM", "NAND", "NOR", "MCU", "SoC",
    "传感器", "MEMS", "CIS", "图像传感器",
    # 军工
    "军工", "航空装备", "航天装备", "船舶装备", "兵器装备",
    "军用通信", "雷达", "导弹", "无人机军用",
    # 传媒/游戏
    "游戏", "影视", "动漫", "出版", "教育",
    "MCN", "直播", "短视频", "网红",
    # 软件/互联网
    "SaaS", "PaaS", "IaaS", "云服务", "云计算",
    "网络安全", "信息安全", "数据安全",
    "操作系统", "数据库", "中间件",
    "金融IT", "医疗IT", "政务IT",
    "人工智能", "大模型", "算力", "AIGC", "AI应用",
]
# 去重 (保留顺序)
GROWTH_SECTOR_KEYWORDS = list(dict.fromkeys(GROWTH_SECTOR_KEYWORDS))

# 行业关键词: 命中 → 倾向 cyclical
CYCLICAL_SECTOR_KEYWORDS = [
    "煤炭", "钢铁", "有色", "化工", "化纤", "造纸", "玻璃",
    "水泥", "建材", "工程机械", "航运", "航空", "化工",
    "猪肉", "鸡苗", "养殖", "种业", "饲料", "农产品",
    "石油", "石化", "天然气",
    "汽车整车", "地产", "银行", "保险", "证券", "多元金融",
    "稀土", "锂矿", "钴", "镍",
    "影视", "游戏", "传媒", "广告",
]


def classify_growth_stock(inp: ValuationInput) -> str:
    """
    综合判定股票属于 growth / value / cyclical

    判定规则 (按优先级):
      1. 行业关键词命中 → 直接分类
      2. 机构预测增速:
         - 增速 > 50% (且 ROE > 10%) → growth
         - 增速 < 5% → value
         - 增速中等 → 看 ROE
      3. ROE:
         - > 15% + 增速 > 20% → growth
         - < 5% → value
      4. 默认 → value (保守)
    """
    reasons = []
    sector = (inp.sector_name or "").strip()

    # 1. 行业关键词 (最强信号)
    sector_lower = sector.lower()
    for kw in GROWTH_SECTOR_KEYWORDS:
        if kw in sector or kw.lower() in sector_lower:
            inp.growth_class = "growth"
            inp.growth_class_reason = f"行业 [{sector}] 命中成长股关键词 [{kw}]"
            return "growth"
    for kw in CYCLICAL_SECTOR_KEYWORDS:
        if kw in sector or kw.lower() in sector_lower:
            inp.growth_class = "cyclical"
            inp.growth_class_reason = f"行业 [{sector}] 命中周期股关键词 [{kw}]"
            return "cyclical"

    # 2. 增速判定
    growth = inp.industry_growth_1y  # 1y 年化增速
    if growth == 0 and inp.forecast_net_profit_2025a > 0 and inp.forecast_net_profit_2026e > 0:
        # 从机构预测重算 1y 增速
        growth = (inp.forecast_net_profit_2026e - inp.forecast_net_profit_2025a) / inp.forecast_net_profit_2025a * 100
    if growth == 0 and inp.forecast_eps_2026e > 0 and inp.eps_ttm > 0:
        growth = (inp.forecast_eps_2026e - inp.eps_ttm) / inp.eps_ttm * 100

    if growth > 50 and inp.roe >= 10:
        inp.growth_class = "growth"
        inp.growth_class_reason = f"高增速 {growth:.0f}% + ROE {inp.roe:.1f}% → 成长股"
        return "growth"
    if growth < 5 and growth != 0:
        inp.growth_class = "value"
        inp.growth_class_reason = f"低增速 {growth:.1f}% → 价值股"
        return "value"

    # 3. ROE 判定
    if inp.roe >= 15 and growth >= 20:
        inp.growth_class = "growth"
        inp.growth_class_reason = f"ROE {inp.roe:.1f}% + 增速 {growth:.0f}% → 成长股"
        return "growth"
    if inp.roe > 0 and inp.roe < 5 and growth < 15:
        inp.growth_class = "value"
        inp.growth_class_reason = f"ROE {inp.roe:.1f}% 低 + 增速 {growth:.0f}% 低 → 价值股"
        return "value"

    # 4. 中等增速 + 中等 ROE, 倾向 growth (A股大部分高增长票都是这种)
    if growth > 15:
        inp.growth_class = "growth"
        inp.growth_class_reason = f"中等增速 {growth:.0f}% → 倾向成长股 (待行业确认)"
        return "growth"

    # 默认: value
    inp.growth_class = "value"
    inp.growth_class_reason = f"无明显信号 (增速 {growth:.0f}%, ROE {inp.roe:.1f}%) → 默认价值股"
    return "value"


# 不同分类的估值参数
GROWTH_CLASS_PARAMS = {
    "growth": {
        "base_pe": 30,         # 成长股合理基准 PE (光模块/AI 龙头 PE 30-50 是常态)
        "fair_pe_multiplier": 5.0,  # fair_pe 上限 = base_pe × 5
        "score_bonus": 0,      # 不额外加分 (避免双重计算)
        "label": "成长股",
    },
    "value": {
        "base_pe": 15,         # 价值股合理基准 PE
        "fair_pe_multiplier": 2.0,
        "score_bonus": 0,
        "label": "价值股",
    },
    "cyclical": {
        "base_pe": 12,         # 周期股合理基准 PE (取 PB 估值更合适)
        "fair_pe_multiplier": 1.5,
        "score_bonus": 0,
        "label": "周期股",
    },
}


def calculate_valuation(inp: ValuationInput, momentum_adjustment: float = 0) -> ValuationResult:
    """
    核心估值计算。

    Forward PE逻辑:
      Forward PE = Current PE / (1 + growth_rate)
      例: PE=60, 半年利润翻倍(growth=100%) → Forward PE = 60/2 = 30

    PEG逻辑:
      PEG = PE / 盈利增速(%)
      PEG < 0.5: 极度低估, < 1: 合理偏低, 1-2: 合理, > 2: 高估

    Args:
        inp: 估值输入参数
        momentum_adjustment: 动量调整分 (-10 ~ +10), 来自短期价格趋势分析
                            + 正分: 趋势向上/暴跌反弹
                            - 负分: 顶部背离/追高风险
    """
    result = ValuationResult()

    pe = inp.pe_ttm
    price = inp.current_price
    eps = inp.eps_ttm
    profit_growth = inp.profit_yoy  # 历史利润增速

    # 如果没有PE但有价格和EPS，计算PE
    if pe <= 0 and price > 0 and eps > 0:
        pe = price / eps

    # 如果没有EPS但有PE和价格，反推EPS
    if eps <= 0 and pe > 0 and price > 0:
        eps = price / pe

    result.current_pe = round(pe, 2)
    result.detail['eps_ttm'] = round(eps, 4)
    result.detail['current_price'] = round(price, 2)

    # ── 1. Forward PE 计算 ──
    # 使用行业展望增速 + 历史增速中较高的那个
    growth_6m = max(inp.industry_growth_6m, profit_growth * 0.5)  # 半年
    growth_1y = max(inp.industry_growth_1y, profit_growth)         # 一年
    growth_2y = max(inp.industry_growth_2y, profit_growth * 2)     # 两年(粗略)

    if growth_6m > 0:
        result.forward_pe_6m = round(pe / (1 + growth_6m / 100), 2)
    if growth_1y > 0:
        result.forward_pe_1y = round(pe / (1 + growth_1y / 100), 2)
    if growth_2y > 0:
        result.forward_pe_2y = round(pe / (1 + growth_2y / 100), 2)

    result.detail['effective_growth_6m'] = round(growth_6m, 1)
    result.detail['effective_growth_1y'] = round(growth_1y, 1)
    result.detail['industry_growth_input'] = inp.industry_growth_1y

    # ── 1.5 Sprint 7 v2: Forward PE (用机构预测 EPS) ──
    # PE(TTM) 会因为单季亏损/低基数失真, Forward PE(2026E) 更能反映"现在买未来"的估值
    # 保留 TTM PE 字段, 同时新增 pe_2026e
    if inp.forecast_eps_2026e > 0 and price > 0:
        pe_2026e = price / inp.forecast_eps_2026e
        result.detail['pe_2026e'] = round(pe_2026e, 2)
        result.detail['pe_source'] = 'forward_2026e'
        # 如果 forward PE 更合理, 用它替代 TTM PE 做 PEG 和评分
        if pe_2026e > 0 and pe_2026e < pe:
            pe = pe_2026e
            eps = inp.forecast_eps_2026e
            result.current_pe = round(pe, 2)
            result.detail['eps_ttm'] = round(eps, 4)  # 用 forecast 替代
    elif inp.forecast_eps_2026e == 0:
        result.detail['pe_source'] = 'ttm (无机构预测)'

    # ── 2. PEG 计算 ──
    effective_growth = growth_1y if growth_1y > 0 else profit_growth
    if pe > 0 and effective_growth > 0:
        result.peg_ratio = round(pe / effective_growth, 2)
    elif pe > 0 and profit_growth > 0:
        result.peg_ratio = round(pe / profit_growth, 2)

    if result.peg_ratio <= 0:
        result.peg_verdict = "数据不足，无法判断"
    elif result.peg_ratio < 0.5:
        result.peg_verdict = "极度低估 — 高增速完全消化了高PE"
    elif result.peg_ratio < 1.0:
        result.peg_verdict = "合理偏低 — 成长性能支撑当前估值"
    elif result.peg_ratio < 2.0:
        result.peg_verdict = "合理区间 — 估值与增速基本匹配"
    elif result.peg_ratio < 3.0:
        result.peg_verdict = "偏贵 — 当前价格已部分透支成长预期"
    else:
        result.peg_verdict = "严重高估 — 即使考虑成长性也偏贵"

    # ── 3. 成长调整公允价值 ──
    # Sprint 7: 先做成长股分类, 再用对应类别的 base_pe
    if not inp.growth_class:
        classify_growth_stock(inp)

    class_params = GROWTH_CLASS_PARAMS.get(inp.growth_class, GROWTH_CLASS_PARAMS["value"])
    base_pe = class_params["base_pe"]
    fair_pe_multiplier = class_params["fair_pe_multiplier"]

    # 行业展望微调 (±3)
    if inp.sector_outlook == 'S':
        base_pe += 3
    elif inp.sector_outlook == 'A':
        base_pe += 1
    elif inp.sector_outlook == 'C':
        base_pe -= 3

    # 成长调整: fair_pe = base_pe × (1 + growth_rate/100) 但上限 base_pe × multiplier
    if effective_growth > 0:
        fair_pe = min(base_pe * (1 + effective_growth / 100), base_pe * fair_pe_multiplier)
    else:
        fair_pe = base_pe

    if eps > 0:
        result.fair_value_current = round(eps * base_pe, 2)
        result.fair_value_growth = round(eps * fair_pe, 2)

    if result.fair_value_growth > 0 and price > 0:
        result.margin_of_safety = round(
            (result.fair_value_growth - price) / result.fair_value_growth * 100, 1
        )

    result.detail['base_pe'] = base_pe
    result.detail['fair_pe'] = round(fair_pe, 1)
    result.detail['sector_outlook'] = inp.sector_outlook or 'N/A'
    # Sprint 7: 成长股分类
    result.detail['growth_class'] = inp.growth_class
    result.detail['growth_class_reason'] = inp.growth_class_reason
    result.detail['growth_class_label'] = class_params.get("label", "")
    # Sprint 7: 标记 fair_value_current 为"无增长假设参考" (对成长股有误导)
    # 真正的安全边际应以 DCF 为锚
    result.detail['fair_value_current_is_baseline'] = True
    result.detail['fair_value_current_note'] = (
        "无增长假设参考值 (适用低速/无增长资产). "
        "对高成长股, 请参考 fair_value_growth 和 dcf_value"
    )

    # ── 4. DCF简化版 (Sprint 7 优化 v3) ──
    # 关键: base FCF 必须是 TTM (当前) 现金流, 不能用 forecast (否则等于 1-2 年后折现, 数值翻倍)
    # 关键: 3 年增速采用机构预测 (6m/1y/2y), 而非单一 effective_growth
    # 兜底: 若 TTM EPS ≤ 0 (亏损), 才用机构预测 EPS (亏损公司必须用未来现金流)
    # 注: 必须用 inp.eps_ttm (原始 TTM), 不能用上面的局部变量 eps (PE 修复时已被覆盖)
    dcf_base_eps = inp.eps_ttm
    dcf_eps_source = "ttm"
    if inp.eps_ttm <= 0 and inp.forecast_eps_2026e > 0:
        # TTM 亏损 → 用机构预测 (亏损公司只能用未来现金流估算)
        dcf_base_eps = inp.forecast_eps_2026e
        dcf_eps_source = "forecast_2026e (TTM 亏损兜底)"

    if dcf_base_eps > 0:
        fcf = dcf_base_eps * 0.7
        discount_rate = 0.10
        terminal_growth = 0.03

        # 3年增速序列: 优先用机构预测的 6m/1y/2y, 否则用 effective_growth
        year_growths = []
        if growth_6m > 0:
            year_growths.append(growth_6m)
        else:
            year_growths.append(effective_growth if effective_growth > 0 else 5)
        if growth_1y > 0:
            year_growths.append(growth_1y)
        else:
            year_growths.append(year_growths[0])  # 用 6m 代替
        if growth_2y > 0:
            year_growths.append(growth_2y)
        else:
            # 兜底: 用 1y 的 80% (增速衰减)
            year_growths.append(year_growths[1] * 0.8 if year_growths[1] > 0 else 5)

        # 3年现金流折现 (按各年增速)
        dcf_sum = 0
        cumulative_factor = 1.0
        for year, g in enumerate(year_growths[:3], start=1):
            cumulative_factor *= (1 + g / 100)
            projected_fcf = fcf * cumulative_factor
            dcf_sum += projected_fcf / ((1 + discount_rate) ** year)
        # 终值: 用第3年 FCF × (1+g_terminal) / (r-g_terminal), 折现到现值
        terminal_value = (fcf * cumulative_factor * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / ((1 + discount_rate) ** 3)

        result.dcf_value = round(dcf_sum + terminal_pv, 2)
        if price > 0:
            result.dcf_upside = round((result.dcf_value / price - 1) * 100, 1)
            # Sprint 7: DCF 安全边际 (DCF - price) / DCF, 是更可靠的安全边际指标
            result.dcf_margin = round((result.dcf_value - price) / result.dcf_value * 100, 1)

        result.detail['dcf_base_eps'] = round(dcf_base_eps, 4)
        result.detail['dcf_eps_source'] = dcf_eps_source
        result.detail['dcf_year_growths'] = [round(g, 1) for g in year_growths[:3]]

        result.detail['dcf_annual_fcf'] = round(fcf, 4)
        result.detail['dcf_discount_rate'] = discount_rate
        result.detail['dcf_terminal_growth'] = terminal_growth

    # ── 5. 综合评分 (Sprint 7: DCF 为锚, 提升机构一致性维度) ──
    # 总分 100, 基准 50
    #   DCF 上行/下行空间   25 分 (新增主权重)
    #   PEG 估值合理性     20 分
    #   成长安全边际       20 分
    #   机构一致性         15 分 (新增)
    #   ROE 质量            5 分
    #   行业展望            5 分
    #   Forward PE 1y       5 分
    #   动量/趋势           5 分 (新增, 由 momentum_adjustment 传入)
    score = 50  # 基准分

    # ── DCF 价值锚 (25 分) ──
    # DCF 是未来现金流的折现, 是估值最可靠的锚
    # dcf_upside = (dcf - price) / price * 100
    if result.dcf_upside > 50:
        score += 25
    elif result.dcf_upside > 20:
        score += 18
    elif result.dcf_upside > 5:
        score += 10
    elif result.dcf_upside > -5:
        score += 0
    elif result.dcf_upside > -20:
        score -= 10
    elif result.dcf_upside > -40:
        score -= 18
    else:
        score -= 25

    # ── PEG 估值合理性 (20 分) ──
    if result.peg_ratio > 0:
        if result.peg_ratio < 0.5:
            score += 20
        elif result.peg_ratio < 0.8:
            score += 14
        elif result.peg_ratio < 1.0:
            score += 7
        elif result.peg_ratio < 1.5:
            score += 0
        elif result.peg_ratio < 2.0:
            score -= 7
        elif result.peg_ratio < 3.0:
            score -= 14
        else:
            score -= 20

    # ── 成长安全边际 (20 分) ──
    # margin_of_safety = (fair_value_growth - price) / fair_value_growth
    if result.margin_of_safety > 50:
        score += 20
    elif result.margin_of_safety > 20:
        score += 14
    elif result.margin_of_safety > 0:
        score += 6
    elif result.margin_of_safety > -20:
        score -= 4
    elif result.margin_of_safety > -50:
        score -= 12
    else:
        score -= 20

    # ── 机构一致性 (15 分) ──
    # 评级 (买入/增持/中性/减持) + 覆盖家数加成
    rating_label = inp.forecast_rating_label or ""
    if "买入" in rating_label or "强烈推荐" in rating_label:
        score += 12
    elif "增持" in rating_label or "推荐" in rating_label:
        score += 7
    elif "中性" in rating_label:
        score += 0
    elif "减持" in rating_label or "卖出" in rating_label:
        score -= 10
    # 覆盖家数加成 (10+ 家机构覆盖 = 数据可靠)
    if inp.forecast_analyst_count >= 20:
        score += 3
    elif inp.forecast_analyst_count >= 10:
        score += 1
    elif inp.forecast_analyst_count < 3 and inp.forecast_source == "institutional":
        score -= 2  # 覆盖太少, 共识度低

    # ── ROE/质量 (5 分) ──
    if inp.roe > 20:
        score += 5
    elif inp.roe > 15:
        score += 3
    elif inp.roe > 10:
        score += 1
    elif inp.roe > 0:
        score += 0
    else:
        score -= 3

    # ── 行业展望 (5 分) ──
    if inp.sector_outlook == 'S':
        score += 5
    elif inp.sector_outlook == 'A':
        score += 3
    elif inp.sector_outlook == 'B':
        score += 1
    elif inp.sector_outlook == 'C':
        score -= 3

    # ── Forward PE 1y (5 分) ──
    if result.forward_pe_1y > 0:
        if result.forward_pe_1y < 20:
            score += 5
        elif result.forward_pe_1y < 30:
            score += 3
        elif result.forward_pe_1y < 45:
            score += 0
        else:
            score -= 3

    # ── 动量/趋势 (5 分, 由外部传入) ──
    # momentum_adjustment 范围: -10 ~ +10, 在这里截断为 ±5
    score += max(-5, min(5, momentum_adjustment))

    result.composite_score = max(0, min(100, round(score)))
    # 把动量分存到 detail 供前端展示
    result.detail['momentum_adjustment'] = momentum_adjustment

    # ── 6. 评级 ──
    if result.composite_score >= 80:
        result.rating = "强烈推荐 — 成长性充分消化高估值，安全边际充足"
    elif result.composite_score >= 65:
        result.rating = "推荐 — 估值合理，成长前景支撑当前价格"
    elif result.composite_score >= 50:
        result.rating = "持有 — 估值与成长基本匹配，需关注行业变化"
    elif result.composite_score >= 35:
        result.rating = "谨慎 — 估值偏高，成长可能不足以支撑当前价格"
    else:
        result.rating = "回避 — 估值严重偏离基本面，建议等待回调"

    # ── 7. 一句话总结 ──
    parts = []
    if effective_growth > 0 and pe > 0:
        parts.append(f"当前PE {pe:.1f}倍")
        if result.peg_ratio > 0:
            parts.append(f"PEG {result.peg_ratio:.2f}")
        if result.forward_pe_1y > 0:
            parts.append(f"Forward PE(1y) {result.forward_pe_1y:.1f}倍")
    if result.margin_of_safety != 0:
        direction = "上行空间" if result.margin_of_safety > 0 else "下行风险"
        parts.append(f"{direction} {abs(result.margin_of_safety):.0f}%")

    result.summary = " | ".join(parts) if parts else "数据不足以完成估值"

    return result


def _parse_yi_value(v) -> float:
    """解析 "1.2亿" / "125.3 亿" / "0.85" 等格式, 返回数值(以亿为单位)"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # 提取首个数字(含小数点和负号)
    import re
    m = re.search(r'-?\d+\.?\d*', s)
    if not m:
        return 0.0
    return _safe_float(m.group(0))


def get_institutional_forecast(code: str) -> Optional[Dict]:
    """
    从 prediction_aggregates 表读取机构预测。

    Returns:
        dict: {
            'net_profit_2025a': float (亿),
            'net_profit_2026e': float (亿),
            'net_profit_2027e': float (亿),
            'eps_2026e': float,
            'eps_2027e': float,
            'analyst_count': int,
            'rating_label': str,
            'updated_at': str,
            'has_data': bool,
        }
        或 None (表不存在/读失败)
    """
    try:
        from sqlalchemy import text
        from models import get_db
        db = next(get_db())
        try:
            row = db.execute(
                text("SELECT net_profit_2025a, net_profit_2026e, net_profit_2027e, "
                     "net_profit_2028e, eps_2025a, eps_2026e, eps_2027e, eps_2028e, "
                     "rating_label, analyst_count, updated_at "
                     "FROM prediction_aggregates WHERE code = :code LIMIT 1"),
                {"code": code}
            ).fetchone()
            if not row:
                return None
            d = dict(row._mapping)
            np_25 = _parse_yi_value(d.get('net_profit_2025a'))
            np_26 = _parse_yi_value(d.get('net_profit_2026e'))
            np_27 = _parse_yi_value(d.get('net_profit_2027e'))
            eps_26 = _parse_yi_value(d.get('eps_2026e'))
            eps_27 = _parse_yi_value(d.get('eps_2027e'))
            analyst_count = _safe_int(d.get('analyst_count'))
            has_data = (np_25 > 0 and np_26 > 0) or eps_26 > 0
            # updated_at 可能是 datetime 或字符串, 统一转为 ISO 字符串
            updated_at_raw = d.get('updated_at')
            if hasattr(updated_at_raw, 'isoformat'):
                updated_at_str = updated_at_raw.isoformat()
            else:
                updated_at_str = str(updated_at_raw or '').strip()
            return {
                'net_profit_2025a': np_25,
                'net_profit_2026e': np_26,
                'net_profit_2027e': np_27,
                'eps_2026e': eps_26,
                'eps_2027e': eps_27,
                'analyst_count': analyst_count,
                'rating_label': str(d.get('rating_label') or '').strip(),
                'updated_at': updated_at_str,
                'has_data': has_data,
            }
        finally:
            db.close()
    except Exception as e:
        # 表不存在/字段不存在/无 MySQL — 静默返回 None
        logger.debug(f"get_institutional_forecast({code}): {e}")
        return None


def _safe_int(v, default=0) -> int:
    try:
        if v is None or v == '':
            return default
        return int(float(v))
    except (ValueError, TypeError):
        return default


def auto_fill_institutional_forecast(inp: ValuationInput) -> ValuationInput:
    """
    从 prediction_aggregates 表读取机构预测, 计算行业增速, 填入 inp.

    优先级:
      - 用户已手动输入 industry_growth_6m/1y (>0) → 标记 "user", 不覆盖
      - 有 2025A + 2026E 净利润 → 计算 6m ≈ (2026E - 2025A)/2025A,
                                    1y ≈ (2027E - 2025A)/2025A (CAGR×2)
      - 仅有 EPS 预测 → 用 (eps_2026e / eps_ttm - 1) 推算
    """
    fc = get_institutional_forecast(inp.code)
    if not fc or not fc.get('has_data'):
        # 没有机构预测数据, 标记数据源
        if inp.industry_growth_6m > 0 or inp.industry_growth_1y > 0:
            inp.forecast_source = "user"
        elif not inp.forecast_source:
            inp.forecast_source = "none"
        return inp

    # 记录原始预测数据
    inp.forecast_net_profit_2025a = fc['net_profit_2025a']
    inp.forecast_net_profit_2026e = fc['net_profit_2026e']
    inp.forecast_net_profit_2027e = fc['net_profit_2027e']
    inp.forecast_eps_2026e = fc['eps_2026e']
    inp.forecast_eps_2027e = fc['eps_2027e']
    inp.forecast_analyst_count = fc['analyst_count']
    inp.forecast_rating_label = fc['rating_label']
    inp.forecast_updated_at = fc['updated_at']

    # 用户已输入则保留, 标注 "user"
    user_provided_6m = inp.industry_growth_6m > 0
    user_provided_1y = inp.industry_growth_1y > 0
    if user_provided_6m and user_provided_1y:
        inp.forecast_source = "user"
        return inp

    # 计算 6m (半年) 增速 = (2026E - 2025A) / 2025A
    growth_6m = 0.0
    if fc['net_profit_2025a'] > 0 and fc['net_profit_2026e'] > 0:
        growth_6m = (fc['net_profit_2026e'] - fc['net_profit_2025a']) / fc['net_profit_2025a'] * 100
    elif fc['eps_2026e'] > 0 and inp.eps_ttm > 0:
        growth_6m = (fc['eps_2026e'] - inp.eps_ttm) / inp.eps_ttm * 100

    # 计算 1y (年化) 增速 = ((2027E / 2025A)^(1/2) - 1) * 100
    growth_1y = 0.0
    if fc['net_profit_2025a'] > 0 and fc['net_profit_2027e'] > 0:
        ratio = fc['net_profit_2027e'] / fc['net_profit_2025a']
        if ratio > 0:
            growth_1y = (pow(ratio, 0.5) - 1) * 100
    elif fc['net_profit_2025a'] > 0 and fc['net_profit_2026e'] > 0:
        # 无 2027 数据, 用 2026E 同比代替
        growth_1y = growth_6m
    elif fc['eps_2027e'] > 0 and inp.eps_ttm > 0:
        growth_1y = (fc['eps_2027e'] - inp.eps_ttm) / inp.eps_ttm * 100 / 2

    if not user_provided_6m and growth_6m != 0:
        inp.industry_growth_6m = growth_6m
    if not user_provided_1y and growth_1y != 0:
        inp.industry_growth_1y = growth_1y

    # 计算 2y = 2028E 同比
    try:
        from sqlalchemy import text
        from models import get_db
        db = next(get_db())
        try:
            row = db.execute(
                text("SELECT net_profit_2027e, net_profit_2028e FROM prediction_aggregates WHERE code=:code"),
                {"code": inp.code}
            ).fetchone()
            if row:
                np27 = _parse_yi_value(row[0])
                np28 = _parse_yi_value(row[1])
                if np27 > 0 and np28 > 0 and inp.industry_growth_2y <= 0:
                    inp.industry_growth_2y = (np28 - np27) / np27 * 100
        finally:
            db.close()
    except Exception:
        pass

    inp.forecast_source = "institutional"
    return inp


def auto_fill_from_db(inp: ValuationInput) -> ValuationInput:
    """从数据库自动填充财务数据 (含机构预测)

    数据源优先级 (以 eps_ttm 为例):
      1. 用户已手动输入 → 保留
      2. realtime.pe_ttm + current_price → 实时 TTM PE (最准确)
      3. StockFinancial 中 pe_ttm 字段 → DB 中存的 PE
      4. StockFinancial 最新年报 EPS (12-31) → 优先用全年而非单季
      5. StockFinancial 最新季报 EPS (单季) → 兜底, 可能为负
      6. 机构一致预期 EPS_2026E → TTM 为负或 0 时回退

    Bug 修复: 蓝思科技 300433 案例
      旧逻辑取最新季报 (2026-03-31, EPS=-0.0284 单季亏损) → TTM 为负
      修复: 优先用 2025-12-31 年报 EPS=0.79, PE=4.29
    """
    try:
        from sqlalchemy import text
        from models import SessionLocal, StockFinancial
        db = SessionLocal()
        try:
            # 取所有相关报告 (一次性查询, 避免多次往返)
            fins = (
                db.query(StockFinancial)
                .filter(StockFinancial.code == inp.code)
                .order_by(StockFinancial.report_date.desc())
                .limit(8)
                .all()
            )

            # 找最新的年报 (report_date 12-31, 优先级最高)
            annual_fin = None
            for f in fins:
                rd = (f.report_date or "")
                if rd.endswith("-12-31") or rd.endswith("1231"):
                    annual_fin = f
                    break
            # 最新季报 (用于 profit_yoy / revenue_yoy 等单季数据)
            latest_fin = fins[0] if fins else None

            # 1. EPS_TTM: 优先用年报 EPS (避免亏损季拉低 TTM)
            if inp.eps_ttm <= 0:
                if annual_fin and _safe_float(annual_fin.eps) > 0:
                    inp.eps_ttm = _safe_float(annual_fin.eps)
                elif latest_fin:
                    inp.eps_ttm = _safe_float(latest_fin.eps)

            # 2. PE_TTM: 优先用年报的 PE 字段 (有可能是 None)
            if inp.pe_ttm <= 0:
                pe_val = _safe_float(getattr(annual_fin or latest_fin, 'pe_ttm', 0))
                if pe_val > 0:
                    inp.pe_ttm = pe_val

            # 3. PB: 用最新 (年报或季报)
            if inp.pb <= 0:
                pb_val = _safe_float(getattr(annual_fin or latest_fin, 'pb', 0))
                if pb_val > 0:
                    inp.pb = pb_val

            # 4. ROE: 用最新年报
            if inp.roe <= 0:
                roe_val = _safe_float(getattr(annual_fin or latest_fin, 'roe', 0))
                if roe_val > 0:
                    inp.roe = roe_val

            # 5. 增长率: 用最新季报的同比 (单季同比更具时效性)
            if latest_fin:
                if inp.revenue_yoy <= 0:
                    inp.revenue_yoy = _safe_float(latest_fin.revenue_yoy)
                if inp.profit_yoy <= 0:
                    inp.profit_yoy = _safe_float(latest_fin.profit_yoy)
                if inp.gross_margin <= 0:
                    inp.gross_margin = _safe_float(latest_fin.gross_margin)

            # 6. debt_ratio 容错 (StockFinancial 模型目前没有此字段)
            if inp.debt_ratio <= 0:
                inp.debt_ratio = _safe_float(getattr(latest_fin, 'debt_ratio', 0))
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"auto_fill_from_db({inp.code}) failed: {e}")

    # 从实时行情获取当前价格 (Sina 实时数据)
    try:
        from data_fetchers import get_realtime_data
        rt = get_realtime_data(inp.code)
        if rt:
            if inp.current_price <= 0:
                inp.current_price = _safe_float(rt.get('current_price', 0))
    except Exception:
        pass

    # ── Sprint 6 优化: 自动使用机构预测净利润 ──
    auto_fill_institutional_forecast(inp)

    # 兜底: 若 EPS_TTM 仍为 0 或负 (T 季度亏损) → 用机构一致预期 EPS_2026E 替代
    if inp.eps_ttm <= 0 and inp.forecast_eps_2026e > 0:
        logger.info(
            f"auto_fill_from_db({inp.code}): TTM EPS 不可用 ({inp.eps_ttm}), "
            f"回退到机构一致预期 2026E EPS={inp.forecast_eps_2026e}"
        )
        inp.eps_ttm = inp.forecast_eps_2026e

    # 从板块预测获取行业展望
    if inp.sector_name and not inp.sector_outlook:
        try:
            from sector_prediction import predict_sectors
            # 尝试获取板块展望
            predictions = predict_sectors()
            if predictions:
                for pred in predictions:
                    if pred.get('name') == inp.sector_name:
                        inp.sector_outlook = pred.get('rating', '')
                        break
        except Exception:
            pass

    return inp


def calculate_momentum_adjustment(code: str, kline_data: list = None) -> float:
    """
    Sprint 7 P1.2: 自动计算动量调整分 (-10 ~ +10)

    基于近 N 日价格动量 + 暴跌反弹识别:
      - 5 日涨跌幅: 短期趋势
      - 20 日涨跌幅: 中期趋势
      - 暴跌反弹: 近 10 日内单日跌幅 > 10% → 反弹机会加分

    评分逻辑 (整体 -10 ~ +10, 评分卡会截断为 -5 ~ +5):
      + 持续上涨趋势 (5日 +10% ~ +20%, 20日 > 0)
      ++ 突破加速 (5日 > +20%, 20日 > +30%)
      +  温和上涨 (5日 +5% ~ +10%)
      0  横盘
      -  温和下跌
      -- 持续下跌 (5日 -10% ~ -20%)
      +++ 暴跌反弹 (近 10 日内有单日 < -10%, 但 5 日累计 > +5%)
    """
    try:
        if kline_data is None:
            # 拉 K 线 (默认 30 天, 够用)
            kline_data = _fetch_kline_data(code, days=30)

        if not kline_data or len(kline_data) < 5:
            return 0.0

        # 计算各周期涨跌幅 (5d 涨幅 = 5 个交易日前到今天)
        closes = [float(d['close']) for d in kline_data]
        latest = closes[-1]
        # 5 日前: 索引 -6 (如果数据足够)
        d5_ago = closes[-6] if len(closes) >= 6 else closes[0]
        # 20 日前: 索引 -21
        d20_ago = closes[-21] if len(closes) >= 21 else closes[0]
        # 10 日前: 索引 -11
        d10_ago = closes[-11] if len(closes) >= 11 else closes[0]

        change_5d = (latest - d5_ago) / d5_ago * 100 if d5_ago > 0 else 0
        change_20d = (latest - d20_ago) / d20_ago * 100 if d20_ago > 0 else 0
        change_10d = (latest - d10_ago) / d10_ago * 100 if d10_ago > 0 else 0

        # 单日最大跌幅 (近 10 日内)
        max_daily_drop = 0
        max_daily_drop_idx = -1
        for i in range(-1, -11, -1):
            if abs(i) - 1 < len(closes) and abs(i) <= len(closes):
                prev_idx = i - 1
                if abs(prev_idx) <= len(closes):
                    day_chg = (closes[i] - closes[prev_idx]) / closes[prev_idx] * 100
                    if day_chg < max_daily_drop:
                        max_daily_drop = day_chg
                        max_daily_drop_idx = i

        # 评分
        score = 0.0

        # 暴跌反弹 (近 10 日有单日 < -10%, 且 5 日累计 > +5%)
        if max_daily_drop < -10 and change_5d > 5:
            # 暴跌后反弹 = 买入机会
            score += 6
        elif max_daily_drop < -15 and change_5d > 0:
            score += 4
        elif max_daily_drop < -10 and change_5d > 0:
            score += 2

        # 5 日动量 (主要短期指标)
        if change_5d > 20:
            score += 5  # 加速上涨
        elif change_5d > 10:
            score += 3
        elif change_5d > 5:
            score += 1
        elif change_5d < -20:
            score -= 5  # 加速下跌
        elif change_5d < -10:
            score -= 3
        elif change_5d < -5:
            score -= 1

        # 20 日动量 (中期趋势, 弱化)
        if change_20d > 30:
            score += 3
        elif change_20d > 15:
            score += 1
        elif change_20d < -30:
            score -= 3
        elif change_20d < -15:
            score -= 1

        return max(-10.0, min(10.0, score))
    except Exception as e:
        logger.debug(f"calculate_momentum_adjustment({code}) failed: {e}")
        return 0.0


def _fetch_kline_data(code: str, days: int = 30) -> list:
    """
    拉 K 线数据 (Sprint 7 P1.2)
    优先从 Sina (无需 token), fallback 腾讯
    支持沪深300 (sh000300) 等指数
    """
    import urllib.request, json
    # 已带 sh/sz 前缀则直接用; 否则按首位数字推断
    if code.startswith(("sh", "sz")):
        sym = code
    elif len(code) == 6:
        prefix = "sh" if code.startswith('6') else "sz"
        sym = f"{prefix}{code}"
    else:
        sym = f"sh{code}"
    try:
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen={days}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'http://finance.sina.com.cn'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('gbk'))
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        logger.debug(f"_fetch_kline_data({code}) sina failed: {e}")
    return []


def calculate_relative_strength_adjustment(code: str) -> float:
    """
    Sprint 7 P2: 相对市场强度 (RS) 调整 (-5 ~ +5)

    个股 5日/20日 涨幅 vs 沪深300 同期涨幅:
      - 跑赢 > +5% → 加分 (强势股)
      - 跑输 < -5% → 减分 (弱势股)
      - 持平 → 0
    """
    try:
        # 拉个股 K 线
        stock_kline = _fetch_kline_data(code, days=30)
        if not stock_kline or len(stock_kline) < 6:
            return 0.0

        # 拉沪深300 K 线
        # sh000300 / sz399300 都可以
        market_kline = _fetch_kline_data('sh000300', days=30)
        if not market_kline or len(market_kline) < 6:
            market_kline = _fetch_kline_data('sz399300', days=30)
        if not market_kline or len(market_kline) < 6:
            return 0.0

        # 对齐数据 (取较短的)
        n = min(len(stock_kline), len(market_kline))

        stock_close = float(stock_kline[-1]['close'])
        stock_5d_ago = float(stock_kline[-6]['close']) if n >= 6 else float(stock_kline[0]['close'])
        stock_20d_ago = float(stock_kline[-21]['close']) if n >= 21 else float(stock_kline[0]['close'])

        market_close = float(market_kline[-1]['close'])
        market_5d_ago = float(market_kline[-6]['close']) if n >= 6 else float(market_kline[0]['close'])
        market_20d_ago = float(market_kline[-21]['close']) if n >= 21 else float(market_kline[0]['close'])

        stock_5d_chg = (stock_close - stock_5d_ago) / stock_5d_ago * 100
        market_5d_chg = (market_close - market_5d_ago) / market_5d_ago * 100
        stock_20d_chg = (stock_close - stock_20d_ago) / stock_20d_ago * 100
        market_20d_chg = (market_close - market_20d_ago) / market_20d_ago * 100

        rs_5d = stock_5d_chg - market_5d_chg
        rs_20d = stock_20d_chg - market_20d_chg

        # 评分 (5d 为主, 20d 为辅)
        score = 0.0
        if rs_5d > 15:
            score += 5
        elif rs_5d > 8:
            score += 3
        elif rs_5d > 3:
            score += 1
        elif rs_5d < -15:
            score -= 5
        elif rs_5d < -8:
            score -= 3
        elif rs_5d < -3:
            score -= 1

        # 20d 调整
        if rs_20d > 20:
            score += 2
        elif rs_20d > 10:
            score += 1
        elif rs_20d < -20:
            score -= 2
        elif rs_20d < -10:
            score -= 1

        return max(-5.0, min(5.0, score))
    except Exception as e:
        logger.debug(f"calculate_relative_strength_adjustment({code}) failed: {e}")
        return 0.0


def quick_valuation(code: str, industry_growth_1y: float = 0,
                    industry_growth_6m: float = 0,
                    sector_name: str = "") -> Dict:
    """
    快速估值 — 一步完成数据获取+计算。

    示例用法:
      result = quick_valuation('002916',
                                industry_growth_6m=100,   # PCB半年利润翻倍
                                industry_growth_1y=150,
                                sector_name='PCB')
    """
    inp = ValuationInput(
        code=code,
        industry_growth_6m=industry_growth_6m,
        industry_growth_1y=industry_growth_1y,
        sector_name=sector_name,
    )
    inp = auto_fill_from_db(inp)

    # 尝试获取名称
    try:
        from data_fetchers import get_realtime_data
        rt = get_realtime_data(code)
        if rt and rt.get('name'):
            inp.name = rt['name']
    except Exception:
        pass

    # Sprint 7 P1.2: 自动计算动量调整分 (5d/20d 趋势)
    momentum_adj = calculate_momentum_adjustment(code)
    # Sprint 7 P2: 相对市场强度 (个股 vs 沪深300)
    rs_adj = calculate_relative_strength_adjustment(code)
    # 合并: 动量占 70%, RS 占 30%, 整体截断为 -10 ~ +10 (评分卡内再截断为 -5 ~ +5)
    combined_momentum = momentum_adj * 0.7 + rs_adj * 0.3 * 2  # RS 范围 -5~+5, 调整到 -10~+10 区间
    combined_momentum = max(-10.0, min(10.0, combined_momentum))
    # 把动量数据存到 detail
    inp_detail_momentum = {
        'momentum_adjustment': round(combined_momentum, 1),
        'momentum_raw': round(momentum_adj, 1),
        'relative_strength': round(rs_adj, 1),
        'momentum_source': 'auto_5d_20d + hs300',
    }

    result = calculate_valuation(inp, momentum_adjustment=combined_momentum)
    # 合并动量 detail
    result.detail.update(inp_detail_momentum)

    return {
        'code': code,
        'name': inp.name,
        'current_price': inp.current_price,
        'current_pe': result.current_pe,
        'eps_ttm': result.detail.get('eps_ttm', 0),
        'peg_ratio': result.peg_ratio,
        'peg_verdict': result.peg_verdict,
        'forward_pe_6m': result.forward_pe_6m,
        'forward_pe_1y': result.forward_pe_1y,
        'forward_pe_2y': result.forward_pe_2y,
        'fair_value_current': result.fair_value_current,
        'fair_value_growth': result.fair_value_growth,
        'margin_of_safety': result.margin_of_safety,
        'dcf_value': result.dcf_value,
        'dcf_upside': result.dcf_upside,
        'dcf_margin': result.dcf_margin,
        'composite_score': result.composite_score,
        'rating': result.rating,
        'summary': result.summary,
        'detail': result.detail,
        # Sprint 6 优化: 机构预测元数据
        'forecast': {
            'source': inp.forecast_source or "none",
            'has_data': inp.forecast_source == "institutional",
            'net_profit_2025a': inp.forecast_net_profit_2025a,
            'net_profit_2026e': inp.forecast_net_profit_2026e,
            'net_profit_2027e': inp.forecast_net_profit_2027e,
            'eps_2026e': inp.forecast_eps_2026e,
            'eps_2027e': inp.forecast_eps_2027e,
            'analyst_count': inp.forecast_analyst_count,
            'rating_label': inp.forecast_rating_label,
            'updated_at': inp.forecast_updated_at,
            'growth_6m_implied': inp.industry_growth_6m,
            'growth_1y_implied': inp.industry_growth_1y,
            'growth_2y_implied': inp.industry_growth_2y,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 紫苏叶产业链候选池 — 暴露给 quant_valuation 作为估值候选宇宙
# ═══════════════════════════════════════════════════════════════

def list_shiso_chokepoint_universe(chain_name: str = None, enabled_only: bool = True) -> List[Dict]:
    """列出紫苏叶产业链卡位候选 (供 quant_valuation / 其它估值模块复用)

    返回:
        [{"code", "name", "chain_name", "layer", "monopoly_score",
          "player_count", "extra_score", "moat_note"}, ...]

    Args:
        chain_name:   指定产业链, None = 全产业链
        enabled_only: 是否只取 enabled=True 的卡位
    """
    try:
        # 延迟导入避免循环依赖 (zisuye 自身也用 quant_valuation 工具)
        from db import list_shiso_chokepoints
        from models import SessionLocal
        db = SessionLocal()
        try:
            rows = list_shiso_chokepoints(
                db, chain_name=chain_name, enabled_only=enabled_only,
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"list_shiso_chokepoint_universe 失败: {e}")
        return []

    return [
        {
            "code": r.code,
            "name": r.name,
            "chain_name": r.chain_name,
            "layer": r.layer,
            "monopoly_score": r.monopoly_score,
            "player_count": r.player_count,
            "extra_score": r.extra_score,
            "moat_note": r.moat_note,
        }
        for r in rows
    ]
