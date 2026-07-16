"""
3.2 外交权谋深化引擎
- 远交近攻策略计算
- 离间计 (离间同盟、贿赂官员、散布谣言、伪造书信)
- 招安 (许以官爵、重金招揽、以兵威迫、联姻笼络)
- 合纵连横分析
"""
from __future__ import annotations
import logging
import random
import uuid
from typing import Optional

logger = logging.getLogger("yuanmo.diplomacy")
from server.models.world_state import (
    WorldState, FactionState, DiplomaticStance, RelationState, TileState,
)
from server.models.generals import (
    DiscordType, CooptType, FactionStrategy, General,
)


class DeepDiplomacyEngine:
    """外交权谋深化引擎"""

    def __init__(self, world: WorldState):
        self.world = world
        # v3.3 离间计冷却追踪: {(schemer_fid, target_a, target_b): last_used_round}
        self._discord_cooldowns: dict[tuple[str, str, str], int] = {}
        # v3.3 警惕buff追踪: {target_faction_id: remaining_rounds}
        self._vigilance_buffs: dict[str, int] = {}
        # 离间计冷却回合数
        self.DISCORD_COOLDOWN_ROUNDS = 6
        # 警惕buff持续回合数
        self.VIGILANCE_DURATION = 4
        # 警惕buff成功率惩罚
        self.VIGILANCE_PENALTY = 0.15

    # ================================================================
    # 远交近攻策略分析
    # ================================================================

    def analyze_strategic_position(self, faction_id: str) -> dict:
        """
        分析势力的战略位置，推荐最优外交策略
        
        返回:
        {
            strategy: 推荐策略,
            far_potential_allies: 远交候选,
            near_threats: 近攻目标,
            border_analysis: 边界分析,
            power_balance: 实力对比,
        }
        """
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"error": "势力不存在"}

        my_tiles = self.world.get_faction_tiles(faction_id)
        my_power = self._calc_faction_power(faction)

        # 分析每个势力的距离和关系
        faction_relations = []
        for fid, other in self.world.factions.items():
            if fid == faction_id or not other.is_alive:
                continue

            distance = self._calc_faction_distance(faction_id, fid)
            relation = self.world.get_relation(faction_id, fid)
            other_power = self._calc_faction_power(other)
            stance = relation.stance.value if relation else "neutral"
            attitude = relation.attitude if relation else 0

            faction_relations.append({
                "faction_id": fid,
                "name": other.name,
                "distance": distance,
                "stance": stance,
                "attitude": attitude,
                "power": other_power,
                "power_ratio": round(other_power / my_power, 2) if my_power > 0 else 1.0,
                "is_bordering": self._are_factions_bordering(faction_id, fid),
            })

        # 分类：近（距离<3）vs 远
        near_threats = [f for f in faction_relations if f["is_bordering"]]
        far_potentials = [f for f in faction_relations if not f["is_bordering"]]

        # 推荐策略
        if len(near_threats) >= 3:
            strategy = FactionStrategy.FAR_FRIEND_NEAR_ATTACK
            reasoning = "四面临敌，应远交近攻，逐次破之"
        elif len(near_threats) == 2:
            # 检查能否拉一个打一个
            stronger = [t for t in near_threats if t["power_ratio"] > 1.2]
            if stronger:
                strategy = FactionStrategy.NEAR_FRIEND_FAR_ATTACK
                reasoning = f"强敌{stronger[0]['name']}在侧，应连弱制强"
            else:
                strategy = FactionStrategy.EXPANSIONIST
                reasoning = "周边皆弱于我方，可逐一蚕食"
        elif len(near_threats) == 1:
            strategy = FactionStrategy.EXPANSIONIST
            reasoning = "仅一邻敌，可集中力量进攻"
        else:
            strategy = FactionStrategy.ISOLATIONIST
            reasoning = "暂无邻敌，宜休养生息"

        return {
            "strategy": strategy.value,
            "strategy_reasoning": reasoning,
            "far_potential_allies": far_potentials,
            "near_threats": near_threats,
            "all_relations": faction_relations,
            "my_power": my_power,
        }

    def _calc_faction_power(self, faction: FactionState) -> float:
        """计算势力综合实力"""
        return (
            faction.total_troops * 1.0 +
            faction.treasury * 0.002 +
            faction.grain * 0.001 +
            faction.tile_count * 50 +
            faction.reputation * 10
        )

    def _calc_faction_distance(self, fid_a: str, fid_b: str) -> float:
        """计算两势力最短距离（通过首都）"""
        fa = self.world.get_faction(fid_a)
        fb = self.world.get_faction(fid_b)
        if not fa or not fb:
            return 99.0

        ta = self.world.get_tile(fa.capital_tile)
        tb = self.world.get_tile(fb.capital_tile)
        if not ta or not tb:
            # 遍历所有地块找最近距离
            tiles_a = self.world.get_faction_tiles(fid_a)
            tiles_b = self.world.get_faction_tiles(fid_b)
            if not tiles_a or not tiles_b:
                return 99.0
            return self._min_tile_distance(tiles_a, tiles_b)

        return self._tile_distance(ta, tb)

    @staticmethod
    def _tile_distance(ta: TileState, tb: TileState) -> float:
        """地块间欧氏距离（基于质心经纬度）"""
        import math
        dx = (ta.centroid_lon - tb.centroid_lon) * 111.0 * math.cos(math.radians((ta.centroid_lat + tb.centroid_lat) / 2))
        dy = (ta.centroid_lat - tb.centroid_lat) * 111.0
        return math.sqrt(dx * dx + dy * dy)

    def _min_tile_distance(self, tiles_a: list[TileState], tiles_b: list[TileState]) -> float:
        """两势力地块集中最近距离"""
        min_dist = float('inf')
        for ta in tiles_a:
            for tb in tiles_b:
                dist = self._tile_distance(ta, tb)
                if dist < min_dist:
                    min_dist = dist
        return min_dist

    def _are_factions_bordering(self, fid_a: str, fid_b: str) -> bool:
        """检查两势力是否接壤"""
        tiles_a = {t.tile_id for t in self.world.get_faction_tiles(fid_a)}
        tiles_b = {t.tile_id for t in self.world.get_faction_tiles(fid_b)}
        if not tiles_a or not tiles_b:
            return False

        try:
            from server.map.admin_hierarchy import get_territory_graph
            graph = get_territory_graph()
            for tid in tiles_a:
                neighbors = set(graph.get(tid, []))
                if neighbors & tiles_b:
                    return True
        except Exception as e:
            logger.debug(f"[Diplomacy] 邻接图查询失败，回退距离判定: {e}")

        # 回退：基于距离判定（距离<100km视为接壤）
        ta_list = [t for t in self.world.tiles.values() if t.tile_id in tiles_a]
        tb_list = [t for t in self.world.tiles.values() if t.tile_id in tiles_b]
        min_dist = self._min_tile_distance(ta_list, tb_list)
        return min_dist < 100.0

    # ================================================================
    # 离间计
    # ================================================================

    def sow_discord(
        self,
        schemer_fid: str,
        target_alliance: tuple[str, str],  # (faction_a, faction_b) 要离间的同盟双方
        discord_type: DiscordType,
    ) -> dict:
        """
        发动离间计
        
        v3.3 平衡改动：
        - 冷却时间：6回合内对同一目标只能使用1次
        - 失败后目标获得"警惕"buff（后续成功率-15%，持续4回合）
        
        返回: {success: bool, message: str, relation_change: int, ...}
        """
        result = {
            "success": False,
            "message": "",
            "relation_change": 0,
            "cost": 0,
            "narrative": "",
        }

        fa, fb = target_alliance
        relation = self.world.get_relation(fa, fb)
        if not relation:
            result["message"] = "目标两方无外交关系"
            return result

        # 只有同盟才能离间
        if relation.stance != DiplomaticStance.ALLIANCE:
            result["message"] = f"目标两方当前并非同盟（现状：{relation.stance.value}）"
            return result

        schemer = self.world.get_faction(schemer_fid)
        if not schemer:
            result["message"] = "施计方势力不存在"
            return result

        # v3.3 冷却检查：6回合内对同一目标组合不能重复使用
        cooldown_key = (schemer_fid, fa, fb)
        last_used = self._discord_cooldowns.get(cooldown_key, -999)
        current_round = getattr(self.world, 'current_round', 0)
        rounds_since = current_round - last_used
        if rounds_since < self.DISCORD_COOLDOWN_ROUNDS:
            remaining = self.DISCORD_COOLDOWN_ROUNDS - rounds_since
            result["message"] = f"离间计冷却中（还需等待{remaining}回合）"
            result["narrative"] = f"上次离间{self._faction_name(fa)}与{self._faction_name(fb)}距今仅{rounds_since}回合，不宜再次行动。"
            return result

        # 成本
        schemer_treasury = schemer.treasury
        costs = {
            DiscordType.SOW_DISCORD: 800,
            DiscordType.BRIBE_OFFICIAL: 1200,
            DiscordType.SPREAD_RUMOR: 500,
            DiscordType.FAKE_LETTER: 1000,
        }
        cost = costs.get(discord_type, 800)

        if schemer_treasury < cost:
            result["message"] = f"国库不足（需要{cost}两，现有{schemer_treasury}两）"
            result["cost"] = cost
            return result

        schemer.treasury -= cost
        result["cost"] = cost

        # v3.3 记录冷却（无论成功失败，都进入冷却）
        self._discord_cooldowns[cooldown_key] = current_round

        # 成功概率：基于关系态度和离间类型
        base_chance = {
            DiscordType.SOW_DISCORD: 0.45,
            DiscordType.BRIBE_OFFICIAL: 0.60,
            DiscordType.SPREAD_RUMOR: 0.35,
            DiscordType.FAKE_LETTER: 0.55,
        }[discord_type]

        # v3.3 警惕buff惩罚：目标有警惕buff时成功率-15%
        vigilance_penalty = 0.0
        for target_fid in (fa, fb):
            vig_rounds = self._vigilance_buffs.get(target_fid, 0)
            if vig_rounds > 0:
                vigilance_penalty = self.VIGILANCE_PENALTY
                result["narrative"] += f"{self._faction_name(target_fid)}已有所警惕，离间成功率降低。"
                break

        # 态度越低越容易离间（负数态度反向放大成功率）
        attitude_factor = max(0.2, (100 - relation.attitude) / 100.0)
        chance = base_chance * attitude_factor - vigilance_penalty
        chance = max(0.05, min(0.95, chance))  # 限制在5%~95%

        if random.random() < chance:
            # 离间成功 — 清除警惕buff
            for target_fid in (fa, fb):
                self._vigilance_buffs.pop(target_fid, None)

            attitude_change = random.randint(30, 60)
            relation.attitude = max(-50, relation.attitude - attitude_change)

            # 态度极低时破裂同盟
            if relation.attitude < -20:
                relation.stance = DiplomaticStance.NEUTRAL
                relation.trade_active = False
                # 清理附庸关系（如存在）
                self.world.vassal_relations.pop(fa, None)
                self.world.vassal_relations.pop(fb, None)
                result["alliance_broken"] = True
                result["message"] = f"离间成功！{self._faction_name(fa)}与{self._faction_name(fb)}的同盟已破裂！"
                result["narrative"] = self._generate_discord_narrative(schemer, fa, fb, discord_type, broken=True)
            else:
                result["message"] = f"离间成功！{self._faction_name(fa)}与{self._faction_name(fb)}的关系大幅恶化（态度{relation.attitude}）"
                result["narrative"] = self._generate_discord_narrative(schemer, fa, fb, discord_type, broken=False)

            result["success"] = True
            result["relation_change"] = -attitude_change
        else:
            # v3.3 离间失败：目标获得"警惕"buff
            for target_fid in (fa, fb):
                self._vigilance_buffs[target_fid] = self.VIGILANCE_DURATION

            result["message"] = f"离间失败！{self._faction_name(fa)}与{self._faction_name(fb)}未受影响。"
            result["narrative"] = f"离间计被{self._faction_name(fa)}识破，双方获得警惕（4回合内离间成功率-15%）。"

            # 可能被发现
            if random.random() < 0.35:
                discoverer = random.choice([fa, fb])
                disc_rel = self.world.get_relation(schemer_fid, discoverer)
                if disc_rel:
                    disc_rel.attitude = max(-50, disc_rel.attitude - 15)
                    result["narrative"] += f"\n{self._faction_name(discoverer)}发现了{schemer.name}的离间阴谋！"

        # 记录外交日志
        self.world.diplomatic_archive.append({
            "round": current_round,
            "action": "discord",
            "schemer": schemer_fid,
            "target_a": fa,
            "target_b": fb,
            "discord_type": discord_type.value,
            "success": result["success"],
            "relation_change": result["relation_change"],
        })

        return result

    def on_round_end(self):
        """每回合结束时调用，递减警惕buff和清理过期冷却"""
        # 递减警惕buff
        expired = []
        for fid in list(self._vigilance_buffs.keys()):
            self._vigilance_buffs[fid] -= 1
            if self._vigilance_buffs[fid] <= 0:
                expired.append(fid)
        for fid in expired:
            del self._vigilance_buffs[fid]
            logger.debug(f"[Diplomacy] {self._faction_name(fid)} 的警惕buff已过期")

    def _generate_discord_narrative(self, schemer: FactionState, fa: str, fb: str,
                                     dtype: DiscordType, broken: bool) -> str:
        """生成离间叙述"""
        fa_name = self._faction_name(fa)
        fb_name = self._faction_name(fb)

        narratives = {
            DiscordType.SOW_DISCORD: f"{schemer.name}遣使暗中离间{fa_name}与{fb_name}。",
            DiscordType.BRIBE_OFFICIAL: f"{schemer.name}以重金贿赂{fa_name}朝臣，挑拨离间。",
            DiscordType.SPREAD_RUMOR: f"{schemer.name}散布谣言，挑唆{fa_name}对{fb_name}的猜忌。",
            DiscordType.FAKE_LETTER: f"{schemer.name}伪造{fb_name}通敌书信，成功离间{fa_name}。",
        }

        base = narratives.get(dtype, f"{schemer.name}对{fa_name}和{fb_name}使用离间计。")
        if broken:
            base += f"\n{fa_name}与{fb_name}的同盟就此破裂！"
        return base

    def _faction_name(self, fid: str) -> str:
        """获取势力名称"""
        f = self.world.get_faction(fid)
        return f.name if f else fid

    def _calc_predicament_bonus(self, target) -> float:
        """
        v3.4: 计算目标势力的困境程度，影响招安成功率
        
        困境因子基于：
        - 正在被围攻/多面作战
        - 国库空虚
        - 兵力薄弱
        - 地块丢失
        
        Returns:
            困境加成 (0.0 ~ 0.25)
        """
        bonus = 0.0

        # 检查目标是否处于战争中
        target_fid = target.faction_id if hasattr(target, 'faction_id') else target.id
        active_wars = 0
        for key, rel in getattr(self.world, 'relations', {}).items():
            if hasattr(rel, 'stance') and str(rel.stance) in ('war', 'War', 'WAR'):
                if (hasattr(rel, 'faction_a') and rel.faction_a == target_fid) or \
                   (hasattr(rel, 'faction_b') and rel.faction_b == target_fid):
                    active_wars += 1

        if active_wars >= 2:
            bonus += 0.15  # 多线作战，压力巨大
        elif active_wars == 1:
            bonus += 0.08  # 正在交战

        # 国库空虚（先检查更严格的条件，避免 elif 死分支）
        treasury = getattr(target, 'treasury', 1000)
        if treasury < 200:
            bonus += 0.10
        elif treasury < 500:
            bonus += 0.05

        # 兵力薄弱（修复：owner_faction → faction_id，TileState 实际字段名）
        total_troops = sum(
            getattr(t, 'troops', 0) or 0
            for t in getattr(self.world, 'tiles', {}).values()
            if getattr(t, 'faction_id', '') == target_fid
        )
        tile_count = len([t for t in getattr(self.world, 'tiles', {}).values()
                          if getattr(t, 'faction_id', '') == target_fid])
        if tile_count > 0 and total_troops / tile_count < 100:
            bonus += 0.05  # 每地块平均兵力不足

        # 丢失首都（如果首都被占）
        capital = getattr(target, 'capital_tile', None)
        if capital:
            cap_tile = getattr(self.world, 'tiles', {}).get(capital)
            if cap_tile and getattr(cap_tile, 'faction_id', '') != target_fid:
                bonus += 0.10  # 首都被占，极度困境

        return min(0.25, bonus)

    # ================================================================
    # 招安
    # ================================================================

    def attempt_coopt(
        self,
        coopter_fid: str,
        target_fid: str,
        coopt_type: CooptType,
    ) -> dict:
        """
        招安/招降势力（使其成为附庸或同盟）
        
        返回: {success, message, new_stance, cost, ...}
        """
        result = {
            "success": False,
            "message": "",
            "new_stance": "",
            "cost": 0,
            "narrative": "",
        }

        coopter = self.world.get_faction(coopter_fid)
        target = self.world.get_faction(target_fid)
        if not coopter or not target:
            result["message"] = "势力不存在"
            return result

        if not target.is_alive:
            result["message"] = "目标势力已灭亡"
            return result

        relation = self.world.get_relation(coopter_fid, target_fid)

        # 已交战则不能招安
        if relation and relation.stance == DiplomaticStance.WAR:
            result["message"] = f"不能招安已交战的势力"
            return result

        # 成本
        costs = {
            CooptType.OFFER_TITLE: 2000,
            CooptType.OFFER_GOLD: 5000,
            CooptType.THREATEN: 1000,
            CooptType.MARRY_ALLIANCE: 3000,
        }
        cost = costs.get(coopt_type, 2000)

        if coopter.treasury < cost:
            result["message"] = f"国库不足（需要{cost}两）"
            result["cost"] = cost
            return result

        coopter.treasury -= cost
        result["cost"] = cost

        # 成功概率
        attitude = relation.attitude if relation else 0
        power_ratio = self._calc_faction_power(coopter) / max(1, self._calc_faction_power(target))

        base_chance = {
            CooptType.OFFER_TITLE: 0.35,
            CooptType.OFFER_GOLD: 0.50,
            CooptType.THREATEN: 0.45,
            CooptType.MARRY_ALLIANCE: 0.40,
        }[coopt_type]

        # 态度因子：越高越好
        attitude_bonus = max(-0.2, attitude / 200.0)
        # 实力因子：我方越强越好
        power_bonus = min(0.3, (power_ratio - 1.0) * 0.15) if power_ratio > 1 else -0.2

        # v3.4 目标困境因子：处于困境的势力更容易被招安
        predicament_bonus = self._calc_predicament_bonus(target)

        # 对方人格影响
        target_personality = target.personality_tags
        personality_bonus = 0
        if "优柔寡断" in target_personality:
            personality_bonus += 0.15  # 容易招安
        if "投机善变" in target_personality:
            personality_bonus += 0.10
        if "野心勃勃" in target_personality:
            personality_bonus -= 0.10  # 难招安
        if "忠勇无双" in target_personality:
            personality_bonus -= 0.20

        chance = base_chance + attitude_bonus + power_bonus + personality_bonus + predicament_bonus
        chance = max(0.05, min(0.85, chance))

        if random.random() < chance:
            # 招安成功
            coopt_type_map = {
                CooptType.OFFER_TITLE: DiplomaticStance.VASSAL,
                CooptType.OFFER_GOLD: DiplomaticStance.VASSAL,
                CooptType.THREATEN: DiplomaticStance.VASSAL,
                CooptType.MARRY_ALLIANCE: DiplomaticStance.ALLIANCE,
            }
            new_stance = coopt_type_map.get(coopt_type, DiplomaticStance.VASSAL)

            if new_stance == DiplomaticStance.VASSAL:
                # 检查目标是否已附庸其他势力
                existing_suzerain = self.world.vassal_relations.get(target_fid)
                if existing_suzerain and existing_suzerain != coopter_fid:
                    suz_faction = self.world.factions.get(existing_suzerain)
                    existing_name = suz_faction.name if suz_faction else existing_suzerain
                    result["message"] = f"招安失败！{target.name}已是{existing_name}的附庸，无法接受你的招安。"
                    return result
                self.world.vassal_relations[target_fid] = coopter_fid

            if relation:
                relation.stance = new_stance
                relation.attitude = min(100, relation.attitude + 30)
            else:
                relation = RelationState(
                    faction_a=coopter_fid,
                    faction_b=target_fid,
                    stance=new_stance,
                    attitude=40,
                )
                key = self.world.relation_key(coopter_fid, target_fid)
                self.world.relations[key] = relation

            result["success"] = True
            result["new_stance"] = new_stance.value
            result["message"] = f"招安成功！{target.name}已成为{coopter.name}的{'附庸' if new_stance == DiplomaticStance.VASSAL else '同盟'}！"
            result["narrative"] = self._generate_coopt_narrative(coopter, target, coopt_type, True)
        else:
            result["message"] = f"招安失败！{target.name}拒绝了{coopter.name}的{'招降' if coopt_type != CooptType.MARRY_ALLIANCE else '联姻'}提议。"
            result["narrative"] = self._generate_coopt_narrative(coopter, target, coopt_type, False)

            # 可能降低好感
            if relation:
                relation.attitude = max(-30, relation.attitude - 5)

        # 记录外交日志
        self.world.diplomatic_archive.append({
            "round": self.world.current_round,
            "action": "coopt",
            "schemer": coopter_fid,
            "target": target_fid,
            "coopt_type": coopt_type.value,
            "success": result["success"],
        })

        return result

    def _generate_coopt_narrative(self, coopter: FactionState, target: FactionState,
                                    ctype: CooptType, success: bool) -> str:
        """生成招安叙述"""
        narratives = {
            CooptType.OFFER_TITLE: f"{coopter.name}派出使者，许以{target.name}高官厚爵。",
            CooptType.OFFER_GOLD: f"{coopter.name}遣使携重金以招揽{target.name}。",
            CooptType.THREATEN: f"{coopter.name}陈兵边境，以武力胁迫{target.name}归附。",
            CooptType.MARRY_ALLIANCE: f"{coopter.name}提议联姻，以结秦晋之好。",
        }

        base = narratives.get(ctype, f"{coopter.name}试图招安{target.name}。")
        if success:
            base += f"\n{target.name}审时度势，接受了{coopter.name}的招揽。"
        else:
            base += f"\n{target.name}不为所动，拒绝了招揽。"
        return base

    # ================================================================
    # 合纵连横自动分析
    # ================================================================

    def recommend_diplomatic_actions(self, faction_id: str) -> list[dict]:
        """
        为AI势力推荐外交行动（每回合自动调用）
        
        返回: [{action, target, priority, reason], ...]
        """
        strat = self.analyze_strategic_position(faction_id)
        recommendations = []

        # 如果推荐远交近攻
        if strat["strategy"] == FactionStrategy.FAR_FRIEND_NEAR_ATTACK.value:
            # 远交：与远方势力结盟
            for far in strat.get("far_potential_allies", []):
                if far["stance"] == "neutral" and far["attitude"] > -20:
                    recommendations.append({
                        "action": "propose_alliance",
                        "target": far["faction_id"],
                        "target_name": far["name"],
                        "priority": "high",
                        "reason": f"远交近攻：拉拢远方{far['name']}以牵制近敌",
                    })

            # 近攻：对周边势力宣战
            for near in strat.get("near_threats", []):
                if near["stance"] == "neutral":
                    recommendations.append({
                        "action": "declare_war",
                        "target": near["faction_id"],
                        "target_name": near["name"],
                        "priority": "medium",
                        "reason": f"近攻：征讨邻敌{near['name']}",
                    })

        # 推荐离间
        faction = self.world.get_faction(faction_id)
        for near in strat.get("near_threats", []):
            # 查找该近敌与其他势力的同盟关系
            for fid, other in self.world.factions.items():
                if fid in (faction_id, near["faction_id"]):
                    continue
                rel = self.world.get_relation(near["faction_id"], fid)
                if rel and rel.stance == DiplomaticStance.ALLIANCE:
                    recommendations.append({
                        "action": "sow_discord",
                        "target_a": near["faction_id"],
                        "target_b": fid,
                        "target_name": f"{near['name']}与{other.name}",
                        "priority": "medium",
                        "reason": f"离间{near['name']}与{other.name}的同盟",
                    })

        return recommendations
