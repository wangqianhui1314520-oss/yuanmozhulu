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

    # v3.4 新增：厌战度与战斗规模
    total_rounds: int = 0                     # 战争已持续回合数
    war_exhaustion_attacker: float = 0.0      # 进攻方厌战度 (0~100)
    war_exhaustion_defender: float = 0.0      # 防守方厌战度 (0~100)
    total_casualties_attacker: int = 0        # 进攻方累计伤亡
    total_casualties_defender: int = 0        # 防守方累计伤亡

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
    SCORE_OCCUPIED_CAPITAL = 35.0       # 3.0 平衡：从25提升至35（对标CK3首都权重）
    SCORE_LOST_CAPITAL = -30.0
    SCORE_SIEGE_WON = 8.0
    SCORE_SIEGE_LOST = -10.0
    SCORE_TICKING_MAX = 50.0            # 战争目标持有最大累计分
    SCORE_TICKING_PER_ROUND = 3.0       # 3.0 平衡：从2提升至3（约17回合拿满）
    SCORE_ALLY_JOINED = 5.0
    SCORE_ALLY_DEFECTED = -8.0
    SCORE_CAPTURED_LEADER = 20.0
    # v3.3 新增：防守方被动分数加成（每回合+0.1，体现本土作战优势）
    SCORE_DEFENDER_PASSIVE = 0.1
    # 3.0 平衡：防守方战争分数加成
    DEFENDER_SCORE_BONUS = 0.1

    # v3.4 厌战度常量
    EXHAUSTION_PER_ROUND = 0.3               # 每回合基础厌战增长
    EXHAUSTION_PER_1000_CASUALTY = 2.0       # 每1000伤亡增加的厌战
    EXHAUSTION_FROM_LOST_CAPITAL = 15.0      # 丢失首都的厌战冲击
    EXHAUSTION_FROM_LOST_BATTLE = 3.0        # 战败的厌战冲击
    EXHAUSTION_THRESHOLD_HIGH = 60.0         # 高厌战阈值（开始影响国内稳定）
    EXHAUSTION_THRESHOLD_CRITICAL = 85.0     # 临界厌战（可能自动求和）

    # v3.4 战斗规模加权常量
    BATTLE_SCALE_THRESHOLD_SMALL = 2000      # 小规模战斗阈值
    BATTLE_SCALE_THRESHOLD_LARGE = 8000      # 大规模会战阈值
    BATTLE_SCALE_BONUS_LARGE = 1.5           # 大规模会战分数倍率
    BATTLE_SCALE_PENALTY_SMALL = 0.5         # 小规模冲突分数衰减

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
        # v3.4: 战斗规模加权
        scaled_value = base_value * self.war_score_multiplier
        if troops_involved is not None and source in (
            WarScoreSource.BATTLE_VICTORY, WarScoreSource.BATTLE_DEFEAT
        ):
            if troops_involved >= self.BATTLE_SCALE_THRESHOLD_LARGE:
                scaled_value *= self.BATTLE_SCALE_BONUS_LARGE
            elif troops_involved < self.BATTLE_SCALE_THRESHOLD_SMALL:
                scaled_value *= self.BATTLE_SCALE_PENALTY_SMALL

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
        每回合推进：计算战争目标持有的渐进分数 + 厌战度增长

        当进攻方控制了战争目标地块时，每回合获得渐进分数。
        渐进分数有上限（防止挂机躺赢）。

        v3.3: 防守方每回合自动获得+0.1战争分数（本土作战优势）
        v3.4: 厌战度随回合和伤亡增长，高厌战影响战争意愿
        """
        # v3.4: 厌战度每回合自然增长
        self.total_rounds += 1
        self.war_exhaustion_attacker = min(100.0,
            self.war_exhaustion_attacker + self.EXHAUSTION_PER_ROUND)
        self.war_exhaustion_defender = min(100.0,
            self.war_exhaustion_defender + self.EXHAUSTION_PER_ROUND * 0.7)  # 防守方厌战增长较慢

        # 防守方被动分数加成（每回合自动获得）
        self.record_event(
            source=WarScoreSource.TICKING_WARSCORE,
            base_value=-self.SCORE_DEFENDER_PASSIVE,  # 负值 = 防守方得分
            round_num=round_num,
            description="防守方本土作战被动优势",
        )

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

        # v3.4: 进攻方极度厌战时，防守方可强制要求和平（进攻方无力继续作战）
        if self.war_exhaustion_attacker >= self.EXHAUSTION_THRESHOLD_HIGH:
            can_enforce = True  # 防守方可强制和平（进攻方厌战，愿意接受条件）

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
            "total_rounds": self.total_rounds,
            "war_exhaustion": {
                "attacker": round(self.war_exhaustion_attacker, 1),
                "defender": round(self.war_exhaustion_defender, 1),
            },
            "casualties": {
                "attacker": self.total_casualties_attacker,
                "defender": self.total_casualties_defender,
            },
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

    # ================================================================
    # v3.4 厌战度方法
    # ================================================================

    def add_casualties(self, attacker_losses: int, defender_losses: int, is_attacker_win: bool):
        """
        记录战斗伤亡并更新厌战度

        Args:
            attacker_losses: 进攻方伤亡
            defender_losses: 防守方伤亡
            is_attacker_win: 进攻方是否获胜
        """
        self.total_casualties_attacker += attacker_losses
        self.total_casualties_defender += defender_losses

        # 伤亡转化为厌战度
        atk_exhaustion = (attacker_losses / 1000) * self.EXHAUSTION_PER_1000_CASUALTY
        def_exhaustion = (defender_losses / 1000) * self.EXHAUSTION_PER_1000_CASUALTY

        # 战败方厌战度额外增加
        if not is_attacker_win:
            atk_exhaustion += self.EXHAUSTION_FROM_LOST_BATTLE
        else:
            def_exhaustion += self.EXHAUSTION_FROM_LOST_BATTLE

        self.war_exhaustion_attacker = min(100.0, self.war_exhaustion_attacker + atk_exhaustion)
        self.war_exhaustion_defender = min(100.0, self.war_exhaustion_defender + def_exhaustion)

    def add_exhaustion_shock(self, faction: str, amount: float):
        """
        添加厌战度冲击（如丢失首都等重大事件）

        Args:
            faction: "attacker" 或 "defender"
            amount: 厌战度增加值
        """
        if faction == "attacker":
            self.war_exhaustion_attacker = min(100.0, self.war_exhaustion_attacker + amount)
        elif faction == "defender":
            self.war_exhaustion_defender = min(100.0, self.war_exhaustion_defender + amount)

    def should_auto_surrender(self, faction: str) -> bool:
        """
        判断是否应自动投降

        当厌战度达到临界值 + 战争分数极端不利时触发

        Args:
            faction: "attacker" 或 "defender"

        Returns:
            是否建议自动求和
        """
        if faction == "attacker":
            exhaustion = self.war_exhaustion_attacker
            score = self.war_score
            # 进攻方厌战临界 + 分数极度不利
            if exhaustion >= self.EXHAUSTION_THRESHOLD_CRITICAL and score <= -80:
                return True
        elif faction == "defender":
            exhaustion = self.war_exhaustion_defender
            score = self.war_score
            # 防守方厌战临界 + 分数极度不利
            if exhaustion >= self.EXHAUSTION_THRESHOLD_CRITICAL and score >= 80:
                return True

        return False

    def get_exhaustion_penalty(self, faction: str) -> float:
        """
        获取厌战度对国内稳定的惩罚

        Args:
            faction: "attacker" 或 "defender"

        Returns:
            稳定度惩罚值 (0.0 ~ 30.0)
        """
        if faction == "attacker":
            exhaustion = self.war_exhaustion_attacker
        elif faction == "defender":
            exhaustion = self.war_exhaustion_defender
        else:
            return 0.0

        if exhaustion < 30:
            return 0.0
        elif exhaustion < self.EXHAUSTION_THRESHOLD_HIGH:
            return (exhaustion - 30) * 0.3  # 30-60: 逐步增加惩罚
        else:
            return 9.0 + (exhaustion - self.EXHAUSTION_THRESHOLD_HIGH) * 0.5  # 60+: 加速惩罚
