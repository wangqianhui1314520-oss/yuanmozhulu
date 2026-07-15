"""
回合操作锁重机制 - 对标文明6标准化回合时序

核心规则:
1. 单回合内同类操作仅唯一生效（去重锁）
2. 全局唯一回合推进入口（统一时序）
3. 军事单位单回合单次行为
4. 内政操作回合内唯一结算
"""
from __future__ import annotations
import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("yuanmo.round_lock")


class LockCategory(str, Enum):
    """操作锁类别"""
    MARCH = "march"           # 行军调兵
    DEVELOP = "develop"       # 屯田开发
    RECRUIT = "recruit"       # 征兵
    BUY_HORSES = "buy_horses" # 买马（势力级别）
    TRAIN_TROOPS = "train_troops"  # 训练（地块级别，独立于征兵）
    TAX = "tax"               # 税政
    RELIEF = "relief"         # 赈灾
    DIPLOMACY = "diplomacy"   # 外交
    SPY = "spy"               # 细作
    BUILD = "build"           # 建造
    LAW = "law"               # 律法
    ENFEOFF = "enfeoff"       # 分封


@dataclass
class TileOperationRecord:
    """地块操作记录"""
    tile_id: str
    action: LockCategory
    round_executed: int = 0
    executed: bool = False


@dataclass
class UnitMarchRecord:
    """军事单位行军记录"""
    unit_key: str  # "{faction_id}:{from_tile}:{to_tile}"
    from_tile: str
    to_tile: str
    troops: int
    round_executed: int = 0


class RoundOperationLock:
    """
    回合操作锁管理器
    
    对标文明6: 单回合内同类操作仅唯一生效
    对标汉末霸业: 单军事单位单回合单次行为
    """
    
    def __init__(self):
        self._current_round: int = 0
        # 势力级别的操作锁: {faction_id: {LockCategory: bool}}
        self._faction_locks: dict[str, dict[str, bool]] = {}
        # 地块级别的操作锁: {tile_id: set[LockCategory]}
        self._tile_locks: dict[str, set[str]] = {}
        # 军事单位行军锁: set[unit_key]
        self._march_records: set[str] = set()
        # 地块操作记录（用于前端展示冷却状态）
        self._tile_records: dict[str, list[TileOperationRecord]] = {}
    
    def new_round(self, round_num: int):
        """新回合开始，清空所有锁"""
        self._current_round = round_num
        self._faction_locks.clear()
        self._tile_locks.clear()
        self._march_records.clear()
        self._tile_records.clear()
        logger.debug(f"[操作锁] 第{round_num}回合开始，所有锁已重置")
    
    def check_faction_lock(self, faction_id: str, category: LockCategory) -> bool:
        """
        检查势力级别操作是否已被锁定
        
        Returns:
            True 表示已被锁定（不可重复操作），False 表示可以操作
        """
        if faction_id not in self._faction_locks:
            return False
        return category.value in self._faction_locks[faction_id]
    
    def acquire_faction_lock(self, faction_id: str, category: LockCategory) -> bool:
        """
        尝试获取势力操作锁
        
        Returns:
            True 表示获取成功，False 表示已被锁定
        """
        if faction_id not in self._faction_locks:
            self._faction_locks[faction_id] = {}
        
        if category.value in self._faction_locks[faction_id]:
            logger.warning(
                f"[操作锁] 势力{faction_id}的{category.value}操作已被锁定，拒绝重复"
            )
            return False
        
        self._faction_locks[faction_id][category.value] = True
        return True
    
    def check_tile_lock(self, tile_id: str, category: LockCategory) -> bool:
        """检查地块级别操作是否已被锁定"""
        if tile_id not in self._tile_locks:
            return False
        return category.value in self._tile_locks[tile_id]
    
    def acquire_tile_lock(self, tile_id: str, category: LockCategory) -> bool:
        """尝试获取地块操作锁"""
        if tile_id not in self._tile_locks:
            self._tile_locks[tile_id] = set()
        
        if category.value in self._tile_locks[tile_id]:
            logger.warning(
                f"[操作锁] 地块{tile_id}的{category.value}操作已被锁定，拒绝重复"
            )
            return False
        
        self._tile_locks[tile_id].add(category.value)
        
        # 记录操作（用于前端展示）
        if tile_id not in self._tile_records:
            self._tile_records[tile_id] = []
        self._tile_records[tile_id].append(
            TileOperationRecord(
                tile_id=tile_id,
                action=category,
                round_executed=self._current_round,
                executed=True,
            )
        )
        return True
    
    def check_march_lock(self, faction_id: str, from_tile: str, to_tile: str) -> bool:
        """
        检查军事行军是否已被锁定
        
        单支部队单回合仅可执行一次调兵/攻城/驻防
        """
        unit_key = f"{faction_id}:{from_tile}"
        return unit_key in self._march_records
    
    def acquire_march_lock(self, faction_id: str, from_tile: str, to_tile: str) -> bool:
        """尝试获取行军锁"""
        unit_key = f"{faction_id}:{from_tile}"
        if unit_key in self._march_records:
            logger.warning(
                f"[操作锁] 势力{faction_id}从{from_tile}的行军已被锁定，拒绝重复行军"
            )
            return False
        
        self._march_records.add(unit_key)
        return True
    
    def get_tile_cooling_actions(self, tile_id: str) -> list[dict]:
        """
        获取地块已执行操作列表（用于前端冷却提示）
        
        Returns:
            [{"action": "develop", "round": 5}, ...]
        """
        records = self._tile_records.get(tile_id, [])
        return [
            {"action": r.action.value, "round": r.round_executed}
            for r in records if r.executed
        ]
    
    def get_faction_locked_actions(self, faction_id: str) -> list[str]:
        """获取势力已锁定的操作类型列表"""
        locks = self._faction_locks.get(faction_id, {})
        return [k for k, v in locks.items() if v]
    
    def is_any_march_locked(self, faction_id: str) -> bool:
        """检查势力是否有任何部队本回合已行军"""
        for key in self._march_records:
            if key.startswith(f"{faction_id}:"):
                return True
        return False


# 全局单例（线程安全）
import threading as _threading
_global_round_lock: Optional[RoundOperationLock] = None
_round_lock_init_mutex = _threading.Lock()


def get_round_lock() -> RoundOperationLock:
    """获取全局回合操作锁单例（线程安全）"""
    global _global_round_lock
    if _global_round_lock is None:
        with _round_lock_init_mutex:
            if _global_round_lock is None:
                _global_round_lock = RoundOperationLock()
                logger.info("全局回合操作锁已初始化")
    return _global_round_lock


def reset_round_lock():
    """重置全局锁（用于对局重启）"""
    global _global_round_lock
    _global_round_lock = RoundOperationLock()
    logger.info("全局回合操作锁已重置")
