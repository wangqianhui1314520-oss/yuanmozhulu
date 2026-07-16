"""核心模块 - 3.3 扩展"""
from .round_lock import RoundOperationLock, LockCategory, get_round_lock, reset_round_lock
from .mode_manager import GameModeManager, GameMode, get_mode_manager, reset_mode_manager
from .responsibility import ResponsibilityTracker, EventDomain, DOMAIN_OWNER, get_responsibility_tracker, reset_responsibility_tracker
# 3.3 新增模块
from .economy_engine import EconomyEngine, TradeGood, PopulationStructure, FACTION_SPECIALTY
from .road_system import RoadSystem, RoadType, RoadSegment, PostalRelayStation
from .fog_of_war import FogOfWarEngine, VisibilityLevel, FogTileRecord
