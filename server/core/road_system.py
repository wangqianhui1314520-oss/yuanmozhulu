"""
道路与驿站系统 - 六角格道路网络与驿站管理

职责:
- 道路建设/拆除/降级/自动规划
- 驿站自动部署与管理
- 道路效果（移动加速、贸易加成、补给延伸）
- 道路维护费计算
- 敌军占领地块道路降级处理

基于 navigation skill 指导设计
"""
from __future__ import annotations
import logging
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

from server.models.world_state import (
    WorldState, FactionState, TileState, TileType, Season,
)

logger = logging.getLogger("yuanmo.road")


# ================================================================
# 枚举与数据类
# ================================================================
class RoadType(str, Enum):
    OFFICIAL_ROAD = "official_road"   # 官道: 移动×0.7, 建设500银两/格
    POSTAL_ROAD = "postal_road"       # 驿道: 移动×0.5, 建设1000银两/格, 需连首都
    DIRT_PATH = "dirt_path"           # 小路: 移动×0.9, 自动生成


@dataclass
class RoadSegment:
    """道路段 - 连接两个相邻地块"""
    road_id: str
    road_type: RoadType
    tile_a: str                        # 地块A的tile_id
    tile_b: str                        # 地块B的tile_id
    faction_id: str
    built_round: int = 0
    is_degraded: bool = False


@dataclass
class PostalRelayStation:
    """驿站"""
    station_id: str
    tile_id: str
    faction_id: str
    supply_radius_bonus: int = 2      # 补给距离加成
    messenger_speed_bonus: float = 0.30  # 信使速度加成
    morale_recovery: int = 5           # 每回合士气回复
    upkeep: int = 50                   # 维护费/回合


# ================================================================
# 道路配置常量
# ================================================================
ROAD_CONFIG: dict[RoadType, dict] = {
    RoadType.OFFICIAL_ROAD: {
        "name": "官道", "speed_mult": 0.7, "build_cost": 500,
        "upkeep": 20, "trade_bonus": 0.15, "supply_extend": 1,
    },
    RoadType.POSTAL_ROAD: {
        "name": "驿道", "speed_mult": 0.5, "build_cost": 1000,
        "upkeep": 40, "trade_bonus": 0.25, "supply_extend": 2,
    },
    RoadType.DIRT_PATH: {
        "name": "小路", "speed_mult": 0.9, "build_cost": 0,
        "upkeep": 0, "trade_bonus": 0.0, "supply_extend": 0,
    },
}

# 驿站配置
RELAY_CONFIG = {
    "min_spacing": 3,        # 驿站最小间距（格）
    "max_spacing": 5,        # 驿站最大间距（格）
    "build_cost": 300,       # 建设费（银两）
    "upkeep": 50,            # 维护费/回合
    "supply_bonus": 2,       # 补给距离加成
    "messenger_bonus": 0.30, # 信使速度加成
    "morale_recovery": 5,    # 士气回复/回合
}

