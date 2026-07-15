"""
疆域遮罩生成器 v4.1 - 东亚全域 (含朝鲜/日本/琉球台湾/中南半岛北部)


核心设计：
- 21 个顶点的顺时针多边形勾勒东亚大陆轮廓（Ray-Casting算法判定）
- 额外用矩形覆盖补充：日本列岛、朝鲜半岛、台湾、琉球群岛
- 排除：青藏高原无人区、塔克拉玛干沙漠腹地、戈壁核心区
- 海洋格子标记为 sea，不在 territory 内
- 多边形覆盖: 经度55°E~165°E, 纬度0°N~60°N

保留区域: 元朝本土 + 朝鲜 + 日本列岛 + 琉球 + 台湾 + 中南半岛北部(越南/老挝/缅甸北部)
"""

from __future__ import annotations
import math
from typing import List, Set, Tuple

from server.map.hex_grid import (
    GRID_ROWS, GRID_MAX_COLS,
    GEO_LON_MIN, GEO_LON_MAX, GEO_LAT_MIN, GEO_LAT_MAX,
    hex_center_geo,
)

# ============================================================
# 东亚大陆疆域多边形 (21 个顶点的顺时针多边形)
# ============================================================
# 21 个顶点顺时针勾勒东亚大陆轮廓，用于 Ray-Casting 算法判定
# 日本列岛、朝鲜半岛、台湾、琉球群岛通过额外矩形覆盖补充
# 排除区：青藏高原无人区、塔克拉玛干沙漠腹地、戈壁核心区

EAST_ASIA_BOUNDARY: List[Tuple[float, float]] = [
    # ---- 北部边界 (巴尔喀什湖→库页岛, 7点) ----
    (55.0, 55.0),    # 巴尔喀什湖西 (~55°E, 55°N)
    (72.0, 57.0),    # 阿尔泰北
    (90.0, 55.0),    # 贝加尔湖西
    (108.0, 55.0),   # 蒙古高原北
    (125.0, 53.0),   # 黑龙江上游
    (140.0, 48.0),   # 库页岛附近
    (148.0, 44.0),   # 北海道北端

    # ---- 东部边界 (日本海侧南下, 5点) ----
    (140.0, 35.0),   # 日本海东侧
    (132.0, 30.0),   # 朝鲜海峡
    (128.0, 24.0),   # 琉球群岛北
    (122.0, 20.0),   # 台湾南 / 巴士海峡
    (115.0, 14.0),   # 南海

    # ---- 南部边界 (中南半岛, 4点) ----
    (108.0, 8.0),    # 越南南端 / 湄公河三角洲
    (100.0, 12.0),   # 泰国湾北
    (96.0, 16.0),    # 缅甸南部
    (90.0, 22.0),    # 缅甸-印度边界

    # ---- 西部边界 (印度→帕米尔→里海, 5点) ----
    (82.0, 28.0),    # 尼泊尔-印度边界
    (75.0, 35.0),    # 帕米尔高原
    (65.0, 42.0),    # 天山以西
    (57.0, 50.0),    # 里海东岸

    # ---- 闭合 ----
    (55.0, 55.0),    # 闭合 (共21个顶点)
]


