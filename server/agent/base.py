"""
八大智能体架构 - Agent基类与类型定义

A1~A8 共8个独立智能体模块:
  A1 谋策    (advisor)   - 谋臣献策、廷议辩论、战略分析
  A2 群雄AI  (advisor)   - 君主NPC自主推演、势力决策
  A3 律法审讯 (advisor)   - 案件审理、律法判决
  A4 谍报谋略 (enemy)     - 细作行动、情报搜集
  A5 随机事件 (enemy)     - 天灾人祸、祥瑞异象
  A6 外交缔约 (law)       - 合纵连横、盟约谈判
  A7 宗室皇储 (advisor)   - 继承顺位、宗室管理
  A8 国史编撰 (law)       - 史书修撰、结局传记

三套模型分组:
  - advisor: chat_role()  → A1/A2/A3/A7
  - law:     chat_strategy() → A6/A8
  - enemy:   chat_fast()  → A4/A5
"""
from __future__ import annotations
import asyncio
import logging
import time
import traceback
from abc import ABC, abstractmethod
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger("yuanmo.agent")


class AgentCategory(Enum):
    """八大智能体类别"""
    A1_ADVISOR = "a1_advisor"           # 谋策 - 谋臣献策
    A2_WARLORD = "a2_warlord"           # 群雄AI - 君主推演
    A3_LAW = "a3_law"                   # 律法审讯
    A4_ESPIONAGE = "a4_espionage"       # 谍报谋略
    A5_EVENT = "a5_event"               # 随机事件
    A6_DIPLOMACY = "a6_diplomacy"       # 外交缔约
    A7_ROYAL = "a7_royal"               # 宗室皇储
    A8_HISTORY = "a8_history"           # 国史编撰

    @property
    def model_group(self) -> str:
        """返回所属模型分组: advisor / law / enemy"""
        mapping = {
            AgentCategory.A1_ADVISOR: "advisor",
            AgentCategory.A2_WARLORD: "advisor",
            AgentCategory.A3_LAW: "advisor",
            AgentCategory.A4_ESPIONAGE: "enemy",
            AgentCategory.A5_EVENT: "enemy",
            AgentCategory.A6_DIPLOMACY: "law",
            AgentCategory.A7_ROYAL: "advisor",
            AgentCategory.A8_HISTORY: "law",
        }
        return mapping.get(self, "enemy")

    @property
    def display_name(self) -> str:
        names = {
            AgentCategory.A1_ADVISOR: "谋策阁",
            AgentCategory.A2_WARLORD: "群雄殿",
            AgentCategory.A3_LAW: "律法堂",
            AgentCategory.A4_ESPIONAGE: "谍报司",
            AgentCategory.A5_EVENT: "司天台",
            AgentCategory.A6_DIPLOMACY: "外交署",
            AgentCategory.A7_ROYAL: "宗室府",
            AgentCategory.A8_HISTORY: "国史馆",
        }
        return names.get(self, "未知")


# ============================================================
# 熔断器 (Circuit Breaker)
# ============================================================

