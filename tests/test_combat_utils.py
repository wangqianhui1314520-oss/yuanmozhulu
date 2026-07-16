"""
战斗工具函数测试 — 零依赖纯函数

覆盖: server/core/combat_utils.py 全部函数
"""
import pytest
from server.core.combat_utils import (
    apply_defense_cap,
    get_faction_attack_bonus,
    get_faction_defense_bonus,
    has_fire_attack,
    estimate_unit_type_from_faction,
    FACTION_COMBAT_BUFFS,
    UnitType,
)


class TestDefenseCap:
    """apply_defense_cap()"""

    def test_below_cap_unchanged(self):
        assert apply_defense_cap(1.5) == 1.5
        assert apply_defense_cap(2.0) == 2.0

    def test_at_cap_boundary(self):
        assert apply_defense_cap(2.5) == 2.5

    def test_above_cap_clamped(self):
        assert apply_defense_cap(3.0) == 2.5
        assert apply_defense_cap(10.0) == 2.5

    def test_custom_cap(self):
        assert apply_defense_cap(3.0, max_cap=3.0) == 3.0
        assert apply_defense_cap(4.0, max_cap=3.0) == 3.0

    def test_no_reduction_below_1(self):
        """1.0以下的防御倍率不应被裁剪"""
        assert apply_defense_cap(0.5) == 0.5


class TestFactionBuffs:
    """FACTION_COMBAT_BUFFS 常量表"""

    def test_nine_factions(self):
        assert len(FACTION_COMBAT_BUFFS) == 9

    def test_yuan_cavalry_attack(self):
        assert FACTION_COMBAT_BUFFS["faction_yuan"]["cavalry_attack"] == 0.35

    def test_mobei_highest_cavalry(self):
        assert FACTION_COMBAT_BUFFS["faction_mobei"]["cavalry_attack"] == 0.45

    def test_zhuyuanzhang_fire_attack(self):
        assert FACTION_COMBAT_BUFFS["faction_zhuyuanzhang"]["fire_attack"] == 0.20

    def test_fangguozhen_naval_and_defense(self):
        buffs = FACTION_COMBAT_BUFFS["faction_fangguozhen"]
        assert buffs["naval_attack"] == 0.40
        assert buffs["defense"] == 0.30

    def test_mingyuzhen_defense(self):
        assert FACTION_COMBAT_BUFFS["faction_mingyuzhen"]["defense"] == 0.40


class TestFactionAttackBonus:
    """get_faction_attack_bonus()"""

    def test_yuan_cavalry(self):
        assert get_faction_attack_bonus("faction_yuan", UnitType.CAVALRY) == 0.35

    def test_yuan_infantry_zero(self):
        assert get_faction_attack_bonus("faction_yuan", UnitType.INFANTRY) == 0.0

    def test_yuan_naval_zero(self):
        assert get_faction_attack_bonus("faction_yuan", UnitType.NAVAL) == 0.0

    def test_chenyouliang_naval(self):
        assert get_faction_attack_bonus("faction_chenyouliang", UnitType.NAVAL) == 0.30

    def test_fangguozhen_naval(self):
        assert get_faction_attack_bonus("faction_fangguozhen", UnitType.NAVAL) == 0.40

    def test_zhuyuanzhang_no_cavalry(self):
        assert get_faction_attack_bonus("faction_zhuyuanzhang", UnitType.CAVALRY) == 0.0

    def test_unknown_faction_zero(self):
        assert get_faction_attack_bonus("faction_nonexistent", UnitType.CAVALRY) == 0.0

    def test_no_unit_type_zero(self):
        assert get_faction_attack_bonus("faction_yuan", None) == 0.0


class TestFactionDefenseBonus:
    """get_faction_defense_bonus()"""

    def test_yuan_no_defense(self):
        assert get_faction_defense_bonus("faction_yuan") == 0.0

    def test_mingyuzhen_defense(self):
        assert get_faction_defense_bonus("faction_mingyuzhen") == 0.40

    def test_fangguozhen_defense(self):
        assert get_faction_defense_bonus("faction_fangguozhen") == 0.30

    def test_unknown_faction_zero(self):
        assert get_faction_defense_bonus("faction_nonexistent") == 0.0


class TestFireAttack:
    """has_fire_attack()"""

    def test_zhuyuanzhang_has_fire(self):
        assert has_fire_attack("faction_zhuyuanzhang") is True

    def test_yuan_no_fire(self):
        assert has_fire_attack("faction_yuan") is False

    def test_chenyouliang_no_fire(self):
        assert has_fire_attack("faction_chenyouliang") is False

    def test_unknown_faction_no_fire(self):
        assert has_fire_attack("faction_nonexistent") is False


class TestEstimateUnitType:
    """estimate_unit_type_from_faction()"""

    def test_cavalry_factions(self):
        cavalry = {"faction_yuan", "faction_wangbaobao", "faction_mobei"}
        for fid in cavalry:
            assert estimate_unit_type_from_faction(fid) == UnitType.CAVALRY, fid

    def test_naval_factions(self):
        naval = {"faction_chenyouliang", "faction_fangguozhen", "faction_zhangshicheng"}
        for fid in naval:
            assert estimate_unit_type_from_faction(fid) == UnitType.NAVAL, fid

    def test_others_infantry(self):
        others = {"faction_zhuyuanzhang", "faction_xushouhui", "faction_mingyuzhen"}
        for fid in others:
            assert estimate_unit_type_from_faction(fid) == UnitType.INFANTRY, fid

    def test_water_terrain_always_naval(self):
        """水域地块无视势力类型，总是水军"""
        for fid in ["faction_yuan", "faction_zhuyuanzhang"]:
            assert estimate_unit_type_from_faction(fid, "water") == UnitType.NAVAL
            assert estimate_unit_type_from_faction(fid, "coastal") == UnitType.NAVAL
            assert estimate_unit_type_from_faction(fid, "ocean") == UnitType.NAVAL

    def test_grassland_no_override(self):
        """非水域地块正常按势力判断"""
        assert estimate_unit_type_from_faction("faction_yuan", "grassland") == UnitType.CAVALRY


class TestUnitTypeEnum:
    """UnitType 枚举验证"""

    def test_four_types(self):
        types = list(UnitType)
        assert len(types) == 4

    def test_all_values_are_strings(self):
        for t in UnitType:
            assert isinstance(t.value, str)

    def test_unique_values(self):
        values = [t.value for t in UnitType]
        assert len(values) == len(set(values))
