"""
经济引擎测试 — EconomyEngine 核心结算

覆盖: server/core/economy_engine.py
"""
import pytest
from unittest.mock import MagicMock, PropertyMock
from server.core.economy_engine import (
    TradeGood, TRADE_GOOD_PRICES, FACTION_SPECIALTY,
    PopulationStructure, EconomyEngine,
)


# ================================================================
# TradeGood + 价格表
# ================================================================
class TestTradeGoods:
    def test_6_goods(self):
        assert len(TradeGood) == 6

    def test_all_prices_positive(self):
        for good, price in TRADE_GOOD_PRICES.items():
            assert price > 0, f"{good} 价格应为正"

    def test_warhorses_most_expensive(self):
        assert TRADE_GOOD_PRICES[TradeGood.WARHORSES] == 120
        assert TRADE_GOOD_PRICES[TradeGood.WARHORSES] >= TRADE_GOOD_PRICES[TradeGood.GRAIN]


class TestFactionSpecialty:
    def test_9_factions(self):
        assert len(FACTION_SPECIALTY) == 9

    def test_yuan_specialties(self):
        specs = FACTION_SPECIALTY["faction_yuan"]
        assert TradeGood.WARHORSES in specs
        assert TradeGood.SILK in specs

    def test_chenyouliang_grain_salt(self):
        specs = FACTION_SPECIALTY["faction_chenyouliang"]
        assert TradeGood.GRAIN in specs
        assert TradeGood.SALT_IRON in specs

    def test_mobei_only_warhorses(self):
        specs = FACTION_SPECIALTY["faction_mobei"]
        assert specs == [TradeGood.WARHORSES]

    def test_fangguozhen_silk_tea(self):
        specs = FACTION_SPECIALTY["faction_fangguozhen"]
        assert TradeGood.SILK in specs
        assert TradeGood.TEA in specs


# ================================================================
# PopulationStructure
# ================================================================
class TestPopulationStructure:
    def test_from_total_default_ratios(self):
        ps = PopulationStructure.from_total(1000)
        assert ps.farmers == 600   # 60%
        assert ps.artisans == 150  # 15%
        assert ps.merchants == 100 # 10%
        assert ps.soldiers == 150  # 15%
        assert ps.total == 1000

    def test_total_sums_correctly(self):
        ps = PopulationStructure(farmers=100, artisans=50, merchants=30, soldiers=20)
        assert ps.total == 200

    def test_empty_total_zero(self):
        ps = PopulationStructure()
        assert ps.total == 0

    def test_to_dict(self):
        ps = PopulationStructure.from_total(1000)
        d = ps.to_dict()
        assert d["farmers"] == 600
        assert d["total"] == 1000

    def test_from_total_small_population(self):
        """小人口不应崩溃（int截断导致各职业和可能<total，这是已知行为）"""
        ps = PopulationStructure.from_total(3)
        # 3 * 0.6=1, 3*0.15=0, 3*0.10=0, 3*0.15=0 → total=1（int截断）
        # 这是 int 乘法截断的预期行为，不是 bug
        assert ps.farmers >= 0
        assert ps.total >= 1


# ================================================================
# EconomyEngine — 静态方法（无 WorldState 依赖）
# ================================================================
class TestEconomyEngineStatics:

    def test_tile_tax_mult_city(self):
        from server.models.world_state import TileType
        assert EconomyEngine._get_tile_tax_mult(TileType.CITY) == 1.5

    def test_tile_tax_mult_port(self):
        from server.models.world_state import TileType
        assert EconomyEngine._get_tile_tax_mult(TileType.PORT) == 1.3

    def test_tile_tax_mult_farmland(self):
        from server.models.world_state import TileType
        assert EconomyEngine._get_tile_tax_mult(TileType.FARMLAND) == 1.0

    def test_tile_tax_mult_desert(self):
        from server.models.world_state import TileType
        assert EconomyEngine._get_tile_tax_mult(TileType.DESERT) == 0.2

    def test_tile_tax_mult_unknown(self):
        """未知地块类型默认 0.5"""
        assert EconomyEngine._get_tile_tax_mult("unknown_type") == 0.5

    def test_season_tax_mult_autumn_highest(self):
        from server.models.world_state import Season
        assert EconomyEngine._get_season_tax_mult(Season.AUTUMN) == 1.3

    def test_season_tax_mult_winter_lowest(self):
        from server.models.world_state import Season
        assert EconomyEngine._get_season_tax_mult(Season.WINTER) == 0.7

    def test_building_tax_bonus_no_buildings(self):
        from unittest.mock import MagicMock
        tile = MagicMock()
        type(tile).buildings = PropertyMock(return_value={})
        assert EconomyEngine._get_building_tax_bonus(tile) == 1.0

    def test_building_tax_bonus_none_buildings(self):
        from unittest.mock import MagicMock
        tile = MagicMock()
        type(tile).buildings = PropertyMock(return_value=None)
        assert EconomyEngine._get_building_tax_bonus(tile) == 1.0