# 六边形邻居偏移（轴向坐标）
_HEX_NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# ================================================================
# RoadSystem 主类
# ================================================================
class RoadSystem:
    """道路与驿站系统"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = game_const or {}
        # 道路网络: faction_id → [RoadSegment, ...]
        self._roads: dict[str, list[RoadSegment]] = {}
        # V4.2: 路段反向索引 — tile_id → [(tile_b_id, RoadSegment), ...]
        self._road_index: dict[str, list[tuple[str, RoadSegment]]] = {}
        # 驿站: faction_id → [PostalRelayStation, ...]
        self._relay_stations: dict[str, list[PostalRelayStation]] = {}
        self._init_roads()

    def _init_roads(self):
        """初始化道路网络（加载已有道路数据，自动生成小路）"""
        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue
            self._roads.setdefault(fid, [])
            self._relay_stations.setdefault(fid, [])

        # 自动为相邻己方地块间生成小路
        self._auto_generate_dirt_paths()

    def _auto_generate_dirt_paths(self):
        """为相邻己方地块自动生成小路 (V4.2: 使用索引避免重复检查)"""
        coord_index = {}
        for t in self.world.tiles.values():
            coord_index[(t.q, t.r)] = t

        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            for dq, dr in _HEX_NEIGHBORS:
                nb = coord_index.get((tile.q + dq, tile.r + dr))
                if nb and nb.faction_id == tile.faction_id:
                    # V4.2: 使用索引快速检查
                    existing_roads = self._road_index.get(tile.tile_id, [])
                    exists = any(nb_id == nb.tile_id for nb_id, _ in existing_roads)
                    if not exists:
                        road_id = f"dirt_{tile.tile_id}_{nb.tile_id}"
                        seg = RoadSegment(
                            road_id=road_id,
                            road_type=RoadType.DIRT_PATH,
                            tile_a=tile.tile_id,
                            tile_b=nb.tile_id,
                            faction_id=tile.faction_id,
                            built_round=self.world.current_round,
                        )
                        self._roads.setdefault(tile.faction_id, []).append(seg)
                        # V4.2: 维护索引
                        self._road_index.setdefault(tile.tile_id, []).append((nb.tile_id, seg))
                        self._road_index.setdefault(nb.tile_id, []).append((tile.tile_id, seg))

    # ================================================================
    # 道路建设与管理
    # ================================================================
    def build_road(self, faction_id: str, tile_a_id: str, tile_b_id: str,
                   road_type: RoadType) -> dict:
        """在两相邻地块间建造道路"""
        faction = self.world.factions.get(faction_id)
        if not faction or not faction.is_alive:
            return {"success": False, "reason": "势力不存在"}

        tile_a = self.world.get_tile(tile_a_id)
        tile_b = self.world.get_tile(tile_b_id)
        if not tile_a or not tile_b:
            return {"success": False, "reason": "地块不存在"}

        # 驿道必须连接首都
        if road_type == RoadType.POSTAL_ROAD:
            if not (tile_a.is_capital or tile_b.is_capital or
                    self._is_connected_to_capital(faction_id, tile_a_id) or
                    self._is_connected_to_capital(faction_id, tile_b_id)):
                return {"success": False, "reason": "驿道必须连接首都"}

        # 检查地块归属
        if tile_a.faction_id != faction_id or tile_b.faction_id != faction_id:
            return {"success": False, "reason": "地块不属于己方"}

        # 检查是否相邻
        if not self._are_adjacent(tile_a, tile_b):
            return {"success": False, "reason": "地块不相邻"}

        # 检查是否已有道路
        fid_roads = self._roads.setdefault(faction_id, [])
        for r in fid_roads:
            if (r.tile_a == tile_a_id and r.tile_b == tile_b_id) or \
               (r.tile_a == tile_b_id and r.tile_b == tile_a_id):
                if r.road_type == road_type:
                    return {"success": False, "reason": "该路段已有同类型道路"}
                # 升级道路：替换旧路
                fid_roads.remove(r)
                break

        # 检查费用
        cost = ROAD_CONFIG[road_type]["build_cost"]
        if faction.treasury < cost:
            return {"success": False, "reason": f"国库不足，需要{cost}银两"}

        faction.treasury -= cost

        road_id = f"{road_type.value}_{tile_a_id}_{tile_b_id}"
        segment = RoadSegment(
            road_id=road_id, road_type=road_type,
            tile_a=tile_a_id, tile_b=tile_b_id,
            faction_id=faction_id, built_round=self.world.current_round,
        )
        fid_roads.append(segment)
        # V4.2: 维护索引
        self._road_index.setdefault(tile_a_id, []).append((tile_b_id, segment))
        self._road_index.setdefault(tile_b_id, []).append((tile_a_id, segment))

        logger.info(f"{faction.name} 建造{ROAD_CONFIG[road_type]['name']}: "
                    f"{tile_a.tile_name}↔{tile_b.tile_name} (花费{cost}银两)")

        return {"success": True, "road_id": road_id, "cost": cost}

    def remove_road(self, faction_id: str, road_id: str) -> dict:
        """拆除道路 (V4.2: 同时清理索引)"""
        fid_roads = self._roads.get(faction_id, [])
        for r in fid_roads:
            if r.road_id == road_id:
                fid_roads.remove(r)
                # V4.2: 清理索引
                self._remove_from_index(r.tile_a, r.tile_b, r)
                self._remove_from_index(r.tile_b, r.tile_a, r)
                return {"success": True, "removed": road_id}
        return {"success": False, "reason": "道路不存在"}

    def _remove_from_index(self, tile_id: str, neighbor_id: str, segment: RoadSegment):
        """V4.2: 从索引中移除路段"""
        entries = self._road_index.get(tile_id, [])
        self._road_index[tile_id] = [
            (nid, seg) for nid, seg in entries
            if not (nid == neighbor_id and seg.road_id == segment.road_id)
        ]

    def _is_connected_to_capital(self, faction_id: str, tile_id: str) -> bool:
        """检查地块是否通过道路连接到首都"""
        faction = self.world.factions.get(faction_id)
        if not faction:
            return False
        capital = self.world.get_tile(faction.capital_tile)
        if not capital or capital.tile_id == tile_id:
            return capital is not None

        # BFS 沿道路图
        visited = {tile_id}
        queue = [tile_id]
        while queue:
            current = queue.pop(0)
            for r in self._roads.get(faction_id, []):
                if r.is_degraded:
                    continue
                neighbor = None
                if r.tile_a == current:
                    neighbor = r.tile_b
                elif r.tile_b == current:
                    neighbor = r.tile_a
                if neighbor and neighbor == capital.tile_id:
                    return True
                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    @staticmethod
    def _are_adjacent(a: TileState, b: TileState) -> bool:
        """判断两个地块是否相邻（基于六边形坐标）"""
        dq = abs(a.q - b.q)
        dr = abs(a.r - b.r)
        return dq <= 1 and dr <= 1 and (dq + dr) <= 1 and (dq + dr) > 0

    # ================================================================
    # 道路效果计算
    # ================================================================
    def get_tile_speed_mult(self, tile_id: str) -> float:
        """获取地块的道路移动速度倍率 (V4.2: 使用索引加速)"""
        best_mult = 1.0
        tile = self.world.get_tile(tile_id)
        if not tile or not tile.faction_id:
            return best_mult

        # V4.2: 使用索引直接查询
        for neighbor_id, r in self._road_index.get(tile_id, []):
            if r.is_degraded:
                continue
            road_mult = ROAD_CONFIG[r.road_type]["speed_mult"]
            if road_mult < best_mult:
                best_mult = road_mult

        return best_mult

    def get_supply_extension(self, tile_id: str) -> int:
        """获取地块的补给距离延伸（取最大道路加成）(V4.2: 使用索引加速)"""
        best_ext = 0
        tile = self.world.get_tile(tile_id)
        if not tile or not tile.faction_id:
            return best_ext

        for neighbor_id, r in self._road_index.get(tile_id, []):
            if r.is_degraded:
                continue
            ext = ROAD_CONFIG[r.road_type]["supply_extend"]
            if ext > best_ext:
                best_ext = ext

        return best_ext

    def get_road_between(self, tile_a_id: str, tile_b_id: str) -> Optional[RoadSegment]:
        """获取两地块间的道路段 (V4.2: 使用索引O(1)查询)"""
        for neighbor_id, r in self._road_index.get(tile_a_id, []):
            if neighbor_id == tile_b_id and not r.is_degraded:
                return r
        return None

    # ================================================================
    # 驿站管理
    # ================================================================
    def build_relay_station(self, faction_id: str, tile_id: str) -> dict:
        """在指定地块建造驿站"""
        faction = self.world.factions.get(faction_id)
        if not faction:
            return {"success": False, "reason": "势力不存在"}

        tile = self.world.get_tile(tile_id)
        if not tile or tile.faction_id != faction_id:
            return {"success": False, "reason": "地块不属于己方"}

        # 检查驿站间距
        for station in self._relay_stations.get(faction_id, []):
            st_tile = self.world.get_tile(station.tile_id)
            if st_tile:
                dq = abs(tile.q - st_tile.q)
                dr = abs(tile.r - st_tile.r)
                dist = max(dq, dr, dq + dr) // 2
                if dist < RELAY_CONFIG["min_spacing"]:
                    return {"success": False,
                            "reason": f"距离已有驿站仅{dist}格，最小间距{RELAY_CONFIG['min_spacing']}格"}

        # 检查是否有道路经过
        has_road = any(r.connects(tile_id) for r in self._roads.get(faction_id, []))
        if not has_road:
            return {"success": False, "reason": "地块无道路经过，无法建驿站"}

        cost = RELAY_CONFIG["build_cost"]
        if faction.treasury < cost:
            return {"success": False, "reason": f"国库不足，需要{cost}银两"}

        faction.treasury -= cost

        station_id = f"relay_{faction_id}_{tile_id}"
        station = PostalRelayStation(
            station_id=station_id, tile_id=tile_id, faction_id=faction_id,
        )
        self._relay_stations.setdefault(faction_id, []).append(station)

        logger.info(f"{faction.name} 在{tile.tile_name}建造驿站 (花费{cost}银两)")
        return {"success": True, "station_id": station_id, "cost": cost}

    def auto_deploy_relay_stations(self, faction_id: str) -> dict:
        """沿驿道自动部署驿站（每隔3-5格）"""
        faction = self.world.factions.get(faction_id)
        if not faction:
            return {"success": False, "reason": "势力不存在"}

        # 找到所有驿道路段
        postal_roads = [r for r in self._roads.get(faction_id, [])
                       if r.road_type == RoadType.POSTAL_ROAD and not r.is_degraded]

        if not postal_roads:
            return {"success": False, "reason": "没有驿道"}

        # 构建驿道路径
        from collections import defaultdict
        adj = defaultdict(list)
        for r in postal_roads:
            adj[r.tile_a].append(r.tile_b)
            adj[r.tile_b].append(r.tile_a)

        # BFS 从首都沿驿道遍历，每隔3-5格建驿站
        capital_tile = faction.capital_tile
        if not capital_tile:
            return {"success": False, "reason": "没有首都"}

        existing = {s.tile_id for s in self._relay_stations.get(faction_id, [])}
        built = 0

        visited = {capital_tile}
        queue = [(capital_tile, 0)]  # (tile_id, distance_from_last_station)

        while queue:
            current, dist = queue.pop(0)
            for neighbor in adj.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                new_dist = dist + 1

                if new_dist >= RELAY_CONFIG["min_spacing"] and neighbor not in existing:
                    # 建造驿站
                    result = self.build_relay_station(faction_id, neighbor)
                    if result["success"]:
                        built += 1
                        existing.add(neighbor)
                        new_dist = 0

                queue.append((neighbor, new_dist))

        return {"success": True, "stations_built": built}

    def get_relay_bonus_for_tile(self, tile_id: str) -> dict:
        """获取地块受驿站影响的加成"""
        bonus = {"supply_extension": 0, "messenger_speed": 0.0, "morale_recovery": 0}
        tile = self.world.get_tile(tile_id)
        if not tile or not tile.faction_id:
            return bonus

        for station in self._relay_stations.get(tile.faction_id, []):
            st_tile = self.world.get_tile(station.tile_id)
            if not st_tile:
                continue
            dq = abs(tile.q - st_tile.q)
            dr = abs(tile.r - st_tile.r)
            dist = max(dq, dr, dq + dr) // 2
            if dist <= station.supply_radius_bonus:
                bonus["supply_extension"] = max(bonus["supply_extension"], 1)
                bonus["messenger_speed"] = max(bonus["messenger_speed"],
                                              station.messenger_speed_bonus)
                bonus["morale_recovery"] = max(bonus["morale_recovery"],
                                              station.morale_recovery)

        return bonus

    # ================================================================
    # 道路维护
    # ================================================================
    def calc_road_upkeep(self, faction_id: str) -> dict:
        """计算势力道路/驿站维护费"""
        total = 0
        road_count = 0
        relay_count = 0

        for r in self._roads.get(faction_id, []):
            if r.is_degraded or r.road_type == RoadType.DIRT_PATH:
                continue
            upkeep = ROAD_CONFIG[r.road_type]["upkeep"]
            total += upkeep
            road_count += 1

        for s in self._relay_stations.get(faction_id, []):
            total += s.upkeep
            relay_count += 1

        return {
            "road_upkeep": total,
            "road_segments": road_count,
            "relay_stations": relay_count,
        }

    def degrade_enemy_roads(self, tile_id: str, new_owner_id: str):
        """地块易主时降级该地块连接的道路（被敌军占领）"""
        old_owners = set()
        for fid, roads in self._roads.items():
            for r in roads:
                if r.connects(tile_id) and fid != new_owner_id:
                    r.is_degraded = True
                    old_owners.add(fid)

        for fid in old_owners:
            logger.debug(f"势力{fid}在{tile_id}的道路已被敌军降级")

    # ================================================================
    # 查询接口
    # ================================================================
    def get_faction_road_network(self, faction_id: str) -> dict:
        """获取势力道路网络概况"""
        roads = self._roads.get(faction_id, [])
        relay = self._relay_stations.get(faction_id, [])

        road_by_type = {}
        for r in roads:
            t = r.road_type.value
            road_by_type[t] = road_by_type.get(t, 0) + 1

        return {
            "total_segments": len(roads),
            "by_type": road_by_type,
            "relay_stations": len(relay),
            "total_upkeep": self.calc_road_upkeep(faction_id)["road_upkeep"],
        }

    def get_all_roads(self) -> dict[str, list[dict]]:
        """获取全部势力的道路数据（用于API序列化）"""
        result = {}
        for fid, roads in self._roads.items():
            result[fid] = [{
                "road_id": r.road_id,
                "type": r.road_type.value,
                "tile_a": r.tile_a,
                "tile_b": r.tile_b,
                "degraded": r.is_degraded,
            } for r in roads]
        return result


__all__ = ["RoadSystem", "RoadType", "RoadSegment", "PostalRelayStation"]
