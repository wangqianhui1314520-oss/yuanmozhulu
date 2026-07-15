"""
标准化地块生成器 v4.1 - 府州级 (每格 = 一府/州)

v4.1 变更:
- 移除 county 字段 (四级→三级)
- 行政字段: province / circuit / prefecture (无 county)
- hex_size = 72 (府州级)
- 支持东亚全域 496 个府州级 tile
"""

from __future__ import annotations
import json
import math
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from server.map.hex_grid import (
    GRID_ROWS, GRID_MAX_COLS, GRID_ODD_COLS,
    DEFAULT_HEX_SIZE, HexCoord,
    iter_all_coords, offset_to_pixel,
    TOTAL_TILES, is_active_hex,
)


@dataclass
class StandardTile:
    """标准化地块数据 (v4.0 府州级)"""
    # 标识
    hex_id: str           # "col,row"
    tile_id: str          # hex_id
    tile_name: str        # 府/州名称

    # 坐标 (Offset)
    col: int
    row: int

    # 坐标 (Axial)
    q: int
    r: int

    # 像素坐标
    pixel_x: float
    pixel_y: float

    # 邻接
    neighbors: List[str] = field(default_factory=list)

    # 地形
    terrain: str = "flatland"
    movement_cost: float = 1.0
    move_cost: float = 1.0
    defense_bonus: float = 0.0
    attack_modifier: float = 0.0
    is_coastal: bool = False
    is_ferry: bool = False
    combat_modifiers: Dict[str, Any] = field(default_factory=dict)
    supply_yield: float = 1.0

    # 三级行政归属
    province: str = ""
    province_id: str = ""
    circuit: str = ""
    circuit_id: str = ""
    prefecture: str = ""     # 府州名称 (v4.0: 替代 county)
    prefecture_id: str = ""

    # 势力
    faction_id: Optional[str] = None
    faction_color: Optional[str] = None

    # 特殊属性
    is_capital: bool = False
    is_port: bool = False
    is_pass: bool = False
    is_strategic: bool = False
    strategic_name: Optional[str] = None
    strategic_note: Optional[str] = None

    # 水域
    water_river: bool = False
    water_lake: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        # 移除 None 值以减小文件
        return {k: v for k, v in d.items() if v is not None}


def generate_all_tiles(
    admin_assignments: Optional[Dict[str, dict]] = None,
    terrain_data: Optional[Dict[str, dict]] = None,
    faction_map: Optional[Dict[str, str]] = None,
    markers: Optional[Dict[str, dict]] = None,
    adjacency: Optional[Dict[str, List[str]]] = None,
    tile_set: Optional[set] = None,
) -> List[StandardTile]:
    """
    遍历指定 tile 集合, 组装完整 StandardTile 列表

    Args:
        admin_assignments: tile_id → {province, circuit, prefecture, ...}
        terrain_data: tile_id → {terrain, move_cost, ...}
        faction_map: tile_id → faction_id
        markers: tile_id → {is_capital, is_port, ...}
        adjacency: tile_id → [neighbor_tile_ids]
        tile_set: 要生成的 tile 集合 {(col, row), ...}, 默认 iter_all_coords()
    """
    tiles: List[StandardTile] = []

    if tile_set is not None:
        coord_iter = (HexCoord(col, row) for col, row in tile_set)
    else:
        coord_iter = iter_all_coords()

    for coord in coord_iter:
        col, row = coord.col, coord.row
        tile_id = f"{col},{row}"

        # 坐标转换
        axial = coord.to_axial()
        px, py = offset_to_pixel(col, row, DEFAULT_HEX_SIZE)

        # 行政归属
        admin = admin_assignments.get(tile_id, {}) if admin_assignments else {}

        # 地形
        terr = terrain_data.get(tile_id, {}) if terrain_data else {}
        terrain = terr.get("terrain", _default_terrain(col, row))
        move_cost = terr.get("movement_cost", 1.0)
        defense = terr.get("defense_bonus", _default_defense(terrain))
        supply = terr.get("supply_yield", 1.0)
        is_coastal = terr.get("is_coastal", False)
        water_river = terr.get("water_river", False)
        water_lake = terr.get("water_lake", False)
        is_ferry = terr.get("is_ferry", False)

        # 势力
        faction_id = faction_map.get(tile_id) if faction_map else None

        # 标记
        marker = markers.get(tile_id, {}) if markers else {}

        # 邻接
        neighbors = adjacency.get(tile_id, []) if adjacency else []

        # 名称
        tile_name = admin.get("prefecture", f"府州{col},{row}")

        tile = StandardTile(
            hex_id=tile_id,
            tile_id=tile_id,
            tile_name=tile_name,
            col=col, row=row,
            q=axial[0], r=axial[1],
            pixel_x=px, pixel_y=py,
            neighbors=neighbors,
            terrain=terrain,
            movement_cost=move_cost,
            move_cost=move_cost,
            defense_bonus=defense,
            attack_modifier=terr.get("attack_modifier", 0.0),
            is_coastal=is_coastal,
            is_ferry=is_ferry,
            combat_modifiers=terr.get("combat_modifiers", {}),
            supply_yield=supply,
            province=admin.get("province", ""),
            province_id=admin.get("province_id", ""),
            circuit=admin.get("circuit", ""),
            circuit_id=admin.get("circuit_id", ""),
            prefecture=admin.get("prefecture", ""),
            prefecture_id=admin.get("prefecture_id", ""),
            faction_id=faction_id,
            is_capital=marker.get("is_capital", False),
            is_port=marker.get("is_port", False),
            is_pass=marker.get("is_pass", False),
            is_strategic=marker.get("is_strategic", False),
            strategic_name=marker.get("strategic_name"),
            strategic_note=marker.get("strategic_note"),
            water_river=water_river,
            water_lake=water_lake,
        )
        tiles.append(tile)

    return tiles


