"""
海地块生成器 v1.0 - 将矩形网格空白区域全部填充为可交互的海域

核心概念:
- 地图是 32行×42列(奇数行41列) 的完整矩形六边形矩阵 = 1,328 个格子
- 当前通过 territory_mask 排除海洋区域，仅保留约 499 个陆地格子
- 本模块为所有排除的格子生成 `sea` 类型的地块，使其可交互
- 海域按地理区域分为 8 个：渤海、黄海、东海、南海、日本海、太平洋、印度洋、远洋深处

海域交互功能:
- 海军移动 (需水师)
- 贸易航线 (海港→海港)
- 登陆作战 (水陆两栖)
- 海盗/倭寇活动
- 渔业资源
- 台风/风暴灾害
"""

from __future__ import annotations
import math
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from server.map.hex_grid import (
    GRID_ROWS, GRID_MAX_COLS, GRID_ODD_COLS,
    GEO_LON_MIN, GEO_LON_MAX, GEO_LAT_MIN, GEO_LAT_MAX,
    HexCoord, hex_center_geo, offset_to_pixel,
    iter_all_coords, is_valid_coord, get_row_width,
)
from server.map.territory_mask import is_hex_in_territory, EXCLUDED_HEXES

# ============================================================
# 海域地理区域定义
# ============================================================

SEA_ZONES: Dict[str, Dict[str, any]] = {
    "bohai_sea": {
        "name": "渤海",
        "chinese_name": "渤海",
        "region": "海域",
        "lon_range": (117.0, 123.0),
        "lat_range": (37.0, 41.5),
        "depth": "shallow",   # 浅海
        "movement_cost": 18,
        "navy_mod": 1.1,
        "supply_yield": 3,     # 渔业丰富
        "description": "渤海湾，近畿海域，渔业昌盛",
        "color": "#4a6078",    # 浅蓝灰
    },
    "yellow_sea": {
        "name": "黄海",
        "chinese_name": "黄海",
        "region": "海域",
        "lon_range": (120.0, 127.0),
        "lat_range": (31.0, 39.0),
        "depth": "shallow",
        "movement_cost": 20,
        "navy_mod": 1.1,
        "supply_yield": 2,
        "description": "黄海，连通渤海与东海",
        "color": "#4a6878",
    },
    "east_china_sea": {
        "name": "东海",
        "chinese_name": "东海",
        "region": "海域",
        "lon_range": (118.0, 132.0),
        "lat_range": (24.0, 32.0),
        "depth": "moderate",
        "movement_cost": 22,
        "navy_mod": 1.15,
        "supply_yield": 3,
        "description": "东海，商贸航道，倭寇出没",
        "color": "#3a5a72",    # 中蓝灰
    },
    "south_china_sea": {
        "name": "南海",
        "chinese_name": "南海",
        "region": "海域",
        "lon_range": (105.0, 122.0),
        "lat_range": (0.0, 24.0),
        "depth": "moderate",
        "movement_cost": 24,
        "navy_mod": 1.2,
        "supply_yield": 2,
        "description": "南海，丝绸之路要冲",
        "color": "#3a5870",
    },
    "sea_of_japan": {
        "name": "日本海",
        "chinese_name": "日本海",
        "region": "海域",
        "lon_range": (127.0, 142.0),
        "lat_range": (34.0, 46.0),
        "depth": "deep",
        "movement_cost": 28,
        "navy_mod": 1.3,
        "supply_yield": 2,
        "description": "日本海，倭国与朝鲜间",
        "color": "#325268",
    },
    "pacific_ocean": {
        "name": "太平洋",
        "chinese_name": "东大洋",
        "region": "海域",
        "lon_range": (128.0, 165.0),
        "lat_range": (0.0, 46.0),
        "depth": "deep",
        "movement_cost": 35,
        "navy_mod": 1.4,
        "supply_yield": 1,
        "description": "茫茫东海之外，远洋深处",
        "color": "#284458",
    },
    "indian_ocean": {
        "name": "印度洋",
        "chinese_name": "西洋",
        "region": "海域",
        "lon_range": (55.0, 100.0),
        "lat_range": (0.0, 15.0),
        "depth": "deep",
        "movement_cost": 32,
        "navy_mod": 1.3,
        "supply_yield": 2,
        "description": "西洋贸易航线",
        "color": "#284860",
    },
    "deep_ocean": {
        "name": "远洋深处",
        "chinese_name": "远洋",
        "region": "海域",
        "lon_range": (55.0, 165.0),
        "lat_range": (0.0, 60.0),
        "depth": "abyssal",
        "movement_cost": 50,
        "navy_mod": 1.5,
        "supply_yield": 0,
        "description": "远洋深处，风浪滔天",
        "color": "#1a3040",
    },
}


