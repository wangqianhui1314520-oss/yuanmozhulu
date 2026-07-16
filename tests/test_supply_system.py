"""
补给线系统测试 — SupplyEngine 核心行为

覆盖: server/core/supply_system.py
"""
import pytest
from unittest.mock import MagicMock, PropertyMock
from server.core.supply_system import SupplyEngine, SUPPLY_CONFIG


# ================================================================
# SUPPLY_CONFIG 常量
# ================================================================
class TestSupplyConfig:
    def test_max_distance_is_4(self):
        assert SUPPLY_CONFIG["max_supply_distance"] == 4

    def test_safe_distance_is_2(self):
        assert SUPPLY_CONFIG["safe_supply_distance"] == 2

    def test_broken_attrition_range(self):
        """逃散率应在合理范围 [0, 1]"""
        assert 0 <= SUPPLY_CONFIG["broken_attrition_base"] <= 1
        assert 0 <= SUPPLY_CONFIG["broken_attrition_max"] <= 1
        assert SUPPLY_CONFIG["broken_attrition_base"] <= SUPPLY_CONFIG["broken_attrition_max"]

    def test_winter_bonus_positive(self):
        assert SUPPLY_CONFIG["winter_attrition_bonus"] > 0

    def test_supply_base_types_include_city(self):
        from server.models.world_state import TileType
        assert TileType.CITY in SUPPLY_CONFIG["supply_base_types"]
        assert TileType.PORT in SUPPLY_CONFIG["supply_base_types"]


