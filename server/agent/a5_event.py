"""
A5 司天台 - 随机事件生成：天灾人祸、祥瑞异象、流民起义

模型分组: enemy (chat_fast)
触发方式: 后端自动回合驱动 + 手动前端调用
核心规则: 天灾、流民、奇遇是全局世界随机事件，不分势力，正常生效
"""
from __future__ import annotations
import json
import logging
import random
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_event_bus import EventTypes, EventPriority, get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a5_event")


class A5EventAgent(BaseAgent):
    """A5 司天台 - 随机事件智能体"""

    EVENT_TYPES = [
        "天灾",    # 地震、洪水、旱灾、蝗灾
        "祥瑞",    # 祥云、麒麟、凤凰、黄河清
        "朝堂",    # 政变、弹劾、党争
        "武将",    # 反叛、投诚、单挑
        "流民",    # 起义、迁徙、瘟疫
        "隐士",    # 献策、归隐、传道
        "商贸",    # 商队、走私、市舶
        "边患",    # 蛮族入侵、倭寇
    ]

    # 天灾子类型
    DISASTER_TYPES = ["地震", "洪水", "旱灾", "蝗灾", "瘟疫", "暴雪", "台风"]

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A5_event",
            category=AgentCategory.A5_EVENT,
            faction_id=faction_id,
            max_retries=2,
            retry_delay=1.5,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        随机事件生成

        Args:
            world_snapshot: 含 round, season, disaster_index, world_state
        """
        client: TencentHunyuanClient = clients["enemy"]
        round_num = world_snapshot.get("round", 0)
        season = world_snapshot.get("season", "春")
        disaster_index = world_snapshot.get("disaster_index", 0)

        prompt = (
            f"当前回合：{round_num}，季节：{season}，灾厄指数：{disaster_index}。\n"
            f"请生成1-2条随机历史事件（天灾、朝堂轶事、武将反叛、流民起义、隐士献策等），"
            f"以邸报格式输出，每条约100字。"
        )

        temperature = (
            self._model_override.get("temperature", 0.7)
            if self._model_override else 0.7
        )

        response = await client.chat_fast(
            prompt=prompt,
            system_prompt="你是元末乱世的记录官，以古风邸报格式记录天下大事。",
            temperature=temperature,
        )

        return {
            "agent_id": self.agent_id,
            "category": "A5_event",
            "round": round_num,
            "season": season,
            "event_triggered": True,      # 与 run_all_factions() 保持一致
            "disaster_occurred": False,   # step() 路径不单独触发天灾
            "narrative": response[:600],  # 统一使用 narrative 字段名
            "events_text": response[:600],  # 保留旧字段名兼容
            "events": [{"type": "random", "description": response[:300]}],
            "affected_factions": [],       # step() 路径无分势力影响
            "ai_generated": True,
        }

    async def run_all_factions(
        self, world_state: dict, clients: dict,
        skip_faction_id: str = "",  # 天灾不分势力，但仍保留此参数以统一接口
    ) -> dict:
        """
        全局事件生成 + 分势力影响计算（核心接口）

        天灾/流民/奇遇是全局事件，但影响会落到具体势力头上。
        此方法生成事件后，计算对每个存活势力的影响。

        Args:
            world_state: 全局世界状态
            clients: LLM客户端
            skip_faction_id: 保留参数（天灾不分势力，但影响仍会涉及玩家势力）

        Returns:
            {"events": [...], "affected_factions": [...], "disaster_occurred": bool}
        """
        client: TencentHunyuanClient = clients["enemy"]
        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")
        disaster_index = world_state.get("disaster_index", 0)
        factions = world_state.get("factions", {})

        # 1. 骰子判定是否触发事件
        event_type = self.roll_event()
        if event_type is None:
            return {
                "narrative": "天象平和，无灾异。",
                "event_triggered": False,
                "events": [],
                "affected_factions": [],
                "round": round_num,
            }

        # 2. LLM生成事件叙事
        event_narrative = ""
        affected_factions = []
        disaster_occurred = False

        if event_type == "天灾":
            disaster_type = random.choice(self.DISASTER_TYPES)
            event_narrative = await self._generate_disaster_narrative(
                client, disaster_type, disaster_index, season
            )
            disaster_occurred = True

            # 天灾影响随机1-3个势力
            living_factions = [
                fid for fid, f in factions.items() if f.get("alive", True)
            ]
            affected_count = min(random.randint(1, 3), len(living_factions))
            affected = random.sample(living_factions, affected_count)

            for fid in affected:
                faction = factions.get(fid, {})
                # ★ v3.5: AI驱动影响计算（替代固定公式）
                impact = await self.calculate_disaster_impact_ai(
                    disaster_type, disaster_index, faction, event_narrative, clients
                )
                affected_factions.append({
                    "faction_id": fid,
                    "faction_name": faction.get("name", fid),
                    "disaster_type": disaster_type,
                    "grain_loss": impact.get("grain_loss", 0),
                    "population_loss": impact.get("population_loss", 0),
                    "troop_loss": impact.get("troop_loss", 0),
                    "reputation_change": impact.get("reputation_change", 0),
                })

            # 通知事件总线
            try:
                bus = get_event_bus()
                bus.publish_simple(
                    event_type=EventTypes.DISASTER_OCCURRED,
                    source_agent="A5",
                    priority=EventPriority.HIGH,
                    data={
                        "disaster_type": disaster_type,
                        "narrative": event_narrative,
                        "affected_factions": [a["faction_id"] for a in affected_factions],
                    },
                )
            except Exception as e:
                logger.debug(f"A5 事件总线通知失败（非致命）: {e}")

        elif event_type == "流民":
            event_narrative = await self._generate_refugee_narrative(client, season)
            # 流民影响所有边境势力
            living_factions = [
                fid for fid, f in factions.items() if f.get("alive", True)
            ]
            affected_count = min(random.randint(2, 4), len(living_factions))
            affected = random.sample(living_factions, affected_count)

            for fid in affected:
                faction = factions.get(fid, {})
                pop_change = random.randint(-500, 2000)
                affected_factions.append({
                    "faction_id": fid,
                    "faction_name": faction.get("name", fid),
                    "event_type": "流民",
                    "population_change": pop_change,
                    "grain_cost": abs(pop_change) // 10 if pop_change > 0 else 0,
                })

            try:
                bus = get_event_bus()
                bus.publish_simple(
                    event_type=EventTypes.REFUGEE_WAVE,
                    source_agent="A5",
                    priority=EventPriority.NORMAL,
                    data={
                        "narrative": event_narrative,
                        "affected_factions": [a["faction_id"] for a in affected_factions],
                    },
                )
            except Exception as e:
                logger.warning(f"发布事件到事件总线失败: {e}")

        else:
            # 其他事件类型：LLM生成叙事（传入 event_type 让LLM聚焦特定事件）
            event_narrative = await self._generate_typed_event_narrative(
                client, event_type, season, disaster_index
            )

            # 随机影响1个势力
            living_factions = [
                fid for fid, f in factions.items() if f.get("alive", True)
            ]
            if living_factions:
                fid = random.choice(living_factions)
                faction = factions.get(fid, {})
                affected_factions.append({
                    "faction_id": fid,
                    "faction_name": faction.get("name", fid),
                    "event_type": event_type,
                    "reputation_change": random.randint(-5, 10),
                })

        return {
            "event_triggered": True,
            "event_type": event_type,
            "narrative": event_narrative,
            "disaster_occurred": disaster_occurred,
            "affected_factions": affected_factions,
            "round": round_num,
            "season": season,
        }

    async def _generate_disaster_narrative(
        self, client: TencentHunyuanClient,
        disaster_type: str, disaster_index: int, season: str
    ) -> str:
        """生成天灾叙事"""
        try:
            prompt = (
                f"灾厄指数：{disaster_index}，季节：{season}。\n"
                f"本回合发生「{disaster_type}」。\n"
                f"请以钦天监口吻描述此次天灾的经过和影响，约100-150字。"
            )
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是钦天监，观测天象灾异。以古文描述灾情。",
                temperature=0.7,
            )
            return response[:300]
        except Exception as e:
            logger.warning(f"A5灾害叙事生成失败: {e}，使用默认叙事")
            return f"是{season}，{disaster_type}大作，民生凋敝。"

    async def _generate_typed_event_narrative(
        self, client: TencentHunyuanClient,
        event_type: str, season: str, disaster_index: int
    ) -> str:
        """为指定类型生成事件叙事（朝堂/武将/祥瑞/隐士/商贸/边患）"""
        try:
            prompt = (
                f"事件类型：{event_type}，季节：{season}，灾厄指数：{disaster_index}。\n"
                f"请以邸报格式描述此事件，约80-120字。"
            )
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是元末乱世的记录官，以古风邸报格式记录天下大事。",
                temperature=0.7,
            )
            return response[:250]
        except Exception as e:
            logger.warning(f"A5 {event_type}叙事生成失败: {e}，使用默认叙事")
            return f"{season}，{event_type}之变，天下为之震动。"

    async def _generate_refugee_narrative(
        self, client: TencentHunyuanClient, season: str
    ) -> str:
        """生成流民叙事"""
        try:
            prompt = (
                f"季节：{season}。\n"
                f"元末乱世，大批流民迁徙。请描述流民潮的起因和影响，约80-120字。"
            )
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt="你是记录元末乱世的史官。",
                temperature=0.7,
            )
            return response[:250]
        except Exception as e:
            logger.warning(f"A5流民叙事生成失败: {e}，使用默认叙事")
            return f"{season}，流民四起，百姓流离失所。"

    async def calculate_disaster_impact_ai(
        self, disaster_type: str, disaster_index: int,
        faction: dict, disaster_narrative: str,
        clients: dict,
    ) -> dict:
        """
        AI驱动天灾影响计算（替代固定公式）

        让LLM基于灾害叙事+势力状况，自主判断影响范围和程度。
        数值系统仅做上下界校验（不能为负，不能超过上限）。

        Args:
            disaster_type: 灾害类型
            disaster_index: 灾厄指数
            faction: 势力数据
            disaster_narrative: LLM生成的灾害叙事
            clients: LLM客户端

        Returns:
            {"grain_loss": int, "population_loss": int, "troop_loss": int,
             "reputation_change": int, "morale_change": int, "ai_reasoning": str}
        """
        client: TencentHunyuanClient = clients.get("enemy")
        if not client:
            return self._calculate_disaster_impact(disaster_type, disaster_index, faction)

        faction_name = faction.get("name", "某势力")
        base_grain = faction.get("grain", 1000)
        base_pop = faction.get("population", 5000)
        base_troops = faction.get("troops", 1000)
        tile_count = faction.get("tile_count", 5)
        has_granary = faction.get("has_granary", False)
        has_hospital = faction.get("has_hospital", False)

        prompt = (
            f"【灾害】{disaster_type}，灾厄指数{disaster_index}/20\n"
            f"【灾害叙事】{disaster_narrative[:200]}\n\n"
            f"【受灾势力】{faction_name}\n"
            f"- 粮草：{base_grain}石\n"
            f"- 人口：{base_pop}人\n"
            f"- 兵力：{base_troops}人\n"
            f"- 领地数：{tile_count}块\n"
            f"- 有粮仓：{'是' if has_granary else '否'}\n"
            f"- 有医馆：{'是' if has_hospital else '否'}\n\n"
            f"请根据上述信息，判断此灾害对该势力的具体影响数值。\n"
            f"考虑因素：灾害严重程度、势力准备程度（粮仓可减粮损、医馆可减人口损）、领地大小（大势力恢复力强）\n\n"
            f"输出格式（严格JSON，不要额外文字）：\n"
            f'{{"grain_loss": 数字, "population_loss": 数字, "troop_loss": 数字, '
            f'"reputation_change": 数字(-10到+5), "morale_change": 数字(-20到+5), '
            f'"reasoning": "对灾害影响的分析(50字内)"}}'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世的灾害评估官。根据灾害类型、严重程度和势力状况，"
                    "给出合理的数值影响。不要过于极端——最严重的灾害也不应超过势力"
                    "对应资源的30%。输出必须是合法JSON。"
                ),
                temperature=0.5,  # 较低温度保证数值合理性
            )

            ai_impact = self._parse_impact_json(raw)

            # 数值校验与边界裁剪
            validated = {
                "grain_loss": max(0, min(ai_impact.get("grain_loss", 0), int(base_grain * 0.3))),
                "population_loss": max(0, min(ai_impact.get("population_loss", 0), int(base_pop * 0.3))),
                "troop_loss": max(0, min(ai_impact.get("troop_loss", 0), int(base_troops * 0.3))),
                "reputation_change": max(-10, min(ai_impact.get("reputation_change", 0), 5)),
                "morale_change": max(-20, min(ai_impact.get("morale_change", 0), 5)),
                "ai_reasoning": ai_impact.get("reasoning", "AI评估"),
            }

            logger.info(
                f"A5 AI灾害影响 [{faction_name}][{disaster_type}]: "
                f"粮损{validated['grain_loss']} 人损{validated['population_loss']} "
                f"兵损{validated['troop_loss']} — {validated['ai_reasoning']}"
            )
            return validated

        except Exception as e:
            logger.warning(f"A5 AI灾害影响计算失败: {e}，降级到固定公式")
            fallback = self._calculate_disaster_impact(disaster_type, disaster_index, faction)
            fallback["ai_reasoning"] = "降级到固定公式"
            return fallback

    @staticmethod
    def _parse_impact_json(raw: str) -> dict:
        """解析LLM输出的影响JSON"""
        import re
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        json_match = re.search(
            r'\{"grain_loss".*\}', raw, re.DOTALL
        )
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {}

    @staticmethod
    def _calculate_disaster_impact(
        disaster_type: str, disaster_index: int, faction: dict
    ) -> dict:
        """计算天灾对势力的具体影响数值（固定公式降级）"""
        base_grain = faction.get("grain", 1000)
        base_pop = faction.get("population", 5000)
        base_troops = faction.get("troops", 1000)

        # 灾厄指数影响倍数
        multiplier = 0.5 + disaster_index * 0.05

        impact = {
            "grain_loss": 0,
            "population_loss": 0,
            "troop_loss": 0,
            "reputation_change": -random.randint(1, 5),
        }

        if disaster_type in ("洪水", "台风"):
            impact["grain_loss"] = int(base_grain * random.uniform(0.05, 0.15) * multiplier)
            impact["population_loss"] = int(base_pop * random.uniform(0.01, 0.05) * multiplier)
        elif disaster_type in ("旱灾", "蝗灾"):
            impact["grain_loss"] = int(base_grain * random.uniform(0.10, 0.30) * multiplier)
            impact["reputation_change"] = -random.randint(3, 8)
        elif disaster_type == "地震":
            impact["population_loss"] = int(base_pop * random.uniform(0.03, 0.10) * multiplier)
            impact["troop_loss"] = int(base_troops * random.uniform(0.01, 0.03) * multiplier)
        elif disaster_type == "瘟疫":
            impact["population_loss"] = int(base_pop * random.uniform(0.05, 0.15) * multiplier)
            impact["troop_loss"] = int(base_troops * random.uniform(0.02, 0.08) * multiplier)
        elif disaster_type == "暴雪":
            impact["grain_loss"] = int(base_grain * random.uniform(0.03, 0.10) * multiplier)
            impact["troop_loss"] = int(base_troops * random.uniform(0.01, 0.02) * multiplier)

        return impact

    async def generate_disaster(self, disaster_index: int, season: str, clients: dict) -> dict:
        """生成天灾事件"""
        client: TencentHunyuanClient = clients["enemy"]
        prompt = (
            f"灾厄指数：{disaster_index}，季节：{season}。\n"
            f"判定本回合是否发生天灾（地震/洪水/旱灾/蝗灾/瘟疫），"
            f"以古文描述灾情，约100-150字。"
        )
        response = await client.chat_fast(
            prompt=prompt,
            system_prompt="你是钦天监，观测天象灾异。",
            temperature=0.7,
        )
        return {
            "type": "disaster",
            "season": season,
            "disaster_index": disaster_index,
            "narrative": response[:300],
        }

    async def generate_omen(self, world_state: dict, clients: dict) -> dict:
        """生成祥瑞/凶兆"""
        client: TencentHunyuanClient = clients["enemy"]
        current_round = world_state.get("current_round", 0)
        prompt = (
            f"回合：{current_round}。\n"
            f"请随机生成一条祥瑞或凶兆（如：黄河清/地震/日食/彗星/麒麟现/凤凰鸣），"
            f"以钦天监口吻描述，约80字。"
        )
        response = await client.chat_fast(
            prompt=prompt,
            system_prompt="你是钦天监，观测天象异变。",
            temperature=0.8,
        )
        return {
            "type": "omen",
            "round": current_round,
            "narrative": response[:200],
        }

    async def analyze_world_situation(
        self, world_state: dict, clients: dict
    ) -> dict:
        """
        v4.3 新增：每回合生成「天下大势分析」（无论是否触发事件）
        
        与 run_all_factions（事件判定+影响计算）互补：
        - run_all_factions: 骰子判定 → 触发则计算影响
        - analyze_world_situation: 始终运行 → 生成战略观察报告
        
        纯叙事，不影响游戏数值。用于前端展示和A8国史参考。
        
        Args:
            world_state: 全局世界状态
            clients: LLM客户端
        
        Returns:
            {"narrative": str, "trends": [...], "round": int}
        """
        client: TencentHunyuanClient = clients.get("enemy")
        if not client:
            return {"narrative": "时局不明。", "trends": [], "round": world_state.get("current_round", 0)}
        
        round_num = world_state.get("current_round", 0)
        year = world_state.get("current_year", 1351)
        season = world_state.get("current_season", "春")
        disaster_index = world_state.get("disaster_index", 0)
        
        # 势力概况
        factions = world_state.get("factions", {})
        faction_summary = ""
        for fid, f in factions.items():
            if f.get("alive", True):
                faction_summary += (
                    f"  {f.get('name', fid)}: "
                    f"兵{f.get('troops', 0)} 领{f.get('tile_count', 0)} "
                    f"粮{f.get('grain', 0)} 声望{f.get('reputation', 0)}\n"
                )
        
        # 活跃战争
        wars = world_state.get("active_battles", []) or world_state.get("active_wars", []) or []
        war_summary = ""
        for w in wars[:5]:
            a_name = w.get("attacker_name", w.get("attacker", "?"))
            d_name = w.get("defender_name", w.get("defender", "?"))
            tile = w.get("tile_name", w.get("location", "某地"))
            war_summary += f"  {a_name} vs {d_name} 于{tile}\n"
        if not war_summary:
            war_summary = "  当前无活跃战事。\n"
        
        prompt = (
            f"=== 元末天下大势分析 ===\n"
            f"年份：{year}年 {season}，第{round_num}回合\n"
            f"灾厄指数：{disaster_index}/20\n\n"
            f"【群雄割据】\n{faction_summary}\n"
            f"【活跃战事】\n{war_summary}\n"
            f"请以军师/谋士口吻，撰写一份天下大势分析报告（约150-200字）。\n"
            f"需分析：当前谁强谁弱、潜在的战略转折点、预测下一回合最可能发生的冲突。\n"
            f"语言风格：仿《隆中对》或《出师表》，古文雅致但不晦涩。"
        )
        
        try:
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世中的隐士军师，洞察天下大势。"
                    "你善于从纷乱的信息中发现战略趋势，语言精辟入里。"
                ),
                temperature=0.7,
            )
            narrative = response[:500] if response else "天下大势，分久必合，合久必分。"
        except Exception as e:
            logger.warning(f"A5 天下大势分析LLM调用失败: {e}")
            narrative = f"{year}年{season}，群雄并立，天下未定。各方势力蓄势待发。"
        
        logger.info(f"A5 天下大势分析: 已生成 (round={round_num}, {len(narrative)}字)")
        
        return {
            "narrative": narrative,
            "round": round_num,
            "year": year,
            "season": season,
            "faction_count": sum(1 for f in factions.values() if f.get("alive", True)),
            "active_wars": len(wars),
        }

    def roll_event(self) -> Optional[str]:
        """
        骰子判定：是否触发事件（非LLM，本地概率判定）

        Returns:
            事件类型字符串，或None表示无事
        """
        roll = random.random()
        # 基础概率分布
        if roll < 0.15:
            return random.choice(["天灾", "边患"])
        elif roll < 0.30:
            return random.choice(["朝堂", "流民"])
        elif roll < 0.40:
            return random.choice(["武将", "商贸"])
        elif roll < 0.45:
            return random.choice(["祥瑞", "隐士"])
        return None
