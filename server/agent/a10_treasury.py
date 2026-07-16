"""
A10 度支司 - AI 经济决策智能体

职责:
- AI 制定税率（丰年加税/灾年减税/常平）
- AI 制定粮储策略（存粮比例/军粮/赈灾/贸易分配）
- AI 制定贸易优先级（买什么/卖什么/贸易对象）
- AI 制定工程建设优先级（粮仓/城墙/驿道/学府/医馆）

模型分组: law (chat_strategy) — 需深度战略分析
触发方式: 后端自动回合驱动（非玩家势力）
"""
from __future__ import annotations
import json
import logging
import random
import re
from typing import Optional

from .base import BaseAgent, AgentCategory
from ..infra.llm_client.hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.agent.a10_treasury")

# A10 决策领域
ECONOMY_DOMAINS = ["tax", "grain", "trade", "construction"]

# 建设工程类型
BUILDING_TYPES = ["granary", "wall", "road", "academy", "hospital"]


class A10TreasuryAgent(BaseAgent):
    """A10 度支司 - AI度支尚书智能体"""

    def __init__(self, faction_id: str = "", agent_id: str = ""):
        super().__init__(
            agent_id=agent_id or f"A10_{faction_id}",
            category=AgentCategory.A10_TREASURY,
            faction_id=faction_id,
            max_retries=2,
            retry_delay=1.5,
        )

    async def step(self, world_snapshot: dict, clients: dict) -> dict:
        """A10 主决策循环：制定本回合经济政策"""
        if not self.faction_id:
            return {"action": "none", "reason": "A10 需绑定势力"}

        try:
            policy = await self.formulate_policy(self.faction_id, world_snapshot, clients)
            return {"action": "economic_policy", "policy": policy}
        except Exception as e:
            logger.warning(f"A10 step 失败: {e}")
            return {"action": "none", "reason": str(e)}

    async def formulate_policy(
        self, faction_id: str, world_state: dict, clients: dict
    ) -> dict:
        """
        制定完整经济政策 — 本回合的税收/粮储/贸易/建设四大决策

        Args:
            faction_id: 目标势力ID
            world_state: 世界状态（含势力/地块/经济数据）
            clients: LLM客户端

        Returns:
            {
                "tax_policy": {"rate": float, "reasoning": str},
                "grain_policy": {"military_pct": int, "relief_pct": int, "trade_pct": int, "reserve_pct": int},
                "trade_policy": {"imports": [...], "exports": [...], "partners": [...]},
                "construction_policy": {"priority": ["granary", "wall", ...], "reasoning": str},
                "narrative": "度支尚书的口吻叙述"
            }
        """
        client: TencentHunyuanClient = clients.get("law", clients.get("advisor"))
        if not client:
            return self._fallback_policy(faction_id, world_state)

        faction = world_state.get("factions", {}).get(faction_id, {})
        if not faction:
            return self._fallback_policy(faction_id, world_state)

        faction_name = faction.get("name", faction_id)
        treasury = faction.get("treasury", 0)
        grain = faction.get("grain", 0)
        population = faction.get("population", 0)
        troops = faction.get("troops", 0)
        tile_count = faction.get("tile_count", 0)
        realm_stability = faction.get("realm_stability", 50)
        disaster_index = world_state.get("disaster_index", 0)
        current_season = world_state.get("current_season", "春")

        # 计算粮食需求
        monthly_grain_need = troops * 3 + population // 10
        grain_months = grain / max(monthly_grain_need, 1)

        # 已有建筑
        buildings = faction.get("buildings", {})
        has_granary = buildings.get("granary", 0) > 0
        has_wall = buildings.get("wall", 0) > 0
        has_academy = buildings.get("academy", 0) > 0

        # 邻国关系
        neighbors = faction.get("neighbors", [])
        relations = world_state.get("relations", {})
        neighbor_info = ""
        for nid in neighbors:
            nf = world_state.get("factions", {}).get(nid, {})
            n_stance = "中立"
            for rkey, rel in relations.items():
                if (rel.get("faction_a") == faction_id and rel.get("faction_b") == nid) or \
                   (rel.get("faction_b") == faction_id and rel.get("faction_a") == nid):
                    n_stance = rel.get("status", "neutral")
                    break
            neighbor_info += f"  {nid}（{nf.get('name', nid)}）：{n_stance} "

        prompt = (
            f"你是{faction_name}的度支尚书，掌管国家财政。\n\n"
            f"【国力概况】\n"
            f"- 国库：{treasury}两\n"
            f"- 存粮：{grain}石（可供{grain_months:.1f}个月）\n"
            f"- 人口：{population}人\n"
            f"- 兵力：{troops}人\n"
            f"- 领地：{tile_count}块\n"
            f"- 民心：{realm_stability}/100\n"
            f"- 季节：{current_season}\n"
            f"- 灾厄指数：{disaster_index}/20\n\n"
            f"【现有设施】\n"
            f"- 粮仓：{'有' if has_granary else '无'}\n"
            f"- 城墙：{'有' if has_wall else '无'}\n"
            f"- 学府：{'有' if has_academy else '无'}\n\n"
            f"【邻国贸易环境】\n{neighbor_info}\n\n"
            f"请制定本季度的经济政策。你必须基于国力做出务实决策。\n\n"
            f"## 决策要点\n"
            f"1. 税率：根据国库/民心/季节调整，范围5%-50%\n"
            f"2. 粮储：四分为军粮/赈灾/贸易/储备（合计100%）\n"
            f"3. 贸易：基于邻国关系选择进出口商品\n"
            f"4. 建设：根据亟需程度排序（粮仓/城墙/驿道/学府/医馆）\n\n"
            f"输出格式（严格JSON，不要额外文字）：\n"
            f'{{"tax_rate": 税率数字(0.05-0.50), '
            f'"grain_allocation": {{"military": 数字, "relief": 数字, "trade": 数字, "reserve": 数字}}, '
            f'"trade": {{"imports": ["商品"], "exports": ["商品"], "partners": ["势力ID"]}}, '
            f'"construction": {{"priority": ["建筑1", "建筑2", "建筑3"], "budget": 预算(两)}}, '
            f'"narrative": "度支尚书口吻的经济策略简述(50字内)"}}'
        )

        system_prompt = (
            f"你是{faction_name}的度支尚书，精通钱粮调度。"
            f"你须根据国力实际做出可行决策：国库空虚时加税但压低幅度，"
            f"粮多时扩大贸易，灾年减税赈灾。不可脱离实际数字。"
            f"当前民心{realm_stability}，若民心低于30不可加税。"
        )

        temperature = (
            self._model_override.get("temperature", 0.5)
            if self._model_override else 0.5
        )

        try:
            raw = await client.chat_strategy(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )
            policy = self._parse_policy_json(raw, faction)
            policy["raw_response"] = raw[:500]
            logger.info(
                f"A10 度支 [{faction_name}]: 税率{policy['tax_rate']:.0%} "
                f"军粮{policy['grain_allocation'].get('military', 0)}% "
                f"建设预算{policy['construction'].get('budget', 0)}两"
            )
            return policy
        except Exception as e:
            logger.warning(f"A10 LLM调用失败 {faction_name}: {e}")
            return self._fallback_policy(faction_id, world_state)

    # ========== 策略应用 ==========

    def apply_tax_policy(self, faction_id: str, world_state: dict, tax_rate: float) -> int:
        """将AI制定的税率应用到势力数据，返回预计税收"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        if not faction:
            return 0

        population = faction.get("population", 0)
        realm_stability = faction.get("realm_stability", 50)

        # 税收计算: 人口 × 税率 × 民心修正
        stability_mod = 0.7 if realm_stability < 30 else (1.1 if realm_stability > 70 else 1.0)
        tax_income = int(population * tax_rate * stability_mod)

        # 加税降民心
        current_rate = faction.get("tax_rate", 0.15)
        if tax_rate > current_rate + 0.05:
            faction["realm_stability"] = max(0, realm_stability - random.randint(2, 5))
        elif tax_rate < current_rate - 0.05:
            faction["realm_stability"] = min(100, realm_stability + random.randint(1, 3))

        faction["tax_rate"] = tax_rate
        faction["treasury"] = faction.get("treasury", 0) + tax_income
        return tax_income

    def apply_grain_policy(self, faction_id: str, world_state: dict, allocation: dict) -> dict:
        """将AI制定的粮储分配策略应用"""
        result = {"military_grain": 0, "relief_grain": 0, "trade_grain": 0, "reserve_grain": 0}
        faction = world_state.get("factions", {}).get(faction_id, {})
        if not faction:
            return result

        total_grain = faction.get("grain", 0)
        military_pct = allocation.get("military", 30) / 100
        relief_pct = allocation.get("relief", 10) / 100
        trade_pct = allocation.get("trade", 20) / 100

        result["military_grain"] = int(total_grain * military_pct)
        result["relief_grain"] = int(total_grain * relief_pct)
        result["trade_grain"] = int(total_grain * trade_pct)
        result["reserve_grain"] = total_grain - result["military_grain"] - result["relief_grain"] - result["trade_grain"]

        # 赈灾提升民心
        if result["relief_grain"] > 100:
            stability_gain = min(5, result["relief_grain"] // 200)
            faction["realm_stability"] = min(100,
                faction.get("realm_stability", 50) + stability_gain)
            faction["grain"] = max(0, faction.get("grain", 0) - result["relief_grain"])

        # 粮食贸易收入（简化为出售贸易粮换取银两）
        if result["trade_grain"] > 100:
            trade_income = result["trade_grain"] // 5  # 每5石换1两
            faction["treasury"] = faction.get("treasury", 0) + trade_income
            faction["grain"] = max(0, faction.get("grain", 0) - result["trade_grain"])
            result["trade_income"] = trade_income

        return result

    def apply_construction_policy(self, faction_id: str, world_state: dict, construction: dict) -> list[str]:
        """将AI制定的建设计划应用"""
        built = []
        faction = world_state.get("factions", {}).get(faction_id, {})
        if not faction:
            return built

        treasury = faction.get("treasury", 0)
        budget = construction.get("budget", 0)
        priorities = construction.get("priority", [])

        if budget <= 0 or treasury < budget:
            budget = min(treasury // 3, 500)  # 降级：用1/3国库但不超过500

        building_costs = {
            "granary": 300, "wall": 500, "road": 200,
            "academy": 400, "hospital": 350,
        }

        buildings = faction.get("buildings", {})
        for bld in priorities:
            if bld not in building_costs:
                continue
            cost = building_costs[bld]
            if budget >= cost:
                buildings[bld] = buildings.get(bld, 0) + 1
                budget -= cost
                built.append(bld)

        if built:
            faction["buildings"] = buildings
            faction["treasury"] = treasury - sum(building_costs.get(b, 0) for b in built)

        return built

    # ========== 解析与降级 ==========

    @staticmethod
    def _parse_policy_json(raw: str, faction: dict) -> dict:
        """从LLM输出中解析经济政策JSON"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*"tax_rate"[\s\S]*\}', raw)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return A10TreasuryAgent._fallback_policy_dict(faction)
            else:
                return A10TreasuryAgent._fallback_policy_dict(faction)

        # 校验边界
        tax_rate = float(data.get("tax_rate", 0.15))
        tax_rate = max(0.05, min(0.50, tax_rate))

        grain_alloc = data.get("grain_allocation", {})
        military = int(grain_alloc.get("military", 30))
        relief = int(grain_alloc.get("relief", 10))
        trade_pct = int(grain_alloc.get("trade", 20))
        # 确保合计100
        total = military + relief + trade_pct
        if total > 100:
            scale = 100 / total
            military = int(military * scale)
            relief = int(relief * scale)
            trade_pct = int(trade_pct * scale)

        trade = data.get("trade", {})
        construction = data.get("construction", {})
        budget = int(construction.get("budget", 0))
        budget = max(0, min(budget, 2000))  # 上限2000两

        return {
            "tax_rate": round(tax_rate, 3),
            "grain_allocation": {
                "military": military,
                "relief": relief,
                "trade": trade_pct,
                "reserve": 100 - military - relief - trade_pct,
            },
            "trade": {
                "imports": trade.get("imports", []),
                "exports": trade.get("exports", []),
                "partners": trade.get("partners", []),
            },
            "construction": {
                "priority": construction.get("priority", ["granary"]),
                "budget": budget,
                "reasoning": construction.get("reasoning", ""),
            },
            "narrative": data.get("narrative", "度支尚书：时局维艰，量入为出。")[:100],
        }

    @staticmethod
    def _fallback_policy(faction_id: str, world_state: dict) -> dict:
        """降级政策（无LLM时用固定公式）"""
        faction = world_state.get("factions", {}).get(faction_id, {})
        d = A10TreasuryAgent._fallback_policy_dict(faction)
        d["_source"] = "fallback_formula"
        return d

    @staticmethod
    def _fallback_policy_dict(faction: dict) -> dict:
        """生成降级经济政策字典"""
        stability = faction.get("realm_stability", 50)
        treasury = faction.get("treasury", 0)
        grain = faction.get("grain", 0)

        # 根据民心决定税率
        if stability < 30:
            tax_rate = 0.10
        elif stability > 70:
            tax_rate = 0.20
        else:
            tax_rate = 0.15

        # 根据粮储决定分配
        if grain > 5000:
            grain_alloc = {"military": 25, "relief": 10, "trade": 30, "reserve": 35}
        elif grain > 2000:
            grain_alloc = {"military": 30, "relief": 15, "trade": 15, "reserve": 40}
        else:
            grain_alloc = {"military": 35, "relief": 20, "trade": 5, "reserve": 40}

        # 根据国库决定建设
        if treasury > 1000:
            construction = {"priority": ["granary", "wall", "road"], "budget": min(800, treasury // 4)}
        elif treasury > 500:
            construction = {"priority": ["granary", "road"], "budget": 300}
        else:
            construction = {"priority": ["granary"], "budget": 0}

        return {
            "tax_rate": tax_rate,
            "grain_allocation": grain_alloc,
            "trade": {"imports": [], "exports": ["grain"], "partners": []},
            "construction": construction,
            "narrative": "度支尚书：据实定策，量入为出。",
            "_source": "fallback",
        }


# ========== 全局单例 ==========
_a10_instance: Optional[A10TreasuryAgent] = None


def get_a10_treasury_agent() -> A10TreasuryAgent:
    global _a10_instance
    if _a10_instance is None:
        _a10_instance = A10TreasuryAgent()
    return _a10_instance