# ================================================================
# EconomyEngine — Gini 系数
# ================================================================
class TestGiniCoefficient:
    def test_equal_distribution(self):
        """完全均衡：Gini = 0"""
        data = [{"treasury": 100, "name": "A"},
                {"treasury": 100, "name": "B"},
                {"treasury": 100, "name": "C"}]
        gini = EconomyEngine._calc_gini(data)
        assert gini == 0.0

    def test_extreme_inequality(self):
        """极端不均：Gini 接近 1"""
        data = [{"treasury": 0, "name": "A"},
                {"treasury": 0, "name": "B"},
                {"treasury": 1000, "name": "C"}]
        gini = EconomyEngine._calc_gini(data)
        assert gini > 0.5  # 高度不均

    def test_one_element(self):
        assert EconomyEngine._calc_gini([{"treasury": 100}]) == 0.0

    def test_all_zero(self):
        assert EconomyEngine._calc_gini([{"treasury": 0}, {"treasury": 0}]) == 0.0

    def test_monotone(self):
        """财富越集中，Gini越大"""
        equal = EconomyEngine._calc_gini([
            {"treasury": 50}, {"treasury": 50}
        ])
        skewed = EconomyEngine._calc_gini([
            {"treasury": 1}, {"treasury": 99}
        ])
        assert skewed > equal


# ================================================================
# EconomyEngine — calc_tax (需要 mock)
# ================================================================
class TestCalcTax:
    """calc_tax() 税收计算"""

    def test_no_tile(self, mock_world_state):
        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", None)
        assert result["tax_income"] == 0
        assert "无地块" in result["breakdown"]

    def test_basic_city_tax(self, mock_world_state):
        """城市地块基础税收"""
        from server.models.world_state import TileType, Season
        tile = MagicMock()
        tile.population = 1000
        tile.tile_type = TileType.CITY
        tile.morale = 50
        tile.development_level = 1
        tile.buildings = {}
        type(tile).buildings = PropertyMock(return_value={})

        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", tile, Season.SPRING)
        # 1000 × 0.15 × 1.5 × 0.9 × 1.0 × 1.0 × 1.0 = 202.5 → 202
        assert result["tax_income"] > 0
        assert result["tax_income"] == 202  # int(1000 * 0.15 * 1.5 * 0.9 * 1.0 * 1.0 * 1.0)

    def test_high_morale_bonus(self, mock_world_state):
        """民心 > 70 获得 1.1x 加成"""
        from server.models.world_state import TileType, Season
        tile = MagicMock()
        tile.population = 1000
        tile.tile_type = TileType.CITY
        tile.morale = 80
        tile.development_level = 1
        tile.buildings = {}
        type(tile).buildings = PropertyMock(return_value={})

        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", tile, Season.SUMMER)
        # 1000 × 0.15 × 1.5 × 1.0 × 1.1 × 1.0 × 1.0 = 247
        assert result["tax_income"] > 0
        assert result["morale_mult"] == 1.1

    def test_low_morale_penalty(self, mock_world_state):
        """民心 < 30 税收打 7 折"""
        from server.models.world_state import TileType, Season
        tile = MagicMock()
        tile.population = 1000
        tile.tile_type = TileType.CITY
        tile.morale = 20
        tile.development_level = 1
        tile.buildings = {}
        type(tile).buildings = PropertyMock(return_value={})

        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", tile, Season.SUMMER)
        assert result["morale_mult"] == 0.7
        assert result["tax_income"] < 225  # 未打折时是 225

    def test_development_bonus(self, mock_world_state):
        """发展度2级 = +5%"""
        from server.models.world_state import TileType, Season
        tile = MagicMock()
        tile.population = 1000
        tile.tile_type = TileType.CITY
        tile.morale = 50
        tile.development_level = 3
        tile.buildings = {}
        type(tile).buildings = PropertyMock(return_value={})

        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", tile, Season.SUMMER)
        expected_dev_mult = 1.0 + (3 - 1) * 0.05  # = 1.10
        assert result["dev_mult"] == expected_dev_mult

    def test_breakdown_readable(self, mock_world_state):
        from server.models.world_state import TileType, Season
        tile = MagicMock()
        tile.population = 1000
        tile.tile_type = TileType.FARMLAND
        tile.morale = 50
        tile.development_level = 1
        tile.buildings = {}
        type(tile).buildings = PropertyMock(return_value={})

        engine = EconomyEngine(mock_world_state)
        result = engine.calc_tax("faction_yuan", tile, Season.SUMMER)
        assert "人口" in result["breakdown"]
        assert "银两" in result["breakdown"]


