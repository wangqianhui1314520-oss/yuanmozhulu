"""
势力初始领地配置 v4.1 - 府州级整块分配 (统一势力ID，按沙盘地图系统文档)

v4.1 变更:
- 按文档修正势力首都：徐寿辉→汴梁(22,13)，王保保→中庆(14,18)
- 王保保核心行省从"中书省"改为"云南"（梁王治云南）
- 势力ID统一为 faction_ 前缀，与 factions.json 体系一致
- 配额算法：独占省份限定上限+共享省份BFS公平竞争+剩余按配额比例分配
- 目标每势力35~95格，总计499格

势力列表（统一ID体系）:
  1. faction_yuan         元廷    - 岭北+辽阳+中书省+陕西+甘肃+宣政院  | 首都: 大都(北京)
  2. faction_xushouhui    徐寿辉   - 河南江北                         | 首都: 汴梁(开封)
  3. faction_zhuyuanzhang 朱元璋   - 江浙                             | 首都: 集庆(南京)
  4. faction_chenyouliang 陈友谅   - 江西+湖广                        | 首都: 武昌
  5. faction_zhangshicheng张士诚   - 江浙                             | 首都: 平江(苏州)
  6. faction_fangguozhen  方国珍   - 江浙                             | 首都: 庆元(宁波)
  7. faction_wangbaobao   王保保   - 云南（梁王）                      | 首都: 中庆(昆明)
  8. faction_mingyuzhen   明玉珍   - 四川                             | 首都: 成都
  9. faction_mobei        漠北诸部 - 岭北                             | 首都: 和林
"""

from __future__ import annotations
import json
import random
from typing import Dict, List, Optional, Set, Tuple
from collections import deque

from server.map.hex_grid import (
    HexCoord, iter_all_coords,
    GRID_ROWS, GRID_MAX_COLS, DEFAULT_HEX_SIZE,
)
from server.map.territory_mask import INCLUDED_HEXES


# ============================================================
# 势力配色（统一ID体系）
# ============================================================

FACTION_COLORS: Dict[str, dict] = {
    "faction_yuan":          {"fill": "#8B0000", "border": "#FF4444", "name": "元廷",    "name_cn": "大元"},
    "faction_xushouhui":     {"fill": "#B8860B", "border": "#FFD700", "name": "徐寿辉",  "name_cn": "天完"},
    "faction_zhuyuanzhang":  {"fill": "#006400", "border": "#32CD32", "name": "朱元璋",  "name_cn": "西吴"},
    "faction_chenyouliang":  {"fill": "#00008B", "border": "#4169E1", "name": "陈友谅",  "name_cn": "大汉"},
    "faction_zhangshicheng": {"fill": "#8B008B", "border": "#FF69B4", "name": "张士诚",  "name_cn": "大周"},
    "faction_fangguozhen":   {"fill": "#2F4F4F", "border": "#20B2AA", "name": "方国珍",  "name_cn": "方氏"},
    "faction_wangbaobao":    {"fill": "#4B0082", "border": "#9370DB", "name": "王保保",  "name_cn": "梁王"},
    "faction_mingyuzhen":    {"fill": "#8B4513", "border": "#DEB887", "name": "明玉珍",  "name_cn": "大夏"},
    "faction_mobei":         {"fill": "#556B2F", "border": "#9ACD32", "name": "漠北诸部","name_cn": "漠北"},
}

FACTION_CAPITALS: Dict[str, Tuple[int, int]] = {
    "faction_yuan":          (24, 8),    # 大都 (北京)
    "faction_xushouhui":     (22, 13),   # 汴梁 (开封)
    "faction_zhuyuanzhang":  (26, 15),   # 集庆 (南京)
    "faction_chenyouliang":  (20, 17),   # 武昌
    "faction_zhangshicheng": (28, 16),   # 平江 (苏州)
    "faction_fangguozhen":   (29, 18),   # 庆元 (宁波)
    "faction_wangbaobao":    (14, 18),   # 中庆 (昆明)
    "faction_mingyuzhen":    (14, 14),   # 成都
    "faction_mobei":         (18, 4),    # 和林 (漠北草原)
}


# ============================================================
# 势力核心地盘定义 (按省份分配)
# ============================================================

FACTION_CORE_PROVINCES: Dict[str, List[str]] = {
    "faction_yuan":          ["lingbei", "liaoyang", "zhongshu", "shaanxi", "gansu", "xuanzheng"],
    "faction_xushouhui":     ["henan_jiangbei"],
    "faction_zhuyuanzhang":  ["jiangzhe"],
    "faction_chenyouliang":  ["jiangxi", "huguang"],
    "faction_zhangshicheng": ["jiangzhe"],
    "faction_fangguozhen":   ["jiangzhe"],
    "faction_wangbaobao":    ["yunnan"],    # 梁王治云南
    "faction_mingyuzhen":    ["sichuan"],
    "faction_mobei":         ["lingbei"],   # 与元廷共享岭北
}

