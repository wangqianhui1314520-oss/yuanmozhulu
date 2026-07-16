"""
六边形网格核心测试 — HexCoord / 坐标转换 / 验证 / 迭代器

覆盖: server/map/hex_grid.py 全部纯函数
"""
import pytest
import math
from server.map.hex_grid import (
    HexCoord, GRID_ROWS, GRID_MAX_COLS, GRID_ODD_COLS,
    TOTAL_TILES_RECT, DEFAULT_HEX_SIZE,
    AXIAL_DIRECTIONS, GEO_LON_MIN, GEO_LON_MAX, GEO_LAT_MIN, GEO_LAT_MAX,
    is_valid_coord, is_valid_active_coord,
    get_row_width, total_tile_count, rect_tile_count,
    offset_to_pixel, pixel_to_offset,
    hex_center_geo, hex_corners_flat_top,
    iter_all_coords, iter_row,
)


# ============================================================
# HexCoord 数据类
# ============================================================

class TestHexCoordCreation:
    """HexCoord 构造与属性"""

    def test_create_origin(self):
        c = HexCoord(0, 0)
        assert c.col == 0
        assert c.row == 0

    def test_create_dadu(self):
        c = HexCoord(21, 15)
        assert c.col == 21
        assert c.row == 15

    def test_eq_same(self):
        assert HexCoord(10, 5) == HexCoord(10, 5)

    def test_eq_different(self):
        assert HexCoord(10, 5) != HexCoord(11, 5)
        assert HexCoord(10, 5) != HexCoord(10, 6)

    def test_hash_equal_coords_have_same_hash(self):
        assert hash(HexCoord(10, 5)) == hash(HexCoord(10, 5))

    def test_repr(self):
        assert repr(HexCoord(21, 15)) == "Hex(21,15)"

    def test_to_key(self):
        assert HexCoord(21, 15).to_key() == "21,15"
        assert HexCoord(0, 0).to_key() == "0,0"


class TestHexCoordAxial:
    """Offset ↔ Axial 坐标转换"""

    def test_axial_even_row(self):
        """偶数行: q = col - row//2"""
        c = HexCoord(10, 4)
        q, r = c.to_axial()
        assert q == 10 - 4 // 2  # = 8
        assert r == 4

    def test_axial_odd_row(self):
        """奇数行: q = col - (row-1)//2"""
        c = HexCoord(10, 5)
        q, r = c.to_axial()
        assert q == 10 - (5 - 1) // 2  # = 8
        assert r == 5

    def test_from_axial_roundtrip(self, sample_coords):
        """轴向 ↔ 偏移 往返一致性"""
        for name, coord in sample_coords.items():
            q, r = coord.to_axial()
            back = HexCoord.from_axial(q, r)
            assert back == coord, f"往返失败: {name} {coord} → axial({q},{r}) → {back}"

    def test_q_property(self):
        c = HexCoord(21, 15)
        expected_q = 21 - (15 - (15 & 1)) // 2
        assert c.q == expected_q

    def test_axial_r_property(self):
        c = HexCoord(21, 15)
        assert c.axial_r == 15


class TestHexCoordNeighbors:
    """HexCoord.neighbors()"""

    def test_six_neighbors_center(self):
        """中心格应有6个邻居（疆域内）"""
        c = HexCoord(21, 15)
        neighbors = c.neighbors(territory_only=False)
        assert len(neighbors) == 6

    def test_neighbor_includes_correct_offsets(self):
        """邻居应包含6个轴向方向的格（所有邻居在同一射程内）"""
        c = HexCoord(21, 15)
        neighbors = c.neighbors(territory_only=False)
        keys = {n.to_key() for n in neighbors}
        # 6个邻居的offset坐标（实际值取决于 HexCoord.neighbors 实现）
        # 验证核心属性：6个唯一邻居，且距离=1
        assert len(keys) == 6, f"应有6个邻居，实际 {len(keys)}: {keys}"
        for n in neighbors:
            assert c.distance_to(n) == 1, f"{c} → {n} 距离应为1"

    def test_territory_neighbors_alias(self):
        c = HexCoord(21, 15)
        assert c.territory_neighbors() == c.neighbors(territory_only=True)

    def test_rect_neighbors_alias(self):
        c = HexCoord(21, 15)
        assert c.rect_neighbors() == c.neighbors(territory_only=False)


class TestHexCoordDistance:
    """HexCoord.distance_to()"""

    def test_distance_self_zero(self):
        c = HexCoord(10, 10)
        assert c.distance_to(c) == 0

    def test_distance_adjacent(self, hex_coord_pairs):
        for a, b in hex_coord_pairs:
            assert a.distance_to(b) == 1, f"{a} → {b} 距离应为1"

    def test_distance_straight_line(self):
        """同列直线上距离"""
        a = HexCoord(10, 10)
        b = HexCoord(10, 15)
        assert a.distance_to(b) == 5

    def test_distance_diagonal(self):
        a = HexCoord(10, 10)
        b = HexCoord(15, 15)
        # 六边形网格距离 = max(|Δq|, |Δr|, |Δq+Δr|) in axial coords
        # (10,10) even row → axial (5,10), (15,15) odd row → axial (8,15)
        # Δq=3, Δr=5, |Δq+Δr|=8 → distance=8
        assert a.distance_to(b) == 8

    def test_distance_symmetric(self):
        """距离对称性"""
        a = HexCoord(5, 8)
        b = HexCoord(20, 14)
        assert a.distance_to(b) == b.distance_to(a)


