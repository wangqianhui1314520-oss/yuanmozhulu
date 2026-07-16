"""
AIExecutor - AI决策执行器

职责：
1. 接收各 Agent 返回的决策结果（文本建议+结构化数据）
2. 将文本决策映射为具体的游戏操作
3. 直接修改 WorldState（征兵、进攻、外交、谍报等）
4. 写入 events_log

这是 AI 决策到游戏状态的关键桥梁——解决 LLM 输出纯文本无法落地的问题。
"""
from __future__ import annotations
import logging
import random
from typing import Optional

from .agent_event_bus import EventTypes, EventPriority, get_event_bus

logger = logging.getLogger("yuanmo.agent.executor")


class AIExecutor:
    """AI决策执行器 - 将AI智能体的文本建议转化为具体的WorldState修改"""

    def __init__(self, world_state, faction_configs: dict, march_engine=None,
                 spy_engine=None, diplomacy_engine=None):
        self.world = world_state
        self.faction_configs = faction_configs
        self.march_engine = march_engine
        self.spy_engine = spy_engine
        self.diplomacy_engine = diplomacy_engine
        # 幂等性防护：去重已执行的操作
        self._executed_warlord_round = -1
        self._executed_diplomacy_round = -1
        self._executed_event_ids: set[str] = set()

    # ================================================================
    # A2 群雄殿决策 → 军事/内政操作
    # ================================================================

    def execute_warlord_decisions(self, warlord_results: list[dict]) -> list[dict]:
        """
        将A2群雄殿的决策解析为游戏操作并执行。

        执行策略（优先级递减）：
        1. ★ 优先使用 A2 返回的 decision_plan（结构化决策，直接落地）
        2. 其次使用 full_response 文本做关键词解析（兼容旧版）
        3. 都不可用时降级为 fallback_ai_step_enhanced 数值驱动

        Returns:
            [{"faction_id": ..., "actions": [...], "status": ...}]
        """
        actions_log = []

        # 幂等性：同一回合只执行一次
        current_round = self.world.current_round
        if current_round == self._executed_warlord_round:
            return actions_log

        for result in warlord_results:
            fid = result.get("faction_id", "")
            if not fid:
                continue

            faction = self.world.factions.get(fid)
            if not faction or not faction.is_alive:
                continue

            ai_config = self._get_ai_config(fid)
            executed = []

            # ★ 优先使用结构化决策计划
            decision_plan = result.get("decision_plan", {})
            if decision_plan and decision_plan.get("actions"):
                executed.extend(self._execute_plan(fid, faction, decision_plan, ai_config))
            else:
                # 降级1：文本关键词解析
                decision = result.get("full_response", "") or result.get("decision_summary", "")
                if decision:
                    executed.extend(self._parse_and_execute_military(fid, faction, decision, ai_config))
                    executed.extend(self._parse_and_execute_economy(fid, faction, decision, ai_config))
                    executed.extend(self._parse_and_execute_civil(fid, faction, decision, ai_config))

            # 如果仍然没有操作，用数值驱动兜底
            if not executed:
                executed.append("休整（无明确行动）")

            actions_log.append({
                "faction_id": fid,
                "faction_name": faction.name,
                "actions": executed,
                "status": "executed",
                "decision_source": "plan" if decision_plan.get("actions") else "text" if decision_plan else "fallback",
            })

        self._executed_warlord_round = current_round
        return actions_log

    def _execute_plan(self, fid: str, faction, plan: dict, ai_config: dict) -> list[str]:
        """
        根据 A2 结构化 decision_plan 执行具体游戏操作。

        plan 结构: {"primary_action": "recruit", "actions": [
            {"type": "recruit", "target": "", "amount": 300}, ...
        ]}
        """
        actions = []
        tiles = self.world.get_faction_tiles(fid)

        for act in plan.get("actions", []):
            action_type = act.get("type", "")
            target = act.get("target", "")
            target_fid = act.get("target_faction", "")
            amount = act.get("amount")  # None 表示 AI 未指定数量
            priority = act.get("priority", "normal")

            try:
                if action_type == "recruit":
                    # 修复 falsy 陷阱: amount=0 时 AI 明确不要招募，不应被 or 吞掉
                    recruit_count = amount if amount is not None else min(300, faction.treasury // 3, 800)
                    if recruit_count <= 0:
                        continue  # AI 明确指示不招募
                    if recruit_count > 50 and faction.treasury > recruit_count * 3:
                        faction.treasury -= recruit_count * 3
                        if tiles:
                            border = self._get_border_tiles(fid, tiles)
                            for t in (border or tiles):
                                t.troops += recruit_count // max(1, len(border or tiles))
                        faction.troops += recruit_count
                        actions.append(f"征兵{recruit_count}人")
                        self._log_event(fid, "military", f"{faction.name}征募新兵{recruit_count}人")

                elif action_type in ("march", "attack"):
                    if self.march_engine and tiles:
                        # v4.0: 检查是否有军事深化数据（阵型/兵力分配/将领）
                        military_detail = plan.get("military_detail", {})
                        executed_attack = self._execute_attack(
                            fid, faction, tiles, target_fid, ai_config,
                            military_detail=military_detail)
                        if executed_attack:
                            actions.extend(executed_attack)

                elif action_type == "defend":
                    if tiles and faction.treasury > 500:
                        for t in tiles[:2]:
                            t.fortification = min(100, t.fortification + random.randint(5, 15))
                        faction.treasury -= 300
                        actions.append("加固城防")
                        self._log_event(fid, "military", f"{faction.name}加固边境城防")

                elif action_type == "train_troops":
                    actions.append("操练士卒")
                    self._log_event(fid, "military", f"{faction.name}操练士卒")

                elif action_type in ("farm", "build"):
                    if tiles and faction.treasury > 400:
                        for t in tiles[:random.randint(1, 3)]:
                            t.development_level = min(100, t.development_level + random.randint(3, 10))
                        faction.treasury -= 300
                        actions.append("开垦荒地")
                        self._log_event(fid, "economy", f"{faction.name}推行屯田垦荒")

                elif action_type == "fortify":
                    if tiles and faction.treasury > 600:
                        for t in tiles[:2]:
                            t.fortification = min(100, t.fortification + random.randint(5, 12))
                        faction.treasury -= 350
                        actions.append("修筑城防")
                        self._log_event(fid, "military", f"{faction.name}修筑城防")

                elif action_type == "tax":
                    tax_income = min(2000, faction.population // 10)
                    faction.treasury += tax_income
                    faction.realm_stability = max(0, faction.realm_stability - random.randint(1, 3))
                    actions.append(f"征收赋税+{tax_income}两")

                elif action_type == "diplomacy":
                    neighbors = faction.neighbors if hasattr(faction, 'neighbors') else []
                    if target_fid and target_fid in neighbors:
                        self._set_relation(fid, target_fid, "alliance")
                        actions.append(f"与{target_fid}缔结外交关系")
                        self._log_event(fid, "diplomacy", f"{faction.name}与{target_fid}开展外交")
                        self._publish_event(
                            EventTypes.ALLIANCE_FORMED, "A2", fid,
                            priority=EventPriority.HIGH, target_fid=target_fid,
                            description=f"{faction.name}主动与{target_fid}结好",
                        )

                elif action_type == "spy":
                    if target_fid and self.spy_engine:
                        actions.append(f"派遣细作前往{target_fid}")
                        self._log_event(fid, "espionage", f"{faction.name}派遣细作渗透{target_fid}")

                elif action_type == "claim_title":
                    actions.append("称帝/称王")
                    faction.reputation = min(100, faction.reputation + 5)
                    self._log_event(fid, "civil", f"{faction.name}僭号称制！")
                    self._publish_event(
                        "new_faction_rise", "A2", fid,
                        priority=EventPriority.CRITICAL,
                        description=f"{faction.name}僭号称制，天下震动！",
                    )

                elif action_type == "consolidate":
                    actions.append("休整内政")
                    if faction.treasury > 200:
                        faction.treasury -= 150
                        faction.realm_stability = min(100, faction.realm_stability + random.randint(1, 3))

            except Exception as e:
                logger.warning(f"A2 plan执行 {action_type} 失败 {fid}: {e}")
                continue

        return actions

    def _parse_and_execute_military(self, fid: str, faction, decision: str, ai_config: dict) -> list[str]:
        """解析军事相关决策并执行"""
        actions = []
        decision_lower = decision.lower()
        tiles = self.world.get_faction_tiles(fid)

        # 征兵
        if any(kw in decision for kw in ["征兵", "募兵", "扩军", "招兵", "增兵", "补充兵力"]):
            recruit_count = self._extract_number(decision, default=300)
            recruit_count = min(recruit_count, faction.treasury // 3, 800)
            if recruit_count > 50 and faction.treasury > recruit_count * 3:
                faction.treasury -= recruit_count * 3
                if tiles:
                    # 优先边境
                    border = self._get_border_tiles(fid, tiles)
                    for t in (border or tiles):
                        t.troops += recruit_count // max(1, len(border or tiles))
                faction.troops += recruit_count
                actions.append(f"征兵{recruit_count}人")
                self._log_event(fid, "military", f"{faction.name}征募新兵{recruit_count}人")

        # 进攻
        if any(kw in decision for kw in ["进攻", "出击", "攻取", "攻打", "征讨", "讨伐"]):
            if self.march_engine and tiles:
                target_fid = self._extract_faction_target(decision)
                executed_attack = self._execute_attack(fid, faction, tiles, target_fid, ai_config)
                if executed_attack:
                    actions.extend(executed_attack)

        # 防守/加固
        if any(kw in decision for kw in ["防守", "固守", "坚守", "守城", "加固", "修缮城防"]):
            if tiles and faction.treasury > 500:
                for t in tiles[:2]:
                    t.fortification = min(100, t.fortification + random.randint(5, 15))
                faction.treasury -= 300
                actions.append("加固城防")
                self._log_event(fid, "military", f"{faction.name}加固边境城防")

        # 训练
        if any(kw in decision for kw in ["训练", "操练", "练兵"]):
            actions.append("操练士卒")

        return actions

    def _parse_and_execute_economy(self, fid: str, faction, decision: str, ai_config: dict) -> list[str]:
        """解析经济相关决策并执行"""
        actions = []
        tiles = self.world.get_faction_tiles(fid)

        # 开垦
        if any(kw in decision for kw in ["开垦", "屯田", "垦荒", "农耕", "劝农"]):
            if tiles and faction.treasury > 400:
                for t in tiles[:random.randint(1, 3)]:
                    t.development_level = min(100, t.development_level + random.randint(3, 10))
                faction.treasury -= 300
                actions.append("开垦荒地")
                self._log_event(fid, "economy", f"{faction.name}推行屯田垦荒")

        # 兴修水利
        if any(kw in decision for kw in ["水利", "灌溉", "修渠"]):
            if tiles and faction.treasury > 500:
                for t in tiles[:2]:
                    t.water_works = min(100, t.water_works + random.randint(5, 12))
                faction.treasury -= 400
                actions.append("兴修水利")

        # 征税
        if any(kw in decision for kw in ["征税", "加税", "课税"]):
            tax_income = min(2000, faction.population // 10)
            faction.treasury += tax_income
            faction.realm_stability = max(0, faction.realm_stability - random.randint(1, 3))
            actions.append(f"征收赋税+{tax_income}两")

        return actions

    def _parse_and_execute_civil(self, fid: str, faction, decision: str, ai_config: dict) -> list[str]:
        """解析内政相关决策并执行"""
        actions = []

        # 赈灾
        if any(kw in decision for kw in ["赈灾", "赈济", "放粮", "救灾"]):
            relief = min(500, faction.grain // 5)
            if relief > 50:
                faction.grain -= relief
                faction.realm_stability = min(100, faction.realm_stability + random.randint(2, 5))
                actions.append(f"赈灾放粮{relief}石")
                self._log_event(fid, "civil", f"{faction.name}开仓赈济灾民")

        # 选官
        if any(kw in decision for kw in ["选官", "举贤", "招贤", "纳士"]):
            if faction.treasury > 300:
                faction.treasury -= 200
                faction.realm_stability = min(100, faction.realm_stability + 1)
                actions.append("招贤纳士")

        return actions

    def _execute_attack(self, fid: str, faction, tiles: list, target_fid: str,
                        ai_config: dict, military_detail: dict = None) -> list[str]:
        """执行进攻操作（v4.0：支持阵型和兵力分配）"""
        actions = []
        military_detail = military_detail or {}

        # ★ v4.0 阵型加成
        formation = military_detail.get("formation", "方圆阵")
        formation_bonus = self._get_formation_bonus(formation)
        if formation_bonus:
            actions.append(f"布{formation}（{formation_bonus}）")

        # 找到可攻击的目标
        expansion_targets = []

        for atk_tile in tiles:
            if atk_tile.troops < 200:
                continue
            attackable = self.march_engine.get_attackable_neighbors(atk_tile.tile_id, fid)
            for target in attackable:
                if not target or not isinstance(target, dict):
                    continue
                enemy_id = target.get("faction_id", "")
                if not enemy_id or enemy_id == fid:
                    continue

                priority = 1.0
                # 如果指定了目标势力，提高优先级
                if target_fid and enemy_id == target_fid:
                    priority = 2.5
                # 如果处于交战状态，提高优先级
                rel = self.world.relations
                for key, r in rel.items():
                    if (r.faction_a == fid and r.faction_b == enemy_id) or \
                       (r.faction_b == fid and r.faction_a == enemy_id):
                        if hasattr(r.stance, 'value') and r.stance.value == "war":
                            priority = 2.0
                            break

                # 只攻击弱于己方的
                if target.get("troops", 9999) < atk_tile.troops * 0.85:
                    expansion_targets.append((atk_tile, target, priority))

        if expansion_targets:
            expansion_targets.sort(key=lambda x: x[2], reverse=True)
            atk_tile, target, _ = expansion_targets[0]
            troops_to_send = min(atk_tile.troops - 100, max(100, atk_tile.troops // 2))

            try:
                march_result = self.march_engine.resolve_march(
                    from_tile=atk_tile.tile_id,
                    to_tile=target["tile_id"],
                    troops=troops_to_send,
                    attacker_faction=fid,
                )
                battle = march_result.get("battle_result") or {}
                won = battle.get("winner") == fid
                tile_captured = march_result.get("tile_captured", False)
                captured_name = march_result.get("tile_name", "")
                actions.append(
                    f"进攻{target.get('faction_name', '?')}的{target.get('tile_name', '?')}"
                    f"{'（胜，占领' + captured_name + '）' if tile_captured else '（胜）' if won else '（败）'}"
                )
                if tile_captured:
                    self._log_event(
                        fid, "military",
                        f"{faction.name}出兵{target.get('faction_name', '?')}，"
                        f"成功占领{captured_name}！"
                    )
                    # 占领后安抚民心，小幅提升稳定度
                    faction.realm_stability = min(100, faction.realm_stability + 1)
                else:
                    self._log_event(
                        fid, "military",
                        f"{faction.name}出兵{target.get('faction_name', '?')}，"
                        f"{'大获全胜' if won else '铩羽而归'}"
                    )
            except Exception as e:
                logger.warning(f"A2 进攻执行失败 {fid}: {e}")

        return actions

    # ================================================================
    # A4 谍报司决策 → 细作操作
    # ================================================================

    def execute_espionage_actions(self, espionage_results: list[dict]) -> list[dict]:
        """
        将A4谍报司的情报分析转化为实际的细作行动

        根据渗透度和情报分析结果，执行渗透/破坏/窃取/谣言等操作。
        """
        actions_log = []

        for result in espionage_results:
            net_id = result.get("network_id", "")
            intel = result.get("intel", "")
            if not net_id or not intel:
                continue

            net_data = self.world.spy_networks.get(net_id)
            if not net_data:
                continue

            owner = net_data.owner_faction
            target = net_data.target_faction
            infiltration = net_data.infiltration
            action_points = net_data.action_points
            executed = []

            # 只有渗透度足够才执行主动行动
            if infiltration >= 20 and action_points > 0:
                # 根据情报内容决定行动类型
                intel_lower = intel.lower()

                if any(kw in intel for kw in ["破坏", " sabotage", "焚毁"]) and infiltration >= 30:
                    if self.spy_engine and target:
                        try:
                            self.spy_engine.sabotage(net_id, target)
                            net_data.action_points -= 1
                            executed.append(f"破坏{target}城防")
                            self._log_event(owner, "espionage",
                                            f"细作网络{net_id}破坏{target}设施")
                        except Exception as e:
                            logger.warning(f"A4 破坏执行失败 {net_id}: {e}")

                elif any(kw in intel for kw in ["窃取", "情报", "steal", "intel"]) and infiltration >= 25:
                    # 窃取情报 → 增加渗透度
                    net_data.infiltration = min(100, infiltration + random.randint(1, 5))
                    net_data.action_points -= 1
                    executed.append(f"窃取{target}情报（渗透度+）")
                    self._log_event(owner, "espionage",
                                    f"细作自{target}获取重要情报")

                elif any(kw in intel for kw in ["谣言", "散布", "rumor"]) and infiltration >= 20:
                    # 散布谣言 → 降低目标稳定度
                    target_faction = self.world.factions.get(target)
                    if target_faction:
                        target_faction.realm_stability = max(0,
                            target_faction.realm_stability - random.randint(1, 5))
                        net_data.action_points -= 1
                        executed.append(f"在{target}散布谣言")
                        self._log_event(owner, "espionage",
                                        f"细作在{target_faction.name}散布谣言，民心浮动")

                elif any(kw in intel for kw in ["渗透", "潜伏", "infiltrate"]):
                    # 持续渗透 → 缓慢增加渗透度
                    net_data.infiltration = min(100, infiltration + random.randint(1, 3))
                    executed.append("持续渗透（渗透度+）")

                # 渗透度自然增长
                if infiltration < 50:
                    net_data.infiltration = min(100, infiltration + random.randint(0, 2))

            actions_log.append({
                "network_id": net_id,
                "owner": owner,
                "target": target,
                "actions": executed,
                "infiltration": net_data.infiltration,
            })

        return actions_log

    # ================================================================
    # A5 司天台事件 → 数值回写
    # ================================================================

    def apply_event_impacts(self, event_result: dict) -> dict:
        """
        将A5司天台计算的事件影响数值回写到WorldState

        这是A5事件闭环的关键步骤——之前A5计算了影响但从未应用。
        """
        applied = {"factions_affected": 0, "total_grain_loss": 0,
                   "total_pop_loss": 0, "total_troop_loss": 0}

        # 幂等性：同 event_id 不重复执行
        event_id = event_result.get("event_id", "")
        if event_id and event_id in self._executed_event_ids:
            return applied
        if event_id:
            self._executed_event_ids.add(event_id)

        affected = event_result.get("affected_factions", [])
        for af in affected:
            fid = af.get("faction_id", "")
            faction = self.world.factions.get(fid)
            if not faction or not faction.is_alive:
                continue

            # 应用粮食损失
            grain_loss = af.get("grain_loss", 0)
            if grain_loss > 0:
                faction.grain = max(0, faction.grain - grain_loss)
                applied["total_grain_loss"] += grain_loss

            # 应用人口损失/变化
            pop_change = af.get("population_change", 0)
            pop_loss = af.get("population_loss", 0)
            if pop_change != 0:
                faction.population = max(100, faction.population + pop_change)
                applied["total_pop_loss"] += abs(pop_change)
            elif pop_loss > 0:
                faction.population = max(100, faction.population - pop_loss)
                applied["total_pop_loss"] += pop_loss

            # 应用兵力损失
            troop_loss = af.get("troop_loss", 0)
            if troop_loss > 0:
                faction.troops = max(0, faction.troops - troop_loss)
                applied["total_troop_loss"] += troop_loss

            # 应用声望变化
            rep_change = af.get("reputation_change", 0)
            if rep_change != 0:
                faction.reputation = max(0, min(100, faction.reputation + rep_change))

            # 流民的粮食消耗
            grain_cost = af.get("grain_cost", 0)
            if grain_cost > 0:
                faction.grain = max(0, faction.grain - grain_cost)

            # 写入事件日志
            event_type = af.get("event_type", af.get("disaster_type", "事件"))
            faction_name = af.get("faction_name", faction.name)
            self._log_event(fid, "event",
                            f"{faction_name}遭遇{event_type}，"
                            f"粮损{grain_loss}石 人口损{pop_loss or abs(pop_change)}人")

            applied["factions_affected"] += 1

        # 如果是天灾，增加灾厄指数
        if event_result.get("disaster_occurred"):
            self.world.disaster_index = min(100,
                self.world.disaster_index + random.randint(3, 8))

        return applied

    # ================================================================
    # A6 外交署决策 → 外交操作
    # ================================================================

    def execute_diplomacy_actions(self, diplomacy_results: list[dict]) -> list[dict]:
        """
        将A6外交署的分析建议转化为实际的外交操作

        根据外交建议文本，执行结盟/宣战/贸易/进贡等操作。
        """
        actions_log = []

        # 幂等性：同一回合只执行一次外交
        current_round = self.world.current_round
        if current_round == self._executed_diplomacy_round:
            return actions_log

        for result in diplomacy_results:
            fid = result.get("faction_id", "")
            advice = result.get("diplomacy_advice", "")
            if not fid or not advice:
                continue

            faction = self.world.factions.get(fid)
            if not faction or not faction.is_alive:
                continue

            neighbors = result.get("neighbors", [])
            executed = []

            # 结盟建议
            if any(kw in advice for kw in ["结盟", "联盟", "联合", "同盟"]):
                ally_target = self._find_diplomacy_target(fid, neighbors, advice)
                if ally_target and self.diplomacy_engine:
                    try:
                        # 建立同盟关系
                        self._set_relation(fid, ally_target, "alliance")
                        executed.append(f"与{ally_target}结盟")
                        self._log_event(fid, "diplomacy",
                                        f"{faction.name}与{ally_target}缔结盟约")
                        # 发布结盟事件到总线
                        self._publish_event(
                            EventTypes.ALLIANCE_FORMED, "A6", fid,
                            priority=EventPriority.HIGH,
                            target_fid=ally_target,
                            description=f"{faction.name}与{ally_target}缔结盟约",
                        )
                    except Exception as e:
                        logger.warning(f"A6 结盟执行失败 {fid}→{ally_target}: {e}")

            # 宣战建议
            if any(kw in advice for kw in ["宣战", "讨伐", "出兵"]):
                war_target = self._find_diplomacy_target(fid, neighbors, advice)
                if war_target and self.diplomacy_engine:
                    try:
                        self._set_relation(fid, war_target, "war")
                        executed.append(f"向{war_target}宣战")
                        self._log_event(fid, "diplomacy",
                                        f"{faction.name}向{war_target}宣战！")
                        # 发布宣战事件到总线
                        self._publish_event(
                            EventTypes.WAR_DECLARED, "A6", fid,
                            priority=EventPriority.CRITICAL,
                            target_fid=war_target,
                            description=f"{faction.name}向{war_target}宣战！",
                        )
                    except Exception as e:
                        logger.warning(f"A6 宣战执行失败 {fid}→{war_target}: {e}")

            # 贸易建议
            if any(kw in advice for kw in ["贸易", "通商", "互市"]):
                trade_target = self._find_diplomacy_target(fid, neighbors, advice)
                if trade_target:
                    trade_income = random.randint(200, 800)
                    faction.treasury += trade_income
                    executed.append(f"与{trade_target}通商+{trade_income}两")

            # 求和/停战（签停战条约，不扣钱）
            if any(kw in advice for kw in ["求和", "停战", "议和", "休战"]):
                peace_target = self._find_diplomacy_target(fid, neighbors, advice)
                if peace_target:
                    self._set_relation(fid, peace_target, "truce")
                    executed.append(f"向{peace_target}求和停战")
                    self._log_event(fid, "diplomacy",
                                    f"{faction.name}向{peace_target}求和停战")
                    self._publish_event(
                        EventTypes.PEACE_TREATY, "A6", fid,
                        priority=EventPriority.HIGH,
                        target_fid=peace_target,
                        description=f"{faction.name}向{peace_target}求和停战",
                    )

            # 纳贡/进贡/称臣（扣钱）
            if any(kw in advice for kw in ["纳贡", "进贡", "称臣"]):
                tribute_target = self._find_diplomacy_target(fid, neighbors, advice)
                if tribute_target and faction.treasury > 500:
                    tribute = min(1000, faction.treasury // 4)
                    faction.treasury -= tribute
                    self._set_relation(fid, tribute_target, "neutral")
                    executed.append(f"向{tribute_target}纳贡{tribute}两")
                    self._log_event(fid, "diplomacy",
                                    f"{faction.name}向{tribute_target}纳贡称臣")
                    self._publish_event(
                        EventTypes.TRIBUTE_OFFERED, "A6", fid,
                        priority=EventPriority.HIGH,
                        target_fid=tribute_target,
                        description=f"{faction.name}向{tribute_target}纳贡称臣",
                    )

            # 联姻
            if any(kw in advice for kw in ["联姻", "和亲"]):
                marry_target = self._find_diplomacy_target(fid, neighbors, advice)
                if marry_target:
                    self._set_relation(fid, marry_target, "alliance")
                    executed.append(f"与{marry_target}联姻")
                    self._log_event(fid, "diplomacy",
                                    f"{faction.name}与{marry_target}联姻结好")

            actions_log.append({
                "faction_id": fid,
                "faction_name": faction.name,
                "actions": executed,
            })

        self._executed_diplomacy_round = current_round
        return actions_log

    # ================================================================
    # A7 宗室府 → 皇子数据回写
    # ================================================================

    def apply_royal_updates(self, royal_results: list[dict]) -> dict:
        """
        将A7宗室府返回的皇子成长数据回写到WorldState

        之前A7计算了皇子年龄+1和能力提升，但从未写回。
        """
        applied = {"factions_updated": 0, "heirs_total": 0}

        for result in royal_results:
            fid = result.get("faction_id", "")
            heirs = result.get("heirs", [])
            ruler_age = result.get("ruler_age")

            faction = self.world.factions.get(fid)
            if not faction:
                continue

            # 回写君主年龄
            if ruler_age:
                faction.ruler_age = ruler_age

            # 回写皇子数据
            if heirs:
                faction.heirs = heirs
                applied["heirs_total"] += len(heirs)

            # 应用继承风险
            risk = result.get("succession_risk", "low")
            if risk == "high":
                faction.realm_stability = max(0, faction.realm_stability - random.randint(2, 5))
            elif risk == "medium":
                faction.realm_stability = max(0, faction.realm_stability - random.randint(0, 2))

            applied["factions_updated"] += 1

        return applied

    # ================================================================
    # 降级方案增强：利用 faction_config 的 ai_logic 参数
    # ================================================================

    def fallback_ai_step_enhanced(self, skip_faction_id: str = "") -> dict:
        """
        增强版降级方案：利用 faction_config 中的 ai_logic 参数
        实现每个势力差异化的数值驱动行为。

        相比原来的纯随机方案，此版本根据势力特质
        （expansion/consolidation/diplomacy/military/economy）
        做出有差异的决策。
        """
        results = {"agents_ran": 0, "engine": "numerical_fallback_enhanced",
                   "actions": [], "battles": []}

        for fid, faction in self.world.factions.items():
            if not faction.is_alive or fid == skip_faction_id:
                continue

            tiles = self.world.get_faction_tiles(fid)
            if not tiles:
                continue

            results["agents_ran"] += 1
            ai_cfg = self._get_ai_config(fid)

            # --- 征兵（受 military 参数影响）---
            military_drive = ai_cfg.get("military", 0.5)
            if faction.treasury > 1500 and random.random() < military_drive * 0.6:
                recruits = int(min(600, faction.treasury // 2) * military_drive)
                faction.treasury -= recruits * 2
                border = self._get_border_tiles(fid, tiles)
                for t in (border or tiles):
                    t.troops += recruits // max(1, len(border or tiles))
                faction.troops += recruits
                results["actions"].append(f"{faction.name}征兵{recruits}人")

            # --- 发展经济（受 economy 参数影响）---
            economy_drive = ai_cfg.get("economy", 0.3)
            if faction.treasury > 800 and random.random() < economy_drive * 0.5:
                faction.treasury -= 400
                for t in tiles[:random.randint(1, 3)]:
                    t.development_level = min(100, t.development_level + random.randint(3, 8))
                results["actions"].append(f"{faction.name}发展经济")

            # --- 扩张（受 expansion 参数影响）---
            expansion_drive = ai_cfg.get("expansion", 0.4)
            if random.random() < expansion_drive * 0.5 and len(tiles) >= 2:
                expansion_targets = []

                # 优先攻击交战势力
                for key, rel in self.world.relations.items():
                    if (rel.faction_a == fid or rel.faction_b == fid):
                        try:
                            stance_val = rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance)
                        except AttributeError:
                            stance_val = str(rel.stance)
                        if stance_val == "war":
                            enemy_id = rel.faction_b if rel.faction_a == fid else rel.faction_a
                            enemy_tiles = self.world.get_faction_tiles(enemy_id)
                            if enemy_tiles:
                                for atk_tile in tiles:
                                    if atk_tile.troops < 200:
                                        continue
                                    attackable = self.march_engine.get_attackable_neighbors(
                                        atk_tile.tile_id, fid) if self.march_engine else []
                                    for target in attackable:
                                        if not target or not isinstance(target, dict):
                                            continue
                                        if target.get("faction_id") == enemy_id:
                                            expansion_targets.append((atk_tile, target, 2.0))

                # 攻击弱邻
                if not expansion_targets:
                    for atk_tile in tiles:
                        if atk_tile.troops < 300:
                            continue
                        attackable = self.march_engine.get_attackable_neighbors(
                            atk_tile.tile_id, fid) if self.march_engine else []
                        for target in attackable:
                            if not target or not isinstance(target, dict):
                                continue
                            tfid = target.get("faction_id", "")
                            if tfid and tfid != fid:
                                if target.get("troops", 9999) < atk_tile.troops * 0.8:
                                    expansion_targets.append((atk_tile, target, 1.0))

                if expansion_targets:
                    expansion_targets.sort(key=lambda x: x[2], reverse=True)
                    atk_tile, target, _ = expansion_targets[0]
                    if self.march_engine:
                        try:
                            march_result = self.march_engine.resolve_march(
                                from_tile=atk_tile.tile_id,
                                to_tile=target["tile_id"],
                                troops=min(atk_tile.troops - 100, max(100, atk_tile.troops // 2)),
                                attacker_faction=fid,
                            )
                            battle = march_result.get("battle_result") or {}
                            won = battle.get("winner") == fid
                            results["actions"].append(
                                f"{faction.name}进攻{target.get('faction_name', '?')}的"
                                f"{target.get('tile_name', '?')}{'（胜）' if won else '（败）'}"
                            )
                            if march_result.get("battle_result"):
                                results["battles"].append({
                                    "attacker": fid,
                                    "defender": target.get("faction_id"),
                                    "tile": target.get("tile_name"),
                                    "result": won,
                                })
                            # 发布战斗事件到总线
                            self._publish_event(
                                EventTypes.BATTLE_STARTED, "fallback", fid,
                                priority=EventPriority.HIGH,
                                target_fid=target.get("faction_id", ""),
                                description=f"{faction.name}进攻{target.get('faction_name', '?')}{'（胜）' if won else '（败）'}",
                            )
                        except Exception as e:
                            logger.warning(f"降级方案进攻失败 {fid}: {e}")

            # --- 巩固（受 consolidation 参数影响）---
            consolidation_drive = ai_cfg.get("consolidation", 0.4)
            if faction.treasury > 600 and random.random() < consolidation_drive * 0.4:
                for t in tiles[:2]:
                    t.fortification = min(100, t.fortification + random.randint(3, 10))
                faction.treasury -= 200
                results["actions"].append(f"{faction.name}巩固城防")

        return results

    # ================================================================
    # 辅助方法
    # ================================================================

    def _get_ai_config(self, faction_id: str) -> dict:
        """获取势力AI参数"""
        factions = self.faction_configs.get("factions", {})
        cfg = factions.get(faction_id, {})
        return cfg.get("ai_logic", {
            "expansion": 0.4, "consolidation": 0.4,
            "diplomacy": 0.3, "military": 0.5, "economy": 0.3,
        })

    def _extract_number(self, text: str, default: int = 300) -> int:
        """从文本中提取数字"""
        import re
        # 匹配中文数字描述
        patterns = [
            (r'(\d+)人', 1), (r'(\d+)名', 1), (r'(\d+)骑', 1),
            (r'(\d+)千', 1000), (r'(\d+)万', 10000), (r'(\d+)百', 100),
        ]
        for pat, mult in patterns:
            m = re.search(pat, text)
            if m:
                return int(m.group(1)) * mult
        return default

    def _extract_faction_target(self, decision: str) -> str:
        """从决策文本中提取目标势力"""
        # 检查所有势力名
        for fid, faction in self.world.factions.items():
            if faction.name in decision:
                return fid
        return ""

    def _find_diplomacy_target(self, fid: str, neighbors: list, advice: str) -> str:
        """从外交建议中找到目标势力"""
        # 先在邻国中找
        for nid in neighbors:
            n_faction = self.world.factions.get(nid)
            if n_faction and n_faction.name in advice:
                return nid
        # 再在所有势力名中找
        for nid, n_faction in self.world.factions.items():
            if nid != fid and n_faction.name in advice:
                return nid
        # 返回第一个邻国
        return neighbors[0] if neighbors else ""

    def _get_border_tiles(self, fid: str, tiles: list) -> list:
        """获取边境地块"""
        if not self.march_engine:
            return tiles
        border = []
        for t in tiles:
            neighbors = self.march_engine.get_attackable_neighbors(t.tile_id, fid)
            if neighbors:
                border.append(t)
        return border or tiles

    def _set_relation(self, fid_a: str, fid_b: str, stance: str):
        """设置两势力关系"""
        from server.models.world_state import RelationState, DiplomaticStance

        stance_map = {
            "alliance": DiplomaticStance.ALLIANCE,
            "war": DiplomaticStance.WAR,
            "neutral": DiplomaticStance.NEUTRAL,
            "truce": DiplomaticStance.TRUCE,
        }

        target_stance = stance_map.get(stance, DiplomaticStance.NEUTRAL)

        # 查找已有关系
        for key, rel in list(self.world.relations.items()):
            if (rel.faction_a == fid_a and rel.faction_b == fid_b) or \
               (rel.faction_a == fid_b and rel.faction_b == fid_a):
                rel.stance = target_stance
                return

        # 创建新关系（键排序保证唯一性，避免 a_b 和 b_a 重复）
        new_key = "_".join(sorted([fid_a, fid_b]))
        self.world.relations[new_key] = RelationState(
            faction_a=fid_a,
            faction_b=fid_b,
            stance=target_stance,
        )

    def _log_event(self, faction_id: str, category: str, description: str):
        """写入事件日志（统一格式，与前端 GameEvent 类型对齐）"""
        event_id = f"ai_{category}_{self.world.current_round}_{len(self.world.events_log)}"
        # 将 category 映射为标准的 event_type
        event_type_map = {
            "military": "battle",
            "economy": "economy",
            "civil": "civil",
            "espionage": "spy",
            "diplomacy": "diplomacy",
            "event": "random",
        }
        event_type = event_type_map.get(category, "civil")
        # 从 description 中提取简短的 title
        title = description[:40] if len(description) <= 40 else description[:38] + ".."
        self.world.events_log.append({
            "event_id": event_id,
            "event_type": event_type,
            "severity": "minor",
            "round": self.world.current_round,
            "title": title,
            "description": description,
            "faction_id": faction_id,
            "tile_id": "",
            "effects": {},
            "narrative": description,
        })

    @staticmethod
    def _publish_event(event_type: str, source_agent: str, source_fid: str,
                       priority: EventPriority = EventPriority.NORMAL,
                       target_fid: str = "", description: str = ""):
        """将游戏事件发布到Agent事件总线"""
        try:
            bus = get_event_bus()
            bus.publish_simple(
                event_type=event_type,
                source_agent=source_agent,
                source_faction_id=source_fid,
                target_faction_id=target_fid,
                priority=priority,
                data={"description": description},
            )
        except Exception as e:
            logger.debug(f"事件总线发布失败（非致命）: {e}")

    @staticmethod
    def _get_formation_bonus(formation: str) -> str:
        """v4.0: 返回阵型加成描述（实际加成由 combat_modifiers 处理）"""
        bonuses = {
            "锋矢阵": "突击+25%，防御-10%",
            "鹤翼阵": "包抄+20%，骑兵伤+15%",
            "方圆阵": "防御+30%，机动-10%",
            "长蛇阵": "行军速度+30%，遭遇战-15%",
            "雁行阵": "远程伤害+25%，近战-10%",
        }
        return bonuses.get(formation, "")

