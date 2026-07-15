"""
战争分数系统 · 对标 CK3

职责：
1. 追踪每场战争的战争分数（-100 ~ +100）
2. 根据战斗、占领、围城等事件计算分数变化
3. 提供战争状态判定（优势/劣势/胶着）
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("yuanmo.war.score")


class WarScoreSource(Enum):
    """战争分数来源"""
    BATTLE_VICTORY = "battle_victory"         # 赢得战斗
    BATTLE_DEFEAT = "battle_defeat"           # 输掉战斗
    OCCUPIED_TILE = "occupied_tile"           # 占领地块
    LOST_TILE = "lost_tile"                   # 失去地块
    OCCUPIED_CAPITAL = "occupied_capital"     # 占领首都
    LOST_CAPITAL = "lost_capital"             # 丢失首都
    SIEGE_WON = "siege_won"                   # 围城胜利
    SIEGE_LOST = "siege_lost"                 # 围城失败
    TICKING_WARSCORE = "ticking_warscore"     # 持有战争目标的时间加成
    ALLY_JOINED = "ally_joined"               # 盟友参战
    ALLY_DEFECTED = "ally_defected"           # 盟友背叛
    CAPTURED_LEADER = "captured_leader"       # 俘虏敌方首领
    TRIBUTE_PAID = "tribute_paid"             # 对方纳贡


@dataclass
class WarScoreEvent:
    """战争分数变化事件"""
    source: WarScoreSource
    value: float                            # 分数变化值（正=进攻方得分）
    round: int
    description: str
    tile_id: Optional[str] = None
    troops_involved: Optional[int] = None


@dataclass
class WarScoreTracker:
    """
    单场战争的分数追踪器

    分数范围: -100（进攻方惨败） ~ +100（进攻方完胜）
    正分 = 进攻方优势，负分 = 防守方优势
    """

    war_id: str
    attacker_faction: str
    defender_faction: str

    # 核心分数
    war_score: float = 0.0                  # 当前总分

    # 分数子项
    battle_score: float = 0.0               # 战斗分数
    occupation_score: float = 0.0           # 占领分数
    ticking_score: float = 0.0              # 战争目标持有分数
    special_score: float = 0.0              # 特殊事件分数

    # 事件历史
    events: list[WarScoreEvent] = field(default_factory=list)

    # 战争目标持续持有回合数
    war_goal_held_rounds: int = 0

    # 配置
    war_score_multiplier: float = 1.0       # CB 决定的分数倍率
    war_goal_tiles: set = field(default_factory=set)  # 战争目标地块

    # ================================================================
    # 分数变化常量（基准值，实际 = 基准 × CB倍率）
    # ================================================================
    SCORE_BATTLE_VICTORY = 10.0
    SCORE_BATTLE_DEFEAT = -12.0
    SCORE_OCCUPIED_TILE = 8.0
    SCORE_LOST_TILE = -10.0
    SCORE_OCCUPIED_CAPITAL = 25.0
    SCORE_LOST_CAPITAL = -30.0
    SCORE_SIEGE_WON = 8.0
    SCORE_SIEGE_LOST = -10.0
    SCORE_TICKING_MAX = 50.0               # 战争目标持有最大累计分
    SCORE_TICKING_PER_ROUND = 2.0           # 每回合加成
    SCORE_ALLY_JOINED = 5.0
    SCORE_ALLY_DEFECTED = -8.0
    SCORE_CAPTURED_LEADER = 20.0

    def record_event(
        self,
        source: WarScoreSource,
        base_value: float,
        round_num: int,
        description: str,
        tile_id: Optional[str] = None,
        troops_involved: Optional[int] = None,
    ):
        """记录战争分数变化事件"""
        scaled_value = base_value * self.war_score_multiplier
        self.events.append(WarScoreEvent(
            source=source,
            value=scaled_value,
            round=round_num,
            description=description,
            tile_id=tile_id,
            troops_involved=troops_involved,
        ))

        # 分配到子项
        if source in (WarScoreSource.BATTLE_VICTORY, WarScoreSource.BATTLE_DEFEAT):
            self.battle_score += scaled_value
        elif source in (WarScoreSource.OCCUPIED_TILE, WarScoreSource.LOST_TILE,
                         WarScoreSource.OCCUPIED_CAPITAL, WarScoreSource.LOST_CAPITAL,
                         WarScoreSource.SIEGE_WON, WarScoreSource.SIEGE_LOST):
            self.occupation_score += scaled_value
        elif source == WarScoreSource.TICKING_WARSCORE:
            self.ticking_score += scaled_value
        else:
            self.special_score += scaled_value

        # 更新总分并裁剪到 [-100, 100]
        old_score = self.war_score
        self.war_score = max(-100.0, min(100.0, self.war_score + scaled_value))

        logger.info(
            f"[WarScore] {self.war_id}: {description} "
            f"({old_score:+.1f} → {self.war_score:+.1f}, Δ{scaled_value:+.1f})"
        )

    def tick(self, round_num: int, war_goal_held_count: int):
        """
        每回合推进：计算战争目标持有的渐进分数

        当进攻方控制了战争目标地块时，每回合获得渐进分数。
        渐进分数有上限（防止挂机躺赢）。
        """
        if war_goal_held_count <= 0:
            self.war_goal_held_rounds = 0
            return

        self.war_goal_held_rounds += 1
        if self.ticking_score >= self.SCORE_TICKING_MAX:
            return

        tick_value = min(
            self.SCORE_TICKING_PER_ROUND * war_goal_held_count * self.war_score_multiplier,
            self.SCORE_TICKING_MAX - self.ticking_score,
        )
        if tick_value > 0:
            self.record_event(
                source=WarScoreSource.TICKING_WARSCORE,
                base_value=tick_value / self.war_score_multiplier,
                round_num=round_num,
                description=f"持有{war_goal_held_count}个战争目标地块的持续优势",
            )

    def get_status(self) -> dict:
        """获取战争状态摘要"""
        # 判定优势方
        if self.war_score >= 75:
            advantage = "attacker_crushing"     # 进攻方碾压
            can_enforce = True
        elif self.war_score >= 50:
            advantage = "attacker_winning"      # 进攻方优势
            can_enforce = True
        elif self.war_score >= 25:
            advantage = "attacker_slight"       # 进攻方小优
            can_enforce = False
        elif self.war_score >= -25:
            advantage = "stalemate"             # 胶着
            can_enforce = False
        elif self.war_score >= -50:
            advantage = "defender_slight"       # 防守方小优
            can_enforce = False
        elif self.war_score >= -75:
            advantage = "defender_winning"      # 防守方优势
            can_enforce = True  # 防守方可以强制白和平
        else:
            advantage = "defender_crushing"     # 防守方碾压
            can_enforce = True  # 防守方可以反制

        return {
            "war_score": round(self.war_score, 1),
            "advantage": advantage,
            "can_enforce_demands": can_enforce,
            "breakdown": {
                "battle": round(self.battle_score, 1),
                "occupation": round(self.occupation_score, 1),
                "ticking": round(self.ticking_score, 1),
                "special": round(self.special_score, 1),
            },
            "events_count": len(self.events),
            "war_goal_held_rounds": self.war_goal_held_rounds,
        }

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        """获取最近的战争分数事件"""
        return [
            {
                "source": e.source.value,
                "value": round(e.value, 1),
                "round": e.round,
                "description": e.description,
                "tile_id": e.tile_id,
                "troops_involved": e.troops_involved,
            }
            for e in self.events[-limit:]
        ]