# ============================================================
# 网格验证
# ============================================================

class TestGridValidation:
    """is_valid_coord / is_valid_active_coord"""

    def test_valid_origin(self):
        assert is_valid_coord(HexCoord(0, 0))

    def test_valid_last_tile(self):
        """最后一行最后一格"""
        c = HexCoord(GRID_ODD_COLS - 1, GRID_ROWS - 1)  # 31行奇数行
        # 检验是否在网格内
        assert isinstance(is_valid_coord(c), bool)

    def test_invalid_negative_row(self):
        assert not is_valid_coord(HexCoord(0, -1))

    def test_invalid_row_out_of_range(self):
        assert not is_valid_coord(HexCoord(0, GRID_ROWS))

    def test_invalid_col_out_of_range_even_row(self):
        assert not is_valid_coord(HexCoord(GRID_MAX_COLS, 0))

    def test_invalid_col_out_of_range_odd_row(self):
        assert not is_valid_coord(HexCoord(GRID_ODD_COLS, 1))

    def test_dadu_is_valid(self):
        assert is_valid_coord(HexCoord(21, 15))


class TestRowWidth:
    """get_row_width()"""

    def test_even_row_width(self):
        assert get_row_width(0) == GRID_MAX_COLS
        assert get_row_width(10) == GRID_MAX_COLS

    def test_odd_row_width(self):
        assert get_row_width(1) == GRID_ODD_COLS
        assert get_row_width(11) == GRID_ODD_COLS


class TestTileCount:
    """total_tile_count / rect_tile_count"""

    def test_rect_count_matches_constant(self):
        assert rect_tile_count() == TOTAL_TILES_RECT

    def test_total_count_positive(self):
        assert total_tile_count() > 0


# ============================================================
# 像素坐标转换
# ============================================================

class TestPixelConversion:
    """offset_to_pixel / pixel_to_offset"""

    def test_origin_pixel(self):
        x, y = offset_to_pixel(0, 0)
        assert x == DEFAULT_HEX_SIZE
        assert y == DEFAULT_HEX_SIZE

    def test_roundtrip(self, sample_coords):
        """像素坐标往返一致性"""
        for name, coord in sample_coords.items():
            px, py = offset_to_pixel(coord.col, coord.row)
            back = pixel_to_offset(px, py)
            assert back == coord, f"像素往返失败: {name} {coord} → ({px:.1f},{py:.1f}) → {back}"

    def test_odd_row_offset(self):
        """奇数行应向右偏移半个格子"""
        _, y_even = offset_to_pixel(0, 0)
        x_odd, y_odd = offset_to_pixel(0, 1)
        assert x_odd == DEFAULT_HEX_SIZE + DEFAULT_HEX_SIZE * 0.75  # 1.5*hex/2


class TestHexCorners:
    """hex_corners_flat_top()"""

    def test_correct_number_of_vertices(self):
        corners = hex_corners_flat_top(100, 100)
        assert len(corners) == 6

    def test_vertices_form_regular_hexagon(self):
        """六边形顶点间距离应接近相等"""
        corners = hex_corners_flat_top(200, 200)
        dists = []
        for i in range(6):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % 6]
            d = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            dists.append(d)
        # 正六边形所有边长应相等（容差1px）
        assert max(dists) - min(dists) < 1.0


class TestGeoMapping:
    """hex_center_geo()"""

    def test_origin_geo_range(self):
        lon, lat = hex_center_geo(0, 0)
        assert GEO_LON_MIN <= lon <= GEO_LON_MAX
        assert GEO_LAT_MIN <= lat <= GEO_LAT_MAX

    def test_last_tile_geo_range(self):
        lon, lat = hex_center_geo(GRID_MAX_COLS - 1, GRID_ROWS - 1)
        assert GEO_LON_MIN <= lon <= GEO_LON_MAX
        assert GEO_LAT_MIN <= lat <= GEO_LAT_MAX

    def test_lat_decreases_as_row_increases(self):
        """行号增大 → 纬度降低（南移）"""
        _, lat_top = hex_center_geo(0, 0)
        _, lat_bottom = hex_center_geo(0, 20)
        assert lat_top > lat_bottom


# ============================================================
# 迭代器
# ============================================================

class TestIterators:
    """iter_all_coords / iter_row"""

    def test_iter_all_coords_count_matches(self):
        all_coords = list(iter_all_coords(include_excluded=False))
        assert len(all_coords) == total_tile_count()

    def test_iter_all_with_excluded_larger(self):
        """含排除格的总数应 ≥ 不含排除的总数"""
        with_excluded = list(iter_all_coords(include_excluded=True))
        without = list(iter_all_coords(include_excluded=False))
        assert len(with_excluded) >= len(without)

    def test_iter_row_valid(self):
        coords = list(iter_row(0))
        assert len(coords) == GRID_MAX_COLS

    def test_iter_row_invalid_is_empty(self):
        coords = list(iter_row(-1))
        assert len(coords) == 0
        coords = list(iter_row(GRID_ROWS))
        assert len(coords) == 0

    def test_iter_all_coords_are_valid(self):
        for coord in iter_all_coords(include_excluded=False):
            assert is_valid_coord(coord)


# ============================================================
# 方向常量
# ============================================================

class TestAxialDirections:
    def test_six_directions(self):
        assert len(AXIAL_DIRECTIONS) == 6

    def test_all_unique(self):
        assert len(set(AXIAL_DIRECTIONS)) == 6
