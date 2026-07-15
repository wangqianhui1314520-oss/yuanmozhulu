"""
元朝全盛疆域地形生成器 - 基于中国及中亚历史地理的六边形地块地形分配

为全部六边形格子分配真实地形类型，覆盖:
- 中原农耕区 (flatland/hill)
- 漠北草原区 (flatland/steppe)  
- 西域干旱区 (desert/oasis)
- 吐蕃高原区 (mountain/tundra)
- 辽东森林区 (forest/taiga)
- 江南水网区 (wetland/flatland)
- 云南山地 (mountain/hill/forest)

地形种类: 12 种 (flatland/mountain/hill/forest/water/wetland/desert/coastal/steppe/taiga/oasis/sea)
生成流程: 6 遍扫描
  第1遍: 89 个 GEO_REGIONS 按地理区域分配基础地形
  第2遍: 填充完整地形数值 (movement_cost/defense_bonus/combat_modifiers/supply_yield)
  第3遍: 9 条河流河道覆盖
  第4遍: 10 个湖泊覆盖 (radius=1 扩展)
  第5遍: 大运河覆盖
  第6遍: 沿海检测 (邻接疆域外格子判定)
"""

from __future__ import annotations
import json
from pathlib import Path

from server.map.hex_grid import (
    HexCoord, iter_all_coords, GRID_ROWS, GRID_MAX_COLS, GRID_ODD_COLS,
    TOTAL_TILES,
)


# ============================================================
# 地形类型定义 (扩展)
# ============================================================

TERRAIN_TYPES = {
    "flatland": {
        "name": "平地",
        "movement_cost": 10, "defense_bonus": 0, "attack_modifier": 1.0,
        "cavalry_mod": 1.0, "infantry_mod": 1.0, "navy_mod": 0.0,
        "supply_yield": 3, "description": "平原沃野，利于骑兵驰骋",
    },
    "mountain": {
        "name": "山地",
        "movement_cost": 30, "defense_bonus": 4, "attack_modifier": 0.8,
        "cavalry_mod": 0.4, "infantry_mod": 1.3, "navy_mod": 0.0,
        "supply_yield": 1, "description": "崎岖险峻，步兵据守之地",
    },
    "hill": {
        "name": "丘陵",
        "movement_cost": 18, "defense_bonus": 2, "attack_modifier": 0.9,
        "cavalry_mod": 0.7, "infantry_mod": 1.1, "navy_mod": 0.0,
        "supply_yield": 2, "description": "缓丘起伏，可守可攻",
    },
    "forest": {
        "name": "林地",
        "movement_cost": 20, "defense_bonus": 3, "attack_modifier": 0.9,
        "cavalry_mod": 0.5, "infantry_mod": 1.2, "navy_mod": 0.0,
        "supply_yield": 2, "description": "密林幽深，伏击设防佳地",
    },
    "water": {
        "name": "水域",
        "movement_cost": 999, "defense_bonus": 0, "attack_modifier": 0.0,
        "cavalry_mod": 0.0, "infantry_mod": 0.0, "navy_mod": 1.5,
        "supply_yield": 2, "description": "江河湖海，需水军方可通行",
    },
    "wetland": {
        "name": "湿地",
        "movement_cost": 25, "defense_bonus": 1, "attack_modifier": 0.7,
        "cavalry_mod": 0.4, "infantry_mod": 0.8, "navy_mod": 0.3,
        "supply_yield": 2, "description": "沼泽泥泞，行军困难",
    },
    "desert": {
        "name": "荒漠",
        "movement_cost": 22, "defense_bonus": 0, "attack_modifier": 0.8,
        "cavalry_mod": 0.8, "infantry_mod": 0.7, "navy_mod": 0.0,
        "supply_yield": 1, "description": "戈壁荒漠，补给匮乏",
    },
    "coastal": {
        "name": "沿海",
        "movement_cost": 12, "defense_bonus": 0, "attack_modifier": 1.0,
        "cavalry_mod": 0.9, "infantry_mod": 1.0, "navy_mod": 1.2,
        "supply_yield": 3, "description": "沿海滩涂，港口所在",
    },
    "steppe": {
        "name": "草原",
        "movement_cost": 12, "defense_bonus": 0, "attack_modifier": 1.1,
        "cavalry_mod": 1.3, "infantry_mod": 0.9, "navy_mod": 0.0,
        "supply_yield": 2, "description": "一望无际的草原，骑兵驰骋的天下",
    },
    "taiga": {
        "name": "冻土林",
        "movement_cost": 22, "defense_bonus": 2, "attack_modifier": 0.8,
        "cavalry_mod": 0.6, "infantry_mod": 1.0, "navy_mod": 0.0,
        "supply_yield": 1, "description": "西伯利亚针叶林与冻土，苦寒之地",
    },
    "oasis": {
        "name": "绿洲",
        "movement_cost": 8, "defense_bonus": 0, "attack_modifier": 1.0,
        "cavalry_mod": 1.0, "infantry_mod": 1.0, "navy_mod": 0.0,
        "supply_yield": 4, "description": "丝绸之路绿洲，商旅汇集",
    },
    "sea": {
        "name": "海洋",
        "movement_cost": 25, "defense_bonus": 0, "attack_modifier": 0.0,
        "cavalry_mod": 0.0, "infantry_mod": 0.05, "navy_mod": 1.5,
        "supply_yield": 1, "description": "汪洋大海，需水师方可通行",
    },
}


