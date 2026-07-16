"""
元末逐鹿 3.0 — 成就系统
回合结算时自动检测成就解锁条件，支持20+成就，含通知推送和历史记录

设计原则：
- 成就检测在每回合结算后执行（无侵入式钩子）
- 成就持久化到 JSON（server/data/achievements.json）
- 解锁时通过事件总线推送通知
"""
from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger("yuanmo.achievement")


# ================================================================
# 成就定义
# ================================================================
@dataclass
class AchievementDef:
    id: str
    name: str
    description: str
    category: str  # military/economy/diplomacy/internal/exploration/special
    icon: str  # emoji 图标
    rarity: str = "common"  # common/rare/epic/legendary
    check_fn: Optional[Callable] = None  # (world, faction_id) -> bool


# ================================================================
# 成就注册表（20+ 成就）
# ================================================================
ACHIEVEMENTS: list[AchievementDef] = [
    # ===== 军事 (military) =====
    AchievementDef(
        id="first_blood", name="初试锋芒", category="military", icon="🗡", rarity="common",
        description="赢得第一场战斗",
    ),
    AchievementDef(
        id="great_victory", name="大破敌军", category="military", icon="⚔", rarity="rare",
        description="单场战斗歼敌超过5000",
    ),
    AchievementDef(
        id="city_conqueror", name="攻城略地", category="military", icon="🏰", rarity="rare",
        description="累计占领10座城池",
    ),
    AchievementDef(
        id="warlord", name="一方诸侯", category="military", icon="👑", rarity="epic",
        description="消灭一个敌对势力",
    ),
    AchievementDef(
        id="invincible", name="百战不殆", category="military", icon="🛡", rarity="legendary",
        description="连续10场战斗不败",
    ),
    AchievementDef(
        id="grand_army", name="雄兵十万", category="military", icon="🏇", rarity="epic",
        description="总兵力超过10万",
    ),

    # ===== 经济 (economy) =====
    AchievementDef(
        id="wealthy", name="富甲一方", category="economy", icon="💰", rarity="common",
        description="国库银两超过5000",
    ),
    AchievementDef(
        id="granary_full", name="仓廪丰实", category="economy", icon="🌾", rarity="common",
        description="粮仓储量超过10000石",
    ),
    AchievementDef(
        id="trade_master", name="通商天下", category="economy", icon="🚢", rarity="rare",
        description="建立5条以上贸易路线",
    ),
    AchievementDef(
        id="golden_treasury", name="富可敌国", category="economy", icon="🏦", rarity="epic",
        description="国库银两超过50000",
    ),
    AchievementDef(
        id="booming_population", name="人口兴旺", category="economy", icon="👥", rarity="rare",
        description="总人口超过50万",
    ),

    # ===== 外交 (diplomacy) =====
    AchievementDef(
        id="ally_maker", name="合纵连横", category="diplomacy", icon="🤝", rarity="rare",
        description="同时与3个势力结盟",
    ),
    AchievementDef(
        id="peacekeeper", name="止戈为武", category="diplomacy", icon="🕊", rarity="rare",
        description="成功调解两方战争",
    ),
    AchievementDef(
        id="vassal_lord", name="天下共主", category="diplomacy", icon="🏴", rarity="epic",
        description="拥有3个附庸国",
    ),
    AchievementDef(
        id="master_negotiator", name="纵横大家", category="diplomacy", icon="📜", rarity="legendary",
        description="累计签订10份条约",
    ),

    # ===== 内政 (internal) =====
    AchievementDef(
        id="reformer", name="变法图强", category="internal", icon="📋", rarity="rare",
        description="解锁10项国策",
    ),
    AchievementDef(
        id="stable_realm", name="国泰民安", category="internal", icon="🏛", rarity="rare",
        description="民心稳定度达到80以上",
    ),
    AchievementDef(
        id="popular", name="万民景仰", category="internal", icon="🌟", rarity="epic",
        description="声望达到100",
    ),
    AchievementDef(
        id="sage_ruler", name="圣主明君", category="internal", icon="☀", rarity="legendary",
        description="民心、声望、朝堂稳定三项均达到90以上",
    ),

    # ===== 探索 (exploration) =====
    AchievementDef(
        id="scout_master", name="烽火斥候", category="exploration", icon="🔭", rarity="common",
        description="获得10个地块的完整情报",
    ),
    AchievementDef(
        id="sea_explorer", name="扬帆出海", category="exploration", icon="⛵", rarity="rare",
        description="拥有水师并探索沿海全部地块",
    ),

    # ===== 特殊 (special) =====
    AchievementDef(
        id="dragon_slayer", name="屠龙者", category="special", icon="🐉", rarity="legendary",
        description="消灭元廷势力",
    ),
    AchievementDef(
        id="unifier", name="天下归一", category="special", icon="🏆", rarity="legendary",
        description="统一天下（成为唯一存活势力）",
    ),
    AchievementDef(
        id="survivor", name="乱世幸存", category="special", icon="⏳", rarity="rare",
        description="存活50回合",
    ),
    AchievementDef(
        id="centenarian", name="百年基业", category="special", icon="🎋", rarity="epic",
        description="存活100回合",
    ),
]


# ================================================================
# 成就存储与加载
# ================================================================
class AchievementTracker:
    """成就追踪器 — 单例模式，按势力追踪"""

    _instance: Optional["AchievementTracker"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_path = Path(__file__).parent.parent / "data" / "achievements.json"
        self._achievements: dict[str, dict] = {}  # faction_id -> {achievement_id: unlock_info}
        self._newly_unlocked: dict[str, list[str]] = {}  # faction_id -> [achievement_id] (本回合新解锁)
        self._load()

    def _load(self):
        """从 JSON 加载成就数据"""
        if self._data_path.exists():
            try:
                with open(self._data_path, "r", encoding="utf-8") as f:
                    self._achievements = json.load(f)
            except Exception:
                logger.warning("成就数据加载失败，从零开始")
                self._achievements = {}
        else:
            self._achievements = {}

    def _save(self):
        """持久化到 JSON"""
        os.makedirs(self._data_path.parent, exist_ok=True)
        try:
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(self._achievements, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"成就数据保存失败: {e}")

    def is_unlocked(self, faction_id: str, achievement_id: str) -> bool:
        return achievement_id in self._achievements.get(faction_id, {})

    def get_unlocked(self, faction_id: str) -> dict:
        return self._achievements.get(faction_id, {})

    def get_newly_unlocked(self, faction_id: str) -> list[dict]:
        """获取本回合新解锁的成就（带详情）"""
        new_ids = self._newly_unlocked.get(faction_id, [])
        result = []
        for ach_id in new_ids:
            ach_def = _get_achievement_def(ach_id)
            if ach_def:
                unlock_info = self._achievements.get(faction_id, {}).get(ach_id, {})
                result.append({
                    "id": ach_id,
                    "name": ach_def.name,
                    "description": ach_def.description,
                    "icon": ach_def.icon,
                    "category": ach_def.category,
                    "rarity": ach_def.rarity,
                    "unlocked_at": unlock_info.get("unlocked_at", ""),
                })
        return result

    def unlock(self, faction_id: str, achievement_id: str, round_num: int = 0):
        """解锁成就（如已解锁则跳过）"""
        if faction_id not in self._achievements:
            self._achievements[faction_id] = {}

        if achievement_id in self._achievements[faction_id]:
            return  # 已解锁，跳过

        self._achievements[faction_id][achievement_id] = {
            "unlocked_at": datetime.now().isoformat(),
            "unlocked_round": round_num,
        }

        # 记录到本回合新解锁列表
        if faction_id not in self._newly_unlocked:
            self._newly_unlocked[faction_id] = []
        self._newly_unlocked[faction_id].append(achievement_id)

        ach_def = _get_achievement_def(achievement_id)
        name = ach_def.name if ach_def else achievement_id
        logger.info(f"🏆 [{faction_id}] 解锁成就: {name}")

        self._save()

    def clear_round_new(self, faction_id: str):
        """清除本回合新解锁缓存"""
        self._newly_unlocked.pop(faction_id, None)

    def get_all_achievements(self) -> list[dict]:
        """获取全部成就定义（含解锁状态供前端查询）"""
        return [
            {
                "id": a.id, "name": a.name, "description": a.description,
                "category": a.category, "icon": a.icon, "rarity": a.rarity,
            }
            for a in ACHIEVEMENTS
        ]


def _get_achievement_def(ach_id: str) -> Optional[AchievementDef]:
    for a in ACHIEVEMENTS:
        if a.id == ach_id:
            return a
    return None


# ================================================================
# 成就检测逻辑（每回合结算后调用）
# ================================================================
def check_achievements(world, tracker: Optional[AchievementTracker] = None) -> list[dict]:
    """检测所有势力本回合是否解锁新成就

    Args:
        world: WorldState 实例（需有 factions/tiles/events 等属性）
        tracker: AchievementTracker 实例，默认使用单例

    Returns:
        list[dict]: 本回合新解锁的成就列表（含 faction_id）
    """
    if tracker is None:
        tracker = AchievementTracker()

    all_new: list[dict] = []

    for fid, faction in getattr(world, "factions", {}).items():
        faction_data = faction if isinstance(faction, dict) else {}
        faction_obj = faction if not isinstance(faction, dict) else None

        # 获取势力基本属性
        treasury = _get_attr(faction, "treasury", 0)
        grain = _get_attr(faction, "grain", 0)
        total_troops = _get_attr(faction, "total_troops", 0)
        total_pop = _get_attr(faction, "total_population", 0)
        realm_stab = _get_attr(faction, "realm_stability", 0)
        reputation = _get_attr(faction, "reputation", 0)
        court_stab = _get_attr(faction, "court_stability", 0)
        unlocked_pols = _get_attr(faction, "unlocked_policies", [])
        tile_count = _get_attr(faction, "tile_count", 0)
        alive = _get_attr(faction, "is_alive", True)
        round_num = getattr(world, "current_round", 0)

        if not alive:
            continue

        # ---- 经济成就 ----
        if treasury >= 5000:
            tracker.unlock(fid, "wealthy", round_num)
        if treasury >= 50000:
            tracker.unlock(fid, "golden_treasury", round_num)
        if grain >= 10000:
            tracker.unlock(fid, "granary_full", round_num)
        if total_pop >= 500000:
            tracker.unlock(fid, "booming_population", round_num)

        # ---- 军事成就 ----
        if total_troops >= 100000:
            tracker.unlock(fid, "grand_army", round_num)
        if tile_count >= 10:
            tracker.unlock(fid, "city_conqueror", round_num)

        # ---- 内政成就 ----
        if isinstance(unlocked_pols, list) and len(unlocked_pols) >= 10:
            tracker.unlock(fid, "reformer", round_num)
        if realm_stab >= 80:
            tracker.unlock(fid, "stable_realm", round_num)
        if reputation >= 100:
            tracker.unlock(fid, "popular", round_num)
        if realm_stab >= 90 and reputation >= 90 and court_stab >= 90:
            tracker.unlock(fid, "sage_ruler", round_num)

        # ---- 特殊成就 ----
        if round_num >= 50:
            tracker.unlock(fid, "survivor", round_num)
        if round_num >= 100:
            tracker.unlock(fid, "centenarian", round_num)

        # ---- 统一检测 ----
        alive_factions = [_get_attr(f, "is_alive", True) for f in
                          (getattr(world, "factions", {}) or {}).values()]
        alive_count = sum(1 for a in alive_factions if a)
        if alive_count <= 1:
            tracker.unlock(fid, "unifier", round_num)

        # ---- 元廷消灭 ----
        yuan_alive = False
        for yfid, yf in (getattr(world, "factions", {}) or {}).items():
            if "yuan" in yfid.lower() or "元" in yfid:
                if _get_attr(yf, "is_alive", True):
                    yuan_alive = True
                    break
        if not yuan_alive:
            tracker.unlock(fid, "dragon_slayer", round_num)

        # 收集本回合新解锁
        newly = tracker.get_newly_unlocked(fid)
        for n in newly:
            all_new.append({**n, "faction_id": fid})

    return all_new


def _get_attr(obj, attr: str, default: Any = 0) -> Any:
    """安全获取对象/字典属性"""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    if obj is None:
        return default
    return getattr(obj, attr, default)


# ================================================================
# 成就游戏事件钩子（由战斗/外交等事件触发）
# ================================================================
def on_battle_won(faction_id: str, enemy_killed: int, tracker: Optional[AchievementTracker] = None):
    """战斗胜利钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    tracker.unlock(faction_id, "first_blood")
    if enemy_killed >= 5000:
        tracker.unlock(faction_id, "great_victory")


def on_warlord_eliminated(faction_id: str, tracker: Optional[AchievementTracker] = None):
    """消灭势力钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    tracker.unlock(faction_id, "warlord")


def on_alliance_formed(faction_id: str, ally_count: int, tracker: Optional[AchievementTracker] = None):
    """结盟钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if ally_count >= 3:
        tracker.unlock(faction_id, "ally_maker")


def on_peace_mediated(faction_id: str, tracker: Optional[AchievementTracker] = None):
    """调解战争钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    tracker.unlock(faction_id, "peacekeeper")


def on_vassal_gained(faction_id: str, vassal_count: int, tracker: Optional[AchievementTracker] = None):
    """获得附庸钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if vassal_count >= 3:
        tracker.unlock(faction_id, "vassal_lord")


def on_treaty_signed(faction_id: str, treaty_count: int, tracker: Optional[AchievementTracker] = None):
    """签订条约钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if treaty_count >= 10:
        tracker.unlock(faction_id, "master_negotiator")


def on_trade_route_established(faction_id: str, route_count: int, tracker: Optional[AchievementTracker] = None):
    """贸易路线钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if route_count >= 5:
        tracker.unlock(faction_id, "trade_master")


def on_intel_gathered(faction_id: str, intel_count: int, tracker: Optional[AchievementTracker] = None):
    """情报收集钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if intel_count >= 10:
        tracker.unlock(faction_id, "scout_master")


def on_naval_explored(faction_id: str, coastal_explored: int, total_coastal: int,
                      tracker: Optional[AchievementTracker] = None):
    """海上探索钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if total_coastal > 0 and coastal_explored >= total_coastal:
        tracker.unlock(faction_id, "sea_explorer")


def on_battle_streak(faction_id: str, streak: int, tracker: Optional[AchievementTracker] = None):
    """连胜钩子"""
    if tracker is None:
        tracker = AchievementTracker()
    if streak >= 10:
        tracker.unlock(faction_id, "invincible")


# ================================================================
# 导出
# ================================================================
__all__ = [
    "AchievementTracker", "AchievementDef", "ACHIEVEMENTS",
    "check_achievements", "on_battle_won", "on_warlord_eliminated",
    "on_alliance_formed", "on_peace_mediated", "on_vassal_gained",
    "on_treaty_signed", "on_trade_route_established", "on_intel_gathered",
    "on_naval_explored", "on_battle_streak",
]
