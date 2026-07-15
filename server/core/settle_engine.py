"""
数值结算引擎 - 回合⑤⑥阶段的真实计算

职责:
- ⑤ 资源结算：税收、粮耗、兵力消耗、人口增长
- ⑥ 世界刷新：灾厄指数、条约过期、贸易路线、势力排名
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    DiplomaticStance, DisasterType, Season, PolicyType, BuildingType,
    SiegeRecord, PrisonerRecord, SiegeState, TreatyRecord,
)
from server.models.events import BattleEvent, EventType, EventSeverity

logger = logging.getLogger("yuanmo.settle")

# 从 game_const.yaml 复制的默认常量（兜底）
DEFAULTS = {
    "base_population_growth": 0.02,
    "base_tax_rate": 0.15,
    "refugee_threshold_morale": 30,
    "famine_threshold_grain": 100,
    "water_works_effect": 0.15,
    "granary_capacity_per_level": 500,
    "clinic_plague_reduction": 0.3,
    "relief_cost_per_pop": 5,  # 与 game_const.yaml 保持一致
    "migration_cost_per_pop": 2,   # 移民每人口消耗银两
    "quarantine_duration": 3,      # 瘟疫隔离持续回合数
    "siege_base_attrition": 0.05,
    "fortification_defense_bonus": 0.2,
    "trade_route_income": 100,
    "peace_treaty_duration": 12,
    "logistics_base_attrition": 0.02,
    # 围城与战斗增强常量
    "siege_grain_consumption_per_round": 0.03,
    "siege_wall_damage_per_round": 0.08,
    "siege_defender_attrition": 0.04,
    "siege_attacker_attrition": 0.01,
    "siege_surrender_morale_threshold": 15,
    "siege_breach_fortification_threshold": 0.3,
    "siege_troops_ratio_threshold": 2.0,
    "siege_fortification_threshold": 3,
    "capital_loot_treasury": 500,
    "capital_loot_grain": 1000,
    "prisoner_capture_chance": 0.25,
}


class SettleEngine:
    """回合数值结算引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**DEFAULTS, **(game_const or {})}

    # ================================================================
    # ⑤ 数值结算
    # ================================================================

    def phase_settle(self) -> dict:
        """完整执行数值结算阶段（集成四季事件、补给、城建、国策）"""
        result = {
            "tax_collected": {},
            "grain_consumed": {},
            "population_changes": {},
            "disasters_triggered": [],
            "year_end": self.world.current_month == 12,
            "season_events": {},
            "supply_attrition": {},
            "building_output": {},
            "policy_effects": {},
        }

        # ================================================================
        # 3.0 新增：季节随机事件（在数值结算之前触发）
        # ================================================================
        from server.core.season_events import SeasonEventEngine
        season_engine = SeasonEventEngine(self.world)
        result["season_events"] = season_engine.process_season_events()

        # ================================================================
        # 3.0 新增：补给线构建与逃散（在部队消耗之前）
        # ================================================================
        from server.core.supply_system import SupplyEngine
        supply_engine = SupplyEngine(self.world)
        supply_engine.build_supply_network()
        result["supply_attrition"] = supply_engine.process_supply_attrition()

        # ================================================================
        # 3.0 新增：城建基建产出结算
        # ================================================================
        from server.core.building_system import BuildingEngine
        building_engine = BuildingEngine(self.world)
        result["building_output"] = building_engine.settle_building_output()

        # ================================================================
        # 3.0 新增：国策效果结算（民心、治安、徭役）
        # ================================================================
        from server.core.policy_system import PolicyEngine
        policy_engine = PolicyEngine(self.world)
        result["policy_effects"] = policy_engine.settle_policy_effects()

        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            faction = self.world.factions.get(tile.faction_id)
            if not faction or not faction.is_alive:
                continue

            # 税收（含天气修正）
            tax = self._calc_tax(tile, faction)
            weather_effects = (self.world.weather or {}).get("effects", {}) or {}
            tax = int(tax * weather_effects.get("trade", 1.0))
            faction.treasury += tax
            tile.treasury += tax
            result["tax_collected"][tile.tile_id] = tax

            # 粮耗（含天气修正）
            grain_cost = self._calc_grain_consumption(tile)
            if weather_effects.get("troop_attrition", 0) > 0:
                grain_cost += int(tile.troops * 0.01 * weather_effects["troop_attrition"])
            tile.grain = max(0, tile.grain - grain_cost)
            result["grain_consumed"][tile.tile_id] = grain_cost

            # 人口变化
            pop_change = self._calc_population_change(tile, faction)
            tile.population = max(100, tile.population + pop_change)
            result["population_changes"][tile.tile_id] = pop_change

            # 兵力恢复（四季修正）
            if tile.garrison_resting and tile.troops < 2000:
                recovery_rate = 0.05  # 默认夏季/秋季
                if self.world.current_season == Season.WINTER:
                    recovery_rate = 0.02   # 寒冬征兵困难
                elif self.world.current_season == Season.SPRING:
                    recovery_rate = 0.07   # 春季募兵容易
                elif self.world.current_season == Season.SUMMER:
                    recovery_rate = 0.05   # 夏季正常恢复
                elif self.world.current_season == Season.AUTUMN:
                    recovery_rate = 0.05   # 秋季正常恢复
                tile.troops += int(tile.troops * recovery_rate) + 10

            # 饥荒判定
            if tile.grain <= self.const["famine_threshold_grain"] and tile.population > 1000:
                tile.morale = max(0, tile.morale - 5)
                if random.random() < 0.15:
                    tile.disasters.append(DisasterType.DROUGHT)

        # 势力总资源汇总（含四季修正）
        season = self.world.current_season
        for faction in self.world.factions.values():
            if not faction.is_alive:
                continue
            tiles = self.world.get_faction_tiles(faction.faction_id)
            faction.total_population = sum(t.population for t in tiles)
            faction.total_troops = sum(t.troops for t in tiles)
            faction.tile_count = len(tiles)
            faction.treasury = max(0, faction.treasury)
            faction.grain = max(0, faction.grain)

            # 四季民心修正
            season_morale_bonus = 0
            if season == Season.SPRING:
                season_morale_bonus = 3   # 万物复苏，民心振奋
            elif season == Season.AUTUMN:
                season_morale_bonus = 2   # 秋收丰足，民心安定
            elif season == Season.WINTER:
                season_morale_bonus = -3  # 寒冬难熬，民怨增加
            elif season == Season.SUMMER:
                season_morale_bonus = 1   # 夏日稍安

            for t in tiles:
                t.morale = max(0, min(100, t.morale + season_morale_bonus))

            # 建筑效果结算（含四季修正）
            season = self.world.current_season
            for t in tiles:
                # 粮仓：每级储粮上限+500，每回合自然产粮（春秋增产）
                granary_cap = t.granary * self.const.get("granary_capacity_per_level", 500)
                grain_base = 50  # 每级粮仓基础产粮
                if season == Season.SPRING:
                    grain_base = 35   # 春播时节，存粮消耗
                elif season == Season.AUTUMN:
                    grain_base = 90   # 秋收时节，粮食大增
                elif season == Season.WINTER:
                    grain_base = 20   # 冬日存粮消耗
                grain_produced = int(t.granary * grain_base)
                t.grain += grain_produced
                faction.grain += grain_produced
                # 储粮上限检查
                if t.grain > granary_cap:
                    overflow = t.grain - granary_cap
                    t.grain = granary_cap
                    faction.grain += overflow  # 溢出存势力

                # 军械所：每级每回合产军械（冬季减产）- 统一使用 building_system 的配置
                from server.core.building_system import BUILDING_CONFIG
                armory_config = BUILDING_CONFIG.get(BuildingType.ARMORY, {})
                arms_per_level = armory_config.get("effects", {}).get("arms_per_level", 5)
                winter_penalty = armory_config.get("effects", {}).get("winter_penalty", 0.33)
                arms_base = arms_per_level
                if season == Season.WINTER:
                    arms_base = int(arms_per_level * (1 - winter_penalty))  # 冬季减产
                arms_produced = getattr(t, 'armory', 0) * arms_base
                # 修复：多地块循环时累加而非覆盖（faction.arms =  → faction.arms +=）
                faction.arms = getattr(faction, 'arms', 0) + arms_produced

                # 马场：每级每回合产战马（春夏产驹多）
                horses_base = 2
                if season in (Season.SPRING, Season.SUMMER):
                    horses_base = 3  # 春夏草长，马匹繁育
                elif season == Season.WINTER:
                    horses_base = 1  # 冬季草料稀缺
                horses_produced = getattr(t, 'stable', 0) * horses_base
                # 修复：多地块循环时累加而非覆盖
                faction.horses = getattr(faction, 'horses', 0) + horses_produced

                # 港口：贸易收入（秋冬季减少）
                port_income = 80
                if season == Season.WINTER:
                    port_income = 40   # 冬季海路不畅
                elif season == Season.SUMMER:
                    port_income = 100  # 夏季海运繁忙
                if t.is_port:
                    faction.treasury += port_income

        # 天气生成（影响农业、行军）
        self._generate_weather()

        # 天灾触发
        self._trigger_disasters(result)

        return result

    def _calc_tax(self, tile: TileState, faction: FactionState) -> int:
        """计算地块税收（四季加成）"""
        base = int(tile.population * self.const["base_tax_rate"] * 0.01)
        morale_factor = tile.morale / 50.0
        tile_factor = {
            TileType.CITY: 2.0,
            TileType.PORT: 1.8,
            TileType.COAST: 1.3,
            TileType.FARMLAND: 1.0,
            TileType.GRASSLAND: 0.8,
            TileType.MOUNTAIN: 0.5,
            TileType.DESERT: 0.3,
            TileType.PASS: 0.6,
            TileType.WATER: 0.0,
        }.get(tile.tile_type, 1.0)

        # 四季税收修正
        season_mult = 1.0
        if self.world.current_season == Season.AUTUMN:
            season_mult = 1.3   # 秋收时节，商税繁荣
        elif self.world.current_season == Season.WINTER:
            season_mult = 0.75  # 寒冬商贸萧条
        elif self.world.current_season == Season.SPRING:
            season_mult = 0.9   # 春耕投入，税赋略减

        tax = int(base * morale_factor * tile_factor * season_mult)
        # 3.0: 国策/民心税收修正
        from server.core.policy_system import PolicyEngine, MORALE_THRESHOLDS
        policy_engine = PolicyEngine(self.world)
        if tile.morale <= MORALE_THRESHOLDS.get("tax_penalty", 50):
            tax = int(tax * 0.80)  # 民心低税收-20%
        tax_mult = policy_engine.get_tax_multiplier(tile)
        if tax_mult != 1.0:
            tax = int(tax * tax_mult)
        # 轻徭薄赋国策效果
        if tile.faction_id and tile.faction_id in self.world.faction_policies:
            if PolicyType.LIGHT_TAX in self.world.faction_policies[tile.faction_id]:
                tax = int(tax * 0.70)  # 税收-30%
        # 重税政策：税收+30%（由 faction 的 tax_policy 标记驱动）
        faction_obj = self.world.factions.get(tile.faction_id)
        if faction_obj and getattr(faction_obj, 'tax_policy', 'normal') == 'heavy':
            tax = int(tax * 1.30)  # 重税+30%
        return max(0, tax)

    def _calc_grain_consumption(self, tile: TileState) -> int:
        """计算粮草消耗（四季加成）"""
        troops_consume = int(tile.troops * 0.05)
        pop_consume = int(tile.population * 0.005)

        # 四季粮耗修正
        season_mult = 1.0
        if self.world.current_season == Season.WINTER:
            season_mult = 1.4   # 冬季取暖耗粮大增
        elif self.world.current_season == Season.SUMMER:
            season_mult = 1.1   # 夏季行军耗粮略增
        elif self.world.current_season == Season.SPRING:
            season_mult = 0.85  # 春季野菜补充，耗粮减少

        # 3.0: 国策粮耗修正（军屯养兵-15%）
        if tile.faction_id and tile.faction_id in self.world.faction_policies:
            if PolicyType.MILITARY_FARM in self.world.faction_policies[tile.faction_id]:
                season_mult *= 0.85  # 粮耗-15%

        return int((troops_consume + pop_consume) * season_mult)

    def _calc_population_change(self, tile: TileState, faction: FactionState) -> int:
        """计算人口自然增长/减少（四季加成）"""
        base_growth = int(tile.population * self.const["base_population_growth"])
        morale_bonus = (tile.morale - 50) * 0.005 * tile.population * 0.01
        water_bonus = int(tile.water_works * self.const["water_works_effect"] * tile.population * 0.01)
        clinic_bonus = int(tile.clinic * self.const["clinic_plague_reduction"] * tile.population * 0.01)

        # 民心≥75: 人口增长额外+5%（文档声明阈值，从 policy_system MORALE_THRESHOLDS 读取）
        from server.core.policy_system import MORALE_THRESHOLDS
        growth_threshold = MORALE_THRESHOLDS.get("growth_bonus", 75)
        if tile.morale >= growth_threshold:
            base_growth += int(tile.population * 0.05)

        # 四季人口修正
        season_mult = 1.0
        if self.world.current_season == Season.SPRING:
            season_mult = 1.6   # 春暖花开，人口恢复
        elif self.world.current_season == Season.AUTUMN:
            season_mult = 1.25  # 秋收丰足，人口增长
        elif self.world.current_season == Season.WINTER:
            season_mult = 0.5   # 严冬酷寒，人口增长停滞
        elif self.world.current_season == Season.SUMMER:
            season_mult = 0.85  # 酷暑略抑增长

        # 灾害影响
        disaster_penalty = 0
        for d in tile.disasters:
            if d == DisasterType.FLOOD:
                disaster_penalty -= int(tile.population * 0.05)
            elif d == DisasterType.DROUGHT:
                disaster_penalty -= int(tile.population * 0.03)
            elif d == DisasterType.LOCUST:
                disaster_penalty -= int(tile.population * 0.04)
            elif d == DisasterType.PLAGUE:
                disaster_penalty -= int(tile.population * 0.08)
            elif d == DisasterType.WAR_DEVASTATION:
                disaster_penalty -= int(tile.population * 0.02)

        # 流民
        if tile.morale < self.const["refugee_threshold_morale"]:
            refugee = int(tile.population * 0.03)
            disaster_penalty -= refugee
            # 触发流民潮事件（每个势力每回合最多1条，防止刷屏）
            if not hasattr(self.world, '_refugee_events_this_round'):
                self.world._refugee_events_this_round = set()
            event_key = f"{tile.faction_id}_refugee"  # 2026-07-15: 改为按势力去重，非按地块
            if event_key not in self.world._refugee_events_this_round:
                self.world._refugee_events_this_round.add(event_key)
                faction_name = faction.name if faction else "未知势力"
                # 统计该势力所有低民心地块
                low_morale_tiles = [t for t in self.world.get_faction_tiles(tile.faction_id) if t.morale < self.const["refugee_threshold_morale"]]
                total_refugee = sum(int(t.population * 0.03) for t in low_morale_tiles)
                tile_names = "、".join((t.tile_name or t.tile_id) for t in low_morale_tiles[:3])
                if len(low_morale_tiles) > 3:
                    tile_names += f"等{len(low_morale_tiles)}处"
                self.world.events_log.append({
                    "event_id": f"refugee_{tile.faction_id}_{self.world.current_round}",
                    "event_type": "refugee", "severity": "minor",  # 2026-07-15: major→minor，降低事件级别
                    "round": self.world.current_round,
                    "title": f"【流民潮】{faction_name}民心不稳",
                    "description": f"{faction_name}的{tile_names}民心低落，共{total_refugee}人流离失所。",
                    "effects": {"refugee_count": total_refugee, "affected_tiles": len(low_morale_tiles)},
                })

        # 3.0: 国策人口修正
        if tile.faction_id and tile.faction_id in self.world.faction_policies:
            policies = self.world.faction_policies[tile.faction_id]
            if PolicyType.LIGHT_TAX in policies:
                base_growth += int(tile.population * 0.02)  # 轻徭薄赋+2%
            if PolicyType.REWARD_FARM_WAR in policies:
                base_growth = int(base_growth * 0.90)  # 奖励耕战-10%

        change = int((base_growth + morale_bonus + water_bonus + clinic_bonus) * season_mult + disaster_penalty)
        return max(-int(tile.population * 0.1), min(int(tile.population * 0.05), change))

    def _trigger_disasters(self, result: dict):
        """随机触发天灾（四季特征）"""
        season = self.world.current_season
        disaster_index = self._calc_disaster_index()

        # 清理过期灾害
        for tile in self.world.tiles.values():
            tile.disasters = [d for d in tile.disasters if d != DisasterType.WAR_DEVASTATION]

        # 全局灾害概率（四季修正）
        base_prob = disaster_index * 0.01
        if season == Season.SUMMER:
            base_prob *= 1.5   # 夏季洪水/蝗灾高发
        elif season == Season.WINTER:
            base_prob *= 0.7   # 冬季灾害较少
        elif season == Season.SPRING:
            base_prob *= 0.85  # 春季融雪可能引发小灾
        # 秋季灾害概率不变

        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            if random.random() < base_prob * 0.3:
                disaster = self._pick_disaster(tile, season)
                if disaster and disaster not in tile.disasters:
                    tile.disasters.append(disaster)
                    result["disasters_triggered"].append({
                        "tile_id": tile.tile_id,
                        "disaster": disaster.value,
                        "tile_name": tile.tile_name,
                    })

    def _pick_disaster(self, tile: TileState, season: Season) -> Optional[DisasterType]:
        """根据地块类型和季节选择灾害（四季特征化）"""
        weights = {
            DisasterType.FLOOD: 0.15,
            DisasterType.DROUGHT: 0.12,
            DisasterType.LOCUST: 0.08,
            DisasterType.PLAGUE: 0.05,
        }

        # 地块类型修正
        if tile.tile_type == TileType.COAST or tile.tile_type == TileType.PORT:
            weights[DisasterType.FLOOD] = 0.25
        if tile.tile_type == TileType.MOUNTAIN:
            weights[DisasterType.DROUGHT] = 0.18
        if tile.tile_type == TileType.CITY:
            weights[DisasterType.PLAGUE] = 0.10

        # 四季灾害权重修正
        if season == Season.SPRING:
            weights[DisasterType.FLOOD] *= 1.3    # 春汛融雪
            weights[DisasterType.LOCUST] *= 0.7   # 蝗虫尚未孵化
        elif season == Season.SUMMER:
            weights[DisasterType.FLOOD] *= 1.6    # 夏季暴雨洪水
            weights[DisasterType.LOCUST] *= 1.4   # 蝗虫活跃
            weights[DisasterType.PLAGUE] *= 1.3   # 瘟疫易传播
            weights[DisasterType.DROUGHT] *= 1.15 # 伏旱
        elif season == Season.AUTUMN:
            weights[DisasterType.LOCUST] *= 1.2   # 秋蝗收尾
            weights[DisasterType.FLOOD] *= 0.8    # 秋雨渐少
            weights[DisasterType.PLAGUE] *= 0.85  # 瘟疫渐息
        elif season == Season.WINTER:
            weights[DisasterType.DROUGHT] *= 0.5  # 冬季少旱
            weights[DisasterType.FLOOD] *= 0.3    # 冬季少洪
            weights[DisasterType.LOCUST] *= 0.2   # 蝗虫蛰伏
            weights[DisasterType.PLAGUE] *= 1.1   # 伤寒多发

        total = sum(weights.values())
        r = random.random() * total
        cumulative = 0
        for d, w in weights.items():
            cumulative += w
            if r <= cumulative:
                return d
        return None

    # ================================================================
    # ⑥ 刷新世界
    # ================================================================

    def phase_refresh_world(self) -> dict:
        """完整执行世界刷新阶段"""
        result = {
            "disaster_index": 0,
            "treaties_expired": [],
            "trade_updated": [],
            "power_ranking": [],
            "faction_updates": {},
        }

        # 灾厄指数
        result["disaster_index"] = self._calc_disaster_index()
        self.world.disaster_index = result["disaster_index"]

        # 条约过期检测
        for treaty in self.world.alliance_treaties:
            if treaty.expires_round > 0 and self.world.current_round >= treaty.expires_round:
                result["treaties_expired"].append(treaty.treaty_id)

        # 贸易路线更新
        for key, rel in self.world.relations.items():
            if rel.trade_active and rel.stance == DiplomaticStance.WAR:
                rel.trade_active = False
                result["trade_updated"].append(key)

        # 势力排名
        result["power_ranking"] = self._calc_power_ranking()

        # 势力状态刷新
        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue
            tiles = self.world.get_faction_tiles(fid)
            # Bug #16修复: 无领地势力标记灭亡，清理其官员
            if not tiles and faction.is_alive:
                faction.is_alive = False
                logger.info(f"势力 {faction.name}({fid}) 失去全部领地，标记为灭亡")
                # 清理该势力所有官员
                orphan_officials = [
                    oid for oid, off in self.world.officials.items()
                    if off.faction_id == fid
                ]
                for oid in orphan_officials:
                    del self.world.officials[oid]
                if fid in self.world.factions:
                    self.world.factions[fid].officials.clear()
                continue
            avg_morale = sum(t.morale for t in tiles) / max(1, len(tiles))
            faction.realm_stability = int(avg_morale * 0.7 + faction.court_stability * 0.3)
            faction.realm_stability = max(0, min(100, faction.realm_stability))

            # debuff 效果
            for d in faction.debuffs:
                if "民心" in d.get("name", ""):
                    faction.realm_stability = max(0, faction.realm_stability - 2)
                if "朝堂" in d.get("name", "") or "腐败" in d.get("name", ""):
                    faction.court_stability = max(0, faction.court_stability - 2)

            result["faction_updates"][fid] = {
                "realm_stability": faction.realm_stability,
                "court_stability": faction.court_stability,
                "tile_count": len(tiles),
            }

        # 清理过期条约
        expired_ids = set(result["treaties_expired"])
        self.world.alliance_treaties = [
            t for t in self.world.alliance_treaties
            if t.treaty_id not in expired_ids
        ]

        # ================================================================
        # 3.2 高级功能：叛军行动、移民、海盗、官员俸禄、围堵
        # ================================================================
        result["advanced_features"] = self._run_advanced_features()

        return result

    def _run_advanced_features(self) -> dict:
        """执行所有高级每回合功能"""
        from server.core.advanced_features import (
            RebelEngine, WorldAdvancedEngine,
            OfficialAdvancedEngine, AdvancedDiplomacyEngine,
        )

        result = {}

        # 叛军行动
        rebel_engine = RebelEngine(self.world, self.const)
        if self.world.rebel_armies:
            result["rebel_actions"] = rebel_engine.rebel_tick()

        # 移民/流民迁徙
        world_engine = WorldAdvancedEngine(self.world, self.const)
        result["migration"] = world_engine.process_migration()

        # 海盗
        result["piracy"] = world_engine.check_piracy()

        # 官员俸禄
        official_engine = OfficialAdvancedEngine(self.world, self.const)
        result["salaries"] = official_engine.pay_salaries()

        # 围堵机制
        diplo_engine = AdvancedDiplomacyEngine(self.world, self.const)
        result["encircle"] = diplo_engine.apply_encircle_penalty()

        return result

    def _generate_weather(self):
        """生成当前回合天气（存储在 world.weather 中，影响农业/行军/事件）"""
        season = self.world.current_season
        disaster_index = self._calc_disaster_index()

        # 基础天气概率分布（各季节不同）
        weather_pool = []
        if season == Season.SPRING:
            weather_pool = [
                ("晴", 0.30), ("多云", 0.20), ("阴", 0.15),
                ("小雨", 0.15), ("大风", 0.10), ("雷雨", 0.05), ("霜冻", 0.05),
            ]
        elif season == Season.SUMMER:
            weather_pool = [
                ("晴", 0.25), ("多云", 0.15), ("阴", 0.10),
                ("雷雨", 0.20), ("暴雨", 0.10), ("大风", 0.10), ("酷热", 0.10),
            ]
        elif season == Season.AUTUMN:
            weather_pool = [
                ("晴", 0.35), ("多云", 0.25), ("阴", 0.15),
                ("小雨", 0.10), ("大风", 0.10), ("霜冻", 0.05),
            ]
        else:  # WINTER
            weather_pool = [
                ("晴", 0.20), ("多云", 0.15), ("阴", 0.15),
                ("小雪", 0.20), ("大雪", 0.10), ("大风", 0.10), ("酷寒", 0.10),
            ]

        # 灾厄指数修正：灾难越高，恶劣天气概率越大
        if disaster_index > 40:
            bad_weather_bonus = (disaster_index - 40) * 0.005
            for i, (name, weight) in enumerate(weather_pool):
                if name not in ("晴", "多云"):
                    weather_pool[i] = (name, weight + bad_weather_bonus)

        # 随机选择天气
        names = [w[0] for w in weather_pool]
        weights = [w[1] for w in weather_pool]
        total = sum(weights)
        if total <= 0:
            total = 1.0  # 防止除零
        normalized = [w / total for w in weights]
        weather_type = random.choices(names, weights=normalized, k=1)[0]

        # 计算天气效果系数
        effects = self._calc_weather_effects(weather_type, season)

        self.world.weather = {
            "type": weather_type,
            "season": season.value,
            "effects": effects,
            "disaster_index": disaster_index,
        }

    def _calc_weather_effects(self, weather_type: str, season: Season) -> dict:
        """计算天气对各系统的影响系数"""
        effects = {
            "agriculture": 1.0,   # 农业产出倍率
            "march_speed": 1.0,   # 行军速度倍率
            "trade": 1.0,         # 贸易收入倍率
            "morale": 0,          # 民心修正
            "troop_attrition": 0, # 额外兵力损耗
        }

        if weather_type in ("晴", "多云"):
            effects["agriculture"] = 1.05
            effects["march_speed"] = 1.0
            effects["trade"] = 1.05
            effects["morale"] = 2
        elif weather_type == "阴":
            effects["agriculture"] = 0.95
            effects["march_speed"] = 1.0
            effects["trade"] = 0.95
            effects["morale"] = 0
        elif weather_type in ("小雨", "小雪"):
            effects["agriculture"] = 1.1 if weather_type == "小雨" else 0.85
            effects["march_speed"] = 0.9
            effects["trade"] = 0.9
            effects["morale"] = 1 if weather_type == "小雨" else -1
        elif weather_type in ("雷雨", "暴雨", "大雪"):
            effects["agriculture"] = 0.7
            effects["march_speed"] = 0.5
            effects["trade"] = 0.5
            effects["morale"] = -3
            effects["troop_attrition"] = 5 if weather_type == "大雪" else 3
        elif weather_type in ("大风",):
            effects["agriculture"] = 0.85
            effects["march_speed"] = 0.7
            effects["trade"] = 0.6
            effects["morale"] = -1
        elif weather_type in ("酷热", "酷寒"):
            effects["agriculture"] = 0.6
            effects["march_speed"] = 0.6
            effects["trade"] = 0.7
            effects["morale"] = -5
            effects["troop_attrition"] = 8 if weather_type == "酷寒" else 5
        elif weather_type == "霜冻":
            effects["agriculture"] = 0.75
            effects["march_speed"] = 0.85
            effects["trade"] = 0.85
            effects["morale"] = -2

        return effects

    def _calc_disaster_index(self) -> int:
        """计算全局灾厄指数 (0-100)"""
        total = 0
        count = 0
        for tile in self.world.tiles.values():
            if tile.disasters:
                total += len(tile.disasters) * 20
                if DisasterType.PLAGUE in tile.disasters:
                    total += 15
                if DisasterType.FLOOD in tile.disasters:
                    total += 10
            count += 1
        avg = total / max(1, count)
        # 叠加季节因素
        if self.world.current_season == Season.WINTER:
            avg *= 0.6
        return min(100, int(avg))

    def _calc_power_ranking(self) -> list[dict]:
        """计算势力实力排名"""
        scores = []
        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue
            tiles = self.world.get_faction_tiles(fid)
            score = (
                faction.total_troops * 0.3
                + faction.total_population * 0.001 * 0.2
                + faction.treasury * 0.0005
                + faction.grain * 0.01
                + len(tiles) * 50
                + faction.realm_stability * 3
                + faction.court_stability * 2
            )
            scores.append({
                "faction_id": fid,
                "name": faction.name,
                "score": int(score),
                "tiles": len(tiles),
                "troops": faction.total_troops,
            })
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores


# ================================================================
# 行军/战斗引擎
# ================================================================

class MarchEngine:
    """行军与战斗引擎（增强版：围城逻辑 + 战斗事件 + 俘虏 + 邻接地块查询）"""

    # Axial 六边形6个邻居方向
    _HEX_DIRECTIONS = [
        (+1, 0), (+1, -1), (0, -1),
        (-1, 0), (-1, +1), (0, +1),
    ]

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**DEFAULTS, **(game_const or {})}

    # ================================================================
    # 行军与战斗
    # ================================================================

    def resolve_march(self, from_tile: str, to_tile: str, troops: int,
                      attacker_faction: str, grain: int = 0) -> dict:
        """行军路径计算与战斗结算（v3.0：多段路径 + 战争分数联动）"""
        result = {
            "success": False,
            "path": [],
            "path_details": [],
            "turns_required": 0,
            "battle_result": None,
            "message": "",
            "event_id": None,
            "is_siege": False,
            "siege_id": None,
            "captured_prisoners": [],
            "grain_consumed": 0,
            "war_score_updated": False,
        }

        from_t = self.world.get_tile(from_tile)
        to_t = self.world.get_tile(to_tile)
        if not from_t or not to_t:
            result["message"] = "地块不存在"
            return result

        if from_t.faction_id != attacker_faction:
            result["message"] = "出发地块不属于你方"
            return result

        if troops <= 0 or troops > from_t.troops:
            result["message"] = f"兵力不足（可调遣：{from_t.troops}）"
            return result

        # ====== v3.0: 多段路径计算 ======
        path = [from_tile, to_tile]  # 默认直达
        total_cost = 1.0
        path_details = []

        # 如果不是邻接，尝试 BFS 寻路
        neighbors = self._get_neighbor_set(from_tile)
        if to_tile not in neighbors:
            try:
                from server.map.pathfinding import a_star_pathfind
                terrain_costs = {
                    str(TileType.MOUNTAIN.value): 2.5,
                    "mountain": 2.5,
                    str(TileType.WATER.value): 2.0,
                    "water": 2.0,
                    str(TileType.DESERT.value): 1.6,
                    "desert": 1.6,
                    str(TileType.GRASSLAND.value): 0.9,
                    "grassland": 0.9,
                    str(TileType.PLAIN.value): 1.0,
                    "plain": 1.0,
                }
                blocked = set()
                for tid, t in self.world.tiles.items():
                    if t.faction_id and t.faction_id != attacker_faction:
                        # Bug #13修复: 非己方地块标记为阻挡，防止穿越敌方领土
                        blocked.add(self._tile_id_to_hex(tid))

                pf_result = a_star_pathfind(
                    start_coord=self._tile_id_to_hex(from_tile),
                    end_coord=self._tile_id_to_hex(to_tile),
                    blocked=blocked,
                    move_costs=terrain_costs,
                )
                if pf_result.path and len(pf_result.path) > 1:
                    path = [self._hex_to_tile_id(h) for h in pf_result.path]
                    total_cost = pf_result.cost
            except Exception as e:
                logger.debug(f"[March] 多段寻路失败，回退直达: {e}")

        # 构建路径详情
        for tid in path:
            t = self.world.tiles.get(tid)
            path_details.append({
                "tile_id": tid,
                "tile_name": t.tile_name if t else tid,
                "faction_id": t.faction_id if t else "",
            })
        result["path"] = path
        result["path_details"] = path_details

        terrain_mult = {
            TileType.MOUNTAIN: 2.0,
            TileType.WATER: 1.5,
            TileType.DESERT: 1.3,
            TileType.GRASSLAND: 0.9,
        }.get(to_t.tile_type, 1.0)
        result["turns_required"] = max(1, int(total_cost * terrain_mult))

        # 粮草消耗（优先使用前端传入的 grain 参数）
        grain_cost = int(troops * self.const["logistics_base_attrition"] * total_cost)
        grain_to_consume = grain if grain > 0 else grain_cost
        if from_t.grain < grain_to_consume:
            result["message"] = f"粮草不足（需要：{grain_to_consume}，现有：{from_t.grain}）"
            return result

        # Bug #9 修复: 记录初始状态用于异常回滚
        _initial_from_troops = from_t.troops
        _initial_from_grain = from_t.grain
        try:
            from_t.grain -= grain_to_consume
            result["grain_consumed"] = grain_to_consume
            from_t.troops = max(0, from_t.troops - troops)  # Bug #10修复: 防止负数兵力

            # 战斗结算
            if to_t.faction_id and to_t.faction_id != attacker_faction:
                # 3.2: 自动将外交关系设为战争状态（通过行军攻击即视为宣战）
                self._ensure_war_stance(attacker_faction, to_t.faction_id)

                # 围城判定：守军远多于攻军且城防较高时进入围城
                siege_threshold = self.const["siege_troops_ratio_threshold"]
                fort_threshold = self.const["siege_fortification_threshold"]
                if to_t.troops > troops * siege_threshold and to_t.fortification >= fort_threshold:
                    # 进入围城状态
                    result = self._enter_siege(from_t, to_t, troops, attacker_faction, result, grain=grain)
                    return result

                battle = self._resolve_battle(
                    attacker_faction, to_t.faction_id, troops,
                    to_t.troops, to_t.tile_type, to_t.fortification,
                )
                result["battle_result"] = battle

            # 创建 BattleEvent 记录
            event_id = self._create_battle_event(
                attacker_faction, to_t.faction_id, to_t.tile_id, to_t.tile_name,
                troops, to_t.troops, battle, to_t.tile_type.value if hasattr(to_t.tile_type, 'value') else str(to_t.tile_type),
                is_siege=False,
            )
            result["event_id"] = event_id

            if battle["winner"] == attacker_faction:
                # 占领
                old_faction = to_t.faction_id
                old_faction_name = ""
                if old_faction:
                    old_f = self.world.get_faction(old_faction)
                    old_faction_name = old_f.name if old_f else old_faction
                new_f = self.world.get_faction(attacker_faction)
                new_faction_name = new_f.name if new_f else attacker_faction

                to_t.faction_id = attacker_faction
                to_t.troops = battle["attacker_remaining"]
                to_t.morale = max(10, to_t.morale - 20)
                to_t.siege_state = None

                # v3.0: 汇报战争分数（攻占地块）
                self._report_war_score(
                    attacker_faction, old_faction,
                    is_victory=True, is_capital=to_t.is_capital,
                    tile_name=to_t.tile_name, troops=troops,
                    round_num=self.world.current_round,
                )

                # 声望与民心调整：攻城略地，威震天下
                if new_f:
                    new_f.reputation = min(100, new_f.reputation + 2)
                if old_f:
                    old_f.reputation = max(0, old_f.reputation - 3)
                    old_f.realm_stability = max(0, old_f.realm_stability - 5)

                # 记录地盘变更
                self._record_tile_change(
                    tile=to_t,
                    old_faction_id=old_faction,
                    new_faction_id=attacker_faction,
                    old_faction_name=old_faction_name,
                    new_faction_name=new_faction_name,
                    change_type="conquer",
                    troops_involved=troops,
                    battle_result="victory",
                )

                # 首都战利品
                if to_t.is_capital:
                    faction = self.world.get_faction(attacker_faction)
                    if faction:
                        faction.treasury += self.const["capital_loot_treasury"]
                        faction.grain += self.const["capital_loot_grain"]
                        result["message"] = f"攻占都城{to_t.tile_name}！缴获银{self.const['capital_loot_treasury']}两、粮{self.const['capital_loot_grain']}石"

                # 俘虏捕获
                prisoners = self._capture_prisoners(old_faction, attacker_faction)
                result["captured_prisoners"] = prisoners

                # field_recruiter 特技：就地征募降卒
                field_recruiter_active = False
                try:
                    # 检查进攻方是否有拥有field_recruiter特技的武将
                    from server.core.general_engine import GeneralEngine
                    ge = GeneralEngine(self.world)
                    atk_generals = ge.get_faction_generals(attacker_faction)
                    for g in atk_generals:
                        for t in g.tactics:
                            if t.value == "field_recruiter":
                                field_recruiter_active = True
                                break
                        if field_recruiter_active:
                            break
                except Exception as e:
                    logger.debug(f"[Settle] field_recruiter特技检查失败（非致命）: {e}", exc_info=True)
                    pass

                if field_recruiter_active:
                    captured_troops = int(battle.get("defender_losses", 0) * 0.25)
                    if captured_troops > 0:
                        to_t.troops += captured_troops
                        result["field_recruiter_troops"] = captured_troops
                        result["message"] = (result.get("message", "") +
                            f" 就地征募降卒{captured_troops}人")

                result["success"] = True
                result["tile_captured"] = True
                result["tile_name"] = to_t.tile_name
                result["old_faction"] = old_faction_name
                result["new_faction"] = new_faction_name
                result["diplomacy_changed"] = True  # 3.2: 标记外交关系已变更
                result["new_stance"] = "war"
                if not result["message"]:
                    result["message"] = f"攻占{to_t.tile_name}！"
                else:
                    # 战败或平局处理
                    from_t.troops += battle["attacker_remaining"]
                    # 更新守方剩余兵力（修复平局时守方损失未生效的bug）
                    battle_def_remaining = battle.get("defender_remaining", 0)
                    if battle_def_remaining >= 0:
                        to_t.troops = battle_def_remaining

                    loser = attacker_faction
                    if battle["winner"]:
                        loser = attacker_faction if battle["winner"] != attacker_faction else to_t.faction_id

                    # v3.0: 汇报战争分数（战败/平局）
                    win_faction = battle["winner"] if battle["winner"] else None
                    is_defeat = win_faction and win_faction != attacker_faction
                    self._report_war_score(
                        attacker_faction, to_t.faction_id,
                        is_victory=False, is_defeat=is_defeat,
                        tile_name=to_t.tile_name, troops=troops,
                        round_num=self.world.current_round,
                    )

                    if battle["winner"] is None:
                        result["message"] = f"进攻{to_t.tile_name}未分胜负，残兵退回。"
                    else:
                        result["message"] = f"进攻{to_t.tile_name}失败，残兵退回。"

                    # 战败声望惩罚
                    atk_f = self.world.get_faction(attacker_faction)
                    if atk_f:
                        atk_f.reputation = max(0, atk_f.reputation - 2)
                        atk_f.realm_stability = max(0, atk_f.realm_stability - 3)
            else:
                # 无主或同势力地块
                to_t.troops += troops
                if not to_t.faction_id:
                    old_faction_id = ""
                    new_f = self.world.get_faction(attacker_faction)
                    new_faction_name = new_f.name if new_f else attacker_faction
                    to_t.faction_id = attacker_faction
                    # 记录开拓
                    self._record_tile_change(
                        tile=to_t,
                        old_faction_id="",
                        new_faction_id=attacker_faction,
                        old_faction_name="无人区",
                        new_faction_name=new_faction_name,
                        change_type="settle",
                        troops_involved=troops,
                        battle_result="peaceful",
                    )
                    result["tile_captured"] = True
                    result["tile_name"] = to_t.tile_name
                    result["old_faction"] = "无人区"
                    result["new_faction"] = new_faction_name
                result["success"] = True
                result["message"] = f"抵达{to_t.tile_name}。"

        except Exception:
            # Bug #9修复: 异常时回滚兵力与粮草
            from_t.troops = _initial_from_troops
            from_t.grain = _initial_from_grain
            logger.error(f"[Settle] 行军结算异常，已回滚兵力与粮草: {from_tile} -> {to_tile}", exc_info=True)
            raise

        return result

    def _ensure_war_stance(self, faction_a: str, faction_b: str):
        """3.2: 确保两方外交关系为战争状态（行军攻击自动宣战）
        
        当一方攻击另一方地块时，自动将双方关系设为 war。
        同时清理同盟、联邦、附庸、贸易等非战争关系。
        """
        if faction_a == faction_b:
            return
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            return
        # 如果已经是战争状态则跳过
        if rel.stance == DiplomaticStance.WAR:
            return

        old_stance = rel.stance.value
        # 记录外交变更
        logger.info(f"[行军宣战] {faction_a} 攻击 {faction_b} 地块，外交状态 {old_stance} → war")

        # 设为战争状态
        rel.stance = DiplomaticStance.WAR
        rel.attitude = -50
        rel.trade_active = False
        # 退出联邦
        if rel.coalition_id:
            self._remove_from_coalition_stub(faction_a, rel.coalition_id)
            self._remove_from_coalition_stub(faction_b, rel.coalition_id)
            rel.coalition_id = ""
        # 取消附庸关系
        self._cancel_vassal_stub(faction_a, faction_b)

        # 记录外交日志
        self.world.diplomatic_archive.append({
            "round": self.world.current_round,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "faction_a": faction_a,
            "faction_b": faction_b,
            "from": old_stance,
            "to": "war",
            "reason": f"{faction_a}出兵攻打{faction_b}，自动宣战",
        })

        # 添加战争事件
        fa_name = faction_a
        fb_name = faction_b
        fa = self.world.get_faction(faction_a)
        fb = self.world.get_faction(faction_b)
        if fa:
            fa_name = fa.name
        if fb:
            fb_name = fb.name
        self.world.events_log.append({
            "event_id": f"war_auto_{faction_a}_{faction_b}_{self.world.current_round}",
            "event_type": "diplomacy",
            "severity": "critical",
            "round": self.world.current_round,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "title": f"【宣战】{fa_name} 与 {fb_name} 进入战争状态",
            "description": f"{fa_name}出兵攻打{fb_name}，两国关系由{old_stance}转为交战。",
            "faction_id": faction_a,
            "effects": {"from_stance": old_stance, "to_stance": "war", "auto_war": True},
        })

    # ================================================================
    # v3.0: 战争分数联动 + 多段路径辅助
    # ================================================================

    def _report_war_score(self, attacker: str, defender: str, *,
                          is_victory: bool = True, is_defeat: bool = False,
                          is_capital: bool = False, tile_name: str = "",
                          troops: int = 0, round_num: int = 0):
        """向 WarOrchestrator 汇报战争分数变化"""
        try:
            # 获取 orchestrator（通过 world 的 round_engine 引用）
            orchestrator = None
            if hasattr(self.world, '_round_engine') and self.world._round_engine:
                reng = self.world._round_engine
                if hasattr(reng, '_war_orchestrator'):
                    orchestrator = reng._war_orchestrator
            if not orchestrator:
                return

            if is_victory:
                # 占领地块
                source = "occupied_capital" if is_capital else "occupied_tile"
                base_value = 25.0 if is_capital else 8.0
                desc = f"攻占{'都城' if is_capital else ''}{tile_name}"
            elif is_defeat:
                source = "battle_defeat"
                base_value = -12.0
                desc = f"进攻{tile_name}失败"
            else:
                source = "battle_defeat"
                base_value = -5.0
                desc = f"进攻{tile_name}未分胜负"

            orchestrator.record_war_score_event(
                attacker=attacker,
                defender=defender,
                source=source,
                base_value=base_value,
                round_num=round_num,
                description=desc,
                tile_id=tile_name,
                troops=troops,
            )
        except Exception as e:
            logger.debug(f"[WarScore] 汇报失败（非致命）: {e}")

    def _get_neighbor_set(self, tile_id: str) -> set:
        """获取地块的邻接 ID 集合"""
        neighbors = set()
        tile = self.world.tiles.get(tile_id)
        if not tile:
            return neighbors
        # 尝试邻接矩阵
        if hasattr(self.world, 'adjacency') and self.world.adjacency:
            neighbors.update(self.world.adjacency.get(tile_id, []))
        # 回退：六边形坐标
        if not neighbors and hasattr(tile, 'col') and hasattr(tile, 'row'):
            for dq, dr in self._HEX_DIRECTIONS:
                n_key = f"hex_{tile.col + dq}_{tile.row + dr}"
                if n_key in self.world.tiles:
                    neighbors.add(n_key)
        return neighbors

    @staticmethod
    def _tile_id_to_hex(tile_id: str):
        """tile_id → (col, row). 支持 \"q,r\" 和 \"hex_q_r\" 两种格式"""
        from collections import namedtuple
        HexCoord = namedtuple('HexCoord', ['q', 'r'])
        try:
            raw = str(tile_id).replace("hex_", "")
            if "," in raw:
                parts = raw.split(",")
            else:
                parts = raw.split("_")
            return HexCoord(q=int(parts[0]), r=int(parts[1]))
        except (ValueError, IndexError):
            import logging
            _log = logging.getLogger(__name__)
            _log.warning(f"[Settle] tile_id解析失败，回退到(0,0): {tile_id}")
            return HexCoord(q=0, r=0)

    @staticmethod
    def _hex_to_tile_id(coord) -> str:
        """(q, r) → tile_id (逗号分隔格式)"""
        return f"{coord.q},{coord.r}"

    def _remove_from_coalition_stub(self, faction_id: str, coalition_id: str):
        """从联邦中移除势力（简化版，供 MarchEngine 内部使用）"""
        if coalition_id and coalition_id in self.world.coalitions:
            members = self.world.coalitions[coalition_id]
            if faction_id in members:
                members.remove(faction_id)
            if len(members) < 2:
                del self.world.coalitions[coalition_id]

    def _cancel_vassal_stub(self, faction_a: str, faction_b: str):
        """取消两方之间的附庸关系（简化版）"""
        for vassal, suzerain in list(self.world.vassal_relations.items()):
            if (vassal == faction_a and suzerain == faction_b) or \
               (vassal == faction_b and suzerain == faction_a):
                del self.world.vassal_relations[vassal]

    def _enter_siege(self, from_t: TileState, to_t: TileState, troops: int,
                     attacker_faction: str, result: dict, grain: int = 0) -> dict:
        """进入围城状态"""
        # 检查攻方粮草（围城至少需要 troops * 0.5 的粮草储备）
        faction = self.world.get_faction(attacker_faction)
        min_grain_needed = int(troops * self.const.get("siege_min_grain_per_troop", 0.5))
        if faction and faction.grain < min_grain_needed:
            result["success"] = False
            result["message"] = f"粮草不足，无法围城（需要{min_grain_needed}，当前{faction.grain}）"
            return result

        siege_id = f"siege_{attacker_faction}_{to_t.tile_id}_{self.world.current_round}"
        siege_record = SiegeRecord(
            siege_id=siege_id,
            attacker_faction=attacker_faction,
            defender_faction=to_t.faction_id,
            tile_id=to_t.tile_id,
            siege_rounds=0,
            attacker_troops=troops,
            defender_troops=to_t.troops,
            wall_damage=0.0,
        )
        self.world.siege_states[siege_id] = siege_record
        to_t.siege_state = SiegeState.SIEGING
        to_t.sieging_faction = attacker_faction  # Bug #12修复: 标记围城部队归属

        result["is_siege"] = True
        result["siege_id"] = siege_id
        result["success"] = True
        result["diplomacy_changed"] = True  # 3.2: 围城也自动宣战
        result["new_stance"] = "war"
        result["message"] = f"已开始围困{to_t.tile_name}（守军{to_t.troops}，城防{to_t.fortification}级）"

        # 创建围城事件
        event_id = self._create_battle_event(
            attacker_faction, to_t.faction_id, to_t.tile_id, to_t.tile_name,
            troops, to_t.troops,
            {"winner": None, "attacker_losses": 0, "defender_losses": 0,
             "attacker_remaining": troops, "defender_remaining": to_t.troops},
            to_t.tile_type.value if hasattr(to_t.tile_type, 'value') else str(to_t.tile_type),
            is_siege=True,
        )
        result["event_id"] = event_id
        return result

    def resolve_siege(self, siege_id: str) -> dict:
        """处理围城结算：每回合消耗守军粮食，降低城防，可能触发投降"""
        siege = self.world.siege_states.get(siege_id)
        if not siege:
            return {"success": False, "message": "围城记录不存在"}

        tile = self.world.get_tile(siege.tile_id)
        if not tile:
            self._end_siege(siege_id)
            return {"success": False, "message": "围城目标地块不存在"}

        siege.siege_rounds += 1

        # 守军消耗
        grain_loss = int(tile.grain * self.const["siege_grain_consumption_per_round"])
        tile.grain = max(0, tile.grain - grain_loss)

        # 城墙损伤
        siege.wall_damage += self.const["siege_wall_damage_per_round"]
        tile.fortification = max(0, tile.fortification - int(siege.wall_damage))

        # 守军减员
        def_loss = int(siege.defender_troops * self.const["siege_defender_attrition"])
        siege.defender_troops = max(0, siege.defender_troops - def_loss)
        tile.troops = siege.defender_troops

        # 攻方减员
        atk_loss = int(siege.attacker_troops * self.const["siege_attacker_attrition"])
        siege.attacker_troops = max(1, siege.attacker_troops - atk_loss)

        # 投降判定
        morale_threshold = self.const["siege_surrender_morale_threshold"]
        if tile.morale <= morale_threshold or tile.grain <= 0:
            old_faction = tile.faction_id
            old_faction_name = ""
            if old_faction:
                old_f = self.world.get_faction(old_faction)
                old_faction_name = old_f.name if old_f else old_faction
            new_f = self.world.get_faction(siege.attacker_faction)
            new_faction_name = new_f.name if new_f else siege.attacker_faction

            tile.faction_id = siege.attacker_faction
            tile.troops = siege.attacker_troops
            tile.siege_state = None
            tile.morale = max(10, tile.morale - 20)
            self._end_siege(siege_id)

            # 记录地盘变更
            self._record_tile_change(
                tile=tile,
                old_faction_id=old_faction,
                new_faction_id=siege.attacker_faction,
                old_faction_name=old_faction_name,
                new_faction_name=new_faction_name,
                change_type="conquer",
                troops_involved=siege.attacker_troops,
                battle_result="victory",
            )

            # 战斗事件
            self._create_battle_event(
                siege.attacker_faction, old_faction, tile.tile_id, tile.tile_name,
                siege.attacker_troops, 0,
                {"winner": siege.attacker_faction, "attacker_losses": atk_loss,
                 "defender_losses": def_loss, "attacker_remaining": siege.attacker_troops,
                 "defender_remaining": 0},
                tile.tile_type.value if hasattr(tile.tile_type, 'value') else str(tile.tile_type),
                is_siege=True,
            )
            # 破城战利品：任意城池破城有基础奖励，首都翻倍
            attacker_f = self.world.get_faction(siege.attacker_faction)
            if attacker_f:
                loot_t = self.const["capital_loot_treasury"]
                loot_g = self.const["capital_loot_grain"]
                if tile.is_capital:
                    attacker_f.treasury += loot_t
                    attacker_f.grain += loot_g
                else:
                    attacker_f.treasury += loot_t // 2
                    attacker_f.grain += loot_g // 2
            return {"success": True, "message": f"围城{ siege.siege_rounds}回合，{tile.tile_name}投降！",
                    "surrendered": True, "tile_captured": True, "tile_name": tile.tile_name,
                    "old_faction": old_faction_name, "new_faction": new_faction_name}

        # 城墙破损后可强攻（城墙破损率：当前城防 <= 原始城防 * breach_threshold 即可强攻）
        breach_threshold = self.const["siege_breach_fortification_threshold"]
        # fortification 基础值为 5，breach_threshold=0.3 表示城防降到原始值的 30% 以下
        if tile.fortification <= self.const["siege_fortification_threshold"] * breach_threshold:
            battle = self._resolve_battle(
                siege.attacker_faction, siege.defender_faction,
                siege.attacker_troops, siege.defender_troops,
                tile.tile_type, max(0, tile.fortification),
            )
            if battle["winner"] == siege.attacker_faction:
                old_faction = tile.faction_id
                old_faction_name = ""
                if old_faction:
                    old_f = self.world.get_faction(old_faction)
                    old_faction_name = old_f.name if old_f else old_faction
                new_f = self.world.get_faction(siege.attacker_faction)
                new_faction_name = new_f.name if new_f else siege.attacker_faction

                tile.faction_id = siege.attacker_faction
                tile.troops = battle["attacker_remaining"]
                tile.siege_state = None
                self._end_siege(siege_id)

                # 记录地盘变更
                self._record_tile_change(
                    tile=tile,
                    old_faction_id=old_faction,
                    new_faction_id=siege.attacker_faction,
                    old_faction_name=old_faction_name,
                    new_faction_name=new_faction_name,
                    change_type="conquer",
                    troops_involved=siege.attacker_troops,
                    battle_result="victory",
                )

                self._create_battle_event(
                    siege.attacker_faction, siege.defender_faction, tile.tile_id, tile.tile_name,
                    siege.attacker_troops, siege.defender_troops, battle,
                    tile.tile_type.value if hasattr(tile.tile_type, 'value') else str(tile.tile_type),
                    is_siege=False,
                )
                # 强攻破城战利品
                attacker_f = self.world.get_faction(siege.attacker_faction)
                if attacker_f:
                    loot_t = self.const["capital_loot_treasury"]
                    loot_g = self.const["capital_loot_grain"]
                    if tile.is_capital:
                        attacker_f.treasury += loot_t
                        attacker_f.grain += loot_g
                    else:
                        attacker_f.treasury += loot_t // 2
                        attacker_f.grain += loot_g // 2
                return {"success": True, "message": f"城墙破损，强攻成功，占领{tile.tile_name}！",
                        "tile_captured": True, "tile_name": tile.tile_name,
                        "old_faction": old_faction_name, "new_faction": new_faction_name}

        return {"success": True, "message": f"围城第{siege.siege_rounds}回合，守军{tile.troops}，城防{tile.fortification}",
                "siege_rounds": siege.siege_rounds}

    def _end_siege(self, siege_id: str):
        """结束围城，重置城墙累积损伤"""
        siege = self.world.siege_states.get(siege_id)
        if siege:
            tile = self.world.get_tile(siege.tile_id)
            if tile:
                tile.siege_state = None
                tile.sieging_faction = None
            # 重置 wall_damage 防止下次围城继承累积损伤
            siege.wall_damage = 0.0
        if siege_id in self.world.siege_states:
            del self.world.siege_states[siege_id]

    def _resolve_battle(self, attacker_fid: str, defender_fid: str,
                        atk_troops: int, def_troops: int,
                        terrain: TileType, fortification: int,
                        attacker_general: Optional[object] = None,
                        defender_general: Optional[object] = None,
                        atk_unit_comp: Optional[dict] = None,
                        def_unit_comp: Optional[dict] = None,
                        atk_formation: Optional[object] = None,
                        def_formation: Optional[object] = None,
                        ) -> dict:
        """战斗结算算法（四季修正 + 可选UnitCounterEngine增强）
        
        v3.2: 当传入武将/兵种/阵型数据时，使用 UnitCounterEngine 进行兵种克制结算；
              否则回退到简化兵力对比（向后兼容）。
        """
        # 尝试使用 UnitCounterEngine 增强结算
        unit_counter_result = None
        if attacker_general or defender_general or atk_unit_comp or def_unit_comp:
            try:
                from server.core.unit_counter import UnitCounterEngine
                uce = UnitCounterEngine()
                
                # 构建临时 Legion 对象用于计算
                from server.models.generals import Legion, LegionFormation
                
                atk_legion = Legion(
                    legion_id=f"_battle_atk_{attacker_fid}",
                    name="攻方",
                    faction_id=attacker_fid,
                    unit_composition=atk_unit_comp or {"infantry": atk_troops},
                    formation=atk_formation if atk_formation else LegionFormation.BALANCED,
                    total_troops=atk_troops,
                )
                def_legion = Legion(
                    legion_id=f"_battle_def_{defender_fid}",
                    name="守方",
                    faction_id=defender_fid,
                    unit_composition=def_unit_comp or {"infantry": def_troops},
                    formation=def_formation if def_formation else LegionFormation.DEFENSIVE,
                    total_troops=def_troops,
                )
                
                # 四季倍率
                season_mult = 1.0
                if self.world.current_season == Season.WINTER:
                    season_mult = 0.75
                elif self.world.current_season == Season.SUMMER:
                    season_mult = 0.9
                elif self.world.current_season == Season.AUTUMN:
                    season_mult = 1.1
                
                terrain_str = terrain.value if hasattr(terrain, 'value') else str(terrain)
                unit_counter_result = uce.resolve_legion_battle(
                    atk_legion, def_legion, terrain_str,
                    attacker_general=attacker_general,
                    defender_general=defender_general,
                    fortification=fortification,
                    season_mult=season_mult,
                )
                
                # 转换 winner 格式（resolve_legion_battle 用 "attacker"/"defender"）
                winner = None
                if unit_counter_result["winner"] == "attacker":
                    winner = attacker_fid
                elif unit_counter_result["winner"] == "defender":
                    winner = defender_fid
                
                return {
                    "winner": winner,
                    "attacker_losses": unit_counter_result["attacker_losses"],
                    "defender_losses": unit_counter_result["defender_losses"],
                    "attacker_remaining": sum(unit_counter_result["attacker_remaining"].values()),
                    "defender_remaining": sum(unit_counter_result["defender_remaining"].values()),
                    "_engine": "unit_counter",
                    "_power_ratio": unit_counter_result.get("power_ratio"),
                    "_tactics_used": unit_counter_result.get("tactics_used", []),
                }
            except Exception as e:
                logger.debug(f"[Battle] UnitCounterEngine 结算失败，回退简化算法: {e}", exc_info=True)
        
        # 简化兵力对比（fallback）— 覆盖全部12种地形
        terrain_bonus = {
            TileType.MOUNTAIN: 1.5,
            TileType.CITY: 1.4,
            TileType.PASS: 1.6,
            TileType.PORT: 1.3,
            TileType.COAST: 1.1,
            TileType.DESERT: 1.2,
            TileType.GRASSLAND: 0.9,
            TileType.FARMLAND: 0.95,
            TileType.WATER: 0.7,
            TileType.SEA: 0.5,
        }.get(terrain, 1.0)  # 平原/未知地形默认1.0

        fort_bonus = 1.0 + fortification * self.const["fortification_defense_bonus"]

        # 四季战斗修正
        atk_season_mult = 1.0
        def_season_mult = 1.0
        if self.world.current_season == Season.WINTER:
            atk_season_mult = 0.75  # 冬季进攻方大幅削弱（粮草、冻伤）
            def_season_mult = 1.15  # 守城方冬季优势（城防取暖）
        elif self.world.current_season == Season.SUMMER:
            atk_season_mult = 0.9   # 酷暑行军略削弱
        elif self.world.current_season == Season.AUTUMN:
            atk_season_mult = 1.1   # 秋高气爽，适合用兵

        atk_power = atk_troops * atk_season_mult * (0.8 + random.random() * 0.4)
        def_power = def_troops * def_season_mult * terrain_bonus * fort_bonus * (0.7 + random.random() * 0.6)

        if atk_power > def_power * 1.2:
            winner = attacker_fid
            atk_remaining = int(atk_troops * (0.4 + random.random() * 0.3))
            def_remaining = 0
        elif def_power > atk_power * 1.2:
            winner = defender_fid
            atk_remaining = int(atk_troops * (0.05 + random.random() * 0.15))
            def_remaining = int(def_troops * (0.5 + random.random() * 0.3))
        else:
            winner = None
            atk_remaining = int(atk_troops * (0.2 + random.random() * 0.3))
            def_remaining = int(def_troops * (0.3 + random.random() * 0.3))

        atk_loss = atk_troops - atk_remaining
        def_loss = def_troops - def_remaining

        return {
            "winner": winner,
            "attacker_losses": atk_loss,
            "defender_losses": def_loss,
            "attacker_remaining": atk_remaining,
            "defender_remaining": def_remaining,
            "_engine": "simple",
        }

    def _create_battle_event(self, attacker_fid: str, defender_fid: str,
                              tile_id: str, tile_name: str,
                              atk_troops: int, def_troops: int,
                              battle: dict, terrain: str, is_siege: bool = False) -> str:
        """创建战斗事件并写入 events_log"""
        atk_faction = self.world.get_faction(attacker_fid)
        def_faction = self.world.get_faction(defender_fid)
        atk_name = atk_faction.name if atk_faction else attacker_fid
        def_name = def_faction.name if def_faction else defender_fid

        winner_name = ""
        result_text = ""
        if battle["winner"] == attacker_fid:
            winner_name = atk_name
            result_text = "victory"
        elif battle["winner"] == defender_fid:
            winner_name = def_name
            result_text = "defeat"
        else:
            result_text = "stalemate"

        if is_siege:
            title = f"围困 · {tile_name}"
            description = f"{atk_name}出兵围困{def_name}的{tile_name}（守军{def_troops}，城防{self.world.get_tile(tile_id).fortification if self.world.get_tile(tile_id) else '?'}级）"
        elif winner_name:
            title = f"{'攻占' if battle['winner'] == attacker_fid else '败绩'} · {tile_name}"
            description = f"{atk_name}进攻{def_name}的{tile_name}，{'大胜' if battle['winner'] == attacker_fid else '败退'}。攻方损{ battle['attacker_losses']}，守方损{ battle['defender_losses']}"
        else:
            title = f"鏖战 · {tile_name}"
            description = f"{atk_name}与{def_name}在{tile_name}激战，双方胶着。攻方损{ battle['attacker_losses']}，守方损{ battle['defender_losses']}"

        event_id = f"battle_{attacker_fid}_{tile_id}_{self.world.current_round}_{random.randint(1000,9999)}"

        event = {
            "event_id": event_id,
            "event_type": "battle",
            "severity": "major",
            "round": self.world.current_round,
            "title": title,
            "description": description,
            "faction_id": attacker_fid,
            "tile_id": tile_id,
            "effects": {
                "attacker": attacker_fid,
                "defender": defender_fid,
                "attacker_losses": battle["attacker_losses"],
                "defender_losses": battle["defender_losses"],
                "attacker_remaining": battle.get("attacker_remaining", 0),
                "defender_remaining": battle.get("defender_remaining", 0),
                "result": result_text,
                "is_siege": is_siege,
                "terrain": terrain,
            },
            "narrative": description,
        }
        self.world.events_log.append(event)
        return event_id

    def _capture_prisoners(self, from_faction: str, to_faction: str) -> list[dict]:
        """攻方胜利时随机捕获俘虏（优先从败方武将列表中捕获真实将领）"""
        prisoners = []
        if random.random() < self.const["prisoner_capture_chance"]:
            faction = self.world.get_faction(from_faction)

            # 优先尝试从败方武将列表中捕获真实武将
            prisoner_name = None
            prisoner_rank = "general"
            if hasattr(self.world, 'generals') and self.world.generals:
                # generals 是 list[dict]，筛选属于败方且存活的武将
                from_generals = [g for g in self.world.generals
                                 if g.get('faction_id') == from_faction
                                 and g.get('is_alive', True)]
                if from_generals:
                    captured_gen = random.choice(from_generals)
                    prisoner_name = captured_gen.get('name')
                    prisoner_rank = captured_gen.get('rank', 'general')

            # 兜底：生成泛型将领
            if not prisoner_name:
                prisoner_name = f"{faction.name}将领" if faction else "无名将领"

            prisoner_id = f"prisoner_{from_faction}_{self.world.current_round}_{random.randint(1000,9999)}"
            prisoner = PrisonerRecord(
                prisoner_id=prisoner_id,
                name=prisoner_name,
                captured_from=from_faction,
                held_by=to_faction,
                rank=prisoner_rank,
                captured_round=self.world.current_round,
            )
            self.world.prisoners[prisoner_id] = prisoner
            prisoners.append({"id": prisoner_id, "name": prisoner_name, "from": from_faction})

            # 更新势力俘虏列表
            to_f = self.world.get_faction(to_faction)
            if to_f:
                to_f.prisoners.append(prisoner_id)
        return prisoners

    def _record_tile_change(self, tile: TileState, old_faction_id: str, new_faction_id: str,
                            old_faction_name: str, new_faction_name: str,
                            change_type: str, troops_involved: int, battle_result: str):
        """记录地盘变更到 world_state.tile_changes"""
        change_id = f"tc_{self.world.current_round}_{tile.tile_id}_{random.randint(1000,9999)}"
        change = {
            "change_id": change_id,
            "round": self.world.current_round,
            "tile_id": tile.tile_id,
            "tile_name": tile.tile_name,
            "region": tile.region,
            "old_faction_id": old_faction_id,
            "new_faction_id": new_faction_id,
            "old_faction_name": old_faction_name,
            "new_faction_name": new_faction_name,
            "change_type": change_type,
            "troops_involved": troops_involved,
            "battle_result": battle_result,
            "narrative": self._build_change_narrative(
                tile.tile_name, old_faction_name, new_faction_name, change_type, battle_result,
            ),
        }
        self.world.tile_changes.append(change)

    @staticmethod
    def _build_change_narrative(tile_name: str, old_name: str, new_name: str,
                                 change_type: str, battle_result: str) -> str:
        """生成地盘变更叙事文本"""
        if change_type == "conquer":
            if battle_result == "victory":
                return f"【攻占】{new_name}从{old_name}手中夺取了{tile_name}！"
            else:
                return f"【陷落】{tile_name}被{new_name}占领，{old_name}失去了这片领土。"
        elif change_type == "settle":
            return f"【开拓】{new_name}在{tile_name}建立了新的据点。"
        elif change_type == "lose":
            return f"【失守】{old_name}失去了{tile_name}。"
        elif change_type == "abandon":
            return f"【放弃】{old_name}主动放弃了{tile_name}。"
        return f"{tile_name}的归属从{old_name}变更为{new_name}。"

    # ================================================================
    # 邻接地块与攻击目标查询
    # ================================================================

    def get_attackable_neighbors(self, tile_id: str, faction_id: str) -> list[dict]:
        """获取可攻击的相邻地块列表（CK3风格：基于领地邻接图）"""
        tile = self.world.get_tile(tile_id)
        if not tile or tile.faction_id != faction_id:
            return []

        # 优先使用 TerritoryGraph
        try:
            from server.core.territory_graph import get_territory_graph
            graph = get_territory_graph()
            if graph._loaded and graph.get_territory(tile_id):
                season = self.world.current_season.value if hasattr(self.world.current_season, 'value') else "春"
                return graph.get_attackable_targets(
                    territory_id=tile_id,
                    faction_id=faction_id,
                    tile_map=self.world.tiles,
                    faction_tiles={},  # 由 graph 内部处理
                )
        except Exception as e:
            logger.debug(f"TerritoryGraph邻接查询失败，回退六边形: {e}")

        # 回退：旧版六边形邻接查询
        results = []
        for dq, dr in self._HEX_DIRECTIONS:
            nq = tile.q + dq
            nr = tile.r + dr
            neighbor = self._find_tile_by_coord(nq, nr)
            if not neighbor:
                continue

            # 跳过己方地块
            if neighbor.faction_id == faction_id:
                continue

            # 计算预估
            estimate = self._estimate_battle(
                tile.troops, neighbor.troops,
                neighbor.tile_type, neighbor.fortification,
            )

            results.append({
                "tile_id": neighbor.tile_id,
                "tile_name": neighbor.tile_name,
                "faction_id": neighbor.faction_id,
                "faction_name": self.world.get_faction(neighbor.faction_id).name if neighbor.faction_id and self.world.get_faction(neighbor.faction_id) else "无人区",
                "troops": neighbor.troops,
                "fortification": neighbor.fortification,
                "tile_type": neighbor.tile_type.value if hasattr(neighbor.tile_type, 'value') else str(neighbor.tile_type),
                "is_capital": neighbor.is_capital,
                "estimate": estimate,
                "q": nq,
                "r": nr,
            })

        return results

    def _find_tile_by_coord(self, q: int, r: int) -> Optional[TileState]:
        """通过六边形坐标查找地块（保留向后兼容）"""
        for tile in self.world.tiles.values():
            if tile.q == q and tile.r == r:
                return tile
        return None

    def _estimate_battle(self, atk_troops: int, def_troops: int,
                         terrain: TileType, fortification: int) -> dict:
        """预估战斗结果（四季修正）"""
        terrain_bonus = {
            TileType.MOUNTAIN: 1.5, TileType.CITY: 1.4,
            TileType.PASS: 1.6, TileType.PORT: 1.3, TileType.COAST: 1.1,
        }.get(terrain, 1.0)
        fort_bonus = 1.0 + fortification * self.const["fortification_defense_bonus"]

        # 四季修正（与 _resolve_battle 一致）
        atk_season_mult = 1.0
        def_season_mult = 1.0
        if self.world.current_season == Season.WINTER:
            atk_season_mult = 0.75
            def_season_mult = 1.15
        elif self.world.current_season == Season.SUMMER:
            atk_season_mult = 0.9
        elif self.world.current_season == Season.AUTUMN:
            atk_season_mult = 1.1

        def_effective = def_troops * def_season_mult * terrain_bonus * fort_bonus
        atk_effective = atk_troops * atk_season_mult
        ratio = atk_effective / max(1, def_effective)

        if ratio > 1.5:
            win_prob = min(0.95, 0.8 + min(0.15, (ratio - 1.5) * 0.1))
            level = "high"
        elif ratio > 1.0:
            win_prob = min(0.95, 0.5 + (ratio - 1.0) * 0.6)
            level = "medium"
        elif ratio > 0.5:
            win_prob = min(0.95, 0.2 + (ratio - 0.5) * 0.6)
            level = "low"
        else:
            win_prob = max(0.01, ratio * 0.2)
            level = "very_low"

        return {
            "win_probability": round(win_prob, 2),
            "level": level,
            "label": {"high": "十拿九稳", "medium": "可堪一战", "low": "凶多吉少", "very_low": "以卵击石"}.get(level, "未知"),
            "atk_effective": int(atk_effective),
            "def_effective": int(def_effective),
            "recommended_troops": max(1, int(def_effective * 1.5)),
        }