def _point_in_polygon(lon: float, lat: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray-casting 算法：判断点是否在多边形内"""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ============================================================
# 补充排除区域
# ============================================================
# 在大陆多边形之外还需排除的海域格子, 或大陆内部特殊排除区域

# 大陆内部排除 (青藏高原腹地无人区、塔克拉玛干沙漠、戈壁无人区)
# 使用简单的经纬度矩形排除
_INLAND_EXCLUDE_ZONES: List[Tuple[float, float, float, float]] = [
    # (lon_min, lat_min, lon_max, lat_max)
    (78.0, 31.0, 92.0, 37.0),   # 青藏高原核心无人区 (羌塘)
    (78.0, 37.0, 88.0, 42.0),   # 塔克拉玛干沙漠腹地
    (95.0, 42.0, 105.0, 47.0),  # 戈壁沙漠核心区
]


def _is_in_inland_exclude(lon: float, lat: float) -> bool:
    """判断经纬度是否落入大陆内部排除区"""
    for lon_min, lat_min, lon_max, lat_max in _INLAND_EXCLUDE_ZONES:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return True
    return False


# ============================================================
# 日本列岛主要岛屿覆盖
# ============================================================
# 用多个矩形覆盖日本四大岛 + 琉球 + 台湾
_JAPAN_ISLANDS_RECTS: List[Tuple[float, float, float, float]] = [
    (129.0, 30.0, 146.0, 46.0),  # 九州+四国+本州+北海道 大矩形
]

_TAIWAN_RYUKYU_RECTS: List[Tuple[float, float, float, float]] = [
    (120.0, 21.5, 122.5, 25.5),  # 台湾
    (122.5, 24.0, 131.5, 31.0),  # 琉球群岛
]


def _is_in_japan_islands(lon: float, lat: float) -> bool:
    """判断是否在日本列岛范围内 (粗略矩形覆盖)"""
    for lon_min, lat_min, lon_max, lat_max in _JAPAN_ISLANDS_RECTS:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            # 进一步排除太平洋深水区
            # 简单判断：日本以西(日本海侧)、以东(太平洋侧)只保留海岸附近
            if lon > 143.0 and lat < 34.0:
                return False  # 排除本州东南远洋
            return True
    return False


def _is_in_taiwan_ryukyu(lon: float, lat: float) -> bool:
    """判断是否在台湾/琉球范围内"""
    for lon_min, lat_min, lon_max, lat_max in _TAIWAN_RYUKYU_RECTS:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return True
    return False


# ============================================================
# 核心判断函数
# ============================================================

def is_hex_in_territory(col: int, row: int) -> bool:
    """
    判断六边形格子是否在东亚疆域内

    分三层判断:
    1. 大陆多边形 (EAST_ASIA_BOUNDARY) - 覆盖东亚大陆
    2. 日本列岛补充 - 多边形外的日本主要岛屿
    3. 台湾/琉球补充 - 多边形外的岛屿

    排除:
    - 大陆内部无人区 (沙漠/高原核心)
    """
    lon, lat = hex_center_geo(col, row)

    # 1. 大陆多边形
    in_mainland = _point_in_polygon(lon, lat, EAST_ASIA_BOUNDARY)

    # 2. 补充岛屿
    in_japan = _is_in_japan_islands(lon, lat)
    in_tw_rk = _is_in_taiwan_ryukyu(lon, lat)

    # 3. 合并区域
    in_territory = in_mainland or in_japan or in_tw_rk

    # 4. 排除大陆无人区
    if in_mainland and _is_in_inland_exclude(lon, lat):
        in_territory = False

    return in_territory


# ============================================================
# 构建排除/包含集合
# ============================================================

def _build_territory_set() -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
    """遍历全网格, 生成排除/包含集合"""
    excluded: Set[Tuple[int, int]] = set()
    included: Set[Tuple[int, int]] = set()

    for row in range(GRID_ROWS):
        max_cols = GRID_MAX_COLS if row % 2 == 0 else GRID_MAX_COLS - 1  # odd rows = 41
        for col in range(max_cols):
            if is_hex_in_territory(col, row):
                included.add((col, row))
            else:
                excluded.add((col, row))

    return excluded, included


EXCLUDED_HEXES, INCLUDED_HEXES = _build_territory_set()
TERRITORY_TILE_COUNT = len(INCLUDED_HEXES)


# ============================================================
# 统计与报告
# ============================================================

def print_territory_report():
    """打印疆域统计报告"""
    print(f"\n  === 东亚全域疆域统计 (v4.1 府州级) ===")
    total_rect = GRID_MAX_COLS * ((GRID_ROWS + 1) // 2) + (GRID_MAX_COLS - 1) * (GRID_ROWS // 2)
    print(f"  网格: {GRID_ROWS}行 × {GRID_MAX_COLS}列 (奇数行{GRID_MAX_COLS-1}列)")
    print(f"  矩形总格数: {total_rect}")
    print(f"  疆域内格数: {TERRITORY_TILE_COUNT}")
    print(f"  排除格数: {len(EXCLUDED_HEXES)}")
    print(f"  覆盖率: {TERRITORY_TILE_COUNT / total_rect * 100:.1f}%")

    # 按象限统计排除分布
    mid_col = GRID_MAX_COLS // 2
    mid_row = GRID_ROWS // 2
    quadrants = {
        "西北": [],
        "东北": [],
        "西南": [],
        "东南": [],
    }
    for col, row in EXCLUDED_HEXES:
        if row < mid_row:
            if col < mid_col:
                quadrants["西北"].append((col, row))
            else:
                quadrants["东北"].append((col, row))
        else:
            if col < mid_col:
                quadrants["西南"].append((col, row))
            else:
                quadrants["东南"].append((col, row))

    for name, cells in quadrants.items():
        pct = len(cells) / len(EXCLUDED_HEXES) * 100 if EXCLUDED_HEXES else 0
        print(f"  {name}: {len(cells)} 排除 ({pct:.1f}%)")

    print(f"  === 报告结束 ===")


if __name__ == "__main__":
    print_territory_report()
