"""
经济引擎 - Faucet-Sink 货币流、人口结构、渐进税制、贸易深化、粮仓赈灾

职责:
- Faucet-Sink 货币流架构：计算净流量 = 总收入 - 总支出
- 人口结构系统：farmers/artisans/merchants/soldiers 职业分布与自动转换
- 渐进税制：基础税率 + 民心修正 + 发展度修正
- 贸易系统深化：商品类型、贸易路线收益、势力特产
- 粮仓与赈灾：饥荒判定、赈灾消耗、移民迁出
- 经济健康指标：Gini系数、收入依赖度、经济趋势

基于 game-economy-designer + game-balance-check skill 指导设计
"""
from __future__ import annotations
import math
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    DiplomaticStance, Season, BuildingType, PolicyType,
)
from server.core.building_config import BUILDING_CONFIG

logger = logging.getLogger("yuanmo.economy")


# ================================================================
# 贸易商品枚举
# ================================================================
class TradeGood(str, Enum):
    """贸易商品类型"""
    GRAIN = "grain"
    SILK = "silk"
    TEA = "tea"
    PORCELAIN = "porcelain"
    SALT_IRON = "salt_iron"
    WARHORSES = "warhorses"


# 商品基础价格表（银两/单位）
TRADE_GOOD_PRICES: dict[TradeGood, int] = {
    TradeGood.GRAIN: 20, TradeGood.SILK: 80, TradeGood.TEA: 50,
    TradeGood.PORCELAIN: 70, TradeGood.SALT_IRON: 90, TradeGood.WARHORSES: 120,
}

# 势力特产映射（faction_id → [TradeGood, ...]）
FACTION_SPECIALTY: dict[str, list[TradeGood]] = {
    "faction_yuan": [TradeGood.WARHORSES, TradeGood.SILK],
    "faction_wangbaobao": [TradeGood.WARHORSES],
    "faction_mobei": [TradeGood.WARHORSES],
    "faction_chenyouliang": [TradeGood.GRAIN, TradeGood.SALT_IRON],
    "faction_fangguozhen": [TradeGood.SILK, TradeGood.TEA],
    "faction_zhangshicheng": [TradeGood.SILK, TradeGood.GRAIN],
    "faction_zhuyuanzhang": [TradeGood.GRAIN, TradeGood.TEA],
    "faction_xushouhui": [TradeGood.GRAIN, TradeGood.SALT_IRON],
    "faction_mingyuzhen": [TradeGood.SALT_IRON, TradeGood.TEA],
}


# ================================================================
# 人口结构数据类
# ================================================================
@dataclass
class PopulationStructure:
    """地块人口职业分布"""
    farmers: int = 0
    artisans: int = 0
    merchants: int = 0
    soldiers: int = 0

    @property
    def total(self) -> int:
        return self.farmers + self.artisans + self.merchants + self.soldiers

    @classmethod
    def from_total(cls, total: int, ratios: dict = None) -> "PopulationStructure":
        """从总人口按比例创建（默认从 game_const.yaml civil 节读取）"""
        r = ratios or {}
        return cls(
            farmers=int(total * r.get("pop_farmer_ratio", 0.60)),
            artisans=int(total * r.get("pop_artisan_ratio", 0.15)),
            merchants=int(total * r.get("pop_merchant_ratio", 0.10)),
            soldiers=int(total * r.get("pop_soldier_ratio", 0.15)),
        )

    def to_dict(self) -> dict:
        return {
            "farmers": self.farmers, "artisans": self.artisans,
            "merchants": self.merchants, "soldiers": self.soldiers,
            "total": self.total,
        }


