"""
季节随机事件引擎 - 四季回合循环机制

职责:
- 每回合判定季节随机事件（洪涝、干旱、蝗灾、瘟疫、流民、兵变、匪患、暴雪、战乱残破）
- 事件影响地块状态（人口、粮食、民心、治安）
- 写入事件日志（events_log）
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    DisasterType, Season, BuildingType,
)

logger = logging.getLogger("yuanmo.season_events")

# 季节事件配置
SEASON_EVENT_CONFIG = {
    Season.SPRING: {
        "flood_chance": 0.06,      # 春汛融雪洪水
        "refugee_chance": 0.04,    # 春季流民涌入
        "mutiny_chance": 0.02,     # 春季兵变较少
        "bandit_chance": 0.03,     # 春季匪患
        "blizzard_chance": 0.0,    # 春季无暴雪
        "drought_chance": 0.03,    # 春旱影响播种
        "locust_chance": 0.01,     # 春末蝗虫孵化
        "plague_chance": 0.02,     # 春季疫病流行
        "spring_plow_bonus": 0.15, # 春耕动员：农田额外产出概率
        "descriptions": {
            "flood": "春汛融雪，{tile}河水泛滥，淹没农田。",
            "refugee": "春荒时节，大批流民涌入{tile}。",
            "mutiny": "春季粮饷不继，{tile}驻军哗变！",
            "bandit": "春暖花开，{tile}境内匪患复燃。",
            "drought": "春雨迟迟未至，{tile}禾苗枯焦，赤地千里。",
            "locust": "春末蝗蝻孵化，{tile}青苗尽被啃食。",
            "plague": "春温乍暖，{tile}疫病流行，染者十之二三。",
        },
    },
    Season.SUMMER: {
        "flood_chance": 0.10,      # 夏季暴雨洪水高发
        "refugee_chance": 0.02,    # 夏季流民较少
        "mutiny_chance": 0.04,     # 酷暑兵变频发
        "bandit_chance": 0.05,     # 夏季匪患活跃
        "blizzard_chance": 0.0,
        "drought_chance": 0.05,    # 伏旱最重
        "locust_chance": 0.03,     # 夏季蝗虫成灾
        "plague_chance": 0.04,     # 夏季瘟疫高发
        "descriptions": {
            "flood": "连日暴雨，{tile}泛滥成灾，粮田被毁。",
            "refugee": "暑热难耐，少量流民逃至{tile}。",
            "mutiny": "酷暑难当，{tile}守军发生兵变！",
            "bandit": "夏夜月黑，{tile}遭遇匪寇劫掠。",
            "drought": "烈日炎炎，{tile}井泉干涸，庄稼尽枯。",
            "locust": "飞蝗蔽日，{tile}田间颗粒无收！",
            "plague": "暑热蒸郁，{tile}瘟疫横行，死者枕藉。",
        },
    },
    Season.AUTUMN: {
        "flood_chance": 0.04,      # 秋雨渐少
        "refugee_chance": 0.03,    # 秋收后少量流民
        "mutiny_chance": 0.03,
        "bandit_chance": 0.06,     # 秋收匪患（抢粮）
        "blizzard_chance": 0.0,
        "drought_chance": 0.02,    # 秋旱较少
        "locust_chance": 0.02,     # 秋蝗残余
        "plague_chance": 0.02,     # 秋凉疫病消退
        "descriptions": {
            "flood": "秋雨连绵，{tile}低洼处积水成涝。",
            "refugee": "秋收之际，邻境流民闻风来投{tile}。",
            "mutiny": "秋粮分配不公，{tile}将士生变！",
            "bandit": "秋收时节，{tile}遭匪寇大肆劫掠！",
            "drought": "秋旱不雨，{tile}晚禾歉收。",
            "locust": "残蝗复起，{tile}秋粮损失惨重。",
            "plague": "秋凉已至，{tile}疫气渐息，然遗患尚存。",
        },
    },
    Season.WINTER: {
        "flood_chance": 0.01,      # 冬季基本无洪水
        "refugee_chance": 0.06,    # 寒冬流民冻毙/涌入城池
        "mutiny_chance": 0.02,     # 冬季兵变
        "bandit_chance": 0.02,     # 冬季匪患收敛
        "blizzard_chance": 0.07,   # 暴雪冻害
        "drought_chance": 0.01,    # 冬季干旱极少
        "locust_chance": 0.0,      # 冬季无蝗虫
        "plague_chance": 0.03,     # 冬季伤寒瘟疫
        "descriptions": {
            "flood": "罕见冬汛，{tile}部分地段积水。",
            "refugee": "凛冬已至，饥寒交迫的流民涌入{tile}。",
            "mutiny": "寒冬柴薪短缺，{tile}将士怨声载道！",
            "bandit": "大雪封山，{tile}边境偶有马贼出没。",
            "blizzard": "暴雪连日，{tile}冻死冻伤无数！",
            "drought": "冬旱无雪，{tile}来年墒情堪忧。",
            "locust": "寒冬之中，蝗蝻尽冻死。",
            "plague": "寒冬疫气，{tile}伤寒流行，老幼多有不测。",
        },
    },
}


class SeasonEventEngine:
    """季节随机事件引擎"""

    def __init__(self, world: WorldState):
        self.world = world

    def process_season_events(self) -> dict:
        """处理当前季节的随机事件，返回事件摘要"""
        season = self.world.current_season
        config = SEASON_EVENT_CONFIG.get(season)
        if not config:
            return {"events_triggered": []}

        result = {
            "season": season.value,
            "events_triggered": [],
        }

        # Bug #41修复: 使用disaster_index调节事件概率
        disaster_mod = 1.0 + (getattr(self.world, 'disaster_index', 0) / 200.0)  # 0→1.0x, 100→1.5x

        # 遍历所有有归属的地块
        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue

            # 春季：春耕动员（额外粮食加成）
            if season == Season.SPRING:
                if random.random() < config.get("spring_plow_bonus", 0.15):
                    bonus = int(tile.population * 0.005)
                    tile.grain += bonus
                    if bonus > 50:
                        result["events_triggered"].append({
                            "tile_id": tile.tile_id,
                            "tile_name": tile.tile_name,
                            "type": "spring_plow",
                            "description": f"春耕动员，{tile.tile_name}农耕兴旺，粮食+{bonus}",
                            "grain_bonus": bonus,
                        })

        # 洪涝判定
        if random.random() < config.get("flood_chance", 0.05) * disaster_mod:
            flood_factor = self._get_terrain_flood_factor(tile)
            if random.random() < flood_factor:
                self._apply_flood_event(tile, config, result)

        # 干旱判定
        if random.random() < config.get("drought_chance", 0.03) * disaster_mod:
            drought_factor = self._get_terrain_drought_factor(tile)
            if random.random() < drought_factor:
                self._apply_drought_event(tile, config, result)

        # 蝗灾判定
        if season != Season.WINTER and random.random() < config.get("locust_chance", 0.02) * disaster_mod:
            self._apply_locust_event(tile, config, result)

        # 瘟疫判定
        if random.random() < config.get("plague_chance", 0.03) * disaster_mod:
            plague_factor = self._get_terrain_plague_factor(tile)
            if random.random() < plague_factor:
                self._apply_plague_event(tile, config, result)

            # 战乱残破判定（仅在有驻军且发生过战斗的地块）
            if tile.troops > 500 and self._check_recent_battle(tile):
                if random.random() < 0.04:
                    self._apply_war_devastation_event(tile, config, result)

            # 流民潮判定
            if random.random() < config.get("refugee_chance", 0.04):
                self._apply_refugee_event(tile, config, result)

            # 兵变判定（仅在有驻军的地块）
            if tile.troops > 300 and random.random() < config.get("mutiny_chance", 0.03):
                self._apply_mutiny_event(tile, config, result)

            # 匪患判定
            if random.random() < config.get("bandit_chance", 0.04):
                # 治安越低，匪患概率越高
                order_factor = max(0.5, (100 - tile.public_order) / 50)
                if random.random() < order_factor:
                    self._apply_bandit_event(tile, config, result)

            # 暴雪判定（仅冬季）
            if season == Season.WINTER and random.random() < config.get("blizzard_chance", 0.07):
                self._apply_blizzard_event(tile, config, result)

        # Bug #42修复: 季节事件修改tile数据后更新世界时间戳
        if result["events_triggered"] and hasattr(self.world, 'mark_updated'):
            self.world.mark_updated()
        return result

    def _check_recent_battle(self, tile: TileState) -> bool:
        """检查地块近期是否发生过战斗"""
        for event in self.world.events_log[-20:]:
            if event.get("tile_id") == tile.tile_id and event.get("event_type") in ("battle", "siege"):
                return True
        return False

    def _get_terrain_flood_factor(self, tile: TileState) -> float:
        """地形洪水系数"""
        factors = {
            TileType.COAST: 1.5,
            TileType.PORT: 1.4,
            TileType.FARMLAND: 1.2,
            TileType.GRASSLAND: 0.8,
            TileType.MOUNTAIN: 0.2,
            TileType.DESERT: 0.1,
            TileType.PASS: 0.3,
            TileType.CITY: 0.6,
            TileType.WATER: 0.0,
            TileType.SEA: 0.0,  # Bug #43修复: 海域不会发生洪水
        }
        return factors.get(tile.tile_type, 1.0)

    def _get_terrain_drought_factor(self, tile: TileState) -> float:
        """地形干旱系数"""
        factors = {
            TileType.DESERT: 2.0,
            TileType.GRASSLAND: 1.5,
            TileType.FARMLAND: 1.3,
            TileType.MOUNTAIN: 0.8,
            TileType.COAST: 0.3,
            TileType.PORT: 0.4,
            TileType.WATER: 0.0,
            TileType.SEA: 0.0,
            TileType.CITY: 0.7,
            TileType.PASS: 1.0,
        }
        return factors.get(tile.tile_type, 1.0)

    def _get_terrain_plague_factor(self, tile: TileState) -> float:
        """地形瘟疫系数"""
        factors = {
            TileType.CITY: 1.8,       # 人口密集，瘟疫传播快
            TileType.PORT: 1.6,       # 港口商旅往来
            TileType.FARMLAND: 0.8,
            TileType.MOUNTAIN: 0.3,   # 山地闭塞
            TileType.DESERT: 0.4,
            TileType.GRASSLAND: 0.5,
            TileType.PASS: 0.6,
            TileType.COAST: 0.7,
            TileType.WATER: 0.2,
            TileType.SEA: 0.1,
        }
        return factors.get(tile.tile_type, 1.0)

    # ============================================================
    # 已有事件（保持不变）
    # ============================================================

    def _apply_flood_event(self, tile: TileState, config: dict, result: dict):
        """应用洪水事件"""
        grain_loss = int(tile.grain * random.uniform(0.1, 0.3))
        pop_loss = int(tile.population * random.uniform(0.01, 0.05))
        morale_loss = random.randint(3, 8)

        tile.grain = max(0, tile.grain - grain_loss)
        tile.population = max(100, tile.population - pop_loss)
        tile.morale = max(0, tile.morale - morale_loss)
        if DisasterType.FLOOD not in tile.disasters:
            tile.disasters.append(DisasterType.FLOOD)

        desc_template = config.get("descriptions", {}).get("flood", "{tile}洪水泛滥")
        desc = desc_template.format(tile=tile.tile_name)

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "flood",
            "description": desc,
            "grain_loss": grain_loss, "pop_loss": pop_loss,
            "morale_loss": morale_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"flood_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"洪水 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"grain_loss": grain_loss, "pop_loss": pop_loss},
            "narrative": desc,
        })

    def _apply_drought_event(self, tile: TileState, config: dict, result: dict):
        """应用干旱事件"""
        grain_loss = int(tile.grain * random.uniform(0.15, 0.4))
        pop_loss = int(tile.population * random.uniform(0.02, 0.08))
        morale_loss = random.randint(5, 12)
        order_loss = random.randint(2, 6)

        tile.grain = max(0, tile.grain - grain_loss)
        tile.population = max(100, tile.population - pop_loss)
        tile.morale = max(0, tile.morale - morale_loss)
        tile.public_order = max(0, tile.public_order - order_loss)
        if DisasterType.DROUGHT not in tile.disasters:
            tile.disasters.append(DisasterType.DROUGHT)

        desc_template = config.get("descriptions", {}).get("drought", "{tile}大旱")
        desc = desc_template.format(tile=tile.tile_name)

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "drought",
            "description": desc,
            "grain_loss": grain_loss, "pop_loss": pop_loss,
            "morale_loss": morale_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"drought_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"干旱 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"grain_loss": grain_loss, "pop_loss": pop_loss},
            "narrative": desc,
        })

    def _apply_locust_event(self, tile: TileState, config: dict, result: dict):
        """应用蝗灾事件"""
        grain_loss = int(tile.grain * random.uniform(0.3, 0.6))
        morale_loss = random.randint(8, 18)
        order_loss = random.randint(3, 8)

        tile.grain = max(0, tile.grain - grain_loss)
        tile.morale = max(0, tile.morale - morale_loss)
        tile.public_order = max(0, tile.public_order - order_loss)
        if DisasterType.LOCUST not in tile.disasters:
            tile.disasters.append(DisasterType.LOCUST)

        desc_template = config.get("descriptions", {}).get("locust", "{tile}蝗灾肆虐")
        desc = desc_template.format(tile=tile.tile_name)

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "locust",
            "description": desc,
            "grain_loss": grain_loss,
            "morale_loss": morale_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"locust_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "critical",
            "round": self.world.current_round,
            "title": f"蝗灾 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"grain_loss": grain_loss},
            "narrative": desc,
        })

    def _apply_plague_event(self, tile: TileState, config: dict, result: dict):
        """应用瘟疫事件"""
        pop_loss = int(tile.population * random.uniform(0.05, 0.2))
        morale_loss = random.randint(8, 20)
        order_loss = random.randint(5, 12)
        # 医馆可降低瘟疫影响
        clinic_level = tile.buildings.get(BuildingType.CLINIC, 0)
        reduction = clinic_level * 0.3
        pop_loss = max(10, int(pop_loss * (1 - reduction)))
        morale_loss = max(2, int(morale_loss * (1 - reduction)))

        tile.population = max(100, tile.population - pop_loss)
        tile.morale = max(0, tile.morale - morale_loss)
        tile.public_order = max(0, tile.public_order - order_loss)
        if DisasterType.PLAGUE not in tile.disasters:
            tile.disasters.append(DisasterType.PLAGUE)

        desc_template = config.get("descriptions", {}).get("plague", "{tile}瘟疫流行")
        desc = desc_template.format(tile=tile.tile_name)

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "plague",
            "description": desc,
            "pop_loss": pop_loss,
            "morale_loss": morale_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"plague_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "critical",
            "round": self.world.current_round,
            "title": f"瘟疫 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"pop_loss": pop_loss},
            "narrative": desc,
        })

    def _apply_war_devastation_event(self, tile: TileState, config: dict, result: dict):
        """应用战乱残破事件"""
        pop_loss = int(tile.population * random.uniform(0.03, 0.1))
        grain_loss = int(tile.grain * random.uniform(0.05, 0.15))
        morale_loss = random.randint(5, 15)
        order_loss = random.randint(5, 10)

        tile.population = max(100, tile.population - pop_loss)
        tile.grain = max(0, tile.grain - grain_loss)
        tile.morale = max(0, tile.morale - morale_loss)
        tile.public_order = max(0, tile.public_order - order_loss)
        if DisasterType.WAR_DEVASTATION not in tile.disasters:
            tile.disasters.append(DisasterType.WAR_DEVASTATION)

        desc = f"兵燹过境，{tile.tile_name}残破不堪，民不聊生。"

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "war_devastation",
            "description": desc,
            "pop_loss": pop_loss,
            "grain_loss": grain_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"war_dev_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"战乱残破 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"pop_loss": pop_loss, "grain_loss": grain_loss},
            "narrative": desc,
        })

    def _apply_refugee_event(self, tile: TileState, config: dict, result: dict):
        """应用流民事件"""
        # 流民涌入：增加人口但消耗粮食、降低治安
        refugee_count = random.randint(200, 1000) if tile.tile_type == TileType.CITY else random.randint(50, 300)
        grain_cost = int(refugee_count * 0.03)
        morale_change = random.randint(-3, 2)  # 可能提振劳动力也可能引起不安

        tile.population += refugee_count
        tile.grain = max(0, tile.grain - grain_cost)
        tile.morale = max(0, min(100, tile.morale + morale_change))
        tile.public_order = max(0, tile.public_order - random.randint(2, 5))
        if DisasterType.REFUGEE_WAVE not in tile.disasters:
            tile.disasters.append(DisasterType.REFUGEE_WAVE)

        desc_template = config.get("descriptions", {}).get("refugee", "流民涌入{tile}")
        desc = desc_template.format(tile=tile.tile_name) + f" 人口+{refugee_count}"

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "refugee",
            "description": desc,
            "refugee_count": refugee_count,
            "grain_cost": grain_cost,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"refugee_{tile.tile_id}_{self.world.current_round}",
            "event_type": "refugee",
            "severity": "minor",
            "round": self.world.current_round,
            "title": f"流民 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"refugee_count": refugee_count, "grain_cost": grain_cost},
            "narrative": desc,
        })

    def _apply_mutiny_event(self, tile: TileState, config: dict, result: dict):
        """应用兵变事件"""
        # 兵变：部分兵力叛逃或自相残杀
        rebel_count = int(tile.troops * random.uniform(0.1, 0.3))
        morale_loss = random.randint(10, 25)
        grain_loss = int(tile.grain * random.uniform(0.05, 0.15))

        tile.troops = max(0, tile.troops - rebel_count)
        tile.morale = max(0, tile.morale - morale_loss)
        tile.grain = max(0, tile.grain - grain_loss)
        if DisasterType.MUTINY not in tile.disasters:
            tile.disasters.append(DisasterType.MUTINY)

        desc_template = config.get("descriptions", {}).get("mutiny", "{tile}发生兵变")
        desc = desc_template.format(tile=tile.tile_name) + f" 损兵{rebel_count}"

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "mutiny",
            "description": desc,
            "rebel_count": rebel_count,
            "morale_loss": morale_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"mutiny_{tile.tile_id}_{self.world.current_round}",
            "event_type": "rebellion",
            "severity": "critical",
            "round": self.world.current_round,
            "title": f"兵变 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"rebel_count": rebel_count, "morale_loss": morale_loss},
            "narrative": desc,
        })

    def _apply_bandit_event(self, tile: TileState, config: dict, result: dict):
        """应用匪患事件"""
        grain_stolen = int(tile.grain * random.uniform(0.05, 0.2))
        treasury_stolen = int(tile.treasury * random.uniform(0.03, 0.12))
        pop_loss = random.randint(10, 80)
        order_loss = random.randint(3, 8)

        tile.grain = max(0, tile.grain - grain_stolen)
        tile.treasury = max(0, tile.treasury - treasury_stolen)
        tile.population = max(100, tile.population - pop_loss)
        tile.public_order = max(0, tile.public_order - order_loss)
        if DisasterType.BANDIT_RAID not in tile.disasters:
            tile.disasters.append(DisasterType.BANDIT_RAID)

        desc_template = config.get("descriptions", {}).get("bandit", "{tile}遭遇匪患")
        desc = desc_template.format(tile=tile.tile_name) + f" 粮失{grain_stolen}，银失{treasury_stolen}"

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "bandit",
            "description": desc,
            "grain_stolen": grain_stolen,
            "treasury_stolen": treasury_stolen,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"bandit_{tile.tile_id}_{self.world.current_round}",
            "event_type": "bandit_raid",
            "severity": "minor",
            "round": self.world.current_round,
            "title": f"匪患 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"grain_stolen": grain_stolen, "treasury_stolen": treasury_stolen},
            "narrative": desc,
        })

    def _apply_blizzard_event(self, tile: TileState, config: dict, result: dict):
        """应用暴雪事件（仅冬季）"""
        # 暴雪：人口冻死、粮食消耗增加、城防受损
        pop_loss = int(tile.population * random.uniform(0.02, 0.07))
        grain_loss = int(tile.grain * random.uniform(0.1, 0.2))
        if tile.fortification > 0:
            fort_damage = random.randint(0, 1)
            tile.fortification = max(0, tile.fortification - fort_damage)

        tile.population = max(100, tile.population - pop_loss)
        tile.grain = max(0, tile.grain - grain_loss)
        tile.morale = max(0, tile.morale - random.randint(5, 10))
        if DisasterType.BLIZZARD not in tile.disasters:
            tile.disasters.append(DisasterType.BLIZZARD)

        desc_template = config.get("descriptions", {}).get("blizzard", "{tile}遭遇暴雪")
        desc = desc_template.format(tile=tile.tile_name) + f" 冻死{pop_loss}人"

        event_record = {
            "tile_id": tile.tile_id, "tile_name": tile.tile_name,
            "type": "blizzard",
            "description": desc,
            "pop_loss": pop_loss,
            "grain_loss": grain_loss,
        }
        result["events_triggered"].append(event_record)

        self.world.events_log.append({
            "event_id": f"blizzard_{tile.tile_id}_{self.world.current_round}",
            "event_type": "disaster",
            "severity": "major",
            "round": self.world.current_round,
            "title": f"暴雪 · {tile.tile_name}",
            "description": desc,
            "faction_id": tile.faction_id,
            "tile_id": tile.tile_id,
            "effects": {"pop_loss": pop_loss, "grain_loss": grain_loss},
            "narrative": desc,
        })
