"""
元末逐鹿 4.0 - 十大智能体架构

目录结构:
  base.py                  - Agent基类 + 熔断器 + AgentCategory枚举
  agent_config.py          - 配置热更新管理器
  orchestrator.py          - 统一调度入口 AgentOrchestrator

  a1_advisor.py            - A1 谋策阁 (advisor/manual)
  a2_warlord.py            - A2 群雄殿 (advisor/auto) + 军事深化
  a3_law.py                - A3 律法堂 (advisor/manual) + 吏部任免
  a4_espionage.py          - A4 谍报司 (enemy/auto) + AI间谍策略
  a5_event.py              - A5 司天台 (enemy/both) + AI事件影响
  a6_diplomacy.py          - A6 外交署 (law/auto) + AI外交谈判
  a7_royal.py              - A7 宗室府 (advisor/auto) + 王朝管理
  a8_history.py            - A8 国史馆 (law/auto)
  a9_battle_report.py      - A9 军机处 (enemy/auto) - AI古风战报
  a10_treasury.py          - A10 度支司 (law/auto) - AI经济决策

  tool_agent.py            - 工具调用Agent（兼容保留）
  runtime.py               - 旧版运行时（兼容保留）

  博弈增强模块 (基于 autonomous-agent-gaming skill):
  game_phase_detector.py   - 游戏阶段检测器 (Opening/Midgame/Endgame)
  strategic_mcts.py        - 战略MCTS搜索器 (Monte Carlo Tree Search)
  game_theory_diplomacy.py - 博弈论外交分析器 (Nash均衡/Shapley值)
  agent_benchmark.py       - 智能体强度基准测试 (Elo评分/锦标赛)
"""
from .base import BaseAgent, AgentCategory, CircuitBreaker
from .orchestrator import AgentOrchestrator, get_orchestrator
from .agent_event_bus import (
    AgentEvent, AgentEventBus, EventTypes, EventPriority,
    get_event_bus, reset_event_bus,
)
from .npc_memory import (
    NPCMemoryManager, KeyMemory,
    Emotion, MemoryType, get_npc_memory_manager,
)
from .npc_relations import (
    NPCRelationManager, NPCRelation, NPCFaction,
    RelationType, FactionType, get_npc_relation_manager,
)
# 博弈增强模块
from .game_phase_detector import (
    GamePhaseDetector, GamePhase, PhaseContext, FactionRole,
    get_phase_detector, reset_phase_detector,
)
from .strategic_mcts import (
    StrategicMCTS, StrategicState, StrategicAction, MCTSNode,
    TranspositionTable, KillerHeuristic, evaluate_state,
    get_strategic_mcts, reset_strategic_mcts, strategic_state_from_world,
)
from .game_theory_diplomacy import (
    GameTheoryAnalyzer, PayoffMatrix, NashEquilibrium,
    CoalitionAnalysis, get_game_theory_analyzer,
)
from .agent_benchmark import (
    EloSystem, EloRating, PerformanceTracker,
    FactionPerformance, TournamentSystem,
    get_tournament, get_performance_tracker, reset_benchmark,
)
# A9 AI战报生成器
from .a9_battle_report import A9BattleReportAgent, get_a9_battle_report_agent
# A10 度支司
from .a10_treasury import A10TreasuryAgent, get_a10_treasury_agent

__all__ = [
    "BaseAgent",
    "AgentCategory",
    "CircuitBreaker",
    "AgentOrchestrator",
    "get_orchestrator",
    "AgentEvent",
    "AgentEventBus",
    "EventTypes",
    "EventPriority",
    "get_event_bus",
    "reset_event_bus",
    # NPC 记忆与情感系统
    "NPCMemoryManager",
    "KeyMemory",
    "Emotion",
    "MemoryType",
    "get_npc_memory_manager",
    # NPC 关系网络
    "NPCRelationManager",
    "NPCRelation",
    "NPCFaction",
    "RelationType",
    "FactionType",
    "get_npc_relation_manager",
    # 博弈增强模块
    "GamePhaseDetector", "GamePhase", "PhaseContext", "FactionRole",
    "get_phase_detector", "reset_phase_detector",
    "StrategicMCTS", "StrategicState", "StrategicAction", "MCTSNode",
    "TranspositionTable", "KillerHeuristic", "evaluate_state",
    "get_strategic_mcts", "reset_strategic_mcts", "strategic_state_from_world",
    "GameTheoryAnalyzer", "PayoffMatrix", "NashEquilibrium",
    "CoalitionAnalysis", "get_game_theory_analyzer",
    "EloSystem", "EloRating", "PerformanceTracker",
    "FactionPerformance", "TournamentSystem",
    "get_tournament", "get_performance_tracker", "reset_benchmark",
    # A9 AI战报生成器
    "A9BattleReportAgent",
    "get_a9_battle_report_agent",
    # A10 度支司
    "A10TreasuryAgent",
    "get_a10_treasury_agent",
]
