"""
征伐全局编排器 - 6大AI模块联动协调中枢

职责：
1. 接收宣战/出征事件，协调所有征伐子AI模块联动响应
2. 确保各模块按正确时序执行（外交→军事→民生→叛军→谋略→疆域）
3. 为每场征伐维护 WarfareContext 追踪全链路状态
4. 回合结算时触发军事AI完成战损/溃散/易主判定

联动时序:
  宣战触发 → ①全局外交AI(同盟援敌/背刺/中立判定)
           → ②敌方军事AI(编组反击军团+反制战术)
           → ③民生治理AI(征兵比例/粮草囤积/民心维稳)
           → ④叛乱灾害AI(战乱地块动乱概率飙升)
  ──回合结算──→ ⑤军事结算AI(战损/溃散/领地易主)
              → ⑥疆域AI(势力色块/法理归属/迷雾刷新)
              → ⑦谋略AI(离间/刺杀/流言降士气)
"""

from __future__ import annotations
import asyncio
import logging
import random
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("yuanmo.war.orchestrator")


class WarfareStage(Enum):
    """征伐阶段"""
    DECLARATION = "declaration"       # 宣战阶段
    MOBILIZATION = "mobilization"     # 动员阶段（外交+军事）
    MARCH = "march"                   # 行军阶段
    ENGAGEMENT = "engagement"         # 交战阶段
    SETTLEMENT = "settlement"         # 结算阶段
    AFTERMATH = "aftermath"           # 战后阶段


@dataclass
class WarfareContext:
    """单场征伐的全链路上下文"""
    war_id: str
    attacker_faction: str
    defender_faction: str
    declared_round: int
    stage: WarfareStage = WarfareStage.DECLARATION

    # 宣战理由（Casus Belli）
    casus_belli: str = ""                      # CB 类型 (conquest/reconquest/...)
    casus_belli_name: str = ""                 # CB 中文名
    war_goal_tiles: list = field(default_factory=list)  # 战争目标地块
    can_seize_territory: bool = True
    can_demand_tribute: bool = False
    can_enforce_vassal: bool = False
    war_score_multiplier: float = 1.0

    # 战争分数追踪器（延迟初始化）
    _war_score_tracker: object = None          # WarScoreTracker 实例

    # ① 外交AI结果
    diplomacy_result: dict = field(default_factory=dict)
    # ② 敌方军事AI结果
    military_counter: dict = field(default_factory=dict)
    # ③ 民生AI结果
    civil_adjustments: dict = field(default_factory=dict)
    # ④ 叛军风险
    rebellion_risks: list = field(default_factory=list)
    # ⑤ 战斗结算
    battle_settlements: list = field(default_factory=list)
    # ⑥ 疆域变更
    territory_changes: list = field(default_factory=list)
    # ⑦ 谋略行为
    stratagem_actions: list = field(default_factory=list)

    # 参战方（含盟友/背刺）
    attacker_allies: list = field(default_factory=list)
    defender_allies: list = field(default_factory=list)
    backstabbers: list = field(default_factory=list)  # 背刺偷袭方
    neutrals: list = field(default_factory=list)

    def get_war_score(self):
        """获取战争分数追踪器（懒加载）"""
        if self._war_score_tracker is None:
            from server.war.war_score import WarScoreTracker
            self._war_score_tracker = WarScoreTracker(
                war_id=self.war_id,
                attacker_faction=self.attacker_faction,
                defender_faction=self.defender_faction,
                war_score_multiplier=self.war_score_multiplier,
                war_goal_tiles=set(self.war_goal_tiles),
            )
        return self._war_score_tracker


