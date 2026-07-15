"""
A6 外交署 - 合纵连横、盟约谈判、外交文书

模型分组: law (chat_strategy)
触发方式: 后端自动回合驱动
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_event_bus import EventTypes, EventPriority, get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a6_diplomacy")


class A6DiplomacyAgent(BaseAgent):
    """A6 外交署 - 外交缔约智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A6_{faction_id}",
            category=AgentCategory.A6_DIPLOMACY,
            faction_id=faction_id,
            max_retries=3,
            retry_delay=2.5,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        外交推演 - 分析合纵连横之势

        Args:
            world_snapshot: 含 faction_id, world_state
        """
        client: TencentHunyuanClient = clients["law"]
        faction_id = world_snapshot.get("faction_id", self.faction_id)
        world_state = world_snapshot.get("world_state", {})

        faction = world_state.get("factions", {}).get(faction_id, {})
        neighbors = faction.get("neighbors", [])
        neighbors_str = "、".join(neighbors) if neighbors else "无邻国"

        prompt = (
            f"势力：{faction_id}（{faction.get('name', '')}）\n"
            f"邻国：{neighbors_str}\n"
            f"当前兵力：{faction.get('troops', '?')} | "
            f"国库：{faction.get('treasury', '?')}两\n"
            f"声望：{faction.get('reputation', '?')}\n\n"
            f"请分析合纵连横之势，提出外交策略建议。"
        )

        world_json = self._build_snapshot(world_state, faction_id)

        temperature = (
            self._model_override.get("temperature", 0.6)
            if self._model_override else 0.6
        )

        response = await client.chat_strategy(
            prompt=prompt,
            world_json=world_json,
            system_prompt="你是外交使臣，精通合纵连横之术。分析各国利害关系，提出外交策略。以使臣口吻分析局势。",
            temperature=temperature,
        )

        advice = response[:400]

        # 将外交决策发布到事件总线，供A8国史记录
        self._publish_diplomacy_to_bus(faction_id, advice)

        return {
            "agent_id": self.agent_id,
            "category": "A6_diplomacy",
            "faction_id": faction_id,
            "neighbors": neighbors,
            "diplomacy_advice": advice,
        }

    def _publish_diplomacy_to_bus(self, faction_id: str, advice: str):
        """将外交决策发布到事件总线"""
        if not advice:
            return
        try:
            bus = get_event_bus()

            if any(kw in advice for kw in ["结盟", "联盟", "联合", "同盟"]):
                bus.publish_simple(
                    event_type=EventTypes.ALLIANCE_FORMED,
                    source_agent="A6",
                    source_faction_id=faction_id,
                    priority=EventPriority.HIGH,
                    data={"description": advice[:200]},
                )
            elif any(kw in advice for kw in ["宣战", "讨伐"]):
                bus.publish_simple(
                    event_type=EventTypes.WAR_DECLARED,
                    source_agent="A6",
                    source_faction_id=faction_id,
                    priority=EventPriority.CRITICAL,
                    data={"description": advice[:200]},
                )
            elif any(kw in advice for kw in ["纳贡", "进贡", "称臣"]):
                bus.publish_simple(
                    event_type=EventTypes.TRIBUTE_OFFERED,
                    source_agent="A6",
                    source_faction_id=faction_id,
                    priority=EventPriority.HIGH,
                    data={"description": advice[:200]},
                )
            elif any(kw in advice for kw in ["求和", "停战", "议和"]):
                bus.publish_simple(
                    event_type=EventTypes.PEACE_TREATY,
                    source_agent="A6",
                    source_faction_id=faction_id,
                    priority=EventPriority.HIGH,
                    data={"description": advice[:200]},
                )
            elif any(kw in advice for kw in ["联姻", "和亲"]):
                bus.publish_simple(
                    event_type=EventTypes.ALLIANCE_FORMED,
                    source_agent="A6",
                    source_faction_id=faction_id,
                    priority=EventPriority.HIGH,
                    data={"description": advice[:200]},
                )
        except Exception as e:
            logger.debug(f"A6 事件总线发布失败（非致命）: {e}")

    async def run_all_factions(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",  # 核心规则：玩家势力外交仅响应手动操作
    ) -> list[dict]:
        """
        并发处理所有存活势力的外交推演（跳过玩家势力：不会主动发起结盟/宣战）

        各势力外交分析互相独立，无数据依赖，改为并发以大幅提速。

        Returns:
            [{"faction_id": ..., "diplomacy_advice": ...}, ...]
        """
        import asyncio

        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id  # 核心规则：跳过玩家势力，外交仅响应手动操作
        }

        async def _one_faction(faction_id: str) -> dict:
            snapshot = {
                "faction_id": faction_id,
                "world_state": world_state,
            }
            try:
                return await self.safe_step(snapshot, clients)
            except Exception as e:
                logger.error(f"A6 外交推演 {faction_id} 失败: {e}")
                return {
                    "faction_id": faction_id,
                    "error": str(e),
                    "status": "failed",
                }

        tasks = [_one_faction(fid) for fid in living]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                fid = list(living.keys())[i] if i < len(living) else "?"
                logger.error(f"A6 外交推演 {fid} 异常: {r}")
                cleaned.append({"faction_id": fid, "error": str(r), "status": "failed"})
            else:
                cleaned.append(r)

        return cleaned

    # ========== 辅助 ==========

    @staticmethod
    def _build_snapshot(world_state: dict, faction_id: str) -> str:
        faction = world_state.get("factions", {}).get(faction_id, {})
        snapshot = {
            "faction_id": faction_id,
            "faction_name": faction.get("name", faction_id),
            "current_round": world_state.get("current_round", 0),
            "troops": faction.get("troops", 0),
            "treasury": faction.get("treasury", 0),
            "grain": faction.get("grain", 0),
            "reputation": faction.get("reputation", 0),
            "tile_count": faction.get("tile_count", 0),
            "neighbors": faction.get("neighbors", []),
            "relations": world_state.get("relations", {}),
            "active_battles": world_state.get("active_battles", []),
        }
        return json.dumps(snapshot, ensure_ascii=False, indent=2)
