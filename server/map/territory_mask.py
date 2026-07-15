"""
疆域遮罩生成器 v4.0 - 东亚全域 (含朝鲜/日本/琉球台湾/中南半岛北部)

核心变更：
- 版图从元朝本土扩展至东亚全域
- 不再使用固定校准目标 (1516格)，直接由多边形决定
- 多边形覆盖: 经度55°E~165°E, 纬度0°N~60°N

多边形顶点说明:
  环绕东亚陆地+主要岛屿，但排除：
  - 太平洋开阔水域
  - 印度洋
  - 西伯利亚极北 (>60°N)
  - 中亚沙漠深处
  - 青藏高原无人区 (保留为地形而非排除)

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
# 东亚全域疆域多边形 (顺时针, 28个唯一顶点 + 1个闭合点 = 29个)
# ============================================================
# 顶点按顺时针方向, 覆盖东亚大陆 + 日本列岛 + 中南半岛
EAST_ASIA_BOUNDARY: List[Tuple[float, float]] = [
    # ---- 北部边界 (从西北→东北) ----
    (55.0, 55.0),    # 巴尔喀什湖西 (~55°E, 55°N)
    (70.0, 57.0),    # 阿尔泰地区
    (85.0, 55.0),    # 贝加尔湖西南
    (100.0, 55.0),   # 蒙古北部
    (110.0, 55.0),   # 贝加尔湖东南
    (120.0, 55.0),   # 黑龙江上游
    (130.0, 52.0),   # 黑龙江中游
    (140.0, 50.0),   # 库页岛附近

    # ---- 东部边界 (沿日本东海岸南下) ----
    (146.0, 46.0),   # 北海道东端
    (148.0, 42.0),   # 本州东北
    (148.0, 38.0),   # 本州东海岸
    (145.0, 34.0),   # 本州东南
    (142.0, 30.0),   # 小笠原群岛
    (138.0, 26.0),   # 琉球南端

    # ---- 南部边界 (台湾→中南半岛) ----
    (128.0, 22.0),   # 台湾南端
    (122.0, 20.0),   # 巴士海峡
    (115.0, 16.0),   # 南海
    (110.0, 10.0),   # 越南南端
    (106.0, 8.0),    # 湄公河三角洲
    (100.0, 12.0),   # 泰国湾北
    (96.0, 15.0),    # 缅甸南部

    # ---- 西部边界 (沿缅甸/印度/西藏西侧北上) ----
    (92.0, 20.0),    # 缅甸-印度边界
    (88.0, 26.0),    # 尼泊尔
    (80.0, 30.0),    # 印度北境
    (75.0, 35.0),    # 帕米尔高原
    (65.0, 40.0),    # 天山以西
    (58.0, 45.0),    # 哈萨克草原
    (55.0, 50.0),    # 里海东岸
    (55.0, 55.0),    # 闭合
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
# 朝鲜半岛覆盖
# ============================================================
_KOREA_RECT: Tuple[float, float, float, float] = (
    124.0, 33.0, 132.0, 43.5,
)


def _is_in_korea(lon: float, lat: float) -> bool:
    return _KOREA_RECT[0] <= lon <= _KOREA_RECT[2] and _KOREA_RECT[1] <= lat <= _KOREA_RECT[3]


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
    print(f"\n  === 东亚全域疆域统计 (v4.0 府州级) ===")
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
