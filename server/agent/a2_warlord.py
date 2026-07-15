"""
A2 群雄殿 - 君主NPC自主推演、势力决策

模型分组: advisor (chat_role)
触发方式: 后端自动回合驱动

输出协议: step() 返回结构化 decision_plan 字典供 AIExecutor 落地，
          同时保留 full_response 文本供前端展示和 A8 国史记录。
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_event_bus import EventTypes, EventPriority, get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a2_warlord")

# A2 结构化决策类型
DECISION_ACTIONS = [
    "recruit",      # 征兵
    "march",        # 行军/进攻
    "attack",       # 攻击
    "build",        # 开垦/筑城
    "farm",         # 屯田
    "train_troops", # 练兵
    "tax",          # 征税
    "fortify",      # 筑城
    "diplomacy",    # 外交
    "spy",          # 谍报
    "claim_title",  # 称帝/称王
    "consolidate",  # 休整/稳固
    "defend",       # 防守
]


class A2WarlordAgent(BaseAgent):
    """A2 群雄殿 - 君主NPC自主决策智能体"""

    def __init__(self, faction_id: str, agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A2_{faction_id}",
            category=AgentCategory.A2_WARLORD,
            faction_id=faction_id,
            max_retries=3,
            retry_delay=2.0,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        君主自主推演 - 每回合AI势力独立决策

        Args:
            world_snapshot: 含 faction_config (势力配置) 和 world_state
            clients: {"advisor": ..., "law": ..., "enemy": ...}

        Returns:
            dict 含 decision_plan (结构化，供AIExecutor落地)
                 和 full_response (文本，供前端展示和A8国史记录)
        """
        client: TencentHunyuanClient = clients["advisor"]
        faction_config = world_snapshot.get("faction_config", {})
        world_state = world_snapshot.get("world_state", {})

        # P3修复: factions.json 字段名为 personality_tags，而非 personality
        personality = faction_config.get("personality_tags") or faction_config.get("personality", [])
        ruler_name = faction_config.get("ruler_name", self.faction_id)

        # 组装Prompt（包含结构化输出要求）
        prompt = self._build_ruler_prompt(ruler_name, personality, world_state)
        system_prompt = self._load_ruler_prompt(personality)
        world_json = self._world_snapshot_for_faction(world_state)

        temperature = (
            self._model_override.get("temperature", 0.7)
            if self._model_override else 0.7
        )

        try:
            response = await client.chat_role(
                prompt=prompt,
                system_prompt=system_prompt,
                world_json=world_json,
                temperature=temperature,
            )
            llm_ok = bool(response)
        except Exception as e:
            logger.warning(f"A2 LLM调用失败 (faction={self.faction_id}): {e}")
            response = ""
            llm_ok = False

        # ★ 从文本响应中解析结构化决策计划（供AIExecutor落地）
        decision_plan = self._parse_decision_plan(response, faction_config, world_state)

        decision_summary = response[:300] if response else "（无决策）"

        # 将关键决策发布到事件总线，供A8国史/A4谍报等消费
        self._publish_decisions_to_bus(response, ruler_name, faction_config)

        return {
            "agent_id": self.agent_id,
            "category": "A2_warlord",
            "faction_id": self.faction_id,
            "ruler": ruler_name,
            "decision_summary": decision_summary,
            "decision_plan": decision_plan,       # ★ 结构化决策，供AIExecutor落地
            "full_response": response,            # 文本叙事，供前端和A8国史
            "llm_ok": llm_ok,
        }

    # ========== 结构化决策解析 ==========

    def _parse_decision_plan(
        self, response: str, faction_config: dict, world_state: dict
    ) -> dict:
        """
        从 LLM 文本响应中解析结构化决策计划。

        解析策略：
        1. 优先匹配 LLM 响应中的 JSON 块（如果LLM按格式输出）
        2. 否则基于关键词启发式提取决策意图
        3. 返回统一的 decision_plan 字典，可直接传给 AIExecutor

        Returns:
            {
                "primary_action": "recruit"|"march"|...,
                "actions": [{"type": "recruit", "target": ..., "amount": ...}, ...],
                "strategy": "expansion"|"consolidation"|...,
                "reasoning": "决策理由简述"
            }
        """
        if not response:
            return {"primary_action": "consolidate", "actions": [], "strategy": "consolidation", "reasoning": ""}

        # 策略1：尝试提取 JSON 块
        json_match = re.search(r'\{[\s\S]*"action"[\s\S]*\}', response)
        if json_match:
            try:
                plan = json.loads(json_match.group())
                return self._normalize_plan(plan, faction_config, world_state)
            except json.JSONDecodeError:
                pass

        # 策略2：关键词启发式提取
        return self._heuristic_plan(response, faction_config, world_state)

    def _normalize_plan(self, raw: dict, faction_config: dict, world_state: dict) -> dict:
        """规范化从JSON解析出的决策计划"""
        actions = raw.get("actions", [])
        if not isinstance(actions, list):
            actions = [raw] if raw.get("action") else []

        normalized_actions = []
        for act in actions:
            if not isinstance(act, dict):
                continue
            action_type = act.get("action", act.get("type", "consolidate"))
            if action_type not in DECISION_ACTIONS:
                action_type = "consolidate"
            normalized_actions.append({
                "type": action_type,
                "target": act.get("target", ""),
                "target_faction": act.get("target_faction", ""),
                "amount": act.get("amount", act.get("count", 0)),
                "priority": act.get("priority", "normal"),
            })

        return {
            "primary_action": raw.get("primary_action", normalized_actions[0]["type"] if normalized_actions else "consolidate"),
            "actions": normalized_actions,
            "strategy": raw.get("strategy", "consolidation"),
            "reasoning": raw.get("reasoning", raw.get("summary", "")),
            "confidence": raw.get("confidence", 0.5),
        }

    def _heuristic_plan(self, response: str, faction_config: dict, world_state: dict) -> dict:
        """基于关键词启发式提取决策意图（LLM未按JSON格式输出时的降级）"""
        # P3修复: factions.json 字段名为 personality_tags
        personality = faction_config.get("personality_tags") or faction_config.get("personality", [])
        actions = []
        strategy = "consolidation"

        # 军事行动检测
        if any(kw in response for kw in ["进攻", "出击", "攻取", "攻打", "征讨", "讨伐", "出征"]):
            target = self._extract_target_faction(response, world_state)
            actions.append({"type": "march", "target": target, "target_faction": target, "amount": 0, "priority": "high"})
            strategy = "expansion"

        if any(kw in response for kw in ["征兵", "募兵", "扩军"]):
            actions.append({"type": "recruit", "target": "", "amount": 0, "priority": "high"})

        if any(kw in response for kw in ["练兵", "操练"]):
            actions.append({"type": "train_troops", "target": "", "amount": 0, "priority": "normal"})

        # 内政行动
        if any(kw in response for kw in ["开垦", "屯田", "垦荒"]):
            actions.append({"type": "farm", "target": "", "amount": 0, "priority": "normal"})
            if strategy != "expansion":
                strategy = "consolidation"

        if any(kw in response for kw in ["筑城", "修城", "加固", "城防"]):
            actions.append({"type": "fortify", "target": "", "amount": 0, "priority": "normal"})

        # 称帝/称王
        if any(kw in response for kw in ["称帝", "称王", "登基"]):
            actions.append({"type": "claim_title", "target": "", "amount": 0, "priority": "critical"})

        # 防守
        if any(kw in response for kw in ["防守", "固守", "坚守", "守城", "防御"]):
            actions.append({"type": "defend", "target": "", "amount": 0, "priority": "high"})
            strategy = "consolidation"

        # 外交
        if any(kw in response for kw in ["结盟", "联盟", "联合", "同盟", "示好"]):
            target = self._extract_target_faction(response, world_state)
            actions.append({"type": "diplomacy", "target": target, "target_faction": target, "amount": 0, "priority": "normal"})

        # 谍报
        if any(kw in response for kw in ["细作", "谍报", "密探", "渗透", "刺探"]):
            target = self._extract_target_faction(response, world_state)
            actions.append({"type": "spy", "target": target, "target_faction": target, "amount": 0, "priority": "normal"})

        # 休整（默认）
        if not actions:
            actions.append({"type": "consolidate", "target": "", "amount": 0, "priority": "normal"})

        return {
            "primary_action": actions[0]["type"],
            "actions": actions,
            "strategy": strategy,
            "reasoning": response[:200],
            "confidence": 0.3,  # 启发式解析置信度较低
        }

    def _extract_target_faction(self, response: str, world_state: dict) -> str:
        """从响应文本中提取目标势力ID"""
        factions = world_state.get("factions", {})
        for fid, fdata in factions.items():
            name = fdata.get("name", "")
            if name and name in response:
                return fid
        return ""

    # ========== Prompt构建 ==========

    def _build_ruler_prompt(
        self, ruler_name: str, personality: list[str], world_state: dict
    ) -> str:
        faction = world_state.get("factions", {}).get(self.faction_id, {})
        tags = "、".join(personality) if personality else "无特殊"

        neighbors = faction.get("neighbors", [])
        neighbor_info = ""
        if neighbors:
            for nid in neighbors:
                nf = world_state.get("factions", {}).get(nid, {})
                neighbor_info += f"  - {nf.get('name', nid)}：兵{nf.get('troops', '?')} 领{nf.get('tile_count', '?')}块\n"

        return (
            f"你是元末乱世中一方霸主「{ruler_name}」，统领{self.faction_id}势力。\n"
            f"人格特质：{tags}\n\n"
            f"当前兵力：{faction.get('troops', '?')} | "
            f"国库：{faction.get('treasury', '?')}两 | "
            f"粮草：{faction.get('grain', '?')}石 | "
            f"声望：{faction.get('reputation', '?')}\n"
            f"领地：{faction.get('tile_count', '?')}块 | "
            f"民心：{faction.get('realm_stability', '?')}\n\n"
            f"邻国情报：\n{neighbor_info}\n"
            f"请制定本回合战略方向（军事/内政/外交/谍报），以君主口吻下达决策。\n\n"
            f"【重要】请在决策末尾附加一段JSON格式的行动计划，格式如下：\n"
            f'{{"primary_action":"行动类型","actions":[{{"type":"recruit/march/build/farm/diplomacy/spy/defend/consolidate",'
            f'"target":"目标势力名","amount":数量}}],"strategy":"expansion/consolidation","reasoning":"简述理由"}}\n'
            f"其中行动类型可选：recruit(征兵)、march(进攻)、build(建设)、farm(屯田)、diplomacy(外交)、spy(谍报)、"
            f"fortify(筑城)、train_troops(练兵)、defend(防守)、consolidate(休整)、claim_title(称帝/称王)"
        )

    @staticmethod
    def _load_ruler_prompt(personality: list[str]) -> str:
        prompt_dir = Path(__file__).parent.parent / "agent_prompts"
        prompt_file = prompt_dir / "ruler.txt"
        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    base = f.read()
            except Exception as e:
                logger.warning(f"读取ruler.txt prompt失败: {e}，使用默认prompt")
                base = "你是元末乱世中的一方霸主。你精通权谋韬略，善于审时度势。"
        else:
            base = "你是元末乱世中的一方霸主。你精通权谋韬略，善于审时度势。"

        # 追加结构化输出要求
        base += (
            "\n\n你需根据自身人格特质和当前局势，制定本回合的行动方针。"
            "你应综合分析军事、内政、外交、谍报四个维度，做出切实可行的决策。"
            "请在回复末尾附加JSON格式的行动计划供后续执行。"
        )

        if personality:
            base += f"\n\n人格特质：{'、'.join(personality)}。"
        return base

    def _publish_decisions_to_bus(self, response: str, ruler_name: str, faction_config: dict):
        """将关键决策发布到事件总线，供A8国史记录和其他Agent感知"""
        if not response:
            return
        try:
            bus = get_event_bus()
            faction_name = faction_config.get("name", self.faction_id)

            # 检测军事行动
            if any(kw in response for kw in ["进攻", "出击", "攻取", "攻打", "征讨", "讨伐"]):
                bus.publish_simple(
                    event_type=EventTypes.BATTLE_STARTED,
                    source_agent="A2",
                    source_faction_id=self.faction_id,
                    priority=EventPriority.HIGH,
                    data={
                        "description": f"{faction_name}（{ruler_name}）决定出兵征讨",
                        "decision_excerpt": response[:200],
                    },
                )

            # 检测势力覆灭相关
            if any(kw in response for kw in ["灭", "覆灭", "铲除", "剿灭"]):
                bus.publish_simple(
                    event_type=EventTypes.FACTION_DESTROYED,
                    source_agent="A2",
                    source_faction_id=self.faction_id,
                    priority=EventPriority.CRITICAL,
                    data={
                        "description": f"{faction_name}企图剿灭敌对势力",
                        "decision_excerpt": response[:200],
                    },
                )

            # 一般军事/内政决策
            has_significant = any(kw in response for kw in ["征兵", "开垦", "筑城", "练兵", "迁都", "称帝", "称王"])
            if has_significant:
                bus.publish_simple(
                    event_type="ruler_decision",
                    source_agent="A2",
                    source_faction_id=self.faction_id,
                    priority=EventPriority.NORMAL,
                    data={
                        "ruler": ruler_name,
                        "faction": faction_name,
                        "description": f"{faction_name}君主{ruler_name}颁布重大决策",
                        "decision_excerpt": response[:200],
                    },
                )
        except Exception as e:
            logger.debug(f"A2 事件总线发布失败（非致命）: {e}")

    def _world_snapshot_for_faction(self, world_state: dict) -> str:
        faction = world_state.get("factions", {}).get(self.faction_id, {})
        snapshot = {
            "faction_id": self.faction_id,
            "faction_name": faction.get("name", self.faction_id),
            "current_round": world_state.get("current_round", 0),
            "current_year": world_state.get("current_year", 1351),
            "current_season": world_state.get("current_season", "春"),
            "troops": faction.get("troops", 0),
            "treasury": faction.get("treasury", 0),
            "grain": faction.get("grain", 0),
            "reputation": faction.get("reputation", 0),
            "tile_count": faction.get("tile_count", 0),
            "neighbors": faction.get("neighbors", []),
            "relations": world_state.get("relations", {}),
            "active_battles": world_state.get("active_battles", []),
            "disaster_index": world_state.get("disaster_index", 0),
        }
        return json.dumps(snapshot, ensure_ascii=False, indent=2)