# ================================================================
# EconomyEngine 主类
# ================================================================
class EconomyEngine:
    """经济引擎 - 集中管理所有经济逻辑

    与 SettleEngine 接口兼容，可通过委托方式集成。
    """

    DEFAULTS = {
        "base_population_growth": 0.02, "base_tax_rate": 0.15,
        "refugee_threshold_morale": 30, "famine_threshold_grain": 150,
        "relief_cost_per_pop": 5, "migration_cost_per_pop": 2,
        "trade_route_income": 100, "trade_route_maintenance": 30,
        "port_income_base": 150, "granary_capacity_per_level": 500,
        "water_works_effect": 0.15, "clinic_plague_reduction": 0.3,
    }

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**self.DEFAULTS, **(game_const or {})}
        # 缓存人口结构: faction_id → tile_id → PopulationStructure
        self._pop_structure: dict[str, dict[str, PopulationStructure]] = {}
        # 贸易路线缓存
        self._trade_routes: dict[str, list[dict]] = {}
        self._init_population_structures()

    # ================================================================
    # 初始化
    # ================================================================
    def _init_population_structures(self):
        """初始化所有地块的人口结构"""
        for faction in self.world.factions.values():
            if not faction.is_alive:
                continue
            fid = faction.faction_id
            self._pop_structure[fid] = {}
            for tile in self.world.tiles.values():
                if tile.faction_id != fid or tile.population <= 0:
                    continue
                self._pop_structure[fid][tile.tile_id] = PopulationStructure.from_total(tile.population, self.const)

    def get_pop_structure(self, tile_id: str) -> Optional[PopulationStructure]:
        """获取地块人口结构"""
        tile = self.world.get_tile(tile_id)
        if not tile or not tile.faction_id:
            return None
        fid = tile.faction_id
        if fid not in self._pop_structure:
            self._pop_structure[fid] = {}
        if tile_id not in self._pop_structure[fid]:
            self._pop_structure[fid][tile_id] = PopulationStructure.from_total(tile.population, self.const)
        return self._pop_structure[fid][tile_id]

    # ================================================================
    # 1. Faucet - 税收计算（渐进税制）
    # ================================================================
    def calc_tax(self, faction_id: str, tile: TileState = None,
                 season: Season = Season.SPRING) -> dict:
        """计算渐进税收

        Faucet公式: 税收 = 人口 × 税率 × 地块系数 × 四季修正 × 民心修正 × 发展度修正

        渐进特征:
        - 民心 < 30: 税率自动打7折（抗税）
        - 民心 > 70: 税收 +10%（踊跃纳粮）
        - 发展度每级提供 +5% 税收加成
        """
        if tile is None:
            return {"tax_income": 0, "breakdown": "无地块"}

        base_rate = self.const.get("base_tax_rate", 0.15)
        pop = tile.population

        # 地块类型系数
        tile_mult = self._get_tile_tax_mult(tile.tile_type)

        # 四季修正
        season_mult = self._get_season_tax_mult(season, self.const)

        # 民心修正（渐进，阈值与倍率从 game_const.yaml 读取）
        morale = getattr(tile, 'morale', 50)
        low_threshold = self.const.get("morale_tax_low", 30)
        high_threshold = self.const.get("morale_tax_high", 70)
        if morale < low_threshold:
            morale_mult = self.const.get("morale_tax_low_mult", 0.7)
        elif morale > high_threshold:
            morale_mult = self.const.get("morale_tax_high_mult", 1.1)
        else:
            morale_mult = 1.0

        # 发展度修正
        dev_level = getattr(tile, 'development_level', 1)
        dev_mult = 1.0 + (dev_level - 1) * 0.05

        # 是否有农田建筑
        building_bonus = self._get_building_tax_bonus(tile)

        tax_income = int(pop * base_rate * tile_mult * season_mult *
                        morale_mult * dev_mult * building_bonus)

        return {
            "tax_income": tax_income,
            "base_rate": base_rate,
            "tile_mult": tile_mult,
            "season_mult": season_mult,
            "morale_mult": morale_mult,
            "dev_mult": dev_mult,
            "breakdown": (f"人口{pop}×税率{base_rate:.0%}×地块{tile_mult:.1f}"
                         f"×季节{season_mult:.1f}×民心{morale_mult:.1f}"
                         f"×发展{dev_mult:.1f}={tax_income}银两"),
        }

    @staticmethod
    def _get_tile_tax_mult(tile_type) -> float:
        """地块税收系数"""
        mapping = {
            TileType.CITY: 1.5, TileType.PORT: 1.3,
            TileType.FARMLAND: 1.0, TileType.GRASSLAND: 0.8,
            TileType.HILL: 0.6, TileType.MOUNTAIN: 0.3,
            TileType.WETLAND: 0.4, TileType.DESERT: 0.2,
            TileType.COASTAL: 0.7, TileType.FOREST: 0.5,
            TileType.TUNDRA_FOREST: 0.3, TileType.OASIS: 0.9,
        }
        return mapping.get(tile_type, 0.5)

    @staticmethod
    def _get_season_tax_mult(season: Season, const: dict = None) -> float:
        """四季税收修正（从 game_const.yaml 读取）"""
        c = const or {}
        mapping = {
            Season.SPRING: c.get("season_tax_spring", 0.9),
            Season.SUMMER: c.get("season_tax_summer", 1.0),
            Season.AUTUMN: c.get("season_tax_autumn", 1.3),
            Season.WINTER: c.get("season_tax_winter", 0.7),
        }
        return mapping.get(season, 1.0)

    @staticmethod
    def _get_building_tax_bonus(tile: TileState) -> float:
        """建筑税收加成"""
        bonus = 1.0
        buildings = getattr(tile, 'buildings', {})
        if not buildings:
            return bonus
        if BuildingType.WORKSHOP.value in buildings:
            bonus += buildings[BuildingType.WORKSHOP.value] * 0.05
        if BuildingType.DOCK.value in buildings:
            bonus += buildings[BuildingType.DOCK.value] * 0.08
        return bonus

    # ================================================================
    # 2. Faucet - 贸易收入
    # ================================================================
    def calc_trade_income(self, faction_id: str) -> dict:
        """计算势力贸易总收入

        贸易路线收益 = 基础收入 × 距离系数 × 关系系数 × 特产加成 × 道路加成
        """
        faction = self.world.factions.get(faction_id)
        if not faction or not faction.is_alive:
            return {"trade_income": 0, "routes": []}

        base_income = self.const.get("trade_route_income", 100)
        total_income = 0
        routes_detail = []

        # 遍历外交关系找贸易伙伴
        for other_id, other in self.world.factions.items():
            if other_id == faction_id or not other.is_alive:
                continue
            stance = faction.diplomatic_stances.get(other_id, DiplomaticStance.NEUTRAL)
            if stance in (DiplomaticStance.WAR, DiplomaticStance.HOSTILE):
                continue
            if not getattr(faction, 'trade_partners', None):
                continue
            if other_id not in getattr(faction, 'trade_partners', []):
                continue

            # 距离系数
            distance = self._calc_faction_distance(faction_id, other_id)
            dist_mult = max(0.3, 1.0 - distance * 0.03)

            # 关系系数
            relation = faction.diplomatic_relations.get(other_id, 0)
            rel_mult = 0.5 + (relation + 100) / 400  # -100→0.25, 0→0.75, 100→1.0

            # 特产加成
            specialty_mult = self._calc_specialty_bonus(faction_id, other_id)

            # 道路加成
            road_mult = self._calc_trade_road_bonus(faction_id, other_id)

            route_income = int(base_income * dist_mult * rel_mult * specialty_mult * road_mult)
            total_income += route_income

            routes_detail.append({
                "partner": other.name,
                "income": route_income,
                "distance": distance,
                "breakdown": (f"基础{base_income}×距离{dist_mult:.2f}×关系{rel_mult:.2f}"
                             f"×特产{specialty_mult:.2f}×道路{road_mult:.2f}={route_income}"),
            })

        # 港口收入加成
        port_bonus = self._calc_port_bonus(faction_id)
        total_income += port_bonus

        return {
            "trade_income": total_income,
            "port_bonus": port_bonus,
            "routes": routes_detail,
        }

    def _calc_faction_distance(self, fid1: str, fid2: str) -> int:
        """计算两势力中心距离（取首都/最大城市距离）"""
        tiles1 = [t for t in self.world.tiles.values() if t.faction_id == fid1]
        tiles2 = [t for t in self.world.tiles.values() if t.faction_id == fid2]
        min_dist = 99
        for t1 in tiles1:
            for t2 in tiles2:
                dq = abs(t1.q - t2.q)
                dr = abs(t1.r - t2.r)
                dist = max(dq, dr, dq + dr) // 2
                if dist < min_dist:
                    min_dist = dist
        return min_dist if min_dist < 99 else 10

    def _calc_specialty_bonus(self, fid1: str, fid2: str) -> float:
        """特产互补加成：特产不同 → 加成1.3x"""
        specs1 = set(g.value for g in FACTION_SPECIALTY.get(fid1, []))
        specs2 = set(g.value for g in FACTION_SPECIALTY.get(fid2, []))
        overlap = specs1 & specs2
        unique = specs1 | specs2
        if not unique:
            return 1.0
        return 1.0 + 0.15 * (len(unique) - len(overlap))

    def _calc_trade_road_bonus(self, fid1: str, fid2: str) -> float:
        """道路贸易加成（如果有道路连接则加成）"""
        # 简化：检查两势力是否有相邻地块且有道路
        bonus = 1.0
        world_roads = getattr(self.world, 'road_network', None)
        if world_roads is None:
            return bonus
        connected = False
        for seg in world_roads.get(fid1, []):
            # 检查道路是否延伸至对方领土方向
            if seg.get('connects_to_faction') == fid2:
                connected = True
                break
        return 1.25 if connected else 1.0

    def _calc_port_bonus(self, faction_id: str) -> int:
        """港口贸易收入"""
        port_income = self.const.get("port_income_base", 150)
        total = 0
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            if tile.tile_type == TileType.PORT:
                dock_level = (tile.buildings or {}).get(BuildingType.DOCK.value, 0)
                total += port_income * (1 + dock_level * 0.25)
        return total

    # ================================================================
    # 3. Sink - 军费（部队维持）
    # ================================================================
    def calc_military_upkeep(self, faction_id: str) -> dict:
        """计算势力军费（Sink）

        军费 = 总兵力 × 每兵维持费 × 季节修正
        """
        total_troops = 0
        total_upkeep = 0
        tile_details = []
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id or tile.troops <= 0:
                continue
            upkeep = tile.troops * 0.8  # 每兵0.8银两/回合（v4.1: 原1.0）
            total_troops += tile.troops
            total_upkeep += upkeep
            tile_details.append({
                "tile_id": tile.tile_id,
                "tile_name": tile.tile_name,
                "troops": tile.troops,
                "upkeep": upkeep,
            })

        # 季节修正（冬季取暖额外消耗，v4.1: 原1.3）
        season_mult = 1.25 if self.world.current_season == Season.WINTER else 1.0
        military_upkeep = int(total_upkeep * season_mult)

        return {
            "military_upkeep": military_upkeep,
            "total_troops": total_troops,
            "details": tile_details,
        }

    # ================================================================
    # 4. Sink - 建筑维护
    # ================================================================
    def calc_building_upkeep(self, faction_id: str) -> dict:
        """计算建筑维护费（Sink）

        使用 BUILDING_CONFIG 权威 upkeep 值，与 settle_engine 保持一致。
        """
        total = 0
        details = []
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            buildings = getattr(tile, 'buildings', {}) or {}
            for bld_type, level in buildings.items():
                bld_cfg = BUILDING_CONFIG.get(bld_type, {})
                rate = bld_cfg.get("upkeep", 20) if isinstance(bld_cfg, dict) else 20
                cost = level * rate
                total += cost
                details.append({
                    "tile": tile.tile_name,
                    "building": bld_type,
                    "level": level,
                    "upkeep": cost,
                })
        return {"building_upkeep": total, "details": details}

    # ================================================================
    # 5. 粮草计算（人口消耗 + 部队消耗）
    # ================================================================
    def calc_grain_consumption(self, faction_id: str) -> dict:
        """计算势力粮草总消耗（v4.3.1: 对齐 SettleEngine 权威公式）

        粮耗 = 人口消耗(每千人5石) + 部队消耗(每兵0.05石) + 季节修正
        """
        pop_grain = 0
        troop_grain = 0
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            pop_grain += int(tile.population * 0.005)
            troop_grain += int(tile.troops * 0.05)

        # 季节修正（对齐 SettleEngine._calc_grain_consumption）
        season_mult = 1.0
        if self.world.current_season == Season.WINTER:
            season_mult = 1.4   # 冬季取暖耗粮大增
        elif self.world.current_season == Season.SUMMER:
            season_mult = 1.1   # 夏季行军耗粮略增
        elif self.world.current_season == Season.SPRING:
            season_mult = 0.85  # 春季野菜补充，耗粮减少

        total_grain = int((pop_grain + troop_grain) * season_mult)

        return {
            "grain_consumed": total_grain,
            "pop_grain": pop_grain,
            "troop_grain": troop_grain,
            "season_mult": season_mult,
        }

    # ================================================================
    # 6. 人口增长
    # ================================================================
    def calc_population_growth(self, faction_id: str) -> dict:
        """计算势力人口增长

        增长率 = 基础增长率 + 建筑加成 + 四季修正 - 灾害惩罚 + 发展度加成
        """
        base_rate = self.const.get("base_population_growth", 0.02)
        total_growth = 0
        tile_changes = []

        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id or tile.population <= 0:
                continue

            # 建筑加成
            bld_bonus = 0.0
            buildings = getattr(tile, 'buildings', {}) or {}
            if BuildingType.FARMLAND.value in buildings:
                bld_bonus += buildings[BuildingType.FARMLAND.value] * 0.005
            if BuildingType.CLINIC.value in buildings:
                bld_bonus += buildings[BuildingType.CLINIC.value] * 0.003

            # 四季修正
            season = self.world.current_season
            season_bonus = 0.0
            if season == Season.SPRING:
                season_bonus = 0.01
            elif season == Season.WINTER:
                season_bonus = -0.005

            # 地块类型修正
            tile_bonus = 0.0
            if tile.tile_type in (TileType.CITY, TileType.FARMLAND, TileType.GRASSLAND):
                tile_bonus = 0.005
            elif tile.tile_type in (TileType.DESERT, TileType.MOUNTAIN):
                tile_bonus = -0.005

            # 发展度修正
            dev_level = getattr(tile, 'development_level', 1)
            dev_bonus = (dev_level - 1) * 0.002

            # 饥荒惩罚（绝对值判定，与 settle_engine 一致）
            famine_penalty = 0.0
            famine_threshold = self.const.get("famine_threshold_grain", 150)
            if tile.grain <= famine_threshold:
                famine_penalty = -0.03  # 饥荒大幅减少人口

            total_rate = base_rate + bld_bonus + season_bonus + tile_bonus + dev_bonus + famine_penalty
            total_rate = max(-0.05, min(0.08, total_rate))  # 限制在 -5% ~ +8%

            growth = int(tile.population * total_rate)
            total_growth += growth

            if growth != 0:
                tile_changes.append({
                    "tile": tile.tile_name,
                    "pop_before": tile.population,
                    "growth": growth,
                    "rate": round(total_rate, 4),
                })

        return {
            "total_growth": total_growth,
            "growth_rate": round(base_rate, 4),
            "tile_changes": tile_changes,
        }

    # ================================================================
    # 7. 粮仓与赈灾
    # ================================================================
    def check_famine(self, faction_id: str) -> list[dict]:
        """检查势力内的饥荒地块

        饥荒判定: 地块粮草 ≤ famine_threshold_grain（与 SettleEngine 一致，用绝对值）
        """
        threshold = self.const.get("famine_threshold_grain", 150)
        famine_tiles = []
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id or tile.population <= 0:
                continue
            if tile.grain <= threshold:
                famine_tiles.append({
                    "tile_id": tile.tile_id,
                    "tile_name": tile.tile_name,
                    "population": tile.population,
                    "grain": tile.grain,
                    "grain_per_pop": round(tile.grain / max(1, tile.population), 1),
                    "severity": "severe" if tile.grain <= threshold * 0.5 else "moderate",
                })
        return famine_tiles

    def calc_relief_cost(self, tile_id: str, relief_ratio: float = 1.0) -> dict:
        """计算赈灾成本

        银两消耗 = 人口 × relief_cost_per_pop × relief_ratio
        效果：降低饥荒影响，恢复民心
        """
        tile = self.world.get_tile(tile_id)
        if not tile:
            return {"cost": 0, "effect": "无效地块"}

        cost_per_pop = self.const.get("relief_cost_per_pop", 5)
        cost = int(tile.population * cost_per_pop * relief_ratio)
        morale_gain = int(5 + tile.population / 500)

        return {
            "cost": cost,
            "morale_gain": morale_gain,
            "population_helped": int(tile.population * relief_ratio),
            "effect": f"消耗{cost}银两，恢复{morale_gain}民心",
        }

    def calc_granary_capacity(self, tile_id: str) -> int:
        """计算粮仓容量"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return 0
        buildings = getattr(tile, 'buildings', {}) or {}
        granary_level = buildings.get(BuildingType.GRANARY.value, 0)
        return granary_level * self.const.get("granary_capacity_per_level", 500)

    # ================================================================
    # 8. 移民系统
    # ================================================================
    def calc_migration_cost(self, from_tile_id: str, to_tile_id: str,
                            pop_amount: int) -> dict:
        """计算移民成本"""
        cost_per_pop = self.const.get("migration_cost_per_pop", 2)
        from_tile = self.world.get_tile(from_tile_id)
        to_tile = self.world.get_tile(to_tile_id)

        if not from_tile or not to_tile:
            return {"success": False, "reason": "地块不存在"}

        if to_tile.faction_id != from_tile.faction_id:
            return {"success": False, "reason": "目标地块不属于己方"}

        if from_tile.population < pop_amount:
            return {"success": False, "reason": "人口不足"}

        # 距离系数
        dq = abs(from_tile.q - to_tile.q)
        dr = abs(from_tile.r - to_tile.r)
        distance = max(dq, dr, dq + dr) // 2
        distance_mult = 1.0 + distance * 0.1

        cost = int(pop_amount * cost_per_pop * distance_mult)

        return {
            "success": True,
            "cost": cost,
            "distance": distance,
            "pop_amount": pop_amount,
            "receive_morale_boost": min(10, pop_amount // 100),
        }

    # ================================================================
    # 9. 经济健康指标（基于 game-balance-check skill）
    # ================================================================
    def calc_economy_health(self) -> dict:
        """计算全局经济健康指标

        指标:
        - Gini系数：势力间财富不均度
        - 收入依赖度：单一收入来源占比
        - 国库趋势：整体增长/衰减
        """
        factions_data = []
        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue
            tax = self._calc_total_tax(fid)
            trade = self.calc_trade_income(fid)["trade_income"]
            upkeep = (self.calc_military_upkeep(fid)["military_upkeep"] +
                     self.calc_building_upkeep(fid)["building_upkeep"])

            total_income = tax + trade
            total_expense = upkeep
            net = total_income - total_expense

            factions_data.append({
                "faction_id": fid,
                "name": faction.name,
                "treasury": faction.treasury,
                "tax_income": tax,
                "trade_income": trade,
                "total_income": total_income,
                "total_expense": total_expense,
                "net_flow": net,
                "population": faction.total_population,
                "tiles": len(self.world.get_faction_tiles(fid)),
            })

        # Gini系数计算（简化版，基于国库财富分布）
        gini = self._calc_gini(factions_data)

        # 收入依赖度检查
        dependency_risks = []
        for fd in factions_data:
            if fd["total_income"] <= 0:
                continue
            tax_ratio = fd["tax_income"] / fd["total_income"]
            trade_ratio = fd["trade_income"] / fd["total_income"]
            if tax_ratio > 0.8:
                dependency_risks.append(f"{fd['name']}: 过度依赖税收({tax_ratio:.0%})")
            if trade_ratio > 0.6:
                dependency_risks.append(f"{fd['name']}: 过度依赖贸易({trade_ratio:.0%})")

        # 净流量趋势
        total_net = sum(fd["net_flow"] for fd in factions_data)
        trend = "增长" if total_net > 0 else "萎缩"

        return {
            "gini_coefficient": round(gini, 3),
            "gini_status": "健康" if gini < 0.4 else ("偏斜" if gini < 0.6 else "严重不均"),
            "total_net_flow": total_net,
            "trend": trend,
            "dependency_risks": dependency_risks,
            "factions_summary": [{
                "name": fd["name"],
                "net_flow": fd["net_flow"],
                "treasury": fd["treasury"],
            } for fd in factions_data],
        }

    def _calc_total_tax(self, faction_id: str) -> int:
        """计算势力总税收"""
        total = 0
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            result = self.calc_tax(faction_id, tile, self.world.current_season)
            total += result["tax_income"]
        return total

    @staticmethod
    def _calc_gini(factions_data: list[dict]) -> float:
        """计算势力间Gini系数（基于国库财富）"""
        wealth = sorted([fd["treasury"] for fd in factions_data])
        n = len(wealth)
        if n <= 1 or sum(wealth) == 0:
            return 0.0
        # Gini = (Σ(2i-n-1)*x_i) / (n*Σx_i)
        total = sum(wealth)
        numerator = sum((2 * (i + 1) - n - 1) * wealth[i] for i in range(n))
        return abs(numerator / (n * total))

    # ================================================================
    # 10. Faucet-Sink 汇总报告
    # ================================================================
    def get_faction_economy_report(self, faction_id: str) -> dict:
        """获取势力经济汇总报告（Faucet-Sink 模型）"""
        faction = self.world.factions.get(faction_id)
        if not faction:
            return {"error": "势力不存在"}

        # Faucets
        tax_total = self._calc_total_tax(faction_id)
        trade = self.calc_trade_income(faction_id)
        grain = self.calc_grain_consumption(faction_id)
        pop_growth = self.calc_population_growth(faction_id)

        # Sinks
        military = self.calc_military_upkeep(faction_id)
        building = self.calc_building_upkeep(faction_id)

        # 粮产估算（基于农田建筑和人口）
        grain_production = self._calc_grain_production(faction_id)

        # 饥荒检查
        famines = self.check_famine(faction_id)

        total_income = tax_total + trade["trade_income"]
        total_expense = military["military_upkeep"] + building["building_upkeep"]
        net_flow = total_income - total_expense

        return {
            "faction_name": faction.name,
            # Faucets
            "faucets": {
                "tax_income": tax_total,
                "trade_income": trade["trade_income"],
                "port_bonus": trade["port_bonus"],
                "total_income": total_income,
            },
            # Sinks
            "sinks": {
                "military_upkeep": military["military_upkeep"],
                "building_upkeep": building["building_upkeep"],
                "total_expense": total_expense,
            },
            # Flow
            "net_flow": net_flow,
            "flow_status": "盈余" if net_flow > 0 else "平衡" if net_flow == 0 else "赤字",
            # Resources
            "treasury": faction.treasury,
            "grain_stock": faction.grain,
            "grain_production": grain_production,
            "grain_consumption": grain["grain_consumed"],
            "grain_net": grain_production - grain["grain_consumed"],
            # Population
            "population": faction.total_population,
            "population_growth": pop_growth["total_growth"],
            # Risks
            "famine_tiles": len(famines),
            "famine_details": famines[:5],  # 最多5个
        }

    def _calc_grain_production(self, faction_id: str) -> int:
        """计算势力粮产"""
        total = 0
        for tile in self.world.tiles.values():
            if tile.faction_id != faction_id:
                continue
            # 基础粮产
            base = tile.population // 10
            # 农田建筑加成
            buildings = getattr(tile, 'buildings', {}) or {}
            farmland_level = buildings.get(BuildingType.FARMLAND.value, 0)
            base += farmland_level * 80  # 每级农田+80粮
            # 季节修正
            season = self.world.current_season
            if season == Season.AUTUMN:
                base = int(base * 1.3)
            elif season == Season.WINTER:
                base = int(base * 0.5)
            total += base
        return total

    # ================================================================
    # 11. 回合结算接口（与 SettleEngine 兼容）
    # ================================================================
    def settle_all(self) -> dict:
        """执行全势力经济结算诊断（只计算不修改状态，状态修改由 SettleEngine 统一处理）"""
        result = {
            "tax_collected": {},
            "grain_consumed": {},
            "grain_produced": {},
            "trade_income": {},
            "military_upkeep": {},
            "building_upkeep": {},
            "population_changes": {},
            "economy_health": self.calc_economy_health(),
            "famine_alerts": [],
        }

        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue

            # 税收（仅计算，不修改 faction.treasury）
            tax_total = self._calc_total_tax(fid)
            result["tax_collected"][fid] = tax_total

            # 粮耗（仅计算）
            grain = self.calc_grain_consumption(fid)
            result["grain_consumed"][fid] = grain["grain_consumed"]

            # 粮产（仅计算）
            grain_prod = self._calc_grain_production(fid)
            result["grain_produced"][fid] = grain_prod

            # 贸易收入（仅计算）
            trade = self.calc_trade_income(fid)
            result["trade_income"][fid] = trade["trade_income"]

            # 军费（仅计算）
            military = self.calc_military_upkeep(fid)
            result["military_upkeep"][fid] = military["military_upkeep"]

            # 建筑维护（仅计算）
            building = self.calc_building_upkeep(fid)
            result["building_upkeep"][fid] = building["building_upkeep"]

            # 人口增长（仅计算）
            pop = self.calc_population_growth(fid)
            result["population_changes"][fid] = pop["total_growth"]

            # 饥荒检查
            famines = self.check_famine(fid)
            if famines:
                result["famine_alerts"].append({
                    "faction": faction.name,
                    "count": len(famines),
                    "severity": max(f["severity"] for f in famines),
                })

        return result


# 便捷导出
__all__ = [
    "EconomyEngine", "TradeGood", "PopulationStructure",
    "TRADE_GOOD_PRICES", "FACTION_SPECIALTY",
]
