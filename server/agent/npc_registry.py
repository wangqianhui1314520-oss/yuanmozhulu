"""
NPC Registry - 谋士数据管理与势力映射

职责：
1. 加载 & 缓存 NPC 文臣数据（npc_ministers.json）
2. 势力 ↔ 谋士团双向映射
3. 按势力/角色/专长索引 NPC
4. NPC 人设 Prompt 模板管理

从 a1_advisor.py 中提取，与 AI 对话逻辑解耦。
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.agent.npc_registry")

# ================================================================
# Faction ID 归一化映射（新旧格式互转）
# ================================================================
FACTION_ID_MAP_NEW_TO_OLD: dict[str, str] = {
    "faction_zhuyuanzhang": "ruler_zhuyuan",
    "faction_chenyouliang": "ruler_chen",
    "faction_zhangshicheng": "ruler_zhang",
    "faction_wangbaobao": "ruler_wang",
    "faction_mingyuzhen": "ruler_ming",
    "faction_fangguozhen": "ruler_fang",
    "faction_mobei": "ruler_tatar",
    "faction_xushouhui": "ruler_xushou",
    "faction_yuan": "ruler_yuan",
}
FACTION_ID_MAP_OLD_TO_NEW: dict[str, str] = {v: k for k, v in FACTION_ID_MAP_NEW_TO_OLD.items()}

# 势力名称映射
FACTION_NAMES: dict[str, str] = {
    "ruler_zhuyuan": "西吴",
    "ruler_yuan": "元廷",
    "ruler_chen": "汉国",
    "ruler_zhang": "周国",
    "ruler_wang": "河南",
    "ruler_ming": "大夏",
    "ruler_fang": "浙东",
    "ruler_tatar": "漠北",
    "ruler_xushou": "天完",
}


def normalize_faction_id(faction_id: str) -> str:
    """将任意格式的 faction_id 归一化为旧格式（NPC 数据使用的格式）"""
    if not faction_id:
        return ""
    if faction_id.startswith("ruler_"):
        return faction_id
    if faction_id in FACTION_ID_MAP_NEW_TO_OLD:
        return FACTION_ID_MAP_NEW_TO_OLD[faction_id]
    return faction_id


def denormalize_faction_id(faction_id: str) -> str:
    """将旧格式 faction_id 转为新格式（供前端使用）"""
    if not faction_id:
        return ""
    return FACTION_ID_MAP_OLD_TO_NEW.get(faction_id, faction_id)


def get_faction_name(faction_id: str) -> str:
    """获取势力中文名称"""
    normalized = normalize_faction_id(faction_id)
    return FACTION_NAMES.get(normalized, faction_id)


class NPCRegistry:
    """NPC 文臣注册中心 —— 单例"""

    _instance: Optional["NPCRegistry"] = None

    def __new__(cls) -> "NPCRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._npc_cache: dict[str, dict] = {}
        self._npc_by_faction: dict[str, list[dict]] = {}
        self._npc_by_role: dict[str, list[dict]] = {}
        self._faction_advisers: dict = {}
        self._prompt_templates: dict[str, str] = {}
        self._load_data()

    # ================================================================
    # 数据加载
    # ================================================================

    def _load_data(self):
        """加载 NPC 数据和势力谋士团配置"""
        npc_path = Path(__file__).parent.parent / "data" / "npc_ministers.json"
        try:
            with open(npc_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._npc_cache = {npc["npc_id"]: npc for npc in data.get("ministers", [])}
            self._faction_advisers = data.get("_faction_advisers", {})

            # 按势力分组
            self._npc_by_faction = {}
            for npc in data.get("ministers", []):
                fid = npc.get("faction", "_wandering")
                if fid not in self._npc_by_faction:
                    self._npc_by_faction[fid] = []
                self._npc_by_faction[fid].append(npc)

            # 按角色分组
            self._npc_by_role = {}
            for npc in data.get("ministers", []):
                role = npc.get("role", "other")
                if role not in self._npc_by_role:
                    self._npc_by_role[role] = []
                self._npc_by_role[role].append(npc)

            logger.info(
                f"NPC Registry 加载完成: {len(self._npc_cache)} 人, "
                f"{len(self._npc_by_faction)} 个势力, "
                f"{len(self._npc_by_role)} 种角色"
            )
        except Exception as e:
            logger.error(f"NPC 数据加载失败: {e}")
            self._npc_cache = {}

    def reload(self):
        """热重载 NPC 数据"""
        self._npc_cache.clear()
        self._npc_by_faction.clear()
        self._npc_by_role.clear()
        self._faction_advisers.clear()
        self._prompt_templates.clear()
        self._load_data()

    def reset_to_template(self):
        """重置 NPC 状态为模板原始数据（新开局时调用）"""
        self._npc_cache.clear()
        self._npc_by_faction.clear()
        self._npc_by_role.clear()
        self._faction_advisers.clear()
        self._prompt_templates.clear()
        self._load_data()
        logger.info("NPC Registry 已重置为模板数据")

    def export_runtime_state(self) -> dict:
        """
        导出当前所有 NPC 的运行时状态（供存档使用）。

        返回: { npc_id: {alive, executed, loyalty, ambition, wisdom, faction, ...}, ... }
        只导出与模板不同的动态字段，减小存档体积。
        """
        state = {}
        for npc_id, npc in self._npc_cache.items():
            dynamic = {
                "alive": npc.get("alive", True),
                "executed": npc.get("executed", False),
                "loyalty": npc.get("loyalty", 80),
                "ambition": npc.get("ambition", 30),
                "wisdom": npc.get("wisdom", 80),
                "faction": npc.get("faction", ""),
            }
            # 仅当有状态变更时才记录
            if npc.get("death_round", 0):
                dynamic["death_round"] = npc["death_round"]
            if npc.get("execution_reason"):
                dynamic["execution_reason"] = npc["execution_reason"]
            if npc.get("faction_change_reason"):
                dynamic["faction_change_reason"] = npc["faction_change_reason"]
            if npc.get("title"):
                dynamic["title"] = npc["title"]
            if npc.get("role_label"):
                dynamic["role_label"] = npc["role_label"]
            state[npc_id] = dynamic
        return state

    def import_runtime_state(self, state: dict):
        """
        从存档恢复 NPC 运行时状态（读档时调用）。

        Args:
            state: export_runtime_state() 导出的字典
        """
        if not state:
            return

        for npc_id, dynamic in state.items():
            npc = self._npc_cache.get(npc_id)
            if not npc:
                continue
            for key, value in dynamic.items():
                npc[key] = value

        # 重建按势力的索引
        self._npc_by_faction = {}
        for npc in self._npc_cache.values():
            fid = npc.get("faction", "_wandering")
            if fid not in self._npc_by_faction:
                self._npc_by_faction[fid] = []
            self._npc_by_faction[fid].append(npc)

        # 重建按角色的索引
        self._npc_by_role = {}
        for npc in self._npc_cache.values():
            role = npc.get("role", "other")
            if role not in self._npc_by_role:
                self._npc_by_role[role] = []
            self._npc_by_role[role].append(npc)

        logger.info(f"NPC 运行时状态恢复完成（{len(state)} 条记录）")

    # ================================================================
    # NPC 查询
    # ================================================================

    def get_npc(self, npc_id: str) -> Optional[dict]:
        """获取单个 NPC 完整信息"""
        return self._npc_cache.get(npc_id)

    def get_npc_field(self, npc_id: str, field: str, default=None):
        """安全获取 NPC 字段"""
        npc = self._npc_cache.get(npc_id)
        return npc.get(field, default) if npc else default

    def npc_exists(self, npc_id: str) -> bool:
        return npc_id in self._npc_cache

    # ================================================================
    # 按势力查询
    # ================================================================

    def get_faction_npcs(self, faction_id: str) -> list[dict]:
        """获取指定势力的所有 NPC（含流浪谋士）"""
        normalized = normalize_faction_id(faction_id)
        native = self._npc_by_faction.get(normalized, [])
        wanderers = self._npc_by_faction.get("_wandering", [])
        return native + wanderers

    def get_faction_native_npcs(self, faction_id: str) -> list[dict]:
        """获取指定势力专属 NPC（不含流浪谋士）"""
        normalized = normalize_faction_id(faction_id)
        return self._npc_by_faction.get(normalized, [])

    def get_faction_adviser_info(self, faction_id: str) -> dict:
        """获取势力的谋士团元信息"""
        normalized = normalize_faction_id(faction_id)
        return self._faction_advisers.get(normalized, {})

    def get_faction_adviser_team_ids(self, faction_id: str) -> list[str]:
        """获取势力的谋士团 NPC ID 列表"""
        info = self.get_faction_adviser_info(faction_id)
        return info.get("adviser_team", [])

    # ================================================================
    # 按角色查询
    # ================================================================

    def get_npcs_by_role(self, role: str) -> list[dict]:
        return self._npc_by_role.get(role, [])

    def get_npcs_by_roles(self, roles: list[str]) -> list[dict]:
        """获取多个角色的 NPC（去重）"""
        seen = set()
        result = []
        for role in roles:
            for npc in self._npc_by_role.get(role, []):
                nid = npc["npc_id"]
                if nid not in seen:
                    seen.add(nid)
                    result.append(npc)
        return result

    # ================================================================
    # 序列化（供前端使用）
    # ================================================================

    def serialize_npc(self, npc: dict) -> dict:
        """将 NPC 数据序列化为前端可用格式"""
        npc_faction_raw = npc.get("faction", "_wandering")
        return {
            "npc_id": npc["npc_id"],
            "name": npc["name"],
            "style_name": npc.get("style_name", ""),
            "title": npc.get("title", ""),
            "role": npc.get("role", ""),
            "role_label": npc.get("role_label", ""),
            "specialties": npc.get("specialties", []),
            "personality": npc.get("personality", ""),
            "greeting": npc.get("greeting", ""),
            "speaking_style": npc.get("speaking_style", ""),
            "faction": denormalize_faction_id(npc_faction_raw),
            "model_temp": npc.get("model_temp", 0.7),
            "wisdom": npc.get("wisdom", 80),
            "loyalty": npc.get("loyalty", 80),
            "ambition": npc.get("ambition", 30),
        }

    def list_npcs(
        self,
        role_filter: str = "",
        faction_id: str = "",
        include_dead: bool = False,
    ) -> list[dict]:
        """获取 NPC 列表（序列化格式，供 API 层使用）"""
        result = []
        normalized_fid = normalize_faction_id(faction_id) if faction_id else ""

        for npc_id, npc in self._npc_cache.items():
            # 默认过滤死亡 NPC
            if not include_dead and not self.is_npc_alive(npc_id):
                continue

            if role_filter and npc.get("role") != role_filter:
                continue

            npc_faction = npc.get("faction", "_wandering")
            if normalized_fid:
                # 匹配该势力 + 流浪谋士
                if npc_faction != normalized_fid and npc_faction != "_wandering":
                    continue

            result.append(self.serialize_npc(npc))

        return result

    def list_faction_advisers(self, faction_id: str) -> list[dict]:
        """获取势力谋士团成员（序列化格式）"""
        return self.list_npcs(faction_id=faction_id)

    def select_debate_npcs(
        self, faction_id: str, count: int = 4
    ) -> list[str]:
        """为廷议选取 NPC（不同角色优先，不足则补充，自动排除死亡 NPC）"""
        normalized = normalize_faction_id(faction_id)

        # 优先从谋士团选取
        adviser_team = self.get_faction_adviser_team_ids(faction_id)
        roles_seen: set[str] = set()
        selected: list[str] = []

        for nid in adviser_team:
            npc = self._npc_cache.get(nid)
            if not npc or not self.is_npc_alive(nid):
                continue
            role = npc.get("role", "")
            if role not in roles_seen:
                roles_seen.add(role)
                selected.append(nid)
            if len(selected) >= count:
                return selected

        # 补充其他 NPC（不同角色）
        for nid, npc in self._npc_cache.items():
            if nid in selected or not self.is_npc_alive(nid):
                continue
            role = npc.get("role", "")
            if role not in roles_seen:
                selected.append(nid)
                roles_seen.add(role)
            if len(selected) >= count:
                break

        return selected[:count]

    # ================================================================
    # Prompt 模板管理
    # ================================================================

    def load_prompt_template(self, template_name: str) -> str:
        """加载 NPC 对话 Prompt 模板"""
        if template_name in self._prompt_templates:
            return self._prompt_templates[template_name]

        prompt_path = Path(__file__).parent.parent / "agent_prompts" / f"{template_name}.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._prompt_templates[template_name] = content
            return content
        except Exception:
            logger.warning(f"Prompt 模板加载失败: {template_name}")
            return ""

    # ================================================================
    # NPC 动态状态更新 (3.3 新增)
    # ================================================================

    def update_npc_state(
        self, npc_id: str, field: str, value,
        persist: bool = True,
    ) -> bool:
        """
        动态更新 NPC 状态字段

        支持更新的字段: loyalty, wisdom, ambition, faction, title,
                       role_label, alive, personality

        Args:
            npc_id: NPC ID
            field: 要更新的字段名
            value: 新值
            persist: 是否持久化到 JSON 文件

        Returns:
            是否更新成功
        """
        npc = self._npc_cache.get(npc_id)
        if not npc:
            logger.warning(f"更新 NPC 状态失败: {npc_id} 不存在")
            return False

        old_value = npc.get(field)
        npc[field] = value

        # 数值字段范围限制
        if field in ("loyalty",):
            npc[field] = max(0, min(100, int(value)))
        elif field in ("wisdom",):
            npc[field] = max(0, min(100, int(value)))
        elif field in ("ambition",):
            npc[field] = max(0, min(100, int(value)))

        logger.info(
            f"[NPC状态] {npc['name']}({npc_id}).{field}: "
            f"{old_value} → {npc[field]}"
        )

        if persist:
            self._persist_npc_data()

        return True

    def modify_npc_stat(
        self, npc_id: str, field: str, delta: int,
        persist: bool = True,
    ) -> bool:
        """
        增量修改 NPC 数值属性

        Args:
            npc_id: NPC ID
            field: 字段名 (loyalty/wisdom/ambition)
            delta: 增量值
            persist: 是否持久化
        """
        npc = self._npc_cache.get(npc_id)
        if not npc:
            return False

        current = npc.get(field, 0)
        return self.update_npc_state(npc_id, field, current + delta, persist)

    def kill_npc(self, npc_id: str, persist: bool = True) -> bool:
        """
        标记 NPC 为死亡状态

        死亡的 NPC:
        - alive 字段设为 False
        - 从势力 NPC 列表中移除
        - 保留在 _npc_cache 中以供历史引用
        """
        npc = self._npc_cache.get(npc_id)
        if not npc:
            return False

        npc["alive"] = False
        npc["death_round"] = getattr(self, '_current_round', 0)

        # 从势力分组中移除
        faction = npc.get("faction", "")
        if faction and faction in self._npc_by_faction:
            self._npc_by_faction[faction] = [
                n for n in self._npc_by_faction[faction]
                if n.get("npc_id") != npc_id
            ]

        # 从角色分组中移除
        role = npc.get("role", "")
        if role and role in self._npc_by_role:
            self._npc_by_role[role] = [
                n for n in self._npc_by_role[role]
                if n.get("npc_id") != npc_id
            ]

        logger.info(f"[NPC死亡] {npc['name']}({npc_id}) 已标记为死亡")

        if persist:
            self._persist_npc_data()

        return True

    def execute_npc(self, npc_id: str, reason: str = "",
                    round_number: int = 0) -> bool:
        """
        处决 NPC（标记死亡并记录原因）

        处决会产生连锁反应:
        - 其他 NPC 的好感度和信任度下降（由 NPCMemoryManager 处理）
        - 同派系 NPC 关系恶化（由 NPCRelationManager 处理）
        """
        npc = self._npc_cache.get(npc_id)
        if not npc:
            return False

        npc["alive"] = False
        npc["executed"] = True
        npc["execution_reason"] = reason
        npc["death_round"] = round_number

        self.kill_npc(npc_id, persist=False)
        self._persist_npc_data()

        logger.info(
            f"[NPC处决] {npc['name']}({npc_id}) 被处决"
            + (f"（原因：{reason}）" if reason else "")
        )
        return True

    def change_npc_faction(
        self, npc_id: str, new_faction_id: str,
        reason: str = "", persist: bool = True,
    ) -> bool:
        """
        NPC 更换势力（叛变/投靠）

        会更新所有相关索引
        """
        npc = self._npc_cache.get(npc_id)
        if not npc:
            return False

        old_faction = npc.get("faction", "")
        normalized_new = normalize_faction_id(new_faction_id)

        # 从旧势力移除
        if old_faction and old_faction in self._npc_by_faction:
            self._npc_by_faction[old_faction] = [
                n for n in self._npc_by_faction[old_faction]
                if n.get("npc_id") != npc_id
            ]

        # 更新 faction
        npc["faction"] = normalized_new
        npc["faction_change_reason"] = reason

        # 加入新势力
        if normalized_new not in self._npc_by_faction:
            self._npc_by_faction[normalized_new] = []
        self._npc_by_faction[normalized_new].append(npc)

        logger.info(
            f"[NPC叛变] {npc['name']}({npc_id}): "
            f"{old_faction} → {normalized_new}"
            + (f"（原因：{reason}）" if reason else "")
        )

        if persist:
            self._persist_npc_data()

        return True

    def get_alive_npcs(self, faction_id: str = "") -> list[dict]:
        """
        获取存活的 NPC 列表（排除已死亡 NPC）

        Args:
            faction_id: 势力 ID（空字符串表示全部势力）
        """
        if faction_id:
            normalized = normalize_faction_id(faction_id)
            candidates = self._npc_by_faction.get(normalized, [])
        else:
            candidates = list(self._npc_cache.values())

        return [
            npc for npc in candidates
            if npc.get("alive", True) and not npc.get("executed", False)
        ]

    def get_dead_npcs(self) -> list[dict]:
        """获取已死亡的 NPC 列表"""
        return [
            npc for npc in self._npc_cache.values()
            if not npc.get("alive", True) or npc.get("executed", False)
        ]

    def is_npc_alive(self, npc_id: str) -> bool:
        """检查 NPC 是否存活"""
        npc = self._npc_cache.get(npc_id)
        if not npc:
            return False
        return npc.get("alive", True) and not npc.get("executed", False)

    def apply_game_event_to_npcs(
        self, event_type: str, affected_npc_ids: list[str],
        stat_changes: dict = None, round_number: int = 0,
    ):
        """
        批量应用游戏事件到 NPC 状态

        Args:
            event_type: 事件类型 (rebellion/execution/promotion/reward/punishment/battle)
            affected_npc_ids: 受影响的 NPC ID 列表
            stat_changes: 属性变化 {"loyalty": delta, "ambition": delta, ...}
            round_number: 当前回合
        """
        stat_changes = stat_changes or {}

        event_effects = {
            "rebellion": {
                "loyalty": -20,
                "ambition": 10,
                "description": "参与叛变",
            },
            "execution_witness": {
                "loyalty": -10,
                "ambition": -5,
                "description": "目睹处决",
            },
            "promotion": {
                "loyalty": 10,
                "ambition": 5,
                "description": "获得升迁",
            },
            "reward": {
                "loyalty": 5,
                "description": "获得赏赐",
            },
            "punishment": {
                "loyalty": -10,
                "ambition": -5,
                "description": "遭受惩罚",
            },
            "battle_victory": {
                "loyalty": 5,
                "ambition": 3,
                "description": "战斗胜利",
            },
            "battle_defeat": {
                "loyalty": -5,
                "ambition": -3,
                "description": "战斗失败",
            },
        }

        effect = event_effects.get(event_type, stat_changes)
        if isinstance(effect, dict) and "description" in effect:
            desc = effect["description"]
            for npc_id in affected_npc_ids:
                for field, delta in effect.items():
                    if field != "description" and isinstance(delta, (int, float)):
                        self.modify_npc_stat(npc_id, field, int(delta), persist=False)
        else:
            # 自定义 stat_changes
            for npc_id in affected_npc_ids:
                for field, delta in stat_changes.items():
                    self.modify_npc_stat(npc_id, field, int(delta), persist=False)

        self._persist_npc_data()

    # ================================================================
    # 数据持久化
    # ================================================================

    def _persist_npc_data(self, player_id: str = ""):
        """
        将当前 NPC 运行时状态持久化到玩家隔离目录（不再覆盖模板文件）。

        v3.5 修复：原实现直接覆盖 server/data/npc_ministers.json（全局模板），
        导致：(1) NPC 死亡/叛变后永久污染模板，新开局 NPC 缺失；
              (2) 多玩家共享同一文件，互相覆盖；(3) 存档不含 NPC 状态，读档后状态丢失。

        现在写入 data/players/{player_id}/npc_runtime_state.json，
        与 npc_memory/npc_relations 保持一致的玩家隔离架构。
        存档文件中的 NPC 状态由 export_runtime_state/import_runtime_state 管理。
        """
        try:
            # 确定运行时状态文件路径
            if player_id:
                runtime_dir = Path(__file__).parent.parent.parent / "data" / "players" / player_id
            else:
                # 无玩家 ID 时写入全局降级目录（兼容旧行为，但不再覆盖模板）
                runtime_dir = Path(__file__).parent.parent / "data"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            npc_path = runtime_dir / "npc_runtime_state.json"

            # 只导出动态状态（不含静态模板数据）
            state_data = {
                "version": "3.5",
                "description": "元末逐鹿 - NPC 运行时状态（不覆盖模板）",
                "npcs": self.export_runtime_state(),
            }

            with open(npc_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"NPC 运行时状态已持久化（{len(state_data['npcs'])} 条）→ {npc_path}")
        except Exception as e:
            logger.error(f"NPC 运行时状态持久化失败: {e}")

    def _load_runtime_state(self, player_id: str):
        """
        从玩家隔离目录加载 NPC 运行时状态（服务器重启后恢复）。

        仅在内存中没有运行时状态时调用（即首次初始化后），
        避免覆盖活跃游戏中的状态。
        """
        runtime_dir = Path(__file__).parent.parent.parent / "data" / "players" / player_id
        npc_path = runtime_dir / "npc_runtime_state.json"
        if not npc_path.exists():
            return

        try:
            with open(npc_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            npcs_state = data.get("npcs", {})
            if npcs_state:
                self.import_runtime_state(npcs_state)
                logger.info(f"NPC 运行时状态已加载（{len(npcs_state)} 条）← {npc_path}")
        except Exception as e:
            logger.warning(f"加载 NPC 运行时状态失败（将使用模板默认值）: {e}")

    def set_current_round(self, round_number: int):
        """设置当前回合号（用于记录事件时间）"""
        self._current_round = round_number

    # ================================================================
    # 序列化增强（包含动态状态）
    # ================================================================

    def serialize_npc_dynamic(self, npc: dict) -> dict:
        """
        序列化 NPC 数据（包含动态状态信息）
        比 serialize_npc 多返回 alive、executed 等运行时字段
        """
        base = self.serialize_npc(npc)
        base.update({
            "alive": npc.get("alive", True),
            "executed": npc.get("executed", False),
            "death_round": npc.get("death_round", 0),
            "execution_reason": npc.get("execution_reason", ""),
            "faction_change_reason": npc.get("faction_change_reason", ""),
        })
        return base

    # ================================================================
    # 关系判断
    # ================================================================

    @staticmethod
    def get_npc_relation(npc: dict, colleague: dict) -> str:
        """根据两个NPC的属性和角色判断他们的关系"""
        relations = []
        role = npc.get("role", "")
        col_role = colleague.get("role", "")

        if role == col_role:
            if npc.get("ambition", 30) > 60 or colleague.get("ambition", 30) > 60:
                relations.append("存在竞争")
            else:
                relations.append("志同道合")

        military_roles = {"general", "strategist"}
        civil_roles = {"chancellor", "economist", "scholar", "reformer"}
        if role in military_roles and col_role in civil_roles:
            relations.append("文武相济，互相尊重")
        elif role in civil_roles and col_role in military_roles:
            relations.append("文武相济，互相尊重")

        loyalty_diff = abs(npc.get("loyalty", 80) - colleague.get("loyalty", 80))
        if loyalty_diff > 30:
            relations.append("有时意见相左")

        wisdom_diff = abs(npc.get("wisdom", 80) - colleague.get("wisdom", 80))
        if wisdom_diff > 20:
            if npc.get("wisdom", 80) > colleague.get("wisdom", 80):
                relations.append("你对他多有提点")
            else:
                relations.append("你对他颇为敬重")

        if not relations:
            relations.append("和睦相处")

        return "，".join(relations[:2])


# ================================================================
# 模块级便捷函数
# ================================================================

def get_npc_registry() -> NPCRegistry:
    return NPCRegistry()
