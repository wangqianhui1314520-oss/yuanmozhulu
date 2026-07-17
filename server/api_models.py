"""
Pydantic 请求模型 — 为关键 API 端点提供类型安全与输入校验。
渐进式迁移：现有端点逐步从 dict 迁移到具体模型。
extra="ignore" 确保现有前端额外字段不触发 422 错误。
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional


class DiplomacyActionRequest(BaseModel):
    """外交行动（遣使/结盟/宣战/朝贡/附庸/和谈/联姻/深化关系）"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    action_type: str = Field(..., min_length=1, max_length=32)
    target_faction: str = Field(..., min_length=1, max_length=64)
    amount: int = Field(default=0, ge=0, le=100000)
    message: str = Field(default="", max_length=500)
    casus_belli: str = Field(default="", max_length=200)
    terms: Optional[dict] = None

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        allowed = {"envoy", "alliance", "war", "tribute", "vassal", "peace", "marriage", "deepen"}
        if v not in allowed:
            raise ValueError(f"不支持的外交操作: {v}，允许的值: {allowed}")
        return v


class WarDeclareRequest(BaseModel):
    """宣战请求"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    target_faction: str = Field(..., min_length=1, max_length=64)
    casus_belli: str = Field(default="", max_length=200)
    troops: int = Field(default=0, ge=0, le=100000)


class DecreeRequest(BaseModel):
    """颁布敕令"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    decree_text: str = Field(..., min_length=1, max_length=2000)
    decree_type: str = Field(default="general", max_length=32)


class UnlockPolicyRequest(BaseModel):
    """解锁国策"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    policy_id: str = Field(..., min_length=1, max_length=64)


class MarchResolveRequest(BaseModel):
    """行军/战斗结算"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    from_tile: str = Field(..., min_length=1, max_length=64)
    to_tile: str = Field(..., min_length=1, max_length=64)
    troops: int = Field(default=0, ge=0, le=50000)
    grain_supply: int = Field(default=0, ge=0, le=100000)
    general_id: str = Field(default="", max_length=64)


class EdictProcessRequest(BaseModel):
    """圣旨处理（自然语言）"""
    model_config = ConfigDict(extra="ignore")
    edict_text: str = Field(..., min_length=1, max_length=5000)
    faction_id: str = Field(..., min_length=1, max_length=64)
    use_ai: bool = True
    use_simulation: bool = True
    direct_execute: bool = False
    source: Optional[str] = None  # 'advisor' 表示来自幕僚，后端跳过谋略问询路由


class EdictExecuteRequest(BaseModel):
    """圣旨执行"""
    model_config = ConfigDict(extra="ignore")
    edict_text: str = Field(..., min_length=1, max_length=5000)
    faction_id: str = Field(..., min_length=1, max_length=64)
    commands: list[dict] = []
    direct_execute: bool = True


class TradeRouteRequest(BaseModel):
    """开通贸易路线"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    target_faction: str = Field(..., min_length=1, max_length=64)
    goods: str = Field(default="general", max_length=128)
    amount: int = Field(default=0, ge=0, le=50000)


class RuntimeConfigRequest(BaseModel):
    """热更新 LLM 运行时配置"""
    model_config = ConfigDict(extra="ignore")
    advisor: Optional[dict] = None
    law: Optional[dict] = None
    enemy: Optional[dict] = None
    max_concurrent: Optional[int] = None
    fallback_enabled: Optional[bool] = None

    @field_validator("max_concurrent")
    @classmethod
    def clamp_concurrent(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return max(1, min(v, 100))
        return v


class AIFactionDecisionsRequest(BaseModel):
    """AI 势力决策请求"""
    model_config = ConfigDict(extra="ignore")
    faction_id: str = Field(..., min_length=1, max_length=64)
    context: Optional[dict] = None
    urgent: bool = False
