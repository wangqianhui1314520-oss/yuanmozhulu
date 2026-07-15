"""
元末逐鹿 3.0 - 八大智能体架构

目录结构:
  base.py          - Agent基类 + 熔断器 + AgentCategory枚举
  agent_config.py  - 配置热更新管理器
  orchestrator.py  - 统一调度入口 AgentOrchestrator

  a1_advisor.py    - A1 谋策阁 (advisor/manual)
  a2_warlord.py    - A2 群雄殿 (advisor/auto)
  a3_law.py        - A3 律法堂 (advisor/manual)
  a4_espionage.py  - A4 谍报司 (enemy/auto)
  a5_event.py      - A5 司天台 (enemy/both)
  a6_diplomacy.py  - A6 外交署 (law/auto)
  a7_royal.py      - A7 宗室府 (advisor/auto)
  a8_history.py    - A8 国史馆 (law/auto)

  tool_agent.py    - 工具调用Agent（兼容保留）
  runtime.py       - 旧版运行时（兼容保留）
"""
from .base import BaseAgent, AgentCategory, CircuitBreaker
from .orchestrator import AgentOrchestrator, get_orchestrator
from .agent_event_bus import (
    AgentEvent, AgentEventBus, EventTypes, EventPriority,
    get_event_bus, reset_event_bus,
)

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
]
