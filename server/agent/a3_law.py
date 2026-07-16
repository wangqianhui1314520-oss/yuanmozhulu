"""
A3 律法堂 - 案件审理、律法判决、朝堂审讯 + 吏部官员任免

模型分组: advisor (chat_role)
触发方式: 手动前端调用 / 后端自动回合（吏部任免）
"""
from __future__ import annotations
import json
import logging
import re
import random
from pathlib import Path
from typing import Optional

from .base import BaseAgent, AgentCategory
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a3_law")

# 缓存加载的 law prompt
_law_prompt_cache: Optional[str] = None


def _load_law_prompt() -> str:
    """加载律法Prompt模板"""
    global _law_prompt_cache
    if _law_prompt_cache is not None:
        return _law_prompt_cache
    prompt_path = Path(__file__).parent.parent / "agent_prompts" / "law.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            _law_prompt_cache = f.read()
    except Exception as e:
        logger.warning(f"读取law.txt prompt失败: {e}，使用默认prompt")
        _law_prompt_cache = "你是元末乱世的刑部主审官，精通律法，刚正不阿。"
    return _law_prompt_cache


class A3LawAgent(BaseAgent):
    """A3 律法堂 - 律法审讯智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A3_{faction_id}",
            category=AgentCategory.A3_LAW,
            faction_id=faction_id,
            max_retries=3,
            retry_delay=2.0,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        律法审讯 - 审理案件、判决、朝堂审讯

        Args:
            world_snapshot: 含 prisoner_name, question, faction_id, world_state
        """
        client: TencentHunyuanClient = clients["advisor"]
        prisoner = world_snapshot.get("prisoner_name", "囚犯")
        question = world_snapshot.get("question", "")
        faction_id = world_snapshot.get("faction_id", self.faction_id)
        world_state = world_snapshot.get("world_state", {})

        # 构建审讯上下文
        faction = world_state.get("factions", {}).get(faction_id, {})
        context = (
            f"当前审讯：{prisoner}\n"
            f"所属势力：{faction.get('name', faction_id)}\n"
            f"审讯问题：{question}\n"
            f"当前回合：{world_state.get('current_round', 0)}\n"
        )

        system_prompt = _load_law_prompt()

        temperature = (
            self._model_override.get("temperature", 0.6)
            if self._model_override else 0.6
        )

        try:
            response = await client.chat_role(
                prompt=context,
                system_prompt=system_prompt,
                temperature=temperature,
                world_json=json.dumps(world_state, ensure_ascii=False) if world_state else None,
            )
        except Exception as e:
            logger.warning(f"A3 审讯LLM调用失败: {e}")
            response = f"堂下囚犯{prisoner}，现有证据不足，暂且收监候审。"

        return {
            "agent_id": self.agent_id,
            "category": "A3_law",
            "prisoner": prisoner,
            "faction_id": faction_id,
            "verdict": response,
        }

    async def judge_case(
        self,
        case_description: str,
        defendant: str,
        evidence: list[str],
        faction_id: str,
        clients: dict,
    ) -> dict:
        """
        审理案件 - 完整的案件审理流程（v4.0 增强：结构化判决）

        Returns:
            {"verdict": ..., "punishment_type": ..., "severity": ..., "reasoning": ...}
        """
        client: TencentHunyuanClient = clients["advisor"]
        evidence_text = "\n".join(f"- {e}" for e in evidence)

        prompt = (
            f"案件：{case_description}\n"
            f"被告：{defendant}\n"
            f"证据：\n{evidence_text}\n\n"
            f"请依法审理此案，给出判决。\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"crime": "罪名", "verdict": "有罪/无罪", '
            f'"punishment_type": "斩首/流放/鞭刑/罚金/免职/赦免", '
            f'"severity": 1-10, "punishment_detail": "具体处罚描述", '
            f'"reasoning": "量刑依据(80字内)", '
            f'"is_miscarriage": true/false, "miscarriage_reason": ""}}'
        )

        system_prompt = _load_law_prompt() + (
            "\n你必须输出合法JSON格式的判决书。"
            "罪行严重度1-10：1-3轻罪（鞭刑/罚金），4-6中罪（流放/免职），7-10重罪（斩首）。"
        )

        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.5,
                world_json=json.dumps({"faction_id": faction_id, "defendant": defendant}, ensure_ascii=False),
            )
            # 尝试解析结构化判决
            result = self._parse_judgment_json(response, defendant, case_description)
            result["raw_response"] = response[:400]
            return result
        except Exception as e:
            logger.warning(f"A3 案件审理LLM调用失败: {e}")
            return {
                "agent_id": self.agent_id, "category": "A3_law",
                "case": case_description, "defendant": defendant,
                "verdict": "暂缓审理", "punishment_type": "收监候审",
                "severity": 3, "reasoning": "主审官暂不可用",
                "is_miscarriage": False,
            }

    # ========== 4.0 吏部：AI官员任免 ==========

    async def manage_officials(
        self, faction_id: str, world_state: dict, clients: dict,
        npcs: list[dict] = None,
    ) -> dict:
        """
        AI官员任免 — 评估绩效、决定升迁降黜

        Args:
            faction_id: 势力ID
            world_state: 世界状态
            clients: LLM客户端
            npcs: 该势力现有官员列表 [{"name":..., "position":..., "loyalty":..., "ability":..., ...}, ...]

        Returns:
            {
                "promotions": [{"name": "张三", "from": "县令", "to": "知府"}],
                "demotions": [{"name": "李四", "from": "知府", "to": "县令"}],
                "dismissals": [{"name": "王五", "reason": "贪腐"}],
                "new_appointments": [{"name": "", "position": "", "criteria": ""}],
                "reasoning": "人事调整总体思路"
            }
        """
        client: TencentHunyuanClient = clients.get("advisor")
        if not client or not npcs:
            return self._fallback_official_management(faction_id, world_state)

        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", faction_id)
        realm_stability = faction.get("realm_stability", 50)
        treasury = faction.get("treasury", 0)

        npc_text = ""
        for n in (npcs or []):
            npc_text += (
                f"  {n.get('name', '?')} | {n.get('position', '无职')} | "
                f"忠诚{n.get('loyalty', 50)} | 能力{n.get('ability', 50)} | "
                f"派系:{n.get('faction', '无')}\n"
            )

        prompt = (
            f"你是{faction_name}的吏部尚书，负责官员考核与任免。\n\n"
            f"【国力】国库{treasury}两 | 民心{realm_stability}/100\n\n"
            f"【现有官员】\n{npc_text}\n"
            f"请进行本季度官员考核：\n"
            f"1. 评估每位官员绩效（忠诚+能力+派系平衡）\n"
            f"2. 决定升迁/留任/贬谪/罢免\n"
            f"3. 如需新官员，说明选拔标准\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"promotions":[{{"name":"官员名","from":"原职","to":"新职","reason":"理由"}}],'
            f'"demotions":[{{"name":"官员名","from":"原职","to":"新职","reason":"理由"}}],'
            f'"dismissals":[{{"name":"官员名","reason":"罢免理由"}}],'
            f'"new_appointments":[{{"position":"职位","criteria":"选拔标准"}}],'
            f'"reasoning":"人事调整总体思路(60字内)"}}'
        )

        try:
            raw = await client.chat_role(
                prompt=prompt,
                system_prompt=(
                    "你是吏部尚书，掌管百官考核。升迁需依据能力和忠诚，"
                    "平衡各派系势力，避免一家独大。不可仅凭好恶处置官员。"
                ),
                temperature=0.5,
            )
            result = self._parse_officials_json(raw)
            logger.info(
                f"A3 吏部 [{faction_name}]: 升{len(result.get('promotions', []))} "
                f"降{len(result.get('demotions', []))} 罢{len(result.get('dismissals', []))}"
            )
            return result
        except Exception as e:
            logger.warning(f"A3 吏部LLM调用失败 {faction_name}: {e}")
            return self._fallback_official_management(faction_id, world_state)

    @staticmethod
    def _parse_judgment_json(raw: str, defendant: str, case: str) -> dict:
        """解析LLM输出的结构化判决"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*"verdict"[\s\S]*\}', raw)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return _fallback_judgment(defendant, case)
            else:
                return _fallback_judgment(defendant, case)

        severity = int(data.get("severity", 5))
        severity = max(1, min(10, severity))
        return {
            "agent_id": f"A3_{defendant}",
            "category": "A3_law",
            "case": case, "defendant": defendant,
            "crime": data.get("crime", "未定罪"),
            "verdict": data.get("verdict", "待审"),
            "punishment_type": data.get("punishment_type", "收监"),
            "severity": severity,
            "punishment_detail": data.get("punishment_detail", ""),
            "reasoning": data.get("reasoning", "")[:80],
            "is_miscarriage": bool(data.get("is_miscarriage", False)),
            "miscarriage_reason": data.get("miscarriage_reason", ""),
        }

    @staticmethod
    def _parse_officials_json(raw: str) -> dict:
        """解析官员任免JSON"""
        import re as _re
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = _re.search(r'\{[\s\S]*"promotions"[\s\S]*\}', raw)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
            return {"promotions": [], "demotions": [], "dismissals": [], "new_appointments": [], "reasoning": "解析失败"}

    def _fallback_official_management(self, faction_id: str, world_state: dict) -> dict:
        """降级官员管理"""
        return {
            "promotions": [], "demotions": [], "dismissals": [],
            "new_appointments": [],
            "reasoning": "吏部和AI均不可用，人事暂缓调整",
            "_source": "fallback",
        }


def _fallback_judgment(defendant: str, case: str) -> dict:
    return {
        "agent_id": f"A3_{defendant}", "category": "A3_law",
        "case": case, "defendant": defendant,
        "crime": "未定罪", "verdict": "待审",
        "punishment_type": "收监", "severity": 3,
        "reasoning": "主审官暂不可用",
        "is_miscarriage": False,
    }
