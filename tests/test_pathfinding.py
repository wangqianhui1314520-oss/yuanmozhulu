"""
寻路与连通性测试 — 纯函数无外部依赖

覆盖: server/map/pathfinding.py 全部函数
"""
import pytest
from server.map.hex_grid import HexCoord
from server.map.pathfinding import (
    a_star_pathfind, PathResult,
    check_supply_connectivity, ConnectivityResult,
    find_connected_components, is_territory_contiguous, find_enclaves,
    hex_distance_batch, find_nearest_faction_tile,
    validate_march_path,
    _parse_tile_key, _tile_key_to_offset_key,
)


# ================================================================
# _parse_tile_key / _tile_key_to_offset_key
# ================================================================
class TestTileKeyParsing:
    """键格式解析"""

    def test_parse_comma_format(self):
        assert _parse_tile_key("21,15") == (21, 15)

    def test_parse_hex_format(self):
        assert _parse_tile_key("hex_21_15") == (21, 15)

    def test_convert_hex_to_offset(self):
        assert _tile_key_to_offset_key("hex_21_15") == "21,15"

    def test_convert_comma_is_idempotent(self):
        assert _tile_key_to_offset_key("21,15") == "21,15"


# ================================================================
# A* 寻路
# ================================================================
class TestAStarPathfind:
    """a_star_pathfind()"""

    def test_same_start_end(self):
        """起点=终点"""
        start = HexCoord(10, 10)
        result = a_star_pathfind(start, start)
        assert result.found is True
        assert result.cost == 0.0
        assert result.steps == 0
        assert len(result.path) == 1

    def test_direct_adjacent(self):
        """相邻格直接到达"""
        start = HexCoord(10, 10)
        end = HexCoord(11, 10)
        result = a_star_pathfind(start, end)
        assert result.found is True
        assert result.steps == 1
        assert result.path[0] == start
        assert result.path[-1] == end

    def test_simple_path(self):
        """简单直线路径"""
        start = HexCoord(10, 10)
        end = HexCoord(10, 15)
        result = a_star_pathfind(start, end)
        assert result.found is True
        assert result.steps == 5

    def test_start_blocked(self):
        """起点被阻挡"""
        start = HexCoord(10, 10)
        end = HexCoord(12, 10)
        result = a_star_pathfind(start, end, blocked={"10,10"})
        assert result.found is False

    def test_end_blocked(self):
        """终点被阻挡"""
        start = HexCoord(10, 10)
        end = HexCoord(12, 10)
        result = a_star_pathfind(start, end, blocked={"12,10"})
        assert result.found is False

    def test_wall_in_middle(self):
        """中间有墙需要绕路"""
        start = HexCoord(10, 10)
        end = HexCoord(12, 10)
        blocked = {"11,10"}  # 正中间阻挡
        result = a_star_pathfind(start, end, blocked=blocked)
        assert result.found is True
        assert result.steps > 2  # 必须绕路

    def test_move_costs(self):
        """不同格子的移动代价"""
        start = HexCoord(10, 10)
        end = HexCoord(12, 10)
        costs = {"11,10": 3.0}  # 中间格高代价
        result = a_star_pathfind(start, end, move_costs=costs)
        assert result.found is True
        assert result.cost > 2.0  # 至少 1+3=4

    def test_path_does_not_contain_blocked(self):
        """路径不包含阻挡格"""
        start = HexCoord(10, 10)
        end = HexCoord(12, 10)
        blocked = {"11,10"}  # 阻挡在中间
        result = a_star_pathfind(start, end, blocked=blocked)
        path_keys = {c.to_key() for c in result.path}
        assert "11,10" not in path_keys

    def test_no_path_returns_empty(self):
        """不可达时返回空路径"""
        # 用 max_steps 限制制造不可达
        start = HexCoord(10, 10)
        end = HexCoord(21, 31)
        result = a_star_pathfind(start, end, max_steps=0)
        assert result.found is False
        assert result.cost == float('inf')


# ================================================================
# 补给连通性
# ================================================================
class TestSupplyConnectivity:
    """check_supply_connectivity()"""

    def test_same_tile_connected(self):
        result = check_supply_connectivity("10,10", "10,10", {"10,10"})
        assert result.connected is True
        assert result.component_size == 1

    def test_adjacent_owned_tiles(self):
        faction_tiles = {"10,10", "11,10"}
        result = check_supply_connectivity("10,10", "11,10", faction_tiles)
        assert result.connected is True

    def test_tile_not_in_faction(self):
        faction_tiles = {"10,10"}
        result = check_supply_connectivity("10,10", "20,20", faction_tiles)
        assert result.connected is False

    def test_blocked_prevent_connection(self):
        """阻挡格切断补给"""
        faction_tiles = {"10,10", "11,10", "12,10"}
        blocked = {"11,10"}
        result = check_supply_connectivity("10,10", "12,10", faction_tiles, blocked)
        assert result.connected is False

    def test_hex_format_support(self):
        """兼容 hex_col_row 格式"""
        # 两个相邻格子，用 hex_ 格式
        faction_tiles = {"hex_10_10", "hex_11_10"}
        result = check_supply_connectivity("hex_10_10", "hex_11_10", faction_tiles)
        assert result.connected is True


