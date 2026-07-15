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
    ) -> list[dict]:
        """获取 NPC 列表（序列化格式，供 API 层使用）"""
        result = []
        normalized_fid = normalize_faction_id(faction_id) if faction_id else ""

        for npc_id, npc in self._npc_cache.items():
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
        """为廷议选取 NPC（不同角色优先，不足则补充）"""
        normalized = normalize_faction_id(faction_id)

        # 优先从谋士团选取
        adviser_team = self.get_faction_adviser_team_ids(faction_id)
        roles_seen: set[str] = set()
        selected: list[str] = []

        for nid in adviser_team:
            npc = self._npc_cache.get(nid)
            if not npc:
                continue
            role = npc.get("role", "")
            if role not in roles_seen:
                roles_seen.add(role)
                selected.append(nid)
            if len(selected) >= count:
                return selected

        # 补充其他 NPC（不同角色）
        for nid, npc in self._npc_cache.items():
            if nid in selected:
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
