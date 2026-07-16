#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
终局可达性深度分析 —— 敏感性测试
分析不同参数组合下结局达成率的变化
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from endgame_monte_carlo import (
    MonteCarloSimulation, FactionState, FACTION_DATA,
    MAX_ROUNDS, TOTAL_TILES, MILITARY_UPKEEP
)
from collections import defaultdict
import random


class EnhancedSimulation(MonteCarloSimulation):
    """增强版模拟 — 加入玩家策略和更真实的行为模型"""

    def __init__(self, iterations=2000, player_faction="朱元璋",
                 player_aggression=0.8, combat_volatility=1.0):
        super().__init__(iterations=iterations)
        self.player_faction = player_faction
        self.player_aggression = player_aggression
        self.combat_volatility = combat_volatility

    def _settle_economy(self, faction: FactionState, season: int):
        """经济结算（继承基类）"""
        pop = faction.population

        avg_tax_coeff = 0.85
        tax_income = pop * 0.15 * avg_tax_coeff * {1: 0.9, 2: 1.0, 3: 1.3, 4: 0.7}.get(season, 1.0)
        tax_income *= faction.tax_bonus

        trade_income = faction.tiles * 100 * 0.5 * faction.trade_bonus

        if faction.non_grassland_penalty > 0:
            gp = 0.4
            tax_income *= (gp + 0.6 * (1 - faction.non_grassland_penalty))
            trade_income *= (gp + 0.6 * (1 - faction.non_grassland_penalty))

        total_income = tax_income + trade_income

        season_upkeep = {4: 1.3}.get(season, 1.0)
        resource_mult = 1.0 + faction.resource_penalty
        military_cost = faction.troops * MILITARY_UPKEEP * season_upkeep * resource_mult

        grain_consumption = pop / 100 + faction.troops * 0.5
        if faction.grain_upkeep_red > 0:
            grain_consumption *= (1 - faction.grain_upkeep_red)

        treasury_drain = 0
        if faction.debuff_treasury_drain > 0:
            min_t = FACTION_DATA[faction.name]["treasury"] * 0.30
            treasury_drain = min(faction.treasury * 0.02, max(0, faction.treasury - min_t))

        grain_produced = (pop / 10 + faction.tiles * 80) * {1: 0.9, 2: 1.0, 3: 1.3, 4: 0.5}.get(season, 1.0)
        grain_produced *= faction.grain_bonus

        pop_growth = 0.02 + {1: 0.01, 2: 0, 3: 0, 4: -0.005}.get(season, 0)
        grain_per_capita = faction.grain / max(pop, 1)
        if grain_per_capita < 150:
            pop_growth -= 0.03
            faction.famine_count += 1
        pop_growth = max(-0.05, min(0.08, pop_growth))
        faction.pop_per_tile = faction.pop_per_tile * (1 + pop_growth)

        event_mult = random.uniform(0.85, 1.15)
        total_income *= event_mult

        faction.treasury += total_income - military_cost - treasury_drain
        faction.treasury = max(0, faction.treasury)
        faction.grain += grain_produced - grain_consumption
        faction.grain = max(0, faction.grain)

        if grain_per_capita < 75:
            faction.stability -= random.uniform(2, 5)
        elif grain_per_capita > 300:
            faction.stability += random.uniform(0, 1)
        if faction.stability_drain > 0:
            faction.stability -= faction.stability_drain
        faction.stability = max(0, min(100, faction.stability))
        if faction.debuff_morale_drain_pct > 0:
            faction.reputation -= max(1, int(faction.debuff_morale_drain_pct * faction.tiles * 0.1))
            faction.reputation = max(0, min(100, faction.reputation))

    def _simulate_ai_action(self, faction: FactionState, all_factions: dict,
                            rnd: int, season: int):
        """改进的AI行为 — 区分玩家和AI势力"""
        alive = [f for f in all_factions.values()
                 if f.alive and f.name != faction.name]
        if not alive:
            return

        is_player = faction.name == self.player_faction
        aggression = self.player_aggression if is_player else (
            faction.ai_expansion + faction.ai_military * 0.3)

        # 玩家有更高的初始扩张意愿，并且有目标选择策略
        if is_player:
            # 玩家倾向于攻击最弱的邻居
            target = min(alive, key=lambda f: f.troops * 0.6 + f.tiles * 0.4)
        else:
            target = random.choice(alive)

        # 进攻决策
        treasury_ok = faction.treasury > 500
        troops_ok = faction.troops > faction.population * 0.03
        can_expand = treasury_ok and troops_ok

        if not can_expand:
            aggression *= 0.2

        if random.random() < aggression:
            self._resolve_combat(faction, target, season, is_player)

    def _resolve_combat(self, attacker: FactionState, defender: FactionState,
                        season: int, is_player: bool):
        """战斗结算"""
        atk_power = attacker.troops
        def_power = defender.troops

        # 兵种加成
        atk_power *= max(attacker.cav_bonus, attacker.inf_bonus)
        def_power *= max(defender.cav_bonus, defender.inf_bonus)
        def_power *= defender.def_bonus

        # 季节修正
        season_mults = {4: (0.75, 1.15), 3: (1.10, 1.0), 2: (0.90, 1.0)}
        atk_mult, def_mult = season_mults.get(season, (1.0, 1.0))
        atk_power *= atk_mult
        def_power *= def_mult

        # 地形防御
        def_power *= min(random.uniform(1.0, 1.6), 2.5)

        # 随机波动（由 volatility 控制）
        v = self.combat_volatility
        atk_power *= 1.0 + (random.uniform(0.8, 1.2) - 1.0) * v
        def_power *= 1.0 + (random.uniform(0.7, 1.3) - 1.0) * v

        # 玩家额外战术优势
        if is_player:
            atk_power *= 1.1

        # 胜负判定
        if atk_power > def_power * 1.2:
            atk_loss = int(attacker.troops * random.uniform(0.05, 0.2))
            def_loss = int(defender.troops * random.uniform(0.4, 0.7))
            tiles_gained = max(1, int(defender.tiles * random.uniform(0.15, 0.40)))

            attacker.troops -= atk_loss
            defender.troops -= def_loss
            attacker.tiles += tiles_gained
            defender.tiles = max(1, defender.tiles - tiles_gained)

            if attacker.loot_bonus > 0:
                attacker.treasury += defender.treasury * attacker.loot_bonus * 0.2

        elif def_power > atk_power * 1.2:
            atk_loss = int(attacker.troops * random.uniform(0.3, 0.6))
            def_loss = int(defender.troops * random.uniform(0.05, 0.15))
            attacker.troops -= atk_loss
            defender.troops -= def_loss
        else:
            atk_loss = int(attacker.troops * random.uniform(0.15, 0.3))
            def_loss = int(defender.troops * random.uniform(0.1, 0.25))
            attacker.troops -= atk_loss
            defender.troops -= def_loss

        attacker.troops = max(0, attacker.troops)
        defender.troops = max(0, defender.troops)
        attacker.tiles = min(TOTAL_TILES, max(1, attacker.tiles))
        defender.tiles = min(TOTAL_TILES, max(1, defender.tiles))


