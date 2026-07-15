"""
A8 国史馆 - 史书修撰、结局传记、大事年表

模型分组: law (chat_strategy)
触发方式: 后端自动回合驱动（全局大事记，包含玩家势力所有操作归档）
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_event_bus import get_event_bus
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a8_history")


class A8HistoryAgent(BaseAgent):
    """A8 国史馆 - 国史编撰智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or "A8_history",
            category=AgentCategory.A8_HISTORY,
            faction_id=faction_id,
            max_retries=2,
            retry_delay=2.0,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        国史记录 - 记录本回合重大事件

        Args:
            world_snapshot: 含 round, year, events, world_state
        """
        client: TencentHunyuanClient = clients["law"]
        round_num = world_snapshot.get("round", 0)
        year = world_snapshot.get("year", 1351)
        season = world_snapshot.get("season", "春")
        events = world_snapshot.get("events", [])
        world_state = world_snapshot.get("world_state", {})

        # 构建事件摘要
        event_summary = ""
        for evt in events[:10]:
            event_summary += f"- {evt.get('description', str(evt))}\n"

        if not event_summary:
            event_summary = "本回合无重大事件。\n"

        prompt = (
            f"年份：{year}年 {season}（第{round_num}回合）\n"
            f"本回合大事：\n{event_summary}\n"
            f"请以史官笔法撰写本回合国史记录，约150-200字。"
        )

        temperature = (
            self._model_override.get("temperature", 0.5)
            if self._model_override else 0.5
        )

        response = await client.chat_strategy(
            prompt=prompt,
            world_json=json.dumps(world_state, ensure_ascii=False, indent=2),
            system_prompt=(
                "你是元末乱世的国史编修官，负责修撰国史。\n"
                "你需客观记录天下大事，笔法严谨，文采斐然。\n"
                "仿《资治通鉴》体例，纪事本末，以古文撰写。"
            ),
            temperature=temperature,
        )

        return {
            "agent_id": self.agent_id,
            "category": "A8_history",
            "round": round_num,
            "year": year,
            "season": season,
            "chronicle": response[:500],
        }

    async def run_single_faction(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        为指定势力编写本回合专史（单势力视角的编年记录）

        Args:
            faction_id: 目标势力ID
            world_state: 全局世界状态
            clients: LLM客户端

        Returns:
            {"faction_id": ..., "chronicle": ..., "round": ...}
        """
        faction = world_state.get("factions", {}).get(faction_id, {})
        if not faction:
            return {"faction_id": faction_id, "chronicle": "势力不存在", "round": 0}

        client: TencentHunyuanClient = clients["law"]
        round_num = world_state.get("current_round", 0)
        year = world_state.get("current_year", 1351)
        season = world_state.get("current_season", "春")

        # 收集该势力相关事件
        events = world_state.get("events_log", []) or []
        faction_events = []
        for evt in events[-10:]:
            evt_fid = evt.get("faction_id", "")
            evt_target = evt.get("target_faction", "")
            if evt_fid == faction_id or evt_target == faction_id:
                faction_events.append(evt)

        event_text = ""
        if faction_events:
            for evt in faction_events:
                event_text += f"- {evt.get('description', str(evt))}\n"
        else:
            event_text = "本回合该势力无特殊事件。\n"

        prompt = (
            f"势力：{faction.get('name', faction_id)}\n"
            f"年份：{year}年 {season}（第{round_num}回合）\n"
            f"领地：{faction.get('tile_count', 0)}块\n"
            f"兵力：{faction.get('troops', 0)}\n"
            f"本回合事件：\n{event_text}\n"
            f"请以史官笔法，为该势力撰写本回合纪事，约100-150字。"
        )

        try:
            response = await client.chat_strategy(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世的国史编修官，负责为各势力修撰专史。\n"
                    "仿《史记》笔法，客观记录，不偏不倚。"
                ),
                temperature=0.5,
            )
            chronicle = response[:400]
        except Exception as e:
            logger.warning(f"A8 LLM调用失败: {e}")
            chronicle = f"{year}年{season}，{faction.get('name', faction_id)}势力稳步发展。"

        return {
            "agent_id": self.agent_id,
            "category": "A8_history",
            "faction_id": faction_id,
            "faction_name": faction.get("name", faction_id),
            "round": round_num,
            "year": year,
            "season": season,
            "chronicle": chronicle,
            "event_count": len(faction_events),
        }

    async def run_round_chronicle(
        self, world_state: dict, clients: dict, event_bus_events: Optional[list] = None
    ) -> dict:
        """
        全局回合编年记录（整合事件总线中的所有事件）

        Args:
            world_state: 全局世界状态
            clients: LLM客户端
            event_bus_events: 来自事件总线的事件列表

        Returns:
            {"round": ..., "chronicle": ..., "key_events": [...]}
        """
        client: TencentHunyuanClient = clients["law"]
        round_num = world_state.get("current_round", 0)
        year = world_state.get("current_year", 1351)
        season = world_state.get("current_season", "春")

        # 收集所有事件：优先从事件总线获取完整数据
        all_events = list(event_bus_events or [])

        # 补充从事件总线归档获取本回合事件（确保完整性）
        try:
            bus = get_event_bus()
            archived = bus.get_archive(round_num=round_num)
            all_events.extend(archived)
        except Exception as e:
            logger.debug(f"从事件总线获取归档失败 (round={round_num}): {e}")

        # 也收集 world_state 中的事件
        ws_events = world_state.get("events_log", []) or []
        events = world_state.get("recent_events", []) or []

        event_summary_parts = []
        # 事件总线事件（按优先级排序）
        for evt in all_events:
            if hasattr(evt, 'to_dict'):
                d = evt.to_dict()
                priority = d.get('priority', 'NORMAL')
                agent = d.get('source_agent', '?')
                evt_type = d.get('event_type', '?')
                desc = d.get('data', {}).get('description', '')
                prefix = "【急报】" if priority in ('HIGH', 'CRITICAL') else ""
                event_summary_parts.append(
                    f"{prefix}[{agent}] {evt_type}: {desc}"
                )
            elif isinstance(evt, dict):
                event_summary_parts.append(
                    f"[{evt.get('source_agent', '?')}] {evt.get('event_type', '?')}: "
                    f"{evt.get('data', {}).get('description', '')}"
                )

        # world_state 事件
        for evt in events[:5]:
            event_summary_parts.append(evt.get("description", str(evt)))

        # 去重并按重要性排序
        seen = set()
        unique_parts = []
        for p in event_summary_parts:
            key = p[:50]
            if key not in seen:
                seen.add(key)
                unique_parts.append(p)

        event_summary = "\n".join(f"- {p}" for p in unique_parts[:15])
        if not event_summary:
            event_summary = "本回合天下太平，无大事发生。"

        # 汇总势力概况
        faction_summary = ""
        factions = world_state.get("factions", {})
        living_factions = {
            fid: f for fid, f in factions.items() if f.get("alive", True)
        }
        for fid, fdata in living_factions.items():
            faction_summary += (
                f"  {fdata.get('name', fid)}: "
                f"兵{fdata.get('troops', 0)} "
                f"领{fdata.get('tile_count', 0)} "
                f"粮{fdata.get('grain', 0)}\n"
            )

        prompt = (
            f"=== 元末逐鹿 第{round_num}回合 ===\n"
            f"年份：{year}年 {season}\n\n"
            f"【天下大势】\n{faction_summary}\n"
            f"【本回合大事记】\n{event_summary}\n\n"
            f"请以国史编修官的身份，用古文撰写本回合的《国史纪要》，约200-300字。"
            f"需包含：天下形势概述、重要事件记录、势力消长。"
        )

        try:
            response = await client.chat_strategy(
                prompt=prompt,
                world_json=json.dumps(world_state, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是元末乱世的国史编修官，负责修撰《元末群雄逐鹿实录》。\n"
                    "你需客观记录天下大事，笔法严谨，文采斐然。\n"
                    "仿《资治通鉴》体例，纪事本末，以古文撰写。"
                ),
                temperature=0.5,
            )
            chronicle = response[:600]
        except Exception as e:
            logger.warning(f"A8 回合编年LLM调用失败: {e}")
            chronicle = f"{year}年{season}，群雄并立，天下纷争。第{round_num}回合。"

        return {
            "agent_id": self.agent_id,
            "category": "A8_history",
            "round": round_num,
            "year": year,
            "season": season,
            "chronicle": chronicle,
            "key_events_count": len(event_summary_parts),
            "living_factions": len(living_factions),
        }

    async def write_biography(
        self, faction_id: str, ruler_name: str, world_state: dict, clients: dict
    ) -> dict:
        """
        撰写君主结局传记

        Returns:
            {"biography": ..., "evaluation": ...}
        """
        client: TencentHunyuanClient = clients["law"]
        faction = world_state.get("factions", {}).get(faction_id, {})

        prompt = (
            f"为元末群雄「{ruler_name}」撰写结局传记。\n"
            f"势力：{faction_id}\n"
            f"最终领地：{faction.get('tile_count', 0)}块\n"
            f"最终兵力：{faction.get('troops', 0)}\n"
            f"声望：{faction.get('reputation', 0)}\n"
            f"是否存活：{faction.get('alive', False)}\n\n"
            f"请以史官笔法撰写传记，约300-400字，"
            f"包含生平、功过、评价。仿《史记》列传体例。"
        )

        response = await client.chat_strategy(
            prompt=prompt,
            world_json=json.dumps(world_state, ensure_ascii=False, indent=2),
            system_prompt=(
                "你是元末明初的史官，为《元末群雄传》修撰列传。\n"
                "笔法严谨，史论公允，仿《史记》体例。"
            ),
            temperature=0.5,
        )

        return {
            "faction_id": faction_id,
            "ruler": ruler_name,
            "biography": response[:600],
        }

    async def compile_annals(
        self, all_events: list[dict], start_year: int, end_year: int, clients: dict
    ) -> dict:
        """
        编撰大事年表

        Returns:
            {"annals": ..., "period_name": ...}
        """
        client: TencentHunyuanClient = clients["law"]
        event_text = ""
        for e in all_events[:20]:
            event_text += (
                f"- {e.get('year', '?')}年 {e.get('season', '')}: "
                f"{e.get('description', str(e))}\n"
            )

        prompt = (
            f"编撰{start_year}-{end_year}年大事年表。\n"
            f"主要事件：\n{event_text}\n"
            f"请以编年体格式整理，并为这一时期命名（如'至正中兴''群雄并起'等）。"
        )

        response = await client.chat_strategy(
            prompt=prompt,
            world_json="{}",
            system_prompt="你是国史编修官，负责修撰大事年表。",
            temperature=0.5,
        )

        # P3修复: 从 LLM 响应中提取时期名称，补全返回值 period_name 字段
        period_name = ""
        full_text = response[:800]
        # 尝试从响应中提取时期名称（常见格式："时期：XXX" / "可称为"XXX"" / "「XXX」"等）
        import re
        for pat in [r'[「「]([^」」]{2,8})[」」]', r'时期[：:]\s*[《「]?([^《」\n]{2,8})', r'称为[《「]?([^《」\n]{2,8})', r'命名[为：:]\s*[《「]?([^《」\n]{2,8})']:
            m = re.search(pat, full_text)
            if m:
                period_name = m.group(1).strip()
                break
        # 兜底：从事件中取首尾年份拼接
        if not period_name:
            period_name = f"{start_year}-{end_year}年大事"

        return {
            "start_year": start_year,
            "end_year": end_year,
            "annals": full_text,
            "period_name": period_name,
        }
