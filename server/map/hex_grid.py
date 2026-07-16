"""
六边形网格核心 - 文明6风格 Flat-Top 奇数行交错 (府州级 v4.1)

Stagger Axis = X, Stagger Index = Odd
即：奇数行(row%2==1)向右偏移半个格子宽度。

坐标系（双坐标系设计）:
- Offset 坐标系 (col, row) 作为主存储坐标 — 直观行列位置
- Axial 坐标系 (q, r) 用于距离/邻居/寻路计算 — 内部高效运算

Offset → Axial (Flat-Top, odd-row offset):
  q = col - (row - (row & 1)) / 2
  r = row

Axial → Offset (Flat-Top, odd-row offset):
  col = q + (r - (r & 1)) / 2
  row = r

v4.1 规范 (按沙盘地图系统文档 v3.0):
- 最小单元: 府州级 (1 个六边形 = 1 个府/州)
- 层级: 三级行政层级 (行省→路→府州)
- 版图: 东亚全域 (含朝鲜/日本/琉球台湾/中南半岛北部)
- 网格: 32行 × 42列(偶数行) / 41列(奇数行) = 1,328 个矩形格位
- 疆域遮罩后: 约496 个有效格位 (21 顶点多边形 Ray-Casting 判定)
- 地理映射: 经度55°E~165°E, 纬度0°N~60°N
- 六边形尺寸: 72px (外接圆半径, 府州级适配界面)
- 寻路: A* 算法, 最大500步, 自定义移动代价
"""

from __future__ import annotations
import math
from typing import Iterator, List, Set, Tuple
from dataclasses import dataclass


# ============================================================
# 网格常量 - 东亚全域府州级 (v4.1)
# ============================================================
GRID_ROWS = 32
GRID_MAX_COLS = 42       # 偶数行总列数
GRID_ODD_COLS = 41       # 奇数行总列数
GRID_MIN_COL = 0         # 最左列索引 (55°E 起)
TOTAL_TILES_RECT = 1328  # 矩形网格总格数 (16×42 + 16×41 = 672+656)

# 地理映射参数
GEO_LON_MIN = 55.0      # 最西经度
GEO_LON_MAX = 165.0     # 最东经度
GEO_LAT_MIN = 0.0       # 最南纬度
GEO_LAT_MAX = 60.0      # 最北纬度

# ============================================================
# 疆域遮罩集成 - 延迟加载避免循环依赖
# ============================================================

_territory_loaded = False
_territory_excluded: Set[Tuple[int, int]] = set()

# ----------------
# V4.2 优化：预计算缓存
# ----------------
_active_coords_cache: List[HexCoord] | None = None  # 疆域内所有坐标的预计算列表
_all_coords_cache: List[HexCoord] | None = None      # 矩形网格所有坐标的预计算列表
_row_widths_cache: List[int] | None = None            # 每行列数的预计算列表

def _ensure_territory_loaded():
    """延迟加载疆域遮罩"""
    global _territory_loaded, _territory_excluded
    if _territory_loaded:
        return
    try:
        from server.map.territory_mask import EXCLUDED_HEXES
        _territory_excluded = EXCLUDED_HEXES
    except ImportError:
        _territory_excluded = set()
    _territory_loaded = True


def warm_cache():
    """V4.2: 预热所有坐标缓存（在服务器启动时调用一次）"""
    global _active_coords_cache, _all_coords_cache, _row_widths_cache, TOTAL_TILES
    _ensure_territory_loaded()

    # 行宽缓存
    _row_widths_cache = [
        GRID_MAX_COLS if r % 2 == 0 else GRID_ODD_COLS
        for r in range(GRID_ROWS)
    ]

    # 全部坐标（矩形网格）
    _all_coords_cache = [
        HexCoord(col, row)
        for row in range(GRID_ROWS)
        for col in range(_row_widths_cache[row])
    ]

    # 疆域内坐标
    if _territory_excluded:
        _active_coords_cache = [
            c for c in _all_coords_cache
            if (c.col, c.row) not in _territory_excluded
        ]
    else:
        _active_coords_cache = list(_all_coords_cache)

    TOTAL_TILES = len(_active_coords_cache)


def is_active_hex(col: int, row: int) -> bool:
    """判断格子是否在疆域内（东亚陆地 + 主要岛屿）"""
    _ensure_territory_loaded()
    return (col, row) not in _territory_excluded


def active_tile_count() -> int:
    """返回疆域遮罩后的有效格子总数"""
    _ensure_territory_loaded()
    if _territory_excluded:
        return TOTAL_TILES_RECT - len(_territory_excluded)
    return TOTAL_TILES_RECT


# 动态 TOTAL_TILES (兼容旧代码引用)
TOTAL_TILES = active_tile_count()