def run_sensitivity_analysis():
    """敏感度分析：测试不同参数组合"""
    scenarios = [
        # (名称, 玩家势力, 进攻性, 战斗波动, 迭代数)
        ("基线(朱元璋被动)", "朱元璋", 0.3, 1.0, 1000),
        ("朱元璋中等进攻", "朱元璋", 0.5, 1.0, 1000),
        ("朱元璋激进进攻", "朱元璋", 0.7, 1.0, 1000),
        ("朱元璋低波动", "朱元璋", 0.6, 0.6, 1000),
        ("朱元璋+低波动+激进", "朱元璋", 0.8, 0.5, 1000),
        ("陈友谅激进", "陈友谅", 0.7, 1.0, 1000),
        ("张士诚经济型", "张士诚", 0.5, 1.0, 1000),
        ("元廷防守型", "元廷", 0.3, 0.8, 1000),
        ("王保保骑兵型", "王保保", 0.7, 1.0, 1000),
        ("漠北劫掠型", "漠北诸部", 0.8, 1.2, 1000),
    ]

    print("\n" + "=" * 90)
    print("  《元末逐鹿》终局可达性 — 敏感度分析")
    print("=" * 90)

    all_results = []

    for name, player, aggression, volatility, iters in scenarios:
        sim = EnhancedSimulation(
            iterations=iters,
            player_faction=player,
            player_aggression=aggression,
            combat_volatility=volatility
        )
        report = sim.run()

        fs = report["faction_ending_stats"]
        player_stats = fs[player]

        unification = player_stats["天下归心"] + player_stats["盛世新朝"]
        any_good = player_stats["天下归心"] + player_stats["盛世新朝"] + player_stats["偏安存续"]

        all_results.append({
            "scenario": name,
            "player": player,
            "aggression": aggression,
            "volatility": volatility,
            "death_pct": player_stats["霸业陨落"],
            "partial_pct": player_stats["偏安存续"],
            "unify_pct": unification,
            "perfect_pct": player_stats["盛世新朝"],
            "any_ending_pct": player_stats["霸业陨落"] + any_good
        })

        print(f"  {name:<22} | {player:<8} | 陨落:{player_stats['霸业陨落']:5.1f}% | "
              f"偏安:{player_stats['偏安存续']:5.1f}% | "
              f"统一:{unification:5.1f}% | 盛世:{player_stats['盛世新朝']:5.1f}%")

    # 最佳策略识别
    print("\n" + "-" * 90)
    print("  【最佳策略分析】")
    best = max(all_results, key=lambda r: r["unify_pct"] + r["partial_pct"] * 0.01)
    best_unify = max(all_results, key=lambda r: r["unify_pct"])

    print(f"  最高存活率策略: {best['scenario']} (存活率 {100 - best['death_pct']:.1f}%)")
    print(f"  最高统一率策略: {best_unify['scenario']} (统一率 {best_unify['unify_pct']:.1f}%)")

    # 敏感性结论
    print("\n  【敏感性结论】")
    # 分析进攻性对统一率的影响
    for player_name in set(r["player"] for r in all_results):
        player_results = [r for r in all_results if r["player"] == player_name]
        if len(player_results) >= 2:
            unify_range = max(r["unify_pct"] for r in player_results) - min(r["unify_pct"] for r in player_results)
            if unify_range > 5:
                print(f"  {player_name}: 统一率对策略敏感 (范围 {unify_range:.1f}%)")

    return all_results


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    random.seed()
    results = run_sensitivity_analysis()

    # 保存
    with open("tools/sensitivity_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n敏感度报告已保存至 tools/sensitivity_report.json")