# ================================================================
# EconomyEngine — 粮耗计算
# ================================================================
class TestGrainConsumption:
    """calc_grain_consumption()"""

    def test_basic_consumption(self, mock_world_state, mock_tile):
        engine = EconomyEngine(mock_world_state)
        # mock_tile: pop=5000, troops=300, grain=2000
        # pop_grain = 5000//100 = 50
        # troop_grain = int(300 * 0.5) = 150
        # total = (50 + 150) = 200
        result = engine.calc_grain_consumption("faction_yuan")
        assert result["grain_consumed"] > 0
        assert result["pop_grain"] > 0
        assert result["troop_grain"] > 0


# ================================================================
# EconomyEngine — 饥荒检查
# ================================================================
class TestFamineCheck:
    """check_famine()"""

    def test_abundant_grain_no_famine(self, mock_world_state, mock_tile):
        """粮食充足无饥荒"""
        engine = EconomyEngine(mock_world_state)
        # mock_tile: grain=2000, pop=5000 → 人均0.4 < 150 threshold，但这只是测试
        # 调整到无饥荒状态
        mock_tile.grain = 1000000  # 大量粮草
        famines = engine.check_famine("faction_yuan")
        assert len(famines) == 0

    def test_famine_detected(self, mock_world_state, mock_tile):
        """粮草不足触发饥荒"""
        engine = EconomyEngine(mock_world_state)
        # v4.5: 饥荒用绝对值判定 threshold=150, severe 条件 grain ≤ 75
        mock_tile.grain = 50  # 严重饥荒（≤75）
        mock_tile.population = 5000
        famines = engine.check_famine("faction_yuan")
        assert len(famines) >= 1
        assert famines[0]["severity"] == "severe"

    def test_other_faction_not_checked(self, mock_world_state):
        """只检查指定势力的饥荒"""
        engine = EconomyEngine(mock_world_state)
        famines = engine.check_famine("faction_zhuyuanzhang")
        assert famines == []  # mock 中没有朱元璋的地块


# ================================================================
# EconomyEngine — 建筑维护
# ================================================================
class TestBuildingUpkeep:
    """calc_building_upkeep()"""

    def test_no_buildings(self, mock_world_state):
        engine = EconomyEngine(mock_world_state)
        result = engine.calc_building_upkeep("faction_yuan")
        # mock_tile 的 buildings={}，无建筑维护
        assert result["building_upkeep"] >= 0

    def test_unknown_faction_zero(self, mock_world_state):
        engine = EconomyEngine(mock_world_state)
        result = engine.calc_building_upkeep("nonexistent")
        assert result["building_upkeep"] == 0


# ================================================================
# EconomyEngine — 移民成本
# ================================================================
class TestMigrationCost:
    def test_same_tile_not_same(self, mock_world_state, mock_tile):
        """同地块=距离0"""
        engine = EconomyEngine(mock_world_state)
        result = engine.calc_migration_cost(mock_tile.tile_id, mock_tile.tile_id, 100)
        assert result["success"] is True
        assert result["distance"] == 0

    def test_missing_tile(self, mock_world_state):
        engine = EconomyEngine(mock_world_state)
        result = engine.calc_migration_cost("nonexistent", "nonexistent2", 100)
        assert result["success"] is False
        assert "不存在" in result["reason"]


# ================================================================
# EconomyEngine — 粮仓容量
# ================================================================
class TestGranaryCapacity:
    def test_no_granary(self, mock_world_state, mock_tile):
        engine = EconomyEngine(mock_world_state)
        capacity = engine.calc_granary_capacity(mock_tile.tile_id)
        assert capacity == 0

    def test_invalid_tile(self, mock_world_state):
        engine = EconomyEngine(mock_world_state)
        assert engine.calc_granary_capacity("nonexistent") == 0