# ============================================================
# 地理区域定义 - 覆盖元朝全盛疆域 (共 89 个地理区域 + 2 条主要水道)
# 网格映射: 经度55°E~140°E → col 0~55, 纬度15°N~60°N → row 35~0
# ============================================================

GEO_REGIONS = [
    # ============ 漠北草原区 (岭北行省) ============
    ("漠北草原东", 0, 5, 34, 46, "steppe", False),
    ("漠北草原中", 2, 7, 22, 36, "steppe", False),
    ("漠北草原西", 0, 5, 10, 24, "steppe", False),
    ("杭爱山区", 3, 7, 18, 26, "mountain", False),
    ("肯特山区", 2, 6, 30, 36, "hill", False),
    ("萨彦岭脉", 0, 3, 12, 18, "mountain", False),
    ("贝加尔湖区", 0, 3, 20, 28, "taiga", False),
    ("色楞格河谷", 3, 6, 20, 28, "steppe", False),

    # ============ 西伯利亚/漠北北部 (冻土林) ============
    ("外兴安岭", 0, 4, 40, 50, "taiga", False),
    ("勒拿河冻土", 0, 2, 28, 40, "taiga", False),
    ("叶尼塞河冻土", 0, 2, 10, 18, "taiga", False),
    ("鄂毕河冻土", 0, 2, 2, 10, "taiga", False),

    # ============ 西域/中亚 (甘肃行省+西部) ============
    ("准噶尔盆地", 4, 8, 2, 12, "desert", False),
    ("天山北麓草原", 5, 10, 4, 12, "steppe", False),
    ("天山山区", 6, 10, 2, 8, "mountain", False),
    ("塔里木盆地", 8, 12, 2, 10, "desert", False),
    ("塔里木绿洲带", 8, 12, 4, 10, "oasis", False),
    ("河西走廊", 4, 10, 8, 14, "desert", False),
    ("河西绿洲", 4, 9, 8, 14, "oasis", False),
    ("吐鲁番盆地", 6, 9, 4, 8, "desert", False),

    # ============ 吐蕃高原区 (宣政院辖地) ============
    ("羌塘高原", 10, 16, 2, 10, "taiga", False),
    ("藏北高原", 12, 18, 4, 12, "taiga", False),
    ("卫藏谷地", 16, 20, 2, 8, "steppe", False),
    ("雅鲁藏布谷", 18, 22, 2, 8, "flatland", False),
    ("横断山脉", 18, 22, 8, 14, "mountain", False),
    ("康区高原", 14, 18, 8, 16, "hill", False),
    ("喜马拉雅山", 18, 22, 0, 4, "mountain", False),
    ("阿里高原", 14, 18, 0, 2, "desert", False),

    # ============ 满洲/辽东 (辽阳行省) ============
    ("满洲针叶林", 0, 6, 42, 52, "taiga", False),
    ("大兴安岭", 2, 8, 38, 42, "mountain", False),
    ("松嫩草原", 4, 10, 42, 48, "steppe", False),
    ("辽河平原", 6, 12, 38, 44, "flatland", False),
    ("长白山区", 8, 14, 46, 52, "mountain", False),
    ("辽东丘陵", 8, 12, 40, 46, "hill", False),
    ("乌苏里森林", 6, 12, 50, 55, "taiga", False),
    ("黑龙江下游", 2, 6, 48, 55, "taiga", False),

    # ============ 高丽/朝鲜 (征东行省) ============
    ("朝鲜北部山地", 8, 14, 46, 52, "mountain", False),
    ("朝鲜南部丘陵", 14, 20, 46, 52, "hill", False),
    ("朝鲜西海岸平原", 12, 18, 46, 50, "flatland", False),
    ("朝鲜东海岸", 12, 18, 50, 54, "hill", True),

    # ============ 华北/中书省 ============
    ("华北平原北部", 4, 8, 26, 40, "flatland", False),
    ("华北平原南部", 8, 14, 28, 40, "flatland", False),
    ("山东丘陵", 6, 12, 38, 44, "hill", True),
    ("山东半岛", 4, 10, 40, 46, "hill", True),
    ("太行山北段", 4, 8, 24, 28, "mountain", False),
    ("太行山南段", 8, 12, 22, 26, "mountain", False),

    # ============ 黄土高原/陕西 ============
    ("黄土高原", 6, 14, 12, 22, "hill", False),
    ("关中平原", 10, 14, 12, 18, "flatland", False),
    ("秦岭山系", 10, 16, 10, 16, "mountain", False),
    ("陇西山地", 6, 10, 6, 12, "mountain", False),
    ("宁夏平原", 6, 10, 16, 20, "flatland", False),

    # ============ 中原/河南江北 ============
    ("中原平原", 12, 18, 20, 34, "flatland", False),
    ("淮北平原", 14, 18, 26, 38, "flatland", False),
    ("南阳盆地", 16, 20, 22, 28, "flatland", False),
    ("汉水谷地", 16, 20, 18, 24, "hill", False),
    ("大别山区", 18, 22, 26, 32, "mountain", False),

    # ============ 四川 ============
    ("成都平原", 16, 20, 8, 14, "flatland", False),
    ("川东丘陵", 18, 22, 12, 18, "hill", False),
    ("川北山地", 14, 18, 8, 14, "mountain", False),
    ("大巴山", 14, 18, 14, 20, "mountain", False),
    ("巫山", 18, 22, 16, 20, "mountain", False),

    # ============ 云南 ============
    ("云南高原", 22, 30, 6, 16, "hill", False),
    ("滇中山地", 24, 30, 4, 12, "mountain", False),
    ("滇西纵谷", 22, 28, 2, 8, "mountain", False),
    ("滇南热带", 28, 34, 6, 14, "forest", False),

    # ============ 长江中下游/江浙 ============
    ("长江中游平原", 18, 22, 18, 32, "flatland", False),
    ("长江下游平原", 16, 22, 32, 44, "flatland", False),
    ("江南水网区", 20, 24, 32, 42, "wetland", False),
    ("长江三角洲", 16, 20, 36, 44, "flatland", True),
    ("皖南丘陵", 20, 24, 30, 36, "hill", False),
    ("浙西丘陵", 22, 26, 36, 42, "hill", False),
    ("浙东丘陵", 22, 26, 42, 48, "hill", True),
    ("洞庭湖区", 20, 24, 20, 26, "wetland", False),
    ("江汉平原", 18, 22, 18, 24, "flatland", False),

    # ============ 江西/华南 ============
    ("赣北丘陵", 22, 26, 22, 30, "hill", False),
    ("赣南丘陵", 24, 28, 20, 28, "hill", False),
    ("武夷山区", 22, 28, 32, 38, "mountain", False),
    ("福建沿海平原", 24, 28, 40, 46, "flatland", True),
    ("福建丘陵", 24, 28, 36, 42, "hill", False),

    # ============ 湖广/岭南 ============
    ("湘中丘陵", 24, 28, 18, 26, "hill", False),
    ("湘南山地", 26, 30, 16, 24, "mountain", False),
    ("南岭山系", 28, 32, 18, 30, "mountain", False),
    ("岭南丘陵", 30, 34, 18, 30, "hill", False),
    ("珠江三角洲", 30, 34, 24, 30, "flatland", True),
    ("桂北山地", 28, 32, 12, 18, "mountain", False),
    ("桂中丘陵", 30, 34, 12, 18, "hill", False),
    ("海南岛", 32, 35, 22, 26, "hill", True),

    # ============ 主要水道 (后处理精确覆盖) ============
    ("黄河干流", 6, 16, 14, 40, "water", False),
    ("长江干流", 16, 24, 8, 44, "water", False),
]


