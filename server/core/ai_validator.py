"""
AI校验引擎 - 防崩坏机制与合法性校验（3.2 全链路AI智能体）

职责：
1. 指令合法性校验：资源/地形/权限三重校验
2. 防崩坏机制：数值上限、变化率限制、熔断器
3. AI违规操作拦截：杜绝AI控制非己势力、超支资源
4. 自动修正：对超出阈值的指令自动降级
5. 校验报告生成
"""
from __future__ import annotations
import logging
from typing import Optional
from collections import defaultdict

from server.models.ai_protocol import (
    AICommand, AICommandSet, CommandType,
    SingleValidation, ValidationReport,
    AntiCollapseConfig,
)
from server.models.world_state import WorldState

logger = logging.getLogger("yuanmo.ai.validator")


class AIValidator:
    """
    AI校验引擎 - 防崩坏与合法性校验
    
    校验层级：
    1. 资源校验：银两/粮草/兵力/军械是否充足
    2. 地形校验：操作是否适用于目标地块类型
    3. 权限校验：AI不能操作其他势力的部队/资源
    4. 防崩坏校验：单回合变化率上限、绝对值上限
    5. 频率校验：指令数上限、重复指令冷却
    """

    def __init__(self, world: WorldState, config: Optional[AntiCollapseConfig] = None):
        self.world = world
        self.config = config or AntiCollapseConfig()
        # 本回合已执行计数（防频率滥用）
        self._turn_executed: dict[str, int] = defaultdict(int)
        self._turn_marches: dict[str, int] = defaultdict(int)
        self._turn_recruits: dict[str, int] = defaultdict(int)
        # 连续失败计数（熔断器）
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        # 冷却记录
        self._cooldowns: dict[str, int] = {}

    def reset_turn_counters(self):
        """重置回合计数器"""
        self._turn_executed.clear()
        self._turn_marches.clear()
        self._turn_recruits.clear()

    def validate_command_set(self, command_set: AICommandSet) -> ValidationReport:
        """
        校验AI指令集
        
        对所有指令逐一校验，生成校验报告。
        校验通过的指令才可以执行。
        """
        results = []
        passed_count = 0
        rejected_count = 0
        corrected_count = 0

        for cmd in command_set.commands:
            result = self.validate_single(cmd)
            results.append(result)
            if result.passed:
                passed_count += 1
            else:
                rejected_count += 1
            if result.corrected_params:
                corrected_count += 1

        # 防崩坏检查
        balance_check = self._balance_check(command_set)

        # 熔断器检查
        fid = command_set.faction_id
        if self._consecutive_failures.get(fid, 0) >= self.config.max_consecutive_failures:
            logger.warning(f"势力 {fid} 连续失败 {self._consecutive_failures[fid]} 次，触发熔断")
            balance_check["circuit_breaker"] = "triggered"
            # 拒绝所有指令
            for r in results:
                if r.passed:
                    r.passed = False
                    r.reason = f"熔断器触发（连续失败{self._consecutive_failures[fid]}次）"
                    passed_count -= 1
                    rejected_count += 1
                # Bug #25修复: corrected计数也同步修正
                if r.corrected:
                    corrected_count -= 1

        return ValidationReport(
            total=len(command_set.commands),
            passed=passed_count,
            rejected=rejected_count,
            corrected=corrected_count,
            results=results,
            balance_check=balance_check,
            summary=f"校验完成：通过{passed_count}条，拒绝{rejected_count}条，修正{corrected_count}条",
        )

    def validate_single(self, cmd: AICommand) -> SingleValidation:
        """
        校验单条指令
        
        Returns:
            SingleValidation with passed=True/False
        """
        warnings = []
        fid = cmd.faction_id
        faction = self.world.factions.get(fid)

        # ===== 1. 基础检查 =====
        if not faction or not faction.is_alive:
            return SingleValidation(
                command_id=cmd.command_id,
                command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                passed=False,
                reason=f"势力 {fid} 不存在或已灭亡",
            )

        # ===== 2. 频率检查 =====
        if self._turn_executed.get(fid, 0) >= self.config.max_commands_per_turn:
            return SingleValidation(
                command_id=cmd.command_id,
                command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                passed=False,
                reason=f"势力 {fid} 本回合指令已达上限 ({self.config.max_commands_per_turn})",
            )

        # ===== 3. 冷却检查 =====
        cmd_key = f"{fid}_{cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type)}"
        if cmd_key in self._cooldowns:
            last_round = self._cooldowns[cmd_key]
            current = getattr(self.world, 'current_round', 0)
            if current - last_round < self.config.command_cooldown_rounds:
                return SingleValidation(
                    command_id=cmd.command_id,
                    command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                    passed=False,
                    reason=f"指令冷却中（还需{self.config.command_cooldown_rounds - (current - last_round)}回合）",
                )

        # ===== 4. 资源校验 =====
        resource_check = self._check_resources(cmd, faction)
        if not resource_check["passed"]:
            return SingleValidation(
                command_id=cmd.command_id,
                command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                passed=False,
                reason=resource_check["reason"],
            )

        # ===== 5. 地形校验 =====
        terrain_check = self._check_terrain(cmd)
        if not terrain_check["passed"]:
            return SingleValidation(
                command_id=cmd.command_id,
                command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                passed=False,
                reason=terrain_check["reason"],
            )
        if terrain_check.get("warnings"):
            warnings.extend(terrain_check["warnings"])

        # ===== 6. 权限校验 =====
        permission_check = self._check_permission(cmd, faction)
        if not permission_check["passed"]:
            return SingleValidation(
                command_id=cmd.command_id,
                command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
                passed=False,
                reason=permission_check["reason"],
            )

        # ===== 7. 防崩坏校验（自动修正） =====
        corrected = None
        collapse_check = self._check_anti_collapse(cmd, faction)
        if collapse_check.get("requires_correction"):
            corrected = collapse_check["corrected_params"]
            warnings.append(f"自动修正: {collapse_check['reason']}")

        # ===== 8. 通过 =====
        self._turn_executed[fid] += 1
        if cmd.command_type == CommandType.MARCH:
            self._turn_marches[fid] += 1
        elif cmd.command_type == CommandType.RECRUIT:
            self._turn_recruits[fid] += 1

        # 更新冷却
        self._cooldowns[cmd_key] = getattr(self.world, 'current_round', 0)

        # 重置连续失败
        if fid in self._consecutive_failures:
            self._consecutive_failures[fid] = 0

        return SingleValidation(
            command_id=cmd.command_id,
            command_type=cmd.command_type.value if hasattr(cmd.command_type, 'value') else str(cmd.command_type),
            passed=True,
            reason="",
            warnings=warnings,
            corrected_params=corrected,
            actual_cost=cmd.estimated_cost,
        )

    # ============================================================
    # 子校验
    # ============================================================

    def _check_resources(self, cmd: AICommand, faction) -> dict:
        """资源校验"""
        params = cmd.params
        ct = cmd.command_type

        # 征兵：2-3银/人, 1军械/3人
        if ct == CommandType.RECRUIT:
            count = params.get("count", params.get("amount", 100))
            cost_gold = count * 3
            cost_arms = count // 3
            if faction.treasury < cost_gold:
                return {"passed": False, "reason": f"银两不足（需{cost_gold}，仅{faction.treasury}）"}
            if faction.arms < cost_arms:
                return {"passed": False, "reason": f"军械不足（需{cost_arms}，仅{faction.arms}）"}

        # 买马：5银/匹
        if ct == CommandType.BUY_HORSES:
            count = params.get("count", params.get("amount", 50))
            cost = count * 5
            if faction.treasury < cost:
                return {"passed": False, "reason": f"银两不足（需{cost}，仅{faction.treasury}）"}

        # 行军：需兵力
        if ct == CommandType.MARCH:
            troops = params.get("troops", params.get("count", 0))
            from_tile = params.get("from_tile", params.get("from", ""))
            if from_tile:
                tile = self.world.tiles.get(from_tile) if hasattr(self.world, 'tiles') else None
                if tile and getattr(tile, 'troops', 0) < troops:
                    return {"passed": False, "reason": f"兵力不足（需{troops}，仅{tile.troops}）"}
            elif faction.troops < troops:
                return {"passed": False, "reason": f"总兵力不足（需{troops}，仅{faction.troops}）"}

        # 建造：600-1200银
        if ct == CommandType.BUILD:
            cost = params.get("cost", 800)
            if faction.treasury < cost:
                return {"passed": False, "reason": f"银两不足（需{cost}，仅{faction.treasury}）"}

        # 开发：500银
        if ct == CommandType.DEVELOP:
            if faction.treasury < 500:
                return {"passed": False, "reason": f"银两不足（需500，仅{faction.treasury}）"}

        # 赈灾：人口×1%粮
        if ct == CommandType.RELIEF:
            grain_needed = max(50, faction.population // 100)
            if faction.grain < grain_needed:
                return {"passed": False, "reason": f"粮草不足（需{grain_needed}，仅{faction.grain}）"}

        # 训练：1银/人 + 0.5粮/人
        if ct == CommandType.TRAIN_TROOPS:
            count = params.get("count", params.get("amount", 500))
            if faction.treasury < count or faction.grain < count // 2:
                return {"passed": False, "reason": f"资源不足（需银{count}粮{count//2}）"}

        return {"passed": True}

    def _check_terrain(self, cmd: AICommand) -> dict:
        """地形校验"""
        warnings = []
        params = cmd.params
        ct = cmd.command_type

        tile_id = params.get("tile_id", params.get("tile", params.get("from_tile", params.get("from", ""))))
        if not tile_id:
            return {"passed": True}

        tile = self.world.tiles.get(tile_id) if hasattr(self.world, 'tiles') else None
        if not tile:
            return {"passed": False, "reason": f"地块 {tile_id} 不存在"}

        tt = self._tile_type_str(getattr(tile, 'tile_type', ''))
        tile_owner = getattr(tile, 'faction_id', '')

        # 发展类：不适用于水域/山脉
        if ct in (CommandType.DEVELOP, CommandType.BUILD):
            if tt in ("water", "mountain"):
                return {"passed": False, "reason": f"{tt} 地块不能进行{ct.value if hasattr(ct, 'value') else ct}操作"}
            if tile_owner and tile_owner != cmd.faction_id:
                return {"passed": False, "reason": f"地块{tile_id}不属于{cmd.faction_id}"}

        # 行军：水域需码头
        if ct == CommandType.MARCH:
            to_tile_id = params.get("to_tile", params.get("to", ""))
            to_tile = self.world.tiles.get(to_tile_id) if hasattr(self.world, 'tiles') else None
            if to_tile:
                to_tt = self._tile_type_str(getattr(to_tile, 'tile_type', ''))
                if to_tt == "water":
                    # 检查是否有码头或水军
                    if "dock" not in list(getattr(tile, 'buildings', [])):
                        warnings.append("目标为水域但出发地无码头，水战惩罚")
                if to_tt == "mountain":
                    warnings.append("目标为山地，进攻惩罚")

        return {"passed": True, "warnings": warnings}

    def _check_permission(self, cmd: AICommand, faction) -> dict:
        """权限校验"""
        params = cmd.params
        ct = cmd.command_type
        fid = cmd.faction_id

        # 检查目标是否属于自己
        target_fid = params.get("target_faction", params.get("target", ""))
        tile_id = params.get("tile_id", params.get("from_tile", ""))

        if tile_id:
            tile = self.world.tiles.get(tile_id) if hasattr(self.world, 'tiles') else None
            if tile:
                owner = getattr(tile, 'faction_id', '')
                # 非己方地块的操作限制
                if owner and owner != fid:
                    allowed_on_foreign = [CommandType.MARCH, CommandType.SPY, CommandType.SCOUT, CommandType.PLUNDER, CommandType.AMBUSH]
                    if ct not in allowed_on_foreign:
                        return {"passed": False, "reason": f"不能对非己方地块执行{ct.value if hasattr(ct, 'value') else ct}操作"}

        # 外交操作不能对自己
        if ct == CommandType.DIPLOMACY and target_fid == fid:
            return {"passed": False, "reason": "不能对自己发动外交操作"}

        # 不能操作不存在的势力
        if target_fid and target_fid not in self.world.factions:
            return {"passed": False, "reason": f"目标势力 {target_fid} 不存在"}

        return {"passed": True}

    def _check_anti_collapse(self, cmd: AICommand, faction) -> dict:
        """防崩坏校验（自动修正）"""
        params = cmd.params
        ct = cmd.command_type
        corrected = {}

        # 兵力上限检查
        if ct == CommandType.RECRUIT:
            count = params.get("count", params.get("amount", 100))
            max_possible = min(
                faction.treasury // 3,           # 银两限制
                faction.arms * 3,                 # 军械限制
                faction.population // 4,          # 人口限制（征兵不超过人口25%）
                int(faction.troops * self.config.max_troops_change_pct),  # 变化率限制
                3000,                             # 单次征兵绝对上限
            )
            if count > max_possible:
                corrected["count"] = max_possible
                return {
                    "requires_correction": True,
                    "reason": f"征兵数{count}超出上限，自动修正为{max_possible}",
                    "corrected_params": {"count": max_possible},
                }

        # 银两变化上限
        estimated_cost = cmd.estimated_cost.get("gold", cmd.estimated_cost.get("treasury", 0))
        if estimated_cost > faction.treasury * self.config.max_treasury_change_pct:
            # 降级为建议模式
            return {
                "requires_correction": True,
                "reason": f"单次消耗{estimated_cost}超出银两变化上限，降级为建议",
                "corrected_params": {"auto": False, "recommend_only": True},
            }

        # 行军兵力上限
        if ct == CommandType.MARCH:
            troops = params.get("troops", params.get("count", 0))
            max_troops = min(
                self.config.max_troops_per_tile,
                int(faction.troops * self.config.max_troops_change_pct),
            )
            if troops > max_troops:
                return {
                    "requires_correction": True,
                    "reason": f"行军兵力{troops}超限，修正为{max_troops}",
                    "corrected_params": {"troops": max_troops},
                }

        return {"requires_correction": False}

    def _balance_check(self, command_set: AICommandSet) -> dict:
        """防崩坏全局检查"""
        fid = command_set.faction_id
        faction = self.world.factions.get(fid)
        if not faction:
            return {"passed": True}

        total_cost = 0
        total_recruit = 0
        total_troop_move = 0

        for cmd in command_set.commands:
            total_cost += cmd.estimated_cost.get("gold", cmd.estimated_cost.get("treasury", 0))
            if cmd.command_type == CommandType.RECRUIT:
                total_recruit += cmd.params.get("count", cmd.params.get("amount", 0))
            if cmd.command_type == CommandType.MARCH:
                total_troop_move += cmd.params.get("troops", cmd.params.get("count", 0))

        issues = []

        # 总消耗检查
        if total_cost > faction.treasury * 0.7:
            issues.append(f"总消耗{total_cost}超过国库70%，可能导致财政崩溃")

        # 总征兵检查
        if total_recruit > faction.population * 0.3:
            issues.append(f"总征兵{total_recruit}超过人口30%，可能导致劳动力不足")

        # 总行军检查
        if total_troop_move > faction.troops * 0.8:
            issues.append(f"总行军{total_troop_move}超过总兵力80%，可能导致防线空虚")

        return {
            "passed": len(issues) == 0,
            "warnings": issues,
            "total_estimated_cost": total_cost,
            "faction_treasury": faction.treasury,
            "cost_ratio": round(total_cost / max(1, faction.treasury), 2),
        }

    def record_failure(self, faction_id: str):
        """记录AI指令执行失败"""
        self._consecutive_failures[faction_id] += 1
        logger.warning(f"势力 {faction_id} 指令执行失败，连续失败: {self._consecutive_failures[faction_id]}")

    def record_success(self, faction_id: str):
        """记录AI指令执行成功"""
        self._consecutive_failures[faction_id] = 0

    @staticmethod
    def _tile_type_str(tt) -> str:
        if hasattr(tt, 'value'):
            return tt.value
        return str(tt)
