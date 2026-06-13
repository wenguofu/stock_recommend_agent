#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紫苏叶理论 — 种子数据

来源: Serenity @aleabitoreddit 的紫苏叶理论 (Shiso Leaf Theory)
核心思想: 在大产业链中,找到那些小到没人愿意看、冷到没人愿意写、但一旦断供
整条 AI 产业链就会卡住的"瓶颈点"。

本文件只放初始几条产业链,后续可手工扩展。
产业链路径参考自用户提供的 zisuye.log1/log2。
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from models import SessionLocal
from db import upsert_shiso_chain, upsert_shiso_chokepoint


# ═══════════════════════════════════════════════════════════════
# 产业链定义 — 自上而下的反推路径
# ═══════════════════════════════════════════════════════════════

CHAINS = [
    {
        "chain_name": "AI光通信",
        "sector_tag": "通信",
        "toro_layer": "GPU / 光模块龙头 (中际旭创、新易盛)",
        "chokepoint_layer": "InP衬底 / DFB激光器 / 硅光子",
        "top_down_path": (
            "AI训练/推理 → 万卡GPU集群 → 高速低功耗互联 → "
            "光模块/CPO → InP激光器 / 硅光子 → InP衬底 / 特种材料"
        ),
        "notes": "Serenity 成名案例 (AXTI 即为 InP 衬底商), AI 算力扩张的最大瓶颈之一",
    },
    {
        "chain_name": "AI先进封装",
        "sector_tag": "半导体",
        "toro_layer": "GPU / 封装龙头 (通富微电、长电科技)",
        "chokepoint_layer": "IC载板 / CoWoS中介层 / ABF",
        "top_down_path": (
            "AI算力 → HBM/CoWoS封装 → IC载板 (ABF) / "
            "中介层材料 → 高纯度玻璃纤维 / 陶瓷基板"
        ),
        "notes": "封装基板全球玩家 ≤5 家, 国内能做的更少",
    },
    {
        "chain_name": "AI液冷散热",
        "sector_tag": "数据中心",
        "toro_layer": "数据中心 / 温控大厂 (英维克、佳力图)",
        "chokepoint_layer": "液冷快接头 / 高导热界面材料 / 冷板",
        "top_down_path": (
            "万卡GPU → 数据中心功率密度暴增 → 风冷撞墙 → "
            "液冷/浸没式 → 冷板 / 快接头 / 高导热界面材料"
        ),
        "notes": "2026 H2 液冷渗透率快速提升, 上游材料供给紧张",
    },
    {
        "chain_name": "半导体材料",
        "sector_tag": "半导体",
        "toro_layer": "晶圆厂 (中芯国际、华虹)",
        "chokepoint_layer": "电子特气 / 光刻胶 / 湿电子化学品 / 硅片",
        "top_down_path": (
            "晶圆制造 → 工艺步骤拆解 → "
            "光刻 / 刻蚀 / 沉积 / 清洗 各环节所需材料"
        ),
        "notes": "国内替代逻辑, 卡脖子的细分材料商",
    },
]


# ═══════════════════════════════════════════════════════════════
# 卡位标的 — 紫苏叶 (产业链 → A股对应公司)
# 字段: code, name, chain_name, layer, monopoly_score, player_count, moat_note, extra_score
# 注: A股映射仅为示例种子,后续可扩展/调整
# ═══════════════════════════════════════════════════════════════

