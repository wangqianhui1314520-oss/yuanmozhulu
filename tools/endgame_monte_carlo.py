#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
终局可达性蒙特卡洛模拟 —— 《元末逐鹿》Balance Check
=====================================================
基于 game-balance-check skill 的工作流：
  Step 1: 系统盘点 + 依赖映射
  Step 2: 经济 Faucet/Sink 验证
  Step 3: 进度曲线分析
  Step 4: 难度缩放评估
  Step 5: 奖励节奏分析
  Step 6: 统计验证
  Step 7: 蒙特卡洛模拟
  Step 8: 报告编制

输出：平衡报告 + 关键风险识别
"""

import random
import math
import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from enum import Enum

# ============================================================
# 常量配置（从 game_const.yaml 提取）
# ============================================================
MAX_ROUNDS = 240
START_YEAR = 1351
START_MONTH = 4
TOTAL_TILES = 1328
PROTECTED_ROUNDS = 3  # 前3回合不检查结局

# 经济参数
BASE_TAX_RATE = 0.15
BASE_POP_GROWTH = 0.02
FAMINE_THRESHOLD = 150  # 人均粮草
MIGRATION_COST = 2
RELIEF_COST = 5
PORT_INCOME_BASE = 150
TRADE_ROUTE_INCOME = 100
MILITARY_UPKEEP = 0.8  # 每兵每回合银两（v4.1: 原1.0）

# 战斗参数
MAX_DEFENSE_MULT = 2.5
FORT_BONUS_PER_LEVEL = 0.2
WINTER_ATK_MULT = 0.85  # v4.1: 原0.75
WINTER_DEF_MULT = 1.10  # v4.1: 原1.15
AUTUMN_ATK_MULT = 1.10
SUMMER_ATK_MULT = 0.90

# 人口
MAX_RECRUIT_PCT = 0.15
GARRISON_BASE = 5000
GARRISON_PER_FORT = 2000
POP_FARMER_RATIO = 0.60
POP_SOLDIER_RATIO = 0.15

# 元廷保护
YUAN_MIN_TREASURY_PCT = 0.30

# 结局条件
ENDING_PARTIAL_TERRITORY = 0.20   # <20% → 偏安
ENDING_PARTIAL_ROUND = 150        # >=150回合 + <20% → 偏安
ENDING_PARTIAL_TREASURY = 8000    # 国库>=8000 → 偏安
ENDING_UNIFY_TERRITORY = 0.75     # >=75% → 天下归心
ENDING_UNIFY_REPUTATION = 65
ENDING_UNIFY_STABILITY = 50
ENDING_UNIFY_SURVIVORS = 2
ENDING_PERFECT_TERRITORY = 0.85   # >=85% → 盛世新朝
ENDING_PERFECT_REPUTATION = 85
ENDING_PERFECT_STABILITY = 75
ENDING_PERFECT_DEVELOPMENT = 75
ENDING_PERFECT_TREASURY = 40000
ENDING_PERFECT_GRAIN = 20000
ENDING_PERFECT_POLICIES = 8

# 四季修正
SEASON_TAX = {1: 0.9, 2: 1.0, 3: 1.3, 4: 0.7}  # 按季度
SEASON_GRAIN = {1: 0.9, 2: 1.0, 3: 1.3, 4: 0.5}
SEASON_POP_GROWTH_BONUS = {1: 0.01, 2: 0.0, 3: 0.0, 4: -0.005}
SEASON_UPKEEP = {4: 1.25}  # 冬季军费×1.25（v4.1: 原1.3）

# 地块税收系数
TILE_TAX_COEFF = {
    "city": 1.5, "port": 1.3, "farmland": 1.0,
    "grassland": 0.8, "hill": 0.6, "mountain": 0.3,
    "desert": 0.2, "water": 0.0, "pass": 0.5,
    "forest": 0.7, "swamp": 0.4
}

# 每地块平均人口
POP_PER_TILE = 800  # 估计值

# ============================================================
# Faction 数据
# ============================================================
FACTION_DATA = {
    "元廷": {
        "id": "faction_yuan", "difficulty": "地狱",
        "treasury": 20000, "grain": 8000, "troops": 6000,
        "arms": 300, "horses": 200, "tiles": 9, "reputation": 60,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.0,
        "cav_bonus": 1.35, "inf_bonus": 1.0, "def_bonus": 1.0,
        "debuff_treasury_drain": 0.02,  # 国库月流失2%
        "debuff_morale_drain": 5,  # 汉人地块每月民心-5
        "stability_drain": 2,  # 朝堂-2
        "ai_expansion": 0.2, "ai_military": 0.5,
        "pop_per_tile": 1000, "soldier_ratio": 0.20
    },
    "朱元璋": {
        "id": "faction_zhuyuanzhang", "difficulty": "普通",
        "treasury": 8000, "grain": 4000, "troops": 3000,
        "arms": 80, "horses": 30, "tiles": 11, "reputation": 40,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.0,
        "inf_bonus": 1.0, "cav_bonus": 1.0, "def_bonus": 1.0,
        "refugee_bonus": 0.30, "grain_upkeep_red": 0.20, "fire_bonus": 0.20,
        "ai_expansion": 0.6, "ai_military": 0.6,
        "pop_per_tile": 900, "soldier_ratio": 0.18
    },
    "陈友谅": {
        "id": "faction_chenyouliang", "difficulty": "困难",
        "treasury": 12000, "grain": 6000, "troops": 5000,
        "arms": 150, "horses": 50, "tiles": 11, "reputation": 35,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.20,
        "naval_bonus": 1.30, "inf_bonus": 1.0,
        "debuff_morale_drain": 0.30, "debuff_diplomacy": -15,
        "ai_expansion": 0.7, "ai_military": 0.8,
        "pop_per_tile": 850, "soldier_ratio": 0.22
    },
    "张士诚": {
        "id": "faction_zhangshicheng", "difficulty": "简单",
        "treasury": 15000, "grain": 7000, "troops": 3500,
        "arms": 100, "horses": 40, "tiles": 9, "reputation": 45,
        "tax_bonus": 1.30, "trade_bonus": 1.25, "grain_bonus": 1.0,
        "def_bonus": 1.0, "inf_bonus": 1.0,
        "debuff_support": -0.20,
        "ai_expansion": 0.2, "ai_military": 0.3,
        "pop_per_tile": 1100, "soldier_ratio": 0.12
    },
    "方国珍": {
        "id": "faction_fangguozhen", "difficulty": "中等",
        "treasury": 6000, "grain": 3000, "troops": 2000,
        "arms": 60, "horses": 20, "tiles": 4, "reputation": 30,
        "tax_bonus": 1.0, "trade_bonus": 1.50, "grain_bonus": 1.0,
        "naval_bonus": 1.40, "def_bonus": 1.30,
        "ai_expansion": 0.3, "ai_military": 0.3,
        "pop_per_tile": 700, "soldier_ratio": 0.15
    },
    "徐寿辉": {
        "id": "faction_xushouhui", "difficulty": "困难",
        "treasury": 6000, "grain": 4000, "troops": 3500,
        "arms": 90, "horses": 40, "tiles": 6, "reputation": 35,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.0,
        "refugee_recruit": 0.50, "convert_bonus": 0.20,
        "stability_drain": 3,
        "ai_expansion": 0.5, "ai_military": 0.6,
        "pop_per_tile": 800, "soldier_ratio": 0.20
    },
    "明玉珍": {
        "id": "faction_mingyuzhen", "difficulty": "简单",
        "treasury": 6500, "grain": 5000, "troops": 3000,
        "arms": 90, "horses": 30, "tiles": 8, "reputation": 40,
        "tax_bonus": 1.0, "trade_bonus": 0.70, "grain_bonus": 1.25,
        "def_bonus": 1.40, "inf_bonus": 1.0,
        "march_penalty": 0.50,  # 进攻行军消耗+50%
        "ai_expansion": 0.2, "ai_military": 0.3,
        "pop_per_tile": 750, "soldier_ratio": 0.15
    },
    "王保保": {
        "id": "faction_wangbaobao", "difficulty": "中等",
        "treasury": 8000, "grain": 5000, "troops": 4000,
        "arms": 120, "horses": 150, "tiles": 6, "reputation": 45,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.0,
        "cav_bonus": 1.40, "inf_bonus": 1.0,
        "resource_penalty": 0.20,  # 资源消耗+20%（v4.1: 原30%）
        "ai_expansion": 0.5, "ai_military": 0.8,
        "pop_per_tile": 900, "soldier_ratio": 0.22
    },
    "漠北诸部": {
        "id": "faction_mobei", "difficulty": "困难",
        "treasury": 5000, "grain": 2000, "troops": 4500,
        "arms": 80, "horses": 200, "tiles": 5, "reputation": 25,
        "tax_bonus": 1.0, "trade_bonus": 1.0, "grain_bonus": 1.0,
        "cav_bonus": 1.45, "inf_bonus": 1.0,
        "non_grassland_penalty": 0.25,  # 非草原收益-25%（v4.1: 原40%）
        "loot_bonus": 0.30,  # 战胜额外银两+30%
        "stability_drain": 2,
        "ai_expansion": 0.7, "ai_military": 0.8,
        "pop_per_tile": 500, "soldier_ratio": 0.30
    }
}


class FactionState:
    """势力状态"""
    def __init__(self, name: str, data: dict):
        self.name = name
        self.data = data
        self.treasury = data["treasury"]
        self.grain = data["grain"]
        self.troops = data["troops"]
        self.tiles = data["tiles"]
        self.reputation = data["reputation"]
        self.stability = 60
        self.development = 40
        self.alive = True
        self.death_round = 0
        self.ending = None
        self.ending_round = 0

        self.tax_bonus = data.get("tax_bonus", 1.0)
        self.trade_bonus = data.get("trade_bonus", 1.0)
        self.grain_bonus = data.get("grain_bonus", 1.0)
        self.cav_bonus = data.get("cav_bonus", 1.0)
        self.inf_bonus = data.get("inf_bonus", 1.0)
        self.naval_bonus = data.get("naval_bonus", 1.0)
        self.def_bonus = data.get("def_bonus", 1.0)
        self.pop_per_tile = data.get("pop_per_tile", 800)
        self.soldier_ratio = data.get("soldier_ratio", 0.15)

        self.debuff_treasury_drain = data.get("debuff_treasury_drain", 0)
        self.debuff_morale_drain_pct = data.get("debuff_morale_drain", 0)
        self.stability_drain = data.get("stability_drain", 0)
        self.non_grassland_penalty = data.get("non_grassland_penalty", 0)
        self.loot_bonus = data.get("loot_bonus", 0)
        self.refugee_bonus = data.get("refugee_bonus", 0)
        self.grain_upkeep_red = data.get("grain_upkeep_red", 0)
        self.resource_penalty = data.get("resource_penalty", 0)
        self.march_penalty = data.get("march_penalty", 0)

        self.ai_expansion = data.get("ai_expansion", 0.4)
        self.ai_military = data.get("ai_military", 0.4)

        # 历史记录
        self.history = []
        self.territory_history = []
        self.bankruptcy_count = 0
        self.famine_count = 0

    @property
    def population(self):
        return self.tiles * self.pop_per_tile

    @property
    def territory_pct(self):
        return self.tiles / TOTAL_TILES

    @property
    def max_garrison(self):
        return GARRISON_BASE + self.tiles * GARRISON_PER_FORT

    def get_season(self, round_num: int) -> int:
        month = ((START_MONTH - 1 + round_num) % 12) + 1
        if 3 <= month <= 5:
            return 1  # 春
        elif 6 <= month <= 8:
            return 2  # 夏
        elif 9 <= month <= 11:
            return 3  # 秋
        else:
            return 4  # 冬


class MonteCarloSimulation:
    """蒙特卡洛模拟引擎"""

    def __init__(self, iterations: int = 5000):
        self.iterations = iterations
        self.results: List[Dict] = []

    def run(self):
        """执行所有迭代"""
        for i in range(self.iterations):
            result = self._run_single()
            self.results.append(result)
            if (i + 1) % 1000 == 0:
                print(f"  已完成 {i + 1}/{self.iterations} 次迭代...")
        return self._compile_report()

    def _run_single(self) -> Dict:
        """单次模拟"""
        factions = {name: FactionState(name, data)
                     for name, data in FACTION_DATA.items()}
        random.seed()  # 重新随机种子

        for rnd in range(MAX_ROUNDS):
            alive_factions = [f for f in factions.values() if f.alive]

            # 每回合每个存活势力执行
            for faction in alive_factions:
                season = faction.get_season(rnd)

                # === 经济结算 ===
                self._settle_economy(faction, season)

                # === AI行为模拟 ===
                if len(alive_factions) > 1:
                    self._simulate_ai_action(faction, factions, rnd, season)

                # === 检查崩溃 ===
                self._check_collapse(faction, rnd)

                # === 检查结局 ===
                if rnd >= PROTECTED_ROUNDS:
                    self._check_ending(faction, rnd, factions)

        # 收集结果
        return self._collect_results(factions)

    def _settle_economy(self, faction: FactionState, season: int):
        """经济结算"""
        pop = faction.population

        # === 收入 ===
        # 税收
        avg_tax_coeff = 0.85  # 平均地块系数
        tax_income = pop * BASE_TAX_RATE * avg_tax_coeff * SEASON_TAX.get(season, 1.0)
        tax_income *= faction.tax_bonus

        # 贸易（简化为地块数×系数）
        trade_income = faction.tiles * TRADE_ROUTE_INCOME * 0.5 * faction.trade_bonus

        # 漠北非草原惩罚
        if faction.non_grassland_penalty > 0:
            grassland_pct = 0.4  # 假设40%草原
            tax_income *= (grassland_pct + (1 - grassland_pct) * (1 - faction.non_grassland_penalty))
            trade_income *= (grassland_pct + (1 - grassland_pct) * (1 - faction.non_grassland_penalty))

        total_income = tax_income + trade_income

        # === 支出 ===
        # 军费
        season_upkeep_mult = SEASON_UPKEEP.get(season, 1.0)
        resource_mult = 1.0 + faction.resource_penalty
        military_cost = faction.troops * MILITARY_UPKEEP * season_upkeep_mult * resource_mult

        # 粮草消耗
        grain_consumption = pop / 100 + faction.troops * 0.5
        if faction.grain_upkeep_red > 0:
            grain_consumption *= (1 - faction.grain_upkeep_red)

        # 元廷国库流失
        treasury_drain = 0
        if faction.debuff_treasury_drain > 0:
            treasury_drain = faction.treasury * faction.debuff_treasury_drain
            min_treasury = FACTION_DATA[faction.name]["treasury"] * YUAN_MIN_TREASURY_PCT
            treasury_drain = min(treasury_drain, faction.treasury - min_treasury)

        total_cost = military_cost + treasury_drain

        # === 粮食生产 ===
        grain_produced = (pop / 10 + faction.tiles * 80) * SEASON_GRAIN.get(season, 1.0)
        grain_produced *= faction.grain_bonus

        # === 人口增长 ===
        pop_growth = BASE_POP_GROWTH + SEASON_POP_GROWTH_BONUS.get(season, 0)
        # 饥荒惩罚
        grain_per_capita = faction.grain / max(pop, 1)
        if grain_per_capita < FAMINE_THRESHOLD:
            pop_growth -= 0.03
            faction.famine_count += 1
        pop_growth = max(-0.05, min(0.08, pop_growth))
        pop_change = int(pop * pop_growth)
        new_pop = max(pop + pop_change, faction.tiles * 50)

        # 更新 pop_per_tile
        faction.pop_per_tile = new_pop / max(faction.tiles, 1)

        # === 随机事件 ===
        event_mult = random.uniform(0.85, 1.15)
        total_income *= event_mult

        # === 应用收支 ===
        faction.treasury += total_income - total_cost
        faction.treasury = max(0, faction.treasury)
        faction.grain += grain_produced - grain_consumption
        faction.grain = max(0, faction.grain)

        # === 稳定度/声望自然变化 ===
        if grain_per_capita < FAMINE_THRESHOLD * 0.5:
            faction.stability -= random.uniform(2, 5)
        elif grain_per_capita > FAMINE_THRESHOLD * 2:
            faction.stability += random.uniform(0, 1)

        if faction.stability_drain > 0:
            faction.stability -= faction.stability_drain
        faction.stability = max(0, min(100, faction.stability))

        if faction.debuff_morale_drain_pct > 0:
            faction.reputation -= max(1, int(faction.debuff_morale_drain_pct * faction.tiles * 0.1))
            faction.reputation = max(0, min(100, faction.reputation))

    def _simulate_ai_action(self, faction: FactionState, all_factions: Dict,
                            rnd: int, season: int):
        """AI 行为模拟：扩张或防守"""
        alive = [f for f in all_factions.values() if f.alive and f.name != faction.name]
        if not alive:
            return

        # 扩张概率
        expand_pct = faction.ai_expansion + faction.ai_military * 0.3
        if faction.treasury < 1000 or faction.troops < faction.population * 0.05:
            expand_pct *= 0.3  # 资源不足，降低扩张

        if random.random() < expand_pct:
            # 选择目标
            target = random.choice(alive)

            # 计算战力
            atk_power = faction.troops
            def_power = target.troops

            # 兵种加成
            atk_power *= faction.cav_bonus if random.random() < 0.3 else faction.inf_bonus
            def_power *= target.cav_bonus if random.random() < 0.3 else target.inf_bonus
            def_power *= target.def_bonus

            # 季节修正
            if season == 4:  # 冬季
                atk_power *= WINTER_ATK_MULT
                def_power *= WINTER_DEF_MULT
            elif season == 3:  # 秋季
                atk_power *= AUTUMN_ATK_MULT
            elif season == 2:  # 夏季
                atk_power *= SUMMER_ATK_MULT

            # 地形防御
            def_power *= min(random.uniform(1.0, 1.6), MAX_DEFENSE_MULT)

            # 随机波动
            atk_power *= random.uniform(0.8, 1.2)
            def_power *= random.uniform(0.7, 1.3)

            # 胜利判断
            if atk_power > def_power * 1.2:
                # 攻方胜利
                atk_loss = int(faction.troops * random.uniform(0.1, 0.3))
                def_loss = int(target.troops * random.uniform(0.4, 0.7))
                tiles_gained = max(1, int(target.tiles * random.uniform(0.1, 0.3)))

                faction.troops -= atk_loss
                target.troops -= def_loss
                faction.tiles += tiles_gained
                target.tiles = max(1, target.tiles - tiles_gained)

                # 掠夺收益
                if faction.loot_bonus > 0:
                    faction.treasury += target.treasury * faction.loot_bonus * random.uniform(0.1, 0.3)

            elif def_power > atk_power * 1.2:
                # 守方胜利
                atk_loss = int(faction.troops * random.uniform(0.4, 0.7))
                def_loss = int(target.troops * random.uniform(0.1, 0.2))
                faction.troops -= atk_loss
                target.troops -= def_loss
            else:
                # 平局
                atk_loss = int(faction.troops * random.uniform(0.2, 0.4))
                def_loss = int(target.troops * random.uniform(0.15, 0.3))
                faction.troops -= atk_loss
                target.troops -= def_loss

            # 下限保护
            faction.troops = max(0, faction.troops)
            target.troops = max(0, target.troops)
            faction.tiles = min(TOTAL_TILES, max(1, faction.tiles))
            target.tiles = min(TOTAL_TILES, max(1, target.tiles))

    def _check_collapse(self, faction: FactionState, rnd: int):
        """检查势力崩溃"""
        if not faction.alive:
            return

        # 国库为0且兵力枯竭
        if faction.treasury <= 0 and faction.troops <= 100:
            faction.bankruptcy_count += 1
            if faction.bankruptcy_count >= 3:
                faction.alive = False
                faction.death_round = rnd + 1
                return

        # 领土归零
        if faction.tiles <= 0:
            faction.alive = False
            faction.death_round = rnd + 1
            return

        # 连续10回合国库<100
        if faction.treasury < 100:
            faction.bankruptcy_count += 1
        else:
            faction.bankruptcy_count = max(0, faction.bankruptcy_count - 1)

        if faction.bankruptcy_count >= 10:
            faction.alive = False
            faction.death_round = rnd + 1

    def _check_ending(self, faction: FactionState, rnd: int,
                      all_factions: Dict):
        """检查结局触发"""
        if not faction.alive or faction.ending is not None:
            return

        alive_count = sum(1 for f in all_factions.values() if f.alive)
        territory = faction.territory_pct

        # 结局一：霸业陨落 (BAD) — 由 _check_collapse 处理

        # 结局二：偏安存续 (NORMAL)
        if rnd >= ENDING_PARTIAL_ROUND and territory <= ENDING_PARTIAL_TERRITORY:
            if faction.treasury >= ENDING_PARTIAL_TREASURY:
                faction.ending = "偏安存续"
                faction.ending_round = rnd + 1
                return

        # 时间耗尽
        if rnd >= MAX_ROUNDS - 1 and faction.ending is None:
            if faction.alive:
                faction.ending = "偏安存续(时间耗尽)"
                faction.ending_round = MAX_ROUNDS
                return
            else:
                faction.ending = "霸业陨落"
                faction.ending_round = faction.death_round
                return

        # 结局三：天下归心 (GOOD)
        if (territory >= ENDING_UNIFY_TERRITORY and
            faction.reputation >= ENDING_UNIFY_REPUTATION and
            faction.stability >= ENDING_UNIFY_STABILITY and
            alive_count <= ENDING_UNIFY_SURVIVORS):
            faction.ending = "天下归心"
            faction.ending_round = rnd + 1
            return

        # 结局四：盛世新朝 (PERFECT)
        if (territory >= ENDING_PERFECT_TERRITORY and
            faction.reputation >= ENDING_PERFECT_REPUTATION and
            faction.stability >= ENDING_PERFECT_STABILITY and
            faction.development >= ENDING_PERFECT_DEVELOPMENT and
            faction.treasury >= ENDING_PERFECT_TREASURY and
            faction.grain >= ENDING_PERFECT_GRAIN and
            alive_count <= 1):
            faction.ending = "盛世新朝"
            faction.ending_round = rnd + 1
            return

    def _collect_results(self, factions: Dict) -> Dict:
        """收集单次模拟结果"""
        alive_count = sum(1 for f in factions.values() if f.alive)
        endings = {}
        survival_rounds = []
        territory_pcts = []

        for name, f in factions.items():
            if f.ending:
                endings[name] = f.ending
            else:
                if f.alive:
                    endings[name] = "存活中(未触发结局)"
                else:
                    endings[name] = "霸业陨落"

            survival_rounds.append(f.death_round if not f.alive else MAX_ROUNDS)
            territory_pcts.append(f.territory_pct)

        return {
            "endings": endings,
            "alive_count": alive_count,
            "avg_survival": sum(survival_rounds) / len(survival_rounds),
            "min_survival": min(survival_rounds),
            "max_territory": max(territory_pcts),
            "any_unification": any(
                e in ("天下归心", "盛世新朝") for e in endings.values()
            ),
            "any_true_ending": any(
                e == "盛世新朝" for e in endings.values()
            )
        }

    def _compile_report(self) -> Dict:
        """编制最终报告"""
        total = len(self.results)

        # 各势力结局统计
        ending_stats = defaultdict(lambda: defaultdict(int))
        survival_stats = defaultdict(list)
        first_death = defaultdict(list)
        territory_final = defaultdict(list)

        for r in self.results:
            for faction_name, ending in r["endings"].items():
                ending_stats[faction_name][ending] += 1

        # 计算各结局达成率
        for faction_name in FACTION_DATA:
            n = total
            stats = ending_stats[faction_name]
            survival_stats[faction_name] = {
                "霸业陨落": stats.get("霸业陨落", 0) / n * 100,
                "偏安存续": (stats.get("偏安存续", 0) +
                           stats.get("偏安存续(时间耗尽)", 0)) / n * 100,
                "天下归心": stats.get("天下归心", 0) / n * 100,
                "盛世新朝": stats.get("盛世新朝", 0) / n * 100,
                "存活中(未触发结局)": stats.get("存活中(未触发结局)", 0) / n * 100,
            }

        # 全局结局统计
        global_endings = defaultdict(int)
        any_ending_reached = 0
        perfect_reached = 0
        all_dead = 0

        for r in self.results:
            endings_reached = set()
            for name, ending in r["endings"].items():
                if ending not in ("存活中(未触发结局)", "霸业陨落"):
                    endings_reached.add(ending)
                    global_endings[ending] += 1

            if endings_reached:
                any_ending_reached += 1
            if r["any_true_ending"]:
                perfect_reached += 1
            if r["alive_count"] == 0:
                all_dead += 1

        return {
            "total_iterations": total,
            "faction_ending_stats": dict(survival_stats),
            "global_endings": dict(global_endings),
            "any_ending_reached_pct": any_ending_reached / total * 100,
            "perfect_reached_pct": perfect_reached / total * 100,
            "all_dead_pct": all_dead / total * 100,
            "raw_results": self.results[:100]  # 保留前100个原始结果
        }


def print_report(report: Dict):
    """打印格式化报告"""
    print("\n" + "=" * 72)
    print("  《元末逐鹿》终局可达性蒙特卡洛模拟报告")
    print("  Balance Report: Endgame Reachability")
    print("=" * 72)
    print(f"  模拟迭代次数: {report['total_iterations']}")
    print(f"  模拟回合数/次: {MAX_ROUNDS}")
    print(f"  总势力数: {len(FACTION_DATA)}")
    print()

    # === Executive Summary ===
    print("─" * 72)
    print("  【执行摘要】")
    print(f"  至少触发一个结局的概率: {report['any_ending_reached_pct']:.1f}%")
    print(f"  盛世新朝(PERFECT)达成率: {report['perfect_reached_pct']:.1f}%")
    print(f"  全势力覆灭概率: {report['all_dead_pct']:.1f}%")
    print()

    # === 各势力结局分布 ===
    print("─" * 72)
    print("  【各势力结局达成率】")
    print(f"  {'势力':<10} {'难度':<6} {'初始地块':<8} {'陨落%':<8} {'偏安%':<8} {'归心%':<8} {'盛世%':<8} {'存活%':<8}")
    print("  " + "-" * 68)

    faction_stats = report["faction_ending_stats"]
    for name, data in FACTION_DATA.items():
        stats = faction_stats[name]
        print(f"  {name:<10} {data['difficulty']:<6} {data['tiles']:<8} "
              f"{stats['霸业陨落']:<8.1f} {stats['偏安存续']:<8.1f} "
              f"{stats['天下归心']:<8.1f} {stats['盛世新朝']:<8.1f} "
              f"{stats['存活中(未触发结局)']:<8.1f}")

    print()

    # === 风险评估 ===
    print("─" * 72)
    print("  【关键风险识别】")

    risks = []
    for name, stats in faction_stats.items():
        death_rate = stats["霸业陨落"]
        if death_rate > 50:
            risks.append((name, "CRITICAL", f"陨落率 {death_rate:.1f}%，远超50%阈值"))
        elif death_rate > 30:
            risks.append((name, "MAJOR", f"陨落率 {death_rate:.1f}%，超过30%"))

    if risks:
        risks.sort(key=lambda x: -float(x[2].split("%")[0].split()[-1]) if "%" in x[2] else 0)
        for name, severity, desc in risks:
            tag = "🔴" if severity == "CRITICAL" else "🟡"
            print(f"  [{severity}] {tag} {name}: {desc}")
    else:
        print("  所有势力陨落率均在可接受范围内。")

    print()

    # === 全局结局分布 ===
    print("─" * 72)
    print("  【全局结局分布】（跨迭代统计）")
    global_ends = report["global_endings"]
    total = report["total_iterations"]
    for ending, count in sorted(global_ends.items(), key=lambda x: -x[1]):
        pct = count / (total * len(FACTION_DATA)) * 100
        print(f"  {ending}: {count}次 ({pct:.2f}% of all faction-endings)")

    print()

    # === 结论 ===
    print("─" * 72)
    print("  【结论与建议】")
    any_pct = report["any_ending_reached_pct"]
    perfect_pct = report["perfect_reached_pct"]
    all_dead_pct = report["all_dead_pct"]

    if any_pct >= 90:
        print(f"  ✅ 终局可达性优秀 ({any_pct:.1f}%)，游戏可以正常推进到结局。")
    elif any_pct >= 70:
        print(f"  ⚠️ 终局可达性尚可 ({any_pct:.1f}%)，但需关注以下问题。")
    else:
        print(f"  ❌ 终局可达性差 ({any_pct:.1f}%)，建议紧急修复。")

    if perfect_pct < 1:
        print(f"  ⚠️ 盛世新朝达成率极低 ({perfect_pct:.1f}%)，完美结局可能过于困难。")

    if all_dead_pct > 10:
        print(f"  ⚠️ 全势力覆灭率偏高 ({all_dead_pct:.1f}%)，游戏可能在中途无势力存活。")

    print()
    print("=" * 72)


if __name__ == "__main__":
    import sys
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"启动蒙特卡洛模拟... ({iterations} 次迭代, 每迭代 {MAX_ROUNDS} 回合)")
    sim = MonteCarloSimulation(iterations=iterations)
    report = sim.run()

    # 保存原始报告
    with open("tools/endgame_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n原始报告已保存至 tools/endgame_report.json")

    print_report(report)
