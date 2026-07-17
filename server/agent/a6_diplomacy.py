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

        # ★ 博弈论外交提示注入
        gt_hint = world_snapshot.get("game_theory_hint", "")
        phase_hint = world_snapshot.get("phase_hint", "")

        prompt = (
            f"势力：{faction_id}（{faction.get('name', '')}）\n"
            f"邻国：{neighbors_str}\n"
            f"当前兵力：{faction.get('troops', '?')} | "
            f"国库：{faction.get('treasury', '?')}两\n"
            f"声望：{faction.get('reputation', '?')}\n"
        )
        if phase_hint:
            prompt += phase_hint + "\n"
        if gt_hint:
            prompt += f"\n{gt_hint}\n"
        prompt += "\n请分析合纵连横之势，提出外交策略建议。"

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

    # ========== AI外交谈判（v3.5 新增）==========

    async def negotiate(
        self, my_faction_id: str, target_faction_id: str,
        proposal: str, world_state: dict, clients: dict,
        negotiation_history: list = None,
    ) -> dict:
        """
        AI外交谈判 — 玩家势力与AI势力的完整谈判对话

        流程：
        1. 构建双方势力快照（国力、关系、邻接）
        2. LLM 扮演目标势力君主，基于其性格/国力/利害关系回应
        3. 返回结构化谈判结果（接受/拒绝/还价）+ 角色对话

        Args:
            my_faction_id: 本方势力ID（通常是玩家势力）
            target_faction_id: 谈判目标势力ID
            proposal: 谈判提议内容
            world_state: 世界状态
            clients: LLM客户端
            negotiation_history: 之前的谈判历史（多轮谈判用）

        Returns:
            {
                "response": str,           # AI君主的角色对话回应
                "decision": str,           # "accept" | "reject" | "counter"
                "counter_proposal": dict,  # 还价内容（如有）
                "reasoning": str,          # AI决策依据
                "mood": str,               # 君主情绪: "friendly" | "cautious" | "hostile" | "indifferent"
            }
        """
        client: TencentHunyuanClient = clients.get("advisor", clients.get("law"))
        if not client:
            return self._fallback_negotiation(target_faction_id, proposal, world_state)

        # 构建双方势力快照
        factions = world_state.get("factions", {})
        my_faction = factions.get(my_faction_id, {})
        target_faction = factions.get(target_faction_id, {})

        my_name = my_faction.get("name", my_faction_id)
        target_name = target_faction.get("name", target_faction_id)

        # 关系数据
        relations = world_state.get("relations", {}).get(target_faction_id, {})
        relation_status = relations.get("status", "neutral")
        relation_value = relations.get("value", 0)

        # 势力国力对比
        my_power = self._calc_power_score(my_faction)
        target_power = self._calc_power_score(target_faction)
        power_ratio = my_power / max(target_power, 1)

        # 构建上下文
        context = {
            "my_name": my_name,
            "target_name": target_name,
            "target_personality": target_faction.get("personality", "审慎务实"),
            "target_ambition": target_faction.get("ambition", "medium"),
            "relation_status": relation_status,
            "relation_value": relation_value,
            "power_ratio": round(power_ratio, 2),
            "my_troops": my_faction.get("troops", 0),
            "target_troops": target_faction.get("troops", 0),
            "my_treasury": my_faction.get("treasury", 0),
            "target_treasury": target_faction.get("treasury", 0),
            "my_tiles": my_faction.get("tile_count", 0),
            "target_tiles": target_faction.get("tile_count", 0),
            "neighbors": target_faction.get("neighbors", []),
        }

        prompt = (
            f"你是{target_name}的君主，你正在与{my_name}的外交使臣进行谈判。\n\n"
            f"【你的势力概况】\n"
            f"- 性格：{context['target_personality']}\n"
            f"- 野心：{context['target_ambition']}\n"
            f"- 兵力：{context['target_troops']}人\n"
            f"- 国库：{context['target_treasury']}两\n"
            f"- 领地：{context['target_tiles']}块\n"
            f"- 邻国：{', '.join(context['neighbors']) if context['neighbors'] else '无'}\n\n"
            f"【对方势力概况】\n"
            f"- {my_name}\n"
            f"- 兵力：{context['my_troops']}人\n"
            f"- 国库：{context['my_treasury']}两\n"
            f"- 领地：{context['my_tiles']}块\n"
            f"- 双方实力比（对方/你）：{context['power_ratio']:.1f}:1\n\n"
            f"【当前关系】\n"
            f"- 状态：{relation_status}\n"
            f"- 好感度：{relation_value}（-100~+100）\n\n"
        )

        if negotiation_history:
            prompt += "【谈判历史】\n"
            for h in negotiation_history[-5:]:
                prompt += f"- {h.get('speaker', '?')}：{h.get('content', '')}\n"
            prompt += "\n"

        prompt += (
            f"【对方提议】\n{proposal}\n\n"
            f"请以{target_name}君主的身份回应。你必须：\n"
            f"1. 基于你的性格、国力对比、利害关系做出理性决策\n"
            f"2. 以君主口吻回复（古文风格，有威严）\n"
            f"3. 明确表示接受(accept)、拒绝(reject)或还价(counter)\n"
            f"4. 若还价，提出具体条件\n\n"
            f"输出格式（严格JSON，不要额外文字）：\n"
            f'{{"response": "你的回复（古文）", "decision": "accept|reject|counter", '
            f'"counter_proposal": {{"条件描述": "..."}}, '
            f'"reasoning": "决策理由", "mood": "friendly|cautious|hostile|indifferent"}}'
        )

        try:
            raw = await client.chat_role(
                prompt=prompt,
                system_prompt=(
                    f"你是{target_name}的君主，性格{context['target_personality']}。"
                    f"面对外交谈判，你要像一个真实的历史人物一样思考——"
                    f"权衡利害、考虑面子、判断对方诚意。"
                    f"不要轻易接受苛刻条件，也不要无理由拒绝合理提议。"
                    f"输出必须是合法JSON。"
                ),
                temperature=0.7,
            )

            # 解析JSON
            result = self._parse_negotiation_json(raw)
            result["raw_response"] = raw
            result["faction_id"] = target_faction_id
            result["faction_name"] = target_name
            return result

        except Exception as e:
            logger.warning(f"A6 谈判 {target_faction_id} 失败: {e}")
            return self._fallback_negotiation(target_faction_id, proposal, world_state)

    async def run_ai_negotiation(
        self, faction_a_id: str, faction_b_id: str,
        world_state: dict, clients: dict,
    ) -> dict:
        """
        AI势力间外交谈判 — 后端自动驱动两个AI势力谈判

        用于处理AI势力之间的外交互动（结盟、求和、纳贡等）。
        两个AI君主分别发表立场，最终由数值系统裁定。

        Returns:
            {"result": "alliance|truce|tribute|stall", "narrative": str, ...}
        """
        client: TencentHunyuanClient = clients.get("law")
        if not client:
            return {"result": "stall", "narrative": "使者未能成行，谈判搁置。"}

        factions = world_state.get("factions", {})
        fa = factions.get(faction_a_id, {})
        fb = factions.get(faction_b_id, {})
        relations = world_state.get("relations", {})

        # 关系上下文
        rel_ab = relations.get(faction_b_id, {}).get(faction_a_id, {})
        rel_value = rel_ab.get("value", 0) if isinstance(rel_ab, dict) else 0

        prompt = (
            f"【谈判双方】\n"
            f"{fa.get('name', faction_a_id)}（兵力{fa.get('troops', 0)}，"
            f"国库{fa.get('treasury', 0)}两，领地{fa.get('tile_count', 0)}块）\n"
            f"与\n"
            f"{fb.get('name', faction_b_id)}（兵力{fb.get('troops', 0)}，"
            f"国库{fb.get('treasury', 0)}两，领地{fb.get('tile_count', 0)}块）\n\n"
            f"双方好感度：{rel_value}\n\n"
            f"请以史官笔法，描述这两大势力之间的一次外交会晤。"
            f"描述对话内容、立场分歧、最终结果（达成盟约/停战/纳贡/谈判破裂）。"
            f"不要替任何一方做超出其国力的承诺。"
            f"输出约150-200字的叙事文本。"
        )

        try:
            narrative = await client.chat_strategy(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世的史官，以《资治通鉴》笔法记录势力间的外交会晤。"
                ),
                temperature=0.7,
            )

            # 关键词判定结果
            result_type = "stall"
            if any(kw in narrative for kw in ["结盟", "盟约", "歃血", "同盟"]):
                result_type = "alliance"
            elif any(kw in narrative for kw in ["停战", "罢兵", "议和"]):
                result_type = "truce"
            elif any(kw in narrative for kw in ["纳贡", "称臣", "岁币"]):
                result_type = "tribute"

            return {
                "result": result_type,
                "narrative": narrative[:500],
                "faction_a": faction_a_id,
                "faction_b": faction_b_id,
            }
        except Exception as e:
            logger.warning(f"A6 AI间谈判失败: {e}")
            return {"result": "stall", "narrative": "谈判未果，使者各归其国。"}

    # ========== 辅助 ==========

    @staticmethod
    def _calc_power_score(faction: dict) -> float:
        """计算势力综合国力分数"""
        troops = faction.get("troops", 0)
        treasury = faction.get("treasury", 0)
        grain = faction.get("grain", 0)
        tiles = faction.get("tile_count", 0)
        reputation = faction.get("reputation", 0)

        return (
            troops * 1.0 +
            treasury * 0.001 +
            grain * 0.0005 +
            tiles * 50 +
            reputation * 2
        )

    @staticmethod
    def _parse_negotiation_json(raw: str) -> dict:
        """从LLM输出中提取JSON"""
        import re

        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.debug(f"A6 外交回复JSON直接解析失败: {str(e)[:120]}")

        # 提取JSON块
        json_match = re.search(r'\{[^{}]*"response"[^{}]*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.debug(f"A6 外交回复JSON正则提取后仍失败: {str(e)[:120]}")

        # 完全降级：将全文作为回复
        return {
            "response": raw[:400],
            "decision": "reject",
            "reasoning": "无法解析结构化输出",
            "mood": "indifferent",
        }

    def _fallback_negotiation(
        self, target_faction_id: str, proposal: str, world_state: dict
    ) -> dict:
        """谈判降级方案（无LLM时使用）"""
        factions = world_state.get("factions", {})
        target = factions.get(target_faction_id, {})
        name = target.get("name", target_faction_id)

        # 基于提案关键词做简单判定
        if any(kw in proposal for kw in ["结盟", "联盟", "联合"]):
            return {
                "response": f"此事关系重大，容寡人三思。",
                "decision": "counter",
                "counter_proposal": {"条件": "需遣质子为质，方可议盟"},
                "reasoning": "数值降级：结盟需对等条件",
                "mood": "cautious",
                "faction_id": target_faction_id,
                "faction_name": name,
            }
        elif any(kw in proposal for kw in ["求和", "停战", "议和"]):
            return {
                "response": f"若诚心求和，当先退兵三十里，以示诚意。",
                "decision": "counter",
                "counter_proposal": {"条件": "退兵+赔偿军费"},
                "reasoning": "数值降级：求和需实际行动",
                "mood": "cautious",
                "faction_id": target_faction_id,
                "faction_name": name,
            }
        else:
            return {
                "response": f"使者远来辛苦，此事寡人已知晓，改日再议。",
                "decision": "reject",
                "reasoning": "数值降级：泛泛提议通常拒绝",
                "mood": "indifferent",
                "faction_id": target_faction_id,
                "faction_name": name,
            }

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