# Flat-Top 六边形六个邻居方向 (Axial 坐标)
AXIAL_DIRECTIONS: list[tuple[int, int]] = [
    (+1,  0),  # 右
    (+1, -1),  # 右上
    ( 0, -1),  # 左上
    (-1,  0),  # 左
    (-1, +1),  # 左下
    ( 0, +1),  # 右下
]


# ============================================================
# 数据类
# ============================================================

@dataclass
class HexCoord:
    """Offset 坐标 (col, row) — 主存储坐标
    
    V4.2: axial 坐标在构造时预计算，避免重复转换
    """
    col: int
    row: int

    def __post_init__(self):
        """预计算 axial 坐标（V4.2 优化）"""
        # 使用 object.__setattr__ 避免 dataclass frozen 限制
        object.__setattr__(self, '_axial_q', self.col - (self.row - (self.row & 1)) // 2)
        object.__setattr__(self, '_axial_r', self.row)

    def __hash__(self) -> int:
        return hash((self.col, self.row))

    def __eq__(self, other) -> bool:
        if not isinstance(other, HexCoord):
            return NotImplemented
        return self.col == other.col and self.row == other.row

    def __repr__(self) -> str:
        return f"Hex({self.col},{self.row})"

    def to_axial(self) -> tuple[int, int]:
        """Offset → Axial (Flat-Top, odd-row offset) — V4.2: 直接返回预计算值"""
        return (self._axial_q, self._axial_r)

    @staticmethod
    def from_axial(q: int, r: int) -> "HexCoord":
        """Axial → Offset (Flat-Top, odd-row offset)"""
        col = q + (r - (r & 1)) // 2
        row = r
        return HexCoord(col, row)

    @property
    def q(self) -> int:
        return self._axial_q

    @property
    def axial_r(self) -> int:
        return self._axial_r

    def neighbors(self, territory_only: bool = True) -> list["HexCoord"]:
        """返回邻居的 Offset 坐标"""
        aq, ar = self._axial_q, self._axial_r
        result = []
        for dq, dr in AXIAL_DIRECTIONS:
            nq, nr = aq + dq, ar + dr
            nc = HexCoord.from_axial(nq, nr)
            if territory_only:
                if is_valid_active_coord(nc):
                    result.append(nc)
            else:
                if is_valid_coord(nc):
                    result.append(nc)
        return result

    def territory_neighbors(self) -> list["HexCoord"]:
        return self.neighbors(territory_only=True)

    def rect_neighbors(self) -> list["HexCoord"]:
        return self.neighbors(territory_only=False)

    def distance_to(self, other: "HexCoord") -> int:
        """六边形曼哈顿距离 (V4.2: 使用预计算坐标)"""
        dq = self._axial_q - other._axial_q
        dr = self._axial_r - other._axial_r
        ds = (-self._axial_q - self._axial_r) - (-other._axial_q - other._axial_r)
        return (abs(dq) + abs(dr) + abs(ds)) // 2

    def to_key(self) -> str:
        return f"{self.col},{self.row}"


# ============================================================
# 网格验证
# ============================================================

def is_valid_coord(coord: HexCoord) -> bool:
    """判断 Offset 坐标是否在矩形网格范围内"""
    if coord.row < 0 or coord.row >= GRID_ROWS:
        return False
    if coord.row % 2 == 0:
        return GRID_MIN_COL <= coord.col < GRID_MIN_COL + GRID_MAX_COLS
    else:
        return GRID_MIN_COL <= coord.col < GRID_MIN_COL + GRID_ODD_COLS


def is_valid_active_coord(coord: HexCoord) -> bool:
    """判断坐标是否在网格内且在疆域遮罩内"""
    if not is_valid_coord(coord):
        return False
    return is_active_hex(coord.col, coord.row)


def get_row_width(row: int) -> int:
    """获取指定行的列数 (V4.2: 使用缓存加速)"""
    if _row_widths_cache is not None and 0 <= row < len(_row_widths_cache):
        return _row_widths_cache[row]
    if row % 2 == 0:
        return GRID_MAX_COLS
    else:
        return GRID_ODD_COLS


def total_tile_count() -> int:
    return active_tile_count()


def rect_tile_count() -> int:
    """V4.2: 返回矩形网格总数（无需遍历计算）"""
    if _row_widths_cache:
        return sum(_row_widths_cache)
    return sum(get_row_width(r) for r in range(GRID_ROWS))


# ============================================================
# 迭代器
# ============================================================

def iter_all_coords(include_excluded: bool = False) -> Iterator[HexCoord]:
    """遍历所有有效格子坐标 (V4.2: 使用预计算缓存)"""
    if include_excluded:
        if _all_coords_cache is not None:
            yield from _all_coords_cache
            return
        for row in range(GRID_ROWS):
            width = get_row_width(row)
            for col in range(width):
                yield HexCoord(col, row)
    else:
        if _active_coords_cache is not None:
            yield from _active_coords_cache
            return
        _ensure_territory_loaded()
        for row in range(GRID_ROWS):
            width = get_row_width(row)
            for col in range(width):
                if is_active_hex(col, row):
                    yield HexCoord(col, row)


def iter_excluded_coords() -> Iterator[HexCoord]:
    """遍历疆域外(被遮挡的)格子坐标"""
    _ensure_territory_loaded()
    for row in range(GRID_ROWS):
        width = get_row_width(row)
        for col in range(width):
            if not is_active_hex(col, row):
                yield HexCoord(col, row)


def iter_row(row: int) -> Iterator[HexCoord]:
    """遍历指定行的所有格子"""
    if 0 <= row < GRID_ROWS:
        width = get_row_width(row)
        for col in range(width):
            yield HexCoord(col, row)


# ============================================================
# 像素坐标转换 (Flat-Top)
# ============================================================

# 六边形外接圆半径 = 72px (府州级, 适配界面)
DEFAULT_HEX_SIZE = 72.0


def hex_center_geo(col: int, row: int) -> tuple[float, float]:
    """
    六边形中心 → 经纬度映射

    经度: GEO_LON_MIN + col/cols * span  (~55°E~165°E)
    纬度: GEO_LAT_MAX - row/rows * span  (~60°N~0°N)

    Returns:
        (longitude, latitude)
    """
    lon = GEO_LON_MIN + (col + 0.5) / GRID_MAX_COLS * (GEO_LON_MAX - GEO_LON_MIN)
    lat = GEO_LAT_MAX - (row + 0.5) / GRID_ROWS * (GEO_LAT_MAX - GEO_LAT_MIN)
    return (lon, lat)


def offset_to_pixel(col: int, row: int, hex_size: float = DEFAULT_HEX_SIZE) -> tuple[float, float]:
    """
    Offset 坐标 → 像素坐标 (Flat-Top, odd-row stagger)

    Returns:
        (center_x, center_y) 六边形中心像素坐标
    """
    horiz_spacing = hex_size * 1.5
    vert_spacing = hex_size * math.sqrt(3)

    x = col * horiz_spacing + hex_size
    if row % 2 == 1:
        x += horiz_spacing / 2

    y = row * vert_spacing + hex_size

    return (x, y)


def pixel_to_offset(px: float, py: float, hex_size: float = DEFAULT_HEX_SIZE) -> HexCoord:
    """像素坐标 → Offset 坐标"""
    horiz_spacing = hex_size * 1.5
    vert_spacing = hex_size * math.sqrt(3)

    row = round((py - hex_size) / vert_spacing)
    row = max(0, min(GRID_ROWS - 1, row))

    x_adjusted = px - hex_size
    if row % 2 == 1:
        x_adjusted -= horiz_spacing / 2

    col = round(x_adjusted / horiz_spacing)
    width = get_row_width(row)
    col = max(0, min(width - 1, col))

    return HexCoord(col, row)


def hex_corners_flat_top(cx: float, cy: float, hex_size: float = DEFAULT_HEX_SIZE) -> list[tuple[float, float]]:
    """计算 Flat-Top 六边形的6个顶点像素坐标"""
    corners = []
    for i in range(6):
        angle_deg = 60 * i
        angle_rad = math.radians(angle_deg)
        corners.append((
            cx + hex_size * math.cos(angle_rad),
            cy + hex_size * math.sin(angle_rad),
        ))
    return corners


# ============================================================
# 初始化验证
# ============================================================

_verified = False


def verify_grid() -> bool:
    """启动时验证网格完整性 (V4.2: 同时预热缓存)"""
    global _verified, TOTAL_TILES
    if _verified:
        return True

    rect_count = rect_tile_count()
    assert rect_count == TOTAL_TILES_RECT, f"矩形网格总数错误: 预期{TOTAL_TILES_RECT}, 实际{rect_count}"

    # V4.2: 预热所有缓存
    warm_cache()
    
    count = total_tile_count()
    TOTAL_TILES = count

    all_coords = list(iter_all_coords())
    assert len(all_coords) == count, f"疆域内格子数不匹配: {len(all_coords)} != {count}"

    for coord in all_coords:
        neighbors = coord.neighbors()
        assert 1 <= len(neighbors) <= 6, f"{coord} 邻居数异常: {len(neighbors)}"

    print(f"  网格验证通过: {count} 个疆域内格子 (矩形共{TOTAL_TILES_RECT}格, 排除{len(_territory_excluded)}格)")
    print(f"  地理映射: 经度{GEO_LON_MIN}°E~{GEO_LON_MAX}°E, 纬度{GEO_LAT_MIN}°N~{GEO_LAT_MAX}°N")
    print(f"  V4.2: 坐标缓存已预热 (活跃坐标{len(_active_coords_cache)}个, 全网格{len(_all_coords_cache)}个)")
    _verified = True
    return True