# ================================================================
# 连通分量分析
# ================================================================
class TestConnectedComponents:
    """find_connected_components / is_territory_contiguous / find_enclaves"""

    def test_single_block(self):
        """单独一块领土"""
        tiles = {"10,10", "11,10", "12,10"}
        components = find_connected_components(tiles)
        assert len(components) == 1
        assert len(components[0]) == 3

    def test_two_disconnected_blocks(self):
        """两块飞地"""
        tiles = {"10,10", "11,10", "20,20", "21,20"}
        components = find_connected_components(tiles)
        assert len(components) == 2
        # 按大小降序
        assert len(components[0]) >= len(components[1])

    def test_is_contiguous_true(self):
        assert is_territory_contiguous({"10,10", "11,10"}) is True

    def test_is_contiguous_false(self):
        assert is_territory_contiguous({"10,10", "20,20"}) is False

    def test_find_enclaves(self):
        tiles = {
            "10,10", "11,10", "12,10",  # 主领土
            "20,20", "21,20",            # 飞地
        }
        enclaves = find_enclaves(tiles)
        assert len(enclaves) == 1
        assert len(enclaves[0]) == 2

    def test_no_enclaves(self):
        tiles = {"10,10", "11,10", "12,10"}
        assert find_enclaves(tiles) == []

    def test_blocked_creates_components(self):
        """阻挡断开连通分量"""
        tiles = {"10,10", "11,10", "12,10", "13,10"}
        blocked = {"11,10", "12,10"}  # 切断中间
        components = find_connected_components(tiles, blocked=blocked)
        assert len(components) == 2  # 两块断开


# ================================================================
# 批量距离
# ================================================================
class TestHexDistanceBatch:
    def test_empty_targets(self):
        assert hex_distance_batch(HexCoord(10, 10), []) == []

    def test_sorted_by_distance(self):
        origin = HexCoord(10, 10)
        targets = [
            HexCoord(15, 15),
            HexCoord(11, 10),
            HexCoord(10, 15),
        ]
        results = hex_distance_batch(origin, targets)
        # 第一个应该是最近的（11,10 距离=1）
        assert results[0][0] == HexCoord(11, 10)
        assert results[0][1] == 1


# ================================================================
# find_nearest_faction_tile
# ================================================================
class TestFindNearestFactionTile:
    def test_empty_set(self):
        coord, dist = find_nearest_faction_tile(HexCoord(10, 10), set())
        assert coord is None
        assert dist == float('inf')

    def test_direct_match(self):
        tiles = {"10,10"}
        coord, dist = find_nearest_faction_tile(HexCoord(10, 10), tiles)
        assert coord == HexCoord(10, 10)
        assert dist == 0

    def test_adjacent_tile(self):
        tiles = {"11,10"}
        coord, dist = find_nearest_faction_tile(HexCoord(10, 10), tiles)
        assert coord == HexCoord(11, 10)
        assert dist == 1

    def test_small_faction_direct_search(self):
        """小势力 (<30 tiles) 直接遍历"""
        tiles = {f"{10+i},{10}" for i in range(5)}
        coord, dist = find_nearest_faction_tile(HexCoord(20, 20), tiles)
        assert coord is not None
        assert dist > 0


# ================================================================
# 行军路径验证
# ================================================================
class TestValidateMarchPath:
    def test_empty_path(self):
        valid, reason = validate_march_path([], set())
        assert valid is False
        assert "路径为空" in reason

    def test_single_tile(self):
        path = [HexCoord(10, 10)]
        valid, reason = validate_march_path(path, {"10,10"})
        assert valid is True
        assert "原地不动" in reason

    def test_start_not_owned(self):
        path = [HexCoord(10, 10), HexCoord(11, 10)]
        valid, reason = validate_march_path(path, {"20,20"})
        assert valid is False
        assert "不在己方领土" in reason

    def test_non_adjacent_step(self):
        """跳步（不相邻）"""
        path = [HexCoord(10, 10), HexCoord(15, 15)]
        valid, reason = validate_march_path(path, {"10,10"})
        assert valid is False
        assert "不相邻" in reason

    def test_blocked_step(self):
        path = [HexCoord(10, 10), HexCoord(11, 10)]
        valid, reason = validate_march_path(
            path, {"10,10"}, blocked={"11,10"}
        )
        assert valid is False
        assert "被阻挡" in reason

    def test_valid_two_step_path(self):
        path = [HexCoord(10, 10), HexCoord(11, 10), HexCoord(12, 10)]
        valid, reason = validate_march_path(
            path, {"10,10", "11,10", "12,10"}
        )
        assert valid is True
        assert "合法" in reason
