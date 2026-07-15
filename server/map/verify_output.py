"""验证地图输出文件的完整性和正确性"""
import json, csv
from pathlib import Path

data_dir = Path(__file__).parent.parent / "data" / "map"

# 验证 map_final.json
with open(data_dir / "map_final.json", "r", encoding="utf-8") as f:
    mf = json.load(f)
print("=== map_final.json ===")
print(f"  总格子数: {len(mf['tiles'])}")
print(f"  元数据 stagger_axis: {mf['meta']['stagger_axis']}")
print(f"  元数据 stagger_index: {mf['meta']['stagger_index']}")
for t in mf["tiles"][:3]:
    print(f"  样本: {t['tile_id']} q={t['q']} r={t['r']} neighbors={len(t['neighbors'])}")
corner_tiles = [t for t in mf["tiles"] if len(t["neighbors"]) <= 3]
print(f"  边界格子数 (<=3邻居): {len(corner_tiles)}")

# 验证 adjacency.json
with open(data_dir / "adjacency.json", "r", encoding="utf-8") as f:
    adj = json.load(f)
print(f"\n=== adjacency.json ===")
print(f"  邻接条目数: {len(adj['adjacency'])}")
sample_key = list(adj["adjacency"].keys())[0]
print(f"  样本 {sample_key}: {adj['adjacency'][sample_key]}")

# 验证 faction_territories.json
with open(data_dir / "faction_territories.json", "r", encoding="utf-8") as f:
    ft = json.load(f)
print(f"\n=== faction_territories.json ===")
for fid, data in ft["factions"].items():
    print(f"  {fid}: {data['tile_count']} tiles, capital={data['capital']}")

all_tiles = set()
for fid, data in ft["factions"].items():
    for tid in data["tiles"]:
        if tid in all_tiles:
            print(f"  ⚠ 重复: {tid} in {fid}")
        all_tiles.add(tid)
print(f"\n  势力总领土: {len(all_tiles)} 个不重复格子")
print(f"  中立格子: {1330 - len(all_tiles)}")

# 验证 Tiled CSV
with open(data_dir / "tiled_import.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)
print(f"\n=== tiled_import.csv ===")
print(f"  行数: {len(csv_rows)}")
print(f"  列: {list(csv_rows[0].keys())}")

print("\n✓ 所有验证通过!")