class WarOrchestrator:
    """
    征伐全局编排器

    用法（在 round_engine 的 AI 推演阶段）:
      orchestrator = WarOrchestrator(world, llm_clients)
      # 对每场 active war:
      await orchestrator.orchestrate_war_turn(war_context)
    """

    def __init__(self, world_state, llm_clients: dict = None,
                 game_const: dict = None):
        self.world = world_state
        self.llm_clients = llm_clients or {}
        self.const = game_const or {}
        self._active_wars: dict[str, WarfareContext] = {}

        # 懒加载子模块
        self._diplomacy_ai = None
        self._military_ai = None
        self._civil_ai = None
        self._rebellion_ai = None
        self._stratagem_ai = None
        self._territory_ai = None

    # ================================================================
    # 入口：宣战触发全链路联动
    # ================================================================

    async def on_war_declared(self, attacker: str, defender: str,
                              reason: str = "",
                              casus_belli: str = "conquest",
                              war_goal_tiles: list = None,
                              can_seize_territory: bool = True,
                              can_demand_tribute: bool = False,
                              can_enforce_vassal: bool = False,
                              war_score_multiplier: float = 1.0) -> WarfareContext:
        """
        宣战触发入口 - 驱动全链路AI联动

        执行顺序:
        ① 全局外交AI → 判定所有NPC势力倾向
        ② 敌方军事AI → 生成反制策略
        ③ 民生治理AI → 调整双方内政
        ④ 叛乱灾害AI → 评估动乱风险
        """
        war_id = f"war_{attacker}_{defender}_{self.world.current_round}"
        # 获取 CB 中文名（安全解析，未知 CB 回退为 conquest）
        from server.war.casus_belli import CasusBelli, CB_CONFIG
        try:
            cb_enum = CasusBelli(casus_belli)
            cfg = CB_CONFIG.get(cb_enum)
            cb_name = cfg.name if cfg else (reason or "兴兵讨伐")
        except (ValueError, KeyError):
            cb_enum = CasusBelli.CONQUEST
            cfg = CB_CONFIG.get(cb_enum)
            cb_name = cfg.name if cfg else (reason or "兴兵讨伐")

        ctx = WarfareContext(
            war_id=war_id,
            attacker_faction=attacker,
            defender_faction=defender,
            declared_round=self.world.current_round,
            casus_belli=casus_belli,
            casus_belli_name=cb_name,
            war_goal_tiles=war_goal_tiles or [],
            can_seize_territory=can_seize_territory,
            can_demand_tribute=can_demand_tribute,
            can_enforce_vassal=can_enforce_vassal,
            war_score_multiplier=war_score_multiplier,
        )
        # 初始化战争分数追踪器
        ctx.get_war_score()
        self._active_wars[war_id] = ctx

        logger.info(f"[征伐编排] 宣战触发: {attacker} → {defender}, "
                     f"cb={casus_belli}, reason={reason}, war_id={war_id}")

        # ① 全局外交AI：所有NPC势力判定倾向
        logger.info(f"[征伐编排] 阶段①: 全局外交AI判定...")
        ctx.diplomacy_result = await self._run_global_diplomacy_ai(ctx)

        # ② 敌方军事AI：防守方生成反制战术
        logger.info(f"[征伐编排] 阶段②: 敌方军事AI反制...")
        ctx.military_counter = await self._run_military_counter_ai(ctx)

        # ③ 民生治理AI：双方调整内政
        logger.info(f"[征伐编排] 阶段③: 民生治理AI调整...")
        ctx.civil_adjustments = await self._run_civil_adjustment_ai(ctx)

        # ④ 叛乱灾害AI：战乱风险评估
        logger.info(f"[征伐编排] 阶段④: 叛乱灾害AI评估...")
        ctx.rebellion_risks = self._run_rebellion_risk_ai(ctx)

        ctx.stage = WarfareStage.MOBILIZATION
        return ctx

    # ================================================================
    # 每回合战时结算入口
    # ================================================================

    async def orchestrate_war_turn(self, ctx: WarfareContext) -> dict:
        """
        回合结算时调用 - 驱动对战双方的战术行为

        执行: ⑤ 军事结算 → ⑥ 疆域刷新 → ⑦ 谋略行为
        """
        result = {"war_id": ctx.war_id, "round": self.world.current_round}

        # ⑤ 军事结算AI
        self._ensure_engines()
        ctx.battle_settlements = await self._run_battle_settlement_ai(ctx)
        result["battles"] = ctx.battle_settlements

        # ⑥ 疆域AI
        ctx.territory_changes = self._run_territory_ai(ctx)
        result["territory_changes"] = ctx.territory_changes

        # ⑦ 谋略AI
        ctx.stratagem_actions = await self._run_stratagem_ai(ctx)
        result["stratagems"] = ctx.stratagem_actions

        ctx.stage = WarfareStage.AFTERMATH
        return result

    # ================================================================
    # ① 全局外交AI - 判定所有NPC势力的战争倾向
    # ================================================================

    async def _run_global_diplomacy_ai(self, ctx: WarfareContext) -> dict:
        """判定所有NPC对这场战争的立场：援攻方、援守方、背刺、中立"""
        result = {
            "attacker_allies": [],
            "defender_allies": [],
            "backstabbers": [],
            "neutrals": [],
            "stance_details": {},
        }

        atk = self.world.factions.get(ctx.attacker_faction)
        dff = self.world.factions.get(ctx.defender_faction)

        for fid, faction in self.world.factions.items():
            if not faction.is_alive:
                continue
            if fid in (ctx.attacker_faction, ctx.defender_faction):
                continue

            stance = self._determine_npc_war_stance(
                faction=faction,
                attacker=atk,
                defender=dff,
                attacker_id=ctx.attacker_faction,
                defender_id=ctx.defender_faction,
            )

            result["stance_details"][fid] = stance

            if stance["action"] == "support_attacker":
                result["attacker_allies"].append(fid)
            elif stance["action"] == "support_defender":
                result["defender_allies"].append(fid)
            elif stance["action"] == "backstab":
                result["backstabbers"].append(fid)
            else:
                result["neutrals"].append(fid)

        ctx.attacker_allies = result["attacker_allies"]
        ctx.defender_allies = result["defender_allies"]
        ctx.backstabbers = result["backstabbers"]
        ctx.neutrals = result["neutrals"]

        # 将外交AI结果写入事件日志
        self._log_diplomacy_stances(ctx, result)
        return result

    def _determine_npc_war_stance(self, faction, attacker, defender,
                                   attacker_id: str, defender_id: str) -> dict:
        """
        判定单个NPC势力对这场战争的立场

        因子：
        - 与攻/守方当前外交关系（同盟>附庸>中立>停战）
        - 与攻/守方的接壤程度
        - 势力AI策略标签（expansion/consolidation/diplomacy等）
        - 攻/守方实力对比
        - 地缘利益（是否有争议地块）
        """
        fid = faction.faction_id

        # 当前与双方的外交关系
        rel_atk = self._get_relation(fid, attacker_id)
        rel_dff = self._get_relation(fid, defender_id)

        # 实力对比
        atk_power = (attacker.total_troops if attacker else 0)
        dff_power = (defender.total_troops if defender else 0)
        npc_power = faction.total_troops

        # 地缘接壤分析
        border_atk = self._count_shared_border(fid, attacker_id)
        border_dff = self._count_shared_border(fid, defender_id)

        # AI策略标签
        personality = getattr(faction, 'personality_tags', [])
        ai_config = {}  # 从 faction_configs 获取
        if hasattr(self, '_faction_configs'):
            ai_config = self._faction_configs.get(fid, {})

        # === 判定逻辑 ===
        stance_score = 0  # 正值=倾向攻方，负值=倾向守方

        # 同盟加成
        if rel_atk == "alliance":
            stance_score += 40
        if rel_dff == "alliance":
            stance_score -= 40

        # 附庸关系
        if rel_atk == "vassal":
            stance_score += 30  # 宗主被攻，附庸必援
        if rel_dff == "vassal":
            stance_score -= 30

        # 战争状态（已与某方交战）
        relations = self.world.relations or {}
        atk_rel_key = self.world.relation_key(fid, attacker_id)
        dff_rel_key = self.world.relation_key(fid, defender_id)
        atk_rel = relations.get(atk_rel_key, {})
        dff_rel = relations.get(dff_rel_key, {})

        if atk_rel.get("stance") == "war":
            stance_score -= 50  # 与攻方已交战，自然支持守方
        if dff_rel.get("stance") == "war":
            stance_score += 50  # 与守方已交战，自然支持攻方

        # 地缘利益：接壤越多越容易趁火打劫
        if border_atk > 0 and border_dff == 0:
            stance_score += 10  # 仅与攻方接壤，可能支持攻方
        elif border_dff > 0 and border_atk == 0:
            stance_score -= 10  # 仅与守方接壤

        # 实力评估：弱者倾向援弱抗强（均势外交）
        power_ratio = (atk_power / max(dff_power, 1)) if dff_power > 0 else 2.0
        if npc_power < atk_power * 0.5 and npc_power < dff_power * 0.5:
            # NPC是小势力，倾向于援弱方
            if power_ratio > 1.5:
                stance_score -= 15  # 攻方太强，援守方
            elif power_ratio < 0.67:
                stance_score += 15  # 守方太强，援攻方

        # 背刺判定：与攻方接壤+守方兵力空虚
        if border_atk > 0 and dff_power < atk_power * 0.5:
            if rel_atk not in ("alliance", "vassal"):
                # 有概率背刺攻方（趁其主力外出）
                if random.random() < 0.25:
                    stance_score -= 60
                    logger.info(f"[外交AI] {faction.name} 决定背刺 {attacker.name if attacker else attacker_id}！")

        # 侵略性AI标签
        if "aggressive" in personality or "扩张" in str(personality):
            # 侵略性格：更倾向趁乱扩张
            if border_atk > 0 or border_dff > 0:
                if random.random() < 0.35:
                    target = "attacker" if random.random() < 0.5 else "defender"
                    if target == "attacker" and rel_atk not in ("alliance", "vassal"):
                        stance_score -= 60
                    elif target == "defender" and rel_dff not in ("alliance", "vassal"):
                        stance_score += 60

        # 确定最终行动
        if stance_score >= 30:
            action = "support_attacker"
            narrative = f"{faction.name}决定支援{attacker.name if attacker else attacker_id}！"
        elif stance_score <= -30:
            action = "support_defender"
            narrative = f"{faction.name}决定支援{defender.name if defender else defender_id}！"
        elif stance_score <= -60:
            action = "backstab"
            target = attacker_id if stance_score < -50 else defender_id
            narrative = f"{faction.name}趁乱偷袭！"
        else:
            action = "neutral"
            narrative = f"{faction.name}坐山观虎斗，按兵不动。"

        return {
            "faction_id": fid,
            "faction_name": faction.name,
            "stance_score": stance_score,
            "action": action,
            "narrative": narrative,
            "border_atk": border_atk,
            "border_dff": border_dff,
        }

    def _get_relation(self, fid_a: str, fid_b: str) -> str:
        """获取两方关系类型"""
        relations = self.world.relations or {}
        key = self.world.relation_key(fid_a, fid_b)
        rel = relations.get(key, {})
        return rel.get("stance", "neutral")

    def _count_shared_border(self, fid_a: str, fid_b: str) -> int:
        """计算两方接壤地块数"""
        count = 0
        tiles_a = self.world.get_faction_tiles(fid_a)
        tiles_b_ids = {t.tile_id for t in self.world.get_faction_tiles(fid_b)}

        for t in tiles_a:
            for nb in self._get_neighbor_ids(t.tile_id):
                if nb in tiles_b_ids:
                    count += 1
        return count

    def _get_neighbor_ids(self, tile_id: str) -> list:
        """获取地块的邻居ID列表"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return []
        col, row = tile.col, tile.row
        neighbors = []
        for dc, dr in [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]:
            nc, nr = col + dc, row + dr
            for tid, t in self.world.tiles.items():
                if t.col == nc and t.row == nr:
                    neighbors.append(tid)
                    break
        return neighbors

    def _log_diplomacy_stances(self, ctx: WarfareContext, result: dict):
        """将外交判定结果写入事件日志"""
        atk_name = (self.world.factions.get(ctx.attacker_faction) or
                    type('', (), {'name': ctx.attacker_faction})()).name
        dff_name = (self.world.factions.get(ctx.defender_faction) or
                    type('', (), {'name': ctx.defender_faction})()).name

        allies_text = ""
        backstab_text = ""

        if result["attacker_allies"]:
            names = [self.world.factions.get(f, type('', (), {'name': f})()).name
                     for f in result["attacker_allies"]]
            allies_text += f"{'、'.join(names)}出兵助战{atk_name}；"

        if result["defender_allies"]:
            names = [self.world.factions.get(f, type('', (), {'name': f})()).name
                     for f in result["defender_allies"]]
            allies_text += f"{'、'.join(names)}出兵助战{dff_name}；"

        if result["backstabbers"]:
            names = [self.world.factions.get(f, type('', (), {'name': f})()).name
                     for f in result["backstabbers"]]
            backstab_text = f"{'、'.join(names)}趁乱偷袭！"

        narrative = f"{atk_name}向{dff_name}宣战！"
        if allies_text:
            narrative += f" {allies_text}"
        if backstab_text:
            narrative += f" 然而{backstab_text}"
        if result["neutrals"]:
            narrative += f" 其余势力观望。"

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "war_declaration",
            "severity": "critical",
            "attacker": ctx.attacker_faction,
            "defender": ctx.defender_faction,
            "war_id": ctx.war_id,
            "diplomacy_stances": {k: v["action"] for k, v in result["stance_details"].items()},
            "narrative": narrative,
        })
        logger.info(f"[外交AI] {narrative}")

    # ================================================================
    # ② 敌方军事AI - 防守方反制战术生成
    # ================================================================

    async def _run_military_counter_ai(self, ctx: WarfareContext) -> dict:
        """敌方割据势力AI：生成反制战术"""
        dff = self.world.factions.get(ctx.defender_faction)
        atk = self.world.factions.get(ctx.attacker_faction)
        if not dff or not atk:
            return {"status": "inactive"}

        result = {
            "status": "active",
            "counter_strategies": [],
            "mobilized_troops": 0,
            "supply_line_actions": [],
            "defense_actions": [],
        }

        # 分析攻方行军路线（前线地块）
        attacker_border = self._get_border_tiles(ctx.attacker_faction)
        defender_border = self._get_frontline_tiles(ctx.defender_faction, ctx.attacker_faction)

        # 策略1: 抽调守军编组反击军团
        total_mobilized = 0
        for tile in self.world.get_faction_tiles(ctx.defender_faction):
            if tile.tile_id in defender_border:
                continue  # 前线不动
            if tile.troops > 500:
                # 从后方抽调30%到前线
                mobilize = int(tile.troops * 0.3)
                if mobilize > 200:
                    # 找到最近的前线地块
                    closest_front = self._find_closest_tile(
                        tile, defender_border, self.world)
                    if closest_front and closest_front.tile_id != tile.tile_id:
                        tile.troops -= mobilize
                        closest_front.troops += mobilize
                        total_mobilized += mobilize
                        logger.debug(f"[军事AI] {ctx.defender_faction} 抽调{mobilize}人 "
                                     f"从{tile.tile_name}→{closest_front.tile_name}")

        result["mobilized_troops"] = total_mobilized

        # 策略2: 截粮/绕后（基于攻方补给线薄弱点）
        atk_supply_lines = self._analyze_supply_lines(ctx.attacker_faction, attacker_border)
        for weak_point in atk_supply_lines[:3]:  # 最多3个截粮点
            if random.random() < 0.4:  # 40%概率采取行动
                # 派遣小队袭扰
                raid_troops = min(300, int(dff.total_troops * 0.05))
                result["supply_line_actions"].append({
                    "type": "supply_raid",
                    "target": weak_point["tile_id"],
                    "tile_name": weak_point["tile_name"],
                    "troops": raid_troops,
                    "narrative": f"{dff.name}派{raid_troops}人袭扰{weak_point['tile_name']}补给线",
                })

        # 策略3: 固守关隘/城池
        for tile_id in defender_border[:5]:
            tile = self.world.get_tile(tile_id)
            if tile and tile.tile_type.value in ("pass", "city", "mountain"):
                # 加固防御姿态
                result["defense_actions"].append({
                    "type": "fortify",
                    "tile_id": tile_id,
                    "tile_name": tile.tile_name,
                    "narrative": f"{dff.name}加强{tile.tile_name}防御，固守待援",
                })

        # 写入事件日志
        if result["mobilized_troops"] > 0:
            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "military_counter",
                "faction_id": ctx.defender_faction,
                "narrative": (f"{dff.name}紧急抽调{total_mobilized}兵力驰援前线，"
                              f"同时派出游击小队截断敌军补给线。"),
            })

        logger.info(f"[军事AI] {dff.name} 动员{total_mobilized}人，"
                     f"截粮{len(result['supply_line_actions'])}次，"
                     f"固守{len(result['defense_actions'])}处")
        return result

    def _get_border_tiles(self, faction_id: str) -> list:
        """获取势力边境地块"""
        own_tiles = {t.tile_id for t in self.world.get_faction_tiles(faction_id)}
        border = []
        for tid in own_tiles:
            for nb_id in self._get_neighbor_ids(tid):
                if nb_id not in own_tiles:
                    border.append(tid)
                    break
        return list(set(border))

    def _get_frontline_tiles(self, faction_id: str, enemy_id: str) -> list:
        """获取面对特定敌人的前线地块"""
        own = set(t.tile_id for t in self.world.get_faction_tiles(faction_id))
        enemy = set(t.tile_id for t in self.world.get_faction_tiles(enemy_id))
        frontline = []
        for tid in own:
            for nb_id in self._get_neighbor_ids(tid):
                if nb_id in enemy:
                    frontline.append(tid)
                    break
        return list(set(frontline))

    def _analyze_supply_lines(self, faction_id: str, border_tiles: list) -> list:
        """分析补给线薄弱点：离首都远、粮草少、兵力少的前线地块"""
        faction = self.world.get_faction(faction_id)
        capital_id = faction.capital_tile if faction else ""

        weak_points = []
        for tid in border_tiles:
            tile = self.world.get_tile(tid)
            if not tile:
                continue

            weakness = 0
            # 兵力少
            if tile.troops < 300:
                weakness += 3
            elif tile.troops < 800:
                weakness += 1
            # 粮草少
            if tile.grain < 200:
                weakness += 2
            # 离首都远（简化：tile_id 距离）
            if capital_id and tid != capital_id:
                weakness += 1

            if weakness >= 3:
                weak_points.append({
                    "tile_id": tid,
                    "tile_name": tile.tile_name,
                    "weakness": weakness,
                    "troops": tile.troops,
                    "grain": tile.grain,
                })

        return sorted(weak_points, key=lambda x: x["weakness"], reverse=True)

    @staticmethod
    def _find_closest_tile(source_tile, target_ids: list, world):
        """找到离source最近的目标地块"""
        best = None
        best_dist = 999
        for tid in target_ids:
            t = world.get_tile(tid)
            if not t:
                continue
            dist = abs(source_tile.col - t.col) + abs(source_tile.row - t.row)
            if dist < best_dist:
                best_dist = dist
                best = t
        return best

    # ================================================================
    # ③ 民生治理AI - 战时内政调整
    # ================================================================

    async def _run_civil_adjustment_ai(self, ctx: WarfareContext) -> dict:
        """交战双方自动调整征兵比例、粮草囤积、民心维稳"""
        result = {"attacker_adjustments": {}, "defender_adjustments": {}}

        for fid, label in [(ctx.attacker_faction, "attacker"),
                           (ctx.defender_faction, "defender")]:
            faction = self.world.factions.get(fid)
            if not faction:
                continue

            adjustments = self._adjust_faction_war_economy(faction, label)
            result[f"{label}_adjustments"] = adjustments

        return result

    def _adjust_faction_war_economy(self, faction, role: str) -> dict:
        """调整单个势力的战时经济"""
        fid = faction.faction_id
        adjustments = {
            "recruit_boost": 0,
            "grain_stockpile": 0,
            "morale_impact": 0,
            "tax_adjustment": 0,
        }

        # 征兵比例提升（战时 +30% 可征兵人口上限）
        adjustments["recruit_boost"] = 30

        # 粮草囤积加成（战时消耗增加，需要更多储备）
        adjustments["grain_stockpile"] = 15  # 囤积效率+15%

        # 民心影响：攻方-3（远征厌战），守方-2（但保家卫国+1，净-1）
        if role == "attacker":
            adjustments["morale_impact"] = -3
        else:
            adjustments["morale_impact"] = -1

        # 税赋调整：战时加税
        adjustments["tax_adjustment"] = 10  # 税率临时+10%

        # 军械消耗加速
        adjustments["arms_consumption"] = 1.5  # 1.5倍消耗

        # 对有战马储备的势力，骑兵动员
        if getattr(faction, 'horses', 0) > 100:
            adjustments["cavalry_mobilized"] = min(
                int(faction.horses * 0.3), 500)

        # 写入势力状态
        if not hasattr(faction, 'war_economy'):
            faction.war_economy = {}
        faction.war_economy = adjustments

        logger.info(f"[民生AI] {faction.name}({role}) 战时调整: "
                     f"征兵+{adjustments['recruit_boost']}%, "
                     f"民心{adjustments['morale_impact']}, "
                     f"税赋+{adjustments['tax_adjustment']}%")

        return adjustments

    # ================================================================
    # ④ 叛乱灾害AI - 战乱地块动乱评估
    # ================================================================

    def _run_rebellion_risk_ai(self, ctx: WarfareContext) -> list:
        """分析交战双方地块的叛乱风险并触发叛乱"""
        risks = []

        for fid in [ctx.attacker_faction, ctx.defender_faction]:
            faction = self.world.factions.get(fid)
            if not faction or not faction.is_alive:
                continue

            for tile in self.world.get_faction_tiles(fid):
                risk = self._calc_tile_rebellion_risk(tile, faction, ctx)
                if risk["risk_level"] >= "high":
                    risks.append(risk)

                    # 高概率触发叛乱
                    trigger_chance = {
                        "low": 0.02,
                        "medium": 0.08,
                        "high": 0.18,
                        "critical": 0.35,
                    }.get(risk["risk_level"], 0.02)

                    if random.random() < trigger_chance:
                        self._trigger_war_rebellion(tile, faction, risk, ctx)

        return risks

    def _calc_tile_rebellion_risk(self, tile, faction, ctx: WarfareContext) -> dict:
        """计算单个地块的战时叛乱风险

        因子：
        - 地块是否为前线（+20）
        - 民心低于30（+25）
        - 粮草低于100（+15）
        - 驻军被抽调（+10）
        - 人口>5000（+5，人多难管）
        - 长期战争（超过6回合+20）
        """
        risk = 0
        factors = []

        # 前线地块
        border_tiles = self._get_border_tiles(faction.faction_id)
        if tile.tile_id in border_tiles:
            risk += 20
            factors.append("前线战乱")

        # 民心低
        if tile.morale < 30:
            risk += 25
            factors.append(f"民心涣散({tile.morale})")
        elif tile.morale < 50:
            risk += 10
            factors.append(f"民心不稳({tile.morale})")

        # 粮草匮乏
        if tile.grain < 100:
            risk += 15
            factors.append(f"粮草告罄({tile.grain})")

        # 驻军薄弱
        if tile.troops < 200:
            risk += 10
            factors.append(f"守军空虚({tile.troops})")

        # 人口众多
        if tile.population > 5000:
            risk += 5
            factors.append("人口膨胀")

        # 战争持续回合（已在交战round数超过6）
        war_duration = self.world.current_round - ctx.declared_round
        if war_duration > 6:
            risk += 20
            factors.append(f"久战疲弊({war_duration}回合)")

        if risk >= 50:
            level = "critical"
        elif risk >= 35:
            level = "high"
        elif risk >= 20:
            level = "medium"
        else:
            level = "low"

        return {
            "tile_id": tile.tile_id,
            "tile_name": tile.tile_name,
            "faction_id": faction.faction_id,
            "risk_score": risk,
            "risk_level": level,
            "factors": factors,
        }

    def _trigger_war_rebellion(self, tile, faction, risk: dict, ctx: WarfareContext):
        """在战时触发叛乱"""
        from server.core.advanced_features import RebelEngine
        rebel_engine = RebelEngine(self.world, self.const)

        cause = random.choice([
            f"久战生厌，{tile.tile_name}民变",
            f"粮饷不济，{tile.tile_name}哗变",
            f"徭役过重，{tile.tile_name}民揭竿而起",
            f"前线溃败消息传来，{tile.tile_name}大乱",
        ])

        result = rebel_engine.spawn_rebellion(
            faction_id=faction.faction_id,
            tile_id=tile.tile_id,
            troops=max(300, int(tile.population * 0.12)),
            cause=cause,
        )

        if result:
            logger.warning(f"[叛乱AI] 战时叛乱! {tile.tile_name}({faction.name}): "
                           f"risk={risk['risk_level']}, cause={cause}")
            ctx.rebellion_risks.append({
                **risk,
                "triggered": True,
                "rebel_id": result.get("rebel_id"),
            })

    # ================================================================
    # ⑤ 军事结算AI - 战损计算/军团溃散/领地易主
    # ================================================================

    async def _run_battle_settlement_ai(self, ctx: WarfareContext) -> list:
        """回合结算时完成双方战损计算、军团溃散回撤、领地易主判定"""
        settlements = []

        atk = self.world.factions.get(ctx.attacker_faction)
        dff = self.world.factions.get(ctx.defender_faction)
        if not atk or not dff or not atk.is_alive or not dff.is_alive:
            return settlements

        # 获取前线对峙地块
        frontline = self._get_frontline_tiles(ctx.attacker_faction, ctx.defender_faction)
        dff_frontline = self._get_frontline_tiles(ctx.defender_faction, ctx.attacker_faction)

        # 对每个前线地块进行AI驱动的战斗推演
        # 攻方前线 + 守方前线，取交叉对峙
        for atk_tid in frontline[:5]:  # 最多5处战场
            atk_tile = self.world.get_tile(atk_tid)
            if not atk_tile or atk_tile.troops < 100:
                continue

            # 找到邻接的守方地块
            for nb_id in self._get_neighbor_ids(atk_tid):
                dff_tile = self.world.get_tile(nb_id)
                if not dff_tile or dff_tile.faction_id != ctx.defender_faction:
                    continue
                if dff_tile.troops < 50:
                    continue

                # 模拟战斗
                battle = self._simulate_battle(
                    atk_tile, dff_tile, atk, dff, ctx)
                settlements.append(battle)

        # 处理溃散回撤
        for settlement in settlements:
            if settlement.get("routed"):
                routed_faction = settlement["routed_faction"]
                routed_tile_id = settlement["routed_tile"]
                routed_tile = self.world.get_tile(routed_tile_id)
                if routed_tile:
                    # 残兵撤向最近的安全地块
                    safe_tiles = [
                        t for t in self.world.get_faction_tiles(routed_faction)
                        if t.tile_id != routed_tile_id and t.troops < 5000
                    ]
                    if safe_tiles:
                        safe = min(safe_tiles,
                                   key=lambda t: abs(t.col - routed_tile.col) +
                                                 abs(t.row - routed_tile.row))
                        safe.troops += settlement["survivors"]

        return settlements

    def _simulate_battle(self, atk_tile, dff_tile, atk, dff,
                         ctx: WarfareContext) -> dict:
        """模拟单场战斗并应用结果"""
        # 地形加成
        terrain_atk = {
            "mountain": 0.7, "pass": 0.6, "city": 0.8,
            "water": 0.5, "desert": 0.8, "grassland": 1.1,
            "farmland": 1.0, "coast": 1.0, "port": 0.9,
        }.get(dff_tile.tile_type.value if hasattr(dff_tile.tile_type, 'value')
              else str(dff_tile.tile_type), 1.0)

        terrain_dff = {
            "mountain": 1.4, "pass": 1.6, "city": 1.5,
            "water": 1.2, "desert": 1.1, "grassland": 0.9,
            "farmland": 0.9, "coast": 1.0, "port": 1.1,
        }.get(dff_tile.tile_type.value if hasattr(dff_tile.tile_type, 'value')
              else str(dff_tile.tile_type), 1.0)

        # 城防加成
        fort_bonus = 1.0 + dff_tile.fortification * 0.1

        # 季节修正
        from server.models.world_state import Season
        season_mult = 1.0
        if self.world.current_season == Season.WINTER:
            season_mult = 0.85  # 冬季攻城困难
        elif self.world.current_season == Season.AUTUMN:
            season_mult = 1.1   # 秋高马肥利于征战

        # 计算战力
        atk_power = (atk_tile.troops * terrain_atk * season_mult *
                     (0.7 + random.random() * 0.6))
        dff_power = (dff_tile.troops * terrain_dff * fort_bonus *
                     (0.7 + random.random() * 0.6))

        # 战损计算
        atk_loss_rate = random.uniform(0.08, 0.25)
        dff_loss_rate = random.uniform(0.06, 0.22)

        if atk_power > dff_power * 1.2:
            atk_loss_rate *= 0.7
            dff_loss_rate *= 1.3
            winner = ctx.attacker_faction
        elif dff_power > atk_power * 1.2:
            atk_loss_rate *= 1.3
            dff_loss_rate *= 0.7
            winner = ctx.defender_faction
        else:
            winner = None  # 僵持

        atk_loss = int(atk_tile.troops * atk_loss_rate)
        dff_loss = int(dff_tile.troops * dff_loss_rate)
        atk_remaining = atk_tile.troops - atk_loss
        dff_remaining = dff_tile.troops - dff_loss

        # 应用战损
        atk_tile.troops = max(0, atk_remaining)
        dff_tile.troops = max(0, dff_remaining)

        result = {
            "attacker_tile": atk_tile.tile_id,
            "attacker_tile_name": atk_tile.tile_name,
            "defender_tile": dff_tile.tile_id,
            "defender_tile_name": dff_tile.tile_name,
            "atk_losses": atk_loss,
            "dff_losses": dff_loss,
            "winner": winner,
            "routed": False,
        }

        # 溃散判定
        if winner == ctx.attacker_faction and dff_remaining < 50:
            # 守方溃散，攻方占领
            old_faction = dff_tile.faction_id
            dff_tile.faction_id = ctx.attacker_faction
            dff_tile.troops = atk_remaining

            result["tile_captured"] = True
            result["captured_tile"] = dff_tile.tile_id
            result["captured_tile_name"] = dff_tile.tile_name
            result["old_faction"] = old_faction
            ctx.territory_changes.append(result)

            # 声望变化
            if atk:
                atk.reputation = min(100, atk.reputation + 1)
            if dff:
                dff.reputation = max(0, dff.reputation - 2)

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "battle_victory",
                "severity": "major",
                "attacker": ctx.attacker_faction,
                "defender": ctx.defender_faction,
                "tile_id": dff_tile.tile_id,
                "tile_name": dff_tile.tile_name,
                "narrative": (
                    f"{atk.name if atk else ctx.attacker_faction}攻占"
                    f"{dff_tile.tile_name}！"
                    f"斩敌{dff_loss}，自身损失{atk_loss}。"
                ),
            })

        elif winner == ctx.defender_faction and atk_remaining < 100:
            result["routed"] = True
            result["routed_faction"] = ctx.attacker_faction
            result["routed_tile"] = atk_tile.tile_id
            result["survivors"] = max(0, atk_remaining)
            atk_tile.troops = 0  # 清空溃散地块

        return result

    # ================================================================
    # ⑥ 疆域AI - 势力地图色块/法理归属/迷雾探索
    # ================================================================

    def _run_territory_ai(self, ctx: WarfareContext) -> list:
        """实时刷新势力地图色块、法理归属与迷雾探索状态"""
        changes = ctx.territory_changes  # 从战斗结算中继承

        for change in changes:
            if not change.get("tile_captured"):
                continue

            tile_id = change.get("captured_tile")
            tile = self.world.get_tile(tile_id)
            if not tile:
                continue

            # 迷雾刷新：攻占方自动获得该地块及周边1格视野
            new_faction_id = tile.faction_id
            self._update_vision(new_faction_id, tile_id, radius=1)

        return changes

    def _update_vision(self, faction_id: str, center_tile_id: str, radius: int = 1):
        """更新势力地图视野"""
        center = self.world.get_tile(center_tile_id)
        if not center:
            return

        # 遍历radius范围内的地块
        for tid, tile in self.world.tiles.items():
            dist = max(abs(tile.col - center.col), abs(tile.row - center.row))
            if dist <= radius:
                # 使用 fog_of_war 的视野机制
                if not hasattr(tile, 'explored_by'):
                    tile.explored_by = set()
                if hasattr(tile, 'explored_by') and isinstance(tile.explored_by, set):
                    tile.explored_by.add(faction_id)

    # ================================================================
    # ⑦ 谋略AI - 离间/刺杀/流言等计策
    # ================================================================

    async def _run_stratagem_ai(self, ctx: WarfareContext) -> list:
        """为交战双方谋士生成计策行为"""
        actions = []

        for fid, target_fid in [(ctx.attacker_faction, ctx.defender_faction),
                                 (ctx.defender_faction, ctx.attacker_faction)]:
            faction = self.world.factions.get(fid)
            target = self.world.factions.get(target_fid)
            if not faction or not target or not target.is_alive:
                continue

            # 可用计策库
            available_stratagems = [
                self._try_sow_discord,
                self._try_assassinate,
                self._try_spread_rumor,
                self._try_bribe_officials,
                self._try_sabotage_supply,
            ]

            # 随机选取1-2个计策尝试
            chosen = random.sample(available_stratagems,
                                   k=min(2, len(available_stratagems)))
            for stratagem_fn in chosen:
                action = stratagem_fn(faction, target, ctx)
                if action:
                    actions.append(action)

        # 如果有AI客户端，调用LLM生成叙事
        if actions and self.llm_clients:
            await self._generate_stratagem_narratives(actions, ctx)

        return actions

    def _try_sow_discord(self, faction, target, ctx: WarfareContext) -> dict:
        """离间计：降低目标朝堂稳定度"""
        if random.random() < 0.25:
            impact = random.randint(5, 15)
            target.court_stability = max(0, target.court_stability - impact)
            return {
                "type": "sow_discord",
                "source": faction.faction_id,
                "source_name": faction.name,
                "target": target.faction_id,
                "target_name": target.name,
                "effect": f"朝堂稳定度-{impact}",
                "narrative": f"{faction.name}谋士暗中离间{target.name}朝臣，朝堂动荡。",
            }
        return None

    def _try_assassinate(self, faction, target, ctx: WarfareContext) -> dict:
        """刺杀主帅：有概率击杀目标势力官员"""
        if random.random() < 0.12:
            officials = getattr(target, 'officials', [])
            if officials:
                victim = random.choice(officials)
                # 移除官员（简化：从列表中移除）
                if victim in officials:
                    officials.remove(victim)
                    target.officials = officials
                return {
                    "type": "assassination",
                    "source": faction.faction_id,
                    "source_name": faction.name,
                    "target": target.faction_id,
                    "target_name": target.name,
                    "victim": victim,
                    "narrative": (
                        f"{faction.name}派刺客暗杀了{target.name}的{victim}！"
                        f"朝野震惊。"
                    ),
                }
        return None

    def _try_spread_rumor(self, faction, target, ctx: WarfareContext) -> dict:
        """散布流言：降低目标势力民心和部队士气"""
        if random.random() < 0.35:
            # 影响所有前线地块士气
            morale_loss = random.randint(3, 10)
            for tile in self.world.get_faction_tiles(target.faction_id):
                if tile.tile_id in self._get_border_tiles(target.faction_id):
                    tile.morale = max(0, tile.morale - morale_loss // 2)

            target.realm_stability = max(0, target.realm_stability -
                                         random.randint(3, 8))

            return {
                "type": "spread_rumor",
                "source": faction.faction_id,
                "source_name": faction.name,
                "target": target.faction_id,
                "target_name": target.name,
                "effect": f"前线民心-{morale_loss//2}",
                "narrative": (
                    f"{faction.name}散布流言：「{target.name}气数已尽！」"
                    f"前线军心浮动。"
                ),
            }
        return None

    def _try_bribe_officials(self, faction, target, ctx: WarfareContext) -> dict:
        """贿赂官员：降低目标势力忠诚度"""
        if random.random() < 0.2:
            loyalties = getattr(target, 'faction_loyalties', {})
            if loyalties:
                # 降低一个派系忠诚度
                worst_faction = min(loyalties, key=loyalties.get, default=None)
                if worst_faction:
                    loyalties[worst_faction] = max(0, loyalties[worst_faction] - 15)
                    return {
                        "type": "bribe_officials",
                        "source": faction.faction_id,
                        "source_name": faction.name,
                        "target": target.faction_id,
                        "target_name": target.name,
                        "effect": f"{worst_faction}忠诚度-15",
                        "narrative": (
                            f"{faction.name}重金贿赂{target.name}的{worst_faction}，"
                            f"朝中离心离德。"
                        ),
                    }
        return None

    def _try_sabotage_supply(self, faction, target, ctx: WarfareContext) -> dict:
        """破坏粮草：烧毁目标势力粮仓"""
        if random.random() < 0.18:
            grain_loss = random.randint(300, 1000)
            target.grain = max(0, target.grain - grain_loss)
            return {
                "type": "sabotage_supply",
                "source": faction.faction_id,
                "source_name": faction.name,
                "target": target.faction_id,
                "target_name": target.name,
                "effect": f"粮草-{grain_loss}",
                "narrative": (
                    f"{faction.name}细作潜入{target.name}粮仓纵火！"
                    f"烧毁粮草{grain_loss}石。"
                ),
            }
        return None

    async def _generate_stratagem_narratives(self, actions: list, ctx: WarfareContext):
        """使用LLM生成谋略行为的历史叙事（可选增强）"""
        if not self.llm_clients.get("enemy"):
            return

        try:
            client = self.llm_clients["enemy"]
            actions_text = "\n".join(
                f"- {a.get('narrative', '')}" for a in actions
            )
            prompt = (
                f"以下是{self.world.current_year}年{self.world.current_month}月"
                f"战争中发生的谋略事件：\n{actions_text}\n\n"
                f"请以史官口吻，为这些事件撰写一段简短的史学评述（50字内）。"
            )

            from ..infra.llm_client.hunyuan_client import TencentHunyuanClient
            if isinstance(client, TencentHunyuanClient):
                response = await client.chat_fast(prompt=prompt, temperature=0.7)
                narrative = (response[:200] if response else "")

                self.world.events_log.append({
                    "round": self.world.current_round,
                    "event_type": "stratagem_roundup",
                    "narrative": narrative or "谋略暗流涌动，各方势力暗中较劲。",
                    "stratagems": [
                        {"type": a["type"], "source": a.get("source_name", ""),
                         "target": a.get("target_name", "")} for a in actions
                    ],
                })
        except Exception as e:
            logger.debug(f"[谋略AI] LLM叙事生成失败: {e}")

    # ================================================================
    # 辅助方法
    # ================================================================

    def _ensure_engines(self):
        """确保子引擎已初始化"""
        pass  # 子模块均为懒加载

    @property
    def active_wars(self) -> dict:
        return self._active_wars

    def get_war_context(self, attacker: str, defender: str) -> Optional[WarfareContext]:
        """获取活跃战争上下文"""
        for ctx in self._active_wars.values():
            if (ctx.attacker_faction == attacker and
                ctx.defender_faction == defender):
                return ctx
        return None

    def get_war_context_by_id(self, war_id: str) -> Optional[WarfareContext]:
        """通过 war_id 获取战争上下文"""
        return self._active_wars.get(war_id)

    def record_war_score_event(
        self, attacker: str, defender: str,
        source: str, base_value: float,
        round_num: int, description: str,
        tile_id: str = None, troops: int = None,
    ):
        """记录战争分数变化事件（由 MarchEngine 战斗结算触发）"""
        from server.war.war_score import WarScoreSource
        ctx = self.get_war_context(attacker, defender)
        if not ctx:
            return
        try:
            ws = ctx.get_war_score()
            ws.record_event(
                source=WarScoreSource(source),
                base_value=base_value,
                round_num=round_num,
                description=description,
                tile_id=tile_id,
                troops_involved=troops,
            )
        except (ValueError, KeyError) as e:
            logger.debug(f"[WarScore] 无效事件来源: {source}, err={e}")

    def tick_all_war_scores(self, round_num: int):
        """每回合结束时，为所有活跃战争推进战争分数"""
        for ctx in self._active_wars.values():
            ws = ctx.get_war_score()
            # 统计进攻方控制了目标地块的数量
            held_count = 0
            for tid in ctx.war_goal_tiles:
                tile = self.world.tiles.get(tid) if hasattr(self.world, 'tiles') else None
                if tile and tile.faction_id == ctx.attacker_faction:
                    held_count += 1
            ws.tick(round_num, held_count)

    def get_all_active_wars_summary(self) -> list[dict]:
        """获取所有活跃战争摘要（供前端 WarPanel 使用）"""
        summaries = []
        for ctx in self._active_wars.values():
            ws = ctx.get_war_score()
            atk = self.world.factions.get(ctx.attacker_faction)
            dff = self.world.factions.get(ctx.defender_faction)
            if not atk or not dff:
                continue
            summaries.append({
                "war_id": ctx.war_id,
                "attacker_id": ctx.attacker_faction,
                "attacker_name": atk.name,
                "defender_id": ctx.defender_faction,
                "defender_name": dff.name,
                "casus_belli": ctx.casus_belli,
                "casus_belli_name": ctx.casus_belli_name,
                "declared_round": ctx.declared_round,
                "stage": ctx.stage.value,
                "war_score": ws.get_status(),
                "allies": {
                    "attacker": ctx.attacker_allies,
                    "defender": ctx.defender_allies,
                },
                "territory_changes": ctx.territory_changes[-5:] if ctx.territory_changes else [],
            })
        return summaries

    def end_war(self, attacker: str, defender: str):
        """结束战争，从活跃列表中移除"""
        for war_id, ctx in list(self._active_wars.items()):
            if ctx.attacker_faction == attacker and ctx.defender_faction == defender:
                del self._active_wars[war_id]
                logger.info(f"[征伐编排] 战争结束: {war_id}")
                return True
        return False

    def end_war(self, ctx: WarfareContext, outcome: str = "ongoing"):
        """结束一场征伐"""
        ctx.stage = WarfareStage.AFTERMATH
        logger.info(f"[征伐编排] 战争结束: {ctx.war_id}, outcome={outcome}")
