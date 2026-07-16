"""
文官内政AI - 全自动城建与资源管理智能体（3.2 全链路AI智能体）

职责：
1. 全自动城建：建筑优先级排序、地块分析、建造规划
2. 资源调配：粮草/银两/军械/战马四维资源最优分配
3. 民心维稳：赈灾、文化政策、徭役平衡
4. 国策推荐：根据当前局势推荐最优国策组合
5. 权限管理：半委任/全委任两种模式
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from collections import defaultdict

from server.models.ai_protocol import (
    AICommandSet, AICommand, CommandType,
    DelegationLevel, DelegationDomain,
)
from server.models.world_state import WorldState, FactionState

logger = logging.getLogger("yuanmo.ai.civil")


class CivilAI:
    """
    文官内政AI
    
    核心算法：
    1. 资源四维评估 → 确定优先级
    2. 地块分析 → 选出最优建设地块
    3. 建筑排队 → 按边际收益排序
    4. 全局平衡 → 避免过度集中
    """

    # 建筑优先级（0-10，越高越优先）
    BUILDING_PRIORITY = {
        "granary": 9,      # 粮仓：粮草安全
        "armory": 8,        # 军械所：军备产能
        "barracks": 8,      # 征兵营：自动募兵
        "farmland": 7,      # 农田：基础粮食
        "clinic": 7,        # 医馆：瘟疫抵抗
        "stable": 6,        # 马场：战马产出
        "workshop": 6,      # 工坊：银两产出
        "beacon": 5,        # 烽燧：视野预警
        "temple": 5,        # 宗庙：民心加成
        "wall": 6,          # 城墙：城防加成
        "dock": 5,          # 码头：贸易水军
    }

    # 建筑成本
    BUILDING_COST = {
        "granary": 800, "armory": 1000, "barracks": 600,
        "farmland": 400, "clinic": 600, "stable": 800,
        "workshop": 700, "beacon": 300, "temple": 500,
        "wall": 500, "dock": 900,
    }

    def __init__(self, world: WorldState):
        self.world = world

    # ============================================================
    # 主分析接口
    # ============================================================

    def analyze_faction(self, faction_id: str) -> dict:
        """
        全面分析势力内政状态
        
        Returns:
            {
                "resource_assessment": {...},
                "building_recommendations": [...],
                "policy_recommendations": [...],
                "risk_alerts": [...],
                "priority_actions": [...],
            }
        """
        faction = self.world.factions.get(faction_id)
        if not faction or not faction.is_alive:
            return {"error": "势力不存在或已灭亡"}

        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []

        return {
            "resource_assessment": self._assess_resources(faction),
            "building_recommendations": self._recommend_buildings(faction, tiles),
            "policy_recommendations": self._recommend_policies(faction),
            "risk_alerts": self._detect_risks(faction, tiles),
            "priority_actions": self._prioritize_actions(faction, tiles),
        }

    # ============================================================
    # 全自动城建
    # ============================================================

    def generate_build_plan(self, faction_id: str, budget: int = 0) -> AICommandSet:
        """
        生成自动城建计划
        
        分析当前势力建筑短板，按边际收益推荐建造顺序。
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return AICommandSet(agent_type="civil_ai", faction_id=faction_id)

        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        available_budget = budget or max(0, faction.treasury - 1000)  # 预留1000应急
        commands = []

        # 统计已有建筑
        existing_buildings = defaultdict(int)
        for t in tiles:
            for b in list(getattr(t, 'buildings', [])):
                existing_buildings[b] += 1

        building_scores = self._score_building_needs(faction, existing_buildings)

        for btype, score in sorted(building_scores, key=lambda x: x[1], reverse=True):
            cost = self.BUILDING_COST.get(btype, 800)
            if cost > available_budget:
                continue

            # 选择最优地块
            best_tile = self._find_best_build_tile(btype, tiles, faction_id)
            if best_tile:
                commands.append(AICommand(
                    command_id=f"{faction_id}_build_{btype}_{best_tile.tile_id}",
                    command_type=CommandType.BUILD,
                    faction_id=faction_id,
                    params={"tile_id": best_tile.tile_id, "building_type": btype},
                    reason=f"兴建{btype}（需求评分{score:.1f}）",
                    priority=int(score),
                    estimated_cost={"gold": cost},
                ))
                available_budget -= cost

        return AICommandSet(
            agent_type="civil_ai",
            faction_id=faction_id,
            turn=getattr(self.world, 'current_round', 0),
            decision_summary=f"城建计划：预算{available_budget}两已用{budget - available_budget}两",
            commands=commands,
            risk_assessment="low",
        )

    # ============================================================
    # 资源调配推荐
    # ============================================================

    def generate_resource_plan(self, faction_id: str) -> dict:
        """
        生成资源调配方案
        
        返回最优的税收、赈灾、发展组合。
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return {}

        plan = {
            "tax_recommendation": "normal",
            "should_relief": False,
            "should_develop": False,
            "should_build": False,
            "suggestions": [],
        }

        # 税收建议
        if faction.treasury < 1000 and faction.population > 5000:
            plan["tax_recommendation"] = "heavy"
            plan["suggestions"].append("国库空虚，建议加征赋税")
        elif faction.treasury > 20000:
            plan["tax_recommendation"] = "light"
            plan["suggestions"].append("府库充盈，建议减税养民")

        # 赈灾建议
        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        disasters = [t for t in tiles if getattr(t, 'active_disaster', '')]
        if disasters and faction.grain > 500:
            plan["should_relief"] = True
            plan["suggestions"].append(f"领地内有{len(disasters)}处灾害，应尽快赈灾")

        # 发展建议
        low_dev = [t for t in tiles if getattr(t, 'development_level', 20) < 40]
        if low_dev and faction.treasury > 1000:
            plan["should_develop"] = True
            plan["suggestions"].append(f"有{len(low_dev)}块低发展度地块，建议开发")

        # 建造建议
        if faction.treasury > 2000:
            plan["should_build"] = True

        # 民心维稳
        if faction.realm_stability < 30:
            plan["suggestions"].append("民心低迷，建议赈灾/文教/大赦")
            if faction.treasury > 800:
                plan["suggestions"].append("可推行文教政策（800两，民心+3）")

        return plan

    # ============================================================
    # 委任模式指令生成
    # ============================================================

    def generate_auto_commands(
        self, faction_id: str, delegation_level: DelegationLevel
    ) -> AICommandSet:
        """
        根据委任等级自动生成指令
        
        Args:
            faction_id: 势力ID
            delegation_level: 委任等级
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return AICommandSet(agent_type="civil_ai", faction_id=faction_id)

        commands = []

        if delegation_level in (DelegationLevel.SEMI_AUTO, DelegationLevel.FULL_AUTO):
            # 自动城建
            build_commands = self.generate_build_plan(faction_id).commands
            commands.extend(build_commands[:3])  # 每回合最多3个建造

            # 自动开发
            tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
            low_dev = [t for t in tiles if getattr(t, 'development_level', 20) < 40]
            if low_dev and faction.treasury > 1500:
                for t in low_dev[:2]:
                    commands.append(AICommand(
                        command_id=f"{faction_id}_auto_dev_{t.tile_id}",
                        command_type=CommandType.DEVELOP,
                        faction_id=faction_id,
                        params={"tile_id": t.tile_id, "type": "farmland"},
                        reason="自动开发低发展度地块",
                        priority=5,
                        estimated_cost={"gold": 500},
                    ))

            # 自动赈灾
            disasters = [t for t in tiles if getattr(t, 'active_disaster', '')]
            for t in disasters[:2]:
                if faction.grain > 500:
                    commands.append(AICommand(
                        command_id=f"{faction_id}_auto_relief_{t.tile_id}",
                        command_type=CommandType.RELIEF,
                        faction_id=faction_id,
                        params={"tile_id": t.tile_id},
                        reason="自动赈灾以安民心",
                        priority=9,
                    ))

        if delegation_level == DelegationLevel.SEMI_AUTO:
            # 半委任：只自动执行低消耗操作
            commands = [c for c in commands if c.estimated_cost.get("gold", 0) <= 500]

        if delegation_level == DelegationLevel.ADVISORY:
            # 建议模式：只返回推荐，不执行
            for c in commands:
                c.params["recommend_only"] = True

        return AICommandSet(
            agent_type="civil_ai",
            faction_id=faction_id,
            turn=getattr(self.world, 'current_round', 0),
            decision_summary=f"内政{'全委任' if delegation_level == DelegationLevel.FULL_AUTO else '半委任' if delegation_level == DelegationLevel.SEMI_AUTO else '建议'}模式：{len(commands)}项操作",
            commands=commands,
            risk_assessment="low",
        )

    # ============================================================
    # 内部算法
    # ============================================================

    def _assess_resources(self, faction) -> dict:
        """资源四维评估"""
        return {
            "treasury": {
                "value": faction.treasury,
                "status": "healthy" if faction.treasury > 5000 else ("warning" if faction.treasury > 1000 else "critical"),
                "per_tile": faction.treasury // max(1, faction.tile_count),
            },
            "grain": {
                "value": faction.grain,
                "status": "healthy" if faction.grain > 3000 else ("warning" if faction.grain > 500 else "critical"),
                "months_remaining": faction.grain // max(1, faction.troops // 20 + faction.population // 200),
            },
            "troops": {
                "value": faction.troops,
                "status": "healthy" if faction.trops > 5000 else ("warning" if faction.troops > 1000 else "critical"),
                "ratio_to_pop": round(faction.troops / max(1, faction.population), 2),
            },
            "arms": {
                "value": faction.arms,
                "status": "healthy" if faction.arms > 300 else ("warning" if faction.arms > 100 else "critical"),
            },
        }

    def _recommend_buildings(self, faction, tiles: list) -> list[dict]:
        """推荐建造"""
        existing = defaultdict(int)
        for t in tiles:
            for b in list(getattr(t, 'buildings', [])):
                existing[b] += 1

        scored = self._score_building_needs(faction, existing)
        recommendations = []
        for btype, score in scored:
            if score > 3:
                recommendations.append({
                    "building": btype,
                    "priority_score": round(score, 1),
                    "cost": self.BUILDING_COST.get(btype, 800),
                    "reason": self._building_reason(btype, faction, existing),
                })
        return recommendations[:5]

    def _recommend_policies(self, faction) -> list[dict]:
        """推荐国策"""
        recommendations = []

        if faction.realm_stability < 40:
            recommendations.append({"policy": "light_tax", "reason": "民心低迷，轻徭薄赋", "priority": 9})
        if faction.troops < 3000 and faction.tile_count >= 3:
            recommendations.append({"policy": "military_farm", "reason": "兵力不足，军屯养兵", "priority": 8})
        if faction.population > 15000 and faction.grain < faction.population // 2:
            recommendations.append({"policy": "heavy_agriculture", "reason": "人多粮少，重农抑商", "priority": 8})
        if faction.court_stability < 40:
            recommendations.append({"policy": "civil_exam", "reason": "朝纲不稳，开科取士", "priority": 7})
        if faction.treasury < 2000 and faction.population > 10000:
            recommendations.append({"policy": "corvee_labor", "reason": "国库空虚，徭役征发", "priority": 5})

        return sorted(recommendations, key=lambda r: r["priority"], reverse=True)[:3]

    def _detect_risks(self, faction, tiles: list) -> list[str]:
        """检测风险"""
        risks = []

        if faction.grain < 500:
            risks.append("粮草告急，即将断粮")
        if faction.treasury < 500 and faction.troops > 100:
            risks.append("库银不足，无法支付军饷")
        if faction.population < 1000:
            risks.append("人口凋零，影响征兵和生产")
        if faction.realm_stability < 20:
            risks.append("民心极低，随时可能叛乱")

        # 检查领地连通性
        if tiles:
            disasters = sum(1 for t in tiles if getattr(t, 'active_disaster', ''))
            if disasters > len(tiles) // 3:
                risks.append(f"领地{disasters}处受灾，急需赈济")

        return risks

    def _prioritize_actions(self, faction, tiles: list) -> list[str]:
        """优先级排序"""
        actions = []
        risks = self._detect_risks(faction, tiles)

        if "粮草告急" in "".join(risks):
            actions.append("立即屯田或购买粮草")
        if "民心极低" in "".join(risks):
            actions.append("赈灾/文教/大赦提民心")
        if faction.troops < 1000 and faction.treasury > 2000:
            actions.append("征兵扩军")
        if faction.treasury < 500:
            actions.append("征税或节流")

        recommendations = self._recommend_buildings(faction, tiles)
        for r in recommendations[:2]:
            actions.append(f"建造{r['building']}（{r['reason']}）")

        return actions

    def _score_building_needs(self, faction, existing: dict) -> list[tuple]:
        """建筑需求评分"""
        scores = []

        # 粮草不足 → 粮仓
        if faction.grain < 2000 and existing.get("granary", 0) < 1:
            scores.append(("granary", 9.0))
        elif faction.grain < 5000 and existing.get("granary", 0) < 2:
            scores.append(("granary", 7.0))

        # 兵力不足 → 征兵营
        if faction.troops < 3000 and existing.get("barracks", 0) < 1:
            scores.append(("barracks", 8.0))

        # 军械不足 → 军械所
        if faction.arms < 500 and existing.get("armory", 0) < 1:
            scores.append(("armory", 8.0))

        # 农田基础
        if existing.get("farmland", 0) < 3:
            scores.append(("farmland", 6.0))

        # 人口大 → 医馆
        if faction.population > 10000 and existing.get("clinic", 0) < 1:
            scores.append(("clinic", 7.0))

        # 钱多 → 工坊
        if faction.treasury > 5000 and existing.get("workshop", 0) < 2:
            scores.append(("workshop", 6.0))

        # 边境 → 城墙/烽燧
        tiles = self.world.get_faction_tiles(faction.faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        border_count = sum(1 for t in tiles if self._is_border(t, faction.faction_id))
        if border_count > 0 and existing.get("wall", 0) < border_count:
            scores.append(("wall", 5.0))
        if border_count > 0 and existing.get("beacon", 0) < border_count // 2:
            scores.append(("beacon", 4.0))

        return scores

    def _find_best_build_tile(self, btype: str, tiles: list, fid: str):
        """找到最优建造地块"""
        candidates = []
        for t in tiles:
            if btype in list(getattr(t, 'buildings', [])):
                continue  # 已有此建筑

            score = 0
            # 边境地块优先建防御建筑
            if btype in ("wall", "beacon") and self._is_border(t, fid):
                score += 3
            # 发展度高的优先
            score += getattr(t, 'development_level', 20) / 20
            # 人口多的优先
            score += getattr(t, 'population', 0) / 5000

            candidates.append((t, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return tiles[0] if tiles else None

    def _is_border(self, tile, fid: str) -> bool:
        """检查是否为边境地块"""
        for nid in getattr(tile, 'neighbors', []):
            n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
            if n_tile and getattr(n_tile, 'faction_id', '') != fid:
                return True
        return False

    def _building_reason(self, btype: str, faction, existing: dict) -> str:
        """生成建造理由"""
        reasons = {
            "granary": "增加粮草储备",
            "armory": "提升军械产能",
            "barracks": "自动招募新兵",
            "farmland": "提升粮食产出",
            "clinic": "抵御瘟疫灾害",
            "stable": "产出战马",
            "workshop": "增加银两收入",
            "beacon": "扩大视野警戒",
            "temple": "提升民心朝纲",
            "wall": "增强城防工事",
            "dock": "开启水路贸易",
        }
        return reasons.get(btype, "强国力")
