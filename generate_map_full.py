# -*- coding: utf-8 -*-
"""生成完整地图数据 (含海域)"""
import sys
import json
from pathlib import Path

# 确保项目根目录在 path 中
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from server.map.sea_generator import generate_full_map, print_sea_report

print_sea_report()

full_map = generate_full_map()

# 服务端路径
output_path = project_root / "server" / "data" / "map" / "map_full.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(full_map, f, ensure_ascii=False)

print(f"\n完整地图已保存至: {output_path}")
print(f"陆地: {full_map['meta']['land_tiles']} 格")
print(f"海洋: {full_map['meta']['sea_tiles']} 格")
print(f"总计: {full_map['meta']['total_tiles']} 格")

# 同时复制到前端public目录
frontend_path = project_root / "frontend" / "public" / "data" / "map" / "map_full.json"
frontend_path.parent.mkdir(parents=True, exist_ok=True)
with open(frontend_path, "w", encoding="utf-8") as f:
    json.dump(full_map, f, ensure_ascii=False)
print(f"前端副本已保存至: {frontend_path}")
