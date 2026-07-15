"""
战争系统模块 (War System)

对标 CK3 的完整战争闭环：
- Casus Belli（宣战理由）→ 战争目标 → 战争分数 → 和平谈判
"""

from .casus_belli import CasusBelli, CB_CONFIG, validate_casus_belli, get_available_cb_list
from .war_score import WarScoreTracker, WarScoreEvent, WarScoreSource
from .peace_negotiation import PeaceNegotiationEngine, PeaceTerm, PEACE_TERM_CONFIG

__all__ = [
    "CasusBelli", "CB_CONFIG", "validate_casus_belli", "get_available_cb_list",
    "WarScoreTracker", "WarScoreEvent", "WarScoreSource",
    "PeaceNegotiationEngine", "PeaceTerm", "PEACE_TERM_CONFIG",
]