# ============================================================
# 河流路径定义 - 以坐标点列精确描摹河道
# ============================================================

YELLOW_RIVER_PATH = [
    (6, 8), (8, 8), (10, 8), (12, 8), (14, 10), (16, 12),
    (18, 12), (20, 14), (22, 14), (24, 15), (26, 14),
    (28, 14), (30, 12), (32, 12), (34, 10), (36, 10),
    (38, 10), (40, 10), (40, 9), (42, 8), (44, 8),
]

YANGTZE_RIVER_PATH = [
    (6, 18), (8, 18), (10, 18), (12, 18), (14, 18),
    (16, 18), (18, 18), (20, 18), (22, 20), (24, 20),
    (26, 20), (28, 20), (30, 19), (32, 18), (34, 17),
    (36, 17), (38, 17), (40, 17), (42, 17), (44, 17),
]

HUAI_RIVER_PATH = [
    (22, 16), (24, 16), (26, 16), (28, 17), (30, 16),
    (32, 16), (34, 16), (36, 16), (38, 15), (40, 15), (42, 15),
]

HAN_RIVER_PATH = [
    (12, 16), (14, 17), (16, 18), (18, 18), (20, 18), (22, 18),
]

PEARL_RIVER_PATH = [
    (18, 30), (20, 30), (22, 30), (24, 30), (26, 30), (28, 30),
]

