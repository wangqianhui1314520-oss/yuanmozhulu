"""游戏事件模型"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    BATTLE = "battle"
    DIPLOMACY = "diplomacy"
    DISASTER = "disaster"
    COURT = "court"
    ECONOMY = "economy"
    SPY = "spy"
    CIVIL = "civil"
    ROYAL = "royal"
    RANDOM = "random"
    ENDING = "ending"


class EventSeverity(str, Enum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class GameEvent(BaseModel):
    """通用游戏事件"""
    event_id: str
    event_type: EventType
    severity: EventSeverity = EventSeverity.MINOR
    round: int
    title: str
    description: str = ""
    faction_id: str = ""
    tile_id: str = ""
    effects: dict = Field(default_factory=dict)
    narrative: str = ""


class BattleEvent(GameEvent):
    """战斗事件"""
    event_type: EventType = EventType.BATTLE  # 固定类型
    attacker: str = ""
    defender: str = ""
    attacker_losses: int = 0
    defender_losses: int = 0
    result: str = ""
    is_siege: bool = False
    tile_captured: bool = False
    battle_narrative: str = ""


class DiplomaticEvent(GameEvent):
    """外交事件"""
    event_type: EventType = EventType.DIPLOMACY  # 固定类型
    from_faction: str = ""
    to_faction: str = ""
    action: str = ""
    relation_change: int = 0
    treaty_signed: bool = False


class DisasterEvent(GameEvent):
    """灾害事件"""
    event_type: EventType = EventType.DISASTER  # 固定类型
    disaster_type: str = ""
    affected_tiles: list[str] = Field(default_factory=list)
    duration: int = 0
    casualties: int = 0


class CourtEvent(GameEvent):
    """朝堂事件"""
    event_type: EventType = EventType.COURT  # 固定类型
    involved_officials: list[str] = Field(default_factory=list)
    faction_affected: str = ""
    loyalty_change: int = 0
    stability_change: int = 0
