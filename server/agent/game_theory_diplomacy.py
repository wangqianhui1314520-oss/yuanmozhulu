"""
博弈论外交分析器 (Game Theory Diplomacy Analyzer)

基于 autonomous-agent-gaming skill 的 Game Theory 模式：
- Nash 均衡计算：2人零和博弈 / 混合策略均衡
- Shapley 值：联盟中每个势力的公平贡献分配
- 联盟稳定性分析（Core）：检查联盟是否稳定
- 支付矩阵构建：基于军事实力/经济/地缘关系

用于增强 A6 外交署的决策质量：
- 为外交 prompt 注入博弈论分析结果
- 预测其他势力的外交倾向
- 评估联盟/对抗策略的收益
"""

from __future__ import annotations
import math
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("yuanmo.agent.game_theory")


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PayoffMatrix:
    """支付矩阵（2人博弈）"""
    player1_id: str
    player2_id: str
    # p1_actions × p2_actions 的收益矩阵
    # payoff[i][j] = (p1_reward, p2_reward)
    p1_actions: list[str] = field(default_factory=list)
    p2_actions: list[str] = field(default_factory=list)
    payoffs: list[list[tuple[float, float]]] = field(default_factory=list)


@dataclass
class NashEquilibrium:
    """Nash 均衡结果"""
    p1_strategy: list[float]  # p1 混合策略概率分布
    p2_strategy: list[float]  # p2 混合策略概率分布
    p1_expected: float        # p1 期望收益
    p2_expected: float        # p2 期望收益
    is_pure: bool = False     # 是否为纯策略均衡
    description: str = ""


@dataclass
class CoalitionAnalysis:
    """联盟分析结果"""
    coalition: list[str]            # 联盟成员
    total_value: float = 0.0        # 联盟总价值
    shapley_values: dict[str, float] = field(default_factory=dict)  # 各成员 Shapley 值
    is_stable: bool = True          # 是否在 Core 中（稳定）
    alternative_coalitions: list[dict] = field(default_factory=list)  # 替代联盟方案


# ============================================================
# 博弈论分析器
# ============================================================

