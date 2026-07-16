"""
国策系统引擎 - 民心、治安、徭役联动

职责:
- 国策激活/废除
- 国策效果每回合结算
- 民心触发民变/税收增减/征兵倍率
- 治安影响匪患概率
- 徭役绑定民心与基建速度
"""
from __future__ import annotations
import json
import logging
import random
from pathlib import Path
from typing import Optional

from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    PolicyType, DisasterType, Season, BuildingType,
)

# 模块级缓存：policies.json 只加载一次，避免每回合/每地块的磁盘 I/O
_policies_cache: Optional[dict] = None
_policies_cache_lock = False  # 简单标记，避免并发重复加载


def _load_policies_data() -> dict:
    """加载 policies.json（模块级缓存，仅首次读盘）"""
    global _policies_cache, _policies_cache_lock
    if _policies_cache is not None:
        return _policies_cache
    logger = logging.getLogger("yuanmo.policy")
    try:
        policy_path = Path(__file__).parent.parent / "data" / "policies.json"
        with open(policy_path, "r", encoding="utf-8") as f:
            _policies_cache = json.load(f)
        logger.info("国策数据加载成功，共 %d 条", len(_policies_cache))
        return _policies_cache
    except FileNotFoundError:
        logger.error("国策数据文件不存在: %s，国策系统将无法工作", policy_path)
        _policies_cache = {}
        return {}
    except json.JSONDecodeError as e:
        logger.error("国策数据 JSON 格式错误: %s，国策系统将无法工作", e)
        _policies_cache = {}
        return {}
    except OSError as e:
        logger.error("读取国策数据文件失败 (%s): %s", policy_path, e)
        _policies_cache = {}
        return {}
    except Exception as e:
        logger.error("加载国策数据时发生未知错误: %s", e, exc_info=True)
        _policies_cache = {}
        return {}



logger = logging.getLogger("yuanmo.policy")

# 国策配置表
POLICY_CONFIG = {
    PolicyType.LIGHT_TAX: {
        "name": "轻徭薄赋",
        "description": "减税养民，与民休息（民心+5/回合、人口增长+2%、税收-30%）",
        "unlock_cost": 500,
        "effects": {
            "morale_per_turn": 5,           # 每回合民心+5
            "population_growth_bonus": 0.02, # 人口增长+2%
            "tax_penalty": 0.30,             # 税收-30%
        },
        "conflicts_with": [PolicyType.HEAVY_AGRICULTURE],
    },
    PolicyType.HEAVY_AGRICULTURE: {
        "name": "重农抑商",
        "description": "以农为本，抑制商贾（粮+20%、农田+30%、工坊-50%）",
        "unlock_cost": 400,
        "effects": {
            "grain_bonus": 0.20,             # 粮食产出+20%
            "farmland_bonus": 0.30,          # 农田产出+30%
            "workshop_penalty": 0.50,        # 工坊产出-50%
        },
        "conflicts_with": [PolicyType.LIGHT_TAX],
    },
    PolicyType.BAOJIA: {
        "name": "保甲连坐",
        "description": "十户一甲，互相监督（治安+3/回合、匪患-50%、民心-3/回合）",
        "unlock_cost": 300,
        "effects": {
            "public_order_per_turn": 3,      # 治安+3/回合
            "bandit_resist": 0.50,            # 匪患-50%
            "morale_penalty": 3,              # 民心-3/回合
        },
        "conflicts_with": [PolicyType.LIGHT_TAX],
    },
    PolicyType.MILITARY_FARM: {
        "name": "军屯养兵",
        "description": "亦兵亦农，以战养战（兵力恢复+50%、粮耗-15%、农田产出-20%）",
        "unlock_cost": 600,
        "effects": {
            "troop_recovery_bonus": 0.50,    # 兵力恢复+50%
            "grain_consumption_bonus": 0.15, # 粮耗-15%
            "farmland_penalty": 0.20,         # 农田产出-20%
        },
        "conflicts_with": [PolicyType.HEAVY_AGRICULTURE],
    },
    PolicyType.CIVIL_EXAM: {
        "name": "开科取士",
        "description": "科举选拔，广纳贤才（官员忠诚+2/回合、朝堂稳定+1/回合、银两消耗200/回合）",
        "unlock_cost": 800,
        "effects": {
            "official_loyalty_bonus": 2,     # 官员忠诚+2/回合
            "court_stability_bonus": 1,      # 朝堂稳定+1/回合
            "treasury_cost": 200,            # 银两消耗200/回合
        },
        "conflicts_with": [],
    },
    PolicyType.STRICT_LAW: {
        "name": "严刑峻法",
        "description": "重典治乱，以刑去刑（犯罪-70%、治安+5/回合、民心-5/回合）",
        "unlock_cost": 400,
        "effects": {
            "crime_reduction": 0.70,          # 犯罪率-70%
            "public_order_per_turn": 5,       # 治安+5/回合
            "morale_penalty": 5,              # 民心-5/回合
        },
        "conflicts_with": [PolicyType.LIGHT_TAX],
    },
    PolicyType.REWARD_FARM_WAR: {
        "name": "奖励耕战",
        "description": "耕者有田，战者有爵（征兵效率+30%、士气+2、人口增长-10%）",
        "unlock_cost": 500,
        "effects": {
            "recruit_efficiency": 0.30,      # 征兵效率+30%
            "troop_morale_bonus": 2,         # 部队士气+2
            "population_growth_penalty": 0.10, # 人口增长-10%
        },
        "conflicts_with": [PolicyType.LIGHT_TAX],
    },
    PolicyType.CORVEE_LABOR: {
        "name": "徭役征发",
        "description": "征发民力，大兴土木（基建速度+30%、徭役负担+20、民心-2/回合）",
        "unlock_cost": 0,  # 徭役免费激活（代价是民心）
        "effects": {
            "build_speed_bonus": 0.30,        # 基建速度+30%
            "corvee_burden": 20,              # 徭役负担+20
            "morale_per_turn": -2,           # 民心-2/回合
        },
        "conflicts_with": [PolicyType.LIGHT_TAX],
    },
}

