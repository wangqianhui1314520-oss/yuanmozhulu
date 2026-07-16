"""
3.2 兵种克制引擎
- 六种兵种克制链计算
- 地形-兵种适配
- 军团编制战斗修正
"""
from __future__ import annotations
import random
from typing import Optional
from server.models.generals import (
    UnitType, UNIT_COUNTER_MATRIX, UNIT_TERRAIN_MATRIX,
    UNIT_BASE_STATS, General, Legion, LegionFormation,
)


class UnitCounterEngine:
    """兵种克制与编制战斗引擎"""

    @staticmethod
    def get_counter_bonus(attacker_unit: str, defender_unit: str) -> float:
        """获取兵种克制倍率"""
        matrix = UNIT_COUNTER_MATRIX.get(attacker_unit, {})
        return matrix.get(defender_unit, 1.0)

    @staticmethod
    def get_terrain_bonus(unit_type: str, terrain: str) -> float:
        """获取地形适应倍率"""
        terrain_map = UNIT_TERRAIN_MATRIX.get(unit_type, {})
        return terrain_map.get(terrain, 1.0)

    def calculate_unit_power(
        self,
        unit_type: str,
        count: int,
        terrain: str,
        opponent_unit_type: str = "",
        general: Optional[General] = None,
        formation: Optional[LegionFormation] = None,
        troops_ratio: float = 1.0,
        is_first_strike: bool = False,
    ) -> float:
        """
        计算单位战斗力
        
        公式: 基础战力 × 兵种克制 × 地形适应 × 武将专精 × 阵型修正 × 随机波动
        
        Args:
            troops_ratio: 当前兵力占总兵力的比例（用于 last_stand 判定），默认1.0
            is_first_strike: 是否为首回合（用于 night_raid 判定），默认False
        """
        if count <= 0:
            return 0.0

        stats = UNIT_BASE_STATS.get(unit_type, {"power": 100, "defense": 50})
        base_power = stats["power"] * count / 100.0

        # 兵种克制
        counter_mult = 1.0
        if opponent_unit_type:
            counter_mult = self.get_counter_bonus(unit_type, opponent_unit_type)

        # 地形适应
        terrain_mult = self.get_terrain_bonus(unit_type, terrain)

        # 武将专精加成 (0.8~1.3)
        general_mult = 1.0
        if general:
            prof = general.get_proficiency(UnitType(unit_type))
            general_mult = 0.8 + (prof / 100.0) * 0.5  # 50%专精 → 1.05, 100%专精 → 1.3

        # 武将战术加成
        tactic_mult = 1.0
        if general:
            tactic_mult = self._apply_general_tactics(general, unit_type, terrain, troops_ratio, is_first_strike)

        # 阵型修正
        formation_mult = 1.0
        if formation:
            formation_mult = self._get_formation_mult(formation)

        # 随机波动 0.85~1.15
        random_mult = 0.85 + random.random() * 0.3

        return base_power * counter_mult * terrain_mult * general_mult * tactic_mult * formation_mult * random_mult

    def calculate_formation_power(
        self,
        legion: Legion,
        terrain: str,
        opponent_legion: Optional[Legion] = None,
        general: Optional[General] = None,
        is_first_strike: bool = False,
    ) -> tuple[float, dict]:
        """
        计算整支军团的总战斗力（考虑混编兵种）
        
        Args:
            is_first_strike: 是否为首回合（用于 night_raid 判定），默认False
        
        返回: (总战力, 各兵种战力明细)
        """
        total_power = 0.0
        unit_powers = {}

        opponent_unit = ""
        if opponent_legion:
            opponent_unit = opponent_legion.get_dominant_unit() or ""

        # 计算兵力比例（用于 last_stand 等战术判定）
        # 注：Legion 模型暂无 max_troops 字段，使用 total_troops 字段作为初始兵力参照
        current_troops = sum(legion.unit_composition.values())
        max_troops = getattr(legion, 'max_troops', legion.total_troops)
        if max_troops <= 0:
            max_troops = current_troops
        troops_ratio = current_troops / max_troops if max_troops > 0 else 1.0

        for unit_type_str, count in legion.unit_composition.items():
            if count <= 0:
                continue
            power = self.calculate_unit_power(
                unit_type_str, count, terrain,
                opponent_unit_type=opponent_unit,
                general=general,
                formation=legion.formation,
                troops_ratio=troops_ratio,
                is_first_strike=is_first_strike,
            )
            unit_powers[unit_type_str] = round(power, 1)
            total_power += power

        return round(total_power, 1), unit_powers

    def calculate_mixed_counter(
        self,
        attacker_units: dict[str, int],
        defender_units: dict[str, int],
    ) -> float:
        """
        计算混编部队的综合克制系数
        
        按兵种比例加权计算克制效果
        """
        atk_total = sum(attacker_units.values())
        def_total = sum(defender_units.values())

        if atk_total == 0 or def_total == 0:
            return 1.0

        total_counter = 0.0
        for atk_type, atk_count in attacker_units.items():
            atk_weight = atk_count / atk_total
            for def_type, def_count in defender_units.items():
                def_weight = def_count / def_total
                counter = self.get_counter_bonus(atk_type, def_type)
                total_counter += counter * atk_weight * def_weight

        return round(total_counter, 2)

    @staticmethod
    def _apply_general_tactics(general: General, unit_type: str, terrain: str,
                                troops_ratio: float = 1.0,
                                is_first_strike: bool = False) -> float:
        """应用武将战术特性加成
        
        Args:
            troops_ratio: 当前兵力占总兵力的比例（用于 last_stand 判定），默认1.0
            is_first_strike: 是否为首回合（用于 night_raid 判定），默认False
        """
        mult = 1.0

        for tactic in general.tactics:
            t = tactic.value if hasattr(tactic, 'value') else str(tactic)

            # 骑兵加成
            if t == "shock_cavalry" and unit_type == "cavalry":
                mult += 0.20
            # 伏击加成
            elif t == "ambush_master" and terrain in ("mountain", "forest"):
                mult += 0.30
            # 攻城加成
            elif t == "siege_expert" and unit_type == "siege":
                mult += 0.30
            # 水战加成
            elif t == "naval_raider" and (unit_type == "navy" or terrain in ("water", "coastal", "port")):
                mult += 0.35
            # 山地坚守
            elif t == "mountain_guard" and terrain == "mountain":
                mult += 0.40
            # 水寨固守
            elif t == "river_defender" and terrain in ("water", "coastal", "wetland"):
                mult += 0.35
            # 背水一战：兵力低于30%时触发，攻击+50%、防御+30%
            elif t == "last_stand" and troops_ratio < 0.3:
                mult += 0.80  # 攻+50% + 防+30% = 综合+80%
            # 夜袭：仅首回合触发
            elif t == "night_raid" and is_first_strike:
                mult += 0.40
            # 火攻（攻城/野战）
            elif t == "fire_attack" and (unit_type == "siege" or terrain in ("city",)):
                mult += 0.30
            # 侧翼包抄（野战）
            elif t == "flank_commander" and terrain not in ("water", "mountain"):
                mult += 0.25
            # 固若金汤（全域防御）
            elif t == "fortress_defender":
                mult += 0.30
            # 粮道精通：速度+15%（补给范围加成由 create_legion 处理）
            elif t == "logistics_master":
                mult += 0.15
            # 强行军：速度+30%，攻击-5%
            elif t == "forced_march":
                mult += 0.25  # 速度+30% - 攻击-5% = 综合+25%
            # 就地征募：攻击+5%
            elif t == "field_recruiter":
                mult += 0.05
            # 攻心为上：无直接战力加成（仅士气效果）
            elif t == "psychological_war":
                pass  # 仅影响士气，不直接影响战力
            # 忠勇无双：防御+10%
            elif t == "loyal_commander":
                mult += 0.10
            # 渡河强袭：水域/沿海速度+50%
            elif t == "river_crossing" and terrain in ("water", "coastal"):
                mult += 0.50

        return mult

    @staticmethod
    def _get_formation_mult(formation: LegionFormation) -> float:
        """阵型战斗修正"""
        mapping = {
            LegionFormation.BALANCED: 1.0,
            LegionFormation.AGGRESSIVE: 1.30,   # 锋矢阵
            LegionFormation.DEFENSIVE: 0.70,     # 方圆阵以防守为主
            LegionFormation.MOBILE: 0.90,        # 长蛇阵
            LegionFormation.SIEGE_MODE: 0.80,    # 攻城阵在野战中较弱
            LegionFormation.NAVAL_FORM: 0.70,    # 水阵在陆战中弱
        }
        return mapping.get(formation, 1.0)

    @staticmethod
    def get_formation_defense_mult(formation: LegionFormation) -> float:
        """阵型防御修正"""
        mapping = {
            LegionFormation.BALANCED: 1.0,
            LegionFormation.AGGRESSIVE: 0.85,
            LegionFormation.DEFENSIVE: 1.30,
            LegionFormation.MOBILE: 0.90,
            LegionFormation.SIEGE_MODE: 1.10,
            LegionFormation.NAVAL_FORM: 1.15,
        }
        return mapping.get(formation, 1.0)

    @staticmethod
    def get_formation_speed_mult(formation: LegionFormation) -> float:
        """阵型行军速度修正"""
        mapping = {
            LegionFormation.BALANCED: 1.0,
            LegionFormation.AGGRESSIVE: 1.1,
            LegionFormation.DEFENSIVE: 0.80,
            LegionFormation.MOBILE: 1.30,
            LegionFormation.SIEGE_MODE: 0.60,
            LegionFormation.NAVAL_FORM: 0.70,
        }
        return mapping.get(formation, 1.0)

    def resolve_legion_battle(
        self,
        attacker_legion: Legion,
        defender_legion: Legion,
        terrain: str,
        attacker_general: Optional[General] = None,
        defender_general: Optional[General] = None,
        fortification: int = 0,
        season_mult: float = 1.0,
        is_flanking: bool = False,
        flank_count: int = 0,
    ) -> dict:
        """
        军团级别战斗结算（全面取代旧版兵力比较）
        
        参数:
        - is_flanking: 是否来自侧翼夹击
        - flank_count: 夹击路数(1~3)，每多一路攻方+15%伤害
        """
        # 计算双方战力（首回合 flag 传递给 night_raid 判定）
        atk_power, atk_detail = self.calculate_formation_power(
            attacker_legion, terrain, defender_legion, attacker_general,
            is_first_strike=True,  # resolve_legion_battle 每次调用视为一次独立战斗的首回合
        )
        def_power, def_detail = self.calculate_formation_power(
            defender_legion, terrain, attacker_legion, defender_general,
            is_first_strike=True,
        )

        # 城防加成（v3.3: 应用防御倍率上限，防止叠加过强）
        # M-1: 改为从 combat_utils 导入（消除与 combat_modifiers 的循环依赖）
        from server.core.combat_utils import apply_defense_cap, get_faction_attack_bonus, get_faction_defense_bonus, estimate_unit_type_from_faction
        fort_mult = 1.0 + fortification * 0.2
        
        # 计算地形倍率（从地形适应推算基础防御倍率）
        def_terrain_bonus = 1.0
        if terrain in ("mountain", "pass", "city", "port", "coastal"):
            def_terrain_bonus = 1.2  # 基础防御地形修正
        
        # 势力特殊防御加成
        def_faction_bonus = get_faction_defense_bonus(defender_legion.faction_id)
        
        # 综合防御倍率（含上限）
        defense_mult = apply_defense_cap(def_terrain_bonus * fort_mult + def_faction_bonus)
        def_power *= defense_mult

        # 攻方势力特殊攻击加成
        atk_unit_type = estimate_unit_type_from_faction(attacker_legion.faction_id, terrain)
        atk_faction_bonus = get_faction_attack_bonus(attacker_legion.faction_id, atk_unit_type)
        atk_power *= (1.0 + atk_faction_bonus)

        # 防御阵型加成
        def_formation_mult = self.get_formation_defense_mult(defender_legion.formation)
        def_power *= def_formation_mult

        # 季节修正
        atk_power *= season_mult

        # 夹击加成 (分兵包夹)
        flank_mult = 1.0
        if is_flanking and flank_count > 0:
            flank_mult = 1.0 + flank_count * 0.15  # 每多一路+15%
        atk_power *= flank_mult

        # 决定胜负
        ratio = atk_power / def_power if def_power > 0 else float('inf')

        if ratio > 1.3:
            winner = "attacker"
            atk_loss_rate = 0.10 + random.random() * 0.10  # 10~20%（v4.1: 原15~30%，降低滚雪球门槛）
            def_loss_rate = 0.40 + random.random() * 0.30  # 40~70%
        elif ratio < 0.7:
            winner = "defender"
            atk_loss_rate = 0.40 + random.random() * 0.30
            def_loss_rate = 0.10 + random.random() * 0.15
        else:
            winner = None  # 平局
            atk_loss_rate = 0.20 + random.random() * 0.15  # 20~35%（v4.1: 原25~45%）
            def_loss_rate = 0.25 + random.random() * 0.20

        # 忠勇无双：攻方不败退
        if winner == "defender" and attacker_general and attacker_general.has_tactic("loyal_commander"):
            atk_loss_rate *= 0.6
            # 仍有30%概率翻盘
            if random.random() < 0.30:
                winner = "attacker"
                atk_loss_rate, def_loss_rate = def_loss_rate, atk_loss_rate

        # 计算实际损失
        atk_losses = {}
        def_losses = {}
        atk_remaining = {}
        def_remaining = {}

        for unit_type_str, count in attacker_legion.unit_composition.items():
            loss = max(0, int(count * atk_loss_rate))
            atk_losses[unit_type_str] = loss
            atk_remaining[unit_type_str] = count - loss

        for unit_type_str, count in defender_legion.unit_composition.items():
            loss = max(0, int(count * def_loss_rate))
            def_losses[unit_type_str] = loss
            def_remaining[unit_type_str] = count - loss

        atk_total_loss = sum(atk_losses.values())
        def_total_loss = sum(def_losses.values())

        return {
            "winner": winner,
            "attacker_losses": atk_total_loss,
            "defender_losses": def_total_loss,
            "attacker_loss_detail": atk_losses,
            "defender_loss_detail": def_losses,
            "attacker_remaining": atk_remaining,
            "defender_remaining": def_remaining,
            "attacker_power": atk_power,
            "defender_power": def_power,
            "power_ratio": round(ratio, 2),
            "flank_bonus": flank_mult,
            "counter_mult": self.calculate_mixed_counter(
                attacker_legion.unit_composition,
                defender_legion.unit_composition,
            ),
            "tactics_used": self._list_tactics_used(attacker_general, defender_general),
        }

    @staticmethod
    def _list_tactics_used(atk_general: Optional[General], def_general: Optional[General]) -> list[str]:
        """列出战斗中触发的战术（只列出无条件触发的，有条件的由调用方在结算中按需补充）"""
        tactics = []
        # 无条件战术（fortress_defender, logistics_master, forced_march, field_recruiter, psychological_war, loyal_commander）
        if atk_general:
            for t in atk_general.tactics:
                tv = t.value if hasattr(t, 'value') else str(t)
                if tv in ("fortress_defender", "logistics_master", "forced_march",
                          "field_recruiter", "psychological_war", "loyal_commander"):
                    tactics.append(f"{atk_general.name}施展【{tv}】")
        if def_general:
            for t in def_general.tactics:
                tv = t.value if hasattr(t, 'value') else str(t)
                if tv in ("fortress_defender", "logistics_master", "psychological_war", "loyal_commander"):
                    tactics.append(f"{def_general.name}施展【{tv}】")
        return tactics