class CircuitBreaker:
    """
    熔断器 - 防止级联故障
    
    三种状态:
    - CLOSED:   正常，请求通过
    - OPEN:     熔断，直接返回fallback
    - HALF_OPEN: 半开，允许试探性请求
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self._half_open_trials = 0

    @property
    def is_open(self) -> bool:
        if self._state == "CLOSED":
            return False
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = "HALF_OPEN"
                self._half_open_trials = 0
                logger.info(f"[熔断器:{self.name}] OPEN → HALF_OPEN，试探性恢复")
                return False
            return True
        if self._state == "HALF_OPEN":
            return self._half_open_trials >= self.half_open_max
        return False

    def success(self):
        if self._state == "HALF_OPEN":
            self._half_open_trials += 1
            self._success_count += 1
            if self._half_open_trials >= self.half_open_max:
                self._state = "CLOSED"
                self._failure_count = 0
                logger.info(f"[熔断器:{self.name}] HALF_OPEN → CLOSED，已恢复")
        else:
            self._failure_count = 0

    def failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == "HALF_OPEN":
            self._state = "OPEN"
            logger.warning(f"[熔断器:{self.name}] HALF_OPEN → OPEN，再次熔断")
        elif self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.warning(
                f"[熔断器:{self.name}] CLOSED → OPEN "
                f"(连续失败{self._failure_count}次)"
            )

    def reset(self):
        self._failure_count = 0
        self._success_count = 0
        self._state = "CLOSED"
        self._half_open_trials = 0
        logger.info(f"[熔断器:{self.name}] 手动重置 → CLOSED")


# ============================================================
# Agent基类（增强版）
# ============================================================

class BaseAgent(ABC):
    """
    八大智能体基类

    每个Agent实例代表一个自主决策单元，通过LLM客户端与游戏世界交互。
    统一包含：重试机制、熔断降级、日志记录、配置热更新。
    """

    def __init__(
        self,
        agent_id: str,
        category: AgentCategory,
        faction_id: str = "",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.agent_id = agent_id
        self.category = category
        self.faction_id = faction_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 熔断器
        self.circuit_breaker = CircuitBreaker(
            name=f"{category.value}:{agent_id}",
            failure_threshold=5,
            recovery_timeout=60.0,
        )

        # 记忆系统
        self.short_term_memory: list[str] = []
        self.mid_term_memory: list[str] = []
        self.long_term_memory: list[str] = []

        # 运行时状态
        self._alive = True
        self._last_decision: Optional[dict] = None
        self._call_count = 0
        self._total_latency = 0.0

        # 模型参数（支持运行时覆盖）
        self._model_override: Optional[dict] = None

    # ========== 属性 ==========

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def model_group(self) -> str:
        return self.category.model_group

    @property
    def avg_latency(self) -> float:
        if self._call_count == 0:
            return 0.0
        return self._total_latency / self._call_count

    # ========== 生命周期 ==========

    def kill(self):
        self._alive = False
        logger.info(f"Agent死亡: {self.agent_id} ({self.category.value})")

    def apply_model_override(self, override: dict):
        """应用模型参数覆盖（热更新入口）"""
        self._model_override = override
        logger.info(
            f"[{self.agent_id}] 模型参数热更新: "
            f"model={override.get('model', 'default')}, "
            f"temperature={override.get('temperature', 'default')}"
        )

    # ========== 核心决策接口 ==========

    @abstractmethod
    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """执行一步自主决策（子类实现）"""
        ...

    async def safe_step(self, world_snapshot: dict, clients: dict) -> dict:
        """
        带重试+熔断+日志的决策包装

        流程:
        1. 检查熔断器状态
        2. 带指数退避重试
        3. 记录延迟和日志
        4. 更新熔断器状态
        """
        if not self._alive:
            return {"agent_id": self.agent_id, "error": "agent_dead", "status": "skipped"}

        if self.circuit_breaker.is_open:
            logger.warning(f"[{self.agent_id}] 熔断器开启，使用降级响应")
            return self._fallback_response("circuit_open")

        client = clients.get(self.model_group)
        if client is None:
            return self._fallback_response("no_client")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                start = time.time()
                result = await self.step(world_snapshot, clients)
                elapsed = time.time() - start

                self._call_count += 1
                self._total_latency += elapsed
                self._last_decision = result
                self.circuit_breaker.success()

                logger.info(
                    f"[{self.agent_id}] step成功 "
                    f"(attempt={attempt+1}, latency={elapsed:.2f}s)"
                )
                return result

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    f"[{self.agent_id}] 超时 (attempt={attempt+1}/{self.max_retries+1})"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self.circuit_breaker.failure()

            except Exception as e:
                last_error = e
                logger.error(
                    f"[{self.agent_id}] 异常 (attempt={attempt+1}): "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self.circuit_breaker.failure()

        return self._fallback_response(str(last_error))

    def _fallback_response(self, reason: str) -> dict:
        """降级兜底响应"""
        fallbacks = {
            "circuit_open": f"{self.category.display_name}暂时无法响应（熔断保护）",
            "no_client": f"{self.category.display_name}未配置LLM客户端",
        }
        msg = fallbacks.get(reason, f"{self.category.display_name}响应异常：{reason}")
        logger.warning(f"[{self.agent_id}] 降级: {reason}")
        return {
            "agent_id": self.agent_id,
            "category": self.category.value,
            "response": msg,
            "status": "degraded",
            "reason": reason,
        }

    # ========== 记忆系统 ==========

    def get_memory_context(self, max_turns: int = 3) -> str:
        if max_turns <= 0:
            return "（无近期记忆）"
        recent = self.short_term_memory[-max_turns:]
        return "\n".join(recent) if recent else "（无近期记忆）"

    def remember(self, event: str, importance: int = 1):
        self.short_term_memory.append(event)
        if len(self.short_term_memory) > 10:
            old = self.short_term_memory.pop(0)
            self.mid_term_memory.append(old)
        if importance >= 7:
            self.long_term_memory.append(event)
        if len(self.mid_term_memory) > 50:
            self.mid_term_memory.pop(0)
        if len(self.long_term_memory) > 30:
            self.long_term_memory.pop(0)

    # ========== 统计信息 ==========

    def get_stats(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "category": self.category.value,
            "display_name": self.category.display_name,
            "model_group": self.model_group,
            "alive": self._alive,
            "call_count": self._call_count,
            "avg_latency": round(self.avg_latency, 3),
            "total_tokens": 0,  # Token由LLM客户端层追踪，Agent层不重复
            "circuit_state": self.circuit_breaker._state,
            "model_override": self._model_override,
            "memories": {
                "short_term": len(self.short_term_memory),
                "mid_term": len(self.mid_term_memory),
                "long_term": len(self.long_term_memory),
            },
        }
