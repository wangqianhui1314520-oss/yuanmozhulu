"""
A3 律法堂 - 案件审理、律法判决、朝堂审讯

模型分组: advisor (chat_role)
触发方式: 手动前端调用
"""
from __future__ import annotations
import json
import logging
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

        response = await client.chat_role(
            prompt=context,
            system_prompt=system_prompt,
            temperature=temperature,
        )

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
        审理案件 - 完整的案件审理流程

        Returns:
            {"verdict": ..., "punishment": ..., "reasoning": ...}
        """
        client: TencentHunyuanClient = clients["advisor"]
        evidence_text = "\n".join(f"- {e}" for e in evidence)

        prompt = (
            f"案件：{case_description}\n"
            f"被告：{defendant}\n"
            f"证据：\n{evidence_text}\n\n"
            f"请依法审理此案，给出判决。需包含：罪名认定、量刑依据、最终判决。"
        )

        system_prompt = _load_law_prompt()

        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.5,
            )
        except Exception as e:
            logger.warning(f"A3 案件审理LLM调用失败: {e}")
            response = f"案件：{case_description}。因主审官暂不可用，依律从简判决：证据不足，发回重审。"

        return {
            "agent_id": self.agent_id,
            "category": "A3_law",
            "case": case_description,
            "defendant": defendant,
            "judgment": response,
        }
