"""
A4 谍报司 - 细作行动、情报搜集、渗透破坏

模型分组: enemy (chat_fast)
触发方式: 后端自动回合驱动
"""
from __future__ import annotations
import json
import logging
from typing import Optional

import random as _random

from .base import BaseAgent, AgentCategory
from .agent_event_bus import EventTypes, EventPriority, get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a4_espionage")


class A4EspionageAgent(BaseAgent):
    """A4 谍报司 - 细作谍报智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A4_{faction_id}",
            category=AgentCategory.A4_ESPIONAGE,
            faction_id=faction_id,
            max_retries=2,
            retry_delay=1.5,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        谍报行动 - 细作网络情报搜集与行动

        Args:
            world_snapshot: 含 network_id, network_data, world_state
        """
        client: TencentHunyuanClient = clients["enemy"]
        network_id = world_snapshot.get("network_id", "")
        network_data = world_snapshot.get("network_data", {})
        world_state = world_snapshot.get("world_state", {})

        target = network_data.get("target_faction", "?")
        infiltration = network_data.get("infiltration", 0)

        prompt = (
            f"细作网络：{network_id}，潜伏于{target}\n"
            f"渗透度：{infiltration} | "
            f"细作人数：{network_data.get('spies_count', 0)}\n"
            f"活动点数：{network_data.get('action_points', 0)}\n"
            f"当前回合：{world_state.get('current_round', 0)}\n\n"
            f"请以密报口吻汇报本回合情报与行动。"
        )

        temperature = (
            self._model_override.get("temperature", 0.8)
            if self._model_override else 0.8
        )

        try:
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是潜伏敌营的细作头目，负责搜集情报。需谨慎行事，避免暴露身份。以密报口吻汇报。",
                temperature=temperature,
            )
        except Exception as e:
            logger.warning(f"A4谍报 LLM调用失败: {e}")
            response = ""

        # LLM不可用时降级：基于渗透度随机行动
        if not response and infiltration >= 20:
            response = self._generate_fallback_intel(network_id, target, infiltration)

        # 将谍报行动发布到事件总线
        self._publish_to_bus(network_id, target, response, infiltration)

        return {
            "agent_id": self.agent_id,
            "category": "A4_espionage",
            "network_id": network_id,
            "target": target,
            "intel": response[:300],
        }

    @staticmethod
    def _generate_fallback_intel(network_id: str, target: str, infiltration: int) -> str:
        """降级：基于渗透度生成随机谍报行动（7种，与 spy_action 六种 + 渗透对齐）"""
        actions = []
        if infiltration >= 40:
            actions.append("刺杀")       # assassinate
        if infiltration >= 35:
            actions.append("纵火毁产")   # sabotage
        if infiltration >= 30:
            actions.append("离间君臣")   # discord
        if infiltration >= 25:
            actions.append("破坏")       # 通用破坏
        if infiltration >= 20:
            actions.append("窃取情报")   # intel
        if infiltration >= 15:
            actions.append("散布谣言")   # rumor
        if not actions:
            actions.append("渗透")       # 基础渗透
        action = _random.choice(actions)
        return f"潜伏于{target}的细作网络（渗透度{infiltration}），建议执行：{action}"

    def _publish_to_bus(self, network_id: str, target: str, intel: str, infiltration: int):
        """将谍报行动发布到事件总线"""
        if not intel:
            return
        try:
            bus = get_event_bus()
            event_type = EventTypes.INTEL_DISCOVERED
            priority = EventPriority.NORMAL
            if "刺杀" in intel or "assass" in intel.lower():
                event_type = EventTypes.ASSASSINATION
                priority = EventPriority.CRITICAL
            elif "纵火" in intel or "毁产" in intel or "sabotage" in intel.lower():
                priority = EventPriority.HIGH
            elif "破坏" in intel:
                priority = EventPriority.HIGH
            elif "离间" in intel or "discord" in intel.lower():
                priority = EventPriority.HIGH

            bus.publish_simple(
                event_type=event_type,
                source_agent="A4",
                target_faction_id=target,
                priority=priority,
                data={
                    "network_id": network_id,
                    "target": target,
                    "infiltration": infiltration,
                    "description": intel[:200],
                },
            )
        except Exception as e:
            logger.debug(f"A4 事件总线发布失败（非致命）: {e}")

    async def run_all_networks(
        self, world_state: dict, clients: dict,
        skip_faction_id: str = "",  # 核心规则：玩家势力谍报仅由手动指令触发
    ) -> list[dict]:
        """
        并发处理所有细作网络（跳过玩家势力的自动谍报）

        各细作网络互相独立，无数据依赖，改为并发以大幅提速。

        Returns:
            [{"network_id": ..., "intel": ...}, ...]
        """
        import asyncio

        spy_networks = world_state.get("spy_networks", {})

        async def _one_network(net_id: str, net_data) -> dict:
            try:
                snapshot = {
                    "network_id": net_id,
                    "network_data": net_data,
                    "world_state": world_state,
                }
                return await self.safe_step(snapshot, clients)
            except Exception as e:
                logger.error(f"A4 细作网络 {net_id} 处理失败: {e}")
                return {
                    "network_id": net_id,
                    "error": str(e),
                    "status": "failed",
                }

        tasks = []
        net_ids = []
        for net_id, net_data in spy_networks.items():
            # 核心规则：跳过玩家势力的自动细作网络处理
            owner = net_data.get("owner_faction", "") if isinstance(net_data, dict) else getattr(net_data, "owner_faction", "")
            if skip_faction_id and owner == skip_faction_id:
                logger.debug(f"A4 谍报: 跳过玩家势力 {owner} 的自动细作网络")
                continue
            tasks.append(_one_network(net_id, net_data))
            net_ids.append(net_id)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                nid = net_ids[i] if i < len(net_ids) else "?"
                logger.error(f"A4 细作网络 {nid} 异常: {r}")
                cleaned.append({"network_id": nid, "error": str(r), "status": "failed"})
            else:
                cleaned.append(r)

        return cleaned

    # ========== 4.0 AI间谍策略制定 ==========

    async def plan_spy_strategy(
        self, faction_id: str, world_state: dict, clients: dict,
        available_spies: list[dict] = None,
    ) -> dict:
        """
        AI自主制定完整谍报计划

        Args:
            faction_id: 势力ID
            world_state: 世界状态
            clients: LLM客户端
            available_spies: 可用密探列表

        Returns:
            {
                "priority_targets": [{"faction_id": "...", "reason": "..."}],
                "intel_types": ["military", "economic", "diplomatic"],
                "actions": [{"type": "...", "target": "...", "spy": "...", "budget": int}],
                "risk_assessment": "总体风险评估",
                "reasoning": "谍报战略思路"
            }
        """
        client: TencentHunyuanClient = clients.get("enemy")
        if not client:
            return self._fallback_spy_strategy(faction_id, world_state)

        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", faction_id)
        treasury = faction.get("treasury", 0)
        neighbors = faction.get("neighbors", [])

        # 邻国情报
        rival_info = ""
        for nid in neighbors:
            nf = world_state.get("factions", {}).get(nid, {})
            spy_nets = world_state.get("spy_networks", {})
            infiltration = 0
            for net_id, net_data in spy_nets.items():
                if isinstance(net_data, dict):
                    if net_data.get("owner_faction") == faction_id and net_data.get("target_faction") == nid:
                        infiltration = net_data.get("infiltration", 0)
                        break
            rival_info += (
                f"  {nf.get('name', nid)}：兵力{nf.get('troops', '?')} "
                f"渗透度{infiltration}%\n"
            )

        spy_text = ""
        if available_spies:
            for s in available_spies:
                spy_text += f"  {s.get('name', '?')}（等级{s.get('level', 1)}）\n"

        prompt = (
            f"你是{faction_name}的谍报总管，负责制定本回合的间谍行动计划。\n\n"
            f"【可用预算】{min(treasury // 5, 2000)}两\n"
            f"【可用密探】\n{spy_text or '  无专属密探，需从普通细作中选派'}\n"
            f"【目标势力情报】\n{rival_info}\n\n"
            f"请制定本回合谍报计划：\n"
            f"1. 优先渗透哪个势力？为什么？\n"
            f"2. 主要窃取哪类情报（军事/经济/外交/科技）？\n"
            f"3. 是否执行高风险行动（刺杀/破坏/离间）？\n"
            f"4. 风险评估\n\n"
            f"注意：渗透度越高，高风险行动成功概率越大。"
            f"但失败可能导致渗透度大幅下降甚至密探暴露。\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"priority_targets":[{{"faction_id":"ID","reason":"理由"}}],'
            f'"intel_types":["military","economic","diplomatic"],'
            f'"actions":[{{"type":"infiltrate|steal|sabotage|assassinate|discord|rumor","target":"势力ID","spy":"密探名","budget":数字}}],'
            f'"risk_assessment":"风险评估(40字内)",'
            f'"reasoning":"谍报战略思路(60字内)"}}'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世中的谍报总管。你需权衡风险与收益，"
                    "在刺探情报和保全密探之间做出选择。"
                    "不可同时执行超过3项高风险行动。"
                ),
                temperature=0.7,
            )
            import re
            try:
                plan = json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*"priority_targets"[\s\S]*\}', raw)
                plan = json.loads(m.group()) if m else {}

            logger.info(
                f"A4 谍报策略 [{faction_name}]: "
                f"目标{len(plan.get('priority_targets', []))}个 "
                f"行动{len(plan.get('actions', []))}项"
            )
            return {
                "priority_targets": plan.get("priority_targets", []),
                "intel_types": plan.get("intel_types", ["military"]),
                "actions": plan.get("actions", []),
                "risk_assessment": plan.get("risk_assessment", "常规风险"),
                "reasoning": plan.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning(f"A4 谍报策略LLM失败 {faction_name}: {e}")
            return self._fallback_spy_strategy(faction_id, world_state)

    def _fallback_spy_strategy(self, faction_id: str, world_state: dict) -> dict:
        """降级谍报策略"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        neighbors = faction.get("neighbors", [])
        targets = []
        for nid in neighbors[:3]:
            nf = world_state.get("factions", {}).get(nid, {})
            targets.append({"faction_id": nid, "reason": f"邻国{nf.get('name', nid)}基础渗透"})
        return {
            "priority_targets": targets,
            "intel_types": ["military"],
            "actions": [{"type": "infiltrate", "target": nid, "spy": "普通细作", "budget": 100}
                        for nid in neighbors[:2]],
            "risk_assessment": "保守渗透，低风险",
            "reasoning": "降级：优先邻国基础渗透",
            "_source": "fallback",
        }
