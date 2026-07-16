"""
A9 军机处 - AI战报生成器

职责：将数值战斗结果转化为沉浸式古风战报叙事
模型分组: enemy (chat_fast)
触发方式: 后端自动 — 每次战斗结算后自动生成

核心设计：
- LLM 不决定战斗胜负（数值引擎负责），只负责叙事包装
- 输入为结构化战斗上下文，输出为古风战报文本
- 降级方案：规则模板文本（当前 _create_battle_event 的逻辑）
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from .base import BaseAgent, AgentCategory
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a9_battle_report")


class A9BattleReportAgent(BaseAgent):
    """A9 军机处 - AI战报生成智能体

    在数值引擎结算完成后调用，生成具有文学性的古风战报。
    LLM 不参与胜负判定，仅负责将已确定的战斗结果包装为叙事。
    """

    def __init__(self, agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or "A9_battle_report",
            category=AgentCategory.A9_BATTLE_REPORT,
            faction_id="",  # 全局单例，不绑定势力
            max_retries=2,
            retry_delay=1.0,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """A9 是后端事件触发型智能体，不参与主动决策循环。
        战报在实际战斗结算后由 generate() 生成。
        """
        return {"action": "none", "reason": "A9 由战斗事件驱动，非主动决策"}

    async def generate(self, battle_context: dict, clients: dict) -> str:
        """
        生成单场战斗的AI战报

        Args:
            battle_context: {
                "attacker_name": str,     # 攻方势力名
                "defender_name": str,     # 守方势力名
                "tile_name": str,         # 战场地名
                "terrain": str,           # 地形类型
                "season": str,            # 当前季节
                "attacker_troops": int,   # 攻方投入兵力
                "defender_troops": int,   # 守方投入兵力
                "attacker_losses": int,   # 攻方损失
                "defender_losses": int,   # 守方损失
                "attacker_remaining": int,# 攻方剩余
                "defender_remaining": int,# 守方剩余
                "result": str,            # "victory" | "defeat" | "stalemate"
                "winner_name": str,       # 胜方名（平局为空）
                "is_siege": bool,         # 是否为围城破城战
                "tile_captured": bool,    # 是否占领
                "fortification": int,     # 城防等级
                "engine": str,            # 结算引擎 "unit_counter" | "simple"
                "tactics_used": list,     # 使用的战术（如有）
                "power_ratio": float,     # 战力比（如有）
            }
            clients: LLM客户端字典

        Returns:
            古风战报叙事文本（约150-300字）
        """
        client: TencentHunyuanClient = clients.get("enemy", clients.get("advisor"))
        if not client:
            return self._fallback_narrative(battle_context)

        prompt = self._build_prompt(battle_context)

        try:
            response = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末军机处的战报撰写官。以精炼古风文笔撰写战报，"
                    "要求：① 必须如实反映胜败结果不得篡改；"
                    "② 描述战术细节（地形利用、兵种运用、关键转折）；"
                    "③ 提及双方将领可能的策略选择；"
                    "④ 语言要有《三国演义》《资治通鉴》的笔法；"
                    "⑤ 150-300字，以「军机处报：」开头。"
                ),
                temperature=0.75,
            )
            narrative = response.strip()
            if narrative and len(narrative) > 20:
                return narrative[:400]
        except Exception as e:
            logger.warning(f"A9 战报生成失败: {e}，使用模板降级")

        return self._fallback_narrative(battle_context)

    async def generate_batch(
        self, battles: list[dict], clients: dict
    ) -> list[dict]:
        """
        批量生成多场战斗的战报（并发）

        Args:
            battles: 多个 battle_context 的列表
            clients: LLM客户端

        Returns:
            [{"battle_index": int, "narrative": str}, ...]
        """
        import asyncio

        async def _one(battle: dict, idx: int) -> dict:
            narrative = await self.generate(battle, clients)
            return {"battle_index": idx, "narrative": narrative}

        tasks = [_one(b, i) for i, b in enumerate(battles)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"A9 批量战报[{i}]异常: {r}")
                cleaned.append({
                    "battle_index": i,
                    "narrative": self._fallback_narrative(battles[i]),
                })
            else:
                cleaned.append(r)

        return cleaned

    async def generate_war_summary(
        self, battles: list[dict], world_state: dict, clients: dict
    ) -> str:
        """
        v4.3 新增：在所有单场战报之后，生成全局「战局综述」
        
        与 generate_batch（单场战报）互补：
        - generate_batch: 每场战斗的独立叙事
        - generate_war_summary: 综合所有战斗，分析全局战局走势
        
        纯叙事，不影响游戏数值。
        
        Args:
            battles: 本回合所有战斗的 battle_context 列表
            world_state: 全局世界状态
            clients: LLM客户端
        
        Returns:
            古风战局综述文本（约200-350字）
        """
        if not battles:
            return "本回合天下无战事。"
        
        client: TencentHunyuanClient = clients.get("law", clients.get("advisor"))
        if not client:
            return self._fallback_war_summary(battles)
        
        round_num = world_state.get("current_round", 0)
        year = world_state.get("current_year", 1351)
        season = world_state.get("current_season", "春")
        
        # 汇总战斗数据
        battle_summary = ""
        total_attackers = set()
        total_defenders = set()
        victories = 0
        defeats = 0
        stalemates = 0
        
        for i, b in enumerate(battles, 1):
            att = b.get("attacker_name", "?")
            dfd = b.get("defender_name", "?")
            tile = b.get("tile_name", "某地")
            result = b.get("result", "unknown")
            terrain = b.get("terrain", "平原")
            
            total_attackers.add(att)
            total_defenders.add(dfd)
            
            if result == "victory":
                victories += 1
                result_text = f"{b.get('winner_name', att)}大胜"
            elif result == "defeat":
                defeats += 1
                result_text = "攻方败退"
            else:
                stalemates += 1
                result_text = "胶着未决"
            
            atk_loss = b.get("attacker_losses", 0)
            def_loss = b.get("defender_losses", 0)
            battle_summary += (
                f"  {i}. {att}攻{dfd}于{tile}({terrain}) — {result_text}，"
                f"攻损{atk_loss}守损{def_loss}\n"
            )
        
        total = victories + defeats + stalemates
        faction_summary = (
            f"参战方：攻方{', '.join(sorted(total_attackers))}；"
            f"守方{', '.join(sorted(total_defenders))}"
        )
        
        prompt = (
            f"=== 元末逐鹿 战局综述 ===\n"
            f"年份：{year}年 {season}，第{round_num}回合\n"
            f"本回合共{total}场战斗：{victories}胜 {defeats}败 {stalemates}平\n"
            f"{faction_summary}\n\n"
            f"【战斗详情】\n{battle_summary}\n"
            f"请以兵部尚书口吻，撰写本回合的《战局综述》，约200-300字。\n"
            f"需包含：\n"
            f"1. 本回合战局总体评价\n"
            f"2. 关键战役分析（哪场最重要、为什么）\n"
            f"3. 对下回合战局的预判（谁可能乘胜追击、谁需要休整）\n"
            f"语言风格：仿《三国演义》军师分析战局，古文雅致，洞若观火。"
        )
        
        try:
            response = await client.chat_strategy(
                prompt=prompt,
                world_json="{}",
                system_prompt=(
                    "你是元末乱世中的兵部尚书/军师，精通战略分析。"
                    "你善于从多场战役中提炼全局战局走势，"
                    "给出有见地的战略判断。语言精辟，洞见深刻。"
                ),
                temperature=0.6,
            )
            narrative = response.strip()
            if narrative and len(narrative) > 30:
                return narrative[:600]
        except Exception as e:
            logger.warning(f"A9 战局综述生成失败: {e}")
        
        return self._fallback_war_summary(battles)
    
    def _fallback_war_summary(self, battles: list[dict]) -> str:
        """战局综述规则模板降级"""
        if not battles:
            return "本回合天下无战事。"
        
        total = len(battles)
        victories = sum(1 for b in battles if b.get("result") == "victory")
        defeats = sum(1 for b in battles if b.get("result") == "defeat")
        
        parts = [f"军机处综述：本回合共发生{total}场战事。"]
        if victories:
            parts.append(f"攻方取胜{victories}场，")
        if defeats:
            parts.append(f"攻方败退{defeats}场，")
        parts.append("天下纷争不息。")
        
        return "".join(parts)

    def _build_prompt(self, ctx: dict) -> str:
        """构建战报生成提示词"""
        parts = [
            f"【战场】{ctx.get('tile_name', '某地')}（{ctx.get('terrain', '平原')}，{ctx.get('season', '春')}季）",
        ]

        # 围城还是野战
        if ctx.get("is_siege"):
            parts.append(
                f"【战役类型】围城破城战\n"
                f"【城防】{ctx.get('fortification', 0)}级城墙\n"
                f"【守军】{ctx.get('defender_troops', 0)}人据守"
            )
        else:
            parts.append("【战役类型】野战")

        # 双方兵力
        parts.append(
            f"【攻方】{ctx.get('attacker_name', '攻方')} "
            f"投入{ctx.get('attacker_troops', 0)}人"
        )
        parts.append(
            f"【守方】{ctx.get('defender_name', '守方')} "
            f"投入{ctx.get('defender_troops', 0)}人"
        )

        # 战术信息
        tactics = ctx.get("tactics_used", [])
        if tactics:
            parts.append(f"【战术】{', '.join(tactics)}")

        # 战力对比
        if ctx.get("power_ratio"):
            parts.append(f"【战力比】攻:守 = {ctx['power_ratio']:.1f}:1")

        # 结果
        result = ctx.get("result", "stalemate")
        winner_name = ctx.get("winner_name", "")
        if result == "victory":
            parts.append(
                f"【结果】{winner_name}大胜！\n"
                f"攻方折损{ctx.get('attacker_losses', 0)}人（余{ctx.get('attacker_remaining', 0)}），"
                f"守方覆灭{ctx.get('defender_losses', 0)}人"
            )
            if ctx.get("tile_captured"):
                parts.append(f"【占领】{winner_name}攻克{ctx.get('tile_name', '城池')}")
        elif result == "defeat":
            parts.append(
                f"【结果】攻方败退！\n"
                f"攻方折损{ctx.get('attacker_losses', 0)}人（余{ctx.get('attacker_remaining', 0)}），"
                f"守方折损{ctx.get('defender_losses', 0)}人（余{ctx.get('defender_remaining', 0)}）"
            )
        else:
            parts.append(
                f"【结果】鏖战未决！\n"
                f"攻方折损{ctx.get('attacker_losses', 0)}人（余{ctx.get('attacker_remaining', 0)}），"
                f"守方折损{ctx.get('defender_losses', 0)}人（余{ctx.get('defender_remaining', 0)}）"
            )

        parts.append("\n请撰写此战的军机处战报：")
        return "\n".join(parts)

    def _fallback_narrative(self, ctx: dict) -> str:
        """规则模板降级 — 保留原 _create_battle_event 的描述逻辑"""
        attacker = ctx.get("attacker_name", "攻方")
        defender = ctx.get("defender_name", "守方")
        tile = ctx.get("tile_name", "某地")
        result = ctx.get("result", "stalemate")
        atk_loss = ctx.get("attacker_losses", 0)
        def_loss = ctx.get("defender_losses", 0)
        atk_rem = ctx.get("attacker_remaining", 0)
        def_rem = ctx.get("defender_remaining", 0)
        terrain = ctx.get("terrain", "平原")
        season = ctx.get("season", "")

        season_text = f"时值{season}，" if season else ""

        if ctx.get("is_siege"):
            base = f"军机处报：{attacker}出兵围困{defender}之{tile}，"
            if result == "victory":
                return (
                    f"{base}城墙破损，强攻成功，攻克{tile}！"
                    f"守军{def_loss}人覆灭，攻方折损{atk_loss}人。"
                )
            elif result == "defeat":
                return (
                    f"{base}久攻不下，{defender}守军顽强抵抗，"
                    f"攻方折损{atk_loss}人败退。"
                )
            else:
                return (
                    f"{base}双方相持不下。攻方折损{atk_loss}人，"
                    f"守方折损{def_loss}人，围城继续。"
                )

        if result == "victory":
            return (
                f"军机处报：{season_text}{attacker}与{defender}战于{tile}（{terrain}），"
                f"大破之。斩首{def_loss}级，自损{atk_loss}人，"
                f"余部{atk_rem}人据守{tile}。"
            )
        elif result == "defeat":
            return (
                f"军机处报：{season_text}{attacker}攻{defender}之{tile}（{terrain}），"
                f"不利，折兵{atk_loss}人，余{atk_rem}人溃退。"
                f"{defender}守军折损{def_loss}人，余{def_rem}人。"
            )
        else:
            return (
                f"军机处报：{season_text}{attacker}与{defender}鏖战于{tile}（{terrain}），"
                f"双方胶着。攻方损{atk_loss}人（余{atk_rem}），"
                f"守方损{def_loss}人（余{def_rem}）。"
            )


# 全局单例
_global_a9_agent: Optional[A9BattleReportAgent] = None


def get_a9_battle_report_agent() -> A9BattleReportAgent:
    """获取A9战报生成器全局单例"""
    global _global_a9_agent
    if _global_a9_agent is None:
        _global_a9_agent = A9BattleReportAgent()
    return _global_a9_agent
