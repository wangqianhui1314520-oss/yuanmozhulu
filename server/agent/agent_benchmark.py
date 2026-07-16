"""
智能体强度基准测试 (Agent Benchmark)

基于 autonomous-agent-gaming skill 的 Benchmarking 模式：
- Elo 评分系统：基于实力差分的动态评分
- 头对头对比：Agent A vs Agent B 统计
- 锦标赛评估：循环赛 / 淘汰赛
- 实力排名：相对基准线的强度评级

用于评估和平衡 AI 势力的决策质量：
- 追踪各势力在多回合中的表现
- 发现过强或过弱的 AI 势力
- 为难度调整提供数据支撑
"""

from __future__ import annotations
import math
import logging
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger("yuanmo.agent.benchmark")


# ============================================================
# Elo 评分系统
# ============================================================

@dataclass
class EloRating:
    """Elo 评分"""
    rating: float = 1500.0       # 当前评分
    games_played: int = 0        # 参与对局数
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rating_history: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def to_dict(self) -> dict:
        return {
            "rating": round(self.rating, 1),
            "games": self.games_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": round(self.win_rate, 3),
        }


class EloSystem:
    """
    Elo 评分系统

    标准参数：
    - K=32: 标准 K 因子
    - 初始评分: 1500
    - 期望胜率公式: E = 1 / (1 + 10^((R_opp - R_self) / 400))
    - 更新公式: R_new = R_old + K * (S - E)
    """

    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self._ratings: dict[str, EloRating] = {}

    def get_or_create(self, agent_id: str) -> EloRating:
        """获取或创建评分记录"""
        if agent_id not in self._ratings:
            self._ratings[agent_id] = EloRating(rating=self.initial_rating)
        return self._ratings[agent_id]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """计算 A 对 B 的期望胜率"""
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def update(self, agent_a: str, agent_b: str, result: str):
        """
        更新 Elo 评分

        Args:
            agent_a, agent_b: 势力ID
            result: "win"(a胜), "loss"(a负), "draw"(平)
        """
        ra = self.get_or_create(agent_a)
        rb = self.get_or_create(agent_b)

        ea = self.expected_score(ra.rating, rb.rating)

        if result == "win":
            sa = 1.0
            ra.wins += 1
            rb.losses += 1
        elif result == "loss":
            sa = 0.0
            ra.losses += 1
            rb.wins += 1
        else:  # draw
            sa = 0.5
            ra.draws += 1
            rb.draws += 1

        delta = self.k_factor * (sa - ea)

        ra.rating_history.append(ra.rating)
        rb.rating_history.append(rb.rating)

        ra.rating += delta
        rb.rating -= delta
        ra.games_played += 1
        rb.games_played += 1

        # 保持历史长度
        if len(ra.rating_history) > 50:
            ra.rating_history = ra.rating_history[-50:]
        if len(rb.rating_history) > 50:
            rb.rating_history = rb.rating_history[-50:]

    def get_rankings(self) -> list[tuple[str, EloRating]]:
        """获取评分排名"""
        return sorted(
            self._ratings.items(),
            key=lambda x: x[1].rating,
            reverse=True,
        )

    def get_rating(self, agent_id: str) -> float:
        """获取评分"""
        return self.get_or_create(agent_id).rating

    def reset(self):
        """重置所有评分"""
        self._ratings.clear()


# ============================================================
# 表现追踪器
# ============================================================

