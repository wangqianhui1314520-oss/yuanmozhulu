"""
势力AI增强引擎 - 群雄敌对AI智能体（3.2 全链路AI智能体）

职责：
1. 人格驱动的自主决策：激进/稳健/苟分/投机/外交
2. 四维AI决策管线：内政 → 军事 → 外交 → 谍报
3. 独立智能体行为：自主评估局势、制定策略、执行操作
4. 与A2群雄殿LLM智能体协同（LLM提供战略方向，引擎提供数值执行）
5. 降级方案：无LLM时纯数值驱动
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from collections import defaultdict

from server.models.ai_protocol import AIPersonality, AICommandSet, AICommand, CommandType
from server.models.world_state import WorldState, FactionState

logger = logging.getLogger("yuanmo.ai.faction")


class FactionAIEngine:
    """
    势力AI增强引擎
    
    每个势力独立运行，根据人格（aggressive/steady/conservative/opportunist/diplomatic）
    做出差异化的决策。
    
    决策管线（每回合按序执行）：
    1. 内政决策：税收/开发/建造/赈灾
    2. 军事决策：征兵/训练/加固/行军/进攻
    3. 外交决策：结盟/宣战/求和/贸易
    4. 谍报决策：渗透/破坏/情报
    """

    # 人格权重矩阵：{人格: {决策维度: 基础权重}}
    PERSONALITY_WEIGHTS = {
        AIPersonality.AGGRESSIVE.value: {
            "military_priority": 0.7, "economy_priority": 0.2,
            "diplomacy_priority": 0.05, "consolidation_priority": 0.05,
            "attack_threshold": 0.6,    # 敌我兵力比低于此值就进攻
            "risk_tolerance": 0.8,      # 高风险承受度
            "ally_tendency": 0.1,       # 结盟倾向（低）
        },
        AIPersonality.STEADY.value: {
            "military_priority": 0.35, "economy_priority": 0.35,
            "diplomacy_priority": 0.15, "consolidation_priority": 0.15,
            "attack_threshold": 0.4,
            "risk_tolerance": 0.5,
            "ally_tendency": 0.5,
        },
        AIPersonality.CONSERVATIVE.value: {
            "military_priority": 0.1, "economy_priority": 0.5,
            "diplomacy_priority": 0.1, "consolidation_priority": 0.3,
            "attack_threshold": 0.25,
            "risk_tolerance": 0.2,
            "ally_tendency": 0.7,
        },
        AIPersonality.OPPORTUNIST.value: {
            "military_priority": 0.4, "economy_priority": 0.2,
            "diplomacy_priority": 0.2, "consolidation_priority": 0.2,
            "attack_threshold": 0.5,
            "risk_tolerance": 0.7,
            "ally_tendency": 0.3,
        },
        AIPersonality.DIPLOMATIC.value: {
            "military_priority": 0.15, "economy_priority": 0.3,
            "diplomacy_priority": 0.45, "consolidation_priority": 0.1,
            "attack_threshold": 0.3,
            "risk_tolerance": 0.4,
            "ally_tendency": 0.9,
        },
    }

    def __init__(self, world: WorldState, faction_configs: dict):
        self.world = world
        self.faction_configs = faction_configs

    # ============================================================
    # 主决策管线
    # ============================================================

    def generate_decisions(self, faction_id: str, personality: str = "steady") -> AICommandSet:
        """
        为单个势力生成一轮决策
        
        Args:
            faction_id: 势力ID
            personality: 人格类型
        Returns:
            AICommandSet with executable commands
        """
        faction = self.world.factions.get(faction_id)
        if not faction or not faction.is_alive:
            return AICommandSet(agent_type="faction_ai", faction_id=faction_id)

        weights = self.PERSONALITY_WEIGHTS.get(personality, self.PERSONALITY_WEIGHTS["steady"])
        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        if not tiles:
            return AICommandSet(agent_type="faction_ai", faction_id=faction_id, decision_summary="无领地")

        commands = []

        # 1. 内政决策
        commands.extend(self._civil_decisions(faction_id, faction, tiles, weights))

        # 2. 军事决策
        commands.extend(self._military_decisions(faction_id, faction, tiles, weights))

        # 3. 外交决策
        commands.extend(self._diplomacy_decisions(faction_id, faction, tiles, weights))

        # 4. 谍报决策
        commands.extend(self._espionage_decisions(faction_id, faction, tiles, weights))

        # 按优先级排序
        commands.sort(key=lambda c: c.priority, reverse=True)

        summary = self._generate_summary(faction_id, faction, personality, commands)

        return AICommandSet(
            agent_type="faction_ai_enhanced",
            faction_id=faction_id,
            turn=getattr(self.world, 'current_round', 0),
            decision_summary=summary,
            commands=commands,
            risk_assessment=self._assess_risk(faction, commands),
        )

    # ============================================================
    # 内政决策
    # ============================================================

    def _civil_decisions(self, fid: str, faction, tiles: list, weights: dict) -> list[AICommand]:
        """内政决策管线"""
        commands = []
        economy_priority = weights.get("economy_priority", 0.3)

        # 税收决策
        if faction.treasury < 2000:
            # 缺钱时激进型会加税，保守型会发展经济
            if weights.get("risk_tolerance", 0.5) > 0.5:
                commands.append(AICommand(
                    command_id=f"{fid}_tax",
                    command_type=CommandType.TAX,
                    faction_id=fid,
                    params={"mode": "heavy"},
                    reason="国库空虚，加征税赋",
                    priority=7,
                ))
            else:
                commands.append(AICommand(
                    command_id=f"{fid}_tax",
                    command_type=CommandType.TAX,
                    faction_id=fid,
                    params={"mode": "normal"},
                    reason="正常征税维持国用",
                    priority=5,
                ))

        # 开发决策
        if faction.treasury > 1000 and random.random() < economy_priority:
            undeveloped = [t for t in tiles if getattr(t, 'development_level', 20) < 60]
            if undeveloped:
                target = random.choice(undeveloped)
                commands.append(AICommand(
                    command_id=f"{fid}_develop_{target.tile_id}",
                    command_type=CommandType.DEVELOP,
                    faction_id=fid,
                    params={"tile_id": target.tile_id, "type": "farmland"},
                    reason="开垦荒地增加产出",
                    priority=6,
                    estimated_cost={"gold": 500},
                ))

        # 建造决策
        if faction.treasury > 1500 and random.random() < economy_priority:
            needs = self._assess_building_needs(faction, tiles)
            if needs:
                btype, target_tile = needs
                commands.append(AICommand(
                    command_id=f"{fid}_build_{btype}",
                    command_type=CommandType.BUILD,
                    faction_id=fid,
                    params={"tile_id": target_tile.tile_id if hasattr(target_tile, 'tile_id') else target_tile, "building_type": btype},
                    reason=f"兴建{btype}以强国力",
                    priority=5,
                    estimated_cost={"gold": 800},
                ))

        # 赈灾决策
        active_disasters = [t for t in tiles if getattr(t, 'active_disaster', '')]
        if active_disasters and faction.grain > 500:
            for t in active_disasters[:2]:
                commands.append(AICommand(
                    command_id=f"{fid}_relief_{t.tile_id}",
                    command_type=CommandType.RELIEF,
                    faction_id=fid,
                    params={"tile_id": t.tile_id},
                    reason="赈济灾民以安民心",
                    priority=9,
                ))

        return commands

    # ============================================================
    # 军事决策
    # ============================================================

    def _military_decisions(self, fid: str, faction, tiles: list, weights: dict) -> list[AICommand]:
        """军事决策管线"""
        commands = []
        military_priority = weights.get("military_priority", 0.4)
        attack_threshold = weights.get("attack_threshold", 0.5)
        risk_tolerance = weights.get("risk_tolerance", 0.5)

        # 征兵决策
        border_tiles = self._get_border_tiles(fid, tiles)
        if faction.treasury > 1500 and faction.arms > 100 and random.random() < military_priority:
            recruit_count = min(600, faction.treasury // 2, faction.arms * 3)
            if recruit_count > 100:
                target_tile = border_tiles[0] if border_tiles else tiles[0]
                commands.append(AICommand(
                    command_id=f"{fid}_recruit",
                    command_type=CommandType.RECRUIT,
                    faction_id=fid,
                    params={"tile_id": target_tile.tile_id, "count": recruit_count},
                    reason="扩充军备以防不测",
                    priority=8,
                    estimated_cost={"gold": recruit_count * 3, "arms": recruit_count // 3},
                ))

        # 训练决策
        if faction.treasury > 800 and random.random() < military_priority * 0.5:
            commands.append(AICommand(
                command_id=f"{fid}_train",
                command_type=CommandType.TRAIN_TROOPS,
                faction_id=fid,
                params={"auto": True},
                reason="操练士卒提振士气",
                priority=6,
                estimated_cost={"gold": 500, "grain": 250},
            ))

        # 加固城防
        if random.random() < weights.get("consolidation_priority", 0.2):
            low_fort = [t for t in tiles if getattr(t, 'fortification', 0) < 40]
            if low_fort and faction.treasury > 500:
                target = random.choice(low_fort)
                commands.append(AICommand(
                    command_id=f"{fid}_fortify_{target.tile_id}",
                    command_type=CommandType.FORTIFY,
                    faction_id=fid,
                    params={"tile_id": target.tile_id},
                    reason="加固城防巩固边防",
                    priority=5,
                    estimated_cost={"gold": 300},
                ))

        # 进攻决策（最重要的人格差异）
        if random.random() < military_priority * 0.6:
            attack_commands = self._plan_attack(fid, faction, tiles, weights, attack_threshold, risk_tolerance)
            commands.extend(attack_commands)

        return commands

    def _plan_attack(self, fid: str, faction, tiles: list, weights: dict, threshold: float, risk: float) -> list[AICommand]:
        """生成进攻指令"""
        commands = []

        # 先处理交战中的势力
        at_war = self._get_at_war(fid)
        attack_targets = []

        for enemy_id in at_war:
            enemy = self.world.factions.get(enemy_id)
            if not enemy or not enemy.is_alive:
                continue
            enemy_tiles = self.world.get_faction_tiles(enemy_id) if hasattr(self.world, 'get_faction_tiles') else []
            for atk_tile in tiles:
                if getattr(atk_tile, 'troops', 0) < 200:
                    continue
                for def_tile in enemy_tiles:
                    if self._are_adjacent(atk_tile, def_tile):
                        power_ratio = getattr(atk_tile, 'troops', 0) / max(1, getattr(def_tile, 'troops', 0))
                        if power_ratio > threshold:
                            attack_targets.append((atk_tile, def_tile, power_ratio, 2.0))  # 加成

        # 再找最弱邻国
        if not attack_targets and risk > 0.3:
            for atk_tile in tiles:
                if getattr(atk_tile, 'troops', 0) < 300:
                    continue
                neighbors = getattr(atk_tile, 'neighbors', [])
                for nid in neighbors:
                    n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
                    if not n_tile:
                        continue
                    n_owner = getattr(n_tile, 'faction_id', '')
                    if n_owner and n_owner != fid and n_owner not in at_war:
                        n_faction = self.world.factions.get(n_owner)
                        if n_faction and n_faction.is_alive:
                            power_ratio = getattr(atk_tile, 'troops', 0) / max(1, getattr(n_tile, 'troops', 0))
                            if power_ratio > threshold:
                                # Bug #48修复: 排除alliance/vassal/truce
                                stance = self._get_stance(fid, n_owner)
                                if stance not in ("alliance", "vassal", "truce"):
                                    attack_targets.append((atk_tile, n_tile, power_ratio, 1.0))

        if attack_targets:
            attack_targets.sort(key=lambda x: x[2], reverse=True)
            atk_tile, def_tile, ratio, _ = attack_targets[0]
            troops_to_send = min(
                getattr(atk_tile, 'troops', 0) - 100,
                max(100, int(getattr(atk_tile, 'troops', 0) * risk))
            )
            if troops_to_send > 100:
                commands.append(AICommand(
                    command_id=f"{fid}_attack_{def_tile.tile_id}",
                    command_type=CommandType.MARCH,
                    faction_id=fid,
                    params={
                        "from_tile": atk_tile.tile_id,
                        "to_tile": def_tile.tile_id,
                        "troops": troops_to_send,
                    },
                    reason=f"出兵攻打{getattr(def_tile, 'tile_name', def_tile.tile_id)}（兵力比{ratio:.1%}）",
                    priority=9,
                ))

        return commands

    # ============================================================
    # 外交决策
    # ============================================================

    def _diplomacy_decisions(self, fid: str, faction, tiles: list, weights: dict) -> list[AICommand]:
        """外交决策管线"""
        commands = []
        diplo_priority = weights.get("diplomacy_priority", 0.2)
        ally_tendency = weights.get("ally_tendency", 0.3)

        # 评估局势：是否需要结盟
        neighbors = self._get_neighbor_factions(fid, tiles)
        at_war = self._get_at_war(fid)

        # 被多线作战时，求和或结盟
        if len(at_war) >= 2:
            if random.random() < ally_tendency:
                # 找最强邻国结盟
                # Bug #51修复: 寻找盟友时排除vassal和truce
                potential_allies = [
                    n for n in neighbors
                    if n not in at_war and self._get_stance(fid, n) not in ("war", "alliance", "vassal", "truce")
                ]
                if potential_allies:
                    # Bug #49修复: 使用None代替FactionState()空构造
                    best_ally = max(potential_allies, key=lambda n: (self.world.factions.get(n) or FactionState(faction_id=n)).troops)
                    commands.append(AICommand(
                        command_id=f"{fid}_ally_{best_ally}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=fid,
                        params={"action": "alliance", "target_faction": best_ally},
                        reason=f"多线作战，联{best_ally}以自保",
                        priority=10,
                    ))

        # 弱小时寻找强大庇护
        if faction.troops < 3000 and faction.tile_count < 5:
            strong_neighbors = [n for n in neighbors if (self.world.factions.get(n) or FactionState(faction_id=n)).troops > faction.troops * 1.5]
            if strong_neighbors and random.random() < ally_tendency:
                lord = min(strong_neighbors, key=lambda n: abs((self.world.factions.get(n) or FactionState(faction_id=n)).troops - faction.troops * 2))
                commands.append(AICommand(
                    command_id=f"{fid}_vassal_{lord}",
                    command_type=CommandType.DIPLOMACY,
                    faction_id=fid,
                    params={"action": "vassal_offer", "target_faction": lord},
                    reason="势单力薄，寻求庇护",
                    priority=9,
                ))

        # 强大时威迫弱小
        if faction.troops > 8000 and faction.tile_count > 8:
            weak_neighbors = [n for n in neighbors if (self.world.factions.get(n) or FactionState(faction_id=n)).troops < faction.troops * 0.3]
            if weak_neighbors and random.random() < diplo_priority:
                target = random.choice(weak_neighbors)
                commands.append(AICommand(
                    command_id=f"{fid}_threaten_{target}",
                    command_type=CommandType.DIPLOMACY,
                    faction_id=fid,
                    params={"action": "tribute", "target_faction": target},
                    reason=f"兵强马壮，令{target}纳贡",
                    priority=7,
                ))

        return commands

    # ============================================================
    # 谍报决策
    # ============================================================

    def _espionage_decisions(self, fid: str, faction, tiles: list, weights: dict) -> list[AICommand]:
        """谍报决策管线"""
        commands = []

        # 激进型更倾向用间谍
        if random.random() > weights.get("risk_tolerance", 0.5) * 0.3:
            return commands

        # 对宿敌派遣细作
        at_war = self._get_at_war(fid)
        if at_war and faction.treasury > 800:
            target = at_war[0]
            commands.append(AICommand(
                command_id=f"{fid}_spy_{target}",
                command_type=CommandType.SPY,
                faction_id=fid,
                params={"action": "deploy", "target_faction": target},
                reason=f"向{target}派遣细作搜集情报",
                priority=6,
                estimated_cost={"gold": 500},
            ))

        # 对邻国渗透
        neighbors = self._get_neighbor_factions(fid, tiles)
        non_allied = [n for n in neighbors if self._get_stance(fid, n) not in ("alliance", "vassal")]
        if non_allied and len(self.world.__dict__.get("spy_networks", {})) < 3:
            target = random.choice(non_allied)
            commands.append(AICommand(
                command_id=f"{fid}_infiltrate_{target}",
                command_type=CommandType.SPY,
                faction_id=fid,
                params={"action": "deploy", "target_faction": target},
                reason=f"渗透{target}以备不时之需",
                priority=4,
                estimated_cost={"gold": 300},
            ))

        return commands

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_border_tiles(self, fid: str, tiles: list) -> list:
        """获取边境地块"""
        border = []
        for t in tiles:
            for nid in getattr(t, 'neighbors', []):
                n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
                if n_tile and getattr(n_tile, 'faction_id', '') != fid:
                    border.append(t)
                    break
        return border or tiles

    def _are_adjacent(self, tile_a, tile_b) -> bool:
        """判断两地块是否邻接"""
        return tile_b.tile_id in getattr(tile_a, 'neighbors', [])

    def _get_at_war(self, fid: str) -> list[str]:
        """获取所有交战中势力"""
        at_war = []
        for key, rel in getattr(self.world, 'relations', {}).items():
            stance = rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance)
            if stance == "war":
                if rel.faction_a == fid:
                    at_war.append(rel.faction_b)
                elif rel.faction_b == fid:
                    at_war.append(rel.faction_a)
        return at_war

    def _get_neighbor_factions(self, fid: str, tiles: list) -> list[str]:
        """获取所有邻接势力"""
        neighbors = set()
        for t in tiles:
            for nid in getattr(t, 'neighbors', []):
                n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
                if n_tile:
                    n_owner = getattr(n_tile, 'faction_id', '')
                    if n_owner and n_owner != fid:
                        neighbors.add(n_owner)
        return list(neighbors)

    def _get_stance(self, fid_a: str, fid_b: str) -> str:
        """获取两势力关系"""
        for key, rel in getattr(self.world, 'relations', {}).items():
            if (rel.faction_a == fid_a and rel.faction_b == fid_b) or \
               (rel.faction_a == fid_b and rel.faction_b == fid_a):
                return rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance)
        return "neutral"

    def _assess_building_needs(self, faction, tiles: list) -> Optional[tuple]:
        """评估建造需求"""
        has_granary = any("granary" in list(getattr(t, 'buildings', [])) for t in tiles)
        has_armory = any("armory" in list(getattr(t, 'buildings', [])) for t in tiles)
        has_barracks = any("barracks" in list(getattr(t, 'buildings', [])) for t in tiles)
        has_clinic = any("clinic" in list(getattr(t, 'buildings', [])) for t in tiles)

        # 粮草不足 → 粮仓
        if faction.grain < 2000 and not has_granary:
            return ("granary", tiles[0])

        # 兵力不足 → 征兵营
        if faction.troops < 3000 and not has_barracks:
            return ("barracks", tiles[0])

        # 军械不足 → 军械所
        if faction.arms < 500 and not has_armory:
            return ("armory", tiles[0])

        # 人口多 → 医馆
        if faction.population > 15000 and not has_clinic:
            return ("clinic", tiles[0])

        return None

    def _generate_summary(self, fid: str, faction, personality: str, commands: list) -> str:
        """生成决策摘要"""
        names = {
            cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type)
            for cmd in commands
        }
        personality_cn = {
            "aggressive": "征伐四方",
            "steady": "稳步经略",
            "conservative": "固守养民",
            "opportunist": "伺机而动",
            "diplomatic": "合纵连横",
        }
        strategy = personality_cn.get(personality, "运筹帷幄")
        return f"{faction.name}（{strategy}）：{len(commands)}项决策【{'、'.join(list(names)[:5])}】"

    def _assess_risk(self, faction, commands: list) -> str:
        """评估风险等级"""
        attack_count = sum(1 for c in commands if c.command_type == CommandType.MARCH)
        if attack_count >= 3:
            return "high"
        elif attack_count >= 1:
            return "medium"
        return "low"
