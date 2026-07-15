"""API 请求模型"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class EdictRequest(BaseModel):
    """圣旨颁布请求"""
    edict_text: str
    faction_id: str
    turn: int = Field(ge=0)
    season: str
    treasury: int = Field(ge=0)
    grain: int = Field(ge=0)
    troops: int = Field(ge=0)
    reputation: int = Field(ge=0, le=100)
    court_stability: int = Field(ge=0, le=100)
    realm_stability: int = Field(ge=0, le=100)
    development_level: int = Field(ge=0)
    disaster_index: int = Field(default=0, ge=0)
    faction_loyalties: dict = Field(default_factory=dict)
    active_factions_info: list = Field(default_factory=list)
    monarch_style: str = "balanced"

    @field_validator('reputation', 'court_stability', 'realm_stability')
    @classmethod
    def clamp_0_100(cls, v: int) -> int:
        return max(0, min(100, v))


class FactionAIRequest(BaseModel):
    """NPC势力AI决策请求"""
    faction_id: str
    faction_name: str
    faction_personality: list = Field(default_factory=list)
    tile_count: int
    troops: int
    treasury: int
    grain: int
    reputation: int
    turn: int
    season: str
    neighbors_info: list = Field(default_factory=list)
    global_situation: str = ""
    buffs: list = Field(default_factory=list)
    debuffs: list = Field(default_factory=list)
    ai_logic: dict = Field(default_factory=dict)


class CourtRequest(BaseModel):
    """朝堂辩论请求"""
    edict_text: str = ""
    faction_loyalties: dict = Field(default_factory=dict)
    ministers_info: list = Field(default_factory=list)
    turn: int = 0
    faction_id: str = ""
    faction_name: str = ""
    ruler_name: str = ""
    monarch_style: str = "balanced"
    active_factions_info: list = Field(default_factory=list)


class MonthlySettlementRequest(BaseModel):
    """派系月度结算请求"""
    faction_id: str
    faction_name: str
    monarch_style: str
    turn: int
    court_stability: int
    active_factions: list = Field(default_factory=list)
    monthly_edicts: list = Field(default_factory=list)
    monthly_events: list = Field(default_factory=list)


class ConflictEventRequest(BaseModel):
    """朝堂冲突事件请求"""
    event_type: str
    faction_id: str
    faction_name: str
    turn: int
    court_stability: int
    involved_factions: list = Field(default_factory=list)
    trigger_cause: str = ""


class BattleRequest(BaseModel):
    """战斗结算请求"""
    attacker_faction: str
    defender_faction: str
    tile_id: str
    attacker_troops: int
    defender_troops: int
    attacker_arms: int
    defender_arms: int
    attacker_horses: int
    defender_horses: int
    wall_level: int = 0
    season: str = "春"
    terrain: str = "farmland"
    is_siege: bool = False
    attacker_buffs: list = Field(default_factory=list)
    defender_buffs: list = Field(default_factory=list)


class StrategyRequest(BaseModel):
    """AI全局战略推演请求"""
    faction_id: str
    faction_name: str
    turn: int
    season: str
    tile_count: int
    troops: int
    treasury: int
    reputation: int
    neighbors: list = Field(default_factory=list)
    threats: list = Field(default_factory=list)
    opportunities: list = Field(default_factory=list)


class DiplomacyRequest(BaseModel):
    """外交请求"""
    from_faction: str
    to_faction: str
    action_type: str
    terms: dict = Field(default_factory=dict)
    turn: int = 0


class DisasterRequest(BaseModel):
    """灾害预判请求"""
    faction_id: str
    turn: int
    season: str
    active_disasters: list = Field(default_factory=list)
    disaster_index: int = 0