class GameTheoryAnalyzer:
    """
    博弈论外交分析器

    用法:
        analyzer = GameTheoryAnalyzer()
        # 分析两国博弈
        nash = analyzer.find_nash_for_pair(faction_a, faction_b, world_state)
        # 联盟分析
        coalition = analyzer.analyze_coalition(faction_ids, world_state)
    """

    def __init__(self):
        pass

    # ---- 势力实力评分 ----

    @staticmethod
    def _calculate_power(faction_id: str, world_state: dict) -> float:
        """
        计算势力综合实力评分

        权重：
        - 兵力 35%
        - 经济(国库+粮草) 30%
        - 地盘 20%
        - 稳定度 10%
        - 声望 5%
        """
        factions = world_state.get("factions", {})
        faction = factions.get(faction_id, {})
        if not faction or not faction.get("alive", True):
            return 0.0

        troops = faction.get("troops", 0)
        treasury = faction.get("treasury", 0)
        grain = faction.get("grain", 0)
        tile_count = faction.get("tile_count", 0)
        stability = faction.get("realm_stability", faction.get("stability", 50))
        reputation = faction.get("reputation", 50)

        # 归一化
        max_troops = 100000
        max_treasury = 100000
        max_grain = 200000
        max_tiles = 500

        military = min(troops / max_troops, 1.0) * 35
        economy = min((treasury / max_treasury + grain / max_grain) / 2, 1.0) * 30
        territory = min(tile_count / max_tiles, 1.0) * 20
        stab = (stability / 100) * 10
        rep = (reputation / 100) * 5

        # 盟友加成：每个盟友 +5%
        allies = 0
        relations = world_state.get("diplomatic_relations", {})
        for other_id, rel in relations.items():
            if other_id == faction_id:
                continue
            rel_type = rel.get("type", "") if isinstance(rel, dict) else ""
            if rel_type in ("ally", "alliance"):
                allies += 1

        base = military + economy + territory + stab + rep
        return base * (1 + allies * 0.05)

    # ---- Nash 均衡 ----

    def build_payoff_matrix(
        self, faction_a: str, faction_b: str, world_state: dict
    ) -> PayoffMatrix:
        """
        构建两个势力间的支付矩阵

        动作空间：
        - COOPERATE: 合作（结盟/示好）
        - COMPETE: 竞争（对抗/宣战）
        - NEUTRAL: 中立（观望）

        收益计算基于：
        - 合作：双方经济+，军事风险-
        - 竞争：强者得利，弱者受损
        - 中立：无变化
        """
        power_a = self._calculate_power(faction_a, world_state)
        power_b = self._calculate_power(faction_b, world_state)
        power_ratio = power_a / max(power_b, 0.01)

        actions = ["COOPERATE", "NEUTRAL", "COMPETE"]

        # 收益矩阵（3×3）
        payoffs = []
        for i, act_a in enumerate(actions):
            row = []
            for j, act_b in enumerate(actions):
                p1, p2 = self._payoff(act_a, act_b, power_ratio, power_a, power_b)
                row.append((p1, p2))
            payoffs.append(row)

        return PayoffMatrix(
            player1_id=faction_a,
            player2_id=faction_b,
            p1_actions=actions,
            p2_actions=actions,
            payoffs=payoffs,
        )

    def _payoff(
        self, act_a: str, act_b: str, power_ratio: float,
        power_a: float, power_b: float
    ) -> tuple[float, float]:
        """计算单个策略组合的收益"""
        base_a, base_b = power_a, power_b

        if act_a == "COOPERATE" and act_b == "COOPERATE":
            # 双赢：双方都获益
            return (base_a * 1.3, base_b * 1.3)
        elif act_a == "COOPERATE" and act_b == "NEUTRAL":
            return (base_a * 1.1, base_b * 1.05)
        elif act_a == "COOPERATE" and act_b == "COMPETE":
            # 被背叛：合作方受损
            return (base_a * 0.6, base_b * 1.4)
        elif act_a == "NEUTRAL" and act_b == "COOPERATE":
            return (base_a * 1.05, base_b * 1.1)
        elif act_a == "NEUTRAL" and act_b == "NEUTRAL":
            return (base_a * 1.0, base_b * 1.0)  # 均不变
        elif act_a == "NEUTRAL" and act_b == "COMPETE":
            return (base_a * 0.8, base_b * 1.15)
        elif act_a == "COMPETE" and act_b == "COOPERATE":
            return (base_a * 1.4, base_b * 0.6)
        elif act_a == "COMPETE" and act_b == "NEUTRAL":
            return (base_a * 1.15, base_b * 0.8)
        elif act_a == "COMPETE" and act_b == "COMPETE":
            # 双方对抗：强者略优，但双输
            if power_ratio > 1.2:
                return (base_a * 0.95, base_b * 0.7)
            elif power_ratio < 0.8:
                return (base_a * 0.7, base_b * 0.95)
            else:
                return (base_a * 0.8, base_b * 0.8)

        return (base_a, base_b)

    def find_nash_equilibria(self, matrix: PayoffMatrix) -> list[NashEquilibrium]:
        """
        查找 Nash 均衡（2人博弈）

        方法：
        1. 纯策略 Nash：检查每个单元格是否互为最佳反应
        2. 混合策略 Nash（2×2 简化）：用无差异条件求解
        """
        results = []

        # 1. 纯策略 Nash
        n_rows = len(matrix.p1_actions)
        n_cols = len(matrix.p2_actions)

        for i in range(n_rows):
            for j in range(n_cols):
                p1_payoff, p2_payoff = matrix.payoffs[i][j]

                # 检查 p1 是否有更好的偏离
                p1_best = True
                for i2 in range(n_rows):
                    if matrix.payoffs[i2][j][0] > p1_payoff + 0.01:
                        p1_best = False
                        break

                # 检查 p2 是否有更好的偏离
                p2_best = True
                for j2 in range(n_cols):
                    if matrix.payoffs[i][j2][1] > p2_payoff + 0.01:
                        p2_best = False
                        break

                if p1_best and p2_best:
                    p1_strat = [0.0] * n_rows
                    p1_strat[i] = 1.0
                    p2_strat = [0.0] * n_cols
                    p2_strat[j] = 1.0
                    results.append(NashEquilibrium(
                        p1_strategy=p1_strat,
                        p2_strategy=p2_strat,
                        p1_expected=p1_payoff,
                        p2_expected=p2_payoff,
                        is_pure=True,
                        description=(
                            f"纯策略均衡: {matrix.player1_id} 选择'{matrix.p1_actions[i]}', "
                            f"{matrix.player2_id} 选择'{matrix.p2_actions[j]}'"
                        ),
                    ))

        # 2. 如果没有纯策略均衡，或策略空间为2×2，尝试混合策略
        if not results and n_rows == 2 and n_cols == 2:
            mixed = self._solve_mixed_2x2(matrix)
            if mixed:
                results.append(mixed)

        return results

    def _solve_mixed_2x2(self, matrix: PayoffMatrix) -> Optional[NashEquilibrium]:
        """求解 2×2 混合策略 Nash 均衡（无差异条件）"""
        # p2 的无差异条件：
        # p * payoff_a1_b1 + (1-p) * payoff_a2_b1 = p * payoff_a1_b2 + (1-p) * payoff_a2_b2
        a1b1, a1b2 = matrix.payoffs[0][0][1], matrix.payoffs[0][1][1]
        a2b1, a2b2 = matrix.payoffs[1][0][1], matrix.payoffs[1][1][1]

        denom_p = a1b1 - a1b2 - a2b1 + a2b2
        if abs(denom_p) < 1e-6:
            return None
        p = (a2b2 - a2b1) / denom_p
        p = max(0.0, min(1.0, p))

        # p1 的无差异条件
        a1b1_p1, a2b1_p1 = matrix.payoffs[0][0][0], matrix.payoffs[1][0][0]
        a1b2_p1, a2b2_p1 = matrix.payoffs[0][1][0], matrix.payoffs[1][1][0]

        denom_q = a1b1_p1 - a2b1_p1 - a1b2_p1 + a2b2_p1
        if abs(denom_q) < 1e-6:
            return None
        q = (a2b2_p1 - a2b1_p1) / denom_q
        q = max(0.0, min(1.0, q))

        # 期望收益
        exp_p1 = (
            p * q * matrix.payoffs[0][0][0] +
            p * (1 - q) * matrix.payoffs[0][1][0] +
            (1 - p) * q * matrix.payoffs[1][0][0] +
            (1 - p) * (1 - q) * matrix.payoffs[1][1][0]
        )
        exp_p2 = (
            p * q * matrix.payoffs[0][0][1] +
            p * (1 - q) * matrix.payoffs[0][1][1] +
            (1 - p) * q * matrix.payoffs[1][0][1] +
            (1 - p) * (1 - q) * matrix.payoffs[1][1][1]
        )

        return NashEquilibrium(
            p1_strategy=[p, 1 - p],
            p2_strategy=[q, 1 - q],
            p1_expected=exp_p1,
            p2_expected=exp_p2,
            is_pure=False,
            description=(
                f"混合策略均衡: {matrix.player1_id} 以 {p:.1%} 概率选择'{matrix.p1_actions[0]}'"
            ),
        )

    # ---- Shapley 值与联盟分析 ----

    def calculate_shapley_values(
        self, coalition: list[str], world_state: dict
    ) -> dict[str, float]:
        """
        计算联盟中各势力的 Shapley 值（公平分配）

        Shapley 值 = Σ (联盟边际贡献 × 排列概率)
        每个势力获得其所有可能加入顺序中的边际贡献期望值。

        Args:
            coalition: 联盟成员势力ID列表
            world_state: 世界状态

        Returns:
            {faction_id: shapley_value, ...}
        """
        n = len(coalition)
        if n <= 1:
            return {coalition[0]: self._calculate_power(coalition[0], world_state)} if n == 1 else {}

        import itertools

        shapley = {fid: 0.0 for fid in coalition}

        # 对所有排列计算边际贡献
        for perm in itertools.permutations(coalition):
            current_coalition = []
            current_value = 0.0
            for fid in perm:
                # 加入该势力前的联盟价值
                value_before = self._coalition_value(current_coalition, world_state)
                current_coalition.append(fid)
                # 加入后的联盟价值
                value_after = self._coalition_value(current_coalition, world_state)
                # 边际贡献
                marginal = value_after - value_before
                shapley[fid] += marginal

        # 除以排列总数
        factorial_n = math.factorial(n)
        for fid in shapley:
            shapley[fid] /= factorial_n

        return shapley

    def _coalition_value(self, members: list[str], world_state: dict) -> float:
        """
        计算联盟总价值

        联盟价值 = Σ成员实力 × (1 + 协同系数)
        协同系数随成员数递增（联盟越大，协同效应越强）
        """
        if not members:
            return 0.0

        total_power = sum(
            self._calculate_power(fid, world_state)
            for fid in members
        )
        # 协同效应：每多一个成员 +10%，上限 50%
        synergy = min((len(members) - 1) * 0.1, 0.5)
        return total_power * (1 + synergy)

    def analyze_coalition(
        self, coalition: list[str], world_state: dict
    ) -> CoalitionAnalysis:
        """
        完整联盟分析

        Returns:
            CoalitionAnalysis 含 Shapley值、稳定性、替代方案
        """
        total_value = self._coalition_value(coalition, world_state)
        shapley = self.calculate_shapley_values(coalition, world_state)

        # 稳定性检查：检查是否有成员有动机离开联盟
        is_stable = True
        alternatives = []
        all_factions = [
            fid for fid in world_state.get("factions", {})
            if world_state["factions"][fid].get("alive", True)
        ]

        for fid in coalition:
            # 如果单独行动收益更高 → 不稳定
            solo_value = self._calculate_power(fid, world_state)
            if solo_value > shapley.get(fid, 0) * 1.2:
                is_stable = False
                alternatives.append({
                    "faction_id": fid,
                    "reason": f"单独行动收益({solo_value:.1f})高于联盟分配({shapley.get(fid, 0):.1f})",
                })

        # 检查是否有更好的替代联盟
        for fid in coalition:
            for other in all_factions:
                if other not in coalition and other != fid:
                    alt_coalition = [fid, other]
                    alt_value = self._coalition_value(alt_coalition, world_state)
                    if alt_value > shapley.get(fid, 0) * 1.5:
                        alternatives.append({
                            "faction_id": fid,
                            "alternative_with": other,
                            "alternative_value": alt_value,
                            "reason": f"与{other}结盟可获更高收益({alt_value:.1f})",
                        })

        return CoalitionAnalysis(
            coalition=coalition,
            total_value=total_value,
            shapley_values=shapley,
            is_stable=is_stable,
            alternative_coalitions=alternatives[:5],  # 限制数量
        )

    # ---- 批量分析 ----

    def analyze_all_pairs(
        self, faction_id: str, world_state: dict
    ) -> dict[str, dict]:
        """
        分析一个势力与所有其他势力的博弈关系

        Returns:
            {other_faction_id: {
                "nash_equilibria": [...],
                "recommended_strategy": str,
                "power_ratio": float,
            }, ...}
        """
        results = {}
        factions_data = world_state.get("factions", {})
        my_power = self._calculate_power(faction_id, world_state)

        for other_id, other_data in factions_data.items():
            if other_id == faction_id or not other_data.get("alive", True):
                continue

            other_power = self._calculate_power(other_id, world_state)
            if other_power == 0:
                continue

            matrix = self.build_payoff_matrix(faction_id, other_id, world_state)
            equilibria = self.find_nash_equilibria(matrix)

            # 推荐策略：选择最有利于自己的均衡
            best_strategy = "NEUTRAL"
            best_payoff = my_power  # 基准
            for eq in equilibria:
                if eq.p1_expected > best_payoff:
                    best_payoff = eq.p1_expected
                    # 找概率最高的动作
                    max_prob_idx = max(range(len(eq.p1_strategy)), key=lambda i: eq.p1_strategy[i])
                    best_strategy = matrix.p1_actions[max_prob_idx]

            results[other_id] = {
                "nash_equilibria": [
                    {
                        "is_pure": eq.is_pure,
                        "p1_strategy": eq.p1_strategy,
                        "p1_expected": round(eq.p1_expected, 2),
                        "description": eq.description,
                    }
                    for eq in equilibria
                ],
                "recommended_strategy": best_strategy,
                "power_ratio": round(my_power / max(other_power, 0.01), 2),
            }

        return results

    def generate_diplomacy_hint(
        self, faction_id: str, world_state: dict
    ) -> str:
        """
        生成博弈论外交提示（可注入 A6 prompt）

        Returns:
            中文外交策略建议（100-200字）
        """
        pair_analysis = self.analyze_all_pairs(faction_id, world_state)

        if not pair_analysis:
            return "周边无其他势力，暂无外交博弈需求。"

        # 按推荐策略分组
        cooperate_with = []
        compete_with = []
        neutral_with = []

        factions_data = world_state.get("factions", {})

        for other_id, analysis in pair_analysis.items():
            name = factions_data.get(other_id, {}).get("name", other_id)
            strategy = analysis["recommended_strategy"]
            ratio = analysis["power_ratio"]

            if strategy == "COOPERATE":
                cooperate_with.append(f"{name}(实力比{ratio:.1f}:1)")
            elif strategy == "COMPETE":
                compete_with.append(f"{name}(实力比{ratio:.1f}:1)")
            else:
                neutral_with.append(f"{name}(实力比{ratio:.1f}:1)")

        parts = []
        if cooperate_with:
            parts.append(f"【建议结盟】{'、'.join(cooperate_with[:3])}")
        if compete_with:
            parts.append(f"【建议对抗】{'、'.join(compete_with[:3])}")
        if neutral_with:
            parts.append(f"【建议观望】{'、'.join(neutral_with[:3])}")

        # 全局建议
        total_pair = len(pair_analysis)
        cooperate_ratio = len(cooperate_with) / total_pair

        global_advice = ""
        if cooperate_ratio > 0.6:
            global_advice = "当前局势宜广结盟友，合纵以抗强敌。"
        elif cooperate_ratio < 0.3:
            global_advice = "当前局势宜示强而非示弱，以实力为后盾展开外交。"
        else:
            global_advice = "当前局势微妙，当灵活应变，择机而动。"

        return "基于博弈论Nash均衡分析：\n" + "\n".join(parts) + f"\n\n全局建议：{global_advice}"


# 全局单例
_global_gt_analyzer: Optional[GameTheoryAnalyzer] = None


def get_game_theory_analyzer() -> GameTheoryAnalyzer:
    """获取全局博弈论分析器单例"""
    global _global_gt_analyzer
    if _global_gt_analyzer is None:
        _global_gt_analyzer = GameTheoryAnalyzer()
    return _global_gt_analyzer
