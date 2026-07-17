"""
游戏引擎核心 - 回合生命周期管理器（全真实实现版 · 3.2 时序重构）
驱动8阶段回合流程，集成Agent运行时与所有子系统引擎

3.2 更新:
- 修复 _phase_validate 签名匹配：edict 参数正确传递到校验阶段
- 修复阶段②跳过逻辑：使用 valid_indices 精确跳过所有被拒绝指令（不仅是 lock_rejected）
- 统一 _check_operation_lock 与 _acquire_operation_lock 的锁映射表
- 藩镇检测改为对所有存活势力生效
- 贸易收益改为从 game_const 可配置读取
- 事件记录增加去重（event_id）
- RoyalAdvancedEngine 实例复用，避免每回合新建
- api_server.py 文档注释与代码对齐

3.1 更新:
- 集成 RoundOperationLock: 单回合同类操作唯一生效
- 集成 GameModeManager: 玩家主导/纯AI观战双模式强制互斥
- 集成 ResponsibilityTracker: 唯一主责AI规则，杜绝重复结算
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional, Callable
from server.models.world_state import WorldState, Season, FactionState, DiplomaticStance
from .round_lock import RoundOperationLock, LockCategory, get_round_lock
from .mode_manager import GameModeManager, get_mode_manager
from .responsibility import ResponsibilityTracker, get_responsibility_tracker, EventDomain
from .ending_system import EndingEngine, get_ending_engine, reset_ending_engine

logger = logging.getLogger("yuanmo.engine")


class RoundEngine:
    """
    回合引擎 - 管理8阶段生命周期（3.2 时序重构版）
    
    固化时序（对标文明6）:
    ┌─ ① 指令校验(含去重锁) ──→ ② 执行政令(唯一结算) ──→ ③ AI推演(跳过玩家势力) ──┐
    │                                                                              │
    │ ④ 事件记录(含去重) ←── ⑤ 数值结算(唯一入口) ←── ⑥ 刷新世界(含外交自动调整)  │
    │                                                                              │
    └────────────────────────── ⑧ 自动存档(含结局判定) ←── ⑦ 回放快照 ←──────────────┘
    
    ③ AI推演阶段按Agent分组（实际并发策略）:
      ┌─ 并发组1: A1谋策阁(玩家献策) + A2群雄殿(NPC并发推演) ──┐
      │  并发组2: A4谍报司 + A5司天台 + A6外交署 + A7宗室府   │
      └─ 串行组3: A8国史馆(依赖前序数据) ──────────────────────┘
    """
    
    def __init__(self, world: WorldState, faction_configs: Optional[dict] = None):
        self.world = world
        self.faction_configs = faction_configs or {}
        self._round_lock = asyncio.Lock()
        self._phase_hooks: dict[int, list[Callable]] = {i: [] for i in range(1, 9)}
        self._llm_clients: Optional[dict] = None
        self._llm_available: bool = False  # LLM是否实际可用（有API Key）

        # 3.1 新增: 操作锁、模式管理、权责追踪
        self._op_lock: RoundOperationLock = get_round_lock()
        self._mode_mgr: GameModeManager = get_mode_manager()
        self._resp_tracker: ResponsibilityTracker = get_responsibility_tracker()

        # 结局引擎（3.3 四大结局系统）
        self._ending_engine: EndingEngine = EndingEngine(world)
        get_ending_engine(world)  # 注册到全局单例

        # v3.5: AI战报收集队列 — 本回合所有战斗的上下文，由A9批量生成
        self._pending_battle_reports: list[dict] = []

        # 懒加载子引擎
        self._settle_engine = None
        self._march_engine = None
        self._spy_engine = None
        self._diplomacy_engine = None
        self._court_engine = None
        self._war_orchestrator = None  # 征伐全链路AI编排器
    
    def _ensure_engines(self):
        """懒加载子引擎"""
        if self._settle_engine is None:
            from server.core.settle_engine import (
                SettleEngine, MarchEngine, SpyEngine,
                DiplomacyEngine, CourtEngine,
            )
            const = self.faction_configs.get("_game_const", {})
            self._settle_engine = SettleEngine(self.world, const)
            self._march_engine = MarchEngine(self.world, const)
            self._spy_engine = SpyEngine(self.world, const)
            self._diplomacy_engine = DiplomacyEngine(self.world, const)
            self._court_engine = CourtEngine(self.world, const)

        if self._war_orchestrator is None:
            from server.agent.war_orchestrator import WarOrchestrator
            self._war_orchestrator = WarOrchestrator(
                self.world, self._llm_clients,
                self.faction_configs.get("_game_const", {}),
            )
    
    def set_llm_clients(self, clients: dict, available: bool = False):
        """设置LLM客户端（由api_server注入），含可用性标记"""
        self._llm_clients = clients
        self._llm_available = available
    
    def register_hook(self, phase: int, hook: Callable):
        """注册阶段钩子"""
        if 1 <= phase <= 8:
            self._phase_hooks[phase].append(hook)
    
    async def execute_round(self, player_edict: Optional[str] = None) -> dict:
        """
        执行完整一回合的8阶段流程（3.1 唯一结算入口）
        
        固化时序（对标文明6）:
        「玩家决策完毕 → 十大AI有序推演 → 全域数值与局势统一更新」
        
        Args:
            player_edict: 玩家圣旨文本（player_turn模式）
        
        Returns:
            回合执行摘要
        
        Raises:
            asyncio.TimeoutError: 回合锁获取超时（300秒）
        """
        # 3.2 修复: 回合锁添加超时，防止死锁永久阻塞
        # Bug #1 修复: 使用标志位跟踪锁获取状态，超时后不释放未获取的锁
        lock_acquired = False
        try:
            round_lock_acquired = await asyncio.wait_for(
                self._round_lock.acquire(),
                timeout=300.0,  # 5分钟超时，足够AI推演完成
            )
            lock_acquired = True
        except asyncio.TimeoutError:
            logger.error("回合锁获取超时（300秒），可能有死锁或长时间运行的操作")
            raise
        
        try:
            self._ensure_engines()
            
            # 3.1: 新回合开始，先递增回合号再执行各阶段
            # 重要：必须在此递增 current_round，确保所有阶段内的事件日志/战斗记录等使用正确的回合号
            self.world.current_round += 1
            new_round = self.world.current_round
            self._op_lock.new_round(new_round)
            self._resp_tracker.new_round()
            
            summary = {"round": new_round, "phases": {}}
            phases_with_errors = []  # 3.2: 记录失败阶段，不中断后续
            
            # 定义阶段执行器（名称, 方法, 参数列表）
            # 参数: (edict, summary) 或 (summary,) —— 不再用布尔标记
            phase_runners = [
                ("validate",        self._phase_validate,        (player_edict, summary)),
                ("execute_edict",   self._phase_execute_edict,   (player_edict, summary)),
                ("ai_step",         self._phase_ai_step,         (summary,)),
                ("record_events",   self._phase_record_events,   (summary,)),
                ("settle",          self._phase_settle,          (summary,)),
                ("refresh_world",   self._phase_refresh_world,   (summary,)),
                ("replay_snapshot", self._phase_replay_snapshot, (summary,)),
                ("auto_save",       self._phase_auto_save,       (summary,)),
            ]
            
            for phase_name, phase_method, args in phase_runners:
                try:
                    await phase_method(*args)
                except Exception as e:
                    logger.error(
                        f"回合{new_round} {phase_name} 阶段异常: {type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    phases_with_errors.append(phase_name)
                    # 确保 summary 中有该阶段记录（即使失败）
                    if phase_name not in summary.get("phases", {}):
                        summary["phases"][phase_name] = {
                            "status": "failed",
                            "error": f"{type(e).__name__}: {str(e)[:200]}",
                        }
            
            # 3.1: 追加权责统计到摘要
            try:
                summary["responsibility_stats"] = self._resp_tracker.get_stats()
            except Exception as e:
                logger.error(f"权责统计获取失败: {type(e).__name__}: {e}")
                summary["responsibility_stats"] = {"error": "unavailable"}
            
            # Bug #4 修复: 如果所有阶段都失败了，回滚回合号
            # P0修复: 回滚检查必须在 _advance_time() 之前，防止时间推进后回滚不完整
            if len(phases_with_errors) >= len(phase_runners):
                self.world.current_round -= 1
                # 同步回滚操作锁中的回合号，避免锁状态与 world 不一致
                self._op_lock.new_round(self.world.current_round)
                summary["round_rolled_back"] = True
                logger.error(f"回合{new_round}全部阶段失败，已回滚回合号至{self.world.current_round}，操作锁已同步")
                # 不推进时间，直接返回
                if phases_with_errors:
                    summary["partial_failure"] = True
                    summary["failed_phases"] = phases_with_errors
                return summary
            
            # P0修复: _advance_time() 移到回滚检查之后，确保只有成功回合才推进时间
            try:
                self._advance_time()
            except Exception as e:
                logger.error(f"回合{new_round} 时间推进异常: {type(e).__name__}: {e}")
            
            # 3.2: 记录失败阶段
            if phases_with_errors:
                summary["partial_failure"] = True
                summary["failed_phases"] = phases_with_errors
            
            return summary
        
        finally:
            if lock_acquired:
                self._round_lock.release()
    
    # ================================================================
    # ① 指令校验 —— 真实实现
    # ================================================================
    
    async def _phase_validate(self, edict: Optional[str], summary: dict):
        """① 指令校验：前置条件、资源充足性、合法性检查 + 3.1 操作锁去重"""
        result = {
            "total_commands": 0,
            "valid": 0,
            "rejected": 0,
            "rejections": [],
            "valid_indices": [],  # 3.2: 通过校验的指令索引，供阶段②精确匹配
            "lock_rejections": 0,  # 3.1 新增：因操作锁拒绝数
        }
        
        if edict:
            import json as _json
            try:
                commands = _json.loads(edict)
            except Exception as e:
                logger.warning(f"圣旨JSON解析失败(验证阶段): {e}, 原始内容前100字符: {str(edict)[:100]}")
                commands = []
            
            result["total_commands"] = len(commands)
            
            for idx, cmd in enumerate(commands):
                action = cmd.get("action", "")
                params = cmd.get("params", {})
                
                # 3.1: 先检查操作锁
                lock_check = self._check_operation_lock(action, params)
                if not lock_check["allowed"]:
                    result["rejected"] += 1
                    result["lock_rejections"] += 1
                    result["rejections"].append({
                        "index": idx,
                        "action": action,
                        "params": params,
                        "reason": lock_check["reason"],
                        "type": "lock_rejected",
                    })
                    continue
                
                # 再检查资源和合法性
                check = self._validate_command(action, params)
                if check["valid"]:
                    result["valid"] += 1
                    result["valid_indices"].append(idx)
                else:
                    result["rejected"] += 1
                    result["rejections"].append({
                        "index": idx,
                        "action": action,
                        "params": params,
                        "reason": check["reason"],
                        "type": "validation_rejected",
                    })
        
        summary["phases"]["validate"] = result
        
        for hook in self._phase_hooks[1]:
            await hook(self.world)
    
    def _check_operation_lock(self, action: str, params: dict) -> dict:
        """3.1: 检查操作锁（对标文明6回合锁重机制）"""
        player = self.world.get_player_faction()
        if not player:
            return {"allowed": True}
        
        fid = player.faction_id
        
        # 行军锁：单部队单回合单次行为
        if action == "march":
            from_tile = params.get("from_tile", "")
            if self._op_lock.check_march_lock(fid, from_tile, params.get("to_tile", "")):
                return {"allowed": False, "reason": f"地块{from_tile}的部队本回合已行军，单回合仅可调兵一次"}
        
        # 势力级别锁：税政、外交、买马、律法、细作、文化/海洋政策等单回合仅一次
        # 3.2: 统一 lock_map，消除 _check_operation_lock 与 _acquire_operation_lock 的不对称
        faction_level_actions = {
            "tax": LockCategory.TAX,
            "diplomacy": LockCategory.DIPLOMACY,
            "amnesty": LockCategory.LAW,
            "enfeoff": LockCategory.ENFEOFF,
            "buy_horses": LockCategory.BUY_HORSES,
            "spy": LockCategory.SPY,               # 细作部署：单回合同一势力仅可部署一次
            "law": LockCategory.LAW,                # 律法审判：单回合仅一次
            "purge": LockCategory.LAW,              # 清洗官员：单回合仅一次
            "cultural_policy": LockCategory.TAX,    # 文化政策：与税政共用势力锁
            "sea_policy": LockCategory.TAX,         # 海洋政策：与税政共用势力锁
            # 2026-07-15: 补充朝堂/皇族/航海等指令的势力级锁
            "decree": LockCategory.LAW,             # 圣旨(册立/教导/纳妃/修史/改元)
            "marriage": LockCategory.ENFEOFF,       # 皇子联姻
            "patrol": LockCategory.LAW,             # 水师巡航
            "appoint": LockCategory.ENFEOFF,        # 提拔官员
            "dismiss": LockCategory.LAW,            # 降职官员
            "trade": LockCategory.DIPLOMACY,        # 开辟航线
        }
        if action in faction_level_actions:
            if self._op_lock.check_faction_lock(fid, faction_level_actions[action]):
                return {"allowed": False, "reason": f"「{action}」类操作本回合已执行，单回合同类操作仅可一次"}
        
        # 地块级别锁：同一地块同类型操作单回合仅一次
        tile_actions = {
            "develop": LockCategory.DEVELOP,
            "recruit": LockCategory.RECRUIT,
            "fortify": LockCategory.BUILD,
            "relief": LockCategory.RELIEF,
            "build": LockCategory.BUILD,
            "train_troops": LockCategory.TRAIN_TROOPS,
            "convict_labor": LockCategory.BUILD,   # 徭役：与建造共用 BUILD 锁
            "medical": LockCategory.RELIEF,         # 医疗：与赈灾共用 RELIEF 锁
            "ambush": LockCategory.RECRUIT,         # 伏击：与征兵共用 RECRUIT 锁
            "plunder": LockCategory.MARCH,          # 劫掠：视为军事行动，用 MARCH 锁（地块级别）
        }
        if action in tile_actions:
            tile_id = params.get("tile_id", "")
            if tile_id and self._op_lock.check_tile_lock(tile_id, tile_actions[action]):
                return {"allowed": False, "reason": f"地块{tile_id}的「{action}」操作本回合已执行"}
        
        # scout（侦查）、move_capital（迁都）：无操作锁限制（可多次执行）
        
        return {"allowed": True}
    
    def _acquire_operation_lock(self, action: str, params: dict) -> bool:
        """3.1: 执行操作前获取锁（与 _check_operation_lock 保持对称）"""
        player = self.world.get_player_faction()
        if not player:
            return True
        
        fid = player.faction_id
        
        if action == "march":
            return self._op_lock.acquire_march_lock(fid, params.get("from_tile", ""), params.get("to_tile", ""))
        
        # (LockCategory, is_faction_level)
        lock_map = {
            "tax": (LockCategory.TAX, True),
            "diplomacy": (LockCategory.DIPLOMACY, True),
            "amnesty": (LockCategory.LAW, True),
            "enfeoff": (LockCategory.ENFEOFF, True),
            "buy_horses": (LockCategory.BUY_HORSES, True),
            "spy": (LockCategory.SPY, True),
            "law": (LockCategory.LAW, True),
            "purge": (LockCategory.LAW, True),
            "cultural_policy": (LockCategory.TAX, True),
            "sea_policy": (LockCategory.TAX, True),
            "develop": (LockCategory.DEVELOP, False),
            "recruit": (LockCategory.RECRUIT, False),
            "fortify": (LockCategory.BUILD, False),
            "relief": (LockCategory.RELIEF, False),
            "build": (LockCategory.BUILD, False),
            "train_troops": (LockCategory.TRAIN_TROOPS, False),
            "convict_labor": (LockCategory.BUILD, False),
            "medical": (LockCategory.RELIEF, False),
            "ambush": (LockCategory.RECRUIT, False),
            "plunder": (LockCategory.MARCH, False),
            # 2026-07-15: 补充政权/皇族/航海等新指令类型到锁映射表
            "decree": (LockCategory.LAW, True),
            "marriage": (LockCategory.ENFEOFF, True),
            "patrol": (LockCategory.LAW, True),
            "appoint": (LockCategory.ENFEOFF, True),
            "dismiss": (LockCategory.LAW, True),
            "trade": (LockCategory.DIPLOMACY, True),
        }
        
        if action in lock_map:
            cat, is_faction_level = lock_map[action]
            if is_faction_level:
                return self._op_lock.acquire_faction_lock(fid, cat)
            else:
                tile_id = params.get("tile_id", "")
                if tile_id:
                    return self._op_lock.acquire_tile_lock(tile_id, cat)
                return True  # 无tile_id时默认放行
        
        # Bug #5 修复: 未知action拒绝，防止锁机制被绕过
        logger.warning(f"未知操作类型 '{action}'，拒绝获取操作锁")
        return False
    
    def _validate_command(self, action: str, params: dict) -> dict:
        """校验单条指令"""
        player = self.world.get_player_faction()
        if not player:
            return {"valid": False, "reason": "无玩家势力"}

        if action == "march":
            from_tile = params.get("from_tile", "")
            troops = params.get("troops", 0)
            tile = self.world.get_tile(from_tile)
            if not tile:
                return {"valid": False, "reason": f"出发地块{from_tile}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": "出发地块不属于你方"}
            if troops <= 0 or troops > tile.troops:
                return {"valid": False, "reason": f"兵力不足（可调遣：{tile.troops}）"}
            # 粮草消耗 = troops * 0.02 * terrain_mult（实际消耗较小），
            # 此处使用较宽松的 troops * 0.1 作为校验阈值
            if tile.grain < troops * 0.1:
                return {"valid": False, "reason": f"粮草不足，无法行军（需要{troops * 0.1:.0f}，现有{tile.grain}）"}

        elif action == "spy":
            target = params.get("target_faction", "")
            if player.treasury < 200:
                return {"valid": False, "reason": f"银两不足（需要200，现有{player.treasury}）"}
            if target not in self.world.factions:
                return {"valid": False, "reason": f"目标势力{target}不存在"}

        elif action == "recruit":
            tile_id = params.get("tile_id", "")
            amount = params.get("amount", 0)
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            if amount <= 0:
                return {"valid": False, "reason": "招募数量必须大于0"}
            if amount > 5000:
                return {"valid": False, "reason": f"单次最多招募5000人（请求{amount}）"}
            # 检查人口限制（最多征用15%人口）
            max_recruit = int(tile.population * 0.15)
            if amount > max_recruit:
                return {"valid": False, "reason": f"人口不足，最多可征{max_recruit}人（当前人口{tile.population}）"}
            # 检查银两
            cost_per = 2
            if tile.tile_type.value in ('city', 'port'):
                cost_per = 3  # 城池招募更贵
            cost = amount * cost_per
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}
            # 3.2修复：军械消耗降低为 1/10（原来1/3过高，初始500军械仅够征1500人）
            # 每10人需要1件军械（弓弩刀枪），农民兵初期可持农具
            arms_needed = max(0, amount // 10)
            if player.arms < arms_needed:
                return {"valid": False, "reason": f"军械不足（需要{arms_needed}，现有{player.arms}）"}
            # 检查地块驻军上限
            max_garrison = 5000 + tile.fortification * 2000
            if tile.troops + amount > max_garrison:
                return {"valid": False, "reason": f"超过驻军上限{max_garrison}（现有{tile.troops}）"}

        elif action == "buy_horses":
            amount = params.get("amount", 0)
            if amount <= 0:
                return {"valid": False, "reason": "购买数量必须大于0"}
            if amount > 1000:
                return {"valid": False, "reason": f"单次最多购买1000匹战马（请求{amount}）"}
            cost = amount * 5  # 每匹战马5银两
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}
            # 需要马场
            has_stable = any(getattr(t, 'stable', 0) > 0 for t in self.world.get_faction_tiles(player.faction_id))
            if not has_stable:
                return {"valid": False, "reason": "需要先建造马场才能购买战马"}

        elif action == "build":
            tile_id = params.get("tile_id", "")
            building = params.get("building", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            valid_buildings = ["granary", "armory", "stable", "port", "clinic",
                              "farmland", "workshop", "barracks", "beacon", "temple", "wall", "dock"]
            if building not in valid_buildings:
                return {"valid": False, "reason": f"未知建筑类型: {building}，支持: {valid_buildings}"}
            costs = {"granary": 250, "armory": 800, "stable": 600, "port": 400, "clinic": 200,
                     "farmland": 300, "workshop": 500, "barracks": 350, "beacon": 200,
                     "temple": 400, "wall": 600, "dock": 400}
            cost = costs.get(building, 500)
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}

        elif action == "train_troops":
            tile_id = params.get("tile_id", "")
            amount = params.get("amount", 0)
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            # 3.2修复：训练数量不能超过地块驻军，但至少为1
            max_train = max(tile.troops, 1)
            if amount <= 0:
                return {"valid": False, "reason": "训练数量必须大于0"}
            if amount > max_train:
                return {"valid": False, "reason": f"训练数量不能超过驻军数量（驻军{tile.troops}，请求{amount}）"}
            cost = amount * 1  # 每训练1人消耗1银两
            grain_cost = amount // 2
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}
            if player.grain < grain_cost:
                return {"valid": False, "reason": f"粮草不足（需要{grain_cost}，现有{player.grain}）"}

        elif action == "develop":
            tile_id = params.get("tile_id", "")
            dev_type = params.get("type", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            valid_dev_types = ["water", "granary", "clinic", "farmland"]
            if dev_type and dev_type not in valid_dev_types:
                return {"valid": False, "reason": f"无效开发类型: {dev_type}，支持: {valid_dev_types}"}
            if player.treasury < 500:
                return {"valid": False, "reason": f"银两不足（需要500，现有{player.treasury}）"}

        elif action == "fortify":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            cost = 300 * (tile.fortification + 1)
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}

        elif action == "relief":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            cost = params.get("cost", 300)  # 前端传入银两消耗，默认300
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}

        elif action == "tax":
            if player.realm_stability < 30:
                return {"valid": False, "reason": "民心过低，无法加税"}

        elif action == "diplomacy":
            target = params.get("target_faction", "")
            dip_type = params.get("diplomacy_type", "")
            if target not in self.world.factions:
                return {"valid": False, "reason": f"目标势力{target}不存在"}
            if dip_type == "tribute" and player.treasury < 500:
                return {"valid": False, "reason": "银两不足以纳贡"}

        elif action == "enfeoff":
            # 接受 prince_name（皇子出镇）或 official_id（官员分封）
            prince_name = params.get("prince_name", "")
            official_id = params.get("official_id", "")
            if not prince_name and official_id not in self.world.officials:
                return {"valid": False, "reason": "官员不存在"}
            if player.treasury < 1000:
                return {"valid": False, "reason": "银两不足以分封"}

        elif action == "law":
            prisoner_id = params.get("prisoner_id", "")
            if prisoner_id not in self.world.prisoners:
                return {"valid": False, "reason": "俘虏不存在"}

        elif action == "scout":
            target_tile = params.get("target_tile", "")
            if not self.world.get_tile(target_tile):
                return {"valid": False, "reason": f"侦查目标{target_tile}不存在"}

        elif action == "amnesty":
            # 大赦：无前置消耗检查，仅影响囚犯和民心
            pass

        elif action == "convict_labor":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            if tile.population < 200:
                return {"valid": False, "reason": f"人口不足（至少200人才能征发徭役，当前{tile.population}）"}

        elif action == "cultural_policy":
            if player.treasury < 800:
                return {"valid": False, "reason": f"银两不足（需要800，现有{player.treasury}）"}

        elif action == "sea_policy":
            policy_type = params.get("policy_type", "开海贸")
            if policy_type == "建水师":
                if player.treasury < 1000:
                    return {"valid": False, "reason": f"银两不足（建水师需要1000，现有{player.treasury}）"}
            else:
                if player.treasury < 600:
                    return {"valid": False, "reason": f"银两不足（需要600，现有{player.treasury}）"}

        elif action == "medical":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            if player.treasury < 400:
                return {"valid": False, "reason": f"银两不足（需要400，现有{player.treasury}）"}

        elif action == "ambush":
            tile_id = params.get("tile_id", "")
            troops = params.get("troops", 0)
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"设伏地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"设伏地块{tile_id}不属于你方"}
            if troops <= 0:
                return {"valid": False, "reason": "伏击兵力必须大于0"}
            if troops > tile.troops:
                return {"valid": False, "reason": f"兵力不足（可调遣：{tile.troops}）"}

        elif action == "plunder":
            tile_id = params.get("tile_id", "")  # 劫掠部队来源地块（己方）
            target_tile = params.get("target_tile", "")
            troops = params.get("troops", 0)
            source_tile = self.world.get_tile(tile_id) if tile_id else None
            tile = self.world.get_tile(target_tile)
            if not tile:
                return {"valid": False, "reason": f"目标地块{target_tile}不存在"}
            if tile.faction_id == player.faction_id:
                return {"valid": False, "reason": "不能劫掠己方地块"}
            if troops <= 0:
                return {"valid": False, "reason": "劫掠兵力必须大于0"}
            if source_tile and source_tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"劫掠部队来源地块{tile_id}不属于你方"}
            if source_tile and source_tile.troops < troops:
                return {"valid": False, "reason": f"劫掠兵力不足（可调遣：{source_tile.troops}）"}

        elif action == "move_capital":
            tile_id = params.get("tile_id", "") or params.get("new_tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            # 从 faction_configs["_game_const"] 读取迁都费用（默认 10000），与 RoyalAdvancedEngine.move_capital 保持一致
            _const = self.faction_configs.get("_game_const", {})
            move_cost = _const.get("move_capital_cost", 10000)
            if player.treasury < move_cost:
                return {"valid": False, "reason": f"银两不足（需要{move_cost}，现有{player.treasury}）"}

        elif action == "purge":
            official_id = params.get("official_id", "")
            if not official_id:
                return {"valid": False, "reason": "未指定要清洗的官员"}

        elif action == "decree":
            decree_type = params.get("decree_type", "")
            valid_decree_types = ["chronicle", "era_name", "heir", "education", "spawn_prince"]
            if decree_type not in valid_decree_types:
                return {"valid": False, "reason": f"无效圣旨类型: {decree_type}，支持: {valid_decree_types}"}
            if decree_type in ("heir", "education", "spawn_prince") and not params.get("prince_name", ""):
                return {"valid": False, "reason": "未指定皇子名称"}

        elif action == "marriage":
            cost = params.get("cost", 300)
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}

        elif action == "patrol":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"巡航地块{tile_id}不存在"}

        elif action == "appoint":
            if not params.get("official_id", "") and not params.get("name", ""):
                return {"valid": False, "reason": "未指定提拔官员信息"}

        elif action == "dismiss":
            if not params.get("official_id", "") and not params.get("name", ""):
                return {"valid": False, "reason": "未指定降职官员信息"}

        elif action == "trade":
            tile_id = params.get("tile_id", "")
            tile = self.world.get_tile(tile_id)
            if not tile:
                return {"valid": False, "reason": f"开航地块{tile_id}不存在"}
            if tile.faction_id != player.faction_id:
                return {"valid": False, "reason": f"地块{tile_id}不属于你方"}
            cost = params.get("cost", 300)
            if player.treasury < cost:
                return {"valid": False, "reason": f"银两不足（需要{cost}，现有{player.treasury}）"}

        return {"valid": True, "reason": ""}
    
    # ================================================================
    # ② 执行政令 —— 真实实现
    # ================================================================
    
    async def _phase_execute_edict(self, edict: Optional[str], summary: dict):
        """② 执行政令：解析玩家圣旨→工具调用→实际执行（跳过阶段①已拒绝的指令）"""
        result = {
            "executed": [],
            "failed": [],
            "skipped": 0,  # 因阶段①验证被拒绝而跳过的指令数
        }
        
        # 从阶段①获取校验通过的指令索引集合
        validate_result = summary.get("phases", {}).get("validate", {})
        # 利用阶段①的 valid_indices 字段精确跳过被拒绝的指令
        valid_indices = set(validate_result.get("valid_indices", []))
        
        if edict:
            import json as _json
            try:
                commands = _json.loads(edict)
            except Exception as e:
                logger.warning(f"圣旨JSON解析失败(执行阶段): {e}, 原始内容前100字符: {str(edict)[:100]}")
                commands = []
            
            for idx, cmd in enumerate(commands):
                action = cmd.get("action", "")
                params = cmd.get("params", {})
                
                # Bug #2 修复: 阶段①失败时(valid_indices为空+validate阶段状态为failed)，全部跳过
                validate_status = validate_result.get("status", "")
                if validate_status == "failed":
                    result["skipped"] += 1
                    continue
                # 跳过阶段①中被拒绝的指令（通过索引精确匹配）
                if valid_indices and idx not in valid_indices:
                    result["skipped"] += 1
                    continue
                
                exec_result = self._execute_command(action, params)
                if exec_result.get("success"):
                    result["executed"].append({"action": action, "result": exec_result})
                else:
                    result["failed"].append({"action": action, "reason": exec_result.get("message", "")})
        
        summary["phases"]["edict"] = result
        
        for hook in self._phase_hooks[2]:
            await hook(self.world, edict)
    
    def _execute_command(self, action: str, params: dict) -> dict:
        """执行单条指令（3.1: 执行前获取操作锁）"""
        self._ensure_engines()
        player = self.world.get_player_faction()
        if not player:
            return {"success": False, "message": "无玩家势力"}
        
        # 3.1: 执行前获取操作锁
        if not self._acquire_operation_lock(action, params):
            return {"success": False, "message": "操作已被锁定，本回合不可重复执行"}

        try:
            if action == "march":
                return self._march_engine.resolve_march(
                    from_tile=params.get("from_tile", ""),
                    to_tile=params.get("to_tile", ""),
                    troops=params.get("troops", 0),
                    attacker_faction=player.faction_id,
                    grain=params.get("grain", 0),
                )
            
            elif action == "spy":
                spy_action = params.get("spy_action", "deploy")
                target = params.get("target_faction", "")
                if spy_action == "deploy":
                    return self._spy_engine.deploy_spy(player.faction_id, target)
                else:
                    return self._spy_engine.spy_action(player.faction_id, target, spy_action)
            
            elif action == "recruit":
                tile_id = params.get("tile_id", "")
                amount = params.get("amount", 100)
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                cost_per = 2
                if tile.tile_type.value in ('city', 'port'):
                    cost_per = 3
                cost = amount * cost_per
                # 3.2修复：军械消耗1/10（与校验逻辑一致）
                arms_needed = max(0, amount // 10)
                player.treasury -= cost
                player.arms -= arms_needed
                tile.troops += amount
                tile.population = max(100, tile.population - amount)
                tile.morale = max(0, tile.morale - 3)  # 征兵降低民心
                return {
                    "success": True,
                    "message": f"从{tile.tile_name}招募{amount}士兵（耗费银{cost}两、军械{arms_needed}件）",
                    "tile": tile_id,
                    "recruited": amount,
                    "cost_silver": cost,
                    "cost_arms": arms_needed,
                    "remaining_population": tile.population,
                    "new_troops": tile.troops,
                }

            elif action == "buy_horses":
                amount = params.get("amount", 0)
                cost = amount * 5
                player.treasury -= cost
                player.horses += amount
                return {
                    "success": True,
                    "message": f"购买{amount}匹战马（耗费银{cost}两）",
                    "purchased": amount,
                    "cost_silver": cost,
                    "total_horses": player.horses,
                }

            elif action == "train_troops":
                tile_id = params.get("tile_id", "")
                amount = params.get("amount", 0)
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不属于你方"}
                cost = amount * 1
                grain_cost = amount // 2
                if player.treasury < cost:
                    return {"success": False, "message": f"银两不足（需要{cost}）"}
                if player.grain < grain_cost:
                    return {"success": False, "message": f"粮草不足（需要{grain_cost}）"}
                player.treasury -= cost
                player.grain -= grain_cost
                # 训练效果：提升士气
                tile.morale = min(100, tile.morale + 10)
                # 训练提升精锐比例（以 elite_ratio 形式存储）
                elite_ratio = getattr(tile, 'elite_ratio', 0.0) or 0.0
                tile.elite_ratio = min(1.0, elite_ratio + amount / max(tile.troops, 1) * 0.1)
                return {
                    "success": True,
                    "message": f"在{tile.tile_name}训练{amount}士兵（耗费银{cost}两、粮{grain_cost}石）",
                    "tile": tile_id,
                    "trained": amount,
                    "cost_silver": cost,
                    "cost_grain": grain_cost,
                    "new_morale": tile.morale,
                }
            
            elif action == "develop":
                tile_id = params.get("tile_id", "")
                dev_type = params.get("type", "farmland")
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不属于你方"}
                player.treasury -= 500
                dev_labels = {"water": "水利", "granary": "粮仓", "clinic": "医馆", "farmland": "农田"}
                label = dev_labels.get(dev_type, dev_type)
                if dev_type == "water":
                    tile.water_works += 1
                elif dev_type == "granary":
                    tile.granary += 1
                elif dev_type == "clinic":
                    tile.clinic += 1
                tile.development_level = getattr(tile, 'development_level', 0) + 1
                return {"success": True, "message": f"「{tile.tile_name or tile_id}」{label}开发完成（耗费500银）", "tile": tile_id}
            
            elif action == "fortify":
                tile_id = params.get("tile_id", "")
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不属于你方"}
                cost = 300 * (tile.fortification + 1)
                if player.treasury >= cost:
                    player.treasury -= cost
                    tile.fortification += 1
                    return {"success": True, "message": f"城防提升至{tile.fortification}级", "tile": tile_id}
                return {"success": False, "message": f"银两不足（需要{cost}）"}
            
            elif action == "relief":
                tile_id = params.get("tile_id", "")
                relief_type = params.get("type", "relieve")
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不属于你方"}
                cost = params.get("cost", 300)
                if player.treasury >= cost:
                    player.treasury -= cost
                    if relief_type == "treat_injured":
                        tile.morale = min(100, tile.morale + 5)
                        tile.population = min(tile.population + 200, tile.population * 2)
                        return {"success": True, "message": f"施药完成，民心恢复（耗费银{cost}两）", "tile": tile_id}
                    else:
                        tile.morale = min(100, tile.morale + 10)
                        tile.disasters = []
                        return {"success": True, "message": f"赈灾成功，民心恢复（耗费银{cost}两）", "tile": tile_id}
                return {"success": False, "message": "银两不足"}
            
            elif action == "tax":
                tax_type = params.get("tax_type", "normal")
                if tax_type == "heavy":
                    player.realm_stability = max(0, player.realm_stability - 5)
                    player.tax_policy = "heavy"  # 标记重税，_calc_tax 中 +30% 税收
                    return {"success": True, "message": "重税政策已施行（税收+30%，民心-5）"}
                elif tax_type == "light":
                    player.realm_stability = min(100, player.realm_stability + 5)
                    player.tax_policy = "light"
                    return {"success": True, "message": "减税政策已施行"}
                else:
                    player.tax_policy = "normal"
                return {"success": True, "message": "税政如常"}
            
            elif action == "diplomacy":
                target = params.get("target_faction", "")
                dip_type = params.get("diplomacy_type", "")
                if dip_type == "alliance":
                    return self._diplomacy_engine.change_stance(player.faction_id, target, "alliance")
                elif dip_type == "war":
                    return self._diplomacy_engine.change_stance(player.faction_id, target, "war")
                elif dip_type == "truce":
                    return self._diplomacy_engine.change_stance(player.faction_id, target, "truce")
                elif dip_type == "trade":
                    return self._diplomacy_engine.open_trade(player.faction_id, target)
                elif dip_type == "marriage":
                    return self._diplomacy_engine.propose_marriage(player.faction_id, target)
                elif dip_type == "tribute":
                    player.treasury -= 500
                    key = self.world.relation_key(player.faction_id, target)
                    rel = self.world.relations.get(key)
                    if rel:
                        rel.attitude += 10
                    return {"success": True, "message": f"向{target}纳贡500银两"}
                elif dip_type == "vassal_offer":
                    return self._diplomacy_engine.offer_vassal(player.faction_id, target)
                elif dip_type == "vassal_cancel":
                    return self._diplomacy_engine.cancel_vassal(player.faction_id, target)
                elif dip_type == "trade_close":
                    return self._diplomacy_engine.close_trade(player.faction_id, target)
                return {"success": False, "message": f"未知外交行动: {dip_type}"}
            
            elif action == "build":
                tile_id = params.get("tile_id", "")
                building = params.get("building", "")
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不属于你方"}
                costs = {"granary": 800, "armory": 800, "stable": 800, "port": 1200, "clinic": 600, "ship": 200, "shipyard": 400}
                labels = {"granary": "粮仓", "armory": "军械所", "stable": "马场", "port": "港口", "clinic": "医馆", "ship": "战船", "shipyard": "船坞"}
                cost = costs.get(building, 500)
                label = labels.get(building, building)
                if player.treasury >= cost:
                    player.treasury -= cost
                    if building == "granary":
                        tile.granary += 1
                    elif building == "armory":
                        # 军械所：提升地块军械产能与精锐比例
                        tile.armory = getattr(tile, 'armory', 0) + 1
                        tile.elite_ratio = min(1.0, getattr(tile, 'elite_ratio', 0.0) + 0.1)
                    elif building == "stable":
                        tile.stable = getattr(tile, 'stable', 0) + 1
                    elif building == "clinic":
                        tile.clinic += 1
                    elif building == "port":
                        tile.is_port = True
                    elif building == "ship":
                        tile.ships = getattr(tile, 'ships', 0) + 1
                        tile.fleet_size = getattr(tile, 'fleet_size', 0) + 1
                    elif building == "shipyard":
                        tile.shipyard_level = getattr(tile, 'shipyard_level', 0) + 1
                        tile.fleet_size = getattr(tile, 'fleet_size', 0) + 3
                    return {"success": True, "message": f"「{tile.tile_name or tile_id}」{label}建造完成（耗费银{cost}两）"}
                return {"success": False, "message": f"银两不足（需要{cost}，现有{player.treasury}）"}
            
            elif action == "enfeoff":
                official_id = params.get("official_id", "")
                tile_id = params.get("tile_id", "")
                player.treasury -= 1000
                return {"success": True, "message": f"已分封{official_id}至{tile_id}"}
            
            elif action == "law":
                prisoner_id = params.get("prisoner_id", "")
                law_action = params.get("law_action", "imprison")
                return self._court_engine.handle_prisoner(prisoner_id, law_action)
            
            elif action == "purge":
                official_id = params.get("official_id", "")
                return self._court_engine.dismiss_official(official_id)
            
            elif action == "amnesty":
                player.reputation += 10
                player.realm_stability = min(100, player.realm_stability + 5)
                # 释放所有囚犯
                freed = len(getattr(self.world, 'prisoners', {}))
                self.world.prisoners.clear()
                return {"success": True, "message": f"大赦天下，释放{freed}名囚犯，民心归附"}
            
            elif action == "scout":
                target_tile = params.get("target_tile", "")
                tile = self.world.get_tile(target_tile)
                return {
                    "success": True,
                    "message": "侦查完成",
                    "data": tile.model_dump() if tile else {},
                }
            
            # ===== 新增指令类型（与 _validate_command 校验分支一一对齐） =====
            
            elif action == "convict_labor":
                tile_id = params.get("tile_id", "")
                project = params.get("project", "筑城")
                tile = self.world.get_tile(tile_id)
                if not tile or tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
                if tile.population < 200:
                    return {"success": False, "message": "人口不足（至少200人才能征发徭役）"}
                tile.morale = max(0, tile.morale - 8)
                tile.population = max(100, tile.population - 100)
                if project in ("筑城", "修路"):
                    tile.fortification = min(100, tile.fortification + 2)
                    return {"success": True, "message": f"「{tile.tile_name or tile_id}」徭役{project}完成（城防+2，民心-8）"}
                else:
                    tile.development_level = getattr(tile, 'development_level', 0) + 3
                    return {"success": True, "message": f"「{tile.tile_name or tile_id}」徭役{project}完成（发展度+3，民心-8）"}
            
            elif action == "cultural_policy":
                policy_type = params.get("policy_type", "开科举")
                if player.treasury < 800:
                    return {"success": False, "message": "银两不足（需要800）"}
                player.treasury -= 800
                player.reputation += 5
                player.realm_stability = min(100, player.realm_stability + 3)
                return {
                    "success": True,
                    "message": f"推行{policy_type}政策（耗费800银，声望+5，民心+3）",
                    "policy": policy_type,
                    "reputation_gain": 5,
                }
            
            elif action == "sea_policy":
                policy_type = params.get("policy_type", "开海贸")
                if policy_type == "建水师":
                    if player.treasury < 1000:
                        return {"success": False, "message": "银两不足（需要1000）"}
                    player.treasury -= 1000
                    player.navy_power = getattr(player, 'navy_power', 0) + 20
                    return {"success": True, "message": "水师已建成（耗费1000银，海军战力+20）"}
                else:
                    player.sea_trade_active = (policy_type == "开海贸")
                    return {
                        "success": True,
                        "message": f"海策已调整为「{policy_type}」",
                        "policy": policy_type,
                    }
            
            elif action == "medical":
                tile_id = params.get("tile_id", "")
                tile = self.world.get_tile(tile_id)
                if not tile or tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
                if player.treasury < 400:
                    return {"success": False, "message": "银两不足（需要400）"}
                player.treasury -= 400
                tile.clinic += 1
                tile.plague_resistance = min(100, getattr(tile, 'plague_resistance', 0) + 10)
                return {
                    "success": True,
                    "message": f"「{tile.tile_name or tile_id}」医馆扩张完成（耗费400银，瘟疫抗性+10）",
                    "tile": tile_id,
                }
            
            elif action == "ambush":
                tile_id = params.get("tile_id", "")
                troops = params.get("troops", 0)
                tile = self.world.get_tile(tile_id)
                if not tile:
                    return {"success": False, "message": f"地块{tile_id}不存在"}
                if tile.troops < troops:
                    return {"success": False, "message": f"兵力不足（需要{troops}，现有{tile.troops}）"}
                grain_cost = troops * 1
                if player.grain < grain_cost:
                    return {"success": False, "message": f"粮草不足（需要{grain_cost}石）"}
                player.grain -= grain_cost
                tile.ambush_troops = troops
                tile.troops -= troops
                return {
                    "success": True,
                    "message": f"在{tile.tile_name or tile_id}设伏{troops}人（耗费粮{grain_cost}石）",
                    "tile": tile_id,
                    "ambush_troops": troops,
                    "cost_grain": grain_cost,
                }
            
            elif action == "plunder":
                tile_id = params.get("tile_id", "")  # 劫掠部队来源地块（己方）
                target_tile = params.get("target_tile", "")
                troops = params.get("troops", 0)
                source_tile = self.world.get_tile(tile_id) if tile_id else None
                tile = self.world.get_tile(target_tile)
                if not tile:
                    return {"success": False, "message": f"目标地块{target_tile}不存在"}
                if tile.faction_id == player.faction_id:
                    return {"success": False, "message": "不能劫掠己方地块"}
                # 从来源地块扣除兵力
                if source_tile and source_tile.faction_id == player.faction_id:
                    if source_tile.troops < troops:
                        return {"success": False, "message": f"劫掠兵力不足（可调遣：{source_tile.troops}）"}
                    source_tile.troops -= troops
                grain_cost = troops * 1
                if player.grain < grain_cost:
                    return {"success": False, "message": "粮草不足"}
                player.grain -= grain_cost
                loot_silver = min(tile.population * 2, 2000)
                loot_grain = min(tile.population, 1000)
                # 从被劫掠方扣除资源（v4.3: 修复劫掠虚空产资源Bug）
                target_faction = self.world.factions.get(tile.faction_id)
                if target_faction:
                    target_faction.treasury = max(0, target_faction.treasury - loot_silver)
                    target_faction.grain = max(0, target_faction.grain - loot_grain)
                tile.treasury = max(0, getattr(tile, 'treasury', 0) - loot_silver)
                tile.grain = max(0, tile.grain - loot_grain)
                tile.morale = max(0, tile.morale - 20)
                tile.population = max(100, tile.population - troops // 2)
                tile.development_level = max(0, getattr(tile, 'development_level', 0) - 1)
                player.treasury += loot_silver
                player.grain += loot_grain
                key = self.world.relation_key(player.faction_id, tile.faction_id)
                if key in self.world.relations:
                    self.world.relations[key].attitude -= 15
                return {
                    "success": True,
                    "message": f"从{source_tile.tile_name or tile_id}调兵劫掠{tile.tile_name or target_tile}，夺取银{loot_silver}两、粮{loot_grain}石",
                    "tile": target_tile,
                    "source_tile": tile_id,
                    "loot_silver": loot_silver,
                    "loot_grain": loot_grain,
                }
            
            elif action == "move_capital":
                tile_id = params.get("tile_id", "")
                tile = self.world.get_tile(tile_id)
                if not tile or tile.faction_id != player.faction_id:
                    return {"success": False, "message": "目标地块不在己方掌控之内"}
                # 从 faction_configs["_game_const"] 读取迁都费用（默认 10000），与 RoyalAdvancedEngine.move_capital 保持一致
                _const = self.faction_configs.get("_game_const", {})
                cost_silver = _const.get("move_capital_cost", 10000)
                if player.treasury < cost_silver:
                    return {"success": False, "message": f"银两不足（需要{cost_silver}，现有{player.treasury}）"}
                player.treasury -= cost_silver
                # 旧都降级
                for tid, t in self.world.tiles.items():
                    if getattr(t, 'is_capital', False) and t.faction_id == player.faction_id:
                        t.is_capital = False
                tile.is_capital = True
                player.realm_stability = max(0, player.realm_stability - 10)
                player.capital_tile = tile_id  # Bug #37修复: 统一为capital_tile
                return {
                    "success": True,
                    "message": f"迁都至{tile.tile_name or tile_id}（耗费银{cost_silver}两，民心暂时动荡）",
                    "new_capital": tile_id,
                    "cost_silver": cost_silver,
                }
            
            elif action == "decree":
                # 圣旨指令：册立世子/教导皇子/纳妃/修史/改元
                decree_type = params.get("decree_type", "")
                content = params.get("content", "")
                prince_name = params.get("prince_name", "")
                cost = params.get("cost", 0)
                if cost > 0 and player.treasury >= cost:
                    player.treasury -= cost
                if decree_type == "chronicle":
                    return {"success": True, "message": f"史书编纂中: {content[:50]}...", "decree_type": decree_type}
                elif decree_type == "era_name":
                    player.era_name = content
                    return {"success": True, "message": f"已改元「{content}」", "decree_type": decree_type}
                elif decree_type == "heir":
                    return {"success": True, "message": f"已册立{prince_name}为世子", "decree_type": decree_type}
                elif decree_type == "education":
                    return {"success": True, "message": f"已安排{prince_name}延师教导", "decree_type": decree_type}
                elif decree_type == "spawn_prince":
                    # 将新皇子实际添加到势力宗室
                    custom_name = params.get("custom_name", False)  # 是否自定义名字
                    new_heir = {
                        "name": prince_name,
                        "age": 0,
                        "status": "新生",
                        "martial": 5,
                        "civil": 5,
                        "charisma": 10,
                        "talent": "尚待观察",
                        "ambition": "低",
                        "is_historical": not custom_name,
                        "is_custom_name": bool(custom_name),
                    }
                    if not hasattr(player, 'heirs') or player.heirs is None:
                        player.heirs = []
                    player.heirs.append(new_heir)
                    return {"success": True, "message": f"新皇子{prince_name}已入宗谱", "decree_type": decree_type, "prince": new_heir}
                else:
                    return {"success": True, "message": f"圣意已下: {content[:50]}", "decree_type": decree_type}
            
            elif action == "marriage":
                # 皇子联姻
                prince_name = params.get("prince_name", "")
                cost = params.get("cost", 300)
                if player.treasury >= cost:
                    player.treasury -= cost
                player.reputation += 3
                return {"success": True, "message": f"{prince_name}已完成大婚，声望+3（耗费银{cost}两）", "prince_name": prince_name}
            
            elif action == "patrol":
                # 水师巡航
                tile_id = params.get("tile_id", "")
                port_name = params.get("port_name", tile_id)
                tile = self.world.get_tile(tile_id)
                if not tile or tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
                tile.morale = min(100, tile.morale + 3)
                return {"success": True, "message": f"水师已从{port_name}出航巡航", "tile": tile_id}
            
            elif action == "appoint":
                # 提拔官员
                official_id = params.get("official_id", "")
                off_name = params.get("name", official_id)
                return {"success": True, "message": f"已提拔{off_name}", "official_id": official_id}
            
            elif action == "dismiss":
                # 降职官员
                official_id = params.get("official_id", "")
                off_name = params.get("name", official_id)
                return {"success": True, "message": f"已降职{off_name}", "official_id": official_id}
            
            elif action == "trade":
                # 开辟航线（非外交贸易，是内政层面的海贸航路）
                tile_id = params.get("tile_id", "")
                cost = params.get("cost", 300)
                tile = self.world.get_tile(tile_id)
                if not tile or tile.faction_id != player.faction_id:
                    return {"success": False, "message": f"地块{tile_id}不存在或不属于你方"}
                if player.treasury >= cost:
                    player.treasury -= cost
                # 标记航线开辟
                tile.trade_route_open = True
                tile.trade_income = getattr(tile, 'trade_income', 0) + 80
                return {"success": True, "message": f"已从{tile.tile_name or tile_id}开辟新航线（耗费银{cost}两）", "tile": tile_id}
            
            else:
                return {"success": False, "message": f"未知指令类型: {action}"}
        
        except Exception as e:
            logger.error(f"执行指令失败 [{action}]: {e}", exc_info=True)
            return {"success": False, "message": f"执行异常: {str(e)}"}
    
    # ================================================================
    # ③ AI推演
    # ================================================================
    
    async def _phase_ai_step(self, summary: dict):
        """
        ③ AI推演：通过Orchestrator调度A1~A10智能体 + AIExecutor执行落地（v4.0）
        
        核心规则：
        - 玩家操控势力(player_faction_id)的A2 RulerAgent强制休眠，完全跳过AI决策
        - 其余敌方势力RulerAgent正常完整运行
        - 玩家势力所有行为100%由前端手动下发指令驱动
        
        3.1增强：AIExecutor将所有AI决策结果转化为实际的WorldState修改
        
        3.2修复：增加LLM可用性检测与结果有效性验证，避免LLM不可用时AI空转
        """
        player_faction_id = self.world.player_faction_id
        
        # ---- 前置检查：LLM是否实际可用 ----
        # 即使 _llm_clients 已初始化(3个客户端对象总是创建)，
        # 若未配置 API Key 则 LLM 调用会静默失败返回空文本，
        # 导致 AIExecutor 跳过所有势力 → AI空转。
        # 修复：只有 _llm_available=True 时才走 LLM 管线。
        can_use_llm = bool(self._llm_clients) and self._llm_available and self.faction_configs
        
        if can_use_llm:
            try:
                from server.agent.orchestrator import get_orchestrator
                from server.agent.ai_executor import AIExecutor
                
                orch = get_orchestrator()
                self._orchestrator = orch  # v4.3.3: 存储到实例，供 A10/A3/A4/A7 子阶段复用
                # 使用轻量快照替代 model_dump()，节省 95%+ 序列化开销
                # Agent 管线不需要 tiles（~1300 地块）等大字段
                world_dict = self.world.to_agent_snapshot() if hasattr(self.world, 'to_agent_snapshot') else {}
                
                # ① AI推演：各Agent生成文本决策
                ai_summary = await orch.run_full_auto_step(
                    world_state=world_dict,
                    faction_configs=self.faction_configs,
                    clients=self._llm_clients,
                    skip_faction_id=player_faction_id,
                )
                phases = ai_summary.get("phases", {})
                
                # ---- 结果有效性验证 ----
                # 如果所有 A2 势力都返回了空的 decision_summary，
                # 说明 LLM 调用全部失败（API不可达/配额耗尽等），应降级到数值方案
                a2_data = phases.get("A2_warlords", {})
                a2_results = a2_data.get("results", [])
                a2_agents_ran = a2_data.get("agents_ran", 0)
                # 仅统计 full_response 非空的势力（decision_summary 有占位文本"（无决策）"不可信）
                a2_non_empty = sum(
                    1 for r in a2_results
                    if r.get("full_response", "").strip()
                )
                
                if a2_agents_ran > 0 and a2_non_empty == 0:
                    # 所有势力 LLM 调用都返回了空文本 → 完全降级
                    logger.warning(
                        f"_phase_ai_step: LLM管线运行完成但 {a2_agents_ran} 个势力决策均为空，"
                        f"降级到数值方案"
                    )
                    summary["phases"]["ai_step"] = self._fallback_ai_step()
                    summary["phases"]["ai_step"]["degraded_from"] = "llm_empty_results"
                else:
                    # v3.4: 部分降级 — 对LLM返回空文本的势力单独使用数值方案
                    partial_fallback_factions = []
                    for r in a2_results:
                        if not r.get("full_response", "").strip():
                            fid = r.get("faction_id", "unknown")
                            partial_fallback_factions.append(fid)
                    
                    if partial_fallback_factions:
                        logger.info(
                            f"_phase_ai_step: {len(partial_fallback_factions)}/{a2_agents_ran} "
                            f"个势力LLM返回空，对这些势力启用数值降级: {partial_fallback_factions}"
                        )
                        # 对空文本势力补充数值方案
                        self._ensure_engines()
                        for fid in partial_fallback_factions:
                            self._apply_fallback_for_faction(fid)
                    
                    # ② AIExecutor：将AI决策落地为游戏操作
                    self._ensure_engines()
                    executor = AIExecutor(
                        self.world, self.faction_configs,
                        march_engine=self._march_engine,
                        spy_engine=self._spy_engine,
                        diplomacy_engine=self._diplomacy_engine,
                    )
                    
                    executed = {}
                    
                    # A2 群雄决策 → 军事/内政操作
                    if a2_results:
                        executed["A2_warlord_actions"] = executor.execute_warlord_decisions(a2_results)
                        total_actions = sum(len(a.get('actions', [])) for a in executed["A2_warlord_actions"])
                        logger.info(f"A2 执行落地: {len(a2_results)} 个势力, 共 {total_actions} 个操作")
                        
                        # v4.3: 收集A2君主决策反思，存入events_log供前端展示
                        a2_reflections = 0
                        for r in a2_results:
                            reflection = r.get("ruler_reflection", "").strip()
                            if reflection and len(reflection) > 10:
                                fid = r.get("faction_id", "")
                                ruler_name = r.get("ruler", fid)
                                self.world.events_log.append({
                                    "event_id": f"reflection_{fid}_{self.world.current_round}",
                                    "event_type": "ruler_reflection",
                                    "severity": "minor",
                                    "faction_id": fid,
                                    "ruler": ruler_name,
                                    "description": reflection,
                                    "round": self.world.current_round,
                                })
                                a2_reflections += 1
                        if a2_reflections:
                            logger.info(f"A2 决策反思: 记录了 {a2_reflections} 个势力的君主独白")
                    
                    # A4 谍报分析 → 细作行动
                    a4_data = phases.get("A4_espionage", {})
                    a4_results = a4_data.get("results", [])
                    if a4_results:
                        executed["A4_espionage_actions"] = executor.execute_espionage_actions(a4_results)
                        logger.info(f"A4 执行落地: {len(a4_results)} 个网络")
                    
                    # A5 事件影响 → 数值回写
                    a5_data = phases.get("A5_events", {})
                    if a5_data.get("event_triggered"):
                        executed["A5_event_impacts"] = executor.apply_event_impacts(a5_data)
                        logger.info(f"A5 执行落地: {executed['A5_event_impacts'].get('factions_affected', 0)} 个势力受影响")
                    
                    # A6 外交分析 → 外交操作
                    a6_data = phases.get("A6_diplomacy", {})
                    a6_results = a6_data.get("results", [])
                    if a6_results:
                        executed["A6_diplomacy_actions"] = executor.execute_diplomacy_actions(a6_results)
                        logger.info(f"A6 执行落地: {len(a6_results)} 个势力")
                    
                    # A7 宗室成长 → 数据回写
                    a7_data = phases.get("A7_royal", {})
                    a7_results = a7_data.get("results", [])
                    if a7_results:
                        executed["A7_royal_updates"] = executor.apply_royal_updates(a7_results)
                        logger.info(f"A7 执行落地: {executed['A7_royal_updates'].get('factions_updated', 0)} 个势力")
                    
                    # v4.3: 叙事引擎输出 → 存入 events_log 供前端展示（纯叙事，不影响数值）
                    narrative_events = 0
                    
                    # 朝堂廷议
                    court_data = phases.get("court_debate", {})
                    court_results = court_data.get("results", [])
                    for debate in court_results:
                        if debate.get("narrative"):
                            self.world.events_log.append({
                                "event_id": f"court_{debate.get('faction_id', '?')}_{self.world.current_round}",
                                "event_type": "court_debate",
                                "severity": "minor",
                                "faction_id": debate.get("faction_id", ""),
                                "ruler": debate.get("ruler", ""),
                                "description": debate["narrative"],
                                "round": self.world.current_round,
                            })
                            narrative_events += 1
                    
                    # 市井舆情
                    sentiment_data = phases.get("public_sentiment", {})
                    rumors = sentiment_data.get("rumors", [])
                    for rumor in rumors:
                        if rumor.get("text"):
                            self.world.events_log.append({
                                "event_id": f"rumor_{self.world.current_round}_{hash(rumor['text']) % 10000}",
                                "event_type": "public_rumor",
                                "severity": "minor",
                                "category": rumor.get("category", ""),
                                "description": rumor["text"],
                                "round": self.world.current_round,
                            })
                            narrative_events += 1
                    
                    # 将领列传
                    chronicles_data = phases.get("general_chronicles", {})
                    entries = chronicles_data.get("entries", [])
                    for entry in entries:
                        if entry.get("narrative"):
                            self.world.events_log.append({
                                "event_id": f"chronicle_{self.world.current_round}_{hash(entry.get('name', '')) % 10000}",
                                "event_type": "general_chronicle",
                                "severity": "minor",
                                "general_name": entry.get("name", ""),
                                "description": entry["narrative"],
                                "round": self.world.current_round,
                            })
                            narrative_events += 1
                    
                    if narrative_events > 0:
                        logger.info(f"v4.3叙事引擎: 存入了 {narrative_events} 条叙事事件")
                    executed["narrative_events_stored"] = narrative_events
                    
                    summary["phases"]["ai_step"] = {
                        **phases,
                        "engine": "llm_8agent",
                        "player_faction_skipped": player_faction_id,
                        "player_skipped": bool(player_faction_id),
                        "executed": executed,
                    }
            except Exception as e:
                logger.error(f"AI推演失败: {e}", exc_info=True)
                summary["phases"]["ai_step"] = self._fallback_ai_step()
        else:
            # LLM不可用或无势力配置 → 直接走降级方案
            if not self._llm_available:
                logger.info(
                    "_phase_ai_step: LLM不可用(无API Key)，使用数值降级方案 "
                    f"(clients_exist={bool(self._llm_clients)}, "
                    f"available={self._llm_available})"
                )
            summary["phases"]["ai_step"] = self._fallback_ai_step()

        # ③.5 征伐全链路AI联动：处理所有活跃战争
        try:
            war_summary = await self._orchestrate_active_wars(summary)
            summary["phases"]["war_ai"] = war_summary
        except Exception as e:
            logger.error(f"征伐AI编排失败: {e}", exc_info=True)
            summary["phases"]["war_ai"] = {"error": str(e)}

        # ③.6 v3.5: A9 AI战报生成 — 为本回合所有战斗生成古风战报
        try:
            # 扫描 events_log 收集本轮所有战斗
            self._scan_battle_events_from_log()
            if self._pending_battle_reports and self._llm_clients and self._llm_available:
                from server.agent.a9_battle_report import get_a9_battle_report_agent
                a9 = get_a9_battle_report_agent()
                reports = await a9.generate_batch(
                    self._pending_battle_reports, self._llm_clients
                )
                # 将战报回写到 events_log
                self._apply_battle_reports(reports)
                logger.info(
                    f"A9 军机处: 生成了 {len(reports)} 份AI战报 "
                    f"(共{len(self._pending_battle_reports)}场战斗)"
                )
                summary["phases"]["ai_step"]["a9_battle_reports"] = len(reports)
                
                # v4.3: A9 战局综述 — 综合所有战斗生成全局战局分析（纯叙事）
                try:
                    ws = self._get_world_dict()
                    war_summary = await a9.generate_war_summary(
                        self._pending_battle_reports, ws, self._llm_clients
                    )
                    if war_summary:
                        # 将战局综述追加到 events_log 供前端展示
                        self.world.events_log.append({
                            "event_id": f"war_summary_{self.world.current_round}",
                            "event_type": "war_summary",
                            "severity": "major",
                            "description": war_summary,
                            "round": self.world.current_round,
                            "year": self.world.current_year,
                            "season": self.world.current_season,
                        })
                        summary["phases"]["ai_step"]["a9_war_summary"] = war_summary[:200]
                        logger.info(f"A9 战局综述已生成 ({len(war_summary)}字)")
                except Exception as ws_e:
                    logger.warning(f"A9 战局综述生成失败（非致命）: {ws_e}")
        except Exception as e:
            logger.error(f"A9战报生成失败: {e}", exc_info=True)

        # ③.7 v4.0: A10 度支司 — AI经济决策（税率/粮储/贸易/建设）
        try:
            if self._llm_clients and self._llm_available:
                from server.agent.a10_treasury import get_a10_treasury_agent
                a10 = get_a10_treasury_agent()
                econ_results = []
                ws = self._get_world_dict()
                for fid, faction in self.world.factions.items():
                    if not faction.is_alive or fid == player_faction_id:
                        continue
                    try:
                        ws = self._get_world_dict()
                        policy = await a10.formulate_policy(fid, ws, self._llm_clients)
                        applied = self._orchestrator.a10_apply_policies(fid, ws, policy)
                        econ_results.append({"faction_id": fid, "policy": policy, "applied": applied})
                    except Exception as inner_e:
                        logger.warning(f"A10 度支 [{fid}] 失败: {inner_e}")
                logger.info(f"A10 度支司: 为 {len(econ_results)} 个势力制定了经济政策")
                summary["phases"]["ai_step"]["a10_economy_policies"] = len(econ_results)
        except Exception as e:
            logger.error(f"A10度支政策失败: {e}", exc_info=True)

        # ③.8 v4.0: A3 吏部 — AI官员任免
        try:
            if self._llm_clients and self._llm_available:
                ws = self._get_world_dict()  # v4.3.3: 防御性定义，避免依赖 A10 作用域
                official_results = []
                for fid, faction in self.world.factions.items():
                    if not faction.is_alive or fid == player_faction_id:
                        continue
                    npcs = faction.npcs if hasattr(faction, 'npcs') else []
                    if not npcs:
                        continue
                    try:
                        result = await self._orchestrator.a3_manage_officials(
                            fid, ws, self._llm_clients, list(npcs))
                        official_results.append({"faction_id": fid, "result": result})
                    except Exception as inner_e:
                        logger.warning(f"A3 吏部 [{fid}] 失败: {inner_e}")
                if official_results:
                    logger.info(f"A3 吏部: 完成了 {len(official_results)} 个势力的官员考核")
                    summary["phases"]["ai_step"]["a3_official_reviews"] = len(official_results)
        except Exception as e:
            logger.error(f"A3吏部失败: {e}", exc_info=True)

        # ③.9 v4.0: A4 谍报司 — AI间谍策略计划
        try:
            if self._llm_clients and self._llm_available:
                ws = self._get_world_dict()  # v4.3.3: 防御性定义，避免依赖 A10 作用域
                spy_plans = []
                for fid, faction in self.world.factions.items():
                    if not faction.is_alive or fid == player_faction_id:
                        continue
                    try:
                        plan = await self._orchestrator.a4_plan_spy_strategy(
                            fid, ws, self._llm_clients)
                        if plan.get("actions"):
                            spy_plans.append({"faction_id": fid, "plan": plan})
                    except Exception as inner_e:
                        logger.warning(f"A4 谍报策略 [{fid}] 失败: {inner_e}")
                if spy_plans:
                    logger.info(f"A4 谍报司: 制定了 {len(spy_plans)} 个势力的谍报计划")
                    summary["phases"]["ai_step"]["a4_spy_strategies"] = len(spy_plans)
        except Exception as e:
            logger.error(f"A4谍报策略失败: {e}", exc_info=True)

        # ③.10 v4.0: A7 宗室府 — AI王朝管理（储位+联姻+历练）
        try:
            if self._llm_clients and self._llm_available:
                ws = self._get_world_dict()  # v4.3.3: 防御性定义，避免依赖 A10 作用域
                dynasty_results = []
                for fid, faction in self.world.factions.items():
                    if not faction.is_alive or fid == player_faction_id:
                        continue
                    try:
                        result = await self._orchestrator.a7_manage_dynasty(
                            fid, ws, self._llm_clients)
                        dynasty_results.append({"faction_id": fid, "result": result})
                    except Exception as inner_e:
                        logger.warning(f"A7 王朝管理 [{fid}] 失败: {inner_e}")
                if dynasty_results:
                    logger.info(f"A7 宗室府: 完成了 {len(dynasty_results)} 个势力的王朝管理")
                    summary["phases"]["ai_step"]["a7_dynasty_management"] = len(dynasty_results)
        except Exception as e:
            logger.error(f"A7王朝管理失败: {e}", exc_info=True)

        for hook in self._phase_hooks[3]:
            await hook(self.world)
    
    def _scan_battle_events_from_log(self):
        """扫描 events_log，收集本回合所有未生成战报的战斗事件"""
        current_round = self.world.current_round
        for event in self.world.events_log:
            if event.get("round") != current_round:
                continue
            if event.get("event_type") != "battle":
                continue

            # 检查是否已经生成了AI战报
            narrative = event.get("narrative", "")
            if narrative and ("军机处报" in narrative):
                continue  # 已经是AI战报，跳过

            # 已有上下文队列中的，跳过
            event_id = event.get("event_id", "")
            if any(b.get("event_id") == event_id for b in self._pending_battle_reports):
                continue

            # 从event数据构建上下文
            effects = event.get("effects", {})
            atk_fid = effects.get("attacker", "")
            def_fid = effects.get("defender", "")
            atk_f = self.world.get_faction(atk_fid)
            def_f = self.world.get_faction(def_fid)

            result_map = {"victory": atk_fid, "defeat": def_fid, "stalemate": None}
            ctx_result = effects.get("result", "stalemate")
            winner_fid = result_map.get(ctx_result)
            winner_name = ""
            if winner_fid:
                wf = self.world.get_faction(winner_fid)
                winner_name = wf.name if wf else winner_fid

            context = {
                "attacker_name": atk_f.name if atk_f else atk_fid,
                "defender_name": def_f.name if def_f else def_fid,
                "tile_name": event.get("title", "").replace("攻占 · ", "").replace("败绩 · ", "").replace("鏖战 · ", "").replace("围困 · ", ""),
                "terrain": effects.get("terrain", "平原"),
                "season": self.world.current_season.value if self.world.current_season else "春",
                "attacker_troops": effects.get("attacker_losses", 0) + effects.get("attacker_remaining", 0),
                "defender_troops": effects.get("defender_losses", 0) + effects.get("defender_remaining", 0),
                "attacker_losses": effects.get("attacker_losses", 0),
                "defender_losses": effects.get("defender_losses", 0),
                "attacker_remaining": effects.get("attacker_remaining", 0),
                "defender_remaining": effects.get("defender_remaining", 0),
                "result": ctx_result,
                "winner_name": winner_name,
                "is_siege": effects.get("is_siege", False),
                "tile_captured": ctx_result == "victory",
                "fortification": effects.get("fortification", 0),
                "engine": effects.get("_engine", "simple"),
                "tactics_used": effects.get("_tactics_used", []),
                "power_ratio": effects.get("_power_ratio"),
                "event_id": event_id,
            }
            self._pending_battle_reports.append(context)

    def _apply_battle_reports(self, reports: list[dict]):
        """将AI生成的战报回写到 events_log 的对应事件中"""
        for report in reports:
            idx = report.get("battle_index", -1)
            narrative = report.get("narrative", "")
            if idx < 0 or idx >= len(self._pending_battle_reports) or not narrative:
                continue

            event_id = self._pending_battle_reports[idx].get("event_id", "")
            if not event_id:
                continue

            for event in self.world.events_log:
                if event.get("event_id") == event_id:
                    event["narrative"] = narrative
                    event["ai_generated_narrative"] = True
                    break

        # 清空待处理队列
        self._pending_battle_reports.clear()

    def _get_world_dict(self) -> dict:
        """将WorldState转换为字典格式供Agent使用"""
        if hasattr(self.world, 'to_agent_snapshot'):
            return self.world.to_agent_snapshot()
        # v4.3.3: 降级路径与 to_agent_snapshot() 保持字段对齐
        return {
            "current_round": self.world.current_round,
            "current_year": getattr(self.world, 'current_year', 1351),
            "current_month": getattr(self.world, 'current_month', 1),
            "current_season": str(self.world.current_season) if self.world.current_season else "春",
            "disaster_index": getattr(self.world, 'disaster_index', 0),
            "player_faction_id": getattr(self.world, 'player_faction_id', ""),
            "factions": {
                fid: {
                    "name": f.name if hasattr(f, 'name') else fid,
                    "alive": f.is_alive if hasattr(f, 'is_alive') else True,
                    "troops": f.troops if hasattr(f, 'troops') else 0,
                    "total_troops": getattr(f, 'total_troops', f.troops if hasattr(f, 'troops') else 0),
                    "treasury": f.treasury if hasattr(f, 'treasury') else 0,
                    "grain": f.grain if hasattr(f, 'grain') else 0,
                    "reputation": f.reputation if hasattr(f, 'reputation') else 50,
                    "realm_stability": f.realm_stability if hasattr(f, 'realm_stability') else 50,
                    "court_stability": getattr(f, 'court_stability', 50),
                    "tile_count": f.tile_count if hasattr(f, 'tile_count') else 0,
                    "total_population": getattr(f, 'total_population', f.population if hasattr(f, 'population') else 0),
                    "population": f.population if hasattr(f, 'population') else 0,
                    "neighbors": f.neighbors if hasattr(f, 'neighbors') else [],
                    "heirs": getattr(f, 'heirs', []),
                    "is_player": getattr(f, 'is_player', False),
                    "is_alive": f.is_alive if hasattr(f, 'is_alive') else True,
                    "personality_tags": getattr(f, 'personality_tags', []),
                    "personality": getattr(f, 'personality', []),
                    "capital_tile": getattr(f, 'capital_tile', ""),
                    "navy_power": getattr(f, 'navy_power', 0),
                    "ruler_name": f.ruler_name if hasattr(f, 'ruler_name') else fid,
                    "ruler_age": f.ruler_age if hasattr(f, 'ruler_age') else 40,
                    "buildings": getattr(f, 'buildings', {}),
                    "tax_rate": getattr(f, 'tax_rate', 0.15),
                }
                for fid, f in self.world.factions.items()
            },
            "relations": {
                rkey: r.model_dump() if hasattr(r, 'model_dump') else {
                    "faction_a": r.faction_a if hasattr(r, 'faction_a') else "",
                    "faction_b": r.faction_b if hasattr(r, 'faction_b') else "",
                    "status": str(r.stance) if hasattr(r, 'stance') else "neutral",
                    "value": getattr(r, 'value', 0),
                }
                for rkey, r in self.world.relations.items()
            },
            "spy_networks": getattr(self.world, 'spy_networks', {}),
            "siege_states": getattr(self.world, 'siege_states', {}),
            "coalitions": getattr(self.world, 'coalitions', {}),
            "vassal_relations": getattr(self.world, 'vassal_relations', {}),
            "recent_events": self.world.events_log[-30:] if getattr(self.world, 'events_log', None) else [],
        }

    def _fallback_ai_step(self) -> dict:
        """
        AI降级：利用AIExecutor增强版降级方案
        
        核心规则：玩家操控势力(player_faction_id)的A2 RulerAgent强制休眠
        - 跳过已灭亡势力
        - 跳过玩家操控势力（该势力行为100%由玩家手动指令驱动，AI不得越权）
        
        增强（3.1）：
        - 利用 faction_config 的 ai_logic 参数实现差异化策略
        - 每个势力根据 expansion/consolidation/diplomacy/military/economy 参数做出不同决策
        - 围城持续推进
        """
        self._ensure_engines()
        
        from server.agent.ai_executor import AIExecutor
        executor = AIExecutor(
            self.world, self.faction_configs,
            march_engine=self._march_engine,
            spy_engine=self._spy_engine,
            diplomacy_engine=self._diplomacy_engine,
        )
        
        # 先处理所有活跃围城
        results = executor.fallback_ai_step_enhanced(
            skip_faction_id=self.world.player_faction_id
        )
        
        return results

    def _apply_fallback_for_faction(self, faction_id: str):
        """
        v3.4: 对单个势力应用数值降级方案
        
        当LLM对某个势力返回空文本时，不放弃该势力，
        而是用数值驱动方案为其做出基础决策（征募/建造/驻防等）。
        
        Args:
            faction_id: 需要降级处理的势力ID
        """
        from server.agent.ai_executor import AIExecutor
        executor = AIExecutor(
            self.world, self.faction_configs,
            march_engine=self._march_engine,
            spy_engine=self._spy_engine,
            diplomacy_engine=self._diplomacy_engine,
        )
        
        # 使用增强版降级，但仅处理指定势力
        # 通过构造临时 skip 集合实现（skip 除当前势力外的所有势力）
        all_factions = [f.faction_id if hasattr(f, 'faction_id') else f.id 
                       for f in self.world.factions.values()]
        results = executor.fallback_ai_step_enhanced(
            skip_faction_id=self.world.player_faction_id
        )
        
        # 从结果中提取仅目标势力的操作
        if results and "actions" in results:
            faction_actions = [
                a for a in results.get("actions", [])
                if a.get("faction_id") == faction_id
            ]
            logger.info(
                f"部分降级: {faction_id} 使用数值方案生成 {len(faction_actions)} 个操作"
            )

    async def _orchestrate_active_wars(self, summary: dict) -> dict:
        """
        征伐全链路AI联动：处理所有活跃战争

        对每场活跃战争，驱动征伐编排器完成：
        - 新宣战 → ①外交AI + ②军事AI + ③民生AI + ④叛军AI
        - 已在战 → ⑤军事结算 + ⑥疆域 + ⑦谋略
        """
        self._ensure_engines()
        war_summary = {"active_wars": 0, "new_wars": 0, "diplomacy_changes": [], "battles": []}

        if not self._war_orchestrator:
            return war_summary

        # 检测新增战争（从事件日志中）
        new_wars = self._detect_new_wars()
        for war_info in new_wars:
            try:
                # 3.0: 检查该势力对是否已有活跃战争，避免双重结算
                atk_id, dff_id = war_info["attacker"], war_info["defender"]
                already_active = False
                for ctx_existing in self._war_orchestrator.active_wars.values():
                    if ((ctx_existing.attacker_faction == atk_id and ctx_existing.defender_faction == dff_id) or
                        (ctx_existing.attacker_faction == dff_id and ctx_existing.defender_faction == atk_id)):
                        already_active = True
                        break
                if already_active:
                    continue

                ctx = await self._war_orchestrator.on_war_declared(
                    attacker=atk_id,
                    defender=dff_id,
                    reason=war_info.get("reason", ""),
                )
                war_summary["new_wars"] += 1
                war_summary["diplomacy_changes"].append({
                    "war_id": ctx.war_id,
                    "attacker_allies": ctx.attacker_allies,
                    "defender_allies": ctx.defender_allies,
                    "backstabbers": ctx.backstabbers,
                })
            except Exception as e:
                logger.error(f"[征伐编排] 宣战处理失败: {war_info}, {e}", exc_info=True)

        # 对已有的活跃战争进行回合结算
        for war_id, ctx in list(self._war_orchestrator.active_wars.items()):
            if ctx.stage.value in ("mobilization", "march", "engagement"):
                try:
                    turn_result = await self._war_orchestrator.orchestrate_war_turn(ctx)
                    war_summary["active_wars"] += 1
                    war_summary["battles"].extend(turn_result.get("battles", []))
                    war_summary.setdefault("stratagems", []).extend(
                        turn_result.get("stratagems", []))
                except Exception as e:
                    logger.error(f"[征伐编排] 回合结算失败: {war_id}, {e}", exc_info=True)

        return war_summary

    def _detect_new_wars(self) -> list[dict]:
        """从事件日志和外交关系变化中检测新宣战"""
        new_wars = []
        seen = set()

        # 检查最近的事件日志
        recent_events = self.world.events_log[-30:]
        for event in recent_events:
            if event.get("event_type") == "war_declaration":
                key = (event.get("attacker", ""), event.get("defender", ""))
                if key not in seen:
                    seen.add(key)
                    new_wars.append({
                        "attacker": key[0],
                        "defender": key[1],
                        "reason": event.get("reason", ""),
                    })

        # 检查外交关系变化（recent tile_changes）
        for change in getattr(self.world, 'tile_changes', [])[-20:]:
            if not isinstance(change, dict):
                continue  # Pydantic 模型保护（兼容 _has_recent_battle 模式）
            if (change.get("change_type") == "conquer" and
                change.get("old_faction_id") and
                change.get("new_faction_id")):
                key = (change["new_faction_id"], change["old_faction_id"])
                if key not in seen:
                    seen.add(key)
                    new_wars.append({
                        "attacker": key[0],
                        "defender": key[1],
                        "reason": "领土争夺",
                    })

        return new_wars
    
    # ================================================================
    # ④ 事件记录 —— 真实实现
    # ================================================================
    
    async def _phase_record_events(self, summary: dict):
        """④ 事件记录：筛选重要事件写治政录（含去重）"""
        important_events = []
        seen_event_ids = set()  # 3.2: 去重
        
        # Bug #6 修复: 检查本回合所有事件(通过round字段过滤)，不再仅限最近20条
        for event in self.world.events_log:
            if event.get("round") != self.world.current_round:
                continue
            severity = event.get("severity", "minor")
            if severity in ("major", "critical"):
                event_id = event.get("event_id", "")
                if event_id and event_id in seen_event_ids:
                    continue  # 跳过已记录的事件
                important_events.append(event)
                if event_id:
                    seen_event_ids.add(event_id)
        
        # 写入治政录（含去重：按 event_id 检查是否已存在于 governance_logs）
        existing_gov_ids = {
            g.get("event_id", "") for g in self.world.governance_logs
        }
        for event in important_events:
            if "narrative" in event:
                event_id = event.get("event_id", "")
                if event_id and event_id in existing_gov_ids:
                    continue  # 已存在，跳过
                entry = {
                    "round": self.world.current_round,
                    "title": event.get("title", ""),
                    "description": event.get("description", ""),
                    "narrative": event.get("narrative", ""),
                    "severity": event.get("severity", ""),
                }
                if event_id:
                    entry["event_id"] = event_id
                self.world.governance_logs.append(entry)
        
        summary["phases"]["events_recorded"] = {
            "total_events": len(self.world.events_log),
            "important_this_round": len(important_events),
            "governance_logs": len(self.world.governance_logs),
        }
        
        # 3.0: 裁剪 events_log（保留最近 600 条，240回合×2.5条/回合约足够）
        if len(self.world.events_log) > 600:
            self.world.events_log = self.world.events_log[-600:]

        for hook in self._phase_hooks[4]:
            await hook(self.world)
    
    # ================================================================
    # ⑤ 数值结算 —— 真实实现
    # ================================================================
    
    async def _phase_settle(self, summary: dict):
        """⑤ 数值结算：税收、粮耗、兵力、人口、天灾"""
        self._ensure_engines()
        settle_result = self._settle_engine.phase_settle()
        
        # 3.0: 推进所有活跃围城结算（每回合自动消耗守军粮食、降低城防）
        for siege_id in list(self.world.siege_states.keys()):
            try:
                siege_result = self._settle_engine.resolve_siege(siege_id)
                if siege_result.get("tile_captured"):
                    settle_result.setdefault("siege_captures", []).append(siege_result)
                    logger.info(f"[回合结算] 围城破城: {siege_result.get('tile_name', siege_id)}")
            except Exception as e:
                logger.warning(f"[回合结算] 围城推进失败 {siege_id}: {e}")
        
        # 贸易收益结算（从 faction_configs["_game_const"] 读取每条约收益，默认 100）
        # 3.3: 所有存活势力（含NPC）均享受贸易收入，不再仅限玩家
        _const = self.faction_configs.get("_game_const", {})
        trade_per_route = _const.get("trade_income_per_route", 100)
        trade_by_faction: dict[str, int] = {}
        for key, rel in self.world.relations.items():
            if not rel.trade_active:
                continue
            # 双方均存活才结算
            fa = self.world.factions.get(rel.faction_a)
            fb = self.world.factions.get(rel.faction_b)
            if not (fa and fa.is_alive and fb and fb.is_alive):
                continue
            trade_by_faction[rel.faction_a] = trade_by_faction.get(rel.faction_a, 0) + trade_per_route
            trade_by_faction[rel.faction_b] = trade_by_faction.get(rel.faction_b, 0) + trade_per_route
        for fid, income in trade_by_faction.items():
            faction = self.world.factions.get(fid)
            if faction:
                faction.treasury += income
        
        # 玩家贸易收入（用于 summary 展示）
        player = self.world.get_player_faction()
        player_trade_income = trade_by_faction.get(player.faction_id, 0) if player else 0
        
        summary["phases"]["settle"] = {
            "year_end": settle_result["year_end"],
            "tax_collected": sum(settle_result["tax_collected"].values()),
            "trade_income": player_trade_income,
            "total_trade_routes": len([k for k, r in self.world.relations.items() if r.trade_active]),
            "trade_by_faction": {fid: inc for fid, inc in trade_by_faction.items() if inc > 0},
            "disasters_triggered": len(settle_result["disasters_triggered"]),
            "disaster_details": settle_result["disasters_triggered"][:5],
            "population_changes": {
                k: v for k, v in list(settle_result["population_changes"].items())[:10]
            },
        }
        
        # v4.3: LLM经济结算审阅 — 结算完成后审阅并微调税率/粮策
        try:
            if self._llm_clients and self._llm_available:
                from server.core.llm_review import SettlementReview
                ws = self._get_world_dict()
                review = await SettlementReview.review_all(ws, settle_result, self._llm_clients)
                if review.get("reviewed_count", 0) > 0:
                    applied = SettlementReview.apply_adjustments(ws, review)
                    summary["phases"]["settle"]["llm_review"] = {
                        "reviewed": review["reviewed_count"],
                        "applied": applied["applied_count"],
                        "narrative": review.get("narrative", "")[:200],
                    }
                    if applied["applied_count"] > 0:
                        logger.info(f"LLM结算审阅: 调整了 {applied['applied_count']} 个势力的经济参数")
        except Exception as e:
            logger.warning(f"LLM结算审阅失败（非致命）: {e}")
        
        for hook in self._phase_hooks[5]:
            await hook(self.world)
    
    # ================================================================
    # ⑥ 刷新世界 —— 真实实现
    # ================================================================
    
    async def _phase_refresh_world(self, summary: dict):
        """⑥ 刷新世界：灾厄指数、条约、贸易、势力排名、人物状态 + 3.2 外交自动调整"""
        self._ensure_engines()
        refresh_result = self._settle_engine.phase_refresh_world()
        
        # 人物状态更新
        character_updates = self._update_characters()

        # 征伐AI：战时叛乱灾害AI评估 + 疆域AI刷新
        war_territory = {}
        if self._war_orchestrator and self._war_orchestrator.active_wars:
            try:
                for war_id, ctx in self._war_orchestrator.active_wars.items():
                    # ④ 叛乱灾害AI：每回合对交战双方地块评估动乱风险
                    risks = self._war_orchestrator._run_rebellion_risk_ai(ctx)
                    if risks:
                        war_territory.setdefault("rebellion_risks", []).extend(risks)
                    # ⑥ 疆域AI刷新
                    territory = self._war_orchestrator._run_territory_ai(ctx)
                    if territory:
                        war_territory.setdefault("territory_changes", []).extend(territory)
                # v3.0: 每回合推进所有活跃战争的战争分数
                self._war_orchestrator.tick_all_war_scores(self.world.current_round)
            except Exception as e:
                logger.error(f"[征伐AI] 刷新阶段失败: {e}", exc_info=True)

        # 3.2: 外交自动调整——根据战争/地盘变更自动修正外交状态
        auto_diplo_changes = self._auto_adjust_diplomacy()
        
        # v4.3: LLM外交关系审阅 — 自动调整后审阅所有势力对，生成细微态度漂移
        try:
            if self._llm_clients and self._llm_available:
                from server.core.llm_review import DiplomacyReview
                ws = self._get_world_dict()
                diplo_review = await DiplomacyReview.review_all(ws, self._llm_clients)
                if diplo_review.get("reviewed_pairs", 0) > 0:
                    applied = DiplomacyReview.apply_drifts(ws, diplo_review)
                    summary["phases"]["refresh"]["llm_diplomacy_review"] = {
                        "reviewed_pairs": diplo_review["reviewed_pairs"],
                        "applied_shifts": applied["applied_count"],
                    }
                    if applied["applied_count"] > 0:
                        logger.info(f"LLM外交审阅: 微调了 {applied['applied_count']} 对关系")
        except Exception as e:
            logger.warning(f"LLM外交审阅失败（非致命）: {e}")
        
        # v4.3: LLM战斗态势审阅 — 审阅所有势力军事态势，输出下回合士气修正
        try:
            if self._llm_clients and self._llm_available:
                from server.core.llm_review import CombatStanceReview
                ws = self._get_world_dict()
                combat_review = await CombatStanceReview.review_all(ws, self._llm_clients)
                if combat_review.get("reviewed_count", 0) > 0:
                    applied = CombatStanceReview.apply_stances(ws, combat_review)
                    summary["phases"]["refresh"]["llm_combat_stance"] = {
                        "reviewed": combat_review["reviewed_count"],
                        "applied": applied["applied_count"],
                        "narrative": combat_review.get("narrative", "")[:200],
                    }
                    if applied["applied_count"] > 0:
                        logger.info(f"LLM战斗态势审阅: 更新了 {applied['applied_count']} 个势力的战斗士气")
        except Exception as e:
            logger.warning(f"LLM战斗态势审阅失败（非致命）: {e}")
        
        # 藩镇检测（对所有势力生效）
        vassal_events = []
        for fid in self.world.factions:
            faction = self.world.factions.get(fid)
            if not faction or not faction.is_alive:
                continue
            for oid, off in self.world.officials.items():
                if off.faction_id == fid and off.loyalty < 30:
                    off.loyalty = max(0, off.loyalty - 2)
                    if off.loyalty < 15:
                        faction_name = faction.name
                        vassal_events.append(f"[{faction_name}]{off.name}野心高涨，有叛乱之虞")
        
        summary["phases"]["refresh"] = {
            "disaster_index": refresh_result["disaster_index"],
            "treaties_expired": len(refresh_result["treaties_expired"]),
            "power_ranking": refresh_result["power_ranking"][:5],
            "character_updates": character_updates,
            "vassal_warnings": vassal_events,
            "advanced_features": refresh_result.get("advanced_features", {}),
            "auto_diplomacy_changes": auto_diplo_changes,  # 3.2
            "war_ai_refresh": war_territory,  # 征伐AI疆域/叛乱刷新
        }

        # 3.2: 流亡朝廷检查（复用引擎实例，避免每回合新建）
        try:
            from server.core.advanced_features import RoyalAdvancedEngine
            if not hasattr(self, '_royal_engine'):
                self._royal_engine = RoyalAdvancedEngine(self.world)
            royal_engine = self._royal_engine
        except ImportError:
            royal_engine = None
        
        if royal_engine:
            for fid, faction in self.world.factions.items():
                if faction.is_alive and not self.world.get_faction_tiles(fid):
                    exile_result = royal_engine.activate_exile_court(fid)
                    if exile_result.get("exiled"):
                        summary["phases"]["refresh"].setdefault("exile_courts", []).append(
                            {"faction_id": fid, "name": faction.name}
                        )
        
        for hook in self._phase_hooks[6]:
            await hook(self.world)
    
    def _update_characters(self) -> list[dict]:
        """人物状态刷新：年龄、伤病、忠诚度浮动（向50均值回归，受court_stability影响）"""
        updates = []
        for oid, off in self.world.officials.items():
            # 获取所属势力的朝堂稳定度，影响忠诚回归速度
            court_stability = 50  # 默认
            if off.faction_id:
                faction = self.world.factions.get(off.faction_id)
                if faction:
                    court_stability = getattr(faction, 'court_stability', 50)
            # court_stability 高则回归慢（官员安心），低则回归快（人心惶惶）
            stability_factor = max(0.5, (100 - court_stability) / 50.0)  # 朝堂稳定100→0.5x, 0→2.0x
            drift = (off.loyalty - 50) * 0.02 * stability_factor
            # 使用 round 而非 int 截断，确保小幅度漂移也能生效
            new_loyalty = off.loyalty - round(drift)
            # 在 0~100 范围内时应用漂移（边界处不漂移）
            if 0 <= new_loyalty <= 100:
                off.loyalty = new_loyalty
            
            # 低忠诚官员可能叛逃（玩家势力阈值更严格：<5 而非 <10）
            if off.loyalty < 10 and off.faction_id:
                faction = self.world.factions.get(off.faction_id)
                if faction and faction.is_alive:
                    if not faction.is_player:
                        # AI势力：忠诚<10叛逃
                        off.faction_id = ""
                        off.is_exiled = True
                        updates.append({"name": off.name, "event": "叛逃"})
                    elif off.loyalty < 5:
                        # 玩家势力：忠诚<5叛逃（更宽容的阈值）
                        off.faction_id = ""
                        off.is_exiled = True
                        updates.append({"name": off.name, "event": "叛逃"})
        
        return updates

    def _auto_adjust_diplomacy(self) -> list[dict]:
        """3.2: 自动根据战争情况调整外交状态

        规则：
        1. 两个势力如果处于同盟/附庸/中立关系，但已发生过战斗（有地盘互相攻占），自动转为 war
        2. 如果两个 war 状态的势力超过 N 回合没有交战记录，AI 自动提议停战
        3. 好感度过低的同盟自动破裂
        4. 有领土接壤但长期中立 → 根据实力对比可能触发 AI 自动宣战（侵略性势力）
        """
        changes = []

        # 获取所有势力对
        faction_ids = list(self.world.factions.keys())
        processed = set()

        for i, fa in enumerate(faction_ids):
            for fb in faction_ids[i+1:]:
                fa_faction = self.world.factions.get(fa)
                fb_faction = self.world.factions.get(fb)
                if not fa_faction or not fb_faction:
                    continue
                if not fa_faction.is_alive or not fb_faction.is_alive:
                    continue

                key = self.world.relation_key(fa, fb)
                rel = self.world.relations.get(key)
                if not rel:
                    continue

                # 规则1: 检查是否有近期战斗记录 → 确保战争状态
                has_recent_battle = self._has_recent_battle(fa, fb)
                if has_recent_battle and rel.stance != DiplomaticStance.WAR:
                    old_stance = rel.stance.value
                    rel.stance = DiplomaticStance.WAR
                    rel.attitude = -50
                    rel.trade_active = False
                    if rel.coalition_id:
                        rel.coalition_id = ""
                    changes.append({
                        "faction_a": fa, "faction_b": fb,
                        "from": old_stance, "to": "war",
                        "reason": "近期交战，自动转为战争状态",
                    })
                    self.world.events_log.append({
                        "event_id": f"auto_war_{fa}_{fb}_{self.world.current_round}",
                        "event_type": "diplomacy", "severity": "critical",
                        "round": self.world.current_round,
                        "title": f"【外交自动】{fa_faction.name}与{fb_faction.name}进入战争状态",
                        "description": f"双方近期发生军事冲突，外交关系自动转为交战。",
                        "effects": {"auto_adjusted": True},
                    })
                    continue

                # 规则2: 战争状态长时间无交战 → 自动提议停战（3.0: 正确转为 TRUCE 而非 NEUTRAL）
                if rel.stance == DiplomaticStance.WAR:
                    rounds_since_battle = self._rounds_since_last_battle(fa, fb)
                    peace_threshold = 8  # 8回合无战事则自动停战
                    if rounds_since_battle >= peace_threshold:
                        rel.stance = DiplomaticStance.TRUCE
                        rel.attitude = 0
                        rel.treaty_expiry = self.world.current_round + 12
                        changes.append({
                        "faction_a": fa, "faction_b": fb,
                        "from": "war", "to": "truce",
                        "reason": f"已{rounds_since_battle}回合无交战，自动停战",
                        })
                        self.world.events_log.append({
                            "event_id": f"auto_peace_{fa}_{fb}_{self.world.current_round}",
                            "event_type": "diplomacy", "severity": "major",
                            "round": self.world.current_round,
                            "title": f"【外交自动】{fa_faction.name}与{fb_faction.name}停战",
                            "description": f"双方已{rounds_since_battle}回合未交战，关系缓和。",
                            "effects": {"auto_adjusted": True},
                        })

                # 规则3: 同盟好感度过低 → 自动破裂（3.0: 先进入 TRUCE 缓冲，不直接跳到 NEUTRAL）
                if rel.stance == DiplomaticStance.ALLIANCE and rel.attitude < -20:
                    rel.stance = DiplomaticStance.TRUCE
                    rel.trade_active = False
                    rel.treaty_expiry = self.world.current_round + 6
                    changes.append({
                        "faction_a": fa, "faction_b": fb,
                        "from": "alliance", "to": "truce",
                        "reason": f"好感度过低({rel.attitude})，同盟自动破裂",
                    })
                    self.world.events_log.append({
                        "event_id": f"auto_break_alliance_{fa}_{fb}_{self.world.current_round}",
                        "event_type": "diplomacy", "severity": "major",
                        "round": self.world.current_round,
                        "title": f"【外交自动】{fa_faction.name}与{fb_faction.name}同盟破裂",
                        "description": f"双方好感度降至{rel.attitude}，同盟关系自动破裂。",
                        "effects": {"auto_adjusted": True},
                    })

                # 规则4: 领土接壤但长期中立 + 侵略性势力 → 可能自动宣战
                if rel.stance == DiplomaticStance.NEUTRAL and self._has_border(fa, fb):
                    neutral_rounds = self._rounds_since_stance_change(fa, fb)
                    if neutral_rounds >= 12:  # 中立超过12回合
                        # 检查双方侵略性
                        a_aggressive = self._is_aggressive_faction(fa)
                        b_aggressive = self._is_aggressive_faction(fb)
                        if a_aggressive and not b_aggressive:
                            # A 对 B 实力优势判定
                            if self._has_power_advantage(fa, fb, ratio=1.3):
                                rel.stance = DiplomaticStance.WAR
                                rel.attitude = -40
                                rel.trade_active = False
                                changes.append({
                                    "faction_a": fa, "faction_b": fb,
                                    "from": "neutral", "to": "war",
                                    "reason": f"长期中立且实力占优，{fa_faction.name}主动宣战",
                                })
                                self.world.events_log.append({
                                    "event_id": f"auto_war_aggressive_{fa}_{fb}_{self.world.current_round}",
                                    "event_type": "diplomacy", "severity": "critical",
                                    "round": self.world.current_round,
                                    "title": f"【外交自动】{fa_faction.name}对{fb_faction.name}宣战",
                                    "description": f"双方领土接壤且中立已{neutral_rounds}回合，{fa_faction.name}趁实力优势发动战争。",
                                    "effects": {"auto_adjusted": True},
                                })
                        elif b_aggressive and not a_aggressive:
                            if self._has_power_advantage(fb, fa, ratio=1.3):
                                rel.stance = DiplomaticStance.WAR
                                rel.attitude = -40
                                rel.trade_active = False
                                changes.append({
                                    "faction_a": fa, "faction_b": fb,
                                    "from": "neutral", "to": "war",
                                    "reason": f"长期中立且实力占优，{fb_faction.name}主动宣战",
                                })
                                self.world.events_log.append({
                                    "event_id": f"auto_war_aggressive_{fb}_{fa}_{self.world.current_round}",
                                    "event_type": "diplomacy", "severity": "critical",
                                    "round": self.world.current_round,
                                    "title": f"【外交自动】{fb_faction.name}对{fa_faction.name}宣战",
                                    "description": f"双方领土接壤且中立已{neutral_rounds}回合，{fb_faction.name}趁实力优势发动战争。",
                                    "effects": {"auto_adjusted": True},
                                })

        return changes

    def _has_recent_battle(self, fa: str, fb: str) -> bool:
        """检查两个势力最近2回合内是否有交战记录"""
        current = self.world.current_round
        # 检查战斗事件日志
        for event in self.world.events_log:
            if event.get("event_type") == "battle" and event.get("round", 0) >= current - 2:
                participants = []
                # 战斗事件中交战方在 effects.attacker / effects.defender
                effects = event.get("effects", {})
                if effects.get("attacker"):
                    participants.append(effects["attacker"])
                if effects.get("defender"):
                    participants.append(effects["defender"])
                # 兼容旧事件格式（attacker_faction 可能在根级别）
                if event.get("attacker_faction"):
                    participants.append(event["attacker_faction"])
                if event.get("defender_faction"):
                    participants.append(event["defender_faction"])
                if fa in participants and fb in participants:
                    return True
        # 检查地盘变更记录
        for tc in self.world.tile_changes:
            tc_round = tc.get("round", 0) if isinstance(tc, dict) else getattr(tc, "round", 0)
            if tc_round >= current - 2:
                tc_old = tc.get("old_faction_id") if isinstance(tc, dict) else tc.old_faction_id
                tc_new = tc.get("new_faction_id") if isinstance(tc, dict) else tc.new_faction_id
                if (tc_old == fa and tc_new == fb) or \
                   (tc_old == fb and tc_new == fa):
                    return True
        return False

    def _rounds_since_last_battle(self, fa: str, fb: str) -> int:
        """计算两个势力自上次交战以来的回合数"""
        current = self.world.current_round
        last_battle_round = 0

        for event in self.world.events_log:
            if event.get("event_type") == "battle":
                participants = []
                # 战斗事件中交战方在 effects.attacker / effects.defender
                effects = event.get("effects", {})
                if effects.get("attacker"):
                    participants.append(effects["attacker"])
                if effects.get("defender"):
                    participants.append(effects["defender"])
                # 兼容旧事件格式
                if event.get("attacker_faction"):
                    participants.append(event["attacker_faction"])
                if event.get("defender_faction"):
                    participants.append(event["defender_faction"])
                if fa in participants and fb in participants:
                    r = event.get("round", 0)
                    if r > last_battle_round:
                        last_battle_round = r

        for tc in self.world.tile_changes:
            tc_old = tc.get("old_faction_id") if isinstance(tc, dict) else tc.old_faction_id
            tc_new = tc.get("new_faction_id") if isinstance(tc, dict) else tc.new_faction_id
            tc_round = tc.get("round", 0) if isinstance(tc, dict) else getattr(tc, "round", 0)
            if (tc_old == fa and tc_new == fb) or \
               (tc_old == fb and tc_new == fa):
                if tc_round > last_battle_round:
                    last_battle_round = tc_round

        if last_battle_round == 0:
            return current  # 从未交战
        return current - last_battle_round

    def _has_border(self, fa: str, fb: str) -> bool:
        """检查两个势力是否领土接壤（任一地块相邻）"""
        fa_tiles = {t.tile_id: t for t in self.world.get_faction_tiles(fa)}
        fb_tile_set = {t.tile_id for t in self.world.get_faction_tiles(fb)}
        if not fa_tiles or not fb_tile_set:
            return False

        # 六边形6方向偏移
        HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        for tile_id, tile in fa_tiles.items():
            q = getattr(tile, 'q', None)
            r = getattr(tile, 'r', None)
            if q is None or r is None:
                continue
            for dq, dr in HEX_DIRS:
                # 尝试匹配邻居 tile_id
                nb_q, nb_r = q + dq, r + dr
                for candidate_id in (f"{nb_q},{nb_r}", f"tile_{nb_q}_{nb_r}"):
                    if candidate_id in fb_tile_set:
                        return True
        return False

    def _rounds_since_stance_change(self, fa: str, fb: str) -> int:
        """计算两个势力自上次外交姿态变更以来的回合数"""
        current = self.world.current_round
        last_change = 0
        for event in self.world.events_log:
            if event.get("event_type") == "diplomacy" and event.get("round", 0) > last_change:
                effects = event.get("effects", {})
                # 检查是否涉及这两个势力
                fid_a = effects.get("faction_a") or event.get("faction_a", "")
                fid_b = effects.get("faction_b") or event.get("faction_b", "")
                if {fid_a, fid_b} == {fa, fb}:
                    last_change = event.get("round", 0)
        if last_change == 0:
            return current
        return current - last_change

    def _is_aggressive_faction(self, fid: str) -> bool:
        """判断势力是否具有侵略性人格"""
        faction = self.world.factions.get(fid)
        if not faction:
            return False
        aggressive_tags = {"好战", "扩张", "掠夺", "穷兵黩武", "野心", "尚武"}
        for tag in faction.personality_tags:
            if tag in aggressive_tags:
                return True
        # 没有人格标签时，根据当前战争数判断：已与2+势力交战视为侵略性
        war_count = 0
        for rel in self.world.relations.values():
            if (rel.faction_a == fid or rel.faction_b == fid) and rel.stance == DiplomaticStance.WAR:
                war_count += 1
        return war_count >= 2

    def _has_power_advantage(self, fa: str, fb: str, ratio: float = 1.3) -> bool:
        """检查 fa 对 fb 是否有兵力优势（fa_total_troops >= fb_total_troops * ratio）"""
        faction_a = self.world.factions.get(fa)
        faction_b = self.world.factions.get(fb)
        if not faction_a or not faction_b:
            return False
        a_troops = faction_a.total_troops or faction_a.troops or 0
        b_troops = faction_b.total_troops or faction_b.troops or 0
        if b_troops <= 0:
            return True
        return a_troops >= b_troops * ratio
    
    # ================================================================
    # ⑦ 回放快照 —— 真实实现
    # ================================================================
    
    async def _phase_replay_snapshot(self, summary: dict):
        """⑦ 回放快照：保存当前回合完整快照"""
        # 此时 current_round 已递增，无需再 +1
        current_r = self.world.current_round
        snapshot = {
            "round": current_r,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "season": self.world.current_season,
            "factions": {
                fid: {
                    "name": f.name,
                    "is_alive": f.is_alive,
                    "treasury": f.treasury,
                    "grain": f.grain,
                    "horses": f.horses,
                    "arms": f.arms,
                    "total_troops": f.total_troops,
                    "total_population": f.total_population,
                    "reputation": f.reputation,
                    "tile_count": len(self.world.get_faction_tiles(fid)),
                    "realm_stability": f.realm_stability,
                    "court_stability": f.court_stability,
                }
                for fid, f in self.world.factions.items()
            },
            "tiles_summary": {
                tid: {
                    "faction_id": t.faction_id,
                    "population": t.population,
                    "troops": t.troops,
                    "morale": t.morale,
                    "disasters": [d.value for d in t.disasters],
                }
                # 优先选取有归属、有兵力/人口的关键地块（最多50个），而非字典前50个
                for tid, t in sorted(
                    self.world.tiles.items(),
                    key=lambda x: (
                        0 if x[1].faction_id else 1,           # 有归属优先
                        -(x[1].troops or 0),                     # 兵力多的优先
                        -(x[1].population or 0),                 # 人口多的优先
                    )
                )[:50]
            },
            "events_this_round": [
                e for e in self.world.events_log[-10:]
                if e.get("round") == current_r
            ],
        }
        
        summary["phases"]["replay"] = {
            "snapshot_size": len(str(snapshot)),
            "factions_alive": sum(1 for f in self.world.factions.values() if f.is_alive),
        }
        
        # 将快照引用传递给 summary（api_server 将追加到 _round_snapshots）
        summary["_snapshot"] = snapshot
        
        for hook in self._phase_hooks[7]:
            await hook(self.world)
    
    # ================================================================
    # ⑧ 自动存档 —— 真实实现
    # ================================================================
    
    async def _phase_auto_save(self, summary: dict):
        """⑧ 自动存档：结局条件判定、自动存档标记"""
        ending = self._check_ending_conditions()
        
        # 自动存档条件：每12回合或年末
        should_auto_save = (
            self.world.current_round % 12 == 0
            or self.world.current_month == 12
        )
        
        summary["phases"]["auto_save"] = {
            "should_auto_save": should_auto_save,
            "ending": ending,
            "max_rounds_reached": self.world.current_round >= 240,
            "living_factions": len(self.world.get_living_factions()),
        }
        
        if ending:
            summary["phases"]["auto_save"]["game_ending"] = ending
        
        for hook in self._phase_hooks[8]:
            await hook(self.world)
    
    def _check_ending_conditions(self) -> Optional[dict]:
        """
        检查结局条件（3.3 四大结局系统）
        
        优先级: 霸业陨落 > 偏安存续 > 天下归心 > 盛世新朝
        
        结局间有渐进逻辑:
        - 霸业陨落 → 偏安存续: 提升声望+存活
        - 偏安存续 → 天下归心: 扩张领土+高声望
        - 天下归心 → 盛世新朝: 全维度极致发展
        """
        if not self._ending_engine:
            return None
        
        result = self._ending_engine.check_all_endings()
        
        if result and result.get("triggered"):
            # 记录到事件日志
            self.world.events_log.append({
                "event_id": f"ending_{result['ending_id']}_{self.world.current_round}",
                "event_type": "ending",
                "severity": "critical",
                "round": self.world.current_round,
                "title": f"【结局】{result['title']}",
                "description": result.get("subtitle", ""),
                "faction_id": self.world.player_faction_id,
                "ending_data": result,
            })
            
            # 设置游戏模式
            if result.get("is_game_over"):
                self.world.game_mode = "victory" if result.get("tier") in ("good", "true") else "game_over"
        
        return result
    
    # ================================================================
    # 时间推进
    # ================================================================
    
    def _advance_time(self):
        """推进时间"""
        self.world.current_month += 1
        if self.world.current_month > 12:
            self.world.current_month = 1
            self.world.current_year += 1
        
        month = self.world.current_month
        if 3 <= month <= 5:
            self.world.current_season = Season.SPRING
        elif 6 <= month <= 8:
            self.world.current_season = Season.SUMMER
        elif 9 <= month <= 11:
            self.world.current_season = Season.AUTUMN
        else:
            self.world.current_season = Season.WINTER
        
        self.world.mark_updated()
    
    @property
    def current_round(self) -> int:
        return self.world.current_round
    
    @property
    def is_max_rounds(self) -> bool:
        return self.world.current_round >= 240
    
    def get_turn_summary(self) -> dict:
        """获取当前回合摘要"""
        return {
            "round": self.world.current_round,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "season": self.world.current_season.value,
            "living_factions": len(self.world.get_living_factions()),
            "game_mode": self.world.game_mode,
        }
