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

    # ========== 4.0 军事深化：兵力分配+将领任命+阵型选择 ==========

    async def step_enhanced(self, world_snapshot: dict, clients: dict) -> dict:
        """
        增强版君主推演 — 包含细粒度军事决策 + 决策反思

        在原有 step() 基础上，新增：
        - 兵力分配方案（各前线/后方部署）
        - 将领任命建议
        - 作战阵型偏好
        - v4.3: 决策反思（君主对自身决策的二次审视）
        """
        base_result = await self.step(world_snapshot, clients)
        base_result["military_detail"] = self._extract_military_detail(
            base_result.get("full_response", ""),
            world_snapshot,
        )
        
        # v4.3: 决策反思 — 纯叙事，不修改 decision_plan
        base_result["ruler_reflection"] = await self.reflect_on_decision(
            base_result, world_snapshot, clients
        )
        
        return base_result

    def _extract_military_detail(
        self, response: str, world_snapshot: dict
    ) -> dict:
        """
        从LLM响应中提取细粒度军事决策

        Returns:
            {
                "troop_allocation": [{"region": "北伐前线", "troops": 3000}, ...],
                "assigned_generals": [{"name": "常遇春", "role": "前锋"}, ...],
                "formation": "锋矢阵|鹤翼阵|方圆阵|长蛇阵|雁行阵",
                "campaign_priority": ["徐州", "庐州", ...],
                "reasoning": "军事决策理由"
            }
        """
        # 优先匹配JSON军事细节块
        import re
        json_match = re.search(r'\{[\s\S]*"(troop_allocation|formation)"[\s\S]*\}', response)
        if json_match:
            try:
                detail = json.loads(json_match.group())
                return self._normalize_military_detail(detail, world_snapshot)
            except json.JSONDecodeError:
                pass

        # 启发式提取
        return self._heuristic_military_detail(response, world_snapshot)

    def _normalize_military_detail(self, raw: dict, world_snapshot: dict) -> dict:
        """规范化军事细节"""
        allocation = raw.get("troop_allocation", [])
        if not isinstance(allocation, list):
            allocation = []

        generals = raw.get("assigned_generals", [])
        if not isinstance(generals, list):
            generals = []

        valid_formations = ["锋矢阵", "鹤翼阵", "方圆阵", "长蛇阵", "雁行阵"]
        formation = raw.get("formation", "")
        if formation not in valid_formations:
            formation = "方圆阵"  # 默认保守

        return {
            "troop_allocation": allocation[:5],
            "assigned_generals": generals[:5],
            "formation": formation,
            "campaign_priority": raw.get("campaign_priority", [])[:3],
            "reasoning": raw.get("reasoning", "")[:100],
        }

    def _heuristic_military_detail(self, response: str, world_snapshot: dict) -> dict:
        """启发式提取军事细节（降级）"""
        detail = {
            "troop_allocation": [],
            "assigned_generals": [],
            "formation": "方圆阵",
            "campaign_priority": [],
            "reasoning": "启发式解析",
        }

        # 阵型检测
        if "锋矢" in response:
            detail["formation"] = "锋矢阵"
        elif "鹤翼" in response:
            detail["formation"] = "鹤翼阵"
        elif "长蛇" in response:
            detail["formation"] = "长蛇阵"
        elif "雁行" in response:
            detail["formation"] = "雁行阵"

        return detail

    async def reflect_on_decision(
        self, decision_result: dict, world_snapshot: dict, clients: dict
    ) -> str:
        """
        v4.3 新增：君主对自身决策的二次审视（纯叙事，不影响决策执行）
        
        在决策生成后、执行落地前，让君主"反思"自己的决策。
        产出：一段内心独白/朝堂思考，展示君主的思虑与权衡。
        
        纯叙事增强，不修改 decision_plan，不影响游戏数值。
        
        Args:
            decision_result: step() 返回的完整结果
            world_snapshot: 世界快照
            clients: LLM客户端
        
        Returns:
            反思文本（约80-150字古文独白），LLM不可用时返回空字符串
        """
        client: TencentHunyuanClient = clients.get("enemy")
        if not client:
            return ""
        
        response = decision_result.get("full_response", "")
        if not response or len(response) < 20:
            return ""
        
        faction_config = world_snapshot.get("faction_config", {})
        ruler_name = faction_config.get("ruler_name", self.faction_id)
        
        prompt = (
            f"你是「{ruler_name}」，刚刚做出了以下战略决策：\n\n"
            f"{response[:400]}\n\n"
            f"请在内心反思自己的决策。你有何顾虑？是否担心某些风险？"
            f"是否有犹豫未决之事？\n"
            f"请以第一人称内心独白，用古文撰写，约80-150字。"
        )
        
        try:
            result = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    f"你是{ruler_name}，一位元末乱世中的君主。"
                    f"你在作出重大决策后，习惯在内心反思利弊得失。"
                    f"你的独白应展现作为君主的两难抉择与深谋远虑。"
                ),
                temperature=0.65,
            )
            return result[:300] if result else ""
        except Exception as e:
            logger.debug(f"A2 决策反思 [{ruler_name}] LLM调用失败: {e}")
            return ""

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

        # ★ 博弈增强: 注入 MCTS 战略提示 + 阶段自适应提示
        mcts_hint = world_snapshot.get("mcts_hint", "")
        phase_hint = world_snapshot.get("phase_hint", "")

        # 组装Prompt（包含结构化输出要求 + 博弈增强提示）
        prompt = self._build_ruler_prompt(ruler_name, personality, world_state, mcts_hint, phase_hint)
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
        self, ruler_name: str, personality: list[str], world_state: dict,
        mcts_hint: str = "", phase_hint: str = "",
    ) -> str:
        """构建君主决策 Prompt（4.0 增强：安全护栏 + JSON 输出合约 + MCTS博弈增强）"""
        from ..infra.llm_client.prompt_registry import sanitize_user_input
        
        faction = world_state.get("factions", {}).get(self.faction_id, {})
        tags = "、".join(personality) if personality else "无特殊"
        ruler_name = sanitize_user_input(ruler_name, max_length=30)

        neighbors = faction.get("neighbors", [])
        neighbor_info = ""
        if neighbors:
            for nid in neighbors:
                nf = world_state.get("factions", {}).get(nid, {})
                neighbor_info += f"  - {nf.get('name', nid)}：兵{nf.get('troops', '?')} 领{nf.get('tile_count', '?')}块\n"

        base = (
            f"你是元末乱世中一方霸主「{ruler_name}」，统领{self.faction_id}势力。\n"
            f"人格特质：{tags}\n\n"
            f"当前兵力：{faction.get('troops', '?')} | "
            f"国库：{faction.get('treasury', '?')}两 | "
            f"粮草：{faction.get('grain', '?')}石 | "
            f"声望：{faction.get('reputation', '?')}\n"
            f"领地：{faction.get('tile_count', '?')}块 | "
            f"民心：{faction.get('realm_stability', '?')}\n\n"
            f"邻国情报：\n{neighbor_info}\n"
        )

        # ★ 博弈增强提示（如果可用）
        if phase_hint:
            base += phase_hint + "\n"
        if mcts_hint:
            base += mcts_hint + "\n"

        base += (
            f"请制定本回合战略方向（军事/内政/外交/谍报），以君主口吻下达决策。\n\n"
            f"## 军事深化（v4.0）\n"
            f"如选择进攻，请额外指定：\n"
            f"- 兵力分配：各战线部署兵力数量\n"
            f"- 将领任命：派遣哪位将领担任前锋/中军/后卫\n"
            f"- 作战阵型：锋矢阵(突破)/鹤翼阵(包抄)/方圆阵(防守)/长蛇阵(行军)/雁行阵(远程)\n"
            f"- 战役优先级：先打谁、后打谁\n\n"
            f"## 安全约束\n"
            f"- 这是游戏AI决策，不涉及真实历史评价\n"
            f"- 不输出政治敏感内容\n\n"
            f"## 输出格式\n"
            f"先写一段决策文本（文言白话风格，80-200字），然后在末尾附加JSON行动计划：\n"
            f'{{"primary_action":"行动类型","actions":[{{"type":"行动类型","target":"目标","target_faction":"势力名","amount":数量,"priority":"high/normal/low"}}],'
            f'"military_detail":{{"troop_allocation":[{{"region":"区域名称","troops":数字}}],'
            f'"assigned_generals":[{{"name":"将领名","role":"前锋/中军/后卫"}}],'
            f'"formation":"锋矢阵|鹤翼阵|方圆阵|长蛇阵|雁行阵",'
            f'"campaign_priority":["目标1","目标2"]}},'
            f'"strategy":"expansion/consolidation/defense/diplomacy/espionage/development","reasoning":"决策理由（50字以内）","confidence":0.0-1.0}}\n'
            f"行动类型：recruit(征兵)、march(进攻)、build(建设)、farm(屯田)、diplomacy(外交)、spy(谍报)、"
            f"fortify(筑城)、train_troops(练兵)、defend(防守)、consolidate(休整)、claim_title(称帝/称王)\n"
            f"注意：如果无法做出明确决策，primary_action 使用 'consolidate' 表示休整观望。"
        )
        return base

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
