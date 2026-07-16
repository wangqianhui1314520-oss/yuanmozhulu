"""
补给线系统 - 六角格地形规则核心

职责:
- 构建每回合补给线拓扑图
- 判定部队是否断补给
- 计算断补给逃散率
- 更新补给线状态
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    SupplyLine, Season,
)

logger = logging.getLogger("yuanmo.supply")

# 补给参数配置
SUPPLY_CONFIG = {
    "max_supply_distance": 4,       # 最大补给距离（格）
    "safe_supply_distance": 2,      # 安全补给距离（无衰减）
    "broken_attrition_base": 0.08,  # 断补给基础逃散率
    "broken_attrition_max": 0.15,   # 断补给最大逃散率
    "winter_attrition_bonus": 0.04, # 冬季断补给额外逃散
    "supply_base_types": {           # 可作为补给基地的地形
        TileType.CITY, TileType.PORT,
    },
    "supply_line_cost_per_tile": 1, # 每格补给线消耗
}


class SupplyEngine:
    """补给线引擎 (V4.2: 添加补给基地预索引和BFS缓存)"""

    def __init__(self, world: WorldState):
        self.world = world
        self._territory_adjacency: dict[str, list[str]] = {}
        # V4.2: 补给基地预索引 — faction_id → [tile]
        self._supply_bases: dict[str, list] = {}
        # V4.2: BFS距离缓存 — (source_id, target_id) → distance
        self._bfs_cache: dict[tuple, int] = {}

    def build_supply_network(self):
        """构建补给网络：为每个势力计算补给线 (V4.2: 预索引补给基地)"""
        # 先构建领地邻接图
        self._build_adjacency()
        # V4.2: 清空BFS缓存（每回合重新计算）
        self._bfs_cache.clear()

        # 清理过期补给线
        expired_lines = []
        for line_id, line in self.world.supply_lines.items():
            source = self.world.get_tile(line.source_tile)
            target = self.world.get_tile(line.target_tile)
            if not source or not target or source.faction_id != target.faction_id:
                expired_lines.append(line_id)
        for lid in expired_lines:
            del self.world.supply_lines[lid]

        # V4.2: 预索引补给基地
        self._supply_bases.clear()
        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            is_base = (tile.tile_type in SUPPLY_CONFIG["supply_base_types"] 
                      or tile.is_capital or tile.is_supply_base)
            if is_base:
                tile.supply_capacity = 200
                tile.is_supply_base = True
                self._supply_bases.setdefault(tile.faction_id, []).append(tile)

        # 为每个有驻军的地块建立/更新补给线
        for tile in self.world.tiles.values():
            if not tile.faction_id or tile.troops <= 0:
                continue
            if tile.tile_type in SUPPLY_CONFIG["supply_base_types"]:
                tile.supply_capacity = 200
                tile.is_supply_base = True
                continue

            # V4.2: 使用预索引查找最近补给基地
            nearest_base = self._find_nearest_supply_base_fast(tile)
            if nearest_base:
                distance = self._bfs_distance_cached(nearest_base.tile_id, tile.tile_id)
                line_id = f"supply_{tile.faction_id}_{tile.tile_id}"

                is_broken = distance > SUPPLY_CONFIG["max_supply_distance"]
                attrition = self._calc_attrition(distance, is_broken)

                line = SupplyLine(
                    line_id=line_id,
                    faction_id=tile.faction_id,
                    source_tile=nearest_base.tile_id,
                    target_tile=tile.tile_id,
                    distance=distance,
                    is_broken=is_broken,
                    attrition_rate=attrition,
                )
                self.world.supply_lines[line_id] = line

                if is_broken:
                    logger.debug(
                        f"补给线断裂: {tile.tile_name}({tile.faction_id}) "
                        f"距离补给基地{nearest_base.tile_name} {distance}格 > {SUPPLY_CONFIG['max_supply_distance']}格上限"
                    )

    def process_supply_attrition(self) -> dict:
        """处理补给消耗与逃散，返回受影响部队摘要"""
        result = {
            "supply_lines_total": len(self.world.supply_lines),
            "broken_lines": 0,
            "deserted_troops": {},  # tile_id → 逃散数量
            "desertion_total": 0,
        }

        for line_id, line in list(self.world.supply_lines.items()):
            tile = self.world.get_tile(line.target_tile)
            if not tile or tile.faction_id != line.faction_id:
                del self.world.supply_lines[line_id]
                continue

            if line.is_broken:
                result["broken_lines"] += 1
                # 断补给逃散
                attrition_rate = line.attrition_rate

                # 冬季额外逃散
                if self.world.current_season == Season.WINTER:
                    attrition_rate += SUPPLY_CONFIG["winter_attrition_bonus"]

                deserted = max(1, int(tile.troops * attrition_rate))
                tile.troops = max(0, tile.troops - deserted)
                tile.morale = max(0, tile.morale - random.randint(3, 10))

                result["deserted_troops"][tile.tile_id] = deserted
                result["desertion_total"] += deserted

                if deserted > 0:
                    logger.debug(  # 3.0: 降级为 debug 避免每回合数十条逃散日志刷屏
                        f"补给断裂逃散: {tile.tile_name} 逃散{deserted}人 "
                        f"(逃散率{attrition_rate:.1%}, 剩余兵力{tile.troops})"
                    )

            else:
                # 补给正常：消耗少量补给品
                grain_cost = int(tile.troops * 0.01 * max(1, line.distance - SUPPLY_CONFIG["safe_supply_distance"]))
                tile.grain = max(0, tile.grain - grain_cost)

        # 3.0: 汇总日志（一条 info 替代数十条 debug）
        if result["broken_lines"] > 0:
            logger.info(
                f"补给报告: {result['broken_lines']}条断裂, "
                f"逃散总计{result['desertion_total']}人 "
                f"(涉及{len(result['deserted_troops'])}个地块)"
            )

        return result

    def _build_adjacency(self):
        """构建领地邻接图（基于同势力相邻地块，使用坐标索引优化O(n²)）"""
        self._territory_adjacency = {}
        # 预建坐标索引: (q, r) → tile
        coord_index: dict = {}
        tiles_list = list(self.world.tiles.values())
        for t in tiles_list:
            coord_index[(t.q, t.r)] = t

        # 六边形合法邻居偏移（轴向坐标 q, r）
        HEX_NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

        for tile_a in tiles_list:
            if not tile_a.faction_id:
                continue
            neighbors = []
            for dq, dr in HEX_NEIGHBORS:
                nb = coord_index.get((tile_a.q + dq, tile_a.r + dr))
                if nb and nb.faction_id == tile_a.faction_id:
                    neighbors.append(nb.tile_id)
            self._territory_adjacency[tile_a.tile_id] = neighbors

    def _are_adjacent(self, a: TileState, b: TileState) -> bool:
        """判断两个地块是否相邻（基于 q/r 六边形坐标）
        
        六边形合法邻居: {(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)}
        注意: (1,1) 和 (-1,-1) 是对角线，不是合法邻居
        """
        if a.q == 0 and a.r == 0 and b.q == 0 and b.r == 0:
            return False
        dq = abs(a.q - b.q)
        dr = abs(a.r - b.r)
        # 六边形合法邻居: dq≤1, dr≤1, 且 dq+dr≤1（排除对角线 (1,1)）
        # 但还需排除 dq+dr==0（同一地块），已在调用方排除
        return dq <= 1 and dr <= 1 and (dq + dr) <= 1

    def _find_nearest_supply_base(self, tile: TileState) -> Optional[TileState]:
        """查找最近的本方补给基地（保留用于向后兼容）"""
        return self._find_nearest_supply_base_fast(tile)

    def _find_nearest_supply_base_fast(self, tile: TileState) -> Optional[TileState]:
        """V4.2: 使用预索引快速查找最近补给基地"""
        bases = self._supply_bases.get(tile.faction_id, [])
        if not bases:
            # 回退：遍历所有tile
            best_base = None
            best_distance = 999
            for other in self.world.tiles.values():
                if other.faction_id != tile.faction_id:
                    continue
                if other.tile_type not in SUPPLY_CONFIG["supply_base_types"] and not other.is_supply_base:
                    if not other.is_capital:
                        continue
                dist = self._bfs_distance_cached(other.tile_id, tile.tile_id)
                if dist < best_distance:
                    best_distance = dist
                    best_base = other
            return best_base
        
        # 遍历预索引的补给基地
        best_base = None
        best_distance = 999
        for base in bases:
            dist = self._bfs_distance_cached(base.tile_id, tile.tile_id)
            if dist < best_distance:
                best_distance = dist
                best_base = base
        return best_base

    def _bfs_distance_cached(self, start_id: str, target_id: str) -> int:
        """V4.2: 带缓存的BFS距离计算"""
        if start_id == target_id:
            return 0
        cache_key = (start_id, target_id)
        if cache_key in self._bfs_cache:
            return self._bfs_cache[cache_key]
        
        dist = self._bfs_distance(start_id, target_id)
        # 缓存双向
        self._bfs_cache[cache_key] = dist
        self._bfs_cache[(target_id, start_id)] = dist
        return dist

    def _bfs_distance(self, start_id: str, target_id: str) -> int:
        """BFS计算两地块间最短距离（沿己方领土相邻图）"""
        if start_id == target_id:
            return 0
        visited = {start_id}
        queue = [(start_id, 0)]
        while queue:
            current, dist = queue.pop(0)
            neighbors = self._territory_adjacency.get(current, [])
            for nid in neighbors:
                if nid == target_id:
                    return dist + 1
                if nid not in visited:
                    visited.add(nid)
                    queue.append((nid, dist + 1))
        return 999  # 不可达

    def _calc_attrition(self, distance: int, is_broken: bool) -> float:
        """计算逃散率"""
        if not is_broken:
            return 0.0
        extra = min(
            SUPPLY_CONFIG["broken_attrition_max"] - SUPPLY_CONFIG["broken_attrition_base"],
            (distance - SUPPLY_CONFIG["max_supply_distance"]) * 0.02,
        )
        return min(
            SUPPLY_CONFIG["broken_attrition_max"],
            SUPPLY_CONFIG["broken_attrition_base"] + extra,
        )

    def get_supply_status(self, tile_id: str) -> Optional[dict]:
        """查询地块补给状态"""
        for line in self.world.supply_lines.values():
            if line.target_tile == tile_id:
                return {
                    "supplied": not line.is_broken,
                    "distance": line.distance,
                    "source_tile": line.source_tile,
                    "attrition_rate": line.attrition_rate,
                }
        return None

    def get_faction_supply_summary(self, faction_id: str) -> dict:
        """获取势力补给摘要"""
        lines = [l for l in self.world.supply_lines.values() if l.faction_id == faction_id]
        broken = [l for l in lines if l.is_broken]
        return {
            "total_supply_lines": len(lines),
            "broken_lines": len(broken),
            "supply_coverage": round(len(lines) / max(1, len(self.world.get_faction_tiles(faction_id))) * 100, 1),
        }