CHOKEPOINTS_CORE = [
    # ── AI光通信 ─────────────────────────────────────────────
    {
        "code": "688498", "name": "源杰科技", "chain_name": "AI光通信",
        "layer": "DFB激光器 / 高速EML芯片",
        "monopoly_score": 85, "player_count": 2,
        "moat_note": "国内为数不多能量产 25G/50G DFB 的厂商, 切入数据中心光模块",
        "extra_score": 15,
    },
    {
        "code": "688313", "name": "仕佳光子", "chain_name": "AI光通信",
        "layer": "AWG / PLC分路器",
        "monopoly_score": 75, "player_count": 3,
        "moat_note": "AWG 国产替代主力, 海外大客户验证完成",
        "extra_score": 8,
    },
    {
        "code": "300570", "name": "太辰光", "chain_name": "AI光通信",
        "layer": "光纤连接器 / MPO",
        "monopoly_score": 70, "player_count": 3,
        "moat_note": "光无源器件, 海外数据中心客户为主",
        "extra_score": 5,
    },
    {
        "code": "002222", "name": "福晶科技", "chain_name": "AI光通信",
        "layer": "非线性光学晶体 (BBO/LBO)",
        "monopoly_score": 90, "player_count": 1,
        "moat_note": "全球非线性光学晶体垄断级供应商",
        "extra_score": 20,
    },
    # ── AI先进封装 ───────────────────────────────────────────
    {
        "code": "002436", "name": "兴森科技", "chain_name": "AI先进封装",
        "layer": "IC载板 / ABF",
        "monopoly_score": 75, "player_count": 3,
        "moat_note": "国内 ABF 载板稀缺产能, 长期成长",
        "extra_score": 12,
    },
    {
        "code": "002916", "name": "深南电路", "chain_name": "AI先进封装",
        "layer": "高端PCB / 封装基板",
        "monopoly_score": 70, "player_count": 4,
        "moat_note": "通信PCB龙头, 封装基板第二增长曲线",
        "extra_score": 8,
    },
    {
        "code": "688234", "name": "天岳先进", "chain_name": "AI先进封装",
        "layer": "SiC衬底 / 第三代半导体",
        "monopoly_score": 65, "player_count": 4,
        "moat_note": "SiC 衬底国产替代, 新能源/AI 电源潜在应用",
        "extra_score": 6,
    },
    # ── AI液冷散热 ───────────────────────────────────────────
    {
        "code": "002837", "name": "英维克", "chain_name": "AI液冷散热",
        "layer": "机房温控 / 液冷CDU",
        "monopoly_score": 70, "player_count": 4,
        "moat_note": "国内机房精密温控龙头, 已切入液冷",
        "extra_score": 10,
    },
    {
        "code": "300499", "name": "高澜股份", "chain_name": "AI液冷散热",
        "layer": "液冷板 / 服务器冷却",
        "monopoly_score": 60, "player_count": 4,
        "moat_note": "液冷老兵, 服务器液冷份额提升",
        "extra_score": 5,
    },
    {
        "code": "300602", "name": "飞荣达", "chain_name": "AI液冷散热",
        "layer": "导热界面材料 (TIM)",
        "monopoly_score": 55, "player_count": 5,
        "moat_note": "TIM/EMC 国内主要供应商",
        "extra_score": 3,
    },
    # ── 半导体材料 ───────────────────────────────────────────
    {
        "code": "688126", "name": "沪硅产业", "chain_name": "半导体材料",
        "layer": "硅片 (12寸)",
        "monopoly_score": 70, "player_count": 3,
        "moat_note": "国内12寸硅片主力, 国产替代核心",
        "extra_score": 10,
    },
    {
        "code": "002409", "name": "雅克科技", "chain_name": "半导体材料",
        "layer": "前驱体材料 / 电子特气",
        "monopoly_score": 65, "player_count": 4,
        "moat_note": "半导体材料平台型公司",
        "extra_score": 6,
    },
    {
        "code": "688268", "name": "华特气体", "chain_name": "半导体材料",
        "layer": "电子特气",
        "monopoly_score": 65, "player_count": 5,
        "moat_note": "国内特气主要供应商, 进入头部晶圆厂",
        "extra_score": 5,
    },
    {
        "code": "002549", "name": "凯美特气", "chain_name": "半导体材料",
        "layer": "氪气 / 氙气 / 稀有气体",
        "monopoly_score": 60, "player_count": 4,
        "moat_note": "稀有气体提纯, AI 半导体激光用气潜在受益",
        "extra_score": 5,
    },
    {
        "code": "002407", "name": "多氟多", "chain_name": "半导体材料",
        "layer": "电子级氢氟酸 / 湿电子化学品",
        "monopoly_score": 60, "player_count": 5,
        "moat_note": "湿电子化学品国产替代",
        "extra_score": 5,
    },
]


# 可选卡位 (默认不入库, 需 --include-optional 才灌入)
# 博创科技 等"严格说不是紫苏叶"的标的, 单独放这里, 不污染主卡位池
CHOKEPOINTS_OPTIONAL = [
    {
        "code": "300548", "name": "博创科技", "chain_name": "AI光通信",
        "layer": "光模块 (中游)",
        "monopoly_score": 55, "player_count": 5,
        "moat_note": "中游模块厂, 议价权较弱 (注: 严格说不是紫苏叶)",
        "extra_score": -5,
    },
]


def seed(include_optional: bool = False):
    """灌入产业链 + 卡位数据

    Args:
        include_optional: 是否同时灌入 CHOKEPOINTS_OPTIONAL (默认 False, 保持主卡位池纯净)
    """
    db = SessionLocal()
    try:
        chain_count = 0
        for c in CHAINS:
            row = upsert_shiso_chain(
                db,
                chain_name=c["chain_name"],
                sector_tag=c.get("sector_tag"),
                toro_layer=c.get("toro_layer"),
                chokepoint_layer=c.get("chokepoint_layer"),
                top_down_path=c.get("top_down_path"),
                enabled=True,
                notes=c.get("notes"),
            )
            chain_count += 1
            print(f"[chain] {row.chain_name}  {row.chokepoint_layer}")

        cp_count = 0
        for cp in CHOKEPOINTS_CORE:
            row = upsert_shiso_chokepoint(
                db,
                code=cp["code"],
                chain_name=cp["chain_name"],
                name=cp.get("name"),
                layer=cp.get("layer"),
                monopoly_score=cp.get("monopoly_score", 50),
                player_count=cp.get("player_count", 3),
                moat_note=cp.get("moat_note"),
                extra_score=cp.get("extra_score", 0),
                enabled=True,
            )
            cp_count += 1
            print(f"[chokepoint] {row.code} {row.name} ({row.chain_name})")

        if include_optional:
            for cp in CHOKEPOINTS_OPTIONAL:
                row = upsert_shiso_chokepoint(
                    db,
                    code=cp["code"],
                    chain_name=cp["chain_name"],
                    name=cp.get("name"),
                    layer=cp.get("layer"),
                    monopoly_score=cp.get("monopoly_score", 50),
                    player_count=cp.get("player_count", 3),
                    moat_note=cp.get("moat_note"),
                    extra_score=cp.get("extra_score", 0),
                    enabled=True,
                )
                cp_count += 1
                print(f"[chokepoint-optional] {row.code} {row.name} ({row.chain_name})")

        print(f"\n✅ seed 完成: {chain_count} 条产业链, {cp_count} 个卡位标的")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="紫苏叶种子数据")
    p.add_argument("--include-optional", action="store_true",
                   help="同时灌入 CHOKEPOINTS_OPTIONAL (默认不入库)")
    args = p.parse_args()
    seed(include_optional=args.include_optional)