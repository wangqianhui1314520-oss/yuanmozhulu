"""核心模块 - 3.1 扩展"""
from .round_lock import RoundOperationLock, LockCategory, get_round_lock, reset_round_lock
from .mode_manager import GameModeManager, GameMode, get_mode_manager, reset_mode_manager
from .responsibility import ResponsibilityTracker, EventDomain, DOMAIN_OWNER, get_responsibility_tracker, reset_responsibility_tracker