# 民心触发阈值
MORALE_THRESHOLDS = {
    "revolt": 20,       # 民心≤20: 高概率民变
    "tax_penalty": 50,  # 民心≤50: 税收惩罚-20%
    "recruit_bonus": 70,# 民心≥70: 征兵倍率+15%
    "growth_bonus": 75, # 民心≥75: 人口增长额外+5%
}

# 治安触发阈值
ORDER_THRESHOLDS = {
    "bandit_double": 20,   # 治安≤20: 匪患概率翻倍
    "revolt_risk": 15,     # 治安≤15: 民变风险增加
    "trade_safe": 60,      # 治安≥60: 贸易安全
}


class PolicyEngine:
    """国策系统引擎"""

    def __init__(self, world: WorldState):
        self.world = world

    # ================================================================
    # 国策管理
    # ================================================================

    def activate_policy(self, faction_id: str, policy_type: PolicyType) -> dict:
        """激活国策"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        config = POLICY_CONFIG.get(policy_type)
        if not config:
            return {"success": False, "message": "未知国策"}

        # 检查是否已激活
        if faction_id not in self.world.faction_policies:
            self.world.faction_policies[faction_id] = []
        current = self.world.faction_policies[faction_id]

        if policy_type in current:
            return {"success": False, "message": f"国策「{config['name']}」已激活"}

        # 检查冲突国策
        for conflict in config.get("conflicts_with", []):
            if conflict in current:
                conflict_config = POLICY_CONFIG.get(conflict, {})
                return {
                    "success": False,
                    "message": f"与已激活的国策「{conflict_config.get('name', conflict.value)}」冲突",
                }

        # 解锁费用
        cost = config.get("unlock_cost", 500)
        if cost > 0 and faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需{cost}，现有{faction.treasury}）"}

        if cost > 0:
            faction.treasury -= cost

        # 激活国策
        current.append(policy_type)
        # current 已是 self.world.faction_policies[faction_id] 的引用，无需重新赋值
        faction.unlocked_policies.append(policy_type.value)

        # 徭役征发：设置徭役负担
        if policy_type == PolicyType.CORVEE_LABOR:
            for tile in self.world.get_faction_tiles(faction_id):
                tile.corvee_burden = min(100, tile.corvee_burden + config["effects"]["corvee_burden"])

        # 写入事件
        self.world.events_log.append({
            "event_id": f"policy_{faction_id}_{policy_type.value}_{self.world.current_round}",
            "event_type": "policy",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"颁布国策 · {config['name']}",
            "description": f"{faction.name}颁布国策「{config['name']}」：{config['description']}",
            "faction_id": faction_id,
            "tile_id": "",
            "effects": {"policy": policy_type.value, "cost": cost},
            "narrative": f"{faction.name}颁布国策「{config['name']}」。",
        })

        return {
            "success": True,
            "policy": policy_type.value,
            "name": config["name"],
            "cost": cost,
            "message": f"已激活国策「{config['name']}」",
        }

    def deactivate_policy(self, faction_id: str, policy_type: PolicyType) -> dict:
        """废除国策"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        config = POLICY_CONFIG.get(policy_type, {})
        policy_name = config.get("name", policy_type.value)

        if faction_id not in self.world.faction_policies:
            return {"success": False, "message": "该势力未激活任何国策"}

        current = self.world.faction_policies[faction_id]
        if policy_type not in current:
            return {"success": False, "message": f"国策「{policy_name}」未激活"}

        current.remove(policy_type)
        self.world.faction_policies[faction_id] = current

        # 徭役征发：取消徭役负担
        if policy_type == PolicyType.CORVEE_LABOR:
            for tile in self.world.get_faction_tiles(faction_id):
                tile.corvee_burden = max(0, tile.corvee_burden - 20)

        return {
            "success": True,
            "message": f"已废除国策「{policy_name}」",
        }

    def get_faction_policies(self, faction_id: str) -> list[dict]:
        """获取势力当前激活的国策"""
        if faction_id not in self.world.faction_policies:
            return []
        result = []
        for pt in self.world.faction_policies[faction_id]:
            config = POLICY_CONFIG.get(pt, {})
            result.append({
                "type": pt.value,
                "name": config.get("name", pt.value),
                "description": config.get("description", ""),
                "effects": config.get("effects", {}),
            })
        return result

    # ================================================================
    # 国策效果每回合结算
    # ================================================================

    def settle_policy_effects(self) -> dict:
        """每回合结算所有势力国策效果，返回效果摘要"""
        result = {
            "faction_effects": {},
            "morale_events": [],
            "revolt_events": [],
        }

        for faction_id in list(self.world.faction_policies.keys()):
            faction = self.world.get_faction(faction_id)
            if not faction or not faction.is_alive:
                continue

            policies = self.world.faction_policies.get(faction_id, [])
            if not policies:
                continue

            tiles = self.world.get_faction_tiles(faction_id)
            fid_effects = {
                "morale_change": 0,
                "order_change": 0,
                "grain_bonus": 0,
                "treasury_cost": 0,
            }

            for pt in policies:
                config = POLICY_CONFIG.get(pt)
                if not config:
                    continue
                effects = config["effects"]

                # 民心变化
                if "morale_per_turn" in effects:
                    delta = effects["morale_per_turn"]
                    fid_effects["morale_change"] += delta
                    for tile in tiles:
                        tile.morale = max(0, min(100, tile.morale + delta))

                # 治安变化
                if "public_order_per_turn" in effects:
                    delta = effects["public_order_per_turn"]
                    fid_effects["order_change"] += delta
                    for tile in tiles:
                        tile.public_order = max(0, min(100, tile.public_order + delta))

                # 民心惩罚
                if "morale_penalty" in effects:
                    delta = -effects["morale_penalty"]
                    fid_effects["morale_change"] += delta
                    for tile in tiles:
                        tile.morale = max(0, min(100, tile.morale + delta))

                # 国库消耗
                if "treasury_cost" in effects:
                    cost = effects["treasury_cost"]
                    fid_effects["treasury_cost"] += cost
                    faction.treasury = max(0, faction.treasury - cost)

                # 徭役负担对民心影响
                if pt == PolicyType.CORVEE_LABOR:
                    for tile in tiles:
                        if tile.corvee_burden > 30:
                            morale_penalty = -int(tile.corvee_burden / 10)
                            tile.morale = max(0, tile.morale + morale_penalty)

                # 朝堂稳定
                if "court_stability_bonus" in effects:
                    faction.court_stability = min(100, faction.court_stability + effects["court_stability_bonus"])

            result["faction_effects"][faction_id] = fid_effects

        # ================================================================
        # 民心触发：民变/税收/征兵
        # ================================================================
        self._process_morale_triggers(result)

        # ================================================================
        # 治安触发：匪患
        # ================================================================
        self._process_order_triggers(result)

        return result

    def _process_morale_triggers(self, result: dict):
        """处理民心阈值触发"""
        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            faction = self.world.get_faction(tile.faction_id)
            if not faction or not faction.is_alive:
                continue

            morale = tile.morale

            # 民变判定
            if morale <= MORALE_THRESHOLDS["revolt"]:
                revolt_chance = (MORALE_THRESHOLDS["revolt"] - morale) * 0.02
                if random.random() < revolt_chance:
                    # 触发民变
                    rebel_troops = random.randint(200, 800)
                    event_id = f"revolt_{tile.tile_id}_{self.world.current_round}"
                    # 生成叛军
                    from server.models.world_state import RebelArmy
                    rebel = RebelArmy(
                        rebel_id=event_id,
                        tile_id=tile.tile_id,
                        troops=rebel_troops,
                        leader=f"{tile.tile_name}义军首领",
                        cause=f"民心{morale}，揭竿而起",
                        spawned_round=self.world.current_round,
                    )
                    self.world.rebel_armies[event_id] = rebel
                    tile.public_order = max(0, tile.public_order - 15)
                    result["revolt_events"].append({
                        "tile_id": tile.tile_id,
                        "tile_name": tile.tile_name,
                        "rebel_troops": rebel_troops,
                        "morale": morale,
                        "message": f"民心尽失！{tile.tile_name}民众揭竿而起，叛军{rebel_troops}人！",
                    })
                    self.world.events_log.append({
                        "event_id": event_id,
                        "event_type": "rebellion",
                        "severity": "critical",
                        "round": self.world.current_round,
                        "title": f"民变 · {tile.tile_name}",
                        "description": f"民心{morale}，{tile.tile_name}民众揭竿而起，叛军{rebel_troops}人。",
                        "faction_id": tile.faction_id,
                        "tile_id": tile.tile_id,
                        "effects": {"rebel_troops": rebel_troops, "morale": morale},
                        "narrative": f"{tile.tile_name}民心尽失，民众揭竿而起！",
                    })

            # 税收惩罚
            if morale <= MORALE_THRESHOLDS["tax_penalty"]:
                tax_penalty = 0.20
                # 将在 settle_engine 中应用

            # 征兵倍率
            if morale >= MORALE_THRESHOLDS["recruit_bonus"]:
                # 民心高涨，征兵效率+15%
                if "recruit_bonus_tiles" not in result:
                    result["recruit_bonus_tiles"] = []
                result["recruit_bonus_tiles"].append({
                    "tile_id": tile.tile_id,
                    "tile_name": tile.tile_name,
                    "morale": morale,
                    "recruit_mult": 1.15,
                })

            # 民心事件日志
            if morale <= 25 and not any(e["tile_id"] == tile.tile_id for e in result["revolt_events"]):
                result["morale_events"].append({
                    "tile_id": tile.tile_id,
                    "tile_name": tile.tile_name,
                    "morale": morale,
                    "risk": "high" if morale <= MORALE_THRESHOLDS["revolt"] else "moderate",
                })

    def _process_order_triggers(self, result: dict):
        """处理治安阈值触发"""
        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue

            order = tile.public_order

            # 治安过低增加匪患
            if order <= ORDER_THRESHOLDS["bandit_double"]:
                bandit_chance = 0.15  # 基础匪患概率翻倍
                if random.random() < bandit_chance:
                    grain_stolen = int(tile.grain * random.uniform(0.1, 0.25))
                    tile.grain = max(0, tile.grain - grain_stolen)
                    tile.morale = max(0, tile.morale - 3)
                    result["morale_events"].append({
                        "tile_id": tile.tile_id,
                        "tile_name": tile.tile_name,
                        "type": "bandit",
                        "grain_stolen": grain_stolen,
                        "message": f"{tile.tile_name}治安败坏，匪寇劫掠，损粮{grain_stolen}石",
                    })

            # 民变风险增加
            if order <= ORDER_THRESHOLDS["revolt_risk"]:
                tile.morale = max(0, tile.morale - 2)  # 治安差叠加民心下降

    # ================================================================
    # 获取民心/治安/徭役对各项的影响系数
    # ================================================================

    def get_tax_multiplier(self, tile: TileState) -> float:
        """获取税收倍率（民心影响）"""
        mult = 1.0
        if tile.morale <= MORALE_THRESHOLDS["tax_penalty"]:
            mult -= 0.20  # 民心低税收-20%
        return mult

    def get_recruit_multiplier(self, tile: TileState) -> float:
        """获取征兵倍率（民心影响）"""
        mult = 1.0
        if tile.morale >= MORALE_THRESHOLDS["recruit_bonus"]:
            mult += 0.15  # 民心高征兵+15%
        return mult

    def get_bandit_resist(self, tile: TileState) -> float:
        """获取匪患抵抗率（治安+烽燧影响）"""
        # M-1: 改为从 building_config 导入（消除与 building_system 的延迟导入）
        from server.core.building_config import BUILDING_CONFIG
        resist = tile.public_order / 100.0
        # 烽燧加成
        for b in tile.buildings.values():
            if b.building_type == BuildingType.BEACON:
                config = BUILDING_CONFIG.get(BuildingType.BEACON, {})
                resist += config.get("effects", {}).get("bandit_resist_per_level", 0.15) * b.level
        return min(0.95, resist)

    def get_build_speed_multiplier(self, faction_id: str) -> float:
        """获取基建速度倍率（徭役影响）"""
        mult = 1.0
        if faction_id in self.world.faction_policies:
            if PolicyType.CORVEE_LABOR in self.world.faction_policies[faction_id]:
                config = POLICY_CONFIG.get(PolicyType.CORVEE_LABOR, {})
                mult += config.get("effects", {}).get("build_speed_bonus", 0.30)
        return mult


    @staticmethod
    def get_tech_policy_modifiers(faction, world=None) -> dict:
        """计算科技树国策的全局修饰符（每回合调用）

        读取 policies.json，根据 faction.unlocked_policies 聚合所有已解锁国策的效果，
        返回可用于税收/粮产/人口/粮耗等结算的修饰符字典。

        Returns:
            dict: {
                "tax_efficiency": float,           # 征税效率加成（0.0~1.0，如 0.30 表示+30%）
                "treasury_income": int,            # 国库收入固定加成（银/回合）
                "grain_production": float,         # 粮产加成（0.0~1.0）
                "population_growth": float,        # 人口增长加成（0.0~1.0）
                "garrison_cost_reduction": float,  # 驻军消耗减少（0.0~1.0）
                "land_fertility": float,           # 土地肥力加成
                "famine_resistance": float,        # 抗灾加成
                "plague_reduction": float,         # 防疫加成
                "flood_reduction": float,          # 防洪加成
                "construction_speed": float,       # 建设速度加成
                "arms_production": float,          # 军械产量加成
                "trade_income": float,             # 贸易收入加成
                "troop_power": float,              # 战力加成
                "morale_bonus": float,             # 士气加成
                "siege_bonus": float,              # 攻城加成
                "fortification_bonus": float,      # 城防加成
                "march_speed": float,              # 行军速度加成
                "naval_power": float,              # 水师加成
                "all_policy_ids": list[str],       # 所有已解锁国策ID
            }
        """  # noqa: D401
        unlocked = getattr(faction, 'unlocked_policies', [])
        if not unlocked:
            return {"all_policy_ids": [], "tax_efficiency": 0.0, "treasury_income": 0,
                    "grain_production": 0.0, "population_growth": 0.0,
                    "garrison_cost_reduction": 0.0, "land_fertility": 0.0,
                    "famine_resistance": 0.0, "plague_reduction": 0.0,
                    "flood_reduction": 0.0, "construction_speed": 0.0,
                    "arms_production": 0.0, "trade_income": 0.0,
                    "troop_power": 0.0, "morale_bonus": 0.0,
                    "siege_bonus": 0.0, "fortification_bonus": 0.0,
                    "march_speed": 0.0, "naval_power": 0.0}

        try:
            policies_data = _load_policies_data()
        except Exception:
            logger = logging.getLogger("yuanmo.policy")
            logger.warning("加载 policies.json 失败，国策修饰符不生效")
            return {"all_policy_ids": [], "tax_efficiency": 0.0, "treasury_income": 0,
                    "grain_production": 0.0, "population_growth": 0.0,
                    "garrison_cost_reduction": 0.0, "land_fertility": 0.0,
                    "famine_resistance": 0.0, "plague_reduction": 0.0,
                    "flood_reduction": 0.0, "construction_speed": 0.0,
                    "arms_production": 0.0, "trade_income": 0.0,
                    "troop_power": 0.0, "morale_bonus": 0.0,
                    "siege_bonus": 0.0, "fortification_bonus": 0.0,
                    "march_speed": 0.0, "naval_power": 0.0}

        modifiers = {
            "all_policy_ids": list(unlocked),
            "tax_efficiency": 0.0,
            "treasury_income": 0,
            "grain_production": 0.0,
            "population_growth": 0.0,
            "garrison_cost_reduction": 0.0,
            "land_fertility": 0.0,
            "famine_resistance": 0.0,
            "plague_reduction": 0.0,
            "flood_reduction": 0.0,
            "construction_speed": 0.0,
            "arms_production": 0.0,
            "trade_income": 0.0,
            "troop_power": 0.0,
            "morale_bonus": 0.0,
            "siege_bonus": 0.0,
            "fortification_bonus": 0.0,
            "march_speed": 0.0,
            "naval_power": 0.0,
        }

        for cat in policies_data.get("policies", {}).values():
            for branch in cat.get("branches", []):
                for tier in branch.get("tiers", []):
                    if tier["id"] not in unlocked:
                        continue
                    effects = tier.get("effects", {})
                    for key, val in effects.items():
                        if key == "tax_efficiency":
                            modifiers["tax_efficiency"] += val / 100.0
                        elif key == "treasury_income":
                            modifiers["treasury_income"] += val
                        elif key == "grain_production":
                            modifiers["grain_production"] += val / 100.0
                        elif key == "population_growth":
                            modifiers["population_growth"] += val / 100.0
                        elif key == "garrison_cost_reduction":
                            modifiers["garrison_cost_reduction"] += val / 100.0
                        elif key == "land_fertility":
                            modifiers["land_fertility"] += val / 100.0
                        elif key == "famine_resistance":
                            modifiers["famine_resistance"] += val / 100.0
                        elif key == "plague_reduction":
                            modifiers["plague_reduction"] += val / 100.0
                        elif key == "flood_reduction":
                            modifiers["flood_reduction"] += val / 100.0
                        elif key == "construction_speed":
                            modifiers["construction_speed"] += val / 100.0
                        elif key == "arms_production":
                            modifiers["arms_production"] += val / 100.0
                        elif key == "trade_income":
                            modifiers["trade_income"] += val / 100.0
                        elif key == "troop_power":
                            modifiers["troop_power"] += val / 100.0
                        elif key == "morale_bonus":
                            modifiers["morale_bonus"] += val / 100.0
                        elif key == "siege_bonus":
                            modifiers["siege_bonus"] += val / 100.0
                        elif key == "fortification_bonus":
                            modifiers["fortification_bonus"] += val / 100.0
                        elif key == "march_speed":
                            modifiers["march_speed"] += val / 100.0
                        elif key == "naval_power":
                            modifiers["naval_power"] += val / 100.0

        return modifiers



