"""API请求/响应数据模型（扩展集）· 元末逐鹿 4.0

H-2 修复：补充 api_models.py 未包含的端点模型。
已存在于 api_models 的模型请从 api_models 导入。
"""

from .requests import (
    OpenTradeRequest,
    SignPeaceRequest,
    DemandTributeRequest,
    OfferVassalRequest,
    DeclareWarRequest,
    ProposePeaceRequest,
    IssueDecreeRequest,
    RecruitOfficialsRequest,
    SuppressRebelRequest,
    BatchRecruitRequest,
    ConstructBuildingRequest,
    MoveCapitalRequest,
    FactionAIDecisionRequest,
    NLCommandRequest,
    GameInitRequest,
)

__all__ = [
    "OpenTradeRequest",
    "SignPeaceRequest",
    "DemandTributeRequest",
    "OfferVassalRequest",
    "DeclareWarRequest",
    "ProposePeaceRequest",
    "IssueDecreeRequest",
    "RecruitOfficialsRequest",
    "SuppressRebelRequest",
    "BatchRecruitRequest",
    "ConstructBuildingRequest",
    "MoveCapitalRequest",
    "FactionAIDecisionRequest",
    "NLCommandRequest",
    "GameInitRequest",
]