# ================================================================
# SupplyEngine — 初始化 + 静态方法
# ================================================================
class TestSupplyEngineInit:
    def test_init_creates_empty_caches(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        assert engine._territory_adjacency == {}
        assert engine._supply_bases == {}
        assert engine._bfs_cache == {}

    def test_world_reference(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        assert engine.world is mock_world_state


# ================================================================
# SupplyEngine — 逃散率计算 (_calc_attrition)
# ================================================================
class TestCalcAttrition:
    def test_not_broken_is_zero(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        assert engine._calc_attrition(3, is_broken=False) == 0.0

    def test_broken_at_exact_max(self, mock_world_state):
        """刚好超出上限 1 格"""
        engine = SupplyEngine(mock_world_state)
        rate = engine._calc_attrition(
            distance=SUPPLY_CONFIG["max_supply_distance"] + 1,
            is_broken=True,
        )
        assert rate > SUPPLY_CONFIG["broken_attrition_base"]
        assert rate <= SUPPLY_CONFIG["broken_attrition_max"]

    def test_broken_rate_not_exceed_max(self, mock_world_state):
        """远超上限时也不超过 max"""
        engine = SupplyEngine(mock_world_state)
        rate = engine._calc_attrition(distance=999, is_broken=True)
        assert rate <= SUPPLY_CONFIG["broken_attrition_max"]

    def test_broken_at_base(self, mock_world_state):
        """刚好在上限距离，不断补给"""
        engine = SupplyEngine(mock_world_state)
        rate = engine._calc_attrition(
            distance=SUPPLY_CONFIG["max_supply_distance"],
            is_broken=True,
        )
        # 超出的 extra = (4 - 4) * 0.02 = 0，所以 rate = base = 0.08
        assert rate == SUPPLY_CONFIG["broken_attrition_base"]


# ================================================================
# SupplyEngine — BFS 距离
# ================================================================
class TestBFSDistance:
    def test_same_tile_zero(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        dist = engine._bfs_distance("10,10", "10,10")
        assert dist == 0

    def test_no_adjacency_unreachable(self, mock_world_state):
        """无邻接关系时返回999"""
        engine = SupplyEngine(mock_world_state)
        dist = engine._bfs_distance("10,10", "99,99")
        assert dist == 999

    def test_cached_bidirectional(self, mock_world_state):
        """缓存双向读取"""
        engine = SupplyEngine(mock_world_state)
        engine._territory_adjacency = {
            "10,10": ["11,10"],
            "11,10": ["10,10", "12,10"],
            "12,10": ["11,10"],
        }
        dist1 = engine._bfs_distance_cached("10,10", "12,10")
        assert dist1 == 2
        # 缓存命中
        dist2 = engine._bfs_distance_cached("12,10", "10,10")
        assert dist2 == 2


# ================================================================
# SupplyEngine — 邻接判断 (_are_adjacent)
# ================================================================
class TestAreAdjacent:
    def test_adjacent_right(self, mock_world_state):
        """(10,10) ↔ (11,10) 相邻"""
        engine = SupplyEngine(mock_world_state)
        a = MagicMock()
        a.q, a.r = 10, 10
        b = MagicMock()
        b.q, b.r = 11, 10
        assert engine._are_adjacent(a, b) is True

    def test_adjacent_diagonal_is_false(self, mock_world_state):
        """六边形对角线 (1,1) 不算合法邻居"""
        engine = SupplyEngine(mock_world_state)
        a = MagicMock()
        a.q, a.r = 10, 10
        b = MagicMock()
        b.q, b.r = 11, 11
        assert engine._are_adjacent(a, b) is False

    def test_not_adjacent_far(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        a = MagicMock()
        a.q, a.r = 10, 10
        b = MagicMock()
        b.q, b.r = 15, 20
        assert engine._are_adjacent(a, b) is False

    def test_same_tile_not_adjacent(self, mock_world_state):
        """同格不算相邻（由调用方排除）"""
        engine = SupplyEngine(mock_world_state)
        a = MagicMock()
        a.q, a.r = 0, 0
        b = MagicMock()
        b.q, b.r = 0, 0
        assert engine._are_adjacent(a, b) is False


# ================================================================
# SupplyEngine — 补给状态查询
# ================================================================
class TestSupplyStatus:
    def test_no_supply_line(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        status = engine.get_supply_status("nonexistent")
        assert status is None

    def test_get_faction_summary_empty(self, mock_world_state):
        engine = SupplyEngine(mock_world_state)
        summary = engine.get_faction_supply_summary("faction_yuan")
        assert summary["total_supply_lines"] == 0
        assert summary["broken_lines"] == 0


# ================================================================
# SupplyEngine — _find_nearest_supply_base_fast
# ================================================================
class TestFindNearestBase:
    def test_no_bases(self, mock_world_state, mock_tile):
        """无补给基地 → 回退遍历所有tile"""
        engine = SupplyEngine(mock_world_state)
        engine._supply_bases = {}
        # mock_world_state 的 tiles 中只有一个 tile (mock_tile)
        # 检查是否返回或 None
        result = engine._find_nearest_supply_base_fast(mock_tile)
        # 即使找不到也不崩溃
        assert result is None or hasattr(result, 'tile_id')

    def test_direct_base_match(self, mock_world_state, mock_tile):
        """当 tile 本身就是基地"""
        engine = SupplyEngine(mock_world_state)
        mock_tile.faction_id = "faction_yuan"
        mock_tile.is_supply_base = True
        engine._supply_bases = {"faction_yuan": [mock_tile]}
        engine._territory_adjacency = {mock_tile.tile_id: []}
        result = engine._find_nearest_supply_base_fast(mock_tile)
        # BFS 距离0，应该找到自己
        assert result is not None


# ================================================================
# SupplyEngine — build_supply_network 完整性
# ================================================================
class TestBuildSupplyNetwork:
    def test_build_network_no_crash(self, mock_world_state, mock_tile):
        """构建补给网络不崩溃"""
        from server.models.world_state import TileType
        # 设置 tile 为城市（可作为基地）
        mock_tile.faction_id = "faction_yuan"
        mock_tile.tile_type = TileType.CITY
        mock_tile.is_capital = True
        mock_tile.troops = 200
        mock_tile.q = 21
        mock_tile.r = 15
        mock_tile.tile_id = "21,15"

        engine = SupplyEngine(mock_world_state)
        # 应不抛出异常
        try:
            engine.build_supply_network()
        except Exception as e:
            pytest.fail(f"build_supply_network() 异常: {e}")

    def test_process_attrition_no_crash(self, mock_world_state):
        """处理补给逃散不崩溃"""
        engine = SupplyEngine(mock_world_state)
        mock_world_state.supply_lines = {}
        try:
            result = engine.process_supply_attrition()
            assert "supply_lines_total" in result
            assert "broken_lines" in result
            assert "desertion_total" in result
        except Exception as e:
            pytest.fail(f"process_supply_attrition() 异常: {e}")

    def test_build_adjacency_empty_world(self, mock_world_state):
        """空世界构建邻接图不崩溃"""
        engine = SupplyEngine(mock_world_state)
        try:
            engine._build_adjacency()
        except Exception as e:
            pytest.fail(f"_build_adjacency() 异常: {e}")