def _default_terrain(col: int, row: int) -> str:
    """根据坐标推断默认地形 (简单规则)"""
    # 粗略纬度带
    if row <= 4:
        return "steppe"       # 蒙古草原
    elif row <= 8:
        if col < 12:
            return "desert"    # 西域沙漠
        return "steppe"        # 草原/满洲
    elif row <= 12:
        if col < 8:
            return "desert"
        return "flatland"      # 华北平原
    elif row <= 16:
        if col < 10:
            return "mountain"   # 青藏高原
        if col < 14:
            return "hill"
        return "flatland"       # 华中
    elif row <= 20:
        if col < 8:
            return "mountain"   # 喜马拉雅
        if col < 14:
            return "hill"
        return "flatland"       # 华南
    elif row <= 24:
        return "forest"         # 东南亚雨林
    else:
        return "coastal"        # 南部沿海


def _default_defense(terrain: str) -> float:
    """地形默认防御加成"""
    bonuses = {
        "mountain": 0.4,
        "hill": 0.2,
        "forest": 0.15,
        "wetland": 0.1,
        "flatland": 0.0,
        "desert": 0.05,
        "steppe": 0.0,
        "coastal": 0.05,
        "taiga": 0.05,
        "oasis": 0.1,
    }
    return bonuses.get(terrain, 0.0)


# ============================================================
# 导出函数
# ============================================================

def export_map_final_json(
    tiles: List[StandardTile],
    output_path: str = "server/data/map/map_final.json",
):
    """导出标准化全量地图 JSON (map_final.json)"""
    output = {
        "version": "4.1",
        "level": "prefecture",  # 府州级
        "hex_size_px": int(DEFAULT_HEX_SIZE),
        "meta": {
            "grid_rows": GRID_ROWS,
            "grid_max_cols": GRID_MAX_COLS,
            "grid_odd_cols": GRID_ODD_COLS,
            "geo_range": {
                "lon_min": 55, "lon_max": 165,
                "lat_min": 0, "lat_max": 60,
            },
            "total_tiles": len(tiles),
        },
        "tiles": [t.to_dict() for t in tiles],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [地块] 导出完成: {output_path} ({len(tiles)} 个府州级 tile)")


def export_tiled_csv(
    tiles: List[StandardTile],
    output_path: str = "server/data/map/tiled_import.csv",
):
    """导出 Tiled 编辑器批导入 CSV"""
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write("col,row,tile_name,terrain,faction_id,province,circuit,prefecture\n")
        for tile in sorted(tiles, key=lambda t: (t.row, t.col)):
            f.write(f"{tile.col},{tile.row},{tile.tile_name},{tile.terrain},"
                    f"{tile.faction_id or ''},{tile.province},{tile.circuit},{tile.prefecture}\n")

    print(f"  [CSV] 导出完成: {output_path}")
