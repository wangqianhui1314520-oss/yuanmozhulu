"""
城建基建引擎 - 城池地块基建体系

职责:
- 建筑建造/升级/拆除
- 建筑产出计算（每回合自动结算）
- 建筑效果叠加
- 绑定民心/治安/徭役联动
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    Building, BuildingType, PolicyType, Season,
)

logger = logging.getLogger("yuanmo.building")

# 建筑配置表
BUILDING_CONFIG = {
    BuildingType.FARMLAND: {
        "name": "农田",
        "build_cost": 300,
        "build_time": 1,  # 建造所需回合
        "upkeep": 0,
        "max_level": 5,
        "effects": {
            "grain_per_level": 80,    # 每级粮食产出/回合
            "spring_bonus": 0.2,       # 春季额外产出
            "autumn_bonus": 0.3,       # 秋季额外产出
            "winter_penalty": 0.4,     # 冬季减产比例
        },
        "description": "耕种田地，每级产粮80石/回合",
        "requires": [],  # 前置条件
    },
    BuildingType.WORKSHOP: {
        "name": "工坊",
        "build_cost": 500,
        "build_time": 2,
        "upkeep": 20,
        "max_level": 4,
        "effects": {
            "treasury_per_level": 60,  # 每级银两产出/回合
            "development_per_level": 1, # 每级发展度+1
        },
        "description": "百工坊市，每级产银60两/回合",
        "requires": [],
    },
    BuildingType.BEACON: {
        "name": "烽燧",
        "build_cost": 200,
        "build_time": 1,
        "upkeep": 5,
        "max_level": 3,
        "effects": {
            "vision_range_per_level": 2,       # 每级视野范围+2格
            "early_warning_chance": 0.3,       # 敌军接近预警概率
            "bandit_resist_per_level": 0.15,   # 每级匪患抵抗
        },
        "description": "烽火台，扩展视野，预警敌军",
        "requires": [],
    },
    BuildingType.DOCK: {
        "name": "码头",
        "build_cost": 400,
        "build_time": 2,
        "upkeep": 15,
        "max_level": 3,
        "effects": {
            "trade_bonus_per_level": 0.25,  # 每级贸易加成
            "naval_capacity": 1,              # 水军容量
        },
        "description": "沿水码头，通商贸易，水军可用",
        "requires": [TileType.COAST, TileType.PORT, TileType.WATER],
    },
    BuildingType.BARRACKS: {
        "name": "征兵营",
        "build_cost": 350,
        "build_time": 2,
        "upkeep": 30,
        "max_level": 4,
        "effects": {
            "recruit_per_level": 15,      # 每级每回合自动招募兵力
            "training_morale": 1,          # 每级驻军士气+1
        },
        "description": "练兵之所，每级每回合自动募兵15人",
        "requires": [],
    },
    BuildingType.GRANARY: {
        "name": "粮仓",
        "build_cost": 250,
        "build_time": 2,
        "upkeep": 5,
        "max_level": 5,
        "effects": {
            "capacity_per_level": 500,    # 每级储粮上限+500
            "grain_per_level": 50,        # 每级产粮/回合
            "spring_penalty": 0.3,        # 春播存粮消耗比例
            "autumn_bonus": 0.8,           # 秋收存粮大增比例
        },
        "description": "储粮之所，每级储粮+500，产粮+50",
        "requires": [],
    },
    BuildingType.CLINIC: {
        "name": "医馆",
        "build_cost": 200,
        "build_time": 1,
        "upkeep": 10,
        "max_level": 3,
        "effects": {
            "plague_resist_per_level": 0.3,   # 每级瘟疫抵抗
            "population_growth_per_level": 0.005,  # 每级人口增长加成
        },
        "description": "悬壶济世，抵抗瘟疫，促进人口",
        "requires": [],
    },
    BuildingType.ARMORY: {
        "name": "军械所",
        "build_cost": 800,
        "build_time": 3,
        "upkeep": 50,
        "max_level": 4,
        "effects": {
            "arms_per_level": 5,        # 每级兵器产出/回合
            "winter_penalty": 0.33,      # 冬季减产比例
        },
        "description": "锻造军械，每级产兵器5件/回合",
        "requires": [],
    },
    BuildingType.STABLE: {
        "name": "马场",
        "build_cost": 600,
        "build_time": 2,
        "upkeep": 40,
        "max_level": 4,
        "effects": {
            "horses_per_level": 2,      # 每级战马产出/回合
            "spring_summer_bonus": 0.5,  # 春夏繁育加成
            "winter_penalty": 0.5,       # 冬季减产比例
        },
        "description": "养马育驹，每级产战马2匹/回合",
        "requires": [],
    },
    BuildingType.TEMPLE: {
        "name": "宗庙",
        "build_cost": 400,
        "build_time": 2,
        "upkeep": 15,
        "max_level": 3,
        "effects": {
            "morale_per_level": 2,           # 每级民心+2/回合
            "public_order_per_level": 1,     # 每级治安+1/回合
            "ceremony_reputation": 3,        # 祭祀声望加成
        },
        "description": "敬天法祖，每级民心+2，治安+1",
        "requires": [],
    },
    BuildingType.WALL: {
        "name": "城墙",
        "build_cost": 600,
        "build_time": 3,
        "upkeep": 25,
        "max_level": 5,
        "effects": {
            "fortification_per_level": 1,     # 每级城防+1
            "siege_resist_per_level": 0.1,    # 每级围城抵抗
            "defense_bonus_per_level": 0.05,  # 每级防御加成
        },
        "description": "坚城壁垒，每级城防+1，抵御围城",
        "requires": [],
    },
}


class BuildingEngine:
    """城建基建引擎"""

    def __init__(self, world: WorldState):
        self.world = world

    # ================================================================
    # 建造/升级/拆除
    # ================================================================

    def construct_building(self, tile_id: str, building_type: BuildingType,
                           faction_id: str) -> dict:
        """在指定地块建造新建筑"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return {"success": False, "message": "地块不存在"}
        if tile.faction_id != faction_id:
            return {"success": False, "message": "该地块不属于你方"}

        config = BUILDING_CONFIG.get(building_type)
        if not config:
            return {"success": False, "message": "未知建筑类型"}

        # 检查地形前置条件
        if config["requires"]:
            if tile.tile_type not in config["requires"]:
                tile_type_names = [t.value for t in config["requires"]]
                return {"success": False, "message": f"{config['name']}只能建造在{'/'.join(tile_type_names)}地块上"}

        # 检查是否已有同类型建筑
        for b in tile.buildings.values():
            if b.building_type == building_type:
                return {"success": False, "message": f"该地块已有{config['name']}，请使用升级功能"}

        # 检查资源
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}
        cost = config["build_cost"]
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需{cost}，现有{faction.treasury}）"}

        # 扣除资源
        faction.treasury -= cost

        # 创建建筑
        building_id = f"building_{tile_id}_{building_type.value}_{self.world.current_round}"
        building = Building(
            building_id=building_id,
            building_type=building_type,
            tile_id=tile_id,
            faction_id=faction_id,
            level=1,
            hp=100,
            built_round=self.world.current_round,
        )
        tile.buildings[building_id] = building
        self.world.building_registry[building_id] = building

        # 写入事件日志
        self.world.events_log.append({
            "event_id": f"build_{building_id}",
            "event_type": "construction",
            "severity": "minor",
            "round": self.world.current_round,
            "title": f"兴建{config['name']}",
            "description": f"{faction.name}在{tile.tile_name}兴建{config['name']}（1级），耗银{cost}两。",
            "faction_id": faction_id,
            "tile_id": tile_id,
            "effects": {"building_type": building_type.value, "cost": cost},
            "narrative": f"{faction.name}在{tile.tile_name}兴建{config['name']}。",
        })

        return {
            "success": True,
            "building_id": building_id,
            "building_type": building_type.value,
            "level": 1,
            "cost": cost,
            "message": f"已在{tile.tile_name}建造{config['name']}（耗银{cost}两）",
        }

    def upgrade_building(self, building_id: str, faction_id: str) -> dict:
        """升级现有建筑"""
        building = self.world.building_registry.get(building_id)
        if not building:
            building = self._find_building_in_tiles(building_id)
        if not building:
            return {"success": False, "message": "建筑不存在"}

        if building.faction_id != faction_id:
            return {"success": False, "message": "该建筑不属于你方"}

        config = BUILDING_CONFIG.get(building.building_type)
        if not config:
            return {"success": False, "message": "未知建筑类型"}

        if building.level >= config["max_level"]:
            return {"success": False, "message": f"{config['name']}已达最高等级({config['max_level']}级)"}

        # 升级费用递增
        upgrade_cost = int(config["build_cost"] * building.level * 0.8)
        faction = self.world.get_faction(faction_id)
        if not faction or faction.treasury < upgrade_cost:
            return {"success": False, "message": f"银两不足（需{upgrade_cost}，现有{faction.treasury if faction else 0}）"}

        faction.treasury -= upgrade_cost
        building.level += 1
        building.hp = 100  # 升级恢复耐久

        # 同步更新tile中的building
        tile = self.world.get_tile(building.tile_id)
        if tile and building_id in tile.buildings:
            tile.buildings[building_id] = building

        return {
            "success": True,
            "building_id": building_id,
            "new_level": building.level,
            "cost": upgrade_cost,
            "message": f"{config['name']}已升级至{building.level}级（耗银{upgrade_cost}两）",
        }

    def demolish_building(self, building_id: str, faction_id: str) -> dict:
        """拆除建筑"""
        building = self.world.building_registry.get(building_id)
        if not building:
            building = self._find_building_in_tiles(building_id)
        if not building:
            return {"success": False, "message": "建筑不存在"}

        if building.faction_id != faction_id:
            return {"success": False, "message": "该建筑不属于你方"}

        config = BUILDING_CONFIG.get(building.building_type, {})
        building_name = config.get("name", building.building_type.value)
        refund = int(config.get("build_cost", 0) * 0.2)  # 拆除返还20%

        # 删除建筑
        tile = self.world.get_tile(building.tile_id)
        if tile and building_id in tile.buildings:
            del tile.buildings[building_id]
        if building_id in self.world.building_registry:
            del self.world.building_registry[building_id]

        if refund > 0:
            faction = self.world.get_faction(faction_id)
            if faction:
                faction.treasury += refund

        return {
            "success": True,
            "message": f"已拆除{building_name}，回收{refund}两",
            "refund": refund,
        }

    # ================================================================
    # 建筑产出结算（每回合）
    # ================================================================

    def settle_building_output(self) -> dict:
        """每回合结算所有建筑产出，返回产出摘要"""
        season = self.world.current_season
        result = {
            "total_grain_produced": 0,
            "total_treasury_produced": 0,
            "total_arms_produced": 0,
            "total_horses_produced": 0,
            "total_recruits": 0,
            "by_faction": {},  # faction_id → summary
        }

        for tile in self.world.tiles.values():
            if not tile.faction_id or not tile.buildings:
                continue

            faction = self.world.get_faction(tile.faction_id)
            if not faction or not faction.is_alive:
                continue

            fid = tile.faction_id
            if fid not in result["by_faction"]:
                result["by_faction"][fid] = {"grain": 0, "treasury": 0, "arms": 0, "horses": 0, "recruits": 0, "morale": 0, "order": 0}

            for building in tile.buildings.values():
                config = BUILDING_CONFIG.get(building.building_type)
                if not config:
                    continue
                effects = config["effects"]

                # 农田产出
                if building.building_type == BuildingType.FARMLAND:
                    grain = effects["grain_per_level"] * building.level
                    if season == Season.SPRING:
                        grain = int(grain * (1 + effects.get("spring_bonus", 0.2)))
                    elif season == Season.AUTUMN:
                        grain = int(grain * (1 + effects.get("autumn_bonus", 0.3)))
                    elif season == Season.WINTER:
                        grain = int(grain * (1 - effects.get("winter_penalty", 0.4)))
                    tile.grain += grain
                    faction.grain += grain
                    result["total_grain_produced"] += grain
                    result["by_faction"][fid]["grain"] += grain

                # 工坊产出
                elif building.building_type == BuildingType.WORKSHOP:
                    treasury = effects["treasury_per_level"] * building.level
                    tile.treasury += treasury
                    faction.treasury += treasury
                    result["total_treasury_produced"] += treasury
                    result["by_faction"][fid]["treasury"] += treasury
                    # 发展度提升
                    tile.development_level = min(100, tile.development_level + effects.get("development_per_level", 1) * building.level)

                # 征兵营产出
                elif building.building_type == BuildingType.BARRACKS:
                    recruits = effects["recruit_per_level"] * building.level
                    season_mult = 1.0
                    if season == Season.WINTER:
                        season_mult = 0.5
                    elif season == Season.SPRING:
                        season_mult = 1.3
                    actual_recruits = int(recruits * season_mult)
                    tile.troops += actual_recruits
                    result["total_recruits"] += actual_recruits
                    result["by_faction"][fid]["recruits"] += actual_recruits

                # 粮仓产出
                elif building.building_type == BuildingType.GRANARY:
                    grain = effects["grain_per_level"] * building.level
                    if season == Season.AUTUMN:
                        grain = int(grain * (1 + effects.get("autumn_bonus", 0.8)))
                    elif season == Season.SPRING:
                        grain = int(grain * (1 - effects.get("spring_penalty", 0.3)))
                    tile.grain += grain
                    faction.grain += grain
                    cap = effects["capacity_per_level"] * building.level
                    if tile.grain > cap:
                        overflow = tile.grain - cap
                        tile.grain = cap
                        faction.grain += overflow
                    result["total_grain_produced"] += grain
                    result["by_faction"][fid]["grain"] += grain

                # 军械所产出
                elif building.building_type == BuildingType.ARMORY:
                    arms = effects["arms_per_level"] * building.level
                    if season == Season.WINTER:
                        arms = int(arms * (1 - effects.get("winter_penalty", 0.33)))
                    faction.arms = getattr(faction, 'arms', 0) + arms
                    result["total_arms_produced"] += arms
                    result["by_faction"][fid]["arms"] += arms

                # 马场产出
                elif building.building_type == BuildingType.STABLE:
                    horses = effects["horses_per_level"] * building.level
                    if season in (Season.SPRING, Season.SUMMER):
                        horses = int(horses * (1 + effects.get("spring_summer_bonus", 0.5)))
                    elif season == Season.WINTER:
                        horses = int(horses * (1 - effects.get("winter_penalty", 0.5)))
                    faction.horses = getattr(faction, 'horses', 0) + horses
                    result["total_horses_produced"] += horses
                    result["by_faction"][fid]["horses"] += horses

                # 宗庙效果
                elif building.building_type == BuildingType.TEMPLE:
                    morale_bonus = effects["morale_per_level"] * building.level
                    order_bonus = effects["public_order_per_level"] * building.level
                    tile.morale = min(100, tile.morale + morale_bonus)
                    tile.public_order = min(100, tile.public_order + order_bonus)
                    result["by_faction"][fid]["morale"] += morale_bonus
                    result["by_faction"][fid]["order"] += order_bonus

                # 城墙效果
                elif building.building_type == BuildingType.WALL:
                    fort_bonus = effects["fortification_per_level"] * building.level
                    tile.fortification += fort_bonus

        return result

    # ================================================================
    # 建筑查询
    # ================================================================

    def get_tile_buildings(self, tile_id: str) -> list[dict]:
        """获取地块所有建筑信息"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return []
        result = []
        for b in tile.buildings.values():
            config = BUILDING_CONFIG.get(b.building_type, {})
            result.append({
                "building_id": b.building_id,
                "type": b.building_type.value,
                "name": config.get("name", b.building_type.value),
                "level": b.level,
                "max_level": config.get("max_level", 5),
                "hp": b.hp,
                "upkeep": config.get("upkeep", 0),
                "description": config.get("description", ""),
                "built_round": b.built_round,
            })
        return result

    def get_available_buildings(self, tile_id: str) -> list[dict]:
        """获取地块可建造的建筑列表"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return []
        existing_types = {b.building_type for b in tile.buildings.values()}
        available = []
        for btype, config in BUILDING_CONFIG.items():
            if btype in existing_types:
                continue
            # 检查地形前置条件
            if config["requires"] and tile.tile_type not in config["requires"]:
                continue
            available.append({
                "type": btype.value,
                "name": config["name"],
                "cost": config["build_cost"],
                "build_time": config["build_time"],
                "max_level": config["max_level"],
                "description": config["description"],
            })
        return available

    def get_upgrade_cost(self, building_id: str) -> Optional[dict]:
        """获取建筑升级费用"""
        building = self.world.building_registry.get(building_id)
        if not building:
            building = self._find_building_in_tiles(building_id)
        if not building:
            return None
        config = BUILDING_CONFIG.get(building.building_type)
        if not config or building.level >= config["max_level"]:
            return None
        return {
            "building_id": building_id,
            "current_level": building.level,
            "max_level": config["max_level"],
            "upgrade_cost": int(config["build_cost"] * building.level * 0.8),
        }

    def _find_building_in_tiles(self, building_id: str) -> Optional[Building]:
        """在tile.buildings中查找建筑"""
        for tile in self.world.tiles.values():
            if building_id in tile.buildings:
                return tile.buildings[building_id]
        return None