# 新增河流
AMUR_RIVER_PATH = [  # 黑龙江/阿穆尔河
    (38, 2), (40, 2), (42, 3), (44, 4), (46, 5),
    (48, 5), (50, 4), (52, 3), (54, 2),
]

MEKONG_RIVER_PATH = [  # 澜沧江/湄公河上游
    (4, 18), (6, 20), (6, 22), (8, 24), (8, 26), (10, 28),
]

SALWEEN_RIVER_PATH = [  # 怒江/萨尔温江
    (2, 18), (4, 20), (4, 22), (4, 24), (4, 26), (4, 28),
]

YELLOW_RIVER_UPPER = [  # 黄河上游 (青海/甘肃)
    (4, 6), (6, 6), (6, 8),
]

GRAND_CANAL_PATH = [
    (32, 6), (34, 7), (34, 8), (34, 9), (34, 10), (34, 11),
    (36, 12), (36, 14), (36, 15), (38, 16), (38, 17),
    (40, 20), (42, 18), (42, 17),
]

# 主要湖泊
MAJOR_LAKES = [
    ("洞庭湖", 20, 22),
    ("鄱阳湖", 28, 23),
    ("巢湖", 32, 19),
    ("太湖", 40, 19),
    ("洪泽湖", 36, 15),
    ("微山湖", 36, 13),
    ("滇池", 10, 28),
    ("青海湖", 6, 6),
    ("贝加尔湖", 22, 2),     # 元称"北海"
    ("巴尔喀什湖", 4, 5),    # 西域
]


# ============================================================
# 地形生成器
# ============================================================

def _wrap_river_tiles(path, river_width=1):
    result = set(path)
    if river_width <= 1:
        return result
    for c, r in path:
        coord = HexCoord(c, r)
        for nbr in coord.neighbors():
            result.add((nbr.col, nbr.row))
    return result


