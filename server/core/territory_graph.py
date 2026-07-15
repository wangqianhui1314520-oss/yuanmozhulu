"""
CK3风格领地邻接图 — 全局路径规划与行军代价计算

功能：
- 基于行政层级(行省→路→府州)构建领地邻接图
- 河流/关隘/山脉地形阻隔判定
- 季节行军代价（冬季翻山×3, 河流结冰可通行）
- 水军判定（有舟船则水域/江河可通行）
- 路径回退方案（降级至六边形A*）
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("yuanmo.territory_graph")


class BarrierType(str, Enum):
    """地形障碍类型"""
    RIVER = "river"           # 河流
    PASS = "pass"             # 关隘
    MOUNTAIN = "mountain"     # 山脉
    SEA = "sea"               # 海域
    DESERT = "desert"         # 沙漠


@dataclass
class MarchCostInfo:
    """行军代价明细"""
    base_cost: float = 1.0
    terrain_mult: float = 1.0
    season_mult: float = 1.0
    barrier_mult: float = 1.0
    supply_mult: float = 1.0
    total_cost: float = 1.0


@dataclass
class Barrier:
    """地形障碍"""
    barrier_id: str
    name: str
    barrier_type: BarrierType
    passable_seasons: List[str] = field(default_factory=lambda: ["春", "夏", "秋"])  # 默认春夏秋可通行
    requires_navy: bool = False       # 是否需要水军
    between_tiles: Tuple[str, str] = field(default_factory=tuple)


class TerritoryGraph:
    """
    领地邻接图
    
    每个地块(tile)为一个节点，边表示可直接行军到达的邻接地块。
    边带有障碍信息(河流、关隘等)和季节通行条件。
    """

    def __init__(self):
        self._loaded: bool = False
        # tile_id → 相邻tile_id列表
        self._adjacency: Dict[str, List[str]] = {}
        # (tile_a, tile_b) → Barrier列表
        self._barriers: Dict[Tuple[str, str], List[Barrier]] = {}
        # tile_id → {季节行军代价乘数}
        self._terrain_modifiers: Dict[str, Dict[str, float]] = {}
        # tile_id → {tile_name, province, circuit, tile_type, hex_coords}
        self._tile_info: Dict[str, dict] = {}
        # 坐标 → tile_id 映射(用于回退寻路)
        self._coord_to_tile: Dict[Tuple[int, int], str] = {}

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load_from_world(self, world) -> None:
        """从WorldState构建领地邻接图"""
        try:
            from server.map.admin_hierarchy import get_territory_graph as get_admin_graph
            admin_data = get_admin_graph()
        except Exception as e:
            logger.warning(f"行政区划图加载失败，使用空邻接图: {e}")
            admin_data = {}

        # 六边形6方向
        HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        self._adjacency.clear()
        self._barriers.clear()
        self._terrain_modifiers.clear()
        self._tile_info.clear()
        self._coord_to_tile.clear()

        # 构建坐标→tile_id映射
        for tid, tile in world.tiles.items():
            coords = self._extract_coords(tid)
            if coords:
                self._coord_to_tile[coords] = tid

        for tid, tile in world.tiles.items():
            # 存储地块信息
            tile_type = tile.tile_type.value if hasattr(tile.tile_type, 'value') else str(tile.tile_type)
            self._tile_info[tid] = {
                "tile_id": tid,
                "tile_name": getattr(tile, 'tile_name', tid),
                "tile_type": tile_type,
                "faction_id": getattr(tile, 'faction_id', ''),
                "province": getattr(tile, 'province', ''),
                "circuit": getattr(tile, 'circuit', ''),
                "q": getattr(tile, 'q', 0),
                "r": getattr(tile, 'r', 0),
            }

            # 计算地形修正
            self._terrain_modifiers[tid] = self._calc_terrain_modifier(tile_type)

            # 寻找邻接地块
            coords = self._extract_coords(tid)
            if not coords:
                continue
            neighbors = []
            for dq, dr in HEX_DIRS:
                n_coords = (coords[0] + dq, coords[1] + dr)
                n_tid = self._coord_to_tile.get(n_coords)
                if n_tid and n_tid in world.tiles:
                    neighbors.append(n_tid)
                    # 检查障碍
                    n_tile = world.tiles.get(n_tid)
                    barriers = self._detect_barriers(tile, n_tile)
                    if barriers:
                        self._barriers.setdefault((tid, n_tid), []).extend(barriers)
            self._adjacency[tid] = neighbors

        self._loaded = True
        logger.info(f"[TerritoryGraph] 已加载 {len(self._adjacency)} 个领地节点, "
                     f"{len(self._barriers)} 条地形障碍")

    def _extract_coords(self, tile_id: str) -> Optional[Tuple[int, int]]:
        """从tile_id提取六边形坐标
        
        支持格式:
        - \"q,r\" (地图数据坐标格式, 如 \"26,15\")
        - \"tile_q_r\" (命名格式)
        - \"q_r\" (纯坐标格式)
        """
        raw = tile_id.replace("tile_", "")
        # 先尝试逗号分隔格式 (如 \"26,15\")
        if "," in raw:
            parts = raw.split(",")
        else:
            parts = raw.split("_")
        if len(parts) >= 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        return None

    def _calc_terrain_modifier(self, tile_type: str) -> Dict[str, float]:
        """计算各地形的季节行军倍率"""
        base = {"春": 1.0, "夏": 1.0, "秋": 1.0, "冬": 1.0}
        if tile_type == "mountain":
            base["冬"] = 3.0   # 冬季翻山×3
            base["秋"] = 1.3
        elif tile_type == "desert":
            base["夏"] = 2.0   # 夏季沙漠×2
            base["冬"] = 0.8
        elif tile_type == "swamp":
            base["夏"] = 1.5
            base["春"] = 1.5
        elif tile_type in ("forest", "jungle"):
            base["冬"] = 1.3
            base["春"] = 1.2
        elif tile_type == "tundra":
            base["冬"] = 2.5
        return base

    def _detect_barriers(self, tile_a, tile_b) -> List[Barrier]:
        """检测两个邻接地块之间的障碍"""
        barriers = []
        type_a = tile_a.tile_type.value if hasattr(tile_a.tile_type, 'value') else str(tile_a.tile_type)
        type_b = tile_b.tile_type.value if hasattr(tile_b.tile_type, 'value') else str(tile_b.tile_type)

        # 关隘判定
        if type_a == "pass" or type_b == "pass":
            barriers.append(Barrier(
                barrier_id=f"barrier_pass_{tile_a.tile_id}_{tile_b.tile_id}",
                name="关隘",
                barrier_type=BarrierType.PASS,
                passable_seasons=["春", "夏", "秋", "冬"],
                between_tiles=(tile_a.tile_id, tile_b.tile_id),
            ))

        # 河流判定
        if type_a == "river" or type_b == "river":
            barriers.append(Barrier(
                barrier_id=f"barrier_river_{tile_a.tile_id}_{tile_b.tile_id}",
                name="河流",
                barrier_type=BarrierType.RIVER,
                passable_seasons=["夏", "秋", "冬"],  # 冬季结冰可通行
                requires_navy=True,
                between_tiles=(tile_a.tile_id, tile_b.tile_id),
            ))

        return barriers

    def get_territory(self, tile_id: str) -> Optional[dict]:
        """获取领地信息"""
        return self._tile_info.get(tile_id)

    def get_neighbors(self, tile_id: str) -> List[str]:
        """获取邻接地块列表"""
        return self._adjacency.get(tile_id, [])

    def find_path(
        self,
        start_id: str,
        end_id: str,
        season: str = "春",
        has_navy: bool = False,
        blocked_territories: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Dijkstra寻路 — 带季节代价、水军判定
        
        Returns:
            路径tile_id列表，空列表表示无路径
        """
        if start_id not in self._adjacency or end_id not in self._adjacency:
            # 尝试回退六边形A*
            return self._hex_astar_fallback(start_id, end_id, season, has_navy, blocked_territories)

        if blocked_territories is None:
            blocked_territories = set()

        import heapq
        # (cost, tile_id, path)
        queue = [(0.0, start_id, [start_id])]
        visited = set()

        while queue:
            cost, current, path = heapq.heappop(queue)
            if current == end_id:
                return path
            if current in visited:
                continue
            visited.add(current)

            for nid in self._adjacency.get(current, []):
                if nid in visited:
                    continue
                if nid in blocked_territories and nid != end_id:
                    continue

                # 计算行军代价
                march_cost = self._calc_edge_cost(current, nid, season, has_navy)
                if march_cost.total_cost >= 999:
                    continue  # 不可通行

                heapq.heappush(queue, (cost + march_cost.total_cost, nid, path + [nid]))

        return []

    def _hex_astar_fallback(
        self, start_id: str, end_id: str, season: str,
        has_navy: bool, blocked: Optional[Set[str]]
    ) -> List[str]:
        """六边形A*寻路回退"""
        import heapq

        start_coord = self._extract_coords(start_id)
        end_coord = self._extract_coords(end_id)
        if not start_coord or not end_coord:
            return []

        def hex_dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs((a[0] + a[1]) - (b[0] + b[1])))

        HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        queue = [(hex_dist(start_coord, end_coord), 0, start_coord, [start_id])]
        visited = set()

        while queue:
            _, g, coord, path = heapq.heappop(queue)
            if coord == end_coord:
                return path
            if coord in visited:
                continue
            visited.add(coord)

            for dq, dr in HEX_DIRS:
                n_coord = (coord[0] + dq, coord[1] + dr)
                n_tid = self._coord_to_tile.get(n_coord)
                if not n_tid:
                    continue
                if blocked and n_tid in blocked and n_tid != end_id:
                    continue
                if n_tid not in self._tile_info:
                    continue
                info = self._tile_info[n_tid]
                
                # 检查通行性
                tile_type = info.get("tile_type", "")
                if tile_type == "sea" and not has_navy:
                    continue
                if tile_type == "river":
                    # 冬季可通行河流，其他季节需要水军
                    if season != "冬" and not has_navy:
                        continue

                terrain_mod = self._terrain_modifiers.get(n_tid, {})
                step_cost = terrain_mod.get(season, 1.0)
                new_g = g + step_cost
                f = new_g + hex_dist(n_coord, end_coord)
                heapq.heappush(queue, (f, new_g, n_coord, path + [n_tid]))

        return []

    def _calc_edge_cost(self, from_id: str, to_id: str, season: str, has_navy: bool) -> MarchCostInfo:
        """计算两地间的行军代价"""
        cost = MarchCostInfo()

        # 基础代价
        cost.base_cost = 1.0

        # 地形季度修正
        terrain_mod = self._terrain_modifiers.get(to_id, {})
        cost.season_mult = terrain_mod.get(season, 1.0)

        # 障碍判定
        barriers = self._barriers.get((from_id, to_id), [])
        for barrier in barriers:
            if barrier.barrier_type == BarrierType.RIVER:
                if season != "冬" and not has_navy:
                    cost.total_cost = 999  # 不可通行
                    return cost
                if season != "冬" and has_navy:
                    cost.barrier_mult *= 1.5
            elif barrier.barrier_type == BarrierType.PASS:
                cost.barrier_mult *= 2.0
            elif barrier.barrier_type == BarrierType.SEA and not has_navy:
                cost.total_cost = 999
                return cost
            elif barrier.barrier_type == BarrierType.MOUNTAIN:
                cost.barrier_mult *= 1.5

        cost.terrain_mult = 1.0
        cost.supply_mult = 1.0
        cost.total_cost = cost.base_cost * cost.season_mult * cost.barrier_mult
        return cost

    def calculate_march_cost(self, from_id: str, to_id: str, season: str, has_navy: bool) -> MarchCostInfo:
        """公开接口：计算行军代价（同_calc_edge_cost）"""
        return self._calc_edge_cost(from_id, to_id, season, has_navy)

    def get_barriers_between(self, from_id: str, to_id: str) -> List[Barrier]:
        """获取两地间的障碍列表"""
        return self._barriers.get((from_id, to_id), [])

    def get_attackable_targets(
        self,
        territory_id: str,
        faction_id: str,
        tile_map: dict,
        faction_tiles: dict,
    ) -> List[dict]:
        """
        获取可攻击的相邻地块
        
        Returns:
            [{tile_id, distance, estimated_defense, ...}]
        """
        results = []
        for nid in self._adjacency.get(territory_id, []):
            info = self._tile_info.get(nid, {})
            if info.get("faction_id") == faction_id:
                continue  # 跳过己方地块

            tile = tile_map.get(nid)
            if not tile:
                continue

            results.append({
                "tile_id": nid,
                "tile_name": info.get("tile_name", nid),
                "tile_type": info.get("tile_type", "unknown"),
                "faction_id": info.get("faction_id", ""),
                "distance": 1,
                "troops": getattr(tile, 'troops', 0) if tile else 0,
                "fortification": getattr(tile, 'fortification', 0) if tile else 0,
                "is_capital": info.get("is_capital", False),
            })

        return results


# ============================================================
# 全局单例
# ============================================================

_global_graph: Optional[TerritoryGraph] = None


def get_territory_graph() -> TerritoryGraph:
    """获取全局领地邻接图单例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = TerritoryGraph()
    return _global_graph


def init_territory_graph(world) -> TerritoryGraph:
    """初始化领地邻接图（从WorldState加载）"""
    global _global_graph
    _global_graph = TerritoryGraph()
    _global_graph.load_from_world(world)
    return _global_graph


def reset_territory_graph():
    """重置领地邻接图"""
    global _global_graph
    _global_graph = None
