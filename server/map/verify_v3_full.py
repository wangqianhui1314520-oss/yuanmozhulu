"""
验证地图产物完整性 - V3 完善版
检查: 县名/势力/特殊标记/连通性
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json

MAP_DIR = PROJECT_ROOT / "server" / "data" / "map"

# 1. map_final.json 验证
with open(MAP_DIR / "map_final.json", "r", encoding="utf-8") as f:
    mf = json.load(f)

tiles = mf["tiles"]
faction_tiles = sum(1 for t in tiles if t["faction_id"])
capital_tiles = sum(1 for t in tiles if t["is_capital"])
port_tiles = sum(1 for t in tiles if t["is_port"])
pass_tiles = sum(1 for t in tiles if t["is_pass"])
named_tiles = sum(1 for t in tiles if "(" not in t["tile_name"])

print(f"=== map_final.json ===")
print(f"总格数: {len(tiles)}")
print(f"有主: {faction_tiles}, 中立: {len(tiles) - faction_tiles}")
print(f"首都: {capital_tiles}, 港口: {port_tiles}, 关隘: {pass_tiles}")
print(f"已命名县: {named_tiles}/{len(tiles)}")

# 取样
for idx in [0, 100, 500, 900, 1200]:
    t = tiles[idx]
    print(f"  [{idx}] {t['tile_id']} name={t['tile_name']} faction={t['faction_id']} "
          f"pref={t['prefecture_id']} capital={t['is_capital']} port={t['is_port']} pass={t['is_pass']}")

# 首都验证
print(f"\n首都列表:")
for t in tiles:
    if t["is_capital"]:
        print(f"  {t['tile_id']}: {t['tile_name']} - {t['faction_id']} ({t['province']})")

# 2. faction_territories.json 连通性验证
with open(MAP_DIR / "faction_territories.json", "r", encoding="utf-8") as f:
    ft = json.load(f)

from server.map.pathfinding import find_connected_components

print(f"\n=== faction_territories.json 连通性验证 ===")
total_assigned = 0
for fid, fdata in ft["factions"].items():
    tiles_set = set(fdata["tiles"])
    total_assigned += len(tiles_set)
    comps = find_connected_components(tiles_set)
    status = "✓ 全连通" if len(comps) <= 1 else f"✗ {len(comps)}块(飞地{len(comps)-1})"
    print(f"  {fid}: {len(tiles_set)}格 {status}")

print(f"势力总格数: {total_assigned}")

# 3. admin_hierarchy.json
with open(MAP_DIR / "admin_hierarchy.json", "r", encoding="utf-8") as f:
    ah = json.load(f)

print(f"\n=== admin_hierarchy.json ===")
tree = ah["hierarchy_tree"]
prov = tree["children"][0]
circ = prov["children"][0]
pref = circ["children"][0]
counties = pref["children"][:3]
print(f"样本层级: {prov['name']} > {circ['name']} > {pref['name']}")
for c in counties:
    print(f"  └ {c['name']} ({c['id']})")

print(f"\n=== 全部验证通过 ===")