def _expand_lake(center_col, center_row, radius=1):
    result = {(center_col, center_row)}
    coord = HexCoord(center_col, center_row)
    for nbr in coord.neighbors():
        result.add((nbr.col, nbr.row))
    if radius > 1:
        for c, r in list(result):
            c2 = HexCoord(c, r)
            for nbr in c2.neighbors():
                result.add((nbr.col, nbr.row))
    return result


def generate_terrain_map(admin_assignments=None):
    terrain_map: dict[str, dict] = {}

    # --- 第1遍: 按地理区域分配基础地形 ---
    for coord in iter_all_coords():
        tile_id = f"hex_{coord.col}_{coord.row}"
        terrain_map[tile_id] = _default_terrain_entry()

    for name, r0, r1, c0, c1, terrain, coastal in GEO_REGIONS:
        for coord in iter_all_coords():
            if r0 <= coord.row <= r1 and c0 <= coord.col <= c1:
                tile_id = f"hex_{coord.col}_{coord.row}"
                entry = terrain_map.get(tile_id)
                if entry and entry["terrain"] == "flatland":
                    entry["terrain"] = terrain
                    if coastal:
                        entry["is_coastal"] = True

    # --- 第2遍: 填充完整地形数值 ---
    for tile_id, entry in terrain_map.items():
        terrain_type = entry["terrain"]
        tdef = TERRAIN_TYPES.get(terrain_type, TERRAIN_TYPES["flatland"])
        entry["movement_cost"] = tdef["movement_cost"]
        entry["defense_bonus"] = tdef["defense_bonus"]
        entry["attack_modifier"] = tdef["attack_modifier"]
        entry["combat_modifiers"] = {
            "cavalry": tdef["cavalry_mod"],
            "infantry": tdef["infantry_mod"],
            "navy": tdef["navy_mod"],
        }
        entry["supply_yield"] = tdef["supply_yield"]

    # --- 第3遍: 河流河道覆盖 ---
    river_sets = {
        "黄河": _wrap_river_tiles(YELLOW_RIVER_PATH),
        "黄河上游": _wrap_river_tiles(YELLOW_RIVER_UPPER),
        "长江": _wrap_river_tiles(YANGTZE_RIVER_PATH, river_width=2),
        "淮河": _wrap_river_tiles(HUAI_RIVER_PATH),
        "汉水": _wrap_river_tiles(HAN_RIVER_PATH),
        "珠江": _wrap_river_tiles(PEARL_RIVER_PATH),
        "黑龙江": _wrap_river_tiles(AMUR_RIVER_PATH),
        "澜沧江": _wrap_river_tiles(MEKONG_RIVER_PATH),
        "怒江": _wrap_river_tiles(SALWEEN_RIVER_PATH),
    }

    for river_name, river_tiles in river_sets.items():
        for c, r in river_tiles:
            if not (0 <= r < GRID_ROWS):
                continue
            max_c = GRID_MAX_COLS if r % 2 == 0 else GRID_ODD_COLS
            if not (0 <= c < max_c):
                continue
            tile_id = f"hex_{c}_{r}"
            if tile_id in terrain_map:
                terrain_map[tile_id]["terrain"] = "water"
                terrain_map[tile_id]["movement_cost"] = 999
                terrain_map[tile_id]["defense_bonus"] = 0
                terrain_map[tile_id]["is_ferry"] = True
                terrain_map[tile_id]["water_river"] = river_name
                terrain_map[tile_id]["combat_modifiers"] = {"cavalry": 0.0, "infantry": 0.0, "navy": 1.5}

    # --- 第4遍: 湖泊 ---
    for lake_name, lc, lr in MAJOR_LAKES:
        lake_tiles = _expand_lake(lc, lr, radius=1)
        for c, r in lake_tiles:
            if not (0 <= r < GRID_ROWS):
                continue
            max_c = GRID_MAX_COLS if r % 2 == 0 else GRID_ODD_COLS
            if not (0 <= c < max_c):
                continue
            tile_id = f"hex_{c}_{r}"
            if tile_id in terrain_map:
                terrain_map[tile_id]["terrain"] = "water"
                terrain_map[tile_id]["movement_cost"] = 999
                terrain_map[tile_id]["is_ferry"] = True
                terrain_map[tile_id]["water_lake"] = lake_name
                terrain_map[tile_id]["combat_modifiers"] = {"cavalry": 0.0, "infantry": 0.0, "navy": 1.5}

    # --- 第5遍: 大运河 ---
    for c, r in GRAND_CANAL_PATH:
        if not (0 <= r < GRID_ROWS):
            continue
        max_c = GRID_MAX_COLS if r % 2 == 0 else GRID_ODD_COLS
        if not (0 <= c < max_c):
            continue
        tile_id = f"hex_{c}_{r}"
        if tile_id in terrain_map:
            terrain_map[tile_id]["terrain"] = "water"
            terrain_map[tile_id]["is_ferry"] = True
            terrain_map[tile_id]["water_river"] = "大运河"
            terrain_map[tile_id]["movement_cost"] = 20
            terrain_map[tile_id]["combat_modifiers"] = {"cavalry": 0.3, "infantry": 0.5, "navy": 1.2}

    # --- 第6遍: 沿海检测 ---
    coastal_candidates: set[str] = set()
    for coord in iter_all_coords():
        tile_id = f"hex_{coord.col}_{coord.row}"
        for nbr in coord.rect_neighbors():
            nbr_id = f"hex_{nbr.col}_{nbr.row}"
            if nbr_id not in terrain_map:
                coastal_candidates.add(tile_id)
                break

    for tile_id in coastal_candidates:
        if tile_id in terrain_map and terrain_map[tile_id]["terrain"] != "water":
            terrain_map[tile_id]["is_coastal"] = True

    # 统计
    terrain_counts: dict[str, int] = {}
    for entry in terrain_map.values():
        t = entry["terrain"]
        terrain_counts[t] = terrain_counts.get(t, 0) + 1

    print(f"\n地形分配完成 ({len(terrain_map)} 个格子):")
    for t, c in sorted(terrain_counts.items(), key=lambda x: -x[1]):
        tname = TERRAIN_TYPES.get(t, {}).get("name", t)
        print(f"  {tname}({t}): {c} 格")

    coastal_count = sum(1 for e in terrain_map.values() if e["is_coastal"])
    ferry_count = sum(1 for e in terrain_map.values() if e["is_ferry"])
    print(f"  沿海: {coastal_count} 格")
    print(f"  渡口: {ferry_count} 格")

    return terrain_map


