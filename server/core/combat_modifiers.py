"""
兵种克制与战斗修正系统 · 元末逐鹿 3.0

职责：
1. 管理兵种之间的克制关系（骑兵/步兵/水军/弓兵）
2. 提供统一的战斗修正计算接口
3. 整合势力buff、地形、城防等多维修正

设计原则：
- 骑兵克步兵（机动优势）
- 步兵克枪兵（近战优势）
- 水军克骑兵（水域限制）
- 弓兵克水军（远程射击）
- 克制关系提供攻击加成，不影响防御
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
import logging

# M-1: 从 combat_utils 重新导出共享函数（消除与 unit_counter 的循环依赖）
from server.core.combat_utils import (
    apply_defense_cap, get_faction_attack_bonus, get_faction_defense_bonus,
    estimate_unit_type_from_faction, has_fire_attack, FACTION_COMBAT_BUFFS,
)

logger = logging.getLogger("yuanmo.combat.modifiers")


class UnitType(Enum):
    """兵种类型"""
    CAVALRY = "cavalry"     # 骑兵
    INFANTRY = "infantry"   # 步兵
    NAVAL = "naval"         # 水军
    ARCHER = "archer"       # 弓兵


# 兵种克制表：{攻击方: {防御方: 攻击加成}}
# 正值表示攻击方对防御方有优势
COUNTER_TABLE: dict[UnitType, dict[UnitType, float]] = {
    UnitType.CAVALRY: {
        UnitType.INFANTRY: 0.25,   # 骑兵对步兵 +25%
        UnitType.NAVAL: -0.15,     # 骑兵对水军 -15%（水域劣势）
        UnitType.ARCHER: 0.10,     # 骑兵对弓兵 +10%
        UnitType.CAVALRY: 0.0,     # 骑兵对骑兵 无克制
    },
    UnitType.INFANTRY: {
        UnitType.CAVALRY: -0.25,   # 步兵对骑兵 -25%（被克制）
        UnitType.NAVAL: 0.0,       # 步兵对水军 无克制
        UnitType.ARCHER: 0.20,     # 步兵对弓兵 +20%
        UnitType.INFANTRY: 0.0,    # 步兵对步兵 无克制
    },
    UnitType.NAVAL: {
        UnitType.CAVALRY: 0.40,    # 水军对骑兵 +40%（水域极大优势）
        UnitType.INFANTRY: 0.10,   # 水军对步兵 +10%
        UnitType.ARCHER: -0.20,    # 水军对弓兵 -20%（被远程克制）
        UnitType.NAVAL: 0.0,       # 水军对水军 无克制
    },
    UnitType.ARCHER: {
        UnitType.CAVALRY: -0.15,   # 弓兵对骑兵 -15%（被冲锋克制）
        UnitType.NAVAL: 0.25,      # 弓兵对水军 +25%
        UnitType.INFANTRY: -0.10,  # 弓兵对步兵 -10%
        UnitType.ARCHER: 0.0,      # 弓兵对弓兵 无克制
    },
}


def get_counter_bonus(attacker_type: UnitType, defender_type: UnitType) -> float:
    """
    获取兵种克制加成

    Args:
        attacker_type: 攻击方兵种
        defender_type: 防御方兵种

    Returns:
        攻击加成系数（0.25 = +25%伤害）
    """
    bonus = COUNTER_TABLE.get(attacker_type, {}).get(defender_type, 0.0)
    if bonus != 0.0:
        logger.debug(f"兵种克制: {attacker_type.value} → {defender_type.value} = {bonus:+.0%}")
    return bonus


# M-1: apply_defense_cap 等已迁移到 server.core.combat_utils，此处通过顶层 import 重新导出
# 保持向后兼容：其他模块可以继续 `from server.core.combat_modifiers import apply_defense_cap`


def calculate_combat_modifiers(
    attacker_unit_type: Optional[UnitType] = None,
    defender_unit_type: Optional[UnitType] = None,
    terrain_defense_bonus: float = 0.0,
    wall_defense_bonus: float = 0.0,
    faction_attack_buff: float = 0.0,
    faction_defense_buff: float = 0.0,
    attacker_is_water_map: bool = False,
    defender_is_water_map: bool = False,
    attacker_has_fire_attack: bool = False,
    defender_is_naval: bool = False,
    defense_cap: float = 2.5,
) -> dict:
    """
    计算综合战斗修正

    Returns:
        {
            "attacker_mult": float,    # 攻击方总倍率
            "defender_mult": float,    # 防御方总倍率（含地形/城防，有上限）
            "counter_bonus": float,    # 兵种克制加成
            "breakdown": str,          # 可读的修正明细
        }
    """
    breakdown_parts = []

    # 1. 兵种克制
    counter_bonus = 0.0
    if attacker_unit_type and defender_unit_type:
        counter_bonus = get_counter_bonus(attacker_unit_type, defender_unit_type)
        if counter_bonus != 0.0:
            breakdown_parts.append(f"兵种克制{counter_bonus:+.0%}")

    # 2. 势力攻击buff
    attacker_mult = 1.0 + faction_attack_buff + counter_bonus
    if faction_attack_buff != 0.0:
        breakdown_parts.append(f"势力攻击{faction_attack_buff:+.0%}")

    # 3. 水域修正
    if attacker_is_water_map and attacker_unit_type == UnitType.NAVAL:
        attacker_mult += 0.30  # 水军在水域获得额外+30%
        breakdown_parts.append("水域优势+30%")
    if defender_is_water_map and defender_unit_type == UnitType.NAVAL:
        faction_defense_buff += 0.30

    # 4. 火攻克制水军
    if attacker_has_fire_attack and defender_is_naval:
        attacker_mult += 0.20
        breakdown_parts.append("火攻克制+20%")

    # 5. 防御方修正（地形 + 城防 + 势力防御buff）
    defender_mult = 1.0 + terrain_defense_bonus + wall_defense_bonus + faction_defense_buff
    if terrain_defense_bonus != 0.0:
        breakdown_parts.append(f"地形防御{terrain_defense_bonus:+.0%}")
    if wall_defense_bonus != 0.0:
        breakdown_parts.append(f"城防{wall_defense_bonus:+.0%}")
    if faction_defense_buff != 0.0:
        breakdown_parts.append(f"势力防御{faction_defense_buff:+.0%}")

    # 6. 应用防御倍率上限
    original_def = defender_mult
    defender_mult = apply_defense_cap(defender_mult, defense_cap)
    if original_def != defender_mult:
        breakdown_parts.append(f"防御上限裁剪({original_def:.2f}x→{defender_mult:.2f}x)")

    breakdown = " | ".join(breakdown_parts) if breakdown_parts else "无修正"

    return {
        "attacker_mult": max(0.1, attacker_mult),    # 最低10%攻击力
        "defender_mult": max(1.0, defender_mult),    # 最低1.0x防御
        "counter_bonus": counter_bonus,
        "breakdown": breakdown,
    }


# M-1: estimate_unit_type_from_faction, FACTION_COMBAT_BUFFS, get_faction_attack_bonus,
# get_faction_defense_bonus, has_fire_attack 等已迁移到 server.core.combat_utils


# ================================================================
# v3.3: 与 unit_counter.py 的桥接（统一两套克制系统）
# ================================================================
# unit_counter.py 使用 6 种兵种（含 spear_pike, siege），combat_modifiers.py 使用 4 种
# 此桥接在需要 6 兵种场景时自动映射

_UNIT_TYPE_EXPANDED = {
    UnitType.CAVALRY: "cavalry",
    UnitType.INFANTRY: "infantry",
    UnitType.NAVAL: "navy",
    UnitType.ARCHER: "archer",
}

_EXPANDED_TO_STANDARD = {
    "cavalry": UnitType.CAVALRY,
    "infantry": UnitType.INFANTRY,
    "spear_pike": UnitType.INFANTRY,   # 枪兵映射到步兵
    "navy": UnitType.NAVAL,
    "archer": UnitType.ARCHER,
    "siege": UnitType.INFANTRY,        # 攻城兵映射到步兵
}


def map_to_expanded_unit(unit: UnitType) -> str:
    """4兵种 → 6兵种映射"""
    return _UNIT_TYPE_EXPANDED.get(unit, "infantry")


def map_to_standard_unit(expanded: str) -> UnitType:
    """6兵种 → 4兵种映射（保留克制关系）"""
    return _EXPANDED_TO_STANDARD.get(expanded, UnitType.INFANTRY)


def calculate_combat_with_expanded_units(
    attacker_units: dict[str, int],   # {"cavalry": 100, "infantry": 200, ...}
    defender_units: dict[str, int],
    terrain: str = "grassland",
    fortification: int = 0,
    faction_buffs: dict = None,
) -> dict:
    """使用6兵种系统计算综合战斗修正（桥接 combat_modifiers + unit_counter）

    统一接口：自动兼容两种兵种表示
    """
    try:
        from server.core.unit_counter import UnitCounterEngine
        from server.models.generals import UNIT_COUNTER_MATRIX
    except ImportError:
        # 降级到4兵种系统
        return _fallback_combat_calc(attacker_units, defender_units, terrain,
                                     fortification, faction_buffs)

    engine = UnitCounterEngine()

    # 计算混编克制
    counter = engine.calculate_mixed_counter(attacker_units, defender_units)

    # 地形修正
    atk_terrain = sum(
        engine.get_terrain_bonus(ut, terrain) * cnt
        for ut, cnt in attacker_units.items()
    ) / max(1, sum(attacker_units.values()))
    def_terrain = sum(
        engine.get_terrain_bonus(ut, terrain) * cnt
        for ut, cnt in defender_units.items()
    ) / max(1, sum(defender_units.values()))

    # 城防
    fort_mult = 1.0 + fortification * 0.2

    # 综合修正
    attacker_mult = counter * atk_terrain
    defender_mult = def_terrain * fort_mult

    return {
        "attacker_mult": max(0.5, attacker_mult),
        "defender_mult": min(2.5, max(1.0, defender_mult)),
        "counter_mult": counter,
        "terrain_mult_atk": atk_terrain,
        "terrain_mult_def": def_terrain,
        "fort_mult": fort_mult,
        "source": "expanded_6unit",
    }


def _fallback_combat_calc(atk_units, def_units, terrain, fort, buffs) -> dict:
    """4兵种降级计算"""
    # 取主力兵种
    atk_main = max(atk_units, key=atk_units.get) if atk_units else "infantry"
    def_main = max(def_units, key=def_units.get) if def_units else "infantry"

    atk_type = _EXPANDED_TO_STANDARD.get(atk_main, UnitType.INFANTRY)
    def_type = _EXPANDED_TO_STANDARD.get(def_main, UnitType.INFANTRY)

    return calculate_combat_modifiers(
        attacker_unit_type=atk_type,
        defender_unit_type=def_type,
        terrain_defense_bonus=0.1 if terrain in ("mountain", "city") else 0.0,
        wall_defense_bonus=fort * 0.15,
        defense_cap=2.5,
    )