@dataclass
class FactionPerformance:
    """单个势力的表现指标"""
    faction_id: str
    total_rounds: int = 0
    # 扩张指标
    tiles_gained: int = 0
    tiles_lost: int = 0
    # 军事指标
    battles_won: int = 0
    battles_lost: int = 0
    troops_peak: int = 0
    # 经济指标
    treasury_peak: int = 0
    grain_peak: int = 0
    # 外交指标
    alliances_formed: int = 0
    alliances_broken: int = 0
    # 生存指标
    survived: bool = True
    eliminated_round: int = -1

    @property
    def net_tiles(self) -> int:
        return self.tiles_gained - self.tiles_lost

    @property
    def battle_win_rate(self) -> float:
        total = self.battles_won + self.battles_lost
        return self.battles_won / max(total, 1)

    def to_dict(self) -> dict:
        return {
            "faction_id": self.faction_id,
            "total_rounds": self.total_rounds,
            "net_tiles": self.net_tiles,
            "battle_win_rate": round(self.battle_win_rate, 3),
            "troops_peak": self.troops_peak,
            "treasury_peak": self.treasury_peak,
            "survived": self.survived,
            "eliminated_round": self.eliminated_round,
        }


class PerformanceTracker:
    """
    表现追踪器

    追踪各 AI 势力在多回合中的关键指标，
    用于评估 AI 决策质量和发现不平衡问题。
    """

    def __init__(self):
        self._performances: dict[str, FactionPerformance] = {}
        self._round_history: list[dict] = []

    def record_round(self, round_num: int, world_state: dict, faction_configs: dict):
        """记录一回合的数据"""
        factions_data = world_state.get("factions", {})
        snapshot = {"round": round_num, "factions": {}}

        for fid in faction_configs.get("factions", {}):
            perf = self._performances.setdefault(fid, FactionPerformance(faction_id=fid))
            faction = factions_data.get(fid, {})

            if not faction.get("alive", True):
                if perf.survived:
                    perf.survived = False
                    perf.eliminated_round = round_num
                    logger.info(f"[Benchmark] {fid} 于第{round_num}回合灭亡")
                continue

            perf.total_rounds += 1

            # 追踪峰值
            troops = faction.get("troops", 0)
            if troops > perf.troops_peak:
                perf.troops_peak = troops

            treasury = faction.get("treasury", 0)
            if treasury > perf.treasury_peak:
                perf.treasury_peak = treasury

            grain = faction.get("grain", 0)
            if grain > perf.grain_peak:
                perf.grain_peak = grain

            # 记录快照
            snapshot["factions"][fid] = {
                "troops": troops,
                "tiles": faction.get("tile_count", 0),
                "treasury": treasury,
                "stability": faction.get("realm_stability", 50),
            }

        self._round_history.append(snapshot)

    def record_battle(self, winner_id: str, loser_id: str, tiles_changed: int = 0):
        """记录战斗结果"""
        wp = self._performances.setdefault(winner_id, FactionPerformance(faction_id=winner_id))
        lp = self._performances.setdefault(loser_id, FactionPerformance(faction_id=loser_id))
        wp.battles_won += 1
        lp.battles_lost += 1
        if tiles_changed > 0:
            wp.tiles_gained += tiles_changed
            lp.tiles_lost += tiles_changed

    def record_diplomacy(self, faction_id: str, action: str):
        """记录外交行动"""
        perf = self._performances.setdefault(faction_id, FactionPerformance(faction_id=faction_id))
        if action in ("ally", "alliance"):
            perf.alliances_formed += 1
        elif action in ("break_alliance", "war"):
            perf.alliances_broken += 1

    def get_rankings(self) -> list[dict]:
        """获取表现排名（综合评分）"""
        scored = []
        for fid, perf in self._performances.items():
            if perf.total_rounds == 0:
                continue

            # 综合评分
            survival_bonus = 100 if perf.survived else 0
            expansion_score = perf.net_tiles * 2
            military_score = perf.battle_win_rate * 50
            peak_score = min(perf.troops_peak / 1000, 30) + min(perf.treasury_peak / 5000, 20)

            total = survival_bonus + expansion_score + military_score + peak_score

            scored.append({
                **perf.to_dict(),
                "total_score": round(total, 1),
                "expansion_score": round(expansion_score, 1),
                "military_score": round(military_score, 1),
            })

        return sorted(scored, key=lambda x: x["total_score"], reverse=True)

    def detect_imbalance(self, threshold_ratio: float = 2.0) -> list[dict]:
        """
        检测势力不平衡

        Returns:
            不平衡警告列表
        """
        rankings = self.get_rankings()
        if len(rankings) < 2:
            return []

        warnings = []
        best = rankings[0]
        worst = rankings[-1]

        if best["total_score"] > worst["total_score"] * threshold_ratio:
            warnings.append({
                "type": "power_imbalance",
                "strongest": best["faction_id"],
                "strongest_score": best["total_score"],
                "weakest": worst["faction_id"],
                "weakest_score": worst["total_score"],
                "ratio": round(best["total_score"] / max(worst["total_score"], 0.1), 1),
            })

        # 检查过强势力（分数超出平均值2倍标准差）
        if len(rankings) >= 3:
            scores = [r["total_score"] for r in rankings]
            mean = sum(scores) / len(scores)
            std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores))
            for r in rankings:
                if r["total_score"] > mean + 2 * std:
                    warnings.append({
                        "type": "outlier_strong",
                        "faction_id": r["faction_id"],
                        "score": r["total_score"],
                        "mean": round(mean, 1),
                        "std": round(std, 1),
                    })

        return warnings

    def get_summary(self) -> dict:
        """获取完整摘要"""
        rankings = self.get_rankings()
        imbalances = self.detect_imbalance()

        return {
            "total_rounds_tracked": len(self._round_history),
            "factions_tracked": len(self._performances),
            "survivors": sum(1 for p in self._performances.values() if p.survived),
            "eliminated": sum(1 for p in self._performances.values() if not p.survived),
            "rankings": rankings,
            "imbalance_warnings": imbalances,
        }

    def reset(self):
        """重置追踪器"""
        self._performances.clear()
        self._round_history.clear()