# ================================================================
# 谍报引擎
# ================================================================

class SpyEngine:
    """谍报细作引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**DEFAULTS, **(game_const or {})}

    def deploy_spy(self, owner_faction: str, target_faction: str) -> dict:
        """派遣细作"""
        faction = self.world.get_faction(owner_faction)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        cost = 200
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        faction.treasury -= cost

        key = f"{owner_faction}|{target_faction}"
        from server.models.world_state import SpyNetwork
        if key not in self.world.spy_networks:
            # 初始渗透度从 game_const 读取，兜底为 20
            init_infiltration = self.const.get("spy_initial_infiltration", 20)
            self.world.spy_networks[key] = SpyNetwork(
                owner_faction=owner_faction,
                target_faction=target_faction,
                infiltration=init_infiltration,
            )
        self.world.spy_networks[key].spies_count += 1

        return {"success": True, "message": f"细作已潜入{target_faction}", "network_key": key}

    def spy_action(self, owner_faction: str, target_faction: str,
                   action_type: str) -> dict:
        """执行谍报行动"""
        key = f"{owner_faction}|{target_faction}"
        network = self.world.spy_networks.get(key)
        if not network or network.spies_count <= 0:
            return {"success": False, "message": "无可用细作"}

        base_success = min(0.95, 0.75 + network.infiltration * 0.08)  # Bug #8修复: 上限95%
        # 暴露概率基于渗透度 + 目标治安值（治安越高越容易发现细作）
        target_faction_obj = self.world.get_faction(target_faction)
        target_public_order = getattr(target_faction_obj, 'public_order', 50) if target_faction_obj else 50
        order_factor = max(0.5, target_public_order / 100.0)  # 治安100→1.0x, 治安0→0.5x
        expose_risk = max(0.03, (0.25 - network.infiltration * 0.05) * order_factor)

        if action_type == "intel":
            # 刺探情报
            target = self.world.get_faction(target_faction)
            success = random.random() < base_success + 0.15
            if success and target:
                network.infiltration = min(100, network.infiltration + 5)
                # 记录情报到持久化列表，带时效性
                self.world.spy_intel.append({
                    "owner_faction": owner_faction,
                    "target_faction": target_faction,
                    "action": "intel",
                    "success": True,
                    "round": self.world.current_round,
                    "infiltration": network.infiltration,
                    "data": {
                        "treasury": target.treasury,
                        "grain": target.grain,
                        "total_troops": target.total_troops,
                        "total_population": target.total_population,
                        "court_stability": target.court_stability,
                        "realm_stability": target.realm_stability,
                        "tiles": len(self.world.get_faction_tiles(target_faction)),
                    },
                })
                # 情报列表上限裁剪（保留最新 500 条，防止无限增长）
                if len(self.world.spy_intel) > 500:
                    self.world.spy_intel = self.world.spy_intel[-500:]
                return {
                    "success": True,
                    "action": "intel",
                    "data": {
                        "treasury": target.treasury,
                        "grain": target.grain,
                        "total_troops": target.total_troops,
                        "total_population": target.total_population,
                        "court_stability": target.court_stability,
                        "realm_stability": target.realm_stability,
                        "tiles": len(self.world.get_faction_tiles(target_faction)),
                    },
                    "message": "情报获取成功",
                }

        elif action_type == "discord":
            # 离间君臣
            success = random.random() < base_success
            if success:
                for oid, off in self.world.officials.items():
                    if off.faction_id == target_faction:
                        off.loyalty = max(0, off.loyalty - random.randint(5, 20))
                return {"success": True, "action": "discord", "message": "离间成功，敌将忠诚动摇"}

        elif action_type == "assassinate":
            # 刺杀
            success = random.random() < base_success - 0.15
            if success:
                return {"success": True, "action": "assassinate", "message": "刺杀成功！"}
            else:
                network.discovered = True
                return {"success": False, "action": "assassinate", "message": "刺杀失败，细作暴露！"}

        elif action_type == "sabotage":
            # 纵火毁产
            success = random.random() < base_success - 0.05
            if success:
                for tile in self.world.get_faction_tiles(target_faction):
                    if random.random() < 0.3:
                        tile.grain = int(tile.grain * 0.3)
                return {"success": True, "action": "sabotage", "message": "破坏成功，敌仓受损"}

        elif action_type == "rumor":
            # 散布流言：同时降低目标民心与朝堂稳定
            success = random.random() < base_success + 0.1
            if success:
                target = self.world.get_faction(target_faction)
                if target:
                    target.realm_stability = max(0, target.realm_stability - 10)
                    # 朝堂稳定也受影响（流言离间君臣）
                    target.court_stability = max(0, getattr(target, 'court_stability', 50) - 8)
                    # 渗透度降低（散布流言消耗情报资源）
                    network.infiltration = max(0, network.infiltration - 5)
                # rumor 成功后也要走暴露检查（与其他行动类型一致）
                if random.random() < expose_risk:
                    network.discovered = True
                    network.spies_count = max(0, network.spies_count - 1)
                    return {"success": False, "action": "rumor", "message": "流言散布后被敌方反间发现，细作暴露！"}
                return {"success": True, "action": "rumor", "message": "流言四起，民心动荡，朝堂不稳"}

        # 暴露检查
        if random.random() < expose_risk:
            network.discovered = True
            network.spies_count = max(0, network.spies_count - 1)  # Bug #11修复: 暴露后减少细作数
            return {"success": False, "action": action_type, "message": "行动失败，细作暴露！"}

        return {"success": False, "action": action_type, "message": "行动失败"}

    def turn_double_agent(self, owner_faction: str, target_faction: str) -> dict:
        """策反双面间谍：将敌方已暴露的细作转化为己方双面间谍"""
        key = f"{owner_faction}|{target_faction}"
        reverse_key = f"{target_faction}|{owner_faction}"
        enemy_network = self.world.spy_networks.get(reverse_key)
        if not enemy_network or enemy_network.spies_count <= 0:
            return {"success": False, "message": "未发现敌方细作网络"}

        if not enemy_network.discovered:
            return {"success": False, "message": "未发现已暴露的敌方细作，无法策反"}

        faction = self.world.get_faction(owner_faction)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        cost = 500
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        # 成功率基于己方渗透度
        base_chance = 0.35
        our_network = self.world.spy_networks.get(key)
        if our_network:
            base_chance += our_network.infiltration * 0.05

        if random.random() < base_chance:
            faction.treasury -= cost
            # 转化为双面间谍：敌方渗透度降低，己方获得情报加成
            enemy_network.spies_count -= 1
            enemy_network.infiltration = max(0, enemy_network.infiltration - 20)
            # 己方渗透度提升
            if key not in self.world.spy_networks:
                from server.models.world_state import SpyNetwork
                self.world.spy_networks[key] = SpyNetwork(
                    owner_faction=owner_faction,
                    target_faction=target_faction,
                    infiltration=15,
                )
            else:
                self.world.spy_networks[key].infiltration = min(100, self.world.spy_networks[key].infiltration + 15)

            self.world.events_log.append({
                "event_id": f"double_agent_{owner_faction}_{target_faction}_{self.world.current_round}",
                "event_type": "espionage", "severity": "major",
                "round": self.world.current_round,
                "title": f"【谍报】成功策反{target_faction}细作",
                "description": f"{faction.name}成功将{target_faction}的细作转化为双面间谍。",
                "effects": {"double_agent": True},
            })
            return {"success": True, "message": f"成功策反敌方细作，获得双面间谍！"}
        else:
            # 失败可能导致暴露
            if random.random() < 0.3:
                if our_network:
                    our_network.discovered = True
                return {"success": False, "message": "策反失败，己方细作反被暴露！"}
            return {"success": False, "message": "策反失败"}

    def plant_false_intel(self, owner_faction: str, target_faction: str,
                          intel_type: str, fake_data: dict = None) -> dict:
        """注入假情报：通过双面间谍向敌方传递虚假信息"""
        key = f"{owner_faction}|{target_faction}"
        network = self.world.spy_networks.get(key)
        if not network or network.spies_count <= 0:
            return {"success": False, "message": "无可用细作网络"}

        if network.infiltration < 30:
            return {"success": False, "message": "渗透度不足（需要≥30），无法注入假情报"}

        faction = self.world.get_faction(owner_faction)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        cost = 300
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        # 成功率基于渗透度
        success_chance = 0.4 + network.infiltration * 0.04
        if random.random() < success_chance:
            faction.treasury -= cost
            intel_record = {
                "owner_faction": owner_faction,
                "target_faction": target_faction,
                "intel_type": intel_type,
                "fake_data": fake_data or {},
                "round": self.world.current_round,
                "is_false": True,
            }
            self.world.planted_false_intel.append(intel_record)
            self.world.events_log.append({
                "event_id": f"false_intel_{owner_faction}_{target_faction}_{self.world.current_round}",
                "event_type": "espionage", "severity": "major",
                "round": self.world.current_round,
                "title": f"【谍报】向{target_faction}注入假情报",
                "description": f"{faction.name}成功向{target_faction}传递了虚假情报。",
                "effects": {"false_intel": True, "intel_type": intel_type},
            })
            return {"success": True, "message": f"假情报已成功注入{target_faction}！"}
        else:
            expose_risk = max(0.05, 0.30 - network.infiltration * 0.04)
            if random.random() < expose_risk:
                network.discovered = True
                return {"success": False, "message": "假情报注入失败，细作暴露！"}
            return {"success": False, "message": "假情报注入失败"}

    def counter_espionage(self, owner_faction: str, target_faction: str) -> dict:
        """反间谍：清除敌方在己方的细作网络（counter_espionage 别名，兼容文档命名）"""
        # 敌方在我方的网络 key 是 target_faction|owner_faction
        reverse_key = f"{target_faction}|{owner_faction}"
        enemy_network = self.world.spy_networks.get(reverse_key)
        if not enemy_network or enemy_network.spies_count <= 0:
            return {"success": False, "message": "未发现敌方细作活动"}
        faction = self.world.get_faction(owner_faction)
        if not faction:
            return {"success": False, "message": "势力不存在"}
        cost = 150
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}
        # 清除成功率基于己方治安
        public_order = getattr(faction, 'public_order', 50)
        clear_chance = 0.3 + public_order * 0.005  # 治安100→80%成功率
        faction.treasury -= cost
        cleared = 0
        if random.random() < clear_chance:
            cleared = enemy_network.spies_count
            enemy_network.spies_count = 0
            enemy_network.infiltration = max(0, enemy_network.infiltration - 30)
            enemy_network.discovered = True
        else:
            cleared = max(0, enemy_network.spies_count - 1)
            enemy_network.spies_count = max(0, enemy_network.spies_count - 1)
        self.world.events_log.append({
            "event_id": f"counter_spy_{owner_faction}_{target_faction}_{self.world.current_round}",
            "event_type": "espionage", "severity": "minor",
            "round": self.world.current_round,
            "title": f"【反间谍】清除{target_faction}细作",
            "description": f"{faction.name}开展了反间谍行动，清除{target_faction}细作{cleared}人。",
        })
        return {"success": True, "message": f"反间谍行动完成，清除{target_faction}细作{cleared}人"}





# ================================================================
# 外交引擎（增强版：联邦/联盟 + 事件记录 + 成本 + 条约系统 + 朝贡）
# ================================================================

class DiplomacyEngine:
    """外交引擎（增强版：联邦创建/管理、条约系统、朝贡、外交事件记录）"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**DEFAULTS, **(game_const or {})}
        # 外交操作成本
        self._diplo_costs = {
            "declare_war": {"treasury": 0, "reputation": -10},
            "propose_alliance": {"treasury": 800, "reputation": 0},
            "propose_truce": {"treasury": 300, "reputation": 0},
            "propose_neutral": {"treasury": 100, "reputation": -3},
            "propose_vassal": {"treasury": 1000, "reputation": 5},
            "open_trade": {"treasury": 200, "reputation": 0},
            "propose_marriage": {"treasury": 500, "reputation": 5},
            "offer_vassal": {"treasury": 1000, "reputation": 5},
            "form_coalition": {"treasury": 1500, "reputation": 10},
            "join_coalition": {"treasury": 800, "reputation": 5},
            "leave_coalition": {"treasury": 0, "reputation": -5},
            "dissolve_coalition": {"treasury": 0, "reputation": -15},
            "demand_tribute": {"treasury": 0, "reputation": -5},
            "cancel_vassal": {"treasury": 0, "reputation": -10},
            "close_trade": {"treasury": 0, "reputation": -3},
            "send_hostage": {"treasury": 300, "reputation": 5},
            "recall_hostage": {"treasury": 0, "reputation": -5},
        }

    # ================================================================
    # 外交姿态变更
    # ================================================================

    def change_stance(self, faction_a: str, faction_b: str,
                      new_stance: str, reason: str = "") -> dict:
        """改变外交关系（含成本 + 事件记录 + 联邦影响）"""
        if faction_a == faction_b:
            return {"success": False, "message": "不能改变与自身的外交关系"}

        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        try:
            stance = DiplomaticStance(new_stance)
        except ValueError:
            return {"success": False, "message": f"无效外交姿态: {new_stance}"}

        old = rel.stance

        # 检查过渡合法性
        if not self._is_valid_stance_transition(old, stance):
            return {"success": False, "message": f"不能从{old.value}直接变为{stance.value}"}

        # 扣除成本：各种姿态变更的成本均已映射到 _diplo_costs
        cost_key = f"propose_{stance.value}" if stance != DiplomaticStance.WAR else "declare_war"
        cost_result = self._apply_diplo_cost(faction_a, cost_key)
        if not cost_result["success"]:
            return cost_result

        # 如果一方在联邦中，需要检查联邦规则
        coalition_effect = self._check_coalition_effect(faction_a, faction_b, old, stance)
        if coalition_effect.get("blocked"):
            return {"success": False, "message": coalition_effect["reason"]}

        # 执行姿态变更
        old_stance_value = old.value
        rel.stance = stance

        if stance == DiplomaticStance.WAR:
            rel.attitude = -50
            rel.trade_active = False
            # 退出联邦
            if rel.coalition_id:
                self._remove_from_coalition(faction_a, rel.coalition_id)
                self._remove_from_coalition(faction_b, rel.coalition_id)
                rel.coalition_id = ""
            # 取消附庸
            self._cancel_vassal_relation(faction_a, faction_b)
        elif stance == DiplomaticStance.ALLIANCE:
            rel.attitude = 50
            rel.trade_active = True
        elif stance == DiplomaticStance.TRUCE:
            rel.attitude = 0
            rel.trade_active = False
        elif stance == DiplomaticStance.NEUTRAL:
            rel.attitude = 0
            rel.trade_active = False
            if rel.coalition_id:
                self._remove_from_coalition(faction_a, rel.coalition_id)
                self._remove_from_coalition(faction_b, rel.coalition_id)
                rel.coalition_id = ""
        elif stance == DiplomaticStance.VASSAL:
            rel.attitude = 30
            self.world.vassal_relations[faction_b] = faction_a

        # 记录外交日志
        archive_entry = {
            "round": self.world.current_round,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "faction_a": faction_a,
            "faction_b": faction_b,
            "from": old_stance_value,
            "to": new_stance,
            "reason": reason,
        }
        self.world.diplomatic_archive.append(archive_entry)

        # 创建外交事件
        self._create_diplomatic_event(faction_a, faction_b, old_stance_value, new_stance, reason)

        # 通知联邦成员
        if coalition_effect.get("notify_coalition"):
            for member in coalition_effect["notify_coalition"]:
                self.world.diplomatic_archive.append({
                    **archive_entry,
                    "notified": member,
                })

        return {
            "success": True,
            "from": old_stance_value,
            "to": new_stance,
            "message": f"外交关系从{old_stance_value}变更为{new_stance}",
            "event_id": f"diplo_{faction_a}_{faction_b}_{self.world.current_round}",
        }

    def _is_valid_stance_transition(self, old: DiplomaticStance, new: DiplomaticStance) -> bool:
        """检查外交姿态过渡是否合法"""
        if old == new:
            return False
        # 可以从任意姿态宣战
        if new == DiplomaticStance.WAR:
            return True
        # 交战状态下只能停战
        if old == DiplomaticStance.WAR:
            return new in (DiplomaticStance.TRUCE, DiplomaticStance.NEUTRAL)
        # 同盟/附庸不能直接中立
        if old in (DiplomaticStance.ALLIANCE, DiplomaticStance.VASSAL) and new == DiplomaticStance.NEUTRAL:
            return False
        # 停战后可变为中立或同盟
        if old == DiplomaticStance.TRUCE:
            return new in (DiplomaticStance.NEUTRAL, DiplomaticStance.ALLIANCE, DiplomaticStance.VASSAL)
        return True

    def _apply_diplo_cost(self, faction_id: str, action: str) -> dict:
        """扣除外交操作成本"""
        cost = self._diplo_costs.get(action, {})
        treasury_cost = cost.get("treasury", 0)
        rep_change = cost.get("reputation", 0)

        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        if faction.treasury < treasury_cost:
            return {"success": False, "message": f"银两不足（需要{treasury_cost}，现有{faction.treasury}）"}

        faction.treasury -= treasury_cost
        faction.reputation = max(0, min(100, faction.reputation + rep_change))
        return {"success": True}

    # ================================================================
    # 通商贸易
    # ================================================================

    def open_trade(self, faction_a: str, faction_b: str) -> dict:
        """开通贸易（增强版：检查姿态 + 创建贸易路线记录）"""
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        if rel.stance == DiplomaticStance.WAR:
            return {"success": False, "message": "交战状态无法通商"}

        if rel.trade_active:
            return {"success": False, "message": "贸易路线已开通"}

        # 扣除成本
        cost_result = self._apply_diplo_cost(faction_a, "open_trade")
        if not cost_result["success"]:
            return cost_result

        rel.trade_active = True
        income = self.const["trade_route_income"]

        # 记录贸易路线
        self.world.trade_routes.append({
            "route_id": f"trade_{faction_a}_{faction_b}",
            "from_faction": faction_a,
            "to_faction": faction_b,
            "income_per_turn": income,
            "started_round": self.world.current_round,
            "active": True,
        })

        # 好感提升
        rel.attitude = min(100, rel.attitude + 10)

        # 创建事件
        self._create_diplomatic_event(faction_a, faction_b, "", "open_trade", "")

        return {
            "success": True,
            "income_per_turn": income,
            "message": f"贸易路线已开通，每回合收益{income}银两",
        }

    def close_trade(self, faction_a: str, faction_b: str) -> dict:
        """关闭贸易路线"""
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        rel.trade_active = False
        rel.attitude = max(-100, rel.attitude - 10)

        # 标记贸易路线失效
        for route in self.world.trade_routes:
            if (route["from_faction"] == faction_a and route["to_faction"] == faction_b) or \
               (route["from_faction"] == faction_b and route["to_faction"] == faction_a):
                route["active"] = False

        return {"success": True, "message": "贸易路线已关闭"}

    # ================================================================
    # 联姻和亲
    # ================================================================

    def propose_marriage(self, from_faction: str, to_faction: str) -> dict:
        """联姻提议（增强版：成本 + 双向效果 + 事件记录）"""
        key = self.world.relation_key(from_faction, to_faction)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        if rel.stance == DiplomaticStance.WAR:
            return {"success": False, "message": "交战状态无法联姻"}

        # 已有联姻检查
        for treaty in self.world.alliance_treaties:
            if treaty.treaty_type == "marriage" and \
               from_faction in treaty.factions and to_faction in treaty.factions:
                return {"success": False, "message": "已有联姻关系"}

        # 扣除成本
        cost_result = self._apply_diplo_cost(from_faction, "propose_marriage")
        if not cost_result["success"]:
            return cost_result

        # 好感大幅提升（与 game_const.yaml marriage_relation_bonus: 30 保持一致）
        marriage_bonus = self.const.get("marriage_relation_bonus", 30)
        rel.attitude = min(100, rel.attitude + marriage_bonus)

        # 中立变停战，停战可能变同盟
        if rel.stance == DiplomaticStance.NEUTRAL:
            rel.stance = DiplomaticStance.TRUCE
        elif rel.stance == DiplomaticStance.TRUCE and rel.attitude >= 60:
            rel.stance = DiplomaticStance.ALLIANCE

        # 创建联姻条约
        treaty = TreatyRecord(
            treaty_id=f"marriage_{from_faction}_{to_faction}_{self.world.current_round}",
            treaty_type="marriage",
            factions=[from_faction, to_faction],
            signed_round=self.world.current_round,
            expires_round=0,  # 联姻不自动过期
            terms={"type": "marriage", "attitude_boost": 25},
        )
        self.world.alliance_treaties.append(treaty)

        # 创建事件
        self._create_diplomatic_event(from_faction, to_faction, "", "marriage", "")

        return {
            "success": True,
            "attitude": rel.attitude,
            "new_stance": rel.stance.value,
            "message": "联姻成功，两国交好",
            "treaty_id": treaty.treaty_id,
        }

    # ================================================================
    # 联邦/联盟系统（核心增强）
    # ================================================================

    def form_coalition(self, founder_faction: str, name: str,
                       member_factions: list[str] = None) -> dict:
        """创建联邦/联盟"""
        member_factions = member_factions or []
        if not member_factions:
            return {"success": False, "message": "至少需要一个初始成员"}

        # 扣除成本
        cost_result = self._apply_diplo_cost(founder_faction, "form_coalition")
        if not cost_result["success"]:
            return cost_result

        coalition_id = f"coalition_{founder_faction}_{self.world.current_round}"

        # 检查所有成员是否可加入
        all_members = [founder_faction] + member_factions
        for fid in all_members:
            if not self.world.get_faction(fid):
                return {"success": False, "message": f"势力 {fid} 不存在"}
            # 检查是否已在其他联邦
            for cid, members in self.world.coalitions.items():
                if fid in members:
                    return {"success": False, "message": f"{self.world.get_faction(fid).name} 已在联邦{cid}中"}

        # 检查成员间是否都非交战状态
        for i in range(len(all_members)):
            for j in range(i + 1, len(all_members)):
                rel = self.world.get_relation(all_members[i], all_members[j])
                if rel and rel.stance == DiplomaticStance.WAR:
                    return {"success": False, "message": f"联邦成员之间存在交战关系，无法结盟"}

        # 创建联邦
        self.world.coalitions[coalition_id] = all_members

        # 更新所有成员间关系为同盟
        for i in range(len(all_members)):
            for j in range(i + 1, len(all_members)):
                rel = self.world.get_relation(all_members[i], all_members[j])
                if rel:
                    rel.stance = DiplomaticStance.ALLIANCE
                    rel.attitude = max(rel.attitude, 50)
                    rel.trade_active = True
                    rel.coalition_id = coalition_id

        # 创建联邦条约
        treaty = TreatyRecord(
            treaty_id=f"coalition_{coalition_id}",
            treaty_type="coalition",
            factions=all_members,
            signed_round=self.world.current_round,
            expires_round=0,
            terms={"name": name, "type": "coalition", "founder": founder_faction},
        )
        self.world.alliance_treaties.append(treaty)

        # 事件记录
        founder_name = self.world.get_faction(founder_faction).name
        self.world.events_log.append({
            "event_id": f"coalition_form_{coalition_id}",
            "event_type": "diplomacy",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"联邦建立 · {name}",
            "description": f"{founder_name}倡导建立{name}，{'、'.join([self.world.get_faction(f).name for f in all_members])}共襄盛举。",
            "faction_id": founder_faction,
            "tile_id": "",
            "effects": {"coalition_id": coalition_id, "members": all_members},
            "narrative": f"{founder_name}倡导建立{name}，{'、'.join([self.world.get_faction(f).name for f in all_members])}共襄盛举。",
        })

        return {
            "success": True,
            "coalition_id": coalition_id,
            "name": name,
            "members": all_members,
            "member_names": [self.world.get_faction(f).name for f in all_members],
            "message": f"联邦「{name}」已建立",
            "treaty_id": treaty.treaty_id,
        }

    def join_coalition(self, faction_id: str, coalition_id: str) -> dict:
        """加入联邦"""
        if coalition_id not in self.world.coalitions:
            return {"success": False, "message": "联邦不存在"}

        if faction_id in self.world.coalitions[coalition_id]:
            return {"success": False, "message": "已是该联邦成员"}

        # 扣除成本
        cost_result = self._apply_diplo_cost(faction_id, "join_coalition")
        if not cost_result["success"]:
            return cost_result

        # 检查与联邦成员是否交战
        for member in self.world.coalitions[coalition_id]:
            rel = self.world.get_relation(faction_id, member)
            if rel and rel.stance == DiplomaticStance.WAR:
                return {"success": False, "message": f"与联邦成员{self.world.get_faction(member).name}处于交战状态"}

        # 加入联邦
        self.world.coalitions[coalition_id].append(faction_id)

        # 与所有联邦成员建立同盟
        for member in self.world.coalitions[coalition_id]:
            if member == faction_id:
                continue
            rel = self.world.get_relation(faction_id, member)
            if rel:
                rel.stance = DiplomaticStance.ALLIANCE
                rel.attitude = max(rel.attitude, 40)
                rel.trade_active = True
                rel.coalition_id = coalition_id

        faction_name = self.world.get_faction(faction_id).name
        self.world.events_log.append({
            "event_id": f"coalition_join_{coalition_id}_{faction_id}",
            "event_type": "diplomacy",
            "severity": "major",
            "round": self.world.current_round,
            "title": "联邦扩张",
            "description": f"{faction_name}加入联邦。",
            "faction_id": faction_id,
            "tile_id": "",
            "effects": {"coalition_id": coalition_id},
            "narrative": f"{faction_name}加入联邦。",
        })

        return {"success": True, "coalition_id": coalition_id, "message": f"已加入联邦"}

    def leave_coalition(self, faction_id: str, coalition_id: str) -> dict:
        """退出联邦"""
        if coalition_id not in self.world.coalitions:
            return {"success": False, "message": "联邦不存在"}

        if faction_id not in self.world.coalitions[coalition_id]:
            return {"success": False, "message": "不在该联邦中"}

        # 扣除成本
        cost_result = self._apply_diplo_cost(faction_id, "leave_coalition")
        if not cost_result["success"]:
            return cost_result

        self._remove_from_coalition(faction_id, coalition_id)

        # 联邦解散检查
        if len(self.world.coalitions.get(coalition_id, [])) <= 1:
            self._dissolve_coalition_internal(coalition_id)

        return {"success": True, "message": "已退出联邦"}

    def dissolve_coalition(self, faction_id: str, coalition_id: str) -> dict:
        """解散联邦（仅创始人可操作）"""
        if coalition_id not in self.world.coalitions:
            return {"success": False, "message": "联邦不存在"}

        # 检查是否为创始人
        members = self.world.coalitions[coalition_id]
        if faction_id not in members:
            return {"success": False, "message": "不在该联邦中"}

        # 查找创始条约
        founder = faction_id
        for treaty in self.world.alliance_treaties:
            if treaty.treaty_type == "coalition" and treaty.treaty_id == f"coalition_{coalition_id}":
                founder = treaty.terms.get("founder", faction_id)
                break

        if faction_id != founder:
            return {"success": False, "message": "仅联邦创始人可以解散联邦"}

        cost_result = self._apply_diplo_cost(faction_id, "dissolve_coalition")
        if not cost_result["success"]:
            return cost_result

        self._dissolve_coalition_internal(coalition_id)
        return {"success": True, "message": "联邦已解散"}

    def _remove_from_coalition(self, faction_id: str, coalition_id: str):
        """从联邦中移除势力（内部方法）"""
        if coalition_id in self.world.coalitions:
            if faction_id in self.world.coalitions[coalition_id]:
                self.world.coalitions[coalition_id].remove(faction_id)
            # 清除该势力与其他联邦成员关系的 coalition_id
            for other in self.world.coalitions.get(coalition_id, []):
                rel = self.world.get_relation(faction_id, other)
                if rel:
                    rel.coalition_id = ""

    def _dissolve_coalition_internal(self, coalition_id: str):
        """解散联邦（内部方法）"""
        if coalition_id not in self.world.coalitions:
            return

        members = list(self.world.coalitions[coalition_id])

        # 清除所有成员的 coalition_id
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                rel = self.world.get_relation(members[i], members[j])
                if rel:
                    rel.coalition_id = ""

        # 删除联邦
        del self.world.coalitions[coalition_id]

        self.world.events_log.append({
            "event_id": f"coalition_dissolve_{coalition_id}",
            "event_type": "diplomacy",
            "severity": "major",
            "round": self.world.current_round,
            "title": "联邦解散",
            "description": f"联邦已解散，{'、'.join([self.world.get_faction(f).name for f in members if self.world.get_faction(f)])}各自为政。",
            "faction_id": "",
            "tile_id": "",
            "effects": {"coalition_id": coalition_id},
            "narrative": f"联邦已解散。",
        })

    def _check_coalition_effect(self, faction_a: str, faction_b: str,
                                 old: DiplomaticStance, new: DiplomaticStance) -> dict:
        """检查联邦对外交操作的影响"""
        result = {"blocked": False, "reason": "", "notify_coalition": []}

        # 如果向联邦成员宣战，整个联邦将参战
        if new == DiplomaticStance.WAR:
            for cid, members in self.world.coalitions.items():
                if faction_b in members:
                    result["notify_coalition"] = [m for m in members if m != faction_b]
                    break

        return result

    # ================================================================
    # 朝贡/附庸系统
    # ================================================================

    def demand_tribute(self, suzerain: str, vassal: str, amount: int) -> dict:
        """宗主向附庸索要朝贡"""
        if vassal not in self.world.vassal_relations:
            return {"success": False, "message": "对方不是你的附庸"}

        if self.world.vassal_relations[vassal] != suzerain:
            return {"success": False, "message": "对方不是你的附庸"}

        vassal_faction = self.world.get_faction(vassal)
        if not vassal_faction:
            return {"success": False, "message": "附庸势力不存在"}

        if vassal_faction.treasury < amount:
            return {"success": False, "message": f"附庸银两不足（需要{amount}，现有{vassal_faction.treasury}）"}

        suzerain_faction = self.world.get_faction(suzerain)
        vassal_faction.treasury -= amount
        suzerain_faction.treasury += amount

        # 好感降低
        rel = self.world.get_relation(suzerain, vassal)
        if rel:
            rel.attitude = max(-100, rel.attitude - 5)

        return {"success": True, "amount": amount, "message": f"获得朝贡银{amount}两"}

    def offer_vassal(self, suzerain: str, target: str) -> dict:
        """提议附庸"""
        key = self.world.relation_key(suzerain, target)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        if rel.stance == DiplomaticStance.WAR:
            return {"success": False, "message": "交战状态无法提议附庸"}

        cost_result = self._apply_diplo_cost(suzerain, "offer_vassal")
        if not cost_result["success"]:
            return cost_result

        # 需要对方实力远小于己方
        suzerain_f = self.world.get_faction(suzerain)
        target_f = self.world.get_faction(target)
        if target_f.total_troops > suzerain_f.total_troops * 0.5:
            return {"success": False, "message": "对方实力过强，不愿称臣"}

        rel.stance = DiplomaticStance.VASSAL
        rel.attitude = 20
        self.world.vassal_relations[target] = suzerain

        self._create_diplomatic_event(suzerain, target, "", "vassal", "")
        return {"success": True, "message": f"{target_f.name}已成为{suzerain_f.name}的附庸"}

    def cancel_vassal(self, suzerain: str, vassal: str) -> dict:
        """取消附庸关系"""
        if vassal not in self.world.vassal_relations:
            return {"success": False, "message": "没有附庸关系"}

        if self.world.vassal_relations[vassal] != suzerain:
            return {"success": False, "message": "对方不是你的附庸"}

        cost_result = self._apply_diplo_cost(suzerain, "cancel_vassal")
        if not cost_result["success"]:
            return cost_result

        self._cancel_vassal_relation(suzerain, vassal)

        rel = self.world.get_relation(suzerain, vassal)
        if rel:
            rel.stance = DiplomaticStance.NEUTRAL
            rel.attitude = -20

        return {"success": True, "message": "附庸关系已取消"}

    def _cancel_vassal_relation(self, faction_a: str, faction_b: str):
        """取消附庸关系（内部方法）"""
        for k, v in list(self.world.vassal_relations.items()):
            if v in (faction_a, faction_b) and k in (faction_a, faction_b):
                del self.world.vassal_relations[k]

    # ================================================================
    # 停战条约
    # ================================================================

    def sign_peace_treaty(self, faction_a: str, faction_b: str,
                          duration: int = None) -> dict:
        """签订停战条约"""
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "关系不存在"}

        if rel.stance != DiplomaticStance.WAR:
            return {"success": False, "message": "双方未处于交战状态"}

        duration = duration or self.const.get("peace_treaty_duration", 12)
        cost_result = self._apply_diplo_cost(faction_a, "propose_truce")
        if not cost_result["success"]:
            return cost_result

        rel.stance = DiplomaticStance.TRUCE
        rel.attitude = 0
        rel.treaty_expiry = self.world.current_round + duration
        rel.trade_active = False

        # 创建条约记录
        treaty = TreatyRecord(
            treaty_id=f"peace_{faction_a}_{faction_b}_{self.world.current_round}",
            treaty_type="peace",
            factions=[faction_a, faction_b],
            signed_round=self.world.current_round,
            expires_round=self.world.current_round + duration,
            terms={"duration": duration, "type": "peace"},
        )
        self.world.alliance_treaties.append(treaty)

        self._create_diplomatic_event(faction_a, faction_b, "war", "truce", f"停战{duration}回合")

        return {
            "success": True,
            "treaty_id": treaty.treaty_id,
            "expires_round": treaty.expires_round,
            "message": f"停战条约已签订，持续{duration}回合",
        }

    # ================================================================
    # 外交事件记录
    # ================================================================

    def _create_diplomatic_event(self, faction_a: str, faction_b: str,
                                  old_stance: str, new_stance: str, reason: str):
        """创建外交事件并写入 events_log"""
        a_name = self.world.get_faction(faction_a).name if self.world.get_faction(faction_a) else faction_a
        b_name = self.world.get_faction(faction_b).name if self.world.get_faction(faction_b) else faction_b

        action_labels = {
            "war": f"{a_name}向{b_name}宣战！",
            "truce": f"{a_name}与{b_name}签订停战条约。",
            "alliance": f"{a_name}与{b_name}缔结同盟。",
            "vassal": f"{b_name}成为{a_name}的附庸。",
            "neutral": f"{a_name}与{b_name}关系降为中立。",
            "open_trade": f"{a_name}与{b_name}开通贸易路线。",
            "marriage": f"{a_name}与{b_name}联姻结好。",
            "coalition": f"{a_name}与{b_name}共建联邦。",
        }

        title = action_labels.get(new_stance, f"{a_name}与{b_name}外交关系变化")

        event = {
            "event_id": f"diplo_{faction_a}_{faction_b}_{self.world.current_round}_{random.randint(1000,9999)}",
            "event_type": "diplomacy",
            "severity": "major" if new_stance in ("war", "alliance", "coalition") else "minor",
            "round": self.world.current_round,
            "title": title,
            "description": title + (f"（{reason}）" if reason else ""),
            "faction_id": faction_a,
            "tile_id": "",
            "effects": {
                "faction_a": faction_a,
                "faction_b": faction_b,
                "from": old_stance,
                "to": new_stance,
                "reason": reason,
            },
            "narrative": title,
        }
        self.world.events_log.append(event)

    # ================================================================
    # 外交关系查询
    # ================================================================

    def get_diplomatic_summary(self, faction_id: str) -> dict:
        """获取势力的外交摘要"""
        summary = {
            "faction_id": faction_id,
            "allies": [],
            "enemies": [],
            "vassals": [],
            "suzerain": None,
            "trading_partners": [],
            "coalition_id": None,
            "coalition_members": [],
            "active_treaties": [],
        }

        # 同盟/交战国
        for key, rel in self.world.relations.items():
            if rel.faction_a == faction_id:
                other = rel.faction_b
            elif rel.faction_b == faction_id:
                other = rel.faction_a
            else:
                continue

            other_f = self.world.get_faction(other)
            other_name = other_f.name if other_f else other

            if rel.stance == DiplomaticStance.ALLIANCE:
                summary["allies"].append({"faction_id": other, "name": other_name, "attitude": rel.attitude})
            elif rel.stance == DiplomaticStance.WAR:
                summary["enemies"].append({"faction_id": other, "name": other_name, "attitude": rel.attitude})

            if rel.trade_active:
                summary["trading_partners"].append({"faction_id": other, "name": other_name})

            if rel.coalition_id:
                summary["coalition_id"] = rel.coalition_id

        # 附庸
        for vassal, suzerain in self.world.vassal_relations.items():
            if suzerain == faction_id:
                v_f = self.world.get_faction(vassal)
                summary["vassals"].append({"faction_id": vassal, "name": v_f.name if v_f else vassal})
            elif vassal == faction_id:
                s_f = self.world.get_faction(suzerain)
                summary["suzerain"] = {"faction_id": suzerain, "name": s_f.name if s_f else suzerain}

        # 联邦成员
        if summary["coalition_id"] and summary["coalition_id"] in self.world.coalitions:
            for m in self.world.coalitions[summary["coalition_id"]]:
                if m != faction_id:
                    m_f = self.world.get_faction(m)
                    summary["coalition_members"].append({"faction_id": m, "name": m_f.name if m_f else m})

        # 活跃条约
        for treaty in self.world.alliance_treaties:
            if faction_id in treaty.factions:
                summary["active_treaties"].append(treaty.model_dump())

        return summary


