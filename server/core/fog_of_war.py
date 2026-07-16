"""
战争迷雾系统 - 势力独立可见性计算

职责:
- 常亮区域：己方领土永远可见
- 哨探区域：烽燧(beacon)周围 N 格可见（N = beacon level × 2）
- 部队视野：己方部队所在地块 + 周围 1 格可见
- 间谍视野：敌方有己方间谍的地块可见
- 盟友共享：同盟势力的领土可见（由 visibility_share 标志控制）
- 迷雾衰减：非己方领土每回合衰减 1 级可见度

可见度等级:
    VISIBLE(3) — 部队数量和建筑
    DIM(2)     — 地形和势力归属
    FOGGY(1)   — 仅地形
    HIDDEN(0)  — 完全不可见
"""
from __future__ import annotations
from enum import IntEnum
from typing import Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("yuanmo.fog")


# ================================================================
# 可见度枚举
# ================================================================
class VisibilityLevel(IntEnum):
    HIDDEN = 0   # 完全不可见
    FOGGY = 1    # 仅地形
    DIM = 2      # 地形 + 势力归属
    VISIBLE = 3  # 全部信息


# ================================================================
# 单个地块迷雾数据
# ================================================================
@dataclass
class FogTileRecord:
    """单个地块在迷雾中的记忆快照（可能与实际不同）"""
    visibility: VisibilityLevel = VisibilityLevel.HIDDEN
    last_seen_round: int = -1
    last_seen_owner: str = ""
    last_seen_troops: int = 0
    last_seen_buildings: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "visibility": int(self.visibility),
            "last_seen_round": self.last_seen_round,
            "last_seen_owner": self.last_seen_owner,
            "last_seen_troops": self.last_seen_troops,
            "last_seen_buildings": dict(self.last_seen_buildings),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FogTileRecord":
        return cls(
            visibility=VisibilityLevel(data.get("visibility", 0)),
            last_seen_round=data.get("last_seen_round", -1),
            last_seen_owner=data.get("last_seen_owner", ""),
            last_seen_troops=data.get("last_seen_troops", 0),
            last_seen_buildings=dict(data.get("last_seen_buildings", {})),
        )