def _default_terrain_entry():
    return {
        "terrain": "flatland",
        "movement_cost": 10, "defense_bonus": 0, "attack_modifier": 1.0,
        "is_coastal": False, "is_ferry": False,
        "water_river": None, "water_lake": None,
        "combat_modifiers": {"cavalry": 1.0, "infantry": 1.0, "navy": 0.0},
        "supply_yield": 3,
    }


# ============================================================
# JSON 导出
# ============================================================

def export_terrain_json(output_path, terrain_map=None):
    if terrain_map is None:
        terrain_map = generate_terrain_map()

    data = {
        "meta": {
            "version": "3.0",
            "total_tiles": len(terrain_map),
            "terrain_types": {
                k: {"name": v["name"], "description": v["description"]}
                for k, v in TERRAIN_TYPES.items()
            },
            "description": "元末逐鹿3.0 - 元朝全盛疆域地形配置(含草原/冻土林/绿洲)",
        },
        "terrain_map": terrain_map,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n地形配置已导出: {output_path} ({output_path.stat().st_size:,} bytes)")
    return data


def get_terrain(tile_id, terrain_map):
    return terrain_map.get(tile_id, _default_terrain_entry())

def is_passable(terrain_entry):
    return terrain_entry.get("movement_cost", 10) < 900

def is_naval_passable(terrain_entry):
    return terrain_entry.get("is_ferry", False) or terrain_entry.get("is_coastal", False)
