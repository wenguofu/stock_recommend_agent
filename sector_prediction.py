"""
主线预判引擎 v1 — 存储芯片10倍行情方法论固化

基于六因子评分 + 四道验证关卡，对候选板块给出 S/A/B/C 评级。
用于识别下一个可能的主线板块，在板块启动前给出预判信号。

理论框架: docs/sector_prediction_framework.md

用法:
    uv run python sector_prediction.py                              # 分析最新导入的板块数据
    uv run python sector_prediction.py --sector "人形机器人"        # 单独分析某个板块
    uv run python sector_prediction.py --all                        # 分析所有已导入板块的历史趋势
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
SECTOR_DATA_DIR = os.path.join(os.path.dirname(__file__), "sector_data")
EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_result")

# 六因子权重
FACTOR_WEIGHTS = {
    "supply_demand": 0.30,   # 供需失衡度
    "cycle_position": 0.20,  # 产业周期位置
    "tech_breakthrough": 0.15,  # 技术突破量级
    "policy_catalyst": 0.15,    # 政策催化强度
    "capital_flow": 0.10,       # 资金流入信号
    "valuation_elasticity": 0.10,  # 板块估值弹性
}

# 高热度关键词 — 用于自动评分
HIGH_INTENSITY_KW = [
    "需求爆发", "供不应求", "供需失衡", "紧缺", "爆舱", "爆单",
    "大涨", "飙升", "暴涨", "井喷", "翻倍",
    "突破", "量产", "历史新高", "商业化落地",
    "拐点", "反转", "景气度", "超级周期",
    "国产替代", "自主可控", "卡脖子",
    "首次", "里程碑", "重大突破",
]

MEDIUM_INTENSITY_KW = [
    "增长", "上升", "扩张", "加速", "催化",
    "政策支持", "补贴", "减税", "利好",
    "渗透率", "放量", "超预期",
    "机构看好", "推荐", "买入",
]

WEAK_SIGNAL_KW = [
    "关注", "布局", "试点", "探索",
    "有望", "可能", "预计", "或将",
    "修复", "企稳", "回暖",
]

# 板块-代码映射（用于后续拉行情数据验证）
SECTOR_STOCK_MAP = {
    "智能驾驶": ["002703", "600611", "002813", "300552", "301488"],
    "人形机器人": ["300503", "688001", "301488", "688585", "002747"],
    "光学光电子": ["300323", "300219", "300303", "300232", "300162"],
    "航运": ["601975", "601872", "600026", "601866", "600428"],
    "电力": ["001258", "603693", "000601", "002039", "600310"],
    "银行": ["601939", "601963", "601988", "002948", "600919"],
    "证券": ["600909", "000728", "600999", "601066", "002945"],
    "汽车整车": ["600303", "601127", "601777", "600733", "002594"],
    "创新药": ["300759", "603259", "002821", "688068", "002001"],
    "存储芯片": ["603986", "300042", "300475", "688525", "301308"],
}


# ---------------------------------------------------------------------------
# 核心评分逻辑
# ---------------------------------------------------------------------------

def score_supply_demand(sector: dict) -> Tuple[int, str]:
    """评分供需失衡度 (0-10)"""
    combined = sector.get("driver", "") + sector.get("insight", "") + sector.get("view", "")
    score = 5  # neutral base

    # 强供需失衡信号
    tight_signals = ["供需失衡", "供不应求", "紧缺", "产能不足", "爆舱", "爆单", "产能转向", "挤占"]
    demand_signals = ["需求爆发", "井喷", "需求拉动", "算力需求", "AI需求", "资本支出"]
    price_signals = ["涨价", "运价攀升", "价格上调", "ASP提升", "量价齐升"]

    for s in tight_signals:
        if s in combined:
            score += 1
    for s in demand_signals:
        if s in combined:
            score += 1
    for s in price_signals:
        if s in combined:
            score += 1

    score = min(10, score)

    if score >= 8:
        detail = "强供需缺口：供给受限+需求爆发+价格上行"
    elif score >= 6:
        detail = "中度供需偏紧"
    else:
        detail = "供需基本平衡或需求尚不明确"

    return score, detail


def score_cycle_position(sector: dict) -> Tuple[int, str]:
    """评分产业周期位置 (0-10)。高位=底部反转，低位=高位见顶"""
    combined = sector.get("insight", "") + sector.get("view", "")
    score = 5

    bottom_signals = ["底部", "低位", "估值修复空间", "调整新低", "创出新低", "历史低位", "超跌"]
    recovery_signals = ["回暖", "企稳", "修复", "改善", "向上", "复苏"]
    peak_signals = ["高位", "过热", "泡沫", "创新高", "历史高位", "涨幅过大"]

    for s in bottom_signals:
        if s in combined:
            score += 2
    for s in recovery_signals:
        if s in combined:
            score += 1
    for s in peak_signals:
        if s in combined:
            score -= 2

    score = max(1, min(10, score))

    if score >= 8:
        detail = "📉 周期底部/复苏初期 — 最佳介入时点"
    elif score >= 6:
        detail = "↗️ 复苏中段 — 仍有空间"
    elif score >= 4:
        detail = "➡️ 周期中段 — 需精选标的"
    else:
        detail = "📈 接近周期高位 — 追高风险大"

    return score, detail


def score_tech_breakthrough(sector: dict) -> Tuple[int, str]:
    """评分技术突破量级 (0-10)"""
    combined = sector.get("driver", "") + sector.get("insight", "") + sector.get("view", "")
    score = 5

    zero_to_one = ["首次", "0-1", "0→1", "里程碑", "从无到有", "历史性", "开创", "首发", "首次量产"]
    one_to_n = ["量产", "规模化", "渗透率提升", "放量", "拐点", "普及", "加速渗透"]
    incremental = ["迭代", "升级", "优化", "改进", "提升"]

    for s in zero_to_one:
        if s in combined:
            score += 2
    for s in one_to_n:
        if s in combined:
            score += 1
    for s in incremental:
        if s in combined:
            score += 0.5

    score = min(10, int(score))

    if score >= 8:
        detail = "🔬 0→1级突破 — 技术代际跨越"
    elif score >= 6:
        detail = "⚙️ 1→N放量 — 规模化拐点"
    else:
        detail = "🔧 渐进式迭代 — 非革命性变化"

    return score, detail


def score_policy_catalyst(sector: dict) -> Tuple[int, str]:
    """评分政策催化强度 (0-10)"""
    combined = sector.get("driver", "") + sector.get("insight", "") + sector.get("view", "")
    score = 5

    national = ["国务院", "发改委", "国家能源局", "工信部", "中央", "国家战略", "十四五", "十五五",
                 "证监会", "大基金", "国家大基金"]
    ministerial = ["财政部", "科技部", "交通运输部", "卫健委", "药监局"]
    local = ["地方政府", "省市", "补贴"]

    for s in national:
        if s in combined:
            score += 2
    for s in ministerial:
        if s in combined:
            score += 1
    for s in local:
        if s in combined:
            score += 0.5

    score = min(10, int(score))

    if score >= 8:
        detail = "🏛️ 国家级政策驱动"
    elif score >= 6:
        detail = "📋 部委级政策支持"
    elif score >= 5:
        detail = "📄 有政策提及但非核心驱动"
    else:
        detail = "⚪ 政策催化剂不足"

    return score, detail


def score_capital_flow(sector: dict) -> Tuple[int, str]:
    """评分资金流入信号 (0-10) — 基于文本信号的代理指标"""
    combined = sector.get("insight", "") + sector.get("view", "")
    score = 5

    inflow_signals = ["资金流入", "机构建仓", "北向资金", "主力资金", "放量", "成交额放大",
                      "活跃", "带动", "情绪高涨", "关注度提升", "换手率"]
    outflow_signals = ["资金流出", "减持", "回落走低", "走弱", "缩量"]

    for s in inflow_signals:
        if s in combined:
            score += 1
    for s in outflow_signals:
        if s in combined:
            score -= 1

    score = max(1, min(10, score))

    if score >= 8:
        detail = "💰 资金明确流入 — 市场认可度高"
    elif score >= 6:
        detail = "📊 资金温和关注"
    else:
        detail = "🔻 资金面偏弱或流出"

    return score, detail


def score_valuation_elasticity(sector: dict) -> Tuple[int, str]:
    """评分板块估值弹性 (0-10) — 基于文本的代理指标"""
    combined = sector.get("insight", "") + sector.get("view", "")
    score = 5

    cheap_signals = ["估值低位", "低估值", "PE低", "PB低", "超跌", "底部区域", "估值洼地",
                     "安全边际", "性价比", "估值修复空间"]
    expensive_signals = ["估值高位", "高估值", "PE高", "创新高", "涨幅较大", "透支",
                         "追高风险", "泡沫"]

    for s in cheap_signals:
        if s in combined:
            score += 2
    for s in expensive_signals:
        if s in combined:
            score -= 2

    score = max(1, min(10, score))

    if score >= 8:
        detail = "📉 估值处于低位 — 弹性空间大"
    elif score >= 6:
        detail = "📊 估值合理 — 有一定空间"
    else:
        detail = "📈 估值偏高 — 上行空间有限"

    return score, detail


# ---------------------------------------------------------------------------
# 综合评估
# ---------------------------------------------------------------------------

def compute_total_score(sector: dict) -> dict:
    """计算单个板块的综合评分"""
    scores = {}
    details = {}

    scores["supply_demand"], details["supply_demand"] = score_supply_demand(sector)
    scores["cycle_position"], details["cycle_position"] = score_cycle_position(sector)
    scores["tech_breakthrough"], details["tech_breakthrough"] = score_tech_breakthrough(sector)
    scores["policy_catalyst"], details["policy_catalyst"] = score_policy_catalyst(sector)
    scores["capital_flow"], details["capital_flow"] = score_capital_flow(sector)
    scores["valuation_elasticity"], details["valuation_elasticity"] = score_valuation_elasticity(sector)

    total = sum(scores[k] * FACTOR_WEIGHTS[k] for k in FACTOR_WEIGHTS) * 10  # 转换为百分制

    return {
        "name": sector["name"],
        "scores": scores,
        "details": details,
        "total": round(total, 1),
        "stocks": sector.get("stocks", ""),
        "driver": sector.get("driver", ""),
    }


def run_verification_gates(result: dict) -> Tuple[int, List[str]]:
    """运行四道验证关卡。返回 (通过数, [关卡结果描述])"""
    gates = []
    passed = 0

    # Gate 1: 供需验证 (supply_demand >= 7)
    if result["scores"]["supply_demand"] >= 7:
        gates.append("✅ Gate1 供需验证通过 — 存在真实供需缺口")
        passed += 1
    else:
        gates.append("❌ Gate1 供需验证未过 — 供需缺口不明确，可能是概念炒作")

    # Gate 2: 周期验证 (cycle_position >= 6)
    if result["scores"]["cycle_position"] >= 6:
        gates.append("✅ Gate2 周期验证通过 — 处于周期有利位置")
        passed += 1
    else:
        gates.append("❌ Gate2 周期验证未过 — 周期位置不利，追高风险")

    # Gate 3: 综合实力验证 (capital_flow + policy >= 12)
    if result["scores"]["capital_flow"] + result["scores"]["policy_catalyst"] >= 12:
        gates.append("✅ Gate3 资金+政策验证通过 — 有资金/政策支撑")
        passed += 1
    else:
        gates.append("❌ Gate3 资金+政策验证未过 — 缺乏资金或政策支撑")

    # Gate 4: 龙头质量验证 (tech >= 6)
    if result["scores"]["tech_breakthrough"] >= 6:
        gates.append("✅ Gate4 技术验证通过 — 有实质性技术/产业突破")
        passed += 1
    else:
        gates.append("❌ Gate4 技术验证未过 — 缺乏核心技术突破支撑")

    return passed, gates


def assign_rating(total: float, gates_passed: int) -> str:
    """根据总分和关卡通过数给出评级"""
    if total >= 80 and gates_passed >= 4:
        return "🔴 S级 — 高确定性主线，可重仓布局"
    elif total >= 65 and gates_passed >= 3:
        return "🟠 A级 — 强候选主线，中等仓位"
    elif total >= 50 and gates_passed >= 2:
        return "🟡 B级 — 关注级，轻仓试探或继续观察"
    else:
        return "⚪ C级 — 条件不满足，维持观望"


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def predict_sectors(sector_data_list: List[dict]) -> List[dict]:
    """对所有板块运行预判模型"""
    results = []
    for sector in sector_data_list:
        result = compute_total_score(sector)
        gates_passed, gate_msgs = run_verification_gates(result)
        result["gates_passed"] = gates_passed
        result["gate_msgs"] = gate_msgs
        result["rating"] = assign_rating(result["total"], gates_passed)
        results.append(result)

    results.sort(key=lambda x: -x["total"])
    return results


def format_report(results: List[dict], date: str = None) -> str:
    """格式化为Markdown报告"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# 🔮 主线预判报告",
        f"日期: {date}",
        f"模型: 六因子 + 四关卡 v1.0",
        f"方法论: docs/sector_prediction_framework.md",
        "",
        "---",
        "",
        "## 📊 板块综合评分",
        "",
        "| 排名 | 板块 | 总分 | 供需 | 周期 | 技术 | 政策 | 资金 | 估值 | 评级 |",
        "|:---:|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------|",
    ]

    for i, r in enumerate(results):
        s = r["scores"]
        lines.append(
            f"| {i+1} | **{r['name']}** | **{r['total']:.0f}** | "
            f"{s['supply_demand']} | {s['cycle_position']} | "
            f"{s['tech_breakthrough']} | {s['policy_catalyst']} | "
            f"{s['capital_flow']} | {s['valuation_elasticity']} | "
            f"{r['rating'][:2]}级 |"
        )

    lines.append("")
    lines.append("## 🏆 主线候选详情")
    lines.append("")

    for r in results:
        if r["total"] >= 50:
            lines.append(f"### {r['rating'][:2]}级 — {r['name']}（总分 {r['total']:.0f}）")
            lines.append("")
            lines.append("| 因子 | 评分 | 解析 |")
            lines.append("|------|:---:|------|")
            for k in FACTOR_WEIGHTS:
                label = {
                    "supply_demand": "供需失衡度",
                    "cycle_position": "周期位置",
                    "tech_breakthrough": "技术突破",
                    "policy_catalyst": "政策催化",
                    "capital_flow": "资金信号",
                    "valuation_elasticity": "估值弹性",
                }[k]
                lines.append(f"| {label} | {r['scores'][k]}/10 | {r['details'][k]} |")
            lines.append("")
            lines.append("**验证关卡:**")
            for gm in r["gate_msgs"]:
                lines.append(f"- {gm}")
            lines.append(f"\n**评级: {r['rating']}**")
            lines.append(f"\n**领涨标的:** {r.get('stocks', 'N/A')}")
            lines.append("")

    lines.append("---")
    lines.append(f"\n*报告由 sector_prediction.py 自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def main():
    """主入口"""
    os.makedirs(EVAL_DIR, exist_ok=True)

    # 加载最新板块数据
    json_files = sorted(
        [f for f in os.listdir(SECTOR_DATA_DIR) if f.endswith(".json")],
        reverse=True,
    )

    if not json_files:
        print("❌ 没有板块数据。请先运行: uv run python sector_import.py")
        sys.exit(1)

    # 支持 --sector 参数单独分析
    target_sector = None
    show_all = False
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--sector" and i + 1 < len(args):
            target_sector = args[i + 1]
        elif arg == "--all":
            show_all = True

    if target_sector:
        # 跨所有历史数据搜索该板块
        all_sectors = []
        for jf in json_files:
            with open(os.path.join(SECTOR_DATA_DIR, jf), encoding="utf-8") as f:
                data = json.load(f)
                for s in data.get("sectors", []):
                    if target_sector in s.get("name", ""):
                        all_sectors.append(s)
        if not all_sectors:
            print(f"❌ 未找到板块: {target_sector}")
            sys.exit(1)
        sector = all_sectors[0]  # 取最新一次
        result = compute_total_score(sector)
        gates_passed, gate_msgs = run_verification_gates(result)
        result["gates_passed"] = gates_passed
        result["gate_msgs"] = gate_msgs
        result["rating"] = assign_rating(result["total"], gates_passed)
        results = [result]
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        latest = json_files[0]
        with open(os.path.join(SECTOR_DATA_DIR, latest), encoding="utf-8") as f:
            day_data = json.load(f)
        date_str = day_data.get("date", "?")
        results = predict_sectors(day_data.get("sectors", []))

    report = format_report(results, date_str)
    print(report)

    # 保存
    report_path = os.path.join(EVAL_DIR, f"主线预判_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 预判报告已保存: {report_path}")


if __name__ == "__main__":
    main()
