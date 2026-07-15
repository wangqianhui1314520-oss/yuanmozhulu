"""
和平谈判引擎 · 对标 CK3

职责：
1. 根据战争分数动态生成可选的和平条款
2. 各项条款消耗战争分数点
3. AI 评估是否接受谈判条件
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import logging
import random

if TYPE_CHECKING:
    from server.models.world_state import DiplomaticStance

logger = logging.getLogger("yuanmo.war.peace")


class PeaceTerm(Enum):
    """和平条款类型"""
    WHITE_PEACE = "white_peace"             # 白和平（恢复战前状态）
    WAR_REPARATIONS = "war_reparations"     # 战争赔款
    CEDE_TILE = "cede_tile"                 # 割让单个地块
    CEDE_MULTIPLE_TILES = "cede_multiple"   # 割让多个地块
    PAY_TRIBUTE = "pay_tribute"             # 成为纳贡国
    BECOME_VASSAL = "become_vassal"         # 成为附庸
    RENOUNCE_CLAIMS = "renounce_claims"     # 放弃宣称
    HUMILIATE = "humiliate"                 # 羞辱（声望惩罚）
    RELEASE_PRISONERS = "release_prisoners" # 释放俘虏
    TRANSFER_TRADE = "transfer_trade"       # 强制开放贸易


# 和平条款配置
PEACE_TERM_CONFIG: dict[PeaceTerm, dict] = {
    PeaceTerm.WHITE_PEACE: {
        "name": "白和平",
        "description": "双方停战，恢复战前边界。",
        "war_score_cost": 0,                # 0 表示双方都可用
        "requires_advantage": False,
        "min_war_score": -100,              # 任何分数都可以
        "for_attacker": True,
        "for_defender": True,
    },
    PeaceTerm.WAR_REPARATIONS: {
        "name": "战争赔款",
        "description": "败方支付银两作为赔偿。",
        "war_score_cost": 30,
        "min_war_score": 30,
        "requires_advantage": True,
        "for_attacker": True,               # 只有优势方可要求
        "for_defender": True,               # 防守方优势也可要求
        "reparations_amount": 2000,         # 赔款基准金额
    },
    PeaceTerm.CEDE_TILE: {
        "name": "割让一地",
        "description": "败方割让一个指定地块。",
        "war_score_cost": 40,
        "min_war_score": 40,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
    },
    PeaceTerm.CEDE_MULTIPLE_TILES: {
        "name": "割让多地",
        "description": "败方割让多个指定地块。",
        "war_score_cost": 70,
        "min_war_score": 70,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
        "max_tiles": 3,
    },
    PeaceTerm.PAY_TRIBUTE: {
        "name": "缴纳岁贡",
        "description": "败方成为纳贡国，每回合缴纳岁贡。",
        "war_score_cost": 60,
        "min_war_score": 60,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": False,
        "tribute_amount": 300,
    },
    PeaceTerm.BECOME_VASSAL: {
        "name": "称臣附庸",
        "description": "败方成为胜方的附庸国。",
        "war_score_cost": 90,
        "min_war_score": 90,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": False,
    },
    PeaceTerm.RENOUNCE_CLAIMS: {
        "name": "放弃宣称",
        "description": "败方放弃对争议地块的法理宣称。",
        "war_score_cost": 25,
        "min_war_score": 25,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
    },
    PeaceTerm.HUMILIATE: {
        "name": "羞辱对方",
        "description": "胜方公开羞辱败方，严重打击对方声望。",
        "war_score_cost": 20,
        "min_war_score": 20,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
        "humiliation_prestige_penalty": 20,
    },
    PeaceTerm.RELEASE_PRISONERS: {
        "name": "释放俘虏",
        "description": "败方释放在押的我方将领。",
        "war_score_cost": 15,
        "min_war_score": 15,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
    },
    PeaceTerm.TRANSFER_TRADE: {
        "name": "开放贸易",
        "description": "强制对方开放贸易路线。",
        "war_score_cost": 20,
        "min_war_score": 20,
        "requires_advantage": True,
        "for_attacker": True,
        "for_defender": True,
    },
}


@dataclass
class PeaceProposal:
    """和平提议"""
    is_from_attacker: bool                  # 提议方是否是进攻方
    terms: list[PeaceTerm]                  # 条款列表
    total_cost: float                       # 总分消耗
    tile_ids: list[str] = field(default_factory=list)  # 涉及地块
    reparation_amount: int = 0              # 赔款金额
    description: str = ""                   # 人类可读描述


class PeaceNegotiationEngine:
    """
    和平谈判引擎

    用法:
      engine = PeaceNegotiationEngine(world_state)
      # 获取可用条款
      terms = engine.get_available_terms(war_score, is_attacker=True, can_seize=True)
      # AI 评估
      accepted = engine.evaluate_proposal(proposal, war_score.get_status(), defender_faction)
      # 执行和平
      result = engine.execute_peace(proposal, attacker_id, defender_id)
    """

    def __init__(self, world_state):
        self.world = world_state

    def get_available_terms(
        self,
        war_score_tracker,
        can_seize_territory: bool = True,
        can_demand_tribute: bool = False,
        can_enforce_vassal: bool = False,
    ) -> dict:
        """
        获取当前战争分数下可选条款

        返回: { "for_attacker": [...], "for_defender": [...] }
        """
        status = war_score_tracker.get_status()
        score = status["war_score"]

        result = {"for_attacker": [], "for_defender": []}

        for term, cfg in PEACE_TERM_CONFIG.items():
            # 进攻方条款
            if cfg["for_attacker"] and score >= cfg["min_war_score"] and abs(score) >= cfg["war_score_cost"]:
                # 特殊过滤
                if term == PeaceTerm.CEDE_TILE and not can_seize_territory:
                    continue
                if term == PeaceTerm.CEDE_MULTIPLE_TILES and not can_seize_territory:
                    continue
                if term == PeaceTerm.PAY_TRIBUTE and not can_demand_tribute:
                    continue
                if term == PeaceTerm.BECOME_VASSAL and not can_enforce_vassal:
                    continue

                result["for_attacker"].append({
                    "term": term.value,
                    "name": cfg["name"],
                    "description": cfg["description"],
                    "cost": cfg["war_score_cost"],
                })

            # 防守方条款（Bug #22修复: 添加war_score_cost检查，防止绕过）
            if cfg["for_defender"] and -score >= cfg["min_war_score"] and abs(score) >= cfg["war_score_cost"]:
                result["for_defender"].append({
                    "term": term.value,
                    "name": cfg["name"],
                    "description": cfg["description"],
                    "cost": cfg["war_score_cost"],
                })

        # 确保白和平始终可用
        if not any(t["term"] == "white_peace" for t in result["for_attacker"]):
            result["for_attacker"].insert(0, {
                "term": "white_peace",
                "name": "白和平",
                "description": "双方停战，恢复战前边界。",
                "cost": 0,
            })
        if not any(t["term"] == "white_peace" for t in result["for_defender"]):
            result["for_defender"].insert(0, {
                "term": "white_peace",
                "name": "白和平",
                "description": "双方停战，恢复战前边界。",
                "cost": 0,
            })

        return result

    def evaluate_acceptance(
        self,
        proposal: PeaceProposal,
        war_score_status: dict,
        offering_faction_id: str,
        receiving_faction_id: str,
    ) -> tuple[bool, str, int]:
        """
        评估对方是否接受和平提议

        返回: (accepted, reason, acceptance_score)

        acceptance_score:
          100+: 绝对接受
          50-99: 可能接受
          0-49: 可能拒绝
          <0: 绝对拒绝
        """
        score = war_score_status["war_score"]
        # Bug #22修复: 正确判断接收方是否是进攻方
        # proposal.is_from_attacker 是布尔值，receiving_faction_id 是字符串
        # 需要与attacker_faction_id/defender_faction_id比较
        receiving_is_attacker = (receiving_faction_id == war_score_status.get("attacker_faction_id", ""))
        receiving_perspective_score = -score if receiving_is_attacker else score

        # 基础接受度 = 对方视角的战争分数（分数越低越愿意接受）
        acceptance = 50  # 基础 50

        # 如果对方分数劣势，接受度提高
        if receiving_perspective_score < -75:
            acceptance += 40   # 快被打趴了
        elif receiving_perspective_score < -50:
            acceptance += 25   # 明显劣势
        elif receiving_perspective_score < -25:
            acceptance += 10   # 小劣势

        # 如果对方分数优势，接受度降低
        if receiving_perspective_score > 50:
            acceptance -= 30   # 明明优势，为什么接受
        elif receiving_perspective_score > 25:
            acceptance -= 15

        # 条款影响
        for term in proposal.terms:
            cfg = PEACE_TERM_CONFIG.get(term, {})
            cost = cfg.get("war_score_cost", 0)
            # 条款越苛刻，接受度越低
            if cost > 50:
                acceptance -= 20
            elif cost > 30:
                acceptance -= 10

            # 割地/附庸等苛刻条款
            if term in (PeaceTerm.CEDE_MULTIPLE_TILES, PeaceTerm.BECOME_VASSAL):
                acceptance -= 15
            if term == PeaceTerm.PAY_TRIBUTE:
                acceptance -= 10

        # 白和平特殊处理：如果非碾压局，接受度较高
        if proposal.terms == [PeaceTerm.WHITE_PEACE]:
            if abs(receiving_perspective_score) < 50:
                acceptance += 20  # 双方都累了，接受白和平

        # AI 性格修正（如果势力有 personality_tags）
        try:
            faction = self.world.factions.get(receiving_faction_id)
            if faction and hasattr(faction, 'personality_tags') and faction.personality_tags:
                tags = faction.personality_tags
                if isinstance(tags, str):
                    tags = [tags]
                if "倔强" in tags or "stubborn" in tags:
                    acceptance -= 15
                if "好战" in tags or "warlike" in tags:
                    acceptance -= 10
                if "谨慎" in tags or "cautious" in tags:
                    acceptance += 10
        except Exception as e:
            logger.debug(f"人格标签修正跳过: {e}")

        # 国力修正
        try:
            faction = self.world.factions.get(receiving_faction_id)
            if faction:
                troop_ratio = faction.total_troops / max(1, self.world.get_faction(offering_faction_id).total_troops if hasattr(self.world, 'get_faction') else 1)
                if troop_ratio < 0.3:
                    acceptance += 15  # 兵力悬殊
                elif troop_ratio > 1.5:
                    acceptance -= 15  # 我方更强
        except Exception as e:
            logger.debug(f"国力比率修正跳过: {e}")

        # 随机因素
        acceptance += random.randint(-10, 10)

        # 判定
        acceptance = max(-100, min(100, acceptance))
        if acceptance >= 50:
            return True, f"对方接受了和平提议（接受度：{acceptance}）", acceptance
        elif acceptance >= 25:
            return False, f"对方犹豫不决（接受度：{acceptance}）", acceptance
        else:
            return False, f"对方拒绝了和平提议（接受度：{acceptance}）", acceptance

    def execute_peace(
        self,
        proposal: PeaceProposal,
        attacker_faction_id: str,
        defender_faction_id: str,
    ) -> dict:
        """
        执行和平协议

        返回执行结果字典
        """
        from server.models.world_state import DiplomaticStance

        result = {
            "success": True,
            "message": "和平协议生效",
            "territory_changed": [],
            "reparations_paid": 0,
            "tribute_established": False,
            "vassal_established": False,
            "trade_established": False,
            "claims_renounced": [],
            "prisoners_released": [],
        }

        atk_faction = self.world.factions.get(attacker_faction_id)
        def_faction = self.world.factions.get(defender_faction_id)

        for term in proposal.terms:
            if term == PeaceTerm.WHITE_PEACE:
                # 停战并回复战前状态（这里简化为停战）
                self._set_peace(attacker_faction_id, defender_faction_id)
                result["message"] = "双方签订白和平，恢复战前状态。"

            elif term == PeaceTerm.WAR_REPARATIONS:
                amount = proposal.reparation_amount or PEACE_TERM_CONFIG[term].get("reparations_amount", 2000)
                # 根据 proposal.is_from_attacker 判断谁付钱
                if proposal.is_from_attacker:
                    payer, receiver = def_faction, atk_faction
                else:
                    payer, receiver = atk_faction, def_faction
                if payer and receiver:
                    amount = min(amount, payer.treasury)
                    payer.treasury -= amount
                    receiver.treasury += amount
                    result["reparations_paid"] = amount
                    result["message"] += f" {payer.name}赔付{receiver.name}{amount}两白银。"

            elif term == PeaceTerm.CEDE_TILE:
                tile_ids = proposal.tile_ids[:1] if proposal.tile_ids else []
                for tid in tile_ids:
                    self._transfer_tile(tid, proposal, attacker_faction_id, defender_faction_id, result)

            elif term == PeaceTerm.CEDE_MULTIPLE_TILES:
                for tid in proposal.tile_ids[:3]:
                    self._transfer_tile(tid, proposal, attacker_faction_id, defender_faction_id, result)

            elif term == PeaceTerm.PAY_TRIBUTE:
                self._set_tribute(attacker_faction_id, defender_faction_id, proposal.is_from_attacker)
                result["tribute_established"] = True
                result["message"] += " 败方成为纳贡国。"

            elif term == PeaceTerm.BECOME_VASSAL:
                self._set_vassal(attacker_faction_id, defender_faction_id, proposal.is_from_attacker)
                result["vassal_established"] = True
                result["message"] += " 败方成为附庸国。"

            elif term == PeaceTerm.TRANSFER_TRADE:
                self._set_trade(attacker_faction_id, defender_faction_id)
                result["trade_established"] = True
                result["message"] += " 双方建立贸易关系。"

            elif term == PeaceTerm.HUMILIATE:
                target = def_faction if proposal.is_from_attacker else atk_faction
                if target:
                    penalty = PEACE_TERM_CONFIG[term].get("humiliation_prestige_penalty", 20)
                    target.reputation = max(0, target.reputation - penalty)
                    result["message"] += f" {target.name}声望-{penalty}，颜面扫地。"

            elif term == PeaceTerm.RENOUNCE_CLAIMS:
                result["claims_renounced"] = proposal.tile_ids
                # TODO: 移除 claim_tiles 中的相关地块
                result["message"] += " 放弃相关领土宣称。"

            elif term == PeaceTerm.RELEASE_PRISONERS:
                result["prisoners_released"] = self._release_prisoners(
                    attacker_faction_id, defender_faction_id
                )
                result["message"] += f" 释放{len(result['prisoners_released'])}名俘虏。"

        # 最终：签订停战（所有和平协议都包含停战）
        self._set_peace(attacker_faction_id, defender_faction_id)

        logger.info(
            f"[Peace] {attacker_faction_id} vs {defender_faction_id}: "
            f"{result['message']}"
        )
        return result

    def _set_peace(self, faction_a: str, faction_b: str):
        """设置停战关系（Bug #22修复: 添加战争状态检查）"""
        from server.models.world_state import DiplomaticStance
        # 检查双方是否处于战争状态
        rel = self.world.relations.get(WorldState.relation_key(faction_a, faction_b))
        if not rel or rel.stance != DiplomaticStance.WAR:
            logger.debug(f"[Peace] {faction_a} vs {faction_b}: 双方未处于战争状态，跳过停战")
            return
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if rel:
            rel.stance = DiplomaticStance.TRUCE
            rel.attitude = 0
            rel.truce_rounds_remaining = 12  # 停战 12 回合

    def _transfer_tile(self, tile_id: str, proposal: PeaceProposal,
                       attacker: str, defender: str, result: dict):
        """转移地块归属"""
        tile = self.world.tiles.get(tile_id)
        if not tile:
            return
        if proposal.is_from_attacker:
            # 进攻方提议 → 防守方割给进攻方
            if tile.faction_id == defender:
                tile.faction_id = attacker
                result["territory_changed"].append({
                    "tile_id": tile_id,
                    "tile_name": tile.tile_name,
                    "from": defender,
                    "to": attacker,
                })
        else:
            # 防守方提议 → 进攻方退出
            if tile.faction_id == attacker:
                tile.faction_id = defender
                result["territory_changed"].append({
                    "tile_id": tile_id,
                    "tile_name": tile.tile_name,
                    "from": attacker,
                    "to": defender,
                })

    def _set_tribute(self, attacker: str, defender: str, is_from_attacker: bool):
        """设置朝贡关系"""
        key = self.world.relation_key(attacker, defender)
        rel = self.world.relations.get(key)
        if rel:
            from server.models.world_state import DiplomaticStance
            rel.stance = DiplomaticStance.TRUCE
            rel.attitude = -10 if is_from_attacker else 10
            # 纳贡标记
            if is_from_attacker:
                rel.tribute_payer = defender
                rel.tribute_amount = 300
            else:
                rel.tribute_payer = attacker
                rel.tribute_amount = 300

    def _set_vassal(self, attacker: str, defender: str, is_from_attacker: bool):
        """建立附庸关系"""
        key = self.world.relation_key(attacker, defender)
        rel = self.world.relations.get(key)
        if rel:
            from server.models.world_state import DiplomaticStance
            rel.stance = DiplomaticStance.ALLIANCE if hasattr(DiplomaticStance, 'ALLIANCE') else DiplomaticStance.TRUCE
            rel.attitude = -20 if is_from_attacker else 20
            # 附庸关系
            if is_from_attacker:
                from dataclasses import dataclass as dc
                @dc
                class _VS: pass
                vs = _VS()
                vs.suzerain = attacker
                vs.vassal = defender
                vs.type = "vassal"
                rel.vassal_suzerain = vs

    def _set_trade(self, faction_a: str, faction_b: str):
        """建立贸易关系"""
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if rel:
            rel.trade_active = True

    def _release_prisoners(self, attacker: str, defender: str) -> list[str]:
        """释放被俘将领"""
        released = []
        if hasattr(self.world, 'prisoners'):
            for prisoner in list(self.world.prisoners):
                if (prisoner.captor_faction == attacker and prisoner.original_faction == defender) or \
                   (prisoner.captor_faction == defender and prisoner.original_faction == attacker):
                    prisoner.freed = True
                    released.append(prisoner.name)
        return released

    def propose_peace(
        self,
        war_score_tracker,
        terms: list[str],
        is_from_attacker: bool,
        tile_ids: Optional[list[str]] = None,
        reparation_amount: int = 0,
    ) -> PeaceProposal:
        """构造和平提议（Bug #22修复: 添加分数校验）"""
        term_enums = [PeaceTerm(t) for t in terms]
        total_cost = sum(PEACE_TERM_CONFIG.get(t, {}).get("war_score_cost", 0) for t in term_enums)

        # Bug #22修复: 验证总消耗不超过可用分数
        status = war_score_tracker.get_status() if war_score_tracker else {"war_score": 0}
        available_score = abs(status.get("war_score", 0))
        if total_cost > available_score:
            logger.warning(f"[Peace] 提议总成本{total_cost}超过可用分数{available_score}，裁减至可用上限")
            # 移除最昂贵的条款直到满足预算
            while total_cost > available_score and term_enums:
                term_enums.pop()
                total_cost = sum(PEACE_TERM_CONFIG.get(t, {}).get("war_score_cost", 0) for t in term_enums)

        # 构建描述
        desc_parts = [PEACE_TERM_CONFIG.get(t, {}).get("name", t.value) for t in term_enums]
        description = "、".join(desc_parts) if desc_parts else "无条件和平"

        return PeaceProposal(
            is_from_attacker=is_from_attacker,
            terms=term_enums,
            total_cost=total_cost,
            tile_ids=tile_ids or [],
            reparation_amount=reparation_amount,
            description=description,
        )