# 六边形邻居偏移
_HEX_NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# ================================================================
# FogOfWarEngine 主类
# ================================================================
class FogOfWarEngine:
    """战争迷雾引擎 - 每势力独立计算可见性"""

    def __init__(self, world, game_const: dict = None):
        self.world = world
        self.const = game_const or {}
        self._fog_layers: dict[str, dict[str, FogTileRecord]] = {}
        # 烽燧参数
        bld_cfg = self.const.get("building", {})
        beacon_cfg = bld_cfg.get("beacon", {})
        self._beacon_vision: int = beacon_cfg.get("vision_range_per_level", 2)
        self._troop_vision: int = 1

    # ================================================================
    # 可见性计算
    # ================================================================
    def calculate_visibility(self, faction_id: str) -> dict[str, FogTileRecord]:
        """为指定势力完整刷新可见性"""
        faction = self.world.factions.get(faction_id)
        if not faction or not faction.is_alive:
            return {}

        fog = self._fog_layers.setdefault(faction_id, {})

        # 获取所有地块
        coord_tiles = {}
        for t in self.world.tiles.values():
            coord_tiles[(t.q, t.r)] = t

        # 新建可见度表（从HIDDEN开始）
        new_visibility: dict[str, int] = {}

        # --- 源1：己方领土常亮 ---
        for tile in self.world.tiles.values():
            if tile.faction_id == faction_id:
                new_visibility[tile.tile_id] = VisibilityLevel.VISIBLE

        # --- 源2：烽燧哨探区域 ---
        self._apply_beacon_vision(faction_id, new_visibility, coord_tiles)

        # --- 源3：部队视野 ---
        self._apply_troop_vision(faction_id, new_visibility, coord_tiles)

        # --- 源4：间谍视野 ---
        self._apply_spy_vision(faction_id, new_visibility)

        # --- 源5：盟友共享 ---
        self._apply_ally_vision(faction_id, new_visibility)

        # 生成 FogTileRecord 并保留旧记忆
        current_round = self.world.current_round
        for tile_id, vis_level in new_visibility.items():
            tile = self.world.get_tile(tile_id)
            if tile:
                fog[tile_id] = FogTileRecord(
                    visibility=VisibilityLevel(vis_level),
                    last_seen_round=current_round,
                    last_seen_owner=tile.faction_id or "",
                    last_seen_troops=tile.troops if vis_level == VisibilityLevel.VISIBLE else 0,
                    last_seen_buildings=(dict(getattr(tile, 'buildings', {}) or {})
                                        if vis_level == VisibilityLevel.VISIBLE else {}),
                )
            else:
                fog[tile_id] = FogTileRecord(
                    visibility=VisibilityLevel(vis_level),
                    last_seen_round=current_round,
                )

        return fog

    def _apply_beacon_vision(self, faction_id: str, visibility: dict,
                             coord_tiles: dict):
        """烽燧哨探：beacon周围 N 格可见"""
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            buildings = getattr(tile, 'buildings', {}) or {}
            beacon_level = buildings.get("beacon", 0)
            if beacon_level <= 0:
                continue
            vision_range = beacon_level * self._beacon_vision

            # BFS 扩展可见范围
            visited = {tile.tile_id}
            queue = [(tile.q, tile.r, 0)]
            while queue:
                q, r, dist = queue.pop(0)
                if dist >= vision_range:
                    continue
                for dq, dr in _HEX_NEIGHBORS:
                    nq, nr = q + dq, r + dr
                    nb = coord_tiles.get((nq, nr))
                    if nb and nb.tile_id not in visited:
                        visited.add(nb.tile_id)
                        queue.append((nq, nr, dist + 1))
                        # 烽燧提供 DIM 级别可见度
                        visibility[nb.tile_id] = max(
                            visibility.get(nb.tile_id, 0),
                            VisibilityLevel.DIM,
                        )

    def _apply_troop_vision(self, faction_id: str, visibility: dict,
                            coord_tiles: dict):
        """部队视野：己方部队所在地块 + 周围 1 格"""
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id or tile.troops <= 0:
                continue
            # 部队所在地块完全可见
            visibility[tile.tile_id] = VisibilityLevel.VISIBLE

            # 周围1格 VISIBLE
            for dq, dr in _HEX_NEIGHBORS:
                nb = coord_tiles.get((tile.q + dq, tile.r + dr))
                if nb:
                    visibility[nb.tile_id] = max(
                        visibility.get(nb.tile_id, 0),
                        VisibilityLevel.VISIBLE,
                    )

    def _apply_spy_vision(self, faction_id: str, visibility: dict):
        """间谍视野：敌方有己方间谍的地块可见"""
        for other_fid, other in self.world.factions.items():
            if other_fid == faction_id:
                continue
            spy_network = getattr(other, 'spy_network', {}) or {}
            # 检查己方间谍在对方领土中的位置
            # spy_network 结构: {faction_id: {tile_id: SpyInfo}}
            for target_fid, spies in spy_network.items():
                if target_fid != faction_id:
                    continue
                for tile_id in spies:
                    visibility[tile_id] = max(
                        visibility.get(tile_id, 0),
                        VisibilityLevel.DIM,
                    )

    def _apply_ally_vision(self, faction_id: str, visibility: dict):
        """盟友共享：同盟势力领土可见 (V4.2: 提前退出+批量处理)"""
        faction = self.world.factions.get(faction_id)
        if not faction:
            return

        # V4.2: 预筛选盟友列表
        allies = [
            other_id for other_id, other in self.world.factions.items()
            if other_id != faction_id and other.is_alive
            and faction.diplomatic_stances.get(other_id)
            and faction.diplomatic_stances[other_id].value == "alliance"
        ]
        if not allies:
            return  # 无盟友，直接退出

        allies_set = set(allies)
        for tile in self.world.tiles.values():
            if tile.faction_id in allies_set:
                visibility[tile.tile_id] = max(
                    visibility.get(tile.tile_id, 0),
                    VisibilityLevel.DIM,
                )

    # ================================================================
    # 迷雾衰减
    # ================================================================
    def decay_fog(self, faction_id: str):
        """回合结束时衰减该势力迷雾"""
        fog = self._fog_layers.get(faction_id, {})
        for tile_id, record in list(fog.items()):
            tile = self.world.get_tile(tile_id)
            if tile and tile.faction_id == faction_id:
                continue  # 己方领土不衰减
            if record.visibility > VisibilityLevel.HIDDEN:
                record.visibility = VisibilityLevel(int(record.visibility) - 1)

    def update_on_round_end(self):
        """所有势力迷雾衰减 (V4.2: 批量处理)"""
        for fid, faction in self.world.factions.items():
            if faction.is_alive:
                self.decay_fog(fid)

    # ================================================================
    # 查询接口
    # ================================================================
    def get_tile_visibility(self, faction_id: str,
                            tile_id: str) -> VisibilityLevel:
        """获取势力对某地块的可见度"""
        fog = self._fog_layers.get(faction_id, {})
        record = fog.get(tile_id)
        if record:
            return record.visibility
        # 如果不在迷雾记录中，检查是否己方领土
        tile = self.world.get_tile(tile_id)
        if tile and tile.faction_id == faction_id:
            return VisibilityLevel.VISIBLE
        return VisibilityLevel.HIDDEN

    def is_tile_visible(self, faction_id: str, tile_id: str) -> bool:
        """地块是否对该势力可见（至少 FOGGY）"""
        return self.get_tile_visibility(faction_id, tile_id) >= VisibilityLevel.FOGGY

    def get_visible_enemy_troops(self, faction_id: str) -> list[dict]:
        """获取该势力能看到的所有敌军信息"""
        fog = self._fog_layers.get(faction_id, {})
        enemy_troops = []
        for tile_id, record in fog.items():
            if record.visibility < VisibilityLevel.DIM:
                continue
            if record.last_seen_owner and record.last_seen_owner != faction_id:
                tile = self.world.get_tile(tile_id)
                actual_owner = tile.faction_id if tile else ""
                enemy_troops.append({
                    "tile_id": tile_id,
                    "tile_name": tile.tile_name if tile else "?",
                    "owner": actual_owner or record.last_seen_owner,
                    "troops": tile.troops if (tile and record.visibility >= VisibilityLevel.VISIBLE)
                              else record.last_seen_troops,
                    "is_stale": record.last_seen_round < self.world.current_round,
                    "visibility_level": int(record.visibility),
                })
        return enemy_troops

    def get_fog_map(self, faction_id: str) -> dict[str, dict]:
        """获取势力完整迷雾地图（用于API序列化）"""
        fog = self._fog_layers.get(faction_id, {})
        # 确保己方领土都在
        for tile in self.world.tiles.values():
            if tile.faction_id == faction_id:
                fog[tile.tile_id] = FogTileRecord(
                    visibility=VisibilityLevel.VISIBLE,
                    last_seen_round=self.world.current_round,
                )

        return {tid: rec.to_dict() for tid, rec in fog.items()}

    def get_visibility_summary(self, faction_id: str) -> dict:
        """获取势力能见度摘要"""
        fog = self._fog_layers.get(faction_id, {})
        total_tiles = len(self.world.tiles)
        visible = sum(1 for r in fog.values() if r.visibility == VisibilityLevel.VISIBLE)
        dim = sum(1 for r in fog.values() if r.visibility == VisibilityLevel.DIM)
        foggy = sum(1 for r in fog.values() if r.visibility == VisibilityLevel.FOGGY)
        hidden = total_tiles - visible - dim - foggy

        return {
            "total_tiles": total_tiles,
            "visible": visible,
            "dim": dim,
            "foggy": foggy,
            "hidden": hidden,
            "visibility_pct": round(visible / max(1, total_tiles) * 100, 1),
        }


__all__ = ["FogOfWarEngine", "VisibilityLevel", "FogTileRecord"]
