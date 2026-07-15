"""
3.2 武将人格战术引擎
- 武将生成、招募、任命、叛变
- 军团编制管理
- 武将委任自主作战
- 武将战术技能触发
"""
from __future__ import annotations
import logging
import random
import uuid
from typing import Optional

logger = logging.getLogger("yuanmo.general")
from server.models.generals import (
    General, GeneralRarity, TacticType, UnitType,
    Legion, LegionFormation,
)
from server.models.world_state import WorldState, FactionState, TileState


class GeneralEngine:
    """武将系统引擎"""

    # 元末历史名将预设
    HISTORICAL_GENERALS = [
        {
            "name": "徐达", "rarity": "legendary", "faction_hint": "faction_zhuyuanzhang",
            "command": 95, "might": 78, "intellect": 88, "loyalty": 95, "charisma": 85,
            "cavalry_proficiency": 90, "infantry_proficiency": 85,
            "tactics": ["shock_cavalry", "siege_expert", "logistics_master"],
            "personality": "balanced",
            "biography": "明朝开国第一功臣，北伐灭元主将。"
        },
        {
            "name": "常遇春", "rarity": "legendary", "faction_hint": "faction_zhuyuanzhang",
            "command": 88, "might": 98, "intellect": 60, "loyalty": 90, "charisma": 75,
            "cavalry_proficiency": 95, "infantry_proficiency": 70,
            "tactics": ["shock_cavalry", "forced_march", "night_raid"],
            "personality": "aggressive",
            "biography": "每战必先登，自言能将十万众横行天下。"
        },
        {
            "name": "刘基", "rarity": "legendary", "faction_hint": "faction_zhuyuanzhang",
            "command": 70, "might": 35, "intellect": 98, "loyalty": 85, "charisma": 60,
            "infantry_proficiency": 60, "archer_proficiency": 75,
            "tactics": ["fire_attack", "psychological_war", "ambush_master"],
            "personality": "cautious",
            "biography": "字伯温，运筹帷幄，料事如神。"
        },
        {
            "name": "张定边", "rarity": "elite", "faction_hint": "faction_chenyouliang",
            "command": 85, "might": 92, "intellect": 65, "loyalty": 95, "charisma": 70,
            "navy_proficiency": 90, "infantry_proficiency": 75,
            "tactics": ["naval_raider", "last_stand"],
            "personality": "aggressive",
            "biography": "陈汉第一勇将，鄱阳湖水战威震天下。"
        },
        {
            "name": "王保保", "rarity": "legendary", "faction_hint": "faction_wangbaobao",
            "command": 92, "might": 85, "intellect": 82, "loyalty": 98, "charisma": 80,
            "cavalry_proficiency": 95, "infantry_proficiency": 70,
            "tactics": ["shock_cavalry", "forced_march", "loyal_commander"],
            "personality": "defensive",
            "biography": "扩廓帖木儿，元末第一名将，忠勇无双。"
        },
        {
            "name": "脱脱", "rarity": "elite", "faction_hint": "faction_yuan",
            "command": 78, "might": 55, "intellect": 90, "loyalty": 88, "charisma": 75,
            "infantry_proficiency": 80, "siege_proficiency": 75,
            "tactics": ["logistics_master", "fortress_defender"],
            "personality": "cautious",
            "biography": "元末名相，脱脱更化，力挽狂澜。"
        },
        {
            "name": "傅友德", "rarity": "elite", "faction_hint": "faction_zhuyuanzhang",
            "command": 82, "might": 88, "intellect": 72, "loyalty": 85, "charisma": 68,
            "infantry_proficiency": 85, "archer_proficiency": 70,
            "tactics": ["ambush_master", "river_crossing"],
            "personality": "aggressive",
            "biography": "从西吴至大明，攻无不克，取四川平云南。"
        },
        {
            "name": "方国珍", "rarity": "elite", "faction_hint": "faction_fangguozhen",
            "command": 65, "might": 55, "intellect": 75, "loyalty": 50, "charisma": 70,
            "navy_proficiency": 90, "cavalry_proficiency": 30,
            "tactics": ["naval_raider", "logistics_master"],
            "personality": "cautious",
            "biography": "浙东海上枭雄，以海贸起家。"
        },
        {
            "name": "明玉珍", "rarity": "elite", "faction_hint": "faction_mingyuzhen",
            "command": 72, "might": 65, "intellect": 68, "loyalty": 80, "charisma": 85,
            "infantry_proficiency": 80, "spearman_proficiency": 75,
            "tactics": ["mountain_guard", "fortress_defender"],
            "personality": "defensive",
            "biography": "据蜀称帝，仁厚爱民。"
        },
        {
            "name": "李文忠", "rarity": "elite", "faction_hint": "faction_zhuyuanzhang",
            "command": 80, "might": 78, "intellect": 75, "loyalty": 90, "charisma": 70,
            "cavalry_proficiency": 82, "infantry_proficiency": 78,
            "tactics": ["forced_march", "flank_commander"],
            "personality": "balanced",
            "biography": "朱元璋外甥，两次北伐横扫漠北。"
        },
    ]

    # 随机武将名
    SURNAMES = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗"]
    GIVEN_NAMES = ["文远", "子龙", "元让", "孟起", "公瑾", "伯符", "仲谋",
                   "季玉", "叔宝", "士元", "奉先", "云长", "翼德", "子敬",
                   "武安", "承恩", "天佑", "克敌", "破虏", "定远"]

    def __init__(self, world: WorldState):
        self.world = world

    # ================================================================
    # 武将生成
    # ================================================================

    def generate_random_general(self, faction_id: str, rarity: Optional[GeneralRarity] = None) -> General:
        """随机生成武将"""
        if rarity is None:
            # 概率分布: 60%普通, 25%老将, 12%精英, 3%传奇
            roll = random.random()
            if roll < 0.03:
                rarity = GeneralRarity.LEGENDARY
            elif roll < 0.15:
                rarity = GeneralRarity.ELITE
            elif roll < 0.40:
                rarity = GeneralRarity.VETERAN
            else:
                rarity = GeneralRarity.COMMON

        name = f"{random.choice(self.SURNAMES)}{random.choice(self.GIVEN_NAMES)}"
        general_id = f"gen_{faction_id}_{uuid.uuid4().hex[:8]}"

        # 稀有度影响基础属性
        base_stats = {
            GeneralRarity.LEGENDARY: (70, 95),
            GeneralRarity.ELITE: (55, 85),
            GeneralRarity.VETERAN: (40, 70),
            GeneralRarity.COMMON: (25, 55),
        }
        stat_range = base_stats[rarity]

        # 随机战术
        tactics = self._roll_random_tactics(rarity)

        # 随机性格
        personalities = ["aggressive", "defensive", "cautious", "reckless", "balanced"]
        personality_weights = [0.25, 0.25, 0.20, 0.10, 0.20]
        personality = random.choices(personalities, weights=personality_weights, k=1)[0]

        return General(
            general_id=general_id,
            name=name,
            faction_id=faction_id,
            rarity=rarity,
            command=random.randint(*stat_range),
            might=random.randint(*stat_range),
            intellect=random.randint(*stat_range),
            loyalty=random.randint(40, 80),
            charisma=random.randint(*stat_range),
            infantry_proficiency=random.randint(*stat_range),
            cavalry_proficiency=random.randint(*stat_range),
            archer_proficiency=random.randint(*stat_range),
            spearman_proficiency=random.randint(*stat_range),
            navy_proficiency=random.randint(*stat_range),
            siege_proficiency=random.randint(*stat_range),
            tactics=tactics,
            personality=personality,
            biography=f"乱世中崛起的将领，效力于{self.world.get_faction(faction_id).name if self.world.get_faction(faction_id) else faction_id}。",
        )

    def _roll_random_tactics(self, rarity: GeneralRarity) -> list[TacticType]:
        """根据稀有度投骰随机战术"""
        num_tactics = {
            GeneralRarity.LEGENDARY: 3,
            GeneralRarity.ELITE: 2,
            GeneralRarity.VETERAN: 1,
            GeneralRarity.COMMON: 0,
        }[rarity]

        if num_tactics == 0:
            return []

        all_tactics = list(TacticType)
        selected = random.sample(all_tactics, min(num_tactics, len(all_tactics)))
        return selected

    def recruit_historical_general(self, faction_id: str, general_name: str) -> Optional[General]:
        """招募历史名将"""
        for template in self.HISTORICAL_GENERALS:
            if template["name"] == general_name and template["faction_hint"] == faction_id:
                general_id = f"gen_{faction_id}_{uuid.uuid4().hex[:8]}"
                return General(
                    general_id=general_id,
                    name=template["name"],
                    faction_id=faction_id,
                    rarity=GeneralRarity(template["rarity"]),
                    command=template["command"],
                    might=template["might"],
                    intellect=template["intellect"],
                    loyalty=template["loyalty"],
                    charisma=template["charisma"],
                    infantry_proficiency=template.get("infantry_proficiency", 50),
                    cavalry_proficiency=template.get("cavalry_proficiency", 50),
                    archer_proficiency=template.get("archer_proficiency", 50),
                    spearman_proficiency=template.get("spearman_proficiency", 50),
                    navy_proficiency=template.get("navy_proficiency", 50),
                    siege_proficiency=template.get("siege_proficiency", 50),
                    tactics=[TacticType(t) for t in template["tactics"]],
                    personality=template["personality"],
                    biography=template["biography"],
                )
        return None

    def init_faction_generals(self, faction_id: str) -> list[General]:
        """初始化势力武将（开局时调用）"""
        generals = []

        # 为每个势力生成2-4个随机武将
        num_generals = random.randint(2, 4)
        for _ in range(num_generals):
            gen = self.generate_random_general(faction_id)
            generals.append(gen)

        # 尝试招募历史名将（如果匹配）
        for template in self.HISTORICAL_GENERALS:
            if template["faction_hint"] == faction_id:
                gen = self.recruit_historical_general(faction_id, template["name"])
                if gen:
                    generals.append(gen)

        return generals

    # ================================================================
    # 人才市场：流浪武将生成与招募
    # ================================================================

    def get_faction_generals(self, faction_id: str) -> list[General]:
        """获取势力武将列表"""
        return self.world.__dict__.get("_generals", {}).get(faction_id, [])

    def generate_wandering_talents(self, count: int = 5) -> list[General]:
        """生成流浪武将（人才市场候选）——不属于任何势力"""
        talents = []
        for _ in range(count):
            gen = self.generate_random_general("_wandering")
            gen.faction_id = "_wandering"
            talents.append(gen)
        return talents

    def recruit_talent(
        self, faction_id: str, general_id: str, cost_silver: int = 500
    ) -> dict:
        """
        从人才市场招募流浪武将
        返回: {success, general, message}
        """
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        if faction.treasury < cost_silver:
            return {"success": False, "message": f"银两不足（需要{cost_silver}，当前{faction.treasury}）"}

        # 尝试从己方武将查找（避免重复招募）
        existing = self.get_faction_generals(faction_id)
        for g in existing:
            if g.general_id == general_id:
                return {"success": False, "message": "该武将已在麾下"}

        # 从玩家已招募的 `_wandering` 池中移除该武将
        # 实际逻辑：将武将的 faction_id 改为目标势力
        if "_generals" not in self.world.__dict__:
            self.world.__dict__["_generals"] = {}

        # 扣费
        faction.treasury -= cost_silver

        # 将流浪武将分配至势力
        gen = None
        for fid, gens in list(self.world.__dict__["_generals"].items()):
            for g in gens:
                if g.general_id == general_id:
                    gen = g
                    gens.remove(g)
                    break
            if gen:
                break

        if not gen:
            return {"success": False, "message": "该武将已不知所踪"}

        gen.faction_id = faction_id
        gen.loyalty = max(50, min(90, gen.loyalty + 10))  # 知遇之恩 +10忠诚
        self.world.__dict__["_generals"].setdefault(faction_id, []).append(gen)

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "talent_recruited",
            "narrative": f"{faction.name}花费{cost_silver}两银两招揽了{gen.name}入朝。",
        })

        return {
            "success": True,
            "general": gen.model_dump(),
            "message": f"成功招揽{gen.name}（{gen.rarity.value}）入朝！",
        }

    # ================================================================
    # 军团编制
    # ================================================================

    def create_legion(
        self,
        name: str,
        faction_id: str,
        commander: General,
        unit_composition: dict[str, int],
        tile_id: str = "",
        formation: LegionFormation = LegionFormation.BALANCED,
    ) -> Legion:
        """创建军团"""
        # 检查武将是否已属于其他军团
        if commander.is_assigned and commander.assigned_legion_id:
            raise ValueError(f"武将 {commander.name} 已在军团 {commander.assigned_legion_id} 中，每位武将只能属于一个军团")

        legion_id = f"legion_{faction_id}_{uuid.uuid4().hex[:8]}"
        legion = Legion(
            legion_id=legion_id,
            name=name,
            faction_id=faction_id,
            commander_id=commander.general_id,
            unit_composition=unit_composition,
            current_tile=tile_id,
            formation=formation,
            supply_range=4,
            total_troops=sum(unit_composition.values()),
            morale=60,
        )

        # 后勤大师：补给范围+2
        if commander.has_tactic(TacticType.LOGISTICS_MASTER):
            legion.supply_range += 2

        # 标记武将已出任
        commander.is_assigned = True
        commander.assigned_tile = tile_id
        commander.assigned_legion_id = legion_id

        return legion

    def assign_units_to_legion(
        self,
        legion: Legion,
        unit_type: UnitType,
        count: int,
        tile: TileState,
    ) -> dict:
        """从一个地块抽调兵种到军团"""
        result = {"success": False, "message": "", "assigned": 0}

        if tile.troops < count:
            result["message"] = f"兵力不足：需要{count}，现有{tile.troops}"
            return result

        # 从地块抽调
        tile.troops -= count
        legion.unit_composition[unit_type.value] = legion.unit_composition.get(unit_type.value, 0) + count
        legion.total_troops = legion.get_total_troops()

        result["success"] = True
        result["assigned"] = count
        result["message"] = f"已向{legion.name}编入{unit_type.value}{count}人"
        return result

    # ================================================================
    # 武将委任自主作战
    # ================================================================

    def set_legion_autonomous(self, legion: Legion, enabled: bool, priority: str = "defensive"):
        """设置军团委任自主作战"""
        legion.is_autonomous = enabled
        legion.auto_priority = priority

    def run_autonomous_legion_turn(self, legion: Legion, general: General) -> dict:
        """
        委任军团自主行动（每回合AI决策）
        
        返回: {actions: [...], results: [...]}
        """
        if not legion.is_autonomous:
            return {"actions": [], "results": []}

        actions = []
        results = []

        # 检查当前地块
        current_tile = self.world.get_tile(legion.current_tile)
        if not current_tile:
            return {"actions": [], "results": [], "error": "军团位置无效"}

        faction = self.world.get_faction(legion.faction_id)
        if not faction:
            return {"actions": [], "results": [], "error": "势力不存在"}

        personality = general.personality
        auto_priority = legion.auto_priority

        # ===== 决策树 =====
        # 1. 防守优先：固守要地
        if auto_priority == "defensive":
            actions.extend(self._defensive_decision(legion, general, current_tile, faction))
        # 2. 进攻优先：寻找目标
        elif auto_priority == "offensive":
            actions.extend(self._offensive_decision(legion, general, current_tile, faction))
        # 3. 劫掠优先：削弱敌方经济
        elif auto_priority == "raid":
            actions.extend(self._raid_decision(legion, general, current_tile, faction))
        # 4. 支援优先：协防盟友
        elif auto_priority == "support":
            actions.extend(self._support_decision(legion, general, current_tile, faction))

        return {"actions": actions, "results": results, "legion_id": legion.legion_id, "general": general.name}

    def _defensive_decision(self, legion: Legion, general: General, tile: TileState, faction: FactionState) -> list[dict]:
        """防守决策：固守、筑城、反击"""
        actions = []

        # 检查是否有敌军邻接
        neighbors = self._get_adjacent_tiles(tile.tile_id)
        enemy_nearby = [n for n in neighbors if n.faction_id and n.faction_id != legion.faction_id]

        if enemy_nearby:
            # 防守型性格：固守待援
            if general.personality in ("defensive", "cautious"):
                actions.append({
                    "type": "fortify",
                    "tile_id": tile.tile_id,
                    "reason": f"{general.name}发现敌军邻接，固守{tile.tile_name}",
                    "priority": "high",
                })
            # 激进型性格：主动反击
            elif general.personality in ("aggressive", "reckless"):
                weakest = min(enemy_nearby, key=lambda t: t.troops)
                actions.append({
                    "type": "counter_attack",
                    "target_tile": weakest.tile_id,
                    "target_name": weakest.tile_name,
                    "reason": f"{general.name}性格刚烈，主动出击{weakest.tile_name}",
                    "priority": "high",
                })
        else:
            # 无敌军：训练或筑城
            actions.append({
                "type": "train",
                "tile_id": tile.tile_id,
                "reason": f"{general.name}在{tile.tile_name}操练军马",
                "priority": "low",
            })

        return actions

    def _offensive_decision(self, legion: Legion, general: General, tile: TileState, faction: FactionState) -> list[dict]:
        """进攻决策：寻找最弱邻敌"""
        actions = []
        neighbors = self._get_adjacent_tiles(tile.tile_id)

        # 寻找可攻击目标
        targets = []
        for n in neighbors:
            if n.faction_id and n.faction_id != legion.faction_id:
                rel = self.world.get_relation(legion.faction_id, n.faction_id)
                if rel:
                    # 优先攻击已交战势力
                    targets.append({
                        "tile": n,
                        "is_at_war": rel.stance.value == "war",
                        "troops": n.troops,
                    })

        if not targets:
            actions.append({"type": "patrol", "reason": f"{general.name}率{legion.name}巡视防区"})
            return actions

        # 性格影响目标选择
        if general.personality == "reckless":
            # 莽撞：攻击任意目标（无视实力）
            target = random.choice(targets)
        elif general.personality == "cautious":
            # 谨慎：只攻击弱势目标
            weak_targets = [t for t in targets if t["troops"] < legion.get_total_troops() * 0.7]
            if not weak_targets:
                return actions
            target = weak_targets[0]
        else:
            # 均衡：优先交战势力，其次最弱
            war_targets = [t for t in targets if t["is_at_war"]]
            if war_targets:
                target = min(war_targets, key=lambda t: t["troops"])
            else:
                target = min(targets, key=lambda t: t["troops"])

        actions.append({
            "type": "attack",
            "target_tile": target["tile"].tile_id,
            "target_name": target["tile"].tile_name,
            "reason": f"{general.name}率{legion.name}进攻{target['tile'].tile_name}",
            "priority": "high",
        })

        return actions

    def _raid_decision(self, legion: Legion, general: General, tile: TileState, faction: FactionState) -> list[dict]:
        """劫掠决策"""
        actions = []
        neighbors = self._get_adjacent_tiles(tile.tile_id)

        # 寻找富裕邻敌地块
        rich_targets = []
        for n in neighbors:
            if n.faction_id and n.faction_id != legion.faction_id:
                if n.grain > 100 or n.treasury > 100:
                    rich_targets.append(n)

        if rich_targets:
            target = max(rich_targets, key=lambda t: t.grain + t.treasury * 2)
            actions.append({
                "type": "raid",
                "target_tile": target.tile_id,
                "target_name": target.tile_name,
                "reason": f"{general.name}率{legion.name}劫掠富庶的{target.tile_name}",
                "priority": "high",
            })
        else:
            actions.append({"type": "scout", "reason": "斥候四出寻找可劫掠目标"})

        return actions

    def _support_decision(self, legion: Legion, general: General, tile: TileState, faction: FactionState) -> list[dict]:
        """支援盟友决策"""
        actions = []

        # 查找正在交战的盟友
        all_tiles = self.world.get_faction_tiles(legion.faction_id)
        battlefronts = []
        for t in all_tiles:
            neighbors = self._get_adjacent_tiles(t.tile_id)
            for n in neighbors:
                if n.faction_id and n.faction_id != legion.faction_id:
                    rel = self.world.get_relation(legion.faction_id, n.faction_id)
                    if rel and rel.stance.value == "war":
                        battlefronts.append(t)

        if battlefronts:
            target = random.choice(battlefronts)
            actions.append({
                "type": "march",
                "target_tile": target.tile_id,
                "target_name": target.tile_name,
                "reason": f"{general.name}率{legion.name}驰援{target.tile_name}前线",
                "priority": "high",
            })

        return actions

    def _get_adjacent_tiles(self, tile_id: str) -> list[TileState]:
        """获取邻接地块（通过 world 关系查询）"""
        # 简化实现：查找所有与目标接壤的地块
        try:
            from server.map.admin_hierarchy import get_territory_graph
            graph = get_territory_graph()
            neighbors = graph.get(tile_id, [])
            return [self.world.get_tile(nid) for nid in neighbors if self.world.get_tile(nid)]
        except Exception as e:
            logger.debug(f"[GeneralEngine] 邻接查询失败，返回空列表: {e}")
            return []

    # ================================================================
    # 武将叛变 / 忠诚度
    # ================================================================

    def check_general_defection(self, general: General) -> tuple[bool, str]:
        """
        检查武将是否叛变
        
        返回: (是否叛变, 原因)
        """
        if general.loyalty >= 60:
            return False, ""
        if general.loyalty >= 40 and random.random() > 0.15:
            return False, ""

        # 低忠诚武将叛变
        prob = (60 - general.loyalty) / 100.0  # 忠诚30 → 30%概率
        if general.personality == "reckless":
            prob *= 1.3

        if random.random() < prob:
            # 寻找可投奔的势力
            candidates = []
            for fid, fac in self.world.factions.items():
                if fid != general.faction_id and fac.is_alive:
                    rel = self.world.get_relation(general.faction_id, fid)
                    if rel and rel.stance.value not in ("war",):
                        candidates.append((fid, fac.name))

            if candidates:
                target_fid, target_name = random.choice(candidates)
                general.faction_id = target_fid
                general.loyalty = 50  # 投奔后重置忠诚
                return True, f"{general.name}因忠诚度不足，叛投{target_name}！"

        return False, ""

    # ================================================================
    # 战术触发
    # ================================================================

    def trigger_tactics_for_battle(
        self,
        general: General,
        battle_type: str,  # "field", "siege", "naval", "ambush"
        terrain: str,
        current_troops_ratio: float,  # 当前兵力/总兵力
        is_first_strike: bool = False,
    ) -> dict:
        """
        战斗中触发武将战术
        
        返回: {bonuses: {...}, narratives: [...]}
        """
        bonuses = {
            "attack_mult": 1.0,
            "defense_mult": 1.0,
            "speed_mult": 1.0,
            "siege_mult": 1.0,
            "morale_effect": 0,
        }
        narratives = []

        for tactic in general.tactics:
            t = tactic.value

            if t == "shock_cavalry" and battle_type == "field":
                bonuses["attack_mult"] += 0.20
                narratives.append(f"{general.name}亲率铁骑冲锋陷阵！")

            elif t == "ambush_master" and battle_type == "ambush":
                bonuses["attack_mult"] += 0.30
                narratives.append(f"{general.name}设伏成功，敌军陷入混乱！")

            elif t == "siege_expert" and battle_type == "siege":
                bonuses["siege_mult"] += 0.30
                narratives.append(f"{general.name}精通攻城之术，城墙摇摇欲坠！")

            elif t == "flank_commander" and battle_type == "field":
                bonuses["attack_mult"] += 0.25
                narratives.append(f"{general.name}指挥侧翼包抄，敌军首尾难顾！")

            elif t == "naval_raider" and (battle_type == "naval" or terrain in ("water", "coastal", "port")):
                bonuses["attack_mult"] += 0.35
                narratives.append(f"{general.name}水战如龙，江面翻腾！")

            elif t == "fortress_defender":
                bonuses["defense_mult"] += 0.30
                narratives.append(f"{general.name}固守城池，敌军寸步难进！")

            elif t == "mountain_guard" and terrain == "mountain":
                bonuses["defense_mult"] += 0.40
                narratives.append(f"{general.name}借山地天险，布下铜墙铁壁！")

            elif t == "river_defender" and terrain in ("water", "coastal", "wetland"):
                bonuses["defense_mult"] += 0.35
                narratives.append(f"{general.name}依托水寨，防守滴水不漏！")

            elif t == "last_stand" and current_troops_ratio < 0.3:
                bonuses["attack_mult"] += 0.50
                bonuses["defense_mult"] += 0.30
                narratives.append(f"{general.name}高呼'背水一战'，全军士气大振！")

            elif t == "logistics_master":
                bonuses["speed_mult"] += 0.15
                # 补给范围加成由 create_legion 处理

            elif t == "forced_march":
                bonuses["speed_mult"] += 0.30
                bonuses["attack_mult"] -= 0.05
                bonuses["supply_consumption_mult"] = 1.20  # 强行军损耗+20%
                narratives.append(f"{general.name}下令强行军，速度大增！")

            elif t == "field_recruiter":
                # 战斗胜利后可征用敌军人口 — 标记战后征兵加成
                bonuses["field_recruiter_active"] = 1
                bonuses["attack_mult"] += 0.05
                narratives.append(f"{general.name}就地征募降卒，以战养战！")

            elif t == "fire_attack" and battle_type in ("siege", "field"):
                bonuses["attack_mult"] += 0.30
                narratives.append(f"{general.name}令人纵火，火势燎原！")

            elif t == "night_raid" and is_first_strike:
                bonuses["attack_mult"] += 0.40
                narratives.append(f"{general.name}趁夜突袭，敌军措手不及！")

            elif t == "psychological_war":
                bonuses["morale_effect"] -= 15
                narratives.append(f"{general.name}攻心为上，敌军士气动摇！")

            elif t == "loyal_commander":
                # 忠勇无双：部队不会溃散
                bonuses["defense_mult"] += 0.10
                if current_troops_ratio < 0.3:
                    narratives.append(f"{general.name}誓死不退，将士用命！")

            elif t == "river_crossing" and terrain in ("water", "coastal"):
                bonuses["speed_mult"] += 0.50
                narratives.append(f"{general.name}精通渡河之术，迅速过水！")

        return {"bonuses": bonuses, "narratives": narratives}