# ============================================================
# 锦标赛系统
# ============================================================

class TournamentSystem:
    """
    锦标赛系统

    用于评估和对比不同 AI 配置或势力的表现。
    支持循环赛（round-robin）和淘汰赛（elimination）。
    """

    def __init__(self):
        self.elo = EloSystem()
        self.tracker = PerformanceTracker()

    def record_agent_outcome(
        self, agent_a: str, agent_b: str, result: str, tiles_diff: int = 0
    ):
        """
        记录一次对抗结果

        Args:
            agent_a, agent_b: 势力ID
            result: "win" / "loss" / "draw"（从 agent_a 视角）
            tiles_diff: 地盘变化（正=agent_a获得）
        """
        self.elo.update(agent_a, agent_b, result)
        if result == "win":
            self.tracker.record_battle(agent_a, agent_b, tiles_diff)
        elif result == "loss":
            self.tracker.record_battle(agent_b, agent_a, -tiles_diff)

    def get_elo_rankings(self) -> list[dict]:
        """获取 Elo 排名"""
        rankings = self.elo.get_rankings()
        return [
            {
                "rank": i + 1,
                "faction_id": fid,
                **rating.to_dict(),
            }
            for i, (fid, rating) in enumerate(rankings)
        ]

    def reset(self):
        self.elo.reset()
        self.tracker.reset()


# 全局单例
_global_tournament: Optional[TournamentSystem] = None
_global_performance_tracker: Optional[PerformanceTracker] = None


def get_tournament() -> TournamentSystem:
    """获取全局锦标赛系统"""
    global _global_tournament
    if _global_tournament is None:
        _global_tournament = TournamentSystem()
    return _global_tournament


def get_performance_tracker() -> PerformanceTracker:
    """获取全局表现追踪器"""
    global _global_performance_tracker
    if _global_performance_tracker is None:
        _global_performance_tracker = PerformanceTracker()
    return _global_performance_tracker


def reset_benchmark():
    """重置所有基准测试"""
    global _global_tournament, _global_performance_tracker
    _global_tournament = TournamentSystem()
    _global_performance_tracker = PerformanceTracker()