# 势力府州配额（v4.1重平衡：每势力35~95格，总和499）
FACTION_QUOTAS: Dict[str, int] = {
    "faction_yuan":          95,
    "faction_xushouhui":     65,
    "faction_zhuyuanzhang":  55,
    "faction_chenyouliang":  70,
    "faction_zhangshicheng": 50,
    "faction_fangguozhen":   35,
    "faction_wangbaobao":    40,
    "faction_mingyuzhen":    55,
    "faction_mobei":         34,
}


# ============================================================
# 核心分配算法 - 府州级整块分配
# ============================================================

def _bfs_from_capitals(
    tile_adjacency: Dict[str, List[str]],
    capitals: Dict[str, str],  # faction_id → tile_id
    available_tiles: Set[str],
    quotas: Dict[str, int],
) -> Dict[str, Set[str]]:
    """
    多势力同时 BFS 扩张, 按格子分配

    每轮各势力扩张一步, 已占领格子从可用池移除。
    到达配额后该势力停止扩张。
    """
    factions = list(capitals.keys())
    territories: Dict[str, Set[str]] = {f: set() for f in factions}
    frontiers: Dict[str, deque] = {}

    # 初始化: 首都加入
    for fid, capital_tile in capitals.items():
        if capital_tile in available_tiles:
            territories[fid].add(capital_tile)
            available_tiles.discard(capital_tile)
            frontiers[fid] = deque([capital_tile])

    # 轮流扩张
    active = True
    while active:
        active = False
        for fid in factions:
            quota = quotas.get(fid, 10)
            if len(territories[fid]) >= quota:
                continue
            if fid not in frontiers or not frontiers[fid]:
                continue

            # 扩张一步
            current = frontiers[fid].popleft()
            for neighbor in tile_adjacency.get(current, []):
                if neighbor in available_tiles:
                    territories[fid].add(neighbor)
                    available_tiles.discard(neighbor)
                    frontiers[fid].append(neighbor)
                    active = True
                    if len(territories[fid]) >= quota:
                        break

    return territories


