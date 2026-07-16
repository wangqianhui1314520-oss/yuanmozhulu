"""
战术AI引擎 - 六角格最优行军路线与战损推演（3.2 全链路AI智能体）

职责：
1. 六角格最优行军路线：A*路径规划（含地形/敌情/补给权重）
2. 战损推演：根据兵种克制/地形/兵力比预演战斗结果
3. 驻防驰援：关键据点防守优先级 + 邻接地块支援规划
4. 战术作战：分兵包夹/围城/伏击策略生成
"""
from __future__ import annotations
import math
import heapq
import random
import logging
from typing import Optional
from collections import defaultdict

from server.models.ai_protocol import AICommandSet, AICommand, CommandType
from server.models.world_state import WorldState
from server.core.combat_modifiers import get_counter_bonus, estimate_unit_type_from_faction, UnitType

logger = logging.getLogger("yuanmo.ai.tactical")


class TacticalAI:
    """
    战术AI引擎
    
    核心算法：
    1. A*路径规划（六角格自适应）
    2. 兰彻斯特方程简化版（战损估算）
    3. 威胁评估矩阵（驻防优先级）
    4. 战术模式选择（包夹/围城/伏击/正面）
    """

    # 地形移动代价（六角格基础代价为1）
    TERRAIN_MOVE_COST = {
        "farmland": 1.0, "grassland": 1.0,
        "mountain": 3.0, "desert": 1.5,
        "water": 2.0, "coast": 1.2,
        "city": 1.0, "pass": 2.5,
        "port": 1.0,
    }

    # 地形战斗修正
    TERRAIN_COMBAT_MOD = {
        "mountain": ("defender", 1.4),   # 山地守方+40%
        "city": ("defender", 1.5),        # 城市守方+50%
        "pass": ("defender", 1.7),        # 关隘守方+70%
        "water": ("attacker", 0.6),       # 水域攻方-40%
        "coast": ("attacker", 0.8),       # 海岸攻方-20%
    }

    def __init__(self, world: WorldState):
        self.world = world

    # ============================================================
    # 最优路径规划
    # ============================================================

    def find_optimal_path(
        self, from_tile_id: str, to_tile_id: str, faction_id: str,
        avoid_enemy: bool = True, prefer_supply: bool = True,
    ) -> dict:
        """
        A*六角格最优行军路线
        
        Returns:
            {
                "path": [tile_id, ...],
                "total_cost": float,
                "num_turns": int,
                "risks": [str, ...],
                "alternatives": [...],
            }
        """
        if from_tile_id == to_tile_id:
            return {"path": [from_tile_id], "total_cost": 0, "num_turns": 0, "risks": []}

        tiles = getattr(self.world, 'tiles', {})
        if from_tile_id not in tiles or to_tile_id not in tiles:
            return {"path": [], "total_cost": float('inf'), "num_turns": 0, "risks": ["地块不存在"]}

        # A* search
        open_set = [(0, 0, from_tile_id, [from_tile_id])]  # (f, g, node, path)
        closed = set()
        g_scores = {from_tile_id: 0}

        MAX_OPEN_SET = 2000  # 防止不可达目标遍历全部格子
        while open_set:
            if len(open_set) > MAX_OPEN_SET:
                logger.warning(f"[A*] open_set 超过 {MAX_OPEN_SET}，提前终止寻路 {from_tile_id}→{to_tile_id}")
                break
            f, g, current, path = heapq.heappop(open_set)

            if current == to_tile_id:
                risks = self._assess_path_risks(path, faction_id)
                return {
                    "path": path,
                    "total_cost": round(g, 1),
                    "num_turns": max(1, math.ceil(g / 5)),  # 假设每回合可移动5步
                    "risks": risks,
                    "tiles": [self._tile_info(tid) for tid in path],
                }

            if current in closed:
                continue
            closed.add(current)

            tile = tiles[current]
            for neighbor_id in getattr(tile, 'neighbors', []):
                if neighbor_id in closed:
                    continue

                n_tile = tiles.get(neighbor_id)
                if not n_tile:
                    continue

                # 计算移动代价
                step_cost = self._calculate_step_cost(
                    current, neighbor_id, faction_id, avoid_enemy, prefer_supply
                )

                new_g = g + step_cost
                if neighbor_id not in g_scores or new_g < g_scores[neighbor_id]:
                    g_scores[neighbor_id] = new_g
                    h = self._heuristic(neighbor_id, to_tile_id)
                    new_path = path + [neighbor_id]
                    heapq.heappush(open_set, (new_g + h, new_g, neighbor_id, new_path))

        return {"path": [], "total_cost": float('inf'), "num_turns": 0, "risks": ["无可行路径"]}

    def _calculate_step_cost(
        self, from_id: str, to_id: str, faction_id: str,
        avoid_enemy: bool, prefer_supply: bool
    ) -> float:
        """计算单步移动代价"""
        tiles = getattr(self.world, 'tiles', {})
        to_tile = tiles.get(to_id)
        if not to_tile:
            return 999

        cost = 1.0

        # 地形代价
        tt = self._tile_type_str(getattr(to_tile, 'tile_type', 'farmland'))
        cost *= self.TERRAIN_MOVE_COST.get(tt, 1.0)

        # 敌军地块代价
        owner = getattr(to_tile, 'faction_id', '')
        if owner and owner != faction_id:
            stance = self._get_stance(faction_id, owner)
            if stance == "war":
                if avoid_enemy:
                    cost *= 10.0  # 大幅增加代价以避开
                else:
                    cost *= 2.0  # 敌军地块通过风险
            elif stance != "alliance":
                cost *= 1.5

        # 友军地块加成
        if owner == faction_id:
            cost *= 0.8

        # 补给线加成（己方领地内移动更便宜）
        if prefer_supply and owner == faction_id:
            cost *= 0.9

        # 灾害地块惩罚
        if getattr(to_tile, 'active_disaster', ''):
            cost *= 1.3

        return cost

    def _heuristic(self, tile_a_id: str, tile_b_id: str) -> float:
        """A*启发式函数（六角格Axial坐标距离）"""
        tiles = getattr(self.world, 'tiles', {})
        tile_a = tiles.get(tile_a_id)
        tile_b = tiles.get(tile_b_id)
        if not tile_a or not tile_b:
            return 999

        # 优先使用六角格 axial 坐标 (q, r) 计算真实六角距离
        aq = getattr(tile_a, 'q', None)
        ar = getattr(tile_a, 'r', None)
        bq = getattr(tile_b, 'q', None)
        br = getattr(tile_b, 'r', None)

        if aq is not None and ar is not None and bq is not None and br is not None:
            hex_dist = self._calculate_hex_distance(aq, ar, bq, br)
            if hex_dist > 0:
                # 使用最快地形代价作为每步最小代价估算
                min_cost = min(self.TERRAIN_MOVE_COST.values())
                return hex_dist * min_cost

        # 回退：使用质心坐标的欧氏距离（乘以最快地形代价）
        ax = getattr(tile_a, 'centroid_lon', 0) or 0
        ay = getattr(tile_a, 'centroid_lat', 0) or 0
        bx = getattr(tile_b, 'centroid_lon', 0) or 0
        by = getattr(tile_b, 'centroid_lat', 0) or 0

        if ax or ay or bx or by:
            min_cost = min(self.TERRAIN_MOVE_COST.values())
            return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2) * min_cost

        # 无坐标时返回默认
        return 1.0

    @staticmethod
    def _calculate_hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
        """
        计算六角格 Axial 坐标距离
        
        使用标准六角格距离公式:
            distance = (abs(dq) + abs(dq+dr) + abs(dr)) / 2
            其中第三个轴 s = -(q+r)，差值 = abs(q1+r1 - q2-r2)
        
        Args:
            q1, r1: 第一个六角格的 axial 坐标
            q2, r2: 第二个六角格的 axial 坐标
        
        Returns:
            六角格距离（整数步数）
        """
        dq = q1 - q2
        dr = r1 - r2
        ds = (q1 + r1) - (q2 + r2)
        return (abs(dq) + abs(dr) + abs(ds)) // 2

    # ============================================================
    # 战损推演
    # ============================================================

    def predict_battle(
        self, attacker_tile_id: str, defender_tile_id: str,
        attacker_troops: int, attacker_faction: str,
    ) -> dict:
        """
        战损推演 - 预演战斗结果
        
        使用简化版兰彻斯特平方律，结合：
        - 兵种克制
        - 地形修正
        - 城防减伤
        - 兵力数量效应
        
        Returns:
            {
                "attacker_win_probability": float,  # 0-1
                "expected_attacker_losses": int,
                "expected_defender_losses": int,
                "post_battle_attacker_troops": int,
                "post_battle_defender_troops": int,
                "key_factors": [str, ...],
                "recommendation": "attack"/"caution"/"avoid",
            }
        """
        tiles = getattr(self.world, 'tiles', {})
        def_tile = tiles.get(defender_tile_id)
        atk_tile = tiles.get(attacker_tile_id)

        if not def_tile:
            return {"attacker_win_probability": 0, "recommendation": "avoid",
                    "key_factors": ["目标地块不存在"]}

        defender_troops = getattr(def_tile, 'troops', 0)
        defender_faction = getattr(def_tile, 'faction_id', '')
        fortification = getattr(def_tile, 'fortification', 0)

        if defender_troops <= 0:
            return {
                "attacker_win_probability": 1.0,
                "expected_attacker_losses": 0,
                "expected_defender_losses": 0,
                "post_battle_attacker_troops": attacker_troops,
                "post_battle_defender_troops": 0,
                "key_factors": ["无人防守"],
                "recommendation": "attack",
            }

        key_factors = []

        # 1. 基础战力比
        base_ratio = attacker_troops / max(1, defender_troops)
        key_factors.append(f"基础兵力比 {base_ratio:.1%}")

        # 1.5. 兵种克制因子
        tt = self._tile_type_str(getattr(def_tile, 'tile_type', 'farmland'))
        attacker_unit_type = estimate_unit_type_from_faction(
            attacker_faction,
            self._tile_type_str(getattr(atk_tile, 'tile_type', 'farmland')) if atk_tile else ""
        )
        defender_unit_type = estimate_unit_type_from_faction(
            defender_faction,
            tt if def_tile else ""
        )
        counter_bonus = get_counter_bonus(attacker_unit_type, defender_unit_type)
        counter_mult = 1.0 + counter_bonus
        if counter_bonus != 0.0:
            key_factors.append(f"兵种克制 {counter_bonus:+.0%}")

        # 2. 地形修正
        terrain_mult = 1.0
        if tt in self.TERRAIN_COMBAT_MOD:
            beneficiary, mod = self.TERRAIN_COMBAT_MOD[tt]
            if beneficiary == "defender":
                terrain_mult = mod
                key_factors.append(f"守方地形优势 x{mod:.1f}")
            else:
                terrain_mult = 1.0 / mod
                key_factors.append(f"攻方地形劣势 /{mod:.1f}")

        # 3. 城防减伤
        fort_mult = 1.0 + fortification / 200  # 100城防 = 50%减伤
        if fortification > 0:
            key_factors.append(f"城防减伤 x{fort_mult:.2f}")

        # v3.3 防御倍率硬上限：防止城墙+关隘+地形无限叠加
        from server.core.combat_modifiers import apply_defense_cap
        raw_defense = terrain_mult * fort_mult
        defense_mult = apply_defense_cap(raw_defense)
        if raw_defense > defense_mult:
            key_factors.append(f"防御倍率限制: {raw_defense:.2f}x → {defense_mult:.2f}x (上限2.5x)")

        # 4. 兰彻斯特有效战力（含兵种克制）
        effective_attacker = attacker_troops * counter_mult
        effective_defender = defender_troops * defense_mult

        # 5. 胜率计算
        if effective_attacker > effective_defender * 1.5:
            win_prob = 0.9 + random.uniform(0, 0.1)
        elif effective_attacker > effective_defender:
            win_prob = 0.5 + (effective_attacker / effective_defender - 1) * 0.4
        else:
            win_prob = max(0.05, effective_attacker / effective_defender * 0.5)

        # 6. 战损估算
        if win_prob > 0.7:
            attacker_loss_rate = 0.15 + random.uniform(0, 0.15)
            defender_loss_rate = 0.6 + random.uniform(0, 0.3)
        elif win_prob > 0.4:
            attacker_loss_rate = 0.35 + random.uniform(0, 0.15)
            defender_loss_rate = 0.4 + random.uniform(0, 0.3)
        else:
            attacker_loss_rate = 0.5 + random.uniform(0, 0.2)
            defender_loss_rate = 0.2 + random.uniform(0, 0.2)

        attacker_losses = int(attacker_troops * attacker_loss_rate)
        defender_losses = int(defender_troops * defender_loss_rate)

        # 7. 建议
        if win_prob > 0.75 and attacker_losses < attacker_troops * 0.3:
            recommendation = "attack"
        elif win_prob > 0.5 and attacker_losses < attacker_troops * 0.5:
            recommendation = "caution"
        else:
            recommendation = "avoid"

        return {
            "attacker_win_probability": round(win_prob, 2),
            "expected_attacker_losses": attacker_losses,
            "expected_defender_losses": defender_losses,
            "post_battle_attacker_troops": attacker_troops - attacker_losses,
            "post_battle_defender_troops": max(0, defender_troops - defender_losses),
            "key_factors": key_factors,
            "recommendation": recommendation,
            "effective_power_ratio": round(effective_attacker / max(1, effective_defender), 2),
            "counter_bonus": counter_bonus,
            "attacker_unit_type": attacker_unit_type.value if attacker_unit_type else "unknown",
            "defender_unit_type": defender_unit_type.value if defender_unit_type else "unknown",
        }

    # ============================================================
    # 驻防驰援规划
    # ============================================================

    def garrison_priority(self, faction_id: str) -> list[dict]:
        """
        驻防优先级分析
        
        返回每个地块的防守紧急性排序。
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return []

        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        priorities = []

        for t in tiles:
            score = 0

            # 边境加权
            is_border = self._is_border_tile(t, faction_id)
            if is_border:
                score += 50

            # 首都加权
            if t.tile_id == faction.capital_tile:
                score += 100

            # 敌情加权
            enemy_threat = sum(
                getattr(self.world.tiles.get(nid, None), 'troops', 0) or 0
                for nid in getattr(t, 'neighbors', [])
                if getattr(self.world.tiles.get(nid, None), 'faction_id', '') != faction_id
            )
            score += enemy_threat // 10

            # 兵力不足加权
            current_troops = getattr(t, 'troops', 0)
            if current_troops < 200:
                score += 30

            # 发展度加权
            dev = getattr(t, 'development_level', 20)
            score += dev // 5

            priority = "critical" if score >= 120 else ("high" if score >= 80 else ("medium" if score >= 40 else "low"))

            priorities.append({
                "tile_id": t.tile_id,
                "tile_name": getattr(t, 'tile_name', t.tile_id),
                "priority_score": score,
                "priority": priority,
                "current_troops": current_troops,
                "is_border": is_border,
                "is_capital": t.tile_id == faction.capital_tile,
            })

        return sorted(priorities, key=lambda p: p["priority_score"], reverse=True)

    def generate_support_plan(self, faction_id: str) -> AICommandSet:
        """
        生成驻防驰援计划
        
        分析关键据点防守薄弱处，生成调兵指令。
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return AICommandSet(agent_type="tactical_ai", faction_id=faction_id)

        garrison = self.garrison_priority(faction_id)
        commands = []

        # 找到兵力过剩的地块和兵力不足的地块
        surplus = []
        deficit = []

        for g in garrison:
            if g["current_troops"] > 500 and g["priority_score"] < 60:
                surplus.append(g)
            elif g["current_troops"] < 200 and g["priority_score"] > 60:
                deficit.append(g)

        # 调兵填补
        for d in deficit[:3]:
            if surplus:
                s = surplus.pop(0)
                transfer = min(s["current_troops"] - 300, 300)
                if transfer > 50:
                    commands.append(AICommand(
                        command_id=f"{faction_id}_support_{s['tile_id']}_to_{d['tile_id']}",
                        command_type=CommandType.MARCH,
                        faction_id=faction_id,
                        params={
                            "from_tile": s["tile_id"],
                            "to_tile": d["tile_id"],
                            "troops": transfer,
                        },
                        reason=f"驰援{d['tile_name']}（防守薄弱）",
                        priority=8 if d["priority"] == "critical" else 6,
                    ))

        return AICommandSet(
            agent_type="tactical_ai",
            faction_id=faction_id,
            decision_summary=f"驻防驰援：{len(commands)}路调兵",
            commands=commands,
            risk_assessment="low",
        )

    # ============================================================
    # 战术作战规划
    # ============================================================

    def plan_tactical_operation(
        self, faction_id: str, target_tile_id: str,
    ) -> dict:
        """
        战术作战规划 - 对目标地块的完整进攻方案
        
        包括：
        - 主攻方向
        - 侧翼包夹路线
        - 围城策略
        - 伏击建议
        """
        tiles = getattr(self.world, 'tiles', {})
        target = tiles.get(target_tile_id)
        if not target:
            return {"error": "目标地块不存在"}

        target_owner = getattr(target, 'faction_id', '')
        target_troops = getattr(target, 'troops', 0)
        target_tt = self._tile_type_str(getattr(target, 'tile_type', 'farmland'))

        faction_tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        adjacent_tiles = [t for t in faction_tiles if target_tile_id in getattr(t, 'neighbors', [])]

        if not adjacent_tiles:
            return {"error": "无邻接己方地块，建议先行军接近"}

        plan = {
            "target_tile": target_tile_id,
            "target_name": getattr(target, 'tile_name', target_tile_id),
            "target_owner": target_owner,
            "target_troops": target_troops,
            "target_terrain": target_tt,
            "strategy": [],
            "attack_routes": [],
            "recommended_troops": 0,
        }

        # 主攻方向
        best_tile = max(adjacent_tiles, key=lambda t: getattr(t, 'troops', 0))
        main_troops = getattr(best_tile, 'troops', 0)

        # 策略选择
        if target_tt in ("city", "mountain", "pass"):
            # 城防目标 → 建议围城
            plan["strategy"].append({
                "type": "siege",
                "description": "围城困敌，切断补给，待敌粮尽",
                "troops_needed": max(500, target_troops * 2),
                "estimated_turns": random.randint(2, 5),
            })

        if len(adjacent_tiles) >= 2:
            # 可包夹
            plan["strategy"].append({
                "type": "flank",
                "description": "多路包夹，敌军首尾难顾",
                "routes": [
                    {"from": t.tile_id, "troops": getattr(t, 'troops', 0) // 3}
                    for t in adjacent_tiles[:3]
                ],
                "flanking_bonus": min(3, len(adjacent_tiles)) * 0.15,  # 每路+15%
            })

        # 伏击建议
        ambush_tiles = [
            t for t in adjacent_tiles
            if self._tile_type_str(getattr(t, 'tile_type', '')) in ("mountain", "forest", "pass")
        ]
        if ambush_tiles:
            plan["strategy"].append({
                "type": "ambush",
                "description": f"在{getattr(ambush_tiles[0], 'tile_name', ambush_tiles[0].tile_id)}设伏",
                "tile_id": ambush_tiles[0].tile_id,
                "ambush_bonus": 1.5,
            })

        # 建议兵力
        if target_troops > 0:
            plan["recommended_troops"] = int(target_troops * (1.5 if target_tt in ("city", "pass") else 1.2))
        else:
            plan["recommended_troops"] = 200

        # 攻击路线
        for atk_tile in adjacent_tiles:
            prediction = self.predict_battle(
                atk_tile.tile_id, target_tile_id,
                getattr(atk_tile, 'troops', 0), faction_id,
            )
            plan["attack_routes"].append({
                "from_tile": atk_tile.tile_id,
                "from_troops": getattr(atk_tile, 'troops', 0),
                "prediction": prediction,
            })

        return plan

    # ============================================================
    # 辅助方法
    # ============================================================

    def _assess_path_risks(self, path: list[str], faction_id: str) -> list[str]:
        """评估路径风险"""
        risks = []
        tiles = getattr(self.world, 'tiles', {})
        for tid in path:
            tile = tiles.get(tid)
            if not tile:
                continue
            owner = getattr(tile, 'faction_id', '')
            if owner and owner != faction_id:
                stance = self._get_stance(faction_id, owner)
                if stance == "war":
                    risks.append(f"途经敌境: {getattr(tile, 'tile_name', tid)}")
            disaster = getattr(tile, 'active_disaster', '')
            if disaster:
                risks.append(f"途经灾区: {getattr(tile, 'tile_name', tid)}")
        return risks

    def _is_border_tile(self, tile, fid: str) -> bool:
        """判断是否边境"""
        for nid in getattr(tile, 'neighbors', []):
            n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
            if n_tile and getattr(n_tile, 'faction_id', '') != fid:
                return True
        return False

    def _get_stance(self, fid_a: str, fid_b: str) -> str:
        """获取关系立场"""
        for key, rel in getattr(self.world, 'relations', {}).items():
            if (rel.faction_a == fid_a and rel.faction_b == fid_b) or \
               (rel.faction_a == fid_b and rel.faction_b == fid_a):
                return rel.stance.value if hasattr(rel.stance, 'value') else str(rel.stance)
        return "neutral"

    def _tile_info(self, tile_id: str) -> dict:
        """地块简要信息"""
        tile = getattr(self.world, 'tiles', {}).get(tile_id)
        if not tile:
            return {"tile_id": tile_id}
        return {
            "tile_id": tile_id,
            "tile_name": getattr(tile, 'tile_name', tile_id),
            "tile_type": self._tile_type_str(getattr(tile, 'tile_type', '')),
            "owner": getattr(tile, 'faction_id', ''),
            "troops": getattr(tile, 'troops', 0),
        }

    @staticmethod
    def _tile_type_str(tt) -> str:
        if hasattr(tt, 'value'):
            return tt.value
        return str(tt)
