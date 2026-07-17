"""
战斗工具函数（零依赖模块）· 元末逐鹿 4.0

从 combat_modifiers.py 抽离，消除 combat_modifiers ↔ unit_counter 双向循环依赖。
本模块不导入任何 core 模块，可被任意模块安全引用。

提取的函数：
- apply_defense_cap: 防御倍率上限裁剪
- get_faction_attack_bonus: 势力攻击加成
- get_faction_defense_bonus: 势力防御加成
- estimate_unit_type_from_faction: 势力兵种推断
- has_fire_attack: 火攻能力判断
- FACTION_COMBAT_BUFFS: 势力战斗buff常量表
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger("yuanmo.combat.utils")


class UnitType(Enum):
    """兵种类型（与 combat_modifiers.py 保持独立定义，避免导入循环）"""
    CAVALRY = "cavalry"
    INFANTRY = "infantry"
    NAVAL = "naval"
    ARCHER = "archer"


# ================================================================
# 势力buff常量（数据源自 factions.json，数值调整参考 game_const.yaml 平衡参数）
# ================================================================
FACTION_COMBAT_BUFFS: dict[str, dict] = {
    "faction_yuan": {"cavalry_attack": 0.35},
    "faction_wangbaobao": {"cavalry_attack": 0.40, "general_loyalty": 0.20},
    "faction_mobei": {"cavalry_attack": 0.45, "victory_gold": 0.30},
    "faction_chenyouliang": {"naval_attack": 0.30, "grain_production": 0.20},
    "faction_fangguozhen": {"naval_attack": 0.40, "defense": 0.30, "sea_speed": 0.30},
    "faction_zhangshicheng": {"tax_income": 0.30, "trade_income": 0.25},
    "faction_zhuyuanzhang": {"refugee_convert": 0.30, "garrison_food": -0.20, "fire_attack": 0.20},
    "faction_xushouhui": {"recruit_efficiency": 0.50, "morale_convert": 0.20},
    "faction_mingyuzhen": {"defense": 0.40, "grain_production": 0.25},
}


def apply_defense_cap(defense_mult: float, max_cap: float = 2.5) -> float:
    """应用防御倍率上限，防止叠加效应过强"""
    if defense_mult > max_cap:
        logger.info(f"防御倍率 {defense_mult:.2f}x 超过上限 {max_cap}x，已裁剪")
        return max_cap
    return defense_mult


def get_faction_attack_bonus(faction_id: str, unit_type: Optional[UnitType] = None) -> float:
    """获取势力的攻击加成"""
    buffs = FACTION_COMBAT_BUFFS.get(faction_id, {})
    bonus = 0.0
    if unit_type == UnitType.CAVALRY:
        bonus += buffs.get("cavalry_attack", 0.0)
    elif unit_type == UnitType.NAVAL:
        bonus += buffs.get("naval_attack", 0.0)
    return bonus


def get_faction_defense_bonus(faction_id: str) -> float:
    """获取势力的防御加成"""
    buffs = FACTION_COMBAT_BUFFS.get(faction_id, {})
    return buffs.get("defense", 0.0)


def has_fire_attack(faction_id: str) -> bool:
    """检查势力是否有火攻能力"""
    buffs = FACTION_COMBAT_BUFFS.get(faction_id, {})
    return buffs.get("fire_attack", 0.0) > 0.0


def estimate_unit_type_from_faction(faction_id: str, tile_terrain: str = "") -> UnitType:
    """根据势力ID和地块地形推断主要兵种类型"""
    if tile_terrain in ("water", "coastal", "ocean"):
        return UnitType.NAVAL

    cavalry_factions = {"faction_yuan", "faction_wangbaobao", "faction_mobei"}
    naval_factions = {"faction_chenyouliang", "faction_fangguozhen", "faction_zhangshicheng"}

    if faction_id in cavalry_factions:
        return UnitType.CAVALRY
    if faction_id in naval_factions:
        return UnitType.NAVAL

    return UnitType.INFANTRY
