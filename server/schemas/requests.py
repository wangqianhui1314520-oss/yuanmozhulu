"""
Pydantic 请求验证模型（扩展集）· 元末逐鹿 4.0

H-2 修复：为尚未迁移的 API 端点提供类型安全校验。
已存在于 server.api_models 的模型（DiplomacyActionRequest/WarDeclareRequest/
DecreeRequest/UnlockPolicyRequest/MarchResolveRequest/EdictProcessRequest/
TradeRouteRequest）不在此重复定义。
所有模型使用 extra="ignore" 保持向后兼容。
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any


# ================================================================
# 外交（扩展）
# ================================================================

class OpenTradeRequest(BaseModel):
    """POST /api/diplomacy/trade — 开通贸易"""
    faction_id: str = Field(default="", max_length=64)
    faction_a: Optional[str] = Field(default=None, max_length=64)
    from_faction: Optional[str] = Field(default=None, max_length=64)
    faction_b: Optional[str] = Field(default=None, max_length=64)
    target_faction: Optional[str] = Field(default=None, max_length=64)
    to_faction: Optional[str] = Field(default=None, max_length=64)

    model_config = {"extra": "ignore"}


class SignPeaceRequest(BaseModel):
    """POST /api/diplomacy/peace — 签署停战"""
    faction_id: str = Field(default="", max_length=64)
    faction_a: Optional[str] = Field(default=None, max_length=64)
    from_faction: Optional[str] = Field(default=None, max_length=64)
    faction_b: Optional[str] = Field(default=None, max_length=64)
    target_faction: Optional[str] = Field(default=None, max_length=64)
    to_faction: Optional[str] = Field(default=None, max_length=64)
    duration: Optional[int] = Field(default=None, ge=1, le=100)

    model_config = {"extra": "ignore"}


class DemandTributeRequest(BaseModel):
    """POST /api/diplomacy/tribute — 朝贡"""
    faction_id: str = Field(default="", max_length=64)
    faction_a: Optional[str] = Field(default=None, max_length=64)
    from_faction: Optional[str] = Field(default=None, max_length=64)
    faction_b: Optional[str] = Field(default=None, max_length=64)
    target_faction: Optional[str] = Field(default=None, max_length=64)
    to_faction: Optional[str] = Field(default=None, max_length=64)
    suzerain: Optional[str] = Field(default=None, max_length=64)
    suzerain_faction: Optional[str] = Field(default=None, max_length=64)
    vassal: Optional[str] = Field(default=None, max_length=64)
    vassal_faction: Optional[str] = Field(default=None, max_length=64)
    amount: int = Field(default=200, ge=0, le=100000)

    model_config = {"extra": "ignore"}


class OfferVassalRequest(BaseModel):
    """POST /api/diplomacy/vassal/offer — 附庸提议"""
    faction_id: str = Field(default="", max_length=64)
    faction_a: Optional[str] = Field(default=None, max_length=64)
    from_faction: Optional[str] = Field(default=None, max_length=64)
    faction_b: Optional[str] = Field(default=None, max_length=64)
    target_faction: Optional[str] = Field(default=None, max_length=64)
    to_faction: Optional[str] = Field(default=None, max_length=64)
    suzerain: Optional[str] = Field(default=None, max_length=64)
    suzerain_faction: Optional[str] = Field(default=None, max_length=64)
    target: Optional[str] = Field(default=None, max_length=64)
    vassal_faction: Optional[str] = Field(default=None, max_length=64)

    model_config = {"extra": "ignore"}


# ================================================================
# 战争
# ================================================================

class DeclareWarRequest(BaseModel):
    """POST /api/war/declare — 宣战（扩展字段，基础版见 api_models.WarDeclareRequest）"""
    faction_id: str = Field(default="", max_length=64)
    attacker_faction: Optional[str] = Field(default=None, max_length=64)
    target_faction: Optional[str] = Field(default=None, max_length=64)
    defender_faction: Optional[str] = Field(default=None, max_length=64)
    reason: str = Field(default="兴兵讨伐", max_length=200)
    casus_belli: str = Field(default="conquest", max_length=32)
    war_goal_tiles: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class ProposePeaceRequest(BaseModel):
    """POST /api/war/peace/propose — 和平提议"""
    war_id: str = Field(default="", max_length=64)
    terms: dict[str, Any] = Field(default_factory=dict)
    tile_ids: list[str] = Field(default_factory=list)
    reparation_amount: int = Field(default=0, ge=0, le=100000)
    is_from_attacker: bool = Field(default=True)

    model_config = {"extra": "ignore"}


# ================================================================
# 朝堂 / 内政
# ================================================================

class IssueDecreeRequest(BaseModel):
    """POST /api/court/decree — 颁布敕令（扩展字段，基础版见 api_models.DecreeRequest）"""
    text: str = Field(default="", max_length=2000)
    decree_type: Optional[str] = Field(default=None, max_length=32)
    faction_id: str = Field(default="", max_length=64)
    params: Optional[dict[str, Any]] = Field(default=None)

    model_config = {"extra": "ignore"}


class RecruitOfficialsRequest(BaseModel):
    """POST /api/court/recruit_officials — 招募官员"""
    faction_id: str = Field(default="", max_length=64)
    count: int = Field(default=1, ge=1, le=20)

    model_config = {"extra": "ignore"}


# ================================================================
# 军事 / 建设
# ================================================================

class SuppressRebelRequest(BaseModel):
    """POST /api/rebel/suppress — 镇压叛乱"""
    faction_id: str = Field(default="", max_length=64)
    rebel_id: str = Field(default="", max_length=64)
    troops: int = Field(default=0, ge=0, le=100000)

    model_config = {"extra": "ignore"}


class BatchRecruitRequest(BaseModel):
    """POST /api/military/batch-recruit — 批量征兵"""
    faction_id: str = Field(default="", max_length=64)
    recruitments: list[dict[str, Any]] = Field(default_factory=list, max_length=20)

    @field_validator("recruitments")
    @classmethod
    def validate_recruitments(cls, v: list) -> list:
        for item in v:
            if not isinstance(item, dict):
                raise ValueError("每项征兵必须是字典")
            if "tile_id" not in item:
                raise ValueError("每项征兵必须包含 tile_id")
            amount = item.get("amount", 0)
            if not isinstance(amount, (int, float)) or amount < 0:
                item["amount"] = max(0, int(amount))
        return v

    model_config = {"extra": "ignore"}


class ConstructBuildingRequest(BaseModel):
    """POST /api/building/construct — 建造建筑"""
    tile_id: str = Field(default="", max_length=64)
    building_type: str = Field(default="", max_length=32)
    faction_id: str = Field(default="", max_length=64)

    model_config = {"extra": "ignore"}


# ================================================================
# 皇家
# ================================================================

class MoveCapitalRequest(BaseModel):
    """POST /api/royal/move_capital — 迁都"""
    faction_id: str = Field(default="", max_length=64)
    new_tile_id: str = Field(default="", max_length=64)

    model_config = {"extra": "ignore"}


# ================================================================
# AI / 圣旨
# ================================================================

class FactionAIDecisionRequest(BaseModel):
    """POST /api/ai/faction/decisions — AI势力决策"""
    faction_id: str = Field(default="", max_length=64)
    personality: Optional[str] = Field(default="steady", max_length=32)

    model_config = {"extra": "ignore"}


class NLCommandRequest(BaseModel):
    """POST /api/ai/nl-command — 自然语言指令"""
    text: str = Field(default="", max_length=2000)
    faction_id: str = Field(default="", max_length=64)
    context: dict[str, Any] = Field(default_factory=dict)
    preferred_agents: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


# ================================================================
# 游戏初始化
# ================================================================

class GameInitRequest(BaseModel):
    """POST /api/game/init — 开局初始化"""
    faction_id: str = Field(default="", max_length=64)
    mode: str = Field(default="player_turn", max_length=32)
    custom_faction: Optional[dict[str, Any]] = Field(default=None)
    api_key: Optional[str] = Field(default=None, max_length=512)

    model_config = {"extra": "ignore"}
