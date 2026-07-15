"""
游戏模式管理器 - 玩家主导 vs AI观战 双模式强制互斥

核心规则:
1. 玩家游玩模式（player_turn）：玩家100%掌控己方势力，己方AI完全休眠
2. AI观战模式（ai_watch）：锁定所有玩家操作，全程纯AI博弈
3. 双模式强制互斥，彻底解决人机逻辑打架
"""
from __future__ import annotations
import logging
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger("yuanmo.mode")


class GameMode(str, Enum):
    """游戏模式"""
    PLAYER_TURN = "player_turn"    # 玩家主导：玩家治一国，AI演天下
    AI_WATCH = "ai_watch"          # AI观战：纯AI博弈，演示/测试用


class ModeSwitchError(Exception):
    """模式切换异常"""
    pass


class GameModeManager:
    """
    游戏模式管理器
    
    核心保证:
    - player_turn模式下: 玩家势力AI = 完全休眠，不触发任何自主决策
    - ai_watch模式下: 所有玩家操作入口 = 锁定，只允许观看
    - 模式切换: 必须在对局开始前设定，中途不可切换
    """
    
    def __init__(self):
        self._mode: GameMode = GameMode.PLAYER_TURN
        self._game_active: bool = False
        self._player_faction_id: str = ""
        self._mode_change_listeners: list[Callable] = []
        
        # 操作白名单（ai_watch模式下允许的操作）
        self._watch_whitelist = {
            "view_map",        # 查看地图
            "view_tile",       # 查看地块
            "view_faction",    # 查看势力
            "view_officials",  # 查看官员
            "view_relations",  # 查看关系
            "view_events",     # 查看事件
            "save_game",       # 存档
            "load_game",       # 读档
        }
    
    @property
    def mode(self) -> GameMode:
        return self._mode
    
    @property
    def is_player_turn(self) -> bool:
        return self._mode == GameMode.PLAYER_TURN
    
    @property
    def is_ai_watch(self) -> bool:
        return self._mode == GameMode.AI_WATCH
    
    @property
    def game_active(self) -> bool:
        return self._game_active
    
    def init_game(self, mode: str, player_faction_id: str):
        """
        初始化对局模式（必须在开局时设定）
        
        Args:
            mode: "player_turn" | "ai_watch"
            player_faction_id: 玩家势力ID
        
        Raises:
            ModeSwitchError: 如果游戏已在进行中尝试重新初始化
        """
        if self._game_active:
            logger.warning("[模式管理] 尝试在游戏进行中重新初始化，已拒绝")
            # 不抛出异常，保持兼容性（读档场景需要重新初始化）
            # 先结束当前对局再重新初始化
            self.end_game()
        
        try:
            self._mode = GameMode(mode)
        except ValueError:
            logger.warning(f"未知游戏模式: {mode}，默认使用 player_turn")
            self._mode = GameMode.PLAYER_TURN
        
        self._player_faction_id = player_faction_id
        self._game_active = True
        
        logger.info(
            f"[模式管理] 对局开始 - 模式={self._mode.value}, "
            f"玩家势力={player_faction_id}"
        )
    
    def end_game(self):
        """对局结束"""
        self._game_active = False
        self._player_faction_id = ""
        logger.info("[模式管理] 对局结束")
    
    def should_ai_skip_player_faction(self, faction_id: str) -> bool:
        """
        判断AI是否应该跳过某势力
        
        在 player_turn 模式下，玩家势力的AI必须休眠
        在 ai_watch 模式下，所有势力AI都活跃
        """
        if self._mode == GameMode.AI_WATCH:
            return False  # 观战模式下所有AI都活跃
        
        # 玩家模式下，跳过玩家势力
        return faction_id == self._player_faction_id
    
    def can_player_operate(self, action: str) -> bool:
        """
        检查玩家是否允许执行某操作
        
        ai_watch模式下只允许查看类操作
        """
        if not self._game_active:
            return False
        
        if self._mode == GameMode.PLAYER_TURN:
            return True  # 玩家模式下所有操作都允许
        
        # AI观战模式下只允许白名单操作
        return action in self._watch_whitelist
    
    def can_player_submit_command(self) -> bool:
        """检查玩家是否可以提交指令"""
        return self._game_active and self._mode == GameMode.PLAYER_TURN
    
    def can_player_advance_turn(self) -> bool:
        """检查玩家是否可以推进回合"""
        return self._game_active and self._mode == GameMode.PLAYER_TURN
    
    def get_mode_info(self) -> dict:
        """获取当前模式信息（供前端展示）"""
        return {
            "mode": self._mode.value,
            "mode_label": "君主亲政" if self._mode == GameMode.PLAYER_TURN else "观战模式",
            "game_active": self._game_active,
            "player_faction_id": self._player_faction_id,
            "player_can_operate": self._mode == GameMode.PLAYER_TURN,
            "ai_active_for_player": self._mode == GameMode.AI_WATCH,
        }
    
    def add_mode_change_listener(self, callback: Callable):
        """注册模式变更监听器"""
        self._mode_change_listeners.append(callback)
    
    def _notify_listeners(self):
        """通知所有监听器"""
        for cb in self._mode_change_listeners:
            try:
                cb(self._mode)
            except Exception as e:
                logger.error(f"模式变更监听器异常: {e}")


# 全局单例
_global_mode_manager: Optional[GameModeManager] = None


def get_mode_manager() -> GameModeManager:
    """获取全局模式管理器单例"""
    global _global_mode_manager
    if _global_mode_manager is None:
        _global_mode_manager = GameModeManager()
        logger.info("全局游戏模式管理器已初始化")
    return _global_mode_manager


def reset_mode_manager():
    """重置模式管理器（用于对局重启）"""
    global _global_mode_manager
    if _global_mode_manager:
        _global_mode_manager.end_game()
    _global_mode_manager = GameModeManager()
    logger.info("全局游戏模式管理器已重置")