def classify_sea_zone(col: int, row: int) -> Tuple[str, Dict]:
    """
    根据六边形中心经纬度分类海域区域

    按优先级从具体到笼统匹配：
    渤海 → 黄海 → 东海 → 南海 → 日本海 → 太平洋 → 印度洋 → 远洋
    """
    lon, lat = hex_center_geo(col, row)

    # 按具体性排序检查（具体海域优先于远洋）
    priority_zones = [
        "bohai_sea",
        "yellow_sea",
        "east_china_sea",
        "south_china_sea",
        "sea_of_japan",
        "pacific_ocean",
        "indian_ocean",
    ]

    for zone_id in priority_zones:
        zone = SEA_ZONES[zone_id]
        lon_min, lon_max = zone["lon_range"]
        lat_min, lat_max = zone["lat_range"]
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return zone_id, zone

    # 兜底：远洋
    return "deep_ocean", SEA_ZONES["deep_ocean"]


def is_sea_hex(col: int, row: int) -> bool:
    """
    判断一个格子是否为海域（含内海和外海）
    
    两层判断：
    1. territory_mask 排除的 → 外海 (直接是海)
    2. territory_mask 包含但落入内海区域的 → 内海 (渤海、黄海等)
    """
    if not is_hex_in_territory(col, row):
        return True  # 外海

    # 检查是否在内海区域 (在疆域多边形内，但地理位置是水域)
    lon, lat = hex_center_geo(col, row)
    inland_seas = [
        SEA_ZONES["bohai_sea"],      # 渤海湾内
        SEA_ZONES["yellow_sea"],     # 黄海中部
        SEA_ZONES["east_china_sea"], # 东海
        SEA_ZONES["sea_of_japan"],   # 日本海
    ]
    for sea in inland_seas:
        lon_min, lon_max = sea["lon_range"]
        lat_min, lat_max = sea["lat_range"]
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return True

    return False


def generate_sea_tile(col: int, row: int) -> Optional[dict]:
    """
    为单个网格位置生成海地块数据

    Returns:
        dict 格式的 tile 数据，与 map_final.json 结构兼容
        如果该位置不是海域，返回 None
    """
    # 只处理海域格子（含外海和内海）
    if not is_sea_hex(col, row):
        return None

    zone_id, zone = classify_sea_zone(col, row)

    # 坐标计算
    coord = HexCoord(col, row)
    q, r = coord.to_axial()
    px, py = offset_to_pixel(col, row)

    # 邻居列表
    neighbors = []
    for nc in coord.rect_neighbors():
        neighbors.append(nc.to_key())

    # 生成 tile_name
    tile_name = f"{zone['chinese_name']}({col},{row})"

    tile = {
        "hex_id": f"{col},{row}",
        "tile_id": f"sea_{col},{row}",
        "tile_name": tile_name,
        "col": col,
        "row": row,
        "q": q,
        "r": r,
        "pixel_x": round(px, 2),
        "pixel_y": round(py, 2),
        "neighbors": neighbors,
        "terrain": "sea",
        "movement_cost": float(zone["movement_cost"]),
        "move_cost": float(zone["movement_cost"]),
        "defense_bonus": 0.0,
        "attack_modifier": 0.0,
        "navy_modifier": zone["navy_mod"],
        "is_coastal": _is_coastal(col, row),
        "is_ferry": False,
        "combat_modifiers": {
            "navy": zone["navy_mod"],
            "cavalry": 0.0,
            "infantry": 0.1,
        },
        "supply_yield": float(zone["supply_yield"]),
        "province": "海域",
        "province_id": "sea_region",
        "circuit": zone["chinese_name"],
        "circuit_id": f"sea_{zone_id}",
        "prefecture": zone["chinese_name"],
        "prefecture_id": f"sea_{zone_id}_{col}_{row}",
        "faction_id": None,
        "is_capital": False,
        "is_port": False,
        "is_pass": False,
        "is_strategic": False,
        "water_river": False,
        "water_lake": False,
        "sea_zone": zone_id,
        "sea_depth": zone["depth"],
        "sea_zone_name": zone["chinese_name"],
    }

    return tile


def _is_coastal(col: int, row: int) -> bool:
    """判断海地块是否邻接陆地（沿岸海域）"""
    coord = HexCoord(col, row)
    for nc in coord.rect_neighbors():
        if is_hex_in_territory(nc.col, nc.row):
            return True
    return False


def generate_all_sea_tiles() -> List[dict]:
    """
    生成所有海域地块

    Returns:
        list of sea tile dicts
    """
    sea_tiles = []

    for row in range(GRID_ROWS):
        width = get_row_width(row)
        for col in range(width):
            if is_sea_hex(col, row):
                tile = generate_sea_tile(col, row)
                if tile:
                    sea_tiles.append(tile)

    return sea_tiles


