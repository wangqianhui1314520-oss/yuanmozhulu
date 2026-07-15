"""
地图生成主入口 v4.1 - 府州级东亚全域 (按沙盘地图系统文档 v3.0)

9步流水线:
  [1] 验证网格完整性
  [2] 生成六向邻接表 (府州级)
  [3] 生成三级行政层级 (行省→路→府州)
  [4] 生成全图地形配置 (12种地形 + 9条河流 + 10个湖泊 + 大运河)
  [5] 生成特殊标记 (首都/港口/关隘/渡口/战略据点)
  [6] 生成势力初始领地 (9大势力 BFS 竞争分配)
  [7] 生成两级行政边界线 + 势力边界
  [8] 生成标准化全量地图 (map_final.json + Tiled CSV)
  [9] 导出图层系统配置 (6层渲染管线)

海域系统:
  - 海域地块由 sea_generator.py 独立生成
  - 步骤[8]完成后自动合并陆地+海域生成 map_full.json
  - 8个海域分区：渤海/黄海/东海/南海/日本海/太平洋/印度洋/远洋
  - 海域系统支持海军移动、贸易航线、登陆作战、海盗活动、渔业资源
"""

import sys
import os
import time
import json

# 确保项目根在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.map import hex_grid
from server.map.adjacency import build_adjacency_table, export_adjacency_json
from server.map.admin_hierarchy import (
    assign_tiles_to_hierarchy, build_hierarchy_tree,
    generate_tile_province_map, aggregate_stats,
    export_admin_hierarchy_json,
)
from server.map.territory_mask import print_territory_report, INCLUDED_HEXES
from server.map.special_markers import generate_special_markers, export_special_markers_json
from server.map.faction_territory import (
    generate_initial_territories, generate_tile_faction_map,
    export_faction_territory_json,
)
from server.map.boundary_generator import generate_boundaries, export_boundary_json
from server.map.terrain_generator import generate_terrain_map
from server.map.tile_generator import generate_all_tiles, export_map_final_json, export_tiled_csv
from server.map.layer_config import export_layer_config_json


def main():
    print("=" * 60)
    print("  元末逐鹿 v4.1 地图生成器 - 府州级东亚全域")
    print("=" * 60)

    start_time = time.time()

    # [1] 验证网格
    print("\n[1/9] 验证网格完整性...")
    hex_grid.verify_grid()
    print_territory_report()

    # [2] 生成邻接表 (仅疆域内 tile)
    print("\n[2/9] 生成六向邻接表...")
    adjacency = build_adjacency_table(tile_set=INCLUDED_HEXES)
    export_adjacency_json(adjacency)

    # [3] 生成行政层级
    print("\n[3/9] 生成三级行政层级...")
    admin_assignments = assign_tiles_to_hierarchy()
    hierarchy_tree = build_hierarchy_tree(admin_assignments)
    stats = aggregate_stats(admin_assignments)
    export_admin_hierarchy_json()

    tile_province_map = generate_tile_province_map(admin_assignments)

    # [4] 生成地形 (12种地形，基于90个地理区域的精确分配)
    print("\n[4/9] 生成地形配置...")
    raw_terrain = generate_terrain_map()
    # 键名映射: terrain_generator 使用 hex_0_1 格式 → tile_generator 使用 0,1 格式
    terrain_data = {}
    for key, val in raw_terrain.items():
        if key.startswith("hex_"):
            parts = key[4:].split("_")
            if len(parts) == 2:
                new_key = f"{parts[0]},{parts[1]}"
                terrain_data[new_key] = val

    # [5] 生成特殊标记
    print("\n[5/9] 生成特殊标记...")
    markers = generate_special_markers(adjacency)
    export_special_markers_json(markers)

    # [6] 生成势力领地 (9大势力 BFS 竞争分配)
    print("\n[6/9] 生成势力初始领地...")
    territories = generate_initial_territories(tile_province_map, adjacency)
    export_faction_territory_json(territories)
    tile_faction_map = generate_tile_faction_map(territories)

    # [7] 生成边界
    print("\n[7/9] 生成行政边界线...")
    tile_circuit_map = {
        tid: info["circuit_id"]
        for tid, info in admin_assignments.items()
    }
    boundaries = generate_boundaries(
        tile_province_map, tile_circuit_map, tile_faction_map,
    )
    export_boundary_json(boundaries)

    # [8] 生成标准化全量地图 (仅疆域内 tile)
    print("\n[8/9] 生成标准化地块数据...")
    tiles = generate_all_tiles(
        admin_assignments=admin_assignments,
        terrain_data=terrain_data,
        faction_map=tile_faction_map,
        markers=markers,
        adjacency=adjacency,
        tile_set=INCLUDED_HEXES,
    )
    export_map_final_json(tiles)
    export_tiled_csv(tiles)

    # [9] 导出图层配置 (6层渲染管线)
    print("\n[9/9] 导出图层系统配置...")
    export_layer_config_json()

    # ==== 海域合并：生成完整地图 (陆地 + 海域) ====
    print("\n[+] 生成完整地图 (陆地 + 海域)...")
    full_map = build_full_map(tiles)
    full_output = "server/data/map/map_full.json"
    with open(full_output, "w", encoding="utf-8") as f:
        json.dump(full_map, f, ensure_ascii=False, indent=2)
    print(f"  [全图] 导出完成: {full_output}")
    print(f"    - 陆地: {full_map['meta']['land_tiles']} 格")
    print(f"    - 海洋: {full_map['meta']['sea_tiles']} 格")
    print(f"    - 总计: {full_map['meta']['total_tiles']} 格")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"  全部完成! 耗时 {elapsed:.1f}s")
    print(f"  生成 {len(tiles)} 个府州级地块")
    print(f"  涵盖 {len(tile_province_map)} 个有归属 tile")
    print(f"  9 大势力已分配")
    print(f"  6 层渲染管线已配置")
    print(f"  海域系统已集成 (8个海域分区)")
    print("=" * 60)



