"""
AgentOrchestrator - 十大智能体统一调度入口（v4.0）

职责:
1. 管理 A1~A10 所有智能体实例的创建与生命周期
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

# A1~A10 智能体
from .a1_advisor import A1AdvisorAgent
from .a2_warlord import A2WarlordAgent
from .a3_law import A3LawAgent
from .a4_espionage import A4EspionageAgent
from .a5_event import A5EventAgent
from .a6_diplomacy import A6DiplomacyAgent
from .a7_royal import A7RoyalAgent
from .a8_history import A8HistoryAgent
from .a9_battle_report import A9BattleReportAgent, get_a9_battle_report_agent
from .a10_treasury import A10TreasuryAgent, get_a10_treasury_agent

logger = logging.getLogger("yuanmo.agent.orchestrator")

# 批量执行默认并发数
BATCH_CONCURRENCY = 20


class AgentOrchestrator:
    """
    十大智能体统一调度器（v4.0）

    === 模型分组绑定 ===
    advisor (chat_role)  → A1 谋策 / A2 群雄 / A3 律法 / A7 宗室
    law     (chat_strategy) → A6 外交 / A8 国史 / A10 度支
    enemy   (chat_fast)  → A4 谍报 / A5 事件 / A9 战报

    === 触发方式区分 ===
    手动前端调用: A1 谋策 / A3 律法 / A5 事件(手动)
    后端自动回合:  A1 谋策(自动献策) / A2 群雄 / A3 吏部 / A4 谍报 / A5 事件(自动) / A6 外交 / A7 宗室 / A8 国史 / A9 战报(战斗后) / A10 度支(经济决策)
    """

    def __init__(self, config_manager: Optional[AgentConfigManager] = None):
        self._config_manager = config_manager or get_agent_config_manager()
        self._clients: Optional[dict] = None

        # Agent实例缓存（按 faction_id 索引）
        self._a1_agents: dict[str, A1AdvisorAgent] = {}   # 每势力一个谋策Agent
        self._a2_agents: dict[str, A2WarlordAgent] = {}   # 每势力一个君主Agent
        self._a3_agents: dict[str, A3LawAgent] = {}       # 每势力一个律法Agent
        self._a4_agents: dict[str, A4EspionageAgent] = {} # 每势力一个谍报Agent
        self._a6_agents: dict[str, A6DiplomacyAgent] = {} # 每势力一个外交Agent
        self._a7_agents: dict[str, A7RoyalAgent] = {}     # 每势力一个宗室Agent

        # 单例Agent（无势力绑定）
        self._a5_agent = A5EventAgent()
        self._a8_agent = A8HistoryAgent()
        self._a9_agent = get_a9_battle_report_agent()   # v3.5: AI战报生成器（使用全局单例）
        self._a10_agent = get_a10_treasury_agent()     # v4.0: AI度支司（使用全局单例）

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
        all_agents = list(self._a1_agents.values()) + \
                     list(self._a2_agents.values()) + \
                     list(self._a3_agents.values()) + \
                     list(self._a4_agents.values()) + \
                     list(self._a6_agents.values()) + \
                     list(self._a7_agents.values()) + \
                     [self._a5_agent, self._a8_agent, self._a9_agent, self._a10_agent]
        for agent in all_agents:
            key = f"A{agent.category.value.split('_')[0][1:]}"
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
        agent = self._a1_agents.get(faction_id)
        if agent is None:
            agent = A1AdvisorAgent(faction_id=faction_id)
            self._a1_agents[faction_id] = agent
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
        agent = self._a1_agents.get(faction_id)
        if agent is None:
            agent = A1AdvisorAgent(faction_id=faction_id)
            self._a1_agents[faction_id] = agent
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
        agent = self._a1_agents.get(faction_id)
        if agent is None:
            agent = A1AdvisorAgent(faction_id=faction_id)
            self._a1_agents[faction_id] = agent
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
        agent = self._a3_agents.get(faction_id)
        if agent is None:
            agent = A3LawAgent(faction_id=faction_id)
            self._a3_agents[faction_id] = agent
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
        agent = self._a3_agents.get(faction_id)
        if agent is None:
            agent = A3LawAgent(faction_id=faction_id)
            self._a3_agents[faction_id] = agent
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
    # A9 军机处 - AI战报生成（v3.5 新增）
    # ============================================================

    async def a9_generate_battle_report(
        self, battle_context: dict, clients: dict
    ) -> str:
        """
        A9 军机处 - 生成单场战斗的AI古风战报

        Args:
            battle_context: 战斗上下文（含双方势力、兵力、地形、结果等）
            clients: LLM客户端

        Returns:
            古风战报文本
        """
        return await self._a9_agent.generate(battle_context, clients)

    async def a9_generate_battle_reports_batch(
        self, battles: list[dict], clients: dict
    ) -> list[dict]:
        """
        A9 军机处 - 批量生成多场战斗的战报（并发）

        用于回合结束时，将本回合所有战斗的数值结果转化为战报。
        """
        return await self._a9_agent.generate_batch(battles, clients)

    # ============================================================
    # A6 外交署 - AI外交谈判（v3.5 新增）
    # ============================================================

    async def a6_diplomatic_negotiation(
        self, my_faction_id: str, target_faction_id: str,
        proposal: str, world_state: dict, clients: dict,
        negotiation_history: list = None,
    ) -> dict:
        """
        A6 外交署 - 玩家与AI势力的外交谈判

        支持多轮谈判：传入 negotiation_history 实现上下文延续。
        """
        agent = self._a6_agents.get(my_faction_id)
        if agent is None:
            agent = A6DiplomacyAgent(faction_id=my_faction_id)
            self._a6_agents[my_faction_id] = agent

        return await agent.negotiate(
            my_faction_id, target_faction_id, proposal,
            world_state, clients, negotiation_history,
        )

    async def a6_ai_to_ai_negotiation(
        self, faction_a_id: str, faction_b_id: str,
        world_state: dict, clients: dict,
    ) -> dict:
        """
        A6 外交署 - AI势力间外交谈判

        两个AI君主通过LLM进行外交对话，解决结盟/停战/纳贡等事务。
        """
        agent = A6DiplomacyAgent()
        return await agent.run_ai_negotiation(
            faction_a_id, faction_b_id, world_state, clients,
        )

    # ============================================================
    # A10 度支司 - AI经济决策（v4.0 新增）
    # ============================================================

    async def a10_formulate_economy_policy(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """A10 度支司 - 为单个势力制定经济政策"""
        return await self._a10_agent.formulate_policy(faction_id, world_state, clients)

    def a10_apply_policies(
        self, faction_id: str, world_state: dict, policy: dict
    ) -> dict:
        """A10 度支司 - 将经济政策落地（税收/粮储/建设）"""
        result = {"faction_id": faction_id}
        if "tax_rate" in policy:
            tax_income = self._a10_agent.apply_tax_policy(faction_id, world_state, policy["tax_rate"])
            result["tax_income"] = tax_income
        if "grain_allocation" in policy:
            result["grain"] = self._a10_agent.apply_grain_policy(
                faction_id, world_state, policy["grain_allocation"])
        if "construction" in policy:
            built = self._a10_agent.apply_construction_policy(
                faction_id, world_state, policy["construction"])
            result["built"] = built
        return result

    # ============================================================
    # A3 吏部 - AI官员任免（v4.0 新增）
    # ============================================================

    async def a3_manage_officials(
        self, faction_id: str, world_state: dict, clients: dict,
        npcs: list[dict] = None,
    ) -> dict:
        """A3 吏部 - 评估官员绩效，决定升迁降黜"""
        agent = self._a3_agents.get(faction_id)
        if agent is None:
            agent = A3LawAgent(faction_id=faction_id)
            self._a3_agents[faction_id] = agent
        return await agent.manage_officials(faction_id, world_state, clients, npcs)

    # ============================================================
    # A4 谍报司 - AI间谍策略（v4.0 新增）
    # ============================================================

    async def a4_plan_spy_strategy(
        self, faction_id: str, world_state: dict, clients: dict,
        available_spies: list[dict] = None,
    ) -> dict:
        """A4 谍报司 - 制定完整谍报计划"""
        agent = self._a4_agents.get(faction_id)
        if agent is None:
            agent = A4EspionageAgent(faction_id=faction_id)
            self._a4_agents[faction_id] = agent
        return await agent.plan_spy_strategy(
            faction_id, world_state, clients, available_spies)

    # ============================================================
    # A7 宗室府 - AI王朝管理（v4.0 新增）
    # ============================================================

    async def a7_manage_dynasty(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """A7 宗室府 - 储位人选、联姻决策、皇子历练"""
        agent = self._a7_agents.get(faction_id)
        if agent is None:
            agent = A7RoyalAgent(faction_id=faction_id)
            self._a7_agents[faction_id] = agent
        return await agent.manage_dynasty(faction_id, world_state, clients)

    # ============================================================
    # A2 群雄殿 - 军事深化（v4.0 新增）
    # ============================================================

    async def a2_step_enhanced(
        self, world_snapshot: dict, clients: dict
    ) -> dict:
        """
        A2 增强版君主推演 — 含兵力分配+将领任命+阵型选择
        由 step_with_agent 内部调用，降级到普通 step
        """
        agent = self._a2_agents.get(world_snapshot.get("faction_id", ""))
        if agent:
            return await agent.step_enhanced(world_snapshot, clients)
        # 降级
        agent = A2WarlordAgent(faction_id=world_snapshot.get("faction_id", ""))
        return await agent.step(world_snapshot, clients)

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
        0. 博弈增强 → 阶段检测 + MCTS预计算（注入后续阶段）
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
        # ★ 博弈增强层 (Phase 0): 阶段检测 + MCTS预计算
        # 在所有Agent调用之前运行，为后续阶段提供策略上下文
        # ============================================================
        from .game_phase_detector import get_phase_detector
        from .strategic_mcts import get_strategic_mcts, strategic_state_from_world
        from .agent_benchmark import get_performance_tracker

        phase_detector = get_phase_detector()
        phase_ctx = phase_detector.detect(world_state, faction_configs)
        summary["phases"]["game_phase"] = phase_ctx.to_dict()

        # MCTS预计算：为所有AI势力预计算战略搜索（在A2之前）
        mcts_results = {}
        mcts = get_strategic_mcts("fast")  # 快速模式，为A2保留更多时间
        factions = faction_configs.get("factions", {})
        for fid in factions:
            if fid == skip_faction_id:
                continue
            if not world_state.get("factions", {}).get(fid, {}).get("alive", True):
                continue
            try:
                state = strategic_state_from_world(fid, world_state)
                mcts_results[fid] = mcts.search(state)
            except Exception as e:
                logger.warning(f"MCTS预计算失败 {fid}: {e}")
                mcts_results[fid] = None
        summary["phases"]["mcts_precompute"] = {
            "factions_analyzed": len(mcts_results),
            "has_results": sum(1 for v in mcts_results.values() if v is not None),
        }

        # 表现追踪：记录本回合初始状态
        try:
            perf_tracker = get_performance_tracker()
            perf_tracker.record_round(round_num, world_state, faction_configs)
        except Exception as e:
            logger.debug(f"表现追踪记录失败: {e}")

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
        a2_task = asyncio.ensure_future(
            self._phase_a2_warlords_enhanced(world_state, faction_configs, clients, skip_faction_id, phase_ctx, mcts_results)
        )

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

        # --- 组2: A4 + A6 + A5 + A7 + 叙事引擎 并发 ---
        logger.info(f"=== [Orchestrator] 组2并发: A4谍报 + A6外交 + A5事件 + A7宗室 + 叙事引擎 (skip={skip_faction_id}) ===")
        a4_task = asyncio.ensure_future(self._phase_a4_espionage(world_state, clients, skip_faction_id))
        a6_task = asyncio.ensure_future(
            self._phase_a6_diplomacy_enhanced(world_state, faction_configs, clients, skip_faction_id, phase_ctx)
        )
        a5_task = asyncio.ensure_future(self._phase_a5_auto_event_enhanced(world_state, clients))
        a7_task = asyncio.ensure_future(self._phase_a7_royal_enhanced(world_state, faction_configs, clients, skip_faction_id))
        # v4.3: A5 天下大势分析 — 与事件判定并发运行，始终生成（纯叙事）
        a5_situation_task = asyncio.ensure_future(self._phase_a5_situation_analysis(world_state, clients))
        # v4.3: 朝堂廷议 — 所有NPC势力并发生成朝堂辩论（纯叙事）
        court_task = asyncio.ensure_future(
            self._phase_court_debate(world_state, faction_configs, clients, skip_faction_id)
        )
        # v4.3: 市井舆情 — 生成民间街谈巷议（纯叙事）
        sentiment_task = asyncio.ensure_future(self._phase_public_sentiment(world_state, clients))
        # v4.3: 将领列传 — 随机将领内心独白补遗（纯叙事）
        chronicles_task = asyncio.ensure_future(self._phase_general_chronicles(world_state, clients))

        summary["phases"]["A4_espionage"] = await a4_task
        summary["phases"]["A6_diplomacy"] = await a6_task
        summary["phases"]["A5_events"] = await a5_task
        summary["phases"]["A7_royal"] = await a7_task
        try:
            summary["phases"]["A5_situation"] = await a5_situation_task
        except Exception as e:
            logger.warning(f"A5 天下大势分析失败（非致命）: {e}")
            summary["phases"]["A5_situation"] = {"error": str(e)}
        try:
            summary["phases"]["court_debate"] = await court_task
        except Exception as e:
            logger.warning(f"朝堂廷议失败（非致命）: {e}")
            summary["phases"]["court_debate"] = {"error": str(e)}
        try:
            summary["phases"]["public_sentiment"] = await sentiment_task
        except Exception as e:
            logger.warning(f"市井舆情失败（非致命）: {e}")
            summary["phases"]["public_sentiment"] = {"error": str(e)}
        try:
            summary["phases"]["general_chronicles"] = await chronicles_task
        except Exception as e:
            logger.warning(f"将领列传失败（非致命）: {e}")
            summary["phases"]["general_chronicles"] = {"error": str(e)}

        # --- 组3: A8 国史（依赖前序事件总线数据）---
        logger.info("=== [Orchestrator] 组3: A8 国史记录 + 事件总线消费 ===")
        history_result = await self._phase_a8_history_enhanced(world_state, clients)
        summary["phases"]["A8_history"] = history_result

        # v4.3: A8 势力专史 — 为每个存活势力生成独立纪事（纯叙事）
        try:
            faction_chronicles = await self._phase_a8_faction_chronicles(world_state, clients, skip_faction_id)
            summary["phases"]["A8_faction_chronicles"] = faction_chronicles
        except Exception as e:
            logger.warning(f"A8 势力专史失败（非致命）: {e}")
            summary["phases"]["A8_faction_chronicles"] = {"error": str(e)}

        # 消费事件总线中所有待处理事件
        bus_events = await self.event_bus.flush()
        summary["phases"]["event_bus"] = {
            "events_processed": len(bus_events),
            "event_types": list(set(e.event_type for e in bus_events)),
        }

        # ★ 回合结束：记录表现数据
        try:
            perf_tracker = get_performance_tracker()
            perf_tracker.record_round(round_num, world_state, faction_configs)
        except Exception as e:
            logger.debug(f"表现追踪记录跳过: {e}")

        logger.info(f"[Orchestrator] 全自动推演完成 (round={summary['round']}, phase={phase_ctx.phase.value}, events={len(bus_events)})")
        return summary

    # ============================================================
    # 各阶段实现
    # ============================================================

    async def _phase_a2_warlords(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> list[dict]:
        """A2 群雄 - 所有存活君主并发推演（跳过玩家势力）[兼容旧接口]"""
        return await self._phase_a2_warlords_enhanced(
            world_state, faction_configs, clients, skip_faction_id, None, {}
        )

    async def _phase_a2_warlords_enhanced(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
        phase_ctx=None,   # PhaseContext from game_phase_detector
        mcts_results: dict = None,  # {faction_id: mcts_result}
    ) -> list[dict]:
        """A2 群雄 - 增强版：融合阶段自适应 + MCTS战略搜索（跳过玩家势力）"""
        if mcts_results is None:
            mcts_results = {}

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

            # ★ 阶段自适应温度调整
            if phase_ctx and hasattr(agent, '_model_override') and agent._model_override:
                base_temp = agent._model_override.get("temperature", 0.7)
                adjusted_temp = max(0.3, min(1.0, base_temp + phase_ctx.temperature_mod))
                agent._model_override["temperature"] = adjusted_temp

            # ★ MCTS 策略提示注入
            mcts_hint = ""
            mcts_result = mcts_results.get(faction_id)
            if mcts_result and mcts_result.get("confidence", 0) > 0.1:
                rankings = mcts_result.get("action_rankings", [])
                top_actions = [a for a, _ in rankings[:3]]
                mcts_hint = (
                    f"\n\n【战略推演参考(MCTS)】\n"
                    f"推荐方向：{mcts_result['strategy_hint']}\n"
                    f"行动排序：{' > '.join(top_actions)}（置信度{mcts_result['confidence']:.0%}）\n"
                    f"备选方案：{', '.join(mcts_result.get('action_scores', {}).keys())}"
                )

            # ★ 阶段策略提示注入
            phase_hint = ""
            if phase_ctx:
                from .game_phase_detector import get_phase_detector
                detector = get_phase_detector()
                phase_hint = f"\n\n【时局判断】当前处于{phase_ctx.phase.value}阶段（{phase_ctx.alive_factions}方势力角逐）。{detector.get_strategy_hint(phase_ctx, faction_id, world_state)}"

            snapshot = {
                "faction_id": faction_id,
                "faction_config": config,
                "world_state": world_state,
                "mcts_hint": mcts_hint,
                "phase_hint": phase_hint,
                "phase_context": phase_ctx.to_dict() if phase_ctx else {},
            }
            # 2026-07-16 调整: 从30s提升到45s，适配LLM高峰期延迟波动
            try:
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=45.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[A2] {faction_id} safe_step 超时(45s)，使用降级")
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
                agent = self._a4_agents.get(owner)
                if agent is None:
                    agent = A4EspionageAgent(faction_id=owner)
                    self._a4_agents[owner] = agent
                if override:
                    agent.apply_model_override(override)
                snapshot = {
                    "network_id": net_id,
                    "network_data": net_data,
                    "world_state": world_state,
                }
                # 2026-07-16 调整: 从20s提升到30s，适配LLM高峰期延迟波动
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A4 细作网络 {net_id} 超时(30s)")
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
        """A6 外交 - 并发处理所有势力外交（跳过玩家势力：不会主动发起结盟/宣战）[兼容旧接口]"""
        return await self._phase_a6_diplomacy_enhanced(
            world_state, faction_configs, clients, skip_faction_id, None
        )

    async def _phase_a6_diplomacy_enhanced(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
        phase_ctx=None,   # PhaseContext from game_phase_detector
    ) -> dict:
        """A6 外交 - 增强版：融合博弈论分析（Nash均衡 + Shapley值）"""
        override = self._config_manager.get_override("A6")

        factions = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id
        }

        # ★ 博弈论预分析：为所有存活势力计算博弈论外交提示
        gt_hints = {}
        try:
            from .game_theory_diplomacy import get_game_theory_analyzer
            gt_analyzer = get_game_theory_analyzer()
            for fid in living:
                gt_hints[fid] = gt_analyzer.generate_diplomacy_hint(fid, world_state)
        except Exception as e:
            logger.warning(f"博弈论外交分析失败: {e}")

        async def _one_faction(faction_id: str) -> dict:
            try:
                agent = self._a6_agents.get(faction_id)
                if agent is None:
                    agent = A6DiplomacyAgent(faction_id=faction_id)
                    self._a6_agents[faction_id] = agent
                if override:
                    agent.apply_model_override(override)

                # ★ 博弈论提示注入
                gt_hint = gt_hints.get(faction_id, "")

                # ★ 阶段自适应
                phase_hint = ""
                if phase_ctx:
                    phase_hint = (
                        f"\n【时局】当前处于{phase_ctx.phase.value}阶段"
                        f"（{phase_ctx.alive_factions}方势力），"
                        f"外交权重={phase_ctx.diplomacy_weight:.0%}。"
                    )

                snapshot = {
                    "faction_id": faction_id,
                    "world_state": world_state,
                    "game_theory_hint": gt_hint,
                    "phase_hint": phase_hint,
                }
                # 2026-07-16 调整: 从20s提升到30s，适配LLM高峰期延迟波动
                return await asyncio.wait_for(
                    agent.safe_step(snapshot, clients),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A6 外交推演 {faction_id} 超时(30s)")
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

        # 2026-07-16 调整: 从20s提升到30s，适配LLM高峰期延迟波动
        try:
            return await asyncio.wait_for(
                self._a5_agent.run_all_factions(world_state, clients),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("A5 事件推演超时(30s)")
            return {"events": [], "narrative": "天象平和，无灾异。", "status": "timeout"}

    async def _phase_a7_royal(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """A7 宗室 - [已废弃] 串行处理各势力宗室
        
        请使用 _phase_a7_royal_enhanced（并发版本）代替。
        保留此方法仅用于向后兼容，不会再被主流程调用。
        """
        import warnings
        warnings.warn("_phase_a7_royal is deprecated, use _phase_a7_royal_enhanced", DeprecationWarning, stacklevel=2)
        return await self._phase_a7_royal_enhanced(world_state, faction_configs, clients, skip_faction_id)

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
            agent = self._a7_agents.get(faction_id)
            if agent is None:
                agent = A7RoyalAgent(faction_id=faction_id)
                self._a7_agents[faction_id] = agent
            override = self._config_manager.get_override("A7")
            if override:
                agent.apply_model_override(override)
            try:
                # 2026-07-16 调整: 从20s提升到30s，适配LLM高峰期延迟波动
                return await asyncio.wait_for(
                    agent.run_single_faction(faction_id, world_state, clients),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"A7 宗室 {faction_id} 超时(30s)")
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

    async def _phase_a8_faction_chronicles(
        self, world_state: dict, clients: dict, skip_faction_id: str = ""
    ) -> dict:
        """v4.3: A8 势力专史 — 为每个存活势力批量生成独立编年纪事（纯叙事）"""
        override = self._config_manager.get_override("A8")
        if override:
            self._a8_agent.apply_model_override(override)

        try:
            results = await self._a8_agent.run_faction_chronicles_batch(
                world_state, clients, skip_faction_id
            )
            return {"factions_recorded": len(results), "results": results}
        except Exception as e:
            logger.warning(f"A8 势力专史批量生成失败: {e}")
            return {"factions_recorded": 0, "error": str(e)}

    async def _phase_a5_situation_analysis(
        self, world_state: dict, clients: dict
    ) -> dict:
        """v4.3: A5 天下大势分析 — 每回合始终运行的全局战略观察（纯叙事）"""
        override = self._config_manager.get_override("A5")
        if override:
            self._a5_agent.apply_model_override(override)

        try:
            return await self._a5_agent.analyze_world_situation(world_state, clients)
        except Exception as e:
            logger.warning(f"A5 天下大势分析失败: {e}")
            return {"narrative": "时局不明。", "error": str(e)}

    async def _phase_court_debate(
        self, world_state: dict, faction_configs: dict, clients: dict,
        skip_faction_id: str = "",
    ) -> dict:
        """v4.3: 朝堂廷议 — 所有NPC势力并发生成朝堂辩论（纯叙事）"""
        try:
            from .world_narrative import CourtDebateEngine
            results = await CourtDebateEngine.run_all(
                world_state, faction_configs, clients, skip_faction_id
            )
            return {"debates_generated": len(results), "results": results}
        except Exception as e:
            logger.warning(f"朝堂廷议失败: {e}")
            return {"debates_generated": 0, "error": str(e)}

    async def _phase_public_sentiment(
        self, world_state: dict, clients: dict
    ) -> dict:
        """v4.3: 市井舆情 — 生成民间街谈巷议（纯叙事）"""
        try:
            from .world_narrative import PublicSentimentEngine
            return await PublicSentimentEngine.generate(world_state, clients)
        except Exception as e:
            logger.warning(f"市井舆情失败: {e}")
            return {"rumors": [], "error": str(e)}

    async def _phase_general_chronicles(
        self, world_state: dict, clients: dict
    ) -> dict:
        """v4.3: 将领列传 — 随机将领内心独白补遗（纯叙事）"""
        try:
            from .world_narrative import GeneralChroniclesEngine
            return await GeneralChroniclesEngine.generate(world_state, clients)
        except Exception as e:
            logger.warning(f"将领列传失败: {e}")
            return {"entries": [], "error": str(e)}

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
        all_agents = list(self._a1_agents.values()) + \
                     list(self._a2_agents.values()) + \
                     list(self._a3_agents.values()) + \
                     list(self._a4_agents.values()) + \
                     list(self._a6_agents.values()) + \
                     list(self._a7_agents.values()) + \
                     [self._a5_agent, self._a8_agent, self._a9_agent, self._a10_agent]

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
        """获取Agent列表（供前端展示）— 十大智能体 A1~A10"""
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
            {
                "key": "A9",
                "name": "军机处",
                "model_group": "enemy",
                "trigger": "auto",
                "description": "战斗后自动生成古风战报、军情分析（无玩家交互）",
                "player_only": False,
                "config": self._safe_get_agent_config("A9"),
            },
            {
                "key": "A10",
                "name": "度支司",
                "model_group": "law",
                "trigger": "auto",
                "description": "税收粮储调配、国策经济影响评估（后台自动运行）",
                "player_only": False,
                "config": self._safe_get_agent_config("A10"),
            },
        ]

    def reset_for_new_game(self):
        """新游戏开始时重置所有Agent状态"""
        self._a1_agents.clear()
        self._a2_agents.clear()
        self._a3_agents.clear()
        self._a4_agents.clear()
        self._a6_agents.clear()
        self._a7_agents.clear()
        self._a5_agent = A5EventAgent()
        self._a8_agent = A8HistoryAgent()
        self._a9_agent = get_a9_battle_report_agent()
        self._a10_agent = get_a10_treasury_agent()
        self._total_calls = 0
        self._total_latency = 0.0
        # 重置事件总线和客户端引用
        reset_event_bus()
        self._event_bus = get_event_bus()
        self._clients = None  # 清除旧LLM客户端引用，由外部重新注入
        # ★ 重置博弈增强模块
        try:
            from .game_phase_detector import reset_phase_detector
            reset_phase_detector()
        except Exception as e:
            logger.debug(f"阶段检测器重置跳过: {e}")
        try:
            from .strategic_mcts import reset_strategic_mcts
            reset_strategic_mcts()
        except Exception as e:
            logger.debug(f"战略MCTS重置跳过: {e}")
        try:
            from .agent_benchmark import reset_benchmark
            reset_benchmark()
        except Exception as e:
            logger.debug(f"基准测试重置跳过: {e}")
        logger.info("AgentOrchestrator 已为新游戏重置（含博弈增强模块）")


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
