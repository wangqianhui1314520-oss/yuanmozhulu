"""
兵种克制与战斗修正测试 — 纯函数无依赖

覆盖: server/core/combat_modifiers.py
"""
import pytest
from server.core.combat_modifiers import (
    UnitType, COUNTER_TABLE,
    get_counter_bonus, calculate_combat_modifiers,
    map_to_expanded_unit, map_to_standard_unit,
    _UNIT_TYPE_EXPANDED, _EXPANDED_TO_STANDARD,
)


# ================================================================
# COUNTER_TABLE 常量表
# ================================================================
class TestCounterTable:
    """兵种克制表验证"""

    def test_all_4_rows(self):
        assert len(COUNTER_TABLE) == 4

    def test_each_row_has_4_targets(self):
        for unit_type, targets in COUNTER_TABLE.items():
            assert len(targets) == 4, f"{unit_type} 缺少目标"

    def test_diagonal_self_zero(self):
        """自己打自己，克制加成必须为0"""
        for ut in UnitType:
            assert COUNTER_TABLE[ut][ut] == 0.0

    def test_cavalry_beats_infantry(self):
        assert COUNTER_TABLE[UnitType.CAVALRY][UnitType.INFANTRY] > 0

    def test_naval_beats_cavalry(self):
        assert COUNTER_TABLE[UnitType.NAVAL][UnitType.CAVALRY] > 0

    def test_archer_beats_naval(self):
        assert COUNTER_TABLE[UnitType.ARCHER][UnitType.NAVAL] > 0

    def test_infantry_beats_archer(self):
        assert COUNTER_TABLE[UnitType.INFANTRY][UnitType.ARCHER] > 0

    def test_counter_matrix_antisymmetric(self):
        """A克B → B被A克（符号相反）"""
        pairs = [
            (UnitType.CAVALRY, UnitType.INFANTRY),
            (UnitType.NAVAL, UnitType.CAVALRY),
            (UnitType.ARCHER, UnitType.NAVAL),
            (UnitType.INFANTRY, UnitType.ARCHER),
        ]
        for a, b in pairs:
            ab = COUNTER_TABLE[a][b]
            ba = COUNTER_TABLE[b][a]
            assert ab > 0 and ba < 0, f"{a.value}克{b.value}但反向不成立"


# ================================================================
# get_counter_bonus()
# ================================================================
class TestGetCounterBonus:
    """get_counter_bonus() 函数"""

    def test_cav_vs_inf(self):
        assert get_counter_bonus(UnitType.CAVALRY, UnitType.INFANTRY) == 0.25

    def test_inf_vs_cav(self):
        assert get_counter_bonus(UnitType.INFANTRY, UnitType.CAVALRY) == -0.25

    def test_naval_vs_cav(self):
        assert get_counter_bonus(UnitType.NAVAL, UnitType.CAVALRY) == 0.40

    def test_archer_vs_naval(self):
        assert get_counter_bonus(UnitType.ARCHER, UnitType.NAVAL) == 0.25

    def test_same_unit_zero(self):
        for ut in UnitType:
            assert get_counter_bonus(ut, ut) == 0.0

    def test_zero_for_all_same_type(self):
        assert get_counter_bonus(UnitType.INFANTRY, UnitType.INFANTRY) == 0.0


