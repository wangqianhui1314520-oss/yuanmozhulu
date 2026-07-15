"""
AgentOrchestrator - 八大智能体统一调度入口

职责:
1. 管理 A1~A8 所有智能体实例的创建与生命周期
2. 区分手动前端调用 Agent 与后端自动回合驱动 Agent
3. 三套模型配置分组绑定对应 Agent
4. 支持配置热更新，服务不重启即可切换大模型
5. 所有LLM调用统一经过 safe_step（含重试+熔断+日志）
6. 集成事件总线，实现跨智能体消息通知
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

from .base import BaseAgent, AgentCategory
from .agent_config import AgentConfigManager, get_agent_config_manager
from .agent_event_bus import AgentEventBus, get_event_bus, reset_event_bus

# A1~A8 智能体
from .a1_advisor import A1AdvisorAgent
from .a2_warlord import A2WarlordAgent
from .a3_law import A3LawAgent
from .a4_espionage import A4EspionageAgent
from .a5_event import A5EventAgent
from .a6_diplomacy import A6DiplomacyAgent
from .a7_royal import A7RoyalAgent
from .a8_history import A8HistoryAgent

logger = logging.getLogger("yuanmo.agent.orchestrator")

# 批量执行默认并发数
BATCH_CONCURRENCY = 20


class AgentOrchestrator:
    """
    八大智能体统一调度器

    === 模型分组绑定 ===
    advisor (chat_role)  → A1 谋策 / A2 群雄 / A3 律法 / A7 宗室
    law     (chat_strategy) → A6 外交 / A8 国史
    enemy   (chat_fast)  → A4 谍报 / A5 事件

    === 触发方式区分 ===
    手动前端调用: A1 谋策 / A3 律法 / A5 事件(手动)
    后端自动回合:  A1 谋策(自动献策) / A2 群雄 / A4 谍报 / A5 事件(自动) / A6 外交 / A7 宗室 / A8 国史
    """

    def __init__(self, config_manager: Optional[AgentConfigManager] = None):
        self._config_manager = config_manager or get_agent_config_manager()
        self._clients: Optional[dict] = None

        # Agent实例缓存（按 faction_id 索引）
        self._a2_agents: dict[str, A2WarlordAgent] = {}   # 每势力一个君主Agent
        self._a4_agents: dict[str, A4EspionageAgent] = {} # 每势力一个谍报Agent
        self._a6_agents: dict[str, A6DiplomacyAgent] = {} # 每势力一个外交Agent

        # 单例Agent（无势力绑定）
        self._a5_agent = A5EventAgent()
        self._a8_agent = A8HistoryAgent()

        # 事件总线
        self._event_bus: Optional[AgentEventBus] = None

        # 统计
        self._total_calls = 0
        self._total_latency = 0.0

    @property
    def event_bus(self) -> AgentEventBus:
        """获取事件总线实例"""
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    # ============================================================
    # 配置热更新
    # ============================================================

    def reload_config(self):
        """热重载Agent配置"""
        self._config_manager.reload()
        # 将热更新应用到所有已创建的Agent实例
        all_agents = list(self._a2_agents.values()) + \
                     list(self._a4_agents.values()) + \
                     list(self._a6_agents.values()) + \
                     [self._a5_agent, self._a8_agent]
        for agent in all_agents:
            key = f"A{agent.category.value[1]}"
            override = self._config_manager.get_override(key)
            if override:
                agent.apply_model_override(override)
        logger.info("所有Agent实例已应用热更新配置")

    def check_config_reload(self):
        """检查配置文件变化并热更新"""
        if self._config_manager.reload_if_changed():
            self.reload_config()

    # ============================================================
    # 手动前端调用接口（暴露给 API 层）
    # ============================================================

    async def a1_strategic_advice(
        self, faction_id: str, question: str, world_state: dict, clients: dict,
        npc_id: str = "", conversation_history: list = None,
    ) -> dict:
        """
        A1 谋策阁 - 谋臣献策（手动前端调用）

        支持两种模式：
        1. 通用模式（npc_id=""）：首席谋臣回答问题
        2. NPC对话模式（npc_id 指定）：与具体 NPC 文臣对话

        Args:
            faction_id: 玩家势力ID
            question: 玩家提问
            world_state: 世界状态
            clients: LLM客户端
            npc_id: NPC ID（可选）
            conversation_history: 对话历史（可选）
        """
        self.check_config_reload()
        agent = A1AdvisorAgent(faction_id=faction_id)
        override = self._config_manager.get_override("A1")
        if override:
            agent.apply_model_override(override)

        snapshot = {
            "faction_id": faction_id,
            "question": question,
            "world_state": world_state,
            "npc_id": npc_id,
            "conversation_history": conversation_history,
        }
        start = time.time()
        result = await agent.safe_step(snapshot, clients)
        self._record_call(time.time() - start)
        return result

    async def a1_court_debate(
        self, faction_id: str, topic: str, world_state: dict, clients: dict,
        npc_ids: list[str] = None,
    ) -> dict:
        """A1 廷议辩论（手动前端调用）- 使用增强版多NPC廷议"""
        self.check_config_reload()
        agent = A1AdvisorAgent(faction_id=faction_id)
        override = self._config_manager.get_override("A1")
        if override:
            agent.apply_model_override(override)

        return await agent.court_debate_multi(
            topic=topic,
            faction_id=faction_id,
            world_state=world_state,
            clients=clients,
            npc_ids=npc_ids,
        )

    async def a1_auto_advice(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        A1 谋策阁 - 每回合自动为玩家势力献策（后端自动驱动）

        此方法在每回合自动推演中被调用，为玩家势力提供策略建议。
        玩家专属智囊，始终为玩家势力服务。
        """
        self.check_config_reload()
        agent = A1AdvisorAgent(faction_id=faction_id)
        override = self._config_manager.get_override("A1")
        if override:
            agent.apply_model_override(override)

        start = time.time()
        result = await agent.run_single_faction(faction_id, world_state, clients)
        self._record_call(time.time() - start)
        return result

    async def a3_interrogate(
        self, faction_id: str, prisoner_name: str, question: str,
        world_state: dict, clients: dict
    ) -> dict:
        """
        A3 律法堂 - 审讯对话（手动前端调用）
        """
        self.check_config_reload()
        agent = A3LawAgent(faction_id=faction_id)
        override = self._config_manager.get_override("A3")
        if override:
            agent.apply_model_override(override)

        snapshot = {
            "faction_id": faction_id,
            "prisoner_name": prisoner_name,
            "question": question,
            "world_state": world_state,
        }
        start = time.time()
        result = await agent.safe_step(snapshot, clients)
        self._record_call(time.time() - start)
        return result

    async def a3_judge_case(
        self, case_description: str, defendant: str, evidence: list[str],
        faction_id: str, clients: dict
    ) -> dict:
        """A3 案件审理（手动前端调用）"""
        agent = A3LawAgent(faction_id=faction_id)
        return await agent.judge_case(case_description, defendant, evidence, faction_id, clients)

    async def a5_generate_events(
        self, round_num: int, season: str, disaster_index: int,
        world_state: dict, clients: dict
    ) -> dict:
        """
        A5 司天台 - 随机事件生成（手动前端调用）
        """
        self.check_config_reload()
        override = self._config_manager.get_override("A5")
        if override:
            self._a5_agent.apply_model_override(override)

        snapshot = {
            "round": round_num,
            "season": season,
            "disaster_index": disaster_index,
            "world_state": world_state,
        }
        start = time.time()
        result = await self._a5_agent.safe_step(snapshot, clients)
        self._record_call(time.time() - start)
        return result

    async def a5_roll_event(self) -> Optional[str]:
        """A5 本地概率判定事件触发"""
        return self._a5_agent.roll_event()

    async def a8_write_biography(
        self, faction_id: str, ruler_name: str, world_state: dict, clients: dict
    ) -> dict:
        """A8 国史馆 - 撰写君主结局传记（手动前端调用）"""
        self.check_config_reload()
        override = self._config_manager.get_override("A8")
        if override:
            self._a8_agent.apply_model_override(override)
        return await self._a8_agent.write_biography(faction_id, ruler_name, world_state, clients)

    # ============================================================
    # 后端自动回合驱动（内部调用）
    # ============================================================

    async def run_full_auto_step(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",  # 玩家势力ID（A2 RulerAgent强制休眠）
    ) -> dict:
        """
        完整自动推演一回合（后端自动驱动）

        执行顺序:
        1. A1 谋策 → 为玩家势力自动献策
        2. A2 群雄 ×N → asyncio.gather() 并发（跳过skip_faction_id）
        3. A4 谍报 → 串行细作步（跳过玩家势力自动谍报）
        4. A6 外交 → 串行外交步（跳过玩家势力自动外交）
        5. A5 事件 → 自动事件触发 + 分势力影响计算
        6. A7 宗室 → 串行宗室管理（跳过玩家势力宫变决策）
        7. A8 国史 → 国史记录 + 事件总线消费
        """
        self.check_config_reload()
        self._clients = clients

        # 初始化事件总线
        round_num = world_state.get("current_round", 0)
        self.event_bus.set_round(round_num)

        summary = {
            "round": round_num,
            "phases": {},
            "skip_faction_id": skip_faction_id,
        }

        # ============================================================
        # 并发优化：将无依赖的阶段合并为并发组，大幅缩减回合耗时
        #
        # 组1（并发）: A1 谋策 + A2 群雄（两者无数据依赖）
        # 组2（并发）: A4 谍报 + A6 外交 + A5 事件 + A7 宗室（互相独立）
        # 组3（串行）: A8 国史（依赖前序所有阶段的结果）
        # ============================================================

        # --- 组1: A1 + A2 并发 ---
        logger.info(f"=== [Orchestrator] 组1并发: A1谋策 + A2群雄 (skip={skip_faction_id}) ===")
        a1_task = None
        if skip_faction_id:
            a1_task = asyncio.ensure_future(self.a1_auto_advice(skip_faction_id, world_state, clients))
        a2_task = asyncio.ensure_future(self._phase_a2_warlords(world_state, faction_configs, clients, skip_faction_id))

        # 等待组1完成
        if a1_task:
            try:
                summary["phases"]["A1_advisor"] = await a1_task
            except Exception as e:
                logger.error(f"A1 自动献策失败: {e}")
                summary["phases"]["A1_advisor"] = {"error": str(e), "status": "failed"}
        else:
            summary["phases"]["A1_advisor"] = {"skipped": True, "reason": "无玩家势力"}

        ruler_results = await a2_task
        summary["phases"]["A2_warlords"] = {
            "agents_ran": len(ruler_results),
            "results": ruler_results,
        }

        # --- 组2: A4 + A6 + A5 + A7 并发 ---
        logger.info(f"=== [Orchestrator] 组2并发: A4谍报 + A6外交 + A5事件 + A7宗室 (skip={skip_faction_id}) ===")
        a4_task = asyncio.ensure_future(self._phase_a4_espionage(world_state, clients, skip_faction_id))
        a6_task = asyncio.ensure_future(self._phase_a6_diplomacy(world_state, faction_configs, clients, skip_faction_id))
        a5_task = asyncio.ensure_future(self._phase_a5_auto_event_enhanced(world_state, clients))
        a7_task = asyncio.ensure_future(self._phase_a7_royal_enhanced(world_state, faction_configs, clients, skip_faction_id))

        summary["phases"]["A4_espionage"] = await a4_task
        summary["phases"]["A6_diplomacy"] = await a6_task
        summary["phases"]["A5_events"] = await a5_task
        summary["phases"]["A7_royal"] = await a7_task

        # --- 组3: A8 国史（依赖前序事件总线数据）---
        logger.info("=== [Orchestrator] 组3: A8 国史记录 + 事件总线消费 ===")
        history_result = await self._phase_a8_history_enhanced(world_state, clients)
        summary["phases"]["A8_history"] = history_result

        # 消费事件总线中所有待处理事件
        bus_events = await self.event_bus.flush()
        summary["phases"]["event_bus"] = {
            "events_processed": len(bus_events),
            "event_types": list(set(e.event_type for e in bus_events)),
        }

        logger.info(f"[Orchestrator] 全自动推演完成 (round={summary['round']}, events={len(bus_events)})")
        return summary

    # ============================================================
    # 各阶段实现
    # ============================================================

    async def _phase_a2_warlords(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> list[dict]:
        """A2 群雄 - 所有存活君主并发推演（跳过玩家势力）"""
        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id  # 核心规则：跳过玩家势力
        }

        async def ruler_step(faction_id: str, config: dict) -> dict:
            agent = self._a2_agents.get(faction_id)
            if agent is None:
                agent = A2WarlordAgent(faction_id=faction_id)
                self._a2_agents[faction_id] = agent

            override = self._config_manager.get_override("A2")
            if override:
                agent.apply_model_override(override)

            snapshot = {
                "faction_id": faction_id,
                "faction_config": config,
                "world_state": world_state,
            }
            # 2026-07-15 修复: 添加30秒超时，防止单个AI调用拖累整组并发
            try:
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[A2] {faction_id} safe_step 超时(30s)，使用降级")
                return {
                    "faction_id": faction_id,
                    "error": "timeout",
                    "status": "fallback",
                    "decision_summary": "（AI超时，使用规则降级）",
                }

        tasks = [ruler_step(fid, cfg) for fid, cfg in living.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"A2 群雄异常: {r}")
                cleaned.append({
                    "faction_id": list(living.keys())[i] if i < len(living) else "?",
                    "error": str(r),
                    "status": "failed",
                })
            else:
                cleaned.append(r)

        return cleaned

    async def _phase_a4_espionage(
        self, world_state: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """A4 谍报 - 并发处理所有细作网络（跳过玩家势力：不会自主派遣细作）"""
        # 并发时每个网络使用独立 agent 实例，避免状态竞争
        override = self._config_manager.get_override("A4")

        spy_networks = world_state.get("spy_networks", {})

        async def _one_network(net_id: str, net_data) -> dict:
            try:
                owner = net_data.get("owner_faction", "") if isinstance(net_data, dict) else getattr(net_data, "owner_faction", "")
                if skip_faction_id and owner == skip_faction_id:
                    return {"network_id": net_id, "status": "skipped", "reason": "player_faction"}
                agent = A4EspionageAgent(faction_id=owner)
                if override:
                    agent.apply_model_override(override)
                snapshot = {
                    "network_id": net_id,
                    "network_data": net_data,
                    "world_state": world_state,
                }
                # 2026-07-15: 添加20秒超时
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A4 细作网络 {net_id} 超时(20s)")
                return {"network_id": net_id, "status": "timeout", "error": "timeout"}
            except Exception as e:
                logger.error(f"A4 细作网络 {net_id} 处理失败: {e}")
                return {"network_id": net_id, "error": str(e), "status": "failed"}

        tasks = []
        net_ids = []
        for net_id, net_data in spy_networks.items():
            tasks.append(_one_network(net_id, net_data))
            net_ids.append(net_id)

        if not tasks:
            return {"networks_processed": 0, "results": []}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                nid = net_ids[i] if i < len(net_ids) else "?"
                logger.error(f"A4 细作网络 {nid} 异常: {r}")
                cleaned.append({"network_id": nid, "error": str(r), "status": "failed"})
            else:
                cleaned.append(r)

        return {"networks_processed": len(cleaned), "results": cleaned}

    async def _phase_a6_diplomacy(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """A6 外交 - 并发处理所有势力外交（跳过玩家势力：不会主动发起结盟/宣战）"""
        override = self._config_manager.get_override("A6")

        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id
        }

        async def _one_faction(faction_id: str) -> dict:
            try:
                agent = A6DiplomacyAgent(faction_id=faction_id)
                if override:
                    agent.apply_model_override(override)
                snapshot = {
                    "faction_id": faction_id,
                    "world_state": world_state,
                }
                # 2026-07-15: 添加20秒超时
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A6 外交推演 {faction_id} 超时(20s)")
                return {"faction_id": faction_id, "status": "timeout", "error": "timeout"}
            except Exception as e:
                logger.error(f"A6 外交推演 {faction_id} 失败: {e}")
                return {"faction_id": faction_id, "error": str(e), "status": "failed"}

        tasks = [_one_faction(fid) for fid in living]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        faction_ids = list(living.keys())
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                fid = faction_ids[i] if i < len(faction_ids) else "?"
                logger.error(f"A6 外交推演 {fid} 异常: {r}")
                cleaned.append({"faction_id": fid, "error": str(r), "status": "failed"})
            else:
                cleaned.append(r)

        return {"factions_processed": len(cleaned), "results": cleaned}

    async def _phase_a5_auto_event(
        self, world_state: dict, clients: dict
    ) -> dict:
        """A5 事件 - 自动事件触发（兼容旧接口）"""
        override = self._config_manager.get_override("A5")
        if override:
            self._a5_agent.apply_model_override(override)

        # 先本地骰子判定
        event_type = self._a5_agent.roll_event()
        if event_type is None:
            return {"narrative": "天象平和，无灾异。", "event_triggered": False}

        # 再LLM生成事件叙事
        snapshot = {
            "round": world_state.get("current_round", 0),
            "season": world_state.get("current_season", "春"),
            "disaster_index": world_state.get("disaster_index", 0),
            "world_state": world_state,
        }
        result = await self._a5_agent.safe_step(snapshot, clients)
        result["event_triggered"] = True
        result["event_type"] = event_type
        return result

    async def _phase_a5_auto_event_enhanced(
        self, world_state: dict, clients: dict
    ) -> dict:
        """A5 事件 - 增强版：全局事件 + 分势力影响计算"""
        override = self._config_manager.get_override("A5")
        if override:
            self._a5_agent.apply_model_override(override)

        # 2026-07-15: 添加20秒超时
        try:
            return await asyncio.wait_for(
                self._a5_agent.run_all_factions(world_state, clients),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            logger.warning("A5 事件推演超时(20s)")
            return {"events": [], "narrative": "天象平和，无灾异。", "status": "timeout"}

    async def _phase_a7_royal(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """A7 宗室 - 串行处理各势力宗室（兼容旧接口，跳过玩家势力）"""
        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id
        }

        results = []
        for faction_id in living:
            agent = A7RoyalAgent(faction_id=faction_id)
            override = self._config_manager.get_override("A7")
            if override:
                agent.apply_model_override(override)

            snapshot = {
                "faction_id": faction_id,
                "world_state": world_state,
                "heirs": world_state.get("factions", {}).get(faction_id, {}).get("heirs", []),
            }
            try:
                result = await agent.safe_step(snapshot, clients)
                results.append(result)
            except Exception as e:
                logger.error(f"A7 宗室 {faction_id} 失败: {e}")
                results.append({"faction_id": faction_id, "error": str(e), "status": "failed"})

        return {"factions_processed": len(results), "results": results}

    async def _phase_a7_royal_enhanced(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """A7 宗室 - 增强版：并发处理所有势力宗室（各势力宗室互相独立，无数据依赖）"""
        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id  # 核心规则：跳过玩家势力（仅保留皇子自然成长）
        }

        async def _one_faction(faction_id: str) -> dict:
            agent = A7RoyalAgent(faction_id=faction_id)
            override = self._config_manager.get_override("A7")
            if override:
                agent.apply_model_override(override)
            try:
                # 2026-07-15: 添加20秒超时
                return await asyncio.wait_for(
                    agent.run_single_faction(faction_id, world_state, clients),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A7 宗室 {faction_id} 超时(20s)")
                return {"faction_id": faction_id, "status": "timeout", "error": "timeout"}
            except Exception as e:
                logger.error(f"A7 宗室 {faction_id} 失败: {e}")
                return {"faction_id": faction_id, "error": str(e), "status": "failed"}

        tasks = [_one_faction(fid) for fid in living]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                fid = list(living.keys())[i] if i < len(living) else "?"
                logger.error(f"A7 宗室 {fid} 异常: {r}")
                cleaned.append({"faction_id": fid, "error": str(r), "status": "failed"})
            else:
                cleaned.append(r)

        return {"factions_processed": len(cleaned), "results": cleaned}

    async def _phase_a8_history(
        self, world_state: dict, clients: dict
    ) -> dict:
        """A8 国史 - 记录本回合大事（兼容旧接口）"""
        override = self._config_manager.get_override("A8")
        if override:
            self._a8_agent.apply_model_override(override)

        # 收集本回合事件
        events = world_state.get("recent_events", []) or []

        snapshot = {
            "round": world_state.get("current_round", 0),
            "year": world_state.get("current_year", 1351),
            "season": world_state.get("current_season", "春"),
            "events": events,
            "world_state": world_state,
        }
        return await self._a8_agent.safe_step(snapshot, clients)

    async def _phase_a8_history_enhanced(
        self, world_state: dict, clients: dict
    ) -> dict:
        """A8 国史 - 增强版：整合事件总线 + 全局编年"""
        override = self._config_manager.get_override("A8")
        if override:
            self._a8_agent.apply_model_override(override)

        # 获取事件总线中本回合的事件
        bus_events = self.event_bus.get_archive(round_num=world_state.get("current_round", 0))

        # 使用增强的 run_round_chronicle 方法
        return await self._a8_agent.run_round_chronicle(world_state, clients, bus_events)

    # ============================================================
    # 自由对话接口（兼容旧 API）
    # ============================================================

    async def agent_chat(
        self, faction_id: str, user_message: str, chat_mode: str,
        world_state: Optional[dict] = None, clients: Optional[dict] = None,
    ) -> str:
        """
        自由对话接口 - 根据 chat_mode 路由到对应 Agent

        chat_mode 映射:
        - "ruler" / "minister" → A1 谋策
        - "commoner" / "law"   → A3 律法
        - "court"              → A1 廷议
        """
        if clients is None:
            clients = self._clients

        if chat_mode in ("commoner", "law"):
            # 律法审讯
            result = await self.a3_interrogate(
                faction_id=faction_id,
                prisoner_name="囚犯",
                question=user_message,
                world_state=world_state or {},
                clients=clients,
            )
            return result.get("verdict", result.get("response", ""))
        elif chat_mode == "court":
            # 廷议辩论
            result = await self.a1_court_debate(
                faction_id=faction_id,
                topic=user_message,
                world_state=world_state or {},
                clients=clients,
            )
            return result.get("debate_result", "")
        else:
            # 谋臣献策
            result = await self.a1_strategic_advice(
                faction_id=faction_id,
                question=user_message,
                world_state=world_state or {},
                clients=clients,
            )
            return result.get("response", "")

    # ============================================================
    # 统计与监控
    # ============================================================

    def _record_call(self, latency: float):
        self._total_calls += 1
        self._total_latency += latency

    def get_stats(self) -> dict:
        """获取所有Agent运行统计（含Token消耗）"""
        all_agents = list(self._a2_agents.values()) + \
                     list(self._a4_agents.values()) + \
                     list(self._a6_agents.values()) + \
                     [self._a5_agent, self._a8_agent]

        agent_stats = {}
        total_agent_tokens = 0
        for agent in all_agents:
            s = agent.get_stats()
            agent_stats[agent.agent_id] = s
            total_agent_tokens += s.get("total_tokens", 0)

        # 事件总线统计
        bus_stats = {
            "pending_events": len(self.event_bus._pending_events),
            "archived_events": len(self.event_bus._event_archive),
        }

        # Token 消耗汇总
        token_stats = {}
        if self._clients:
            for key in ("advisor", "law", "enemy"):
                client = self._clients.get(key)
                if client and hasattr(client, "get_token_stats"):
                    token_stats[key] = client.get_token_stats()

        return {
            "total_calls": self._total_calls,
            "avg_latency": round(self._total_latency / max(self._total_calls, 1), 3),
            "agent_count": len(all_agents),
            "agents": agent_stats,
            "token_stats": token_stats,
            "total_tokens_consumed": sum(
                ts.get("total_tokens", 0) for ts in token_stats.values()
            ),
            "event_bus": bus_stats,
            "config_version": self._config_manager.to_dict() if self._config_manager else {},
        }

    def _safe_get_agent_config(self, agent_key: str) -> dict:
        """安全获取Agent配置，防止 None.get_override() 崩溃"""
        try:
            agent_cfg = self._config_manager.get(agent_key)
            if agent_cfg is None:
                logger.warning(f"[Orchestrator] Agent {agent_key} 配置缺失，使用默认空配置")
                return {}
            return agent_cfg.get_override() or {}
        except Exception as e:
            logger.warning(f"[Orchestrator] Agent {agent_key} 配置读取异常: {e}")
            return {}

    def get_agent_list(self) -> list[dict]:
        """获取Agent列表（供前端展示）"""
        return [
            {
                "key": "A1",
                "name": "谋策阁",
                "model_group": "advisor",
                "trigger": "both",
                "description": "谋臣献策、廷议辩论、战略分析（每回合自动为玩家献策）",
                "player_only": True,
                "config": self._safe_get_agent_config("A1"),
            },
            {
                "key": "A2",
                "name": "群雄殿",
                "model_group": "advisor",
                "trigger": "auto",
                "description": "君主NPC自主推演、势力决策（玩家势力强制休眠）",
                "player_only": False,
                "config": self._safe_get_agent_config("A2"),
            },
            {
                "key": "A3",
                "name": "律法堂",
                "model_group": "advisor",
                "trigger": "manual",
                "description": "案件审理、律法判决、朝堂审讯（仅玩家手动触发）",
                "player_only": True,
                "config": self._safe_get_agent_config("A3"),
            },
            {
                "key": "A4",
                "name": "谍报司",
                "model_group": "enemy",
                "trigger": "both",
                "description": "细作行动、情报搜集、渗透破坏（玩家势力仅手动触发）",
                "player_only": False,
                "config": self._safe_get_agent_config("A4"),
            },
            {
                "key": "A5",
                "name": "司天台",
                "model_group": "enemy",
                "trigger": "both",
                "description": "天灾人祸、祥瑞异象、随机事件（全局生效）",
                "player_only": False,
                "config": self._safe_get_agent_config("A5"),
            },
            {
                "key": "A6",
                "name": "外交署",
                "model_group": "law",
                "trigger": "both",
                "description": "合纵连横、盟约谈判、外交文书（玩家势力仅手动触发）",
                "player_only": False,
                "config": self._safe_get_agent_config("A6"),
            },
            {
                "key": "A7",
                "name": "宗室府",
                "model_group": "advisor",
                "trigger": "auto",
                "description": "继承顺位、宗室管理、皇储培养（玩家势力仅保留皇子成长）",
                "player_only": False,
                "config": self._safe_get_agent_config("A7"),
            },
            {
                "key": "A8",
                "name": "国史馆",
                "model_group": "law",
                "trigger": "auto",
                "description": "史书修撰、结局传记、大事年表（全局编年）",
                "player_only": False,
                "config": self._safe_get_agent_config("A8"),
            },
        ]

    def reset_for_new_game(self):
        """新游戏开始时重置所有Agent状态"""
        self._a2_agents.clear()
        self._a4_agents.clear()
        self._a6_agents.clear()
        self._a5_agent = A5EventAgent()
        self._a8_agent = A8HistoryAgent()
        self._total_calls = 0
        self._total_latency = 0.0
        # 重置事件总线
        reset_event_bus()
        self._event_bus = get_event_bus()
        logger.info("AgentOrchestrator 已为新游戏重置")


# ============================================================
# 全局单例
# ============================================================

_global_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """获取全局调度器单例"""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
        logger.info("AgentOrchestrator 全局实例已创建")
    return _global_orchestrator
