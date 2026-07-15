"""
智能体事件总线 - 八大智能体间的消息通知与协作机制

职责:
1. 提供 Agent 间的松耦合消息传递
2. 支持事件订阅/发布模式
3. 统一的事件格式（EventEnvelope）
4. 回合结束时自动清空事件队列

典型事件流:
  A5(天灾) → bus.publish("disaster_occurred") → A8(国史) 记录
  A2(出征) → bus.publish("battle_started") → A4(谍报) 关注战场
  A6(缔约) → bus.publish("alliance_formed") → A8(国史) 记录
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("yuanmo.agent.event_bus")


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0       # 普通信息
    NORMAL = 1    # 常规事件
    HIGH = 2      # 重要事件（天灾、战争等）
    CRITICAL = 3  # 紧急事件（势力覆灭、皇帝驾崩等）


@dataclass
class AgentEvent:
    """
    智能体事件信封

    统一的事件数据结构，所有 Agent 间通信均通过此格式。
    """
    event_type: str                              # 事件类型标识 (如 "disaster_occurred")
    source_agent: str                            # 来源智能体 (如 "A5", "A2")
    source_faction_id: str = ""                  # 来源势力ID
    target_faction_id: str = ""                  # 目标势力ID（可选）
    priority: EventPriority = EventPriority.NORMAL
    data: dict[str, Any] = field(default_factory=dict)  # 事件负载数据
    round: int = 0                               # 发生回合
    timestamp: float = field(default_factory=time.time)
    consumed: bool = False                       # 是否已被消费

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "source_agent": self.source_agent,
            "source_faction_id": self.source_faction_id,
            "target_faction_id": self.target_faction_id,
            "priority": self.priority.name,
            "data": self.data,
            "round": self.round,
            "timestamp": self.timestamp,
        }


# 标准事件类型常量
class EventTypes:
    """预定义的跨智能体事件类型"""
    # A5 天灾人事事件
    DISASTER_OCCURRED = "disaster_occurred"         # 天灾发生
    OMEN_APPEARED = "omen_appeared"                 # 祥瑞/凶兆出现
    REFUGEE_WAVE = "refugee_wave"                   # 流民潮
    PEASANT_UPRISING = "peasant_uprising"           # 农民起义

    # A2 群雄军事事件
    BATTLE_STARTED = "battle_started"               # 战斗开始
    BATTLE_ENDED = "battle_ended"                   # 战斗结束
    CITY_CAPTURED = "city_captured"                 # 城池攻陷
    FACTION_DESTROYED = "faction_destroyed"         # 势力覆灭
    NEW_FACTION_RISE = "new_faction_rise"           # 新势力崛起

    # A6 外交事件
    ALLIANCE_FORMED = "alliance_formed"             # 结盟
    ALLIANCE_BROKEN = "alliance_broken"             # 盟约破裂
    WAR_DECLARED = "war_declared"                   # 宣战
    PEACE_TREATY = "peace_treaty"                   # 和平条约
    TRIBUTE_OFFERED = "tribute_offered"             # 朝贡

    # A4 谍报事件
    INTEL_DISCOVERED = "intel_discovered"           # 情报获取
    SPY_CAUGHT = "spy_caught"                       # 细作被捕
    ASSASSINATION = "assassination"                 # 暗杀事件

    # A7 宗室事件
    SUCCESSION_CRISIS = "succession_crisis"         # 继承危机
    HEIR_COMING_OF_AGE = "heir_coming_of_age"       # 皇子成年
    RULER_DEATH = "ruler_death"                     # 君主驾崩
    COURTYARD_COUP = "courtyard_coup"               # 宫变

    # A3 律法事件
    HIGH_TREASON = "high_treason"                   # 谋反大案
    CORRUPTION_EXPOSED = "corruption_exposed"       # 贪腐暴露

    # 系统事件
    ROUND_START = "round_start"                     # 回合开始
    ROUND_END = "round_end"                         # 回合结束
    GAME_OVER = "game_over"                         # 游戏结束


class AgentEventBus:
    """
    智能体事件总线

    使用方式:
        bus = AgentEventBus()

        # 订阅
        @bus.on(EventTypes.DISASTER_OCCURRED)
        async def on_disaster(event: AgentEvent):
            # A8 记录天灾
            pass

        # 发布
        bus.publish(AgentEvent(
            event_type=EventTypes.DISASTER_OCCURRED,
            source_agent="A5",
            priority=EventPriority.HIGH,
            data={"disaster_type": "洪水", "affected_region": "江淮"},
        ))

        # 处理所有待消费事件
        await bus.flush()
    """

    def __init__(self):
        # 事件类型 → 订阅者列表
        self._subscribers: dict[str, list[Callable]] = {}
        # 通配符订阅者（接收所有事件）
        self._wildcard_subscribers: list[Callable] = []
        # 待消费事件队列
        self._pending_events: list[AgentEvent] = []
        # 已处理事件归档（用于 A8 国史回溯）
        self._event_archive: list[AgentEvent] = []
        # 当前回合
        self._current_round: int = 0

    def set_round(self, round_num: int):
        """设置当前回合号"""
        self._current_round = round_num

    def on(self, event_type: str):
        """装饰器：订阅指定事件类型"""
        def decorator(func: Callable):
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(func)
            logger.debug(f"[EventBus] 订阅 {event_type} → {func.__name__}")
            return func
        return decorator

    def on_any(self, func: Callable):
        """注册通配符订阅者（接收所有事件）"""
        self._wildcard_subscribers.append(func)
        logger.debug(f"[EventBus] 通配符订阅 → {func.__name__}")
        return func

    def publish(self, event: AgentEvent):
        """
        发布事件到总线

        Args:
            event: AgentEvent 实例（自动填充 round 和 timestamp）
        """
        if event.round == 0:
            event.round = self._current_round
        if event.timestamp == 0:
            event.timestamp = time.time()

        self._pending_events.append(event)
        logger.debug(
            f"[EventBus] 发布事件: {event.event_type} "
            f"(src={event.source_agent}, priority={event.priority.name})"
        )

    def publish_simple(
        self, event_type: str, source_agent: str,
        source_faction_id: str = "", target_faction_id: str = "",
        priority: EventPriority = EventPriority.NORMAL,
        data: Optional[dict] = None,
    ):
        """快捷发布方法"""
        self.publish(AgentEvent(
            event_type=event_type,
            source_agent=source_agent,
            source_faction_id=source_faction_id,
            target_faction_id=target_faction_id,
            priority=priority,
            data=data or {},
            round=self._current_round,
        ))

    async def flush(self) -> list[AgentEvent]:
        """
        消费所有待处理事件

        按优先级排序后逐个通知订阅者。
        返回已消费的事件列表。

        Returns:
            已消费的 AgentEvent 列表
        """
        if not self._pending_events:
            return []

        # 按优先级降序排列（CRITICAL 先处理）
        events = sorted(
            self._pending_events,
            key=lambda e: e.priority.value,
            reverse=True,
        )

        processed = []
        for event in events:
            try:
                # 通知精确订阅者
                subs = self._subscribers.get(event.event_type, [])
                for handler in subs:
                    try:
                        if asyncio and hasattr(handler, '__call__'):
                            import asyncio as _asyncio
                            if _asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                    except Exception as e:
                        logger.error(f"[EventBus] 处理 {event.event_type} 异常: {e}")

                # 通知通配符订阅者
                for handler in self._wildcard_subscribers:
                    try:
                        import asyncio as _asyncio
                        if _asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"[EventBus] 通配符处理异常: {e}")

                event.consumed = True
                processed.append(event)
                self._event_archive.append(event)

            except Exception as e:
                logger.error(f"[EventBus] 事件 {event.event_type} 处理失败: {e}")

        # 清空待处理队列
        self._pending_events.clear()

        if processed:
            logger.info(f"[EventBus] 已处理 {len(processed)} 个事件")

        return processed

    def get_archive(self, round_num: Optional[int] = None) -> list[AgentEvent]:
        """
        获取事件归档

        Args:
            round_num: 指定回合，None 则返回全部

        Returns:
            AgentEvent 列表
        """
        if round_num is not None:
            return [e for e in self._event_archive if e.round == round_num]
        return list(self._event_archive)

    def get_events_by_type(self, event_type: str) -> list[AgentEvent]:
        """按类型获取已归档事件"""
        return [e for e in self._event_archive if e.event_type == event_type]

    def clear_archive(self, before_round: int = 0):
        """清理指定回合之前的事件归档"""
        if before_round > 0:
            self._event_archive = [
                e for e in self._event_archive if e.round >= before_round
            ]

    def reset(self):
        """重置总线状态（新游戏开始时调用）"""
        self._pending_events.clear()
        self._event_archive.clear()
        self._current_round = 0
        logger.info("[EventBus] 已重置")


# 全局单例
import asyncio

_global_event_bus: Optional[AgentEventBus] = None


def get_event_bus() -> AgentEventBus:
    """获取全局事件总线单例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = AgentEventBus()
        logger.info("AgentEventBus 全局实例已创建")
    return _global_event_bus


def reset_event_bus():
    """重置全局事件总线"""
    global _global_event_bus
    if _global_event_bus is not None:
        _global_event_bus.reset()
    _global_event_bus = AgentEventBus()