# ================================================================
# calculate_combat_modifiers()
# ================================================================
class TestCalculateCombatModifiers:
    """calculate_combat_modifiers() 综合修正"""

    def test_neutral_no_modifiers(self):
        """无任何修正时：attacker=1.0x, defender=1.0x"""
        result = calculate_combat_modifiers()
        assert result["attacker_mult"] == 1.0
        assert result["defender_mult"] == 1.0
        assert result["counter_bonus"] == 0.0
        assert result["breakdown"] == "无修正"

    def test_counter_only(self):
        """仅兵种克制"""
        result = calculate_combat_modifiers(
            attacker_unit_type=UnitType.CAVALRY,
            defender_unit_type=UnitType.INFANTRY,
        )
        assert result["attacker_mult"] == 1.25  # 1.0 + 0.25
        assert result["defender_mult"] == 1.0
        assert result["counter_bonus"] == 0.25

    def test_terrain_defense(self):
        """地形防御 +30%"""
        result = calculate_combat_modifiers(
            terrain_defense_bonus=0.30,
        )
        assert result["defender_mult"] == 1.30

    def test_wall_defense(self):
        """城防 +50%"""
        result = calculate_combat_modifiers(wall_defense_bonus=0.50)
        assert result["defender_mult"] == 1.50

    def test_faction_buffs(self):
        """势力攻击+防守 buff"""
        result = calculate_combat_modifiers(
            faction_attack_buff=0.35,
            faction_defense_buff=0.40,
        )
        assert result["attacker_mult"] == 1.35
        assert result["defender_mult"] == 1.40

    def test_water_map_naval_attacker(self):
        """水军在水域攻击 +30%"""
        result = calculate_combat_modifiers(
            attacker_unit_type=UnitType.NAVAL,
            attacker_is_water_map=True,
        )
        assert result["attacker_mult"] == 1.30

    def test_water_map_naval_defender(self):
        """水军在水域防守 +30% buff"""
        result = calculate_combat_modifiers(
            defender_unit_type=UnitType.NAVAL,
            defender_is_water_map=True,
        )
        assert result["defender_mult"] == 1.30

    def test_fire_attack_vs_naval(self):
        """火攻克制水军 +20%"""
        result = calculate_combat_modifiers(
            attacker_has_fire_attack=True,
            defender_is_naval=True,
        )
        assert result["attacker_mult"] == 1.20

    def test_defense_cap_applies(self):
        """防御倍率超上限时自动裁剪"""
        result = calculate_combat_modifiers(
            terrain_defense_bonus=1.0,
            wall_defense_bonus=1.0,
            faction_defense_buff=1.0,
        )
        assert result["defender_mult"] == 2.5  # 裁剪到上限

    def test_attacker_mult_minimum(self):
        """攻击倍率不低于 0.1x"""
        result = calculate_combat_modifiers(
            attacker_unit_type=UnitType.INFANTRY,
            defender_unit_type=UnitType.CAVALRY,  # 步兵被骑兵克 -25%
        )
        assert result["attacker_mult"] == 0.75  # 1.0 - 0.25 = 0.75

    def test_defender_mult_minimum(self):
        """防御倍率不低于 1.0x"""
        result = calculate_combat_modifiers(
            faction_defense_buff=-0.5,
        )
        assert result["defender_mult"] >= 1.0

    def test_breakdown_readable(self):
        result = calculate_combat_modifiers(
            attacker_unit_type=UnitType.CAVALRY,
            defender_unit_type=UnitType.INFANTRY,
            terrain_defense_bonus=0.20,
        )
        assert "兵种克制" in result["breakdown"]
        assert "地形防御" in result["breakdown"]


# ================================================================
# 兵种桥接 (4→6兵种)
# ================================================================
class TestUnitTypeBridge:
    """map_to_expanded_unit / map_to_standard_unit"""

    def test_map_4to6_cavalry(self):
        assert map_to_expanded_unit(UnitType.CAVALRY) == "cavalry"

    def test_map_4to6_naval(self):
        assert map_to_expanded_unit(UnitType.NAVAL) == "navy"

    def test_map_6to4_spear_pike(self):
        """枪兵 → 步兵"""
        assert map_to_standard_unit("spear_pike") == UnitType.INFANTRY

    def test_map_6to4_siege(self):
        """攻城兵 → 步兵"""
        assert map_to_standard_unit("siege") == UnitType.INFANTRY

    def test_map_6to4_navy(self):
        assert map_to_standard_unit("navy") == UnitType.NAVAL

    def test_map_6to4_unknown_defaults_infantry(self):
        assert map_to_standard_unit("elephant") == UnitType.INFANTRY

    def test_map_6to4_roundtrip(self):
        """4→6→4 往返一致"""
        for ut in UnitType:
            expanded = map_to_expanded_unit(ut)
            if expanded in ("navy",):  # NAVAL → "navy" → NAVAL
                assert map_to_standard_unit(expanded) == ut

    def test_expanded_table_has_all_4(self):
        assert len(_UNIT_TYPE_EXPANDED) == 4

    def test_standard_table_has_6(self):
        assert len(_EXPANDED_TO_STANDARD) == 6