def generate_initial_territories(
    tile_province_map: Dict[str, str],
    tile_adjacency: Dict[str, List[str]],
) -> Dict[str, dict]:
    """
    生成九大势力初始领地 (府州级)
    
    策略: 核心行省独占 + BFS按配额扩张 + 未分配按距离归属

    Returns:
        faction_id → {tiles, capital, tile_count, color, provinces}
    """
    territories: Dict[str, Set[str]] = {fid: set() for fid in FACTION_CAPITALS}
    assigned: Set[str] = set()

    # 所有 tile 按省份分组
    prov_tiles: Dict[str, Set[str]] = {}
    for tid, pid in tile_province_map.items():
        prov_tiles.setdefault(pid, set()).add(tid)

    # ======== 第一步: 每势力保留首都 ========
    for fid, (cc, cr) in FACTION_CAPITALS.items():
        cap_tid = f"{cc},{cr}"
        if cap_tid in tile_adjacency:
            territories[fid].add(cap_tid)
            assigned.add(cap_tid)

    # ======== 第二步: 独占省份 → BFS 限配额 ========
    for fid, core_provs in FACTION_CORE_PROVINCES.items():
        quota = FACTION_QUOTAS.get(fid, 10)
        for prov_id in core_provs:
            if prov_id not in prov_tiles:
                continue
            # 检查是否独占
            other_factions = [f for f, ps in FACTION_CORE_PROVINCES.items()
                             if f != fid and prov_id in ps]
            if other_factions:
                continue  # 共享省份, 第三步处理
            
            # 独占省份: 全部拿下(上限 = quota)
            available = prov_tiles[prov_id] - assigned
            for tid in list(available)[:quota - len(territories[fid])]:
                territories[fid].add(tid)
                assigned.add(tid)
                if len(territories[fid]) >= quota:
                    break

    # ======== 第三步: 共享省份 → 多势力BFS竞争 ========
    # 动态识别共享省份（任一省份被多个势力声明）
    shared_provs: Set[str] = set()
    prov_faction_count: Dict[str, int] = {}
    for fid, core_provs in FACTION_CORE_PROVINCES.items():
        for prov_id in core_provs:
            prov_faction_count[prov_id] = prov_faction_count.get(prov_id, 0) + 1
    shared_provs = {pid for pid, cnt in prov_faction_count.items() if cnt > 1}

    for prov_id in shared_provs:
        if prov_id not in prov_tiles:
            continue
        available = prov_tiles[prov_id] - assigned
        if not available:
            continue
        competitors = [f for f, ps in FACTION_CORE_PROVINCES.items()
                      if prov_id in ps]

        # 多势力轮流BFS，使用队列逐层扩张
        frontiers: Dict[str, deque] = {}
        for fid in competitors:
            cap_tid = f"{FACTION_CAPITALS[fid][0]},{FACTION_CAPITALS[fid][1]}"
            frontiers[fid] = deque([cap_tid]) if cap_tid in tile_adjacency else deque()

        max_rounds = 50
        for _ in range(max_rounds):
            if not available:
                break
            any_expanded = False
            for fid in competitors:
                quota = FACTION_QUOTAS.get(fid, 10)
                if len(territories[fid]) >= quota:
                    continue
                if not frontiers.get(fid):
                    continue
                # BFS 一层：处理当前队列中所有节点
                next_frontier = deque()
                for _ in range(len(frontiers[fid])):
                    if not frontiers[fid]:
                        break
                    current = frontiers[fid].popleft()
                    for nb in tile_adjacency.get(current, []):
                        if nb in available:
                            territories[fid].add(nb)
                            assigned.add(nb)
                            available.discard(nb)
                            next_frontier.append(nb)
                            any_expanded = True
                            if len(territories[fid]) >= quota:
                                break
                    if len(territories[fid]) >= quota:
                        break
                frontiers[fid] = next_frontier
            if not any_expanded:
                break

    # ======== 第四步: 未分配按距离归属（带配额上限） ========
    unassigned = set(tile_adjacency.keys()) - assigned
    # 按距离排序，离势力首都越近越优先
    tile_distances: List[Tuple[str, str, int]] = []  # (tile_id, faction_id, distance)
    for tid in unassigned:
        tc, tr = map(int, tid.split(","))
        for fid, (fc, fr) in FACTION_CAPITALS.items():
            dist = abs(tc - fc) + abs(tr - fr)
            tile_distances.append((tid, fid, dist))
    # 按距离升序：近的优先分配
    tile_distances.sort(key=lambda x: x[2])
    for tid, fid, dist in tile_distances:
        if tid not in unassigned:
            continue
        quota = FACTION_QUOTAS.get(fid, 10)
        if len(territories[fid]) >= quota:
            continue
        territories[fid].add(tid)
        assigned.add(tid)
        unassigned.discard(tid)

    # ======== 组装输出 ========
    result = {}
    for fid, color_info in FACTION_COLORS.items():
        cc, cr = FACTION_CAPITALS[fid]
        capital_tile = f"{cc},{cr}"
        tiles = sorted(territories.get(fid, set()))

        result[fid] = {
            "tiles": tiles,
            "capital": capital_tile,
            "tile_count": len(tiles),
            "color": color_info,
            "provinces": list(set(
                tile_province_map.get(tid, "unknown") for tid in tiles
            )),
        }

    return result


# ============================================================
# 导出和工具
# ============================================================

def export_faction_territory_json(
    territories: Dict[str, dict],
    output_path: str = "server/data/map/faction_territories.json",
):
    """导出势力领地配置 JSON"""
    output = {
        "version": "4.1",
        "level": "prefecture",
        "meta": {
            "grid_rows": GRID_ROWS,
            "grid_max_cols": GRID_MAX_COLS,
            "hex_size": int(DEFAULT_HEX_SIZE),
            "faction_count": len(territories),
            "total_assigned_tiles": sum(t["tile_count"] for t in territories.values()),
        },
        "factions": {
            fid: {
                "tiles": data["tiles"],
                "capital": data["capital"],
                "tile_count": data["tile_count"],
                "color": data["color"],
                "provinces": data["provinces"],
            }
            for fid, data in territories.items()
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    for fid, data in territories.items():
        print(f"    {FACTION_COLORS[fid]['name']}({fid}): {data['tile_count']} 府州")

    print(f"  [势力] 导出完成: {output_path}")


def generate_tile_faction_map(territories: Dict[str, dict]) -> Dict[str, str]:
    """生成 tile_id → faction_id 映射"""
    mapping = {}
    for fid, data in territories.items():
        for tid in data["tiles"]:
            mapping[tid] = fid
    return mapping


if __name__ == "__main__":
    from server.map.admin_hierarchy import assign_tiles_to_hierarchy, generate_tile_province_map
    from server.map.adjacency import build_adjacency_table

    print("生成势力初始领地...")
    assignments = assign_tiles_to_hierarchy()
    prov_map = generate_tile_province_map(assignments)
    adj = build_adjacency_table()

    territories = generate_initial_territories(prov_map, adj)
    export_faction_territory_json(territories)
