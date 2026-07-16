"""
A7 宗室府 - 继承顺位、宗室管理、皇储培养

模型分组: advisor (chat_role)
触发方式: 后端自动回合驱动（跳过玩家势力：仅保留皇子自然成长，无自主宫变决策）
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_event_bus import EventTypes, EventPriority, get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a7_royal")


class A7RoyalAgent(BaseAgent):
    """A7 宗室府 - 宗室皇储智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A7_{faction_id}",
            category=AgentCategory.A7_ROYAL,
            faction_id=faction_id,
            max_retries=2,
            retry_delay=1.5,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        宗室管理 - 继承顺位判定、皇子培养、宗室事务

        Args:
            world_snapshot: 含 faction_id, world_state, heirs (可选)
        """
        client: TencentHunyuanClient = clients["advisor"]
        faction_id = world_snapshot.get("faction_id", self.faction_id)
        world_state = world_snapshot.get("world_state", {})
        heirs = world_snapshot.get("heirs", [])

        faction = world_state.get("factions", {}).get(faction_id, {})
        ruler_name = faction.get("ruler_name", faction_id)
        ruler_age = faction.get("ruler_age", 40)

        # 构建宗室上下文
        heir_info = ""
        if heirs:
            for i, h in enumerate(heirs):
                heir_info += (
                    f"  {i+1}. {h.get('name','?')} "
                    f"(年龄{h.get('age','?')}, 能力{h.get('ability','?')}, "
                    f"嫡庶:{h.get('status','?')})\n"
                )
        else:
            heir_info = "  暂无明确的继承人选。\n"

        prompt = (
            f"君主：{ruler_name}，年龄：{ruler_age}\n"
            f"势力：{faction_id}\n"
            f"继承人选：\n{heir_info}\n"
            f"当前回合：{world_state.get('current_round', 0)}\n\n"
            f"请分析宗室状况，评估继承顺位，对皇储培养提出建议。"
        )

        temperature = (
            self._model_override.get("temperature", 0.6)
            if self._model_override else 0.6
        )

        response = await client.chat_role(
            prompt=prompt,
            system_prompt=(
                "你是元末乱世中的宗正卿，掌管皇室宗族事务。\n"
                "你需关注继承顺位、皇子教育、宗室和睦。\n"
                "以宗正口吻建言，语气恭敬而有见地。"
            ),
            temperature=temperature,
        )

        # 皇子自然成长（数值演化，与 run_single_faction 一致）
        grown_heirs = []
        for heir in heirs:
            aged_heir = dict(heir)
            aged_heir["age"] = heir.get("age", 0) + 1
            if heir.get("age", 0) < 16:
                aged_heir["ability"] = min(100, heir.get("ability", 30) + 2)
            elif heir.get("age", 0) < 30:
                aged_heir["ability"] = min(100, heir.get("ability", 40) + 1)
            grown_heirs.append(aged_heir)

        # 评估继承风险
        ruler_age_now = ruler_age + 1
        risk_level = "low"
        if ruler_age_now > 55 and not grown_heirs:
            risk_level = "high"
        elif ruler_age_now > 50 and len(grown_heirs) <= 1:
            risk_level = "medium"

        return {
            "agent_id": self.agent_id,
            "category": "A7_royal",
            "faction_id": faction_id,
            "ruler": ruler_name,
            "ruler_age": ruler_age_now,
            "heir_count": len(grown_heirs),
            "heirs": grown_heirs,               # ★ 与 run_single_faction 保持一致
            "succession_risk": risk_level,       # ★ 继承风险评估
            "advice": response[:300],
        }

    async def run_single_faction(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        统一单势力宗室推演接口（核心规则：玩家势力跳过宫变决策，仅保留皇子自然成长）

        Args:
            faction_id: 目标势力ID
            world_state: 全局世界状态
            clients: LLM客户端

        Returns:
            {"faction_id": ..., "ruler_status": ..., "heirs_growth": ..., "succession_risk": ...}
        """
        faction = world_state.get("factions", {}).get(faction_id, {})
        ruler_name = faction.get("ruler_name", faction_id)
        ruler_age = faction.get("ruler_age", 40)
        heirs = faction.get("heirs", [])
        is_player = faction.get("is_player", False)

        # 皇子自然成长（数值演化，不依赖LLM）
        grown_heirs = []
        for heir in heirs:
            aged_heir = dict(heir)
            aged_heir["age"] = heir.get("age", 0) + 1  # 每回合+1岁
            # 能力随年龄微调
            if heir.get("age", 0) < 16:
                aged_heir["ability"] = min(100, heir.get("ability", 30) + 2)
            elif heir.get("age", 0) < 30:
                aged_heir["ability"] = min(100, heir.get("ability", 40) + 1)
            grown_heirs.append(aged_heir)

        # 玩家势力：仅保留皇子自然成长，不执行自主宫变/储位争斗决策
        if is_player:
            logger.debug(f"A7 宗室: 玩家势力 {faction_id} 仅皇子成长，跳过AI宫变决策")
            return {
                "agent_id": self.agent_id,
                "category": "A7_royal",
                "faction_id": faction_id,
                "ruler": ruler_name,
                "ruler_age": ruler_age + 1,  # 君主也年长一岁
                "heirs_grown": len(grown_heirs),
                "heirs": grown_heirs,
                "succession_risk": "none",  # 玩家势力无自主宫变风险
                "player_faction": True,
            }

        # 非玩家势力：完整宗室推演（含LLM辅助判定）
        client: TencentHunyuanClient = clients["advisor"]

        heir_info = ""
        if grown_heirs:
            for i, h in enumerate(grown_heirs):
                heir_info += (
                    f"  {i+1}. {h.get('name','?')} "
                    f"(年龄{h.get('age','?')}, 能力{h.get('ability','?')}, "
                    f"嫡庶:{h.get('status','?')})\n"
                )
        else:
            heir_info = "  暂无明确的继承人选。\n"

        prompt = (
            f"君主：{ruler_name}，年龄：{ruler_age + 1}\n"
            f"势力：{faction.get('name', faction_id)}\n"
            f"继承人选：\n{heir_info}\n"
            f"当前回合：{world_state.get('current_round', 0)}\n\n"
            f"请评估宗室状况，分析继承风险，给出建议。"
            f"注意：不要自动发起宫变或储位争斗，仅做分析和建议。"
        )

        temperature = (
            self._model_override.get("temperature", 0.6)
            if self._model_override else 0.6
        )

        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世中的宗正卿，掌管皇室宗族事务。\n"
                    "你需关注继承顺位、皇子教育、宗室和睦。\n"
                    "以宗正口吻建言，语气恭敬而有见地。\n"
                    "重要：你只能分析和建议，不得擅自决定废立或发动宫变。"
                ),
                temperature=temperature,
            )
            advice = response[:400]
        except Exception as e:
            logger.warning(f"A7 LLM调用失败，降级为数值推演: {e}")
            advice = "（AI推演暂不可用，宗室数值正常演化）"

        # 评估继承风险等级
        risk_level = "low"
        if ruler_age > 55 and not grown_heirs:
            risk_level = "high"
        elif ruler_age > 50 and len(grown_heirs) <= 1:
            risk_level = "medium"

        # 将继承风险事件发布到事件总线
        if risk_level in ("high", "medium"):
            self._publish_succession_risk(faction_id, ruler_name, risk_level, ruler_age)

        return {
            "agent_id": self.agent_id,
            "category": "A7_royal",
            "faction_id": faction_id,
            "ruler": ruler_name,
            "ruler_age": ruler_age + 1,
            "heirs_grown": len(grown_heirs),
            "heirs": grown_heirs,
            "succession_risk": risk_level,
            "advice": advice,
            "player_faction": False,
        }

    @staticmethod
    def _publish_succession_risk(faction_id: str, ruler_name: str, risk_level: str, ruler_age: int):
        """将继承风险发布到事件总线"""
        try:
            bus = get_event_bus()
            bus.publish_simple(
                event_type=EventTypes.SUCCESSION_CRISIS,
                source_agent="A7",
                source_faction_id=faction_id,
                priority=EventPriority.HIGH if risk_level == "high" else EventPriority.NORMAL,
                data={
                    "faction_id": faction_id,
                    "ruler_name": ruler_name,
                    "ruler_age": ruler_age,
                    "risk_level": risk_level,
                    "description": f"{ruler_name}年事已高（{ruler_age}岁），继承风险为{risk_level}",
                },
            )
        except Exception as e:
            logger.debug(f"A7 事件总线发布失败（非致命）: {e}")

    async def evaluate_succession(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        评估继承顺位 - 判定谁最有资格继承

        Returns:
            {"successor": ..., "risk": ..., "recommendation": ...}
        """
        client: TencentHunyuanClient = clients["advisor"]
        faction = world_state.get("factions", {}).get(faction_id, {})
        heirs = faction.get("heirs", [])

        heir_list = []
        for h in heirs:
            heir_list.append({
                "name": h.get("name", "?"),
                "age": h.get("age", 0),
                "ability": h.get("ability", 50),
                "status": h.get("status", "庶出"),
            })

        prompt = (
            f"势力：{faction.get('name', faction_id)}\n"
            f"继承人列表：{json.dumps(heir_list, ensure_ascii=False)}\n\n"
            f"请评估继承顺位，分析每位继承人的优劣，"
            f"指出潜在的继承风险，并给出建议。"
        )

        response = await client.chat_role(
            prompt=prompt,
            system_prompt="你是宗正卿，负责评估皇位继承。",
            temperature=0.5,
        )

        return {
            "faction_id": faction_id,
            "heirs": heir_list,
            "evaluation": response[:400],
        }

    # ========== 4.0 AI王朝管理：储位决策+联姻+历练 ==========

    async def manage_dynasty(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        AI王朝管理 — 储位人选、联姻决策、皇子历练任务

        Args:
            faction_id: 势力ID
            world_state: 世界状态
            clients: LLM客户端

        Returns:
            {
                "heir_selection": {"chosen": "皇子名", "reasoning": "理由"},
                "marriage_proposals": [{"prince": "皇子名", "target_faction": "势力ID", "bride": "公主名"}],
                "prince_assignments": [{"prince": "皇子名", "task": "边关监军/地方历练/从文习政"}],
                "court_stability": "稳定/紧张/危机",
                "reasoning": "王朝管理思路"
            }
        """
        client: TencentHunyuanClient = clients.get("advisor")
        if not client:
            return self._fallback_dynasty_management(faction_id, world_state)

        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", faction_id)
        ruler_name = faction.get("ruler_name", faction_id)
        ruler_age = faction.get("ruler_age", 40)
        heirs = faction.get("heirs", [])
        neighbors = faction.get("neighbors", [])
        realm_stability = faction.get("realm_stability", 50)

        heir_text = ""
        for i, h in enumerate(heirs):
            heir_text += (
                f"  {i+1}. {h.get('name', '?')} "
                f"(年龄{h.get('age', '?')} 能力{h.get('ability', '?')} "
                f"嫡庶:{h.get('status', '?')})\n"
            )

        neighbor_text = ""
        for nid in neighbors:
            nf = world_state.get("factions", {}).get(nid, {})
            relations = world_state.get("relations", {})
            stance = "中立"
            for rkey, rel in relations.items():
                if (rel.get("faction_a") == faction_id and rel.get("faction_b") == nid) or \
                   (rel.get("faction_b") == faction_id and rel.get("faction_a") == nid):
                    stance = rel.get("status", "neutral")
                    break
            neighbor_text += (
                f"  {nf.get('name', nid)}：{stance} | "
                f"兵力{nf.get('troops', '?')}\n"
            )

        # 提取默认值，避免 f-string 表达式内出现反斜杠（Python 3.11 限制）
        default_heir_text = '  尚无皇子\n'
        prompt = (
            f"你是{faction_name}的宗正卿，负责宗室管理与王朝传承。\n\n"
            f"【君主】{ruler_name}（{ruler_age}岁）\n"
            f"【民心】{realm_stability}/100\n"
            f"【继承人】\n{heir_text or default_heir_text}\n"
            f"【邻国】\n{neighbor_text}\n\n"
            "请做出以下决策：\n"
            "1. 谁应为储君（立嫡立长还是立贤）？\n"
            "2. 是否需要联姻巩固外交？与谁联姻（需有适龄公主/皇子）？\n"
            "3. 各成年皇子应派往何处历练（边关/地方/朝堂）？\n\n"
            "注意：不可无皇子而空谈立储，不可无适龄子女而谈联姻。\n\n"
            "输出格式（严格JSON）：\n"
            '{"heir_selection":{"chosen":"皇子名","reasoning":"选择理由"},'
            '"marriage_proposals":[{"royal":"皇子/公主名","target_faction":"势力ID"}],'
            '"prince_assignments":[{"prince":"皇子名","task":"边关监军/地方历练/从文习政"}],'
            '"court_stability":"稳定/紧张/危机",'
            '"reasoning":"王朝管理思路(60字内)"}'
        )

        try:
            raw = await client.chat_role(
                prompt=prompt,
                system_prompt=(
                    "你是宗正卿，掌管宗室事务。你须在维护礼法（嫡长子继承）"
                    "与务实治国（立贤）之间权衡。联姻需考虑外交利益。"
                ),
                temperature=0.6,
            )
            import re
            try:
                plan = json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*"heir_selection"[\s\S]*\}', raw)
                plan = json.loads(m.group()) if m else {}

            logger.info(
                f"A7 王朝管理 [{faction_name}]: "
                f"储君{plan.get('heir_selection', {}).get('chosen', '未定')} "
                f"联姻{len(plan.get('marriage_proposals', []))}桩"
            )
            return {
                "heir_selection": plan.get("heir_selection", {}),
                "marriage_proposals": plan.get("marriage_proposals", []),
                "prince_assignments": plan.get("prince_assignments", []),
                "court_stability": plan.get("court_stability", "稳定"),
                "reasoning": plan.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning(f"A7 王朝管理LLM失败 {faction_name}: {e}")
            return self._fallback_dynasty_management(faction_id, world_state)

    def _fallback_dynasty_management(self, faction_id: str, world_state: dict) -> dict:
        """降级王朝管理"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        heirs = faction.get("heirs", [])
        chosen = ""
        if heirs:
            # 嫡长子优先
            for h in heirs:
                if h.get("status") == "嫡出":
                    chosen = h.get("name", "")
                    break
            if not chosen:
                chosen = heirs[0].get("name", "")

        return {
            "heir_selection": {"chosen": chosen, "reasoning": "降级：嫡长子优先"},
            "marriage_proposals": [],
            "prince_assignments": [],
            "court_stability": "稳定",
            "reasoning": "降级王朝管理",
            "_source": "fallback",
        }