def generate_full_map() -> dict:
    """
    生成完整地图数据：陆地tiles(map_final) + 海域tiles(新生成)

    Returns:
        完整的 map_full 格式 dict，含所有1,328个格子
    """
    # 加载现有陆地tiles
    server_dir = Path(__file__).parent.parent
    map_final_path = server_dir / "data" / "map" / "map_final.json"

    if map_final_path.exists():
        with open(map_final_path, "r", encoding="utf-8") as f:
            land_data = json.load(f)
        land_tiles = land_data.get("tiles", [])
        meta = land_data.get("meta", {})
    else:
        land_tiles = []
        meta = {}

    # 收集已有陆地块的 col,row 位置
    land_positions: set = set()
    for t in land_tiles:
        col = t.get("col")
        row = t.get("row")
        if col is not None and row is not None:
            land_positions.add((int(col), int(row)))

    # 生成海域tiles（排除已有陆地位置）
    all_sea_tiles = generate_all_sea_tiles()
    sea_tiles = []
    inland_sea_count = 0
    for st in all_sea_tiles:
        col = st.get("col")
        row = st.get("row")
        if col is not None and row is not None:
            if (int(col), int(row)) not in land_positions:
                sea_tiles.append(st)
                # 统计内海 vs 外海
                if is_hex_in_territory(int(col), int(row)):
                    inland_sea_count += 1
            # 跳过与陆地重叠的位置
        else:
            sea_tiles.append(st)

    # 合并
    all_tiles = list(land_tiles) + sea_tiles

    # 更新meta
    meta["total_tiles"] = len(all_tiles)
    meta["land_tiles"] = len(land_tiles)
    meta["sea_tiles"] = len(sea_tiles)
    meta["inland_sea_tiles"] = inland_sea_count
    meta["grid_coverage"] = "full"
    meta["sea_enabled"] = True

    return {
        "version": "4.1",
        "level": "prefecture",
        "hex_size_px": 72,
        "meta": meta,
        "sea_zones": {
            zone_id: {
                "name": z["chinese_name"],
                "depth": z["depth"],
                "color": z["color"],
            }
            for zone_id, z in SEA_ZONES.items()
        },
        "tiles": all_tiles,
    }


def get_sea_zone_color(col: int, row: int) -> str:
    """获取海地块的渲染颜色"""
    if is_hex_in_territory(col, row):
        return ""
    _, zone = classify_sea_zone(col, row)
    return zone.get("color", "#1a3040")


def get_sea_zone_name(col: int, row: int) -> str:
    """获取海地块的海域名称"""
    if is_hex_in_territory(col, row):
        return "陆地"
    zone_id, zone = classify_sea_zone(col, row)
    return zone["chinese_name"]


# ============================================================
# 海域统计
# ============================================================

def print_sea_report():
    """打印海域统计报告"""
    from collections import Counter
    zone_counts = Counter()

    for row in range(GRID_ROWS):
        width = get_row_width(row)
        for col in range(width):
            if is_sea_hex(col, row):
                zone_id, _ = classify_sea_zone(col, row)
                zone_counts[zone_id] += 1
                # 同时统计沿岸
                if _is_coastal(col, row):
                    zone_counts[f"{zone_id}__coastal"] += 1

    print("\n  === 海域地块统计 ===")
    total_rect = sum(get_row_width(r) for r in range(GRID_ROWS))
    total_sea = sum(zone_counts[z] for z in SEA_ZONES if z in zone_counts)
    print(f"  矩形总格数: {total_rect}")
    print(f"  海域总格数: {total_sea}")
    print(f"  海域占比: {total_sea / total_rect * 100:.1f}%")
    print()
    for zone_id, zone in SEA_ZONES.items():
        count = zone_counts.get(zone_id, 0)
        coastal = zone_counts.get(f"{zone_id}__coastal", 0)
        if count > 0:
            print(f"  {zone['chinese_name']:8s}: {count:4d} 格 (沿岸{coastal}格) "
                  f"| 水深:{zone['depth']:8s} | 移动:{zone['movement_cost']}")
    print(f"  === 报告结束 ===")


if __name__ == "__main__":
    print_sea_report()

    # 生成完整地图
    full_map = generate_full_map()
    output_path = Path(__file__).parent.parent / "data" / "map" / "map_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, ensure_ascii=False, indent=2)
    print(f"\n  完整地图已保存至: {output_path}")
    print(f"  陆地: {full_map['meta']['land_tiles']} 格")
    print(f"  海洋: {full_map['meta']['sea_tiles']} 格")
    print(f"  总计: {full_map['meta']['total_tiles']} 格")