# ================================================================
# 朝堂/藩镇引擎
# ================================================================

class CourtEngine:
    """朝堂与藩镇引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = {**DEFAULTS, **(game_const or {})}

    def appoint_official(self, faction_id: str, name: str, position: str,
                         ability: int = 50, loyalty: int = 60) -> dict:
        """任命官员"""
        from server.models.world_state import OfficialRecord
        oid = f"official_{faction_id}_{name}_{self.world.current_round}"
        official = OfficialRecord(
            official_id=oid,
            name=name,
            faction_id=faction_id,
            position=position,
            loyalty=loyalty,
            ability=ability,
        )
        self.world.officials[oid] = official
        if faction_id in self.world.factions:
            self.world.factions[faction_id].officials.append(oid)
        return {"success": True, "official_id": oid, "message": f"{name}已任命为{position}"}

    def dismiss_official(self, official_id: str) -> dict:
        """罢免官员"""
        off = self.world.officials.get(official_id)
        if not off:
            return {"success": False, "message": "官员不存在"}

        faction = self.world.factions.get(off.faction_id)
        if faction and official_id in faction.officials:
            faction.officials.remove(official_id)

        off.is_exiled = True
        self.world.exiled_officials.append(official_id)
        # Bug #15修复: 从world.officials中移除，避免继续消耗俸禄/参与风险计算
        if official_id in self.world.officials:
            del self.world.officials[official_id]
        return {"success": True, "message": f"{off.name}已罢免"}

    def execute_official(self, official_id: str) -> dict:
        """处决官员"""
        off = self.world.officials.get(official_id)
        if not off:
            return {"success": False, "message": "官员不存在"}

        faction = self.world.factions.get(off.faction_id)
        if faction:
            faction.court_stability = max(0, faction.court_stability - 10)
            if official_id in faction.officials:
                faction.officials.remove(official_id)

        self.world.purges.append({
            "round": self.world.current_round,
            "official_id": official_id,
            "name": off.name,
        })

        return {"success": True, "message": f"{off.name}已处决，朝堂动荡"}

    def handle_prisoner(self, prisoner_id: str, action: str) -> dict:
        """俘虏处置（五档）"""
        prisoner = self.world.prisoners.get(prisoner_id)
        if not prisoner:
            return {"success": False, "message": "俘虏不存在"}

        actions = {
            "recruit": "招安入朝",
            "imprison": "长期关押",
            "exile": "流放边疆",
            "execute": "斩首处决",
            "exchange": "交换俘虏",
            "ransom": "索取赎金",
        }
        if action not in actions:
            return {"success": False, "message": f"无效处置方式，可选：{list(actions.keys())}"}

        held_by_faction = self.world.factions.get(prisoner.held_by)
        captured_from = self.world.factions.get(prisoner.captured_from)

        if action == "recruit":
            self.appoint_official(prisoner.held_by, prisoner.name, "降将")
            # 清理已招安的俘虏记录
            if prisoner.prisoner_id in self.world.prisoners:
                del self.world.prisoners[prisoner.prisoner_id]
            if held_by_faction and prisoner.prisoner_id in held_by_faction.prisoners:
                held_by_faction.prisoners.remove(prisoner.prisoner_id)
        elif action == "execute":
            if held_by_faction:
                held_by_faction.reputation = max(0, held_by_faction.reputation - 5)
        elif action == "ransom":
            # 赎金：向俘虏来源势力索取银两
            ransom_amount = random.randint(800, 3000)
            if captured_from and captured_from.is_alive:
                if captured_from.treasury >= ransom_amount:
                    captured_from.treasury -= ransom_amount
                    if held_by_faction:
                        held_by_faction.treasury += ransom_amount
                    self.world.events_log.append({
                        "round": self.world.current_round,
                        "event_type": "ransom_paid",
                        "narrative": f"{captured_from.name}支付{ransom_amount}银两赎回将领{prisoner.name}。",
                    })
                    # 释放俘虏
                    if prisoner.prisoner_id in self.world.prisoners:
                        del self.world.prisoners[prisoner.prisoner_id]
                    if prisoner.prisoner_id in held_by_faction.prisoners:
                        held_by_faction.prisoners.remove(prisoner.prisoner_id)
                    return {"success": True, "action": "索取赎金",
                            "ransom_amount": ransom_amount,
                            "message": f"从{captured_from.name}获得赎金{ransom_amount}银两，{prisoner.name}已被释放"}
                else:
                    return {"success": False, "message": f"{captured_from.name}国库空虚，无力支付赎金"}
            else:
                # 来源势力已灭亡，改为没收财物
                loot = random.randint(300, 800)
                if held_by_faction:
                    held_by_faction.treasury += loot
                if prisoner.prisoner_id in self.world.prisoners:
                    del self.world.prisoners[prisoner.prisoner_id]
                if prisoner.prisoner_id in held_by_faction.prisoners:
                    held_by_faction.prisoners.remove(prisoner.prisoner_id)
                return {"success": True, "action": "没收财物",
                        "ransom_amount": loot,
                        "message": f"{prisoner.name}所属势力已灭亡，没收其财物{loot}银两"}

        # 通用：清除已处置的俘虏记录（除 ransom 外其他操作也应清除）
        if action in ("imprison", "exile", "exchange", "execute"):
            if prisoner.prisoner_id in self.world.prisoners:
                del self.world.prisoners[prisoner.prisoner_id]
            if held_by_faction and prisoner.prisoner_id in held_by_faction.prisoners:
                held_by_faction.prisoners.remove(prisoner.prisoner_id)

        return {"success": True, "action": actions[action], "message": f"已对{prisoner.name}执行{actions[action]}"}

    def check_vassal_rebellion(self, faction_id: str) -> Optional[dict]:
        """检查藩镇叛乱（3.2 增强：真正生成叛军）"""
        # 检查是否有高野心的官员在外
        risk = 5  # 基础风险
        rebel_official = None
        for oid, off in self.world.officials.items():
            if off.faction_id == faction_id and off.loyalty < 20 and off.ability > 60:
                risk += 15
                if random.random() < 0.1:
                    rebel_official = (oid, off)
                risk += off.ability // 10
            elif off.faction_id == faction_id and off.loyalty < 40:
                risk += 5

        # 官员数量少增加风险（朝堂空虚，藩镇坐大）
        risk += max(0, 15 - len([o for o in self.world.officials.values() if o.faction_id == faction_id]))

        risk = min(risk, 100)

        # 3.2 新增：高风险时真正生成叛军
        spawned_rebel = None
        if risk >= 60 and rebel_official:
            oid, off = rebel_official
            from server.core.advanced_features import RebelEngine
            rebel_engine = RebelEngine(self.world, self.const)
            spawned_rebel = rebel_engine.spawn_rebellion(
                faction_id=faction_id,
                troops=random.randint(800, 2000),
                cause=f"{off.name}举兵叛乱",
            )
        elif risk >= 40 and random.random() < 0.15:
            # 民心过低触发民变
            tiles = self.world.get_faction_tiles(faction_id)
            if tiles:
                low_morale_tiles = [t for t in tiles if t.morale < 25]
                if low_morale_tiles:
                    from server.core.advanced_features import RebelEngine
                    rebel_engine = RebelEngine(self.world, self.const)
                    spawned_rebel = rebel_engine.spawn_rebellion(
                        faction_id=faction_id,
                        tile_id=random.choice(low_morale_tiles).tile_id,
                        troops=random.randint(400, 1200),
                        cause="民变",
                    )

        result = {"risk": risk}
        if rebel_official:
            result["rebel"] = rebel_official[0]
            result["name"] = rebel_official[1].name
            result["message"] = f"{rebel_official[1].name}举兵叛乱！"
        if spawned_rebel:
            result["spawned_rebel"] = spawned_rebel

        return result