def build_full_map(land_tiles=None):
    """生成完整地图 (陆地 + 海域)
    
    从已有的陆地块和海域生成器合并，生成 map_full.json
    """
    from server.map.sea_generator import generate_all_sea_tiles, SEA_ZONES, is_hex_in_territory
    
    if land_tiles is None:
        land_tiles = []
    
    # 收集陆地块的坐标
    land_positions = set()
    for t in land_tiles:
        col = getattr(t, 'col', None) if hasattr(t, 'col') else t.get('col')
        row = getattr(t, 'row', None) if hasattr(t, 'row') else t.get('row')
        if col is not None and row is not None:
            land_positions.add((int(col), int(row)))
    
    # 序列化陆地块
    land_dicts = []
    for t in land_tiles:
        if hasattr(t, 'to_dict'):
            land_dicts.append(t.to_dict())
        else:
            land_dicts.append(t)
    
    # 生成海域tiles（排除已有陆地位置）
    all_sea = generate_all_sea_tiles()
    sea_dicts = []
    inland_sea_count = 0
    for st in all_sea:
        col = st.get('col')
        row = st.get('row')
        if col is not None and row is not None:
            if (int(col), int(row)) not in land_positions:
                sea_dicts.append(st)
                if is_hex_in_territory(int(col), int(row)):
                    inland_sea_count += 1
        else:
            sea_dicts.append(st)
    
    # 合并
    all_tiles = land_dicts + sea_dicts
    
    return {
        "version": "4.1",
        "level": "prefecture",
        "hex_size_px": 72,
        "meta": {
            "total_tiles": len(all_tiles),
            "land_tiles": len(land_dicts),
            "sea_tiles": len(sea_dicts),
            "inland_sea_tiles": inland_sea_count,
            "grid_coverage": "full",
            "sea_enabled": True,
        },
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


def generate_full_map():
    """生成完整地图 (陆地 + 海域) - 独立入口
    
    需要先运行 main() 生成 map_final.json，
    然后调用此函数从已有文件合并。
    """
    from server.map.sea_generator import generate_full_map as sea_generate_full_map
    return sea_generate_full_map()


if __name__ == "__main__":
    main()
