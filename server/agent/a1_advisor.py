"""
A1 谋策阁 - 谋臣献策、廷议辩论、战略分析、多NPC对话

模型分组: advisor (chat_role)
触发方式: 手动前端调用 + 每回合自动为玩家势力献策（玩家专属智囊）

3.3 重构：
- 引入 NPCRegistry 解偶 NPC 数据管理
- 引入 ConversationManager 管理独立对话上下文
- 保持向后兼容所有原有 API
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from .base import BaseAgent, AgentCategory
from .npc_registry import (
    NPCRegistry, get_npc_registry, normalize_faction_id,
)
from .conversation_manager import get_conversation_manager
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a1_advisor")


class A1AdvisorAgent(BaseAgent):
    """A1 谋策阁 - 谋臣献策智能体（玩家专属智囊，始终为玩家势力服务）

    增���功能：
    - chat_with_npc(): 与指定 NPC 文臣对话（独立对话上下文）
    - court_debate_multi(): 多 NPC 廷议辩论（并发）
    - step() / run_single_faction(): 自动回合献策
    """

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A1_{faction_id}",
            category=AgentCategory.A1_ADVISOR,
            faction_id=faction_id,
            max_retries=3,
            retry_delay=2.0,
        )
        self._registry = get_npc_registry()
        self._conv_mgr = get_conversation_manager()

    # ================================================================
    # 静态查询方法（供 API 层直接调用，无需实例化）
    # ================================================================

    @staticmethod
    def list_npcs(role_filter: str = "", faction_id: str = "") -> list[dict]:
        """获取可用 NPC 文臣列表"""
        return get_npc_registry().list_npcs(
            role_filter=role_filter, faction_id=faction_id,
        )

    @staticmethod
    def list_faction_advisers(faction_id: str) -> list[dict]:
        """获取指定势力的谋士团成员列表"""
        return get_npc_registry().list_faction_advisers(faction_id)

    @staticmethod
    def get_faction_adviser_info(faction_id: str) -> dict:
        """获取势力谋士团配置信息"""
        return get_npc_registry().get_faction_adviser_info(faction_id)

    @staticmethod
    def get_npc(npc_id: str) -> Optional[dict]:
        """获取单个 NPC 信息"""
        registry = get_npc_registry()
        npc = registry.get_npc(npc_id)
        if not npc:
            return None
        return registry.serialize_npc(npc)

    # ================================================================
    # 与指定 NPC 文臣对话（核心增强功能）
    # ================================================================

    async def chat_with_npc(
        self,
        npc_id: str,
        faction_id: str,
        message: str,
        world_state: dict,
        clients: dict,
        conversation_history: list[dict] = None,
    ) -> dict:
        """与指定 NPC 文臣对话

        每个 NPC 有独立的对话上下文（ConversationManager），
        通过腾讯云混元 AI 生成个性化回复。

        Args:
            npc_id: NPC ID（如 "liu_ji", "li_shanchang" 等）
            faction_id: 玩家势力 ID
            message: 玩家发送的消息
            world_state: 世界状态
            clients: LLM 客户端
            conversation_history: 前端传入的对话历史（可选，用于新旧兼容）

        Returns:
            {"npc_id": ..., "npc_name": ..., "response": ..., "role": ...}
        """
        client: TencentHunyuanClient = clients["advisor"]
        npc = self._registry.get_npc(npc_id)
        if not npc:
            return {"error": f"NPC '{npc_id}' 不存在", "npc_id": npc_id}

        # 构建 NPC 专用系统提示
        system_prompt = self._build_npc_system_prompt(npc, faction_id, world_state)

        # 构建世界快照
        world_json = self._build_faction_snapshot(world_state, faction_id)

        # 构建对话 prompt
        prompt = self._build_npc_chat_prompt(
            npc=npc,
            faction_id=faction_id,
            message=message,
            world_state_snapshot=world_json,
            conversation_history=conversation_history,
        )

        # 优先使用 NPC 自身配置的 temperature
        npc_model_temp = npc.get("model_temp", 0.75)
        temperature = (
            self._model_override.get("temperature", npc_model_temp)
            if self._model_override else npc_model_temp
        )

        response = await client.chat_role(
            prompt=prompt,
            system_prompt=system_prompt,
            world_json=world_json,
            temperature=temperature,
        )

        # 保存到独立对话上下文
        self._conv_mgr.add_exchange(
            npc_id=npc_id,
            user_message=message,
            assistant_response=response,
            faction_id=faction_id,
            npc_name=npc["name"],
        )

        return {
            "npc_id": npc_id,
            "npc_name": npc["name"],
            "npc_title": npc.get("title", ""),
            "role": npc.get("role", ""),
            "role_label": npc.get("role_label", ""),
            "response": response,
            "agent_id": self.agent_id,
            "category": "A1_advisor",
        }

    def _build_npc_system_prompt(
        self, npc: dict, faction_id: str, world_state: dict
    ) -> str:
        """构建 NPC 专用系统提示（含人设+专业领域+势力背景+同僚关系+互动指引）"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", "我方")

        # 基础人设
        parts = [
            f"你是元末乱世中{faction_name}势力的{npc.get('title', '')}{npc['name']}（字{npc.get('style_name', '')}）。",
            f"你的身份是{npc.get('role_label', '谋臣')}。",
            f"你的才智等级为{npc.get('wisdom', 80)}/100，忠诚度为{npc.get('loyalty', 80)}/100，野心为{npc.get('ambition', 30)}/100。",
            f"性格特征：{npc.get('personality', '')}",
            f"说话风格：{npc.get('speaking_style', '')}",
            f"背景经历：{npc.get('background', '')}",
            f"专长领域：{'、'.join(npc.get('specialties', []))}",
        ]

        # 添加势力背景 + 同僚信息
        normalized_fid = normalize_faction_id(faction_id)
        faction_config = self._registry.get_faction_adviser_info(faction_id)
        if faction_config:
            parts.append(f"\n你所属的势力：{faction_config.get('name', '')}")
            parts.append(f"势力定位：{faction_config.get('description', '')}")
            team = faction_config.get("adviser_team", [])
            if team:
                parts.append("\n【同僚信息】你可以根据话题自然地提及或赞同/反对以下同僚的观点：")
                for nid in team:
                    if nid != npc.get("npc_id"):
                        cnpc = self._registry.get_npc(nid)
                        if cnpc:
                            relation = NPCRegistry.get_npc_relation(npc, cnpc)
                            parts.append(
                                f"  - {cnpc.get('name', '')}（{cnpc.get('role_label', '')}）："
                                f"性格{cnpc.get('personality', '')[:20]}……，"
                                f"专长{'、'.join(cnpc.get('specialties', [])[:2])}。"
                                f"你与他{relation}。"
                            )
        else:
            # 流浪谋士：列出玩家势力的主要官员
            parts.append("\n【可参考的同僚】你可以根据话题提及以下朝中官员的观点：")
            advisers = self._registry.list_faction_advisers(faction_id)
            shown = 0
            for a in advisers:
                if a.get("npc_id") != npc.get("npc_id") and shown < 5:
                    cnpc = self._registry.get_npc(a["npc_id"])
                    if cnpc:
                        parts.append(
                            f"  - {cnpc.get('name', '')}（{cnpc.get('role_label', '')}）："
                            f"专长{'、'.join(cnpc.get('specialties', [])[:2])}"
                        )
                        shown += 1

        # Prompt 模板
        template_name = npc.get("prompt_template", "")
        if template_name:
            template = self._registry.load_prompt_template(template_name)
            if template:
                parts.append(f"\n【专业职责】\n{template}")

        # 当前局势
        parts.append(f"\n【当前局势】你所在势力为{faction_name}，你需要基于当前元末乱世的时局来分析问题。")
        parts.append("天下群雄并起，各方势力互相攻伐，需审时度势做出判断。")

        # 对话要求
        parts.extend([
            "\n【对话要求】",
            "1. 始终保持角色设定，不可脱离人物性格和背景",
            "2. 以古文白话风格回答，语气符合你的身份和说话风格",
            "3. 基于你的专长领域提供专业建议，不要越俎代庖",
            "4. 对君主恭敬但不谄媚，敢于直言但注意分寸",
            "5. 可以引用历史典故来佐证观点",
            "6. 回答要具体、有建设性，避免泛泛而谈",
            "7. 根据你的才智等级决定回答深度，根据忠诚度决定是否畅所欲言",
            "8. 当话题涉及同僚专长领域时，可以自然地表示'此事可问XX'或'XX大人所言极是'",
        ])

        return "\n".join(parts)

    def _build_npc_chat_prompt(
        self,
        npc: dict,
        faction_id: str,
        message: str,
        world_state_snapshot: str = "",
        conversation_history: list[dict] = None,
    ) -> str:
        """构建 NPC 对话 prompt（含历史记录）

        优先使用前端传入的 conversation_history，
        否则从 ConversationManager 获取服务端维护的对话上下文。
        """
        # 使用 ConversationManager 构建上下文
        prompt = self._conv_mgr.build_context_for_npc(
            npc_id=npc["npc_id"],
            faction_id=faction_id,
            message=message,
            world_state_snapshot=world_state_snapshot,
        )

        # 如果有前端传入的额外历史（兼容模式），追加到末尾提示
        if conversation_history:
            # conversation_history 已被 build_context_for_npc 合并处理
            # 此处仅做兜底补充
            pass

        return prompt

    # ================================================================
    # 多 NPC 廷议辩论（多轮交互增强版 3.3）
    # ================================================================
    # 改进：从单轮并发+汇总 → 三轮交互
    #   第1轮：各NPC独立发言（并发）
    #   第2轮：NPC互相反驳/支持（基于第1轮观点）
    #   第3轮：调停汇总（秉笔太监归纳+最终建议）
    #
    # 新增集成：
    #   - NPCMemoryManager：好感度影响发言倾向
    #   - NPCRelationManager：廷议后自动更新 NPC 关系

    async def court_debate_multi(
        self,
        topic: str,
        faction_id: str,
        world_state: dict,
        clients: dict,
        npc_ids: list[str] = None,
    ) -> dict:
        """多 NPC 廷议辩论 - 三轮交互：独立发言 → 互相反驳 → 调停汇总"""
        import asyncio

        client: TencentHunyuanClient = clients["advisor"]
        world_json = self._build_faction_snapshot(world_state, faction_id)

        # 延迟导入记忆/关系模块（避免循环依赖）
        from .npc_memory import get_npc_memory_manager
        from .npc_relations import get_npc_relation_manager

        memory_mgr = get_npc_memory_manager()
        relation_mgr = get_npc_relation_manager()

        current_round = world_state.get("current_round", 0)

        # 确定参与 NPC
        if not npc_ids:
            npc_ids = self._registry.select_debate_npcs(faction_id, count=4)

        if len(npc_ids) < 2:
            return {"error": "至少需要2名NPC参与廷议", "topic": topic}

        # ================================================================
        # 第1轮：各 NPC 独立发表意见（并发）
        # ================================================================

        async def _round1_opinion(npc_id: str) -> dict:
            npc = self._registry.get_npc(npc_id)
            if not npc:
                return None

            system_prompt = self._build_npc_system_prompt(npc, faction_id, world_state)

            # 注入好感度/记忆上下文
            memory_context = memory_mgr.build_affection_context(npc_id, current_round)
            system_prompt += memory_context

            # 注入 NPC 关系上下文
            other_ids = [n for n in npc_ids if n != npc_id]
            relation_context = relation_mgr.get_relation_context_for_prompt(npc_id, other_ids)
            system_prompt += relation_context

            system_prompt += (
                f"\n\n当前你正在参加朝堂廷议，议题是「{topic}」。"
                f"\n这是第一轮发言。请你就此议题从你的专业角度发表独立见解。"
                f"\n请坦率地表达你的观点，可以赞同常理，也可以提出异议。"
            )

            prompt = (
                f"廷议议题：「{topic}」\n\n"
                f"请{npc['name']}以你的身份和专长，就此议题发表独立见解。"
                f"你可以：\n"
                f"1. 从你的专业角度分析利弊\n"
                f"2. 提出1-2条具体建议\n"
                f"3. 指出可能的隐患或机遇\n"
                f"发言100-200字即可，言简意赅。"
            )

            try:
                response = await client.chat_role(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    world_json=world_json,
                    temperature=npc.get("model_temp", 0.7),
                )
                return {
                    "npc_id": npc_id,
                    "npc_name": npc["name"],
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": response,
                    "round": 1,
                }
            except Exception as e:
                logger.error(f"廷议第1轮 NPC {npc['name']} 发言失败: {e}")
                return {
                    "npc_id": npc_id,
                    "npc_name": npc["name"],
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": f"（{npc['name']}未及发言）",
                    "round": 1,
                }

        logger.info(f"[廷议] 第1轮：{len(npc_ids)}名NPC独立发言，议题「{topic}」")
        tasks = [_round1_opinion(nid) for nid in npc_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        round1_opinions = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                nid = npc_ids[i] if i < len(npc_ids) else "?"
                logger.error(f"廷议第1轮 NPC {nid} 异常: {r}")
                npc = self._registry.get_npc(nid) or {}
                round1_opinions.append({
                    "npc_id": nid,
                    "npc_name": npc.get("name", nid),
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": f"（{npc.get('name', nid)}因故未能发言）",
                    "round": 1,
                })
            elif r is not None:
                round1_opinions.append(r)

        # 如果第1轮只有不到2个有效发言，直接汇总
        valid_round1 = [o for o in round1_opinions if not o["opinion"].startswith("（")]
        if len(valid_round1) < 2:
            return await self._debate_summary_only(
                topic, round1_opinions, client, world_json
            )

        # ================================================================
        # 第2轮：NPC 互相反驳/支持（基于第1轮观点）
        # ================================================================

        # 构建第1轮发言摘要
        round1_summary = "\n\n".join([
            f"【{o['npc_name']}（{o['role_label']}）的观点】\n{o['opinion']}"
            for o in round1_opinions
        ])

        async def _round2_rebuttal(npc_id: str) -> dict:
            npc = self._registry.get_npc(npc_id)
            if not npc:
                return None

            system_prompt = self._build_npc_system_prompt(npc, faction_id, world_state)

            # 注入好感度上下文（影响反驳倾向）
            memory_context = memory_mgr.build_affection_context(npc_id, current_round)
            system_prompt += memory_context

            # 获取该 NPC 对其他人的关系
            other_ids = [n for n in npc_ids if n != npc_id]
            relation_context = relation_mgr.get_relation_context_for_prompt(npc_id, other_ids)
            system_prompt += relation_context

            # 好感度驱动的辩论倾向提示
            bias = memory_mgr.get_debate_bias(npc_id)
            if bias > 0.3:
                bias_hint = "你对主公心怀感激，倾向于支持主公可能赞同的观点。"
            elif bias < -0.3:
                bias_hint = "你对主公心存不满，可能对主公可能赞同的观点提出异议。"
            else:
                bias_hint = "你持中立态度，根据专业判断发表意见。"

            system_prompt += (
                f"\n\n当前廷议进入第二轮辩论。议题仍是「{topic}」。"
                f"\n以下是第一轮各位大臣的发言：\n{round1_summary}"
                f"\n\n现在请你对同僚的观点进行回应："
                f"\n- 你可以支持与你观点相近的同僚（点名表示赞同）"
                f"\n- 你可以反驳你认为不妥的观点（有理有据地指出问题）"
                f"\n- 你可以补充新的论据来强化你的立场"
                f"\n{bias_hint}"
                f"\n请以朝堂辩论的礼仪发言，不必逐一回应所有观点，挑选1-2个你最关心的进行回应即可。"
                f"\n发言80-150字。"
            )

            prompt = (
                f"廷议第二轮辩论，议题「{topic}」。"
                f"请{npc['name']}就第一轮发言进行回应和辩论。"
            )

            try:
                response = await client.chat_role(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    world_json=world_json,
                    temperature=npc.get("model_temp", 0.75),
                )
                return {
                    "npc_id": npc_id,
                    "npc_name": npc["name"],
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": response,
                    "round": 2,
                }
            except Exception as e:
                logger.error(f"廷议第2轮 NPC {npc['name']} 辩论失败: {e}")
                return {
                    "npc_id": npc_id,
                    "npc_name": npc["name"],
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": f"（{npc['name']}默然不语）",
                    "round": 2,
                }

        logger.info(f"[廷议] 第2轮：{len(npc_ids)}名NPC互相辩论")
        tasks2 = [_round2_rebuttal(nid) for nid in npc_ids]
        results2 = await asyncio.gather(*tasks2, return_exceptions=True)

        round2_opinions = []
        for i, r in enumerate(results2):
            if isinstance(r, Exception):
                nid = npc_ids[i] if i < len(npc_ids) else "?"
                npc = self._registry.get_npc(nid) or {}
                round2_opinions.append({
                    "npc_id": nid,
                    "npc_name": npc.get("name", nid),
                    "title": npc.get("title", ""),
                    "role_label": npc.get("role_label", ""),
                    "role": npc.get("role", ""),
                    "opinion": f"（{npc.get('name', nid)}未能回应）",
                    "round": 2,
                })
            elif r is not None:
                round2_opinions.append(r)

        # ================================================================
        # 第3轮：调停汇总
        # ================================================================

        all_rounds_text = (
            "【第一轮：独立发言】\n" +
            "\n\n".join([
                f"  {o['npc_name']}（{o['role_label']}）：{o['opinion']}"
                for o in round1_opinions
            ]) +
            "\n\n【第二轮：互相辩论】\n" +
            "\n\n".join([
                f"  {o['npc_name']}（{o['role_label']}）：{o['opinion']}"
                for o in round2_opinions
            ])
        )

        summary_prompt = (
            f"廷议议题：「{topic}」\n\n"
            f"以下是两轮廷议的完整记录：\n{all_rounds_text}\n\n"
            f"请你以秉笔太监的身份，将两轮廷议归纳为一份廷议纪要。需包含：\n"
            f"1. 【各方观点】各方的主要立场\n"
            f"2. 【争议焦点】存在分歧的关键问题\n"
            f"3. 【共识与建议】各方能达成一致的方面及最终建议\n"
            f"4. 【辩论态势】哪方观点占据上风\n"
            f"以古文风格撰写，总计不超过250字。"
        )

        summary_system = (
            "你是朝堂上的秉笔太监，负责记录廷议内容。"
            "用古文风格撰写纪要，客观中立，言简意赅。"
        )
        summary_response = ""
        try:
            summary_response = await client.chat_role(
                prompt=summary_prompt,
                system_prompt=summary_system,
                world_json=world_json,
                temperature=0.5,
            )
        except Exception as e:
            logger.warning(f"廷议汇总失败: {e}")
            summary_response = "廷议已毕，详情见各位大臣的发言记录。"

        # 廷议后更新 NPC 间关系
        try:
            all_opinions = round1_opinions + round2_opinions
            relation_mgr.update_after_debate(all_opinions, current_round)
        except Exception as e:
            logger.warning(f"廷议后关系更新失败: {e}")

        # 合并所有意见（按轮次排列）
        all_opinions_combined = round1_opinions + round2_opinions

        return {
            "topic": topic,
            "rounds": {
                "round1": round1_opinions,
                "round2": round2_opinions,
            },
            "opinions": all_opinions_combined,  # 向后兼容
            "summary": summary_response,
            "npc_count": len(npc_ids),
            "debate_rounds": 2,  # 辩论轮次数
            "agent_id": self.agent_id,
            "category": "A1_advisor",
        }

    async def _debate_summary_only(
        self, topic: str, opinions: list[dict],
        client: TencentHunyuanClient, world_json: str,
    ) -> dict:
        """降级：仅有第1轮意见时的简单汇总"""
        all_opinions_text = "\n\n".join([
            f"【{o['npc_name']}（{o['role_label']}）】\n{o['opinion']}"
            for o in opinions
        ])

        summary_prompt = (
            f"廷议议题：「{topic}」\n\n"
            f"以下是各位大臣的意见：\n{all_opinions_text}\n\n"
            f"请你以秉笔太监的身份，将各位大臣的意见归纳为一份简洁的廷议纪要。"
            f"需包含：各方主要观点、争议焦点（若有分歧）、最终建议。不超过200字。"
        )

        summary_system = "你是朝堂上的秉笔太监，负责记录廷议内容。用古文风格撰写纪要，客观中立，言简意赅。"
        summary_response = ""
        try:
            summary_response = await client.chat_role(
                prompt=summary_prompt,
                system_prompt=summary_system,
                world_json=world_json,
                temperature=0.5,
            )
        except Exception as e:
            logger.warning(f"降级汇总失败: {e}")
            summary_response = "廷议已毕，详情见各位大臣的发言记录。"

        return {
            "topic": topic,
            "rounds": {"round1": opinions},
            "opinions": opinions,
            "summary": summary_response,
            "npc_count": len(opinions),
            "debate_rounds": 1,
            "agent_id": self.agent_id,
            "category": "A1_advisor",
        }

    # ================================================================
    # 通用献策 (step)
    # ================================================================

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """谋臣献策 - 分析天下大势，给出策略建议"""
        client: TencentHunyuanClient = clients["advisor"]
        faction_id = world_snapshot.get("faction_id", self.faction_id)
        question = world_snapshot.get("question", "请分析当前天下大势")
        world_state = world_snapshot.get("world_state", {})
        npc_id = world_snapshot.get("npc_id", "")

        # 如果指定了 NPC，使用 NPC 对话模式
        if npc_id and self._registry.npc_exists(npc_id):
            return await self.chat_with_npc(
                npc_id=npc_id,
                faction_id=faction_id,
                message=question,
                world_state=world_state,
                clients=clients,
                conversation_history=world_snapshot.get("conversation_history"),
            )

        world_json = self._build_faction_snapshot(world_state, faction_id)

        template = self._registry.load_prompt_template("advisor_strategic")
        if not template:
            template = (
                "你乃元末乱世首席谋臣，精通兵法韬略、治国安邦之术。\n"
                "你需审时度势，为君主分析天下大势，提出切实可行的策略建议。\n"
                "回答需条理清晰，分点陈述，引经据典。\n"
                "以古文白话皆可，口吻当恭敬而不失骨气。\n\n"
                "【铁律】所有策略建议必须严格基于沙盘数据中的owned_tiles（己方地块）和border_tiles（接壤前线）：\n"
                "- 提及地名时，只可使用owned_tiles中的tile_name\n"
                "- 建议进攻时，目标必须是border_tiles中的敌方势力\n"
                "- 建议建造时，费用不可超过treasury，地点必须在owned_tiles中\n"
                "- 建议征兵时，数量不可超过各地块population之和的60%\n"
                "- 不得凭空捏造任何地名、数字或势力名"
            )

        faction_data = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction_data.get("name", "我方")
        enhanced_question = (
            f"当前为至正{world_state.get('current_year', 1351)}年"
            f"{world_state.get('current_season', '春')}季，"
            f"第{world_state.get('current_round', 0)}回合。\n\n"
            f"君主问：{question}"
        )

        response = await client.chat_role(
            prompt=enhanced_question,
            system_prompt=template,
            world_json=world_json,
            temperature=self._model_override.get("temperature", 0.7) if self._model_override else 0.7,
        )

        return {
            "agent_id": self.agent_id,
            "category": "A1_advisor",
            "faction_id": faction_id,
            "response": response,
            "advisor": "首席谋臣",
            "round": world_state.get("current_round", 0),
            "year": world_state.get("current_year", 1351),
            "season": world_state.get("current_season", "春"),
        }

    # ================================================================
    # 自动回合献策 (run_single_faction)
    # ================================================================

    async def run_single_faction(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """每回合自动为指定势力提供谋略建议"""
        client: TencentHunyuanClient = clients["advisor"]
        world_json = self._build_faction_snapshot(world_state, faction_id)

        # 获取谋士团
        faction_advisers = self._registry.list_faction_advisers(faction_id)
        native_advisers = [a for a in faction_advisers if a.get("faction") == faction_id]
        wandering_advisers = [a for a in faction_advisers if a.get("faction") == "_wandering"]

        selected_advisers = native_advisers[:3]
        remaining_slots = 4 - len(selected_advisers)
        if remaining_slots > 0 and wandering_advisers:
            selected_advisers.extend(wandering_advisers[:remaining_slots])

        if not selected_advisers:
            return await self._auto_advice_generic(faction_id, world_state, clients)

        # 各谋士并发献策
        import asyncio as _asyncio
        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", "我方")

        async def _one_adviser_advice(adviser: dict):
            try:
                npc_full = self._registry.get_npc(adviser["npc_id"]) or {}
                system_prompt = self._build_npc_system_prompt(npc_full, faction_id, world_state)
                system_prompt += (
                    f"\n\n当前是回合结束时，你作为{faction_name}的{adviser.get('role_label', '')}，"
                    f"需要就本回合的局势给出你的专业建议。"
                    f"请聚焦于你的专长领域（{'、'.join(adviser.get('specialties', []))}），"
                    f"给出1-2条具体可行的建议，每条30-50字。"
                )
                prompt = f"请就本回合局势，从你的专业角度为{faction_name}献上一策。"
                response = await client.chat_role(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    world_json=world_json,
                    temperature=adviser.get("model_temp", 0.7),
                )
                return {
                    "npc_id": adviser["npc_id"],
                    "npc_name": adviser["name"],
                    "role_label": adviser.get("role_label", ""),
                    "opinion": response,
                }
            except Exception as e:
                logger.warning(f"谋士 {adviser.get('name', '?')} 献策失败: {e}")
                return None

        tasks = [_one_adviser_advice(a) for a in selected_advisers]
        raw_results = await _asyncio.gather(*tasks, return_exceptions=True)

        adviser_opinions = []
        for r in raw_results:
            if isinstance(r, Exception):
                logger.warning(f"谋士献策异常: {r}")
            elif r is not None:
                adviser_opinions.append(r)

        if not adviser_opinions:
            return await self._auto_advice_generic(faction_id, world_state, clients)

        all_opinions_text = "\n\n".join([
            f"【{o['npc_name']}（{o['role_label']}）】\n{o['opinion']}"
            for o in adviser_opinions
        ])

        summary_prompt = (
            f"你是{faction_name}势力的秉笔太监。以下是各位谋士本回合的献策：\n\n"
            f"{all_opinions_text}\n\n"
            f"请将以上献策归纳为一份简洁的回合策略纪要，格式如下：\n"
            f"【形势总览】一句话概括当前局势（20字内）\n"
            f"【军事方略】汇总军事建议\n"
            f"【内政要务】汇总内政建议\n"
            f"【外交谋略】汇总外交建议\n"
            f"以古文白话风格，总计不超过150字。"
        )

        summary_system = "你是朝堂上的秉笔太监，负责整理谋士们的献策纪要。客观、简洁、条理分明。"
        summary_response = ""
        try:
            summary_response = await client.chat_role(
                prompt=summary_prompt,
                system_prompt=summary_system,
                world_json=world_json,
                temperature=0.5,
            )
        except Exception as e:
            logger.warning(f"献策汇总失败: {e}")
            summary_response = "谋士团已献策，详情见各谋士意见。"

        return {
            "agent_id": self.agent_id,
            "category": "A1_advisor",
            "faction_id": faction_id,
            "mode": "auto_advice_multi",
            "adviser_count": len(adviser_opinions),
            "adviser_opinions": adviser_opinions,
            "advice": summary_response,
            "advisor": f"谋士团（{len(adviser_opinions)}人）",
        }

    async def _auto_advice_generic(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """降级：通用首席谋臣献策（无谋士团时使用）"""
        client: TencentHunyuanClient = clients["advisor"]
        world_json = self._build_faction_snapshot(world_state, faction_id)
        faction = world_state.get("factions", {}).get(faction_id, {})
        faction_name = faction.get("name", "我方")

        system_prompt = (
            "你乃元末乱世首席谋臣，精通兵法韬略、治国安邦之术。\n"
            "每回合你需为君主分析当前局势，给出清晰的策略建议。\n"
            "请严格按以下四段格式输出，不得遗漏任何一段：\n"
            "【形势总览】分析当前天下大势与本势力处境（50-100字）\n"
            "【军事方略】建议下一步军事行动，进攻/防守/征兵等（50-100字）\n"
            "【内政要务】建议优先处理的内政事务，粮草/民心/建设等（50-100字）\n"
            "【外交谋略】建议的外交策略，结盟/示好/防备等（50-100字）\n"
            "以古文白话，口吻恭敬而有见地。"
        )

        prompt = f"请为本回合（{world_state.get('current_year', 1351)}年{world_state.get('current_season', '春')}）的{faction_name}制定策略建议。"
        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=system_prompt,
                world_json=world_json,
                temperature=0.65,
            )
        except Exception as e:
            logger.warning(f"A1 降级献策LLM调用失败: {e}")
            response = (
                f"【形势总览】当前天下纷争未定，{faction_name}宜审时度势。\n"
                f"【军事方略】稳固边境，酌情募兵以备不时之需。\n"
                f"【内政要务】劝课农桑，安抚民心，充实府库。\n"
                f"【外交谋略】远交近攻，结好强援，孤立仇雠。"
            )

        # 后处理：确保四段格式完整
        response = self._ensure_four_section_format(response, faction_name)

        return {
            "agent_id": self.agent_id,
            "category": "A1_advisor",
            "faction_id": faction_id,
            "mode": "auto_advice",
            "advice": response,
            "advisor": "首席谋臣",
        }

    @staticmethod
    def _ensure_four_section_format(text: str, faction_name: str) -> str:
        """确保献策输出包含完整的四段格式"""
        sections = ["【形势总览】", "【军事方略】", "【内政要务】", "【外交谋略】"]
        defaults = {
            "【形势总览】": f"天下纷争未定，{faction_name}宜审时度势。",
            "【军事方略】": "稳固边境，酌情募兵以备不时之需。",
            "【内政要务】": "劝课农桑，安抚民心，充实府库。",
            "【外交谋略】": "远交近攻，结好强援，孤立仇雠。",
        }
        for sec in sections:
            if sec not in text:
                text += f"\n{sec}{defaults[sec]}"
        return text

    # ================================================================
    # 廷议辩论（旧版接口，向后兼容）
    # ================================================================

    async def court_debate(
        self,
        topic: str,
        faction_id: str,
        world_state: dict,
        clients: dict,
    ) -> dict:
        """廷议辩论模式 - 向后兼容旧接口"""
        client: TencentHunyuanClient = clients["advisor"]
        world_json = self._build_faction_snapshot(world_state, faction_id)

        system_prompt = (
            "你是元末朝廷重臣，正在参加廷议辩论。\n"
            "你需就当前议题发表见解，与同僚辩论，最终形成决议。\n"
            "口吻当符合朝堂礼仪，有理有据，不卑不亢。"
        )

        prompt = f"廷议议题：{topic}\n请发表你的见解，并与其他大臣辩论，最终给出建议。"
        response = await client.chat_role(
            prompt=prompt,
            system_prompt=system_prompt,
            world_json=world_json,
            temperature=0.65,
        )

        return {
            "agent_id": self.agent_id,
            "category": "A1_advisor",
            "topic": topic,
            "debate_result": response,
        }

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _build_faction_snapshot(world_state: dict, faction_id: str) -> str:
        """构建势力视角的世界快照 JSON（含地块详情，确保献策数据对齐）"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        all_factions = world_state.get("factions", {})
        all_tiles = world_state.get("tiles", {})
        all_relations = world_state.get("relations", {})

        other_factions = []
        for fid, fdata in all_factions.items():
            if fid != faction_id and fdata.get("alive", True):
                other_factions.append({
                    "name": fdata.get("name", fid),
                    "troops": fdata.get("troops", 0),
                    "tile_count": fdata.get("tile_count", 0),
                    "reputation": fdata.get("reputation", 0),
                })

        # ── 己方地块详情 ──
        owned_tiles = []
        border_tiles = []
        for tid, td in all_tiles.items():
            if not isinstance(td, dict):
                continue
            if td.get("faction_id", "") != faction_id:
                continue
            tile_info = {
                "tile_id": td.get("tile_id", tid),
                "tile_name": td.get("tile_name", ""),
                "tile_type": td.get("tile_type", ""),
                "population": td.get("population", 0),
                "troops": td.get("troops", 0),
                "grain": td.get("grain", 0),
                "treasury": td.get("treasury", 0),
                "fortification": td.get("fortification", 0),
                "granary": td.get("granary", 0),
                "armory": td.get("armory", 0),
                "stable": td.get("stable", 0),
                "water_works": td.get("water_works", 0),
                "clinic": td.get("clinic", 0),
                "is_capital": td.get("is_capital", False),
                "is_port": td.get("is_port", False),
            }
            owned_tiles.append(tile_info)

        # ── 接壤关系 ──
        for td in owned_tiles:
            tid = td["tile_id"]
            # 通过 relations 中的邻接关系判断是否前线
            for rel_key, rel_data in all_relations.items():
                if not isinstance(rel_data, dict):
                    continue
                parts = rel_key.split("|")
                if len(parts) != 2:
                    continue
                # 检查该关系是否涉及本地块
                if tid in parts:
                    other_part = parts[1] if parts[0] == tid else parts[0]
                    # 如果对方是地块ID且有势力归属
                    other_tile = all_tiles.get(other_part, {})
                    if isinstance(other_tile, dict):
                        other_fid = other_tile.get("faction_id", "")
                        if other_fid and other_fid != faction_id:
                            other_name = all_factions.get(other_fid, {}).get("name", other_fid)
                            border_entry = f"{td['tile_name']}↔{other_name}"
                            if border_entry not in border_tiles:
                                border_tiles.append(border_entry)
                    break

        snapshot = {
            "faction_id": faction_id,
            "faction_name": faction.get("name", faction_id),
            "current_round": world_state.get("current_round", 0),
            "current_year": world_state.get("current_year", 1351),
            "current_season": world_state.get("current_season", "春"),
            "troops": faction.get("troops", 0),
            "treasury": faction.get("treasury", 0),
            "grain": faction.get("grain", 0),
            "arms": faction.get("arms", 0),
            "horses": faction.get("horses", 0),
            "reputation": faction.get("reputation", 0),
            "tile_count": faction.get("tile_count", len(owned_tiles)),
            "population": faction.get("population", 0),
            "owned_tiles": owned_tiles,
            "border_tiles": border_tiles,
            "neighbors": faction.get("neighbors", []),
            "other_factions": other_factions,
            "relations": {k: v for k, v in all_relations.items() 
                          if isinstance(v, dict) and faction_id in k},
            "active_battles": world_state.get("active_battles", []),
            "events_log": world_state.get("events_log", [])[-5:],
        }
        return json.dumps(snapshot, ensure_ascii=False, indent=2)
