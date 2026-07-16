"""
NPC 关系网络 (NPC Relations Network)

职责：
1. NPC之间的好感度/敌意网络
2. 同僚关系动态变化（某NPC反对过另一NPC的观点 → 关系恶化）
3. 派系形成：志同道合的NPC自然结盟

设计原则：
- 异步安全 (asyncio)
- 与 NPCMemoryManager 和 NPCRegistry 无缝集成
- 数据可持久化到 JSON 文件
- 适当的降级和错误处理
- 支持图论算法（派系检测、影响力计算）
"""
from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
from enum import Enum

logger = logging.getLogger("yuanmo.agent.npc_relations")


# ================================================================
# 枚举定义
# ================================================================

class RelationType(Enum):
    """NPC 关系类型"""
    ALLY = "ally"               # 盟友
    FRIEND = "friend"           # 朋友
    COLLEAGUE = "colleague"     # 同僚（默认）
    RIVAL = "rival"             # 竞争者
    ENEMY = "enemy"             # 敌人
    MENTOR = "mentor"           # 导师
    STUDENT = "student"         # 学生
    KINSHIP = "kinship"         # 亲属
    UNKNOWN = "unknown"         # 未知


class FactionType(Enum):
    """派系类型"""
    REFORM = "reform"           # 改革派
    CONSERVATIVE = "conservative"  # 保守派
    MILITARY = "military"       # 主战派
    PACIFIST = "pacifist"       # 主和派
    LOYALIST = "loyalist"       # 保皇派
    OPPORTUNIST = "opportunist"  # 投机派
    NONE = "none"               # 无派系


# ================================================================
# 数据类定义
# ================================================================

@dataclass
class NPCRelation:
    """两个 NPC 之间的双边关系"""
    npc_id_a: str
    npc_id_b: str
    affinity: int = 0           # -100 到 +100，好感度
    relation_type: RelationType = RelationType.COLLEAGUE
    last_interaction_round: int = 0
    interactions: list[dict] = field(default_factory=list)  # 最近的交互记录

    # 统计
    agreements: int = 0         # 廷议中互相支持的次数
    disagreements: int = 0      # 廷议中互相反对的次数
    collaborations: int = 0     # 合作的次数

    def modify_affinity(self, delta: int, reason: str = "", round_num: int = 0):
        """修改 NPC 间好感度"""
        old = self.affinity
        self.affinity = max(-100, min(100, self.affinity + delta))

        if round_num:
            self.last_interaction_round = round_num

        self.interactions.append({
            "delta": delta,
            "reason": reason,
            "round": round_num,
            "timestamp": time.time(),
        })
        if len(self.interactions) > 20:
            self.interactions = self.interactions[-20:]

        logger.debug(
            f"[NPC关系] {self.npc_id_a} ↔ {self.npc_id_b}: "
            f"affinity {old} → {self.affinity} ({reason})"
        )

    def get_relation_label(self) -> str:
        """获取关系文字描述"""
        if self.relation_type == RelationType.KINSHIP:
            return "骨肉至亲"
        if self.relation_type == RelationType.MENTOR:
            return "师徒之情"
        if self.relation_type == RelationType.STUDENT:
            return "师生之谊"

        if self.affinity >= 70:
            return "莫逆之交"
        elif self.affinity >= 40:
            return "相交甚厚"
        elif self.affinity >= 10:
            return "以礼相待"
        elif self.affinity >= -10:
            return "泛泛之交"
        elif self.affinity >= -40:
            return "面和心不和"
        elif self.affinity >= -70:
            return "积怨颇深"
        else:
            return "势不两立"

    def to_dict(self) -> dict:
        return {
            "npc_id_a": self.npc_id_a,
            "npc_id_b": self.npc_id_b,
            "affinity": self.affinity,
            "relation_type": self.relation_type.value,
            "last_interaction_round": self.last_interaction_round,
            "agreements": self.agreements,
            "disagreements": self.disagreements,
            "collaborations": self.collaborations,
            "interactions": self.interactions[-10:],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCRelation":
        try:
            rel_type = RelationType(data.get("relation_type", "colleague"))
        except ValueError:
            rel_type = RelationType.COLLEAGUE

        return cls(
            npc_id_a=data["npc_id_a"],
            npc_id_b=data["npc_id_b"],
            affinity=data.get("affinity", 0),
            relation_type=rel_type,
            last_interaction_round=data.get("last_interaction_round", 0),
            agreements=data.get("agreements", 0),
            disagreements=data.get("disagreements", 0),
            collaborations=data.get("collaborations", 0),
            interactions=data.get("interactions", []),
        )


@dataclass
class NPCFaction:
    """NPC 派系"""
    faction_id: str             # 派系 ID
    faction_type: FactionType
    name: str                   # 派系名称（如"淮西集团"）
    leader_npc_id: str          # 派系领袖
    members: list[str] = field(default_factory=list)  # 成员 NPC ID 列表
    cohesion: float = 0.5       # 凝聚力 0~1
    influence: float = 0.3      # 在朝中影响力 0~1
    created_round: int = 0
    description: str = ""

    def add_member(self, npc_id: str):
        if npc_id not in self.members:
            self.members.append(npc_id)

    def remove_member(self, npc_id: str):
        if npc_id in self.members:
            self.members.remove(npc_id)

    def to_dict(self) -> dict:
        return {
            "faction_id": self.faction_id,
            "faction_type": self.faction_type.value,
            "name": self.name,
            "leader_npc_id": self.leader_npc_id,
            "members": self.members,
            "cohesion": self.cohesion,
            "influence": self.influence,
            "created_round": self.created_round,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCFaction":
        try:
            ftype = FactionType(data.get("faction_type", "none"))
        except ValueError:
            ftype = FactionType.NONE
        return cls(
            faction_id=data["faction_id"],
            faction_type=ftype,
            name=data.get("name", ""),
            leader_npc_id=data.get("leader_npc_id", ""),
            members=data.get("members", []),
            cohesion=data.get("cohesion", 0.5),
            influence=data.get("influence", 0.3),
            created_round=data.get("created_round", 0),
            description=data.get("description", ""),
        )


# ================================================================
# NPC 关系网络管理器
# ================================================================

class NPCRelationManager:
    """
    NPC 关系网络管理器 —— 单例

    管理所有 NPC 之间的关系、派系形成与演化。
    """

    _instance: Optional["NPCRelationManager"] = None

    def __new__(cls, persist_dir: str = None) -> "NPCRelationManager":
        # 多玩家模式：persist_dir 提供时创建独立实例，不走单例
        if persist_dir is not None:
            inst = super().__new__(cls)
            inst._initialized = False
            return inst
        # 兼容旧行为：全局单例
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, persist_dir: str = None):
        if self._initialized:
            return
        self._initialized = True

        # 关系图：key = "npc_a:npc_b" (字母序)
        self._relations: dict[str, NPCRelation] = {}

        # 派系
        self._factions: dict[str, NPCFaction] = {}

        # NPC → 所属派系映射
        self._npc_faction_map: dict[str, str] = {}

        # 配置：优先使用传入路径，否则使用默认全局路径
        if persist_dir:
            self._persist_dir = Path(persist_dir)
        else:
            self._persist_dir = Path(__file__).parent.parent.parent / "data" / "npc_relations"

        # 加载已有数据
        self._load_all()

        # 初始化已知关系（基于历史设定）
        self._init_known_relations()

        logger.info(f"NPCRelationManager 初始化完成 (dir={self._persist_dir})")

    # ================================================================
    # 关系键生成
    # ================================================================

    @staticmethod
    def _relation_key(npc_a: str, npc_b: str) -> str:
        """生成有序关系键（字母序）"""
        if npc_a <= npc_b:
            return f"{npc_a}:{npc_b}"
        return f"{npc_b}:{npc_a}"

    # ================================================================
    # 关系查询与修改
    # ================================================================

    def get_relation(self, npc_a: str, npc_b: str) -> NPCRelation:
        """获取两个 NPC 之间的关系（不存在则创建默认同僚关系）"""
        if npc_a == npc_b:
            # 自关系
            return NPCRelation(
                npc_id_a=npc_a, npc_id_b=npc_b,
                affinity=100, relation_type=RelationType.ALLY,
            )

        key = self._relation_key(npc_a, npc_b)
        if key not in self._relations:
            self._relations[key] = NPCRelation(npc_id_a=npc_a, npc_id_b=npc_b)
        return self._relations[key]

    def set_relation_type(self, npc_a: str, npc_b: str, rel_type: RelationType):
        """设置关系类型"""
        rel = self.get_relation(npc_a, npc_b)
        rel.relation_type = rel_type
        self._try_persist_relation(npc_a, npc_b)

    def modify_affinity(
        self, npc_a: str, npc_b: str, delta: int,
        reason: str = "", round_num: int = 0,
    ):
        """修改 NPC 间好感度"""
        rel = self.get_relation(npc_a, npc_b)
        rel.modify_affinity(delta, reason, round_num)
        self._try_persist_relation(npc_a, npc_b)

    def record_agreement(self, npc_a: str, npc_b: str, round_num: int = 0):
        """记录廷议中互相支持"""
        rel = self.get_relation(npc_a, npc_b)
        rel.agreements += 1
        rel.modify_affinity(3, "廷议中相互支持", round_num)
        self._try_persist_relation(npc_a, npc_b)

    def record_disagreement(self, npc_a: str, npc_b: str, round_num: int = 0):
        """记录廷议中互相反对"""
        rel = self.get_relation(npc_a, npc_b)
        rel.disagreements += 1
        rel.modify_affinity(-5, "廷议中意见相左", round_num)
        self._try_persist_relation(npc_a, npc_b)

    def record_collaboration(self, npc_a: str, npc_b: str, round_num: int = 0):
        """记录一次合作"""
        rel = self.get_relation(npc_a, npc_b)
        rel.collaborations += 1
        rel.modify_affinity(2, "合作共事", round_num)
        self._try_persist_relation(npc_a, npc_b)

    # ================================================================
    # 关系查询（批量）
    # ================================================================

    def get_all_relations_for_npc(self, npc_id: str) -> dict[str, NPCRelation]:
        """获取某 NPC 的所有关系"""
        result = {}
        for key, rel in self._relations.items():
            if rel.npc_id_a == npc_id or rel.npc_id_b == npc_id:
                other = rel.npc_id_b if rel.npc_id_a == npc_id else rel.npc_id_a
                result[other] = rel
        return result

    def get_friends(self, npc_id: str, min_affinity: int = 30) -> list[str]:
        """获取某 NPC 的朋友列表"""
        friends = []
        for key, rel in self._relations.items():
            if (rel.npc_id_a == npc_id or rel.npc_id_b == npc_id) and rel.affinity >= min_affinity:
                other = rel.npc_id_b if rel.npc_id_a == npc_id else rel.npc_id_a
                friends.append(other)
        return friends

    def get_enemies(self, npc_id: str, max_affinity: int = -20) -> list[str]:
        """获取某 NPC 的敌人列表"""
        enemies = []
        for key, rel in self._relations.items():
            if (rel.npc_id_a == npc_id or rel.npc_id_b == npc_id) and rel.affinity <= max_affinity:
                other = rel.npc_id_b if rel.npc_id_a == npc_id else rel.npc_id_a
                enemies.append(other)
        return enemies

    def get_relation_context_for_prompt(
        self, npc_id: str, other_npc_ids: list[str]
    ) -> str:
        """
        生成 NPC 对其他 NPC 的关系上下文文本（用于系统提示注入）

        帮助 NPC "了解"自己与同僚的关系
        """
        parts = ["\n【你与同僚的关系】"]
        has_content = False

        for other_id in other_npc_ids:
            if other_id == npc_id:
                continue
            rel = self.get_relation(npc_id, other_id)
            if rel.affinity == 0 and rel.relation_type == RelationType.COLLEAGUE:
                continue

            has_content = True
            parts.append(f"  - 与{other_id}：{rel.get_relation_label()}"
                        f"（好感{rel.affinity}）")

        return "\n".join(parts) if has_content else ""

    # ================================================================
    # 派系管理
    # ================================================================

    def create_faction(
        self,
        name: str,
        faction_type: FactionType,
        leader_npc_id: str,
        members: list[str] = None,
        description: str = "",
        round_number: int = 0,
    ) -> NPCFaction:
        """创建新派系"""
        faction_id = f"clique_{leader_npc_id}_{int(time.time())}"

        faction = NPCFaction(
            faction_id=faction_id,
            faction_type=faction_type,
            name=name,
            leader_npc_id=leader_npc_id,
            members=members or [],
            created_round=round_number,
            description=description,
        )

        if leader_npc_id not in faction.members:
            faction.members.insert(0, leader_npc_id)

        self._factions[faction_id] = faction
        for member_id in faction.members:
            self._npc_faction_map[member_id] = faction_id

        logger.info(f"[派系] 创建派系「{name}」，领袖：{leader_npc_id}，成员：{len(faction.members)}人")
        self._try_persist_factions()
        return faction

    def add_to_faction(self, npc_id: str, faction_id: str):
        """将 NPC 加入派系"""
        faction = self._factions.get(faction_id)
        if not faction:
            logger.warning(f"派系 {faction_id} 不存在")
            return

        # 先从旧派系移除
        old_faction_id = self._npc_faction_map.get(npc_id)
        if old_faction_id and old_faction_id != faction_id:
            old_faction = self._factions.get(old_faction_id)
            if old_faction:
                old_faction.remove_member(npc_id)

        faction.add_member(npc_id)
        self._npc_faction_map[npc_id] = faction_id
        self._try_persist_factions()

    def remove_from_faction(self, npc_id: str, faction_id: str):
        """将 NPC 从派系移除"""
        faction = self._factions.get(faction_id)
        if faction:
            faction.remove_member(npc_id)
        if self._npc_faction_map.get(npc_id) == faction_id:
            del self._npc_faction_map[npc_id]
        self._try_persist_factions()

    def get_npc_faction(self, npc_id: str) -> Optional[NPCFaction]:
        """获取 NPC 所属派系"""
        faction_id = self._npc_faction_map.get(npc_id)
        if faction_id:
            return self._factions.get(faction_id)
        return None

    def get_faction_members(self, faction_id: str) -> list[str]:
        """获取派系所有成员"""
        faction = self._factions.get(faction_id)
        return faction.members.copy() if faction else []

    def get_faction_context_for_prompt(self, npc_id: str) -> str:
        """获取 NPC 的派系上下文文本"""
        faction = self.get_npc_faction(npc_id)
        if not faction:
            return ""

        parts = [
            f"\n【你所属的派系】你是「{faction.name}」的一员。",
            f"派系主张：{faction.description}" if faction.description else "",
            f"派系领袖：{faction.leader_npc_id}",
        ]

        other_members = [m for m in faction.members if m != npc_id]
        if other_members:
            parts.append(f"同派系成员：{'、'.join(other_members)}")

        parts.append(
            f"派系凝聚力：{'强' if faction.cohesion > 0.7 else '中' if faction.cohesion > 0.4 else '弱'}，"
            f"朝中影响力：{'大' if faction.influence > 0.6 else '中' if faction.influence > 0.3 else '小'}。"
        )

        return "\n".join(parts)

    # ================================================================
    # 自动派系检测
    # ================================================================

    def detect_factions(
        self, npc_ids: list[str], npc_data_map: dict[str, dict],
        round_number: int = 0,
    ) -> list[NPCFaction]:
        """
        基于 NPC 间关系网络自动检测派系

        使用简单的社区检测算法：
        1. 构建好感度图
        2. 找出紧密连接的子图（社区）
        3. 为每个社区创建派系
        """
        if len(npc_ids) < 3:
            return []

        # 构建邻接矩阵（仅保留正向关系）
        graph: dict[str, set[str]] = {nid: set() for nid in npc_ids}

        for i, nid_a in enumerate(npc_ids):
            for nid_b in npc_ids[i + 1:]:
                rel = self.get_relation(nid_a, nid_b)
                if rel.affinity >= 25:  # 好感度阈值
                    graph[nid_a].add(nid_b)
                    graph[nid_b].add(nid_a)

        # 使用贪心社区检测
        visited: set[str] = set()
        communities: list[list[str]] = []

        for nid in npc_ids:
            if nid in visited:
                continue

            # BFS 找连通分量
            community = []
            queue = [nid]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                community.append(current)
                for neighbor in graph.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(community) >= 2:
                communities.append(community)

        # 为每个社区创建派系
        new_factions = []
        for community in communities:
            if len(community) < 2:
                continue

            # 找领袖（关系网中最中心的 NPC）
            leader = self._find_community_leader(community, npc_data_map)

            # 判断派系类型
            faction_type = self._classify_faction_type(community, npc_data_map)

            faction = self.create_faction(
                name=f"派系_{leader}_{round_number}",
                faction_type=faction_type,
                leader_npc_id=leader,
                members=community,
                description=f"自动检测到的派系（{len(community)}人）",
                round_number=round_number,
            )
            new_factions.append(faction)

        return new_factions

    def _find_community_leader(
        self, community: list[str], npc_data_map: dict[str, dict]
    ) -> str:
        """找社区领袖（度和智慧最高的 NPC）"""
        best_npc = community[0]
        best_score = -1

        for nid in community:
            npc = npc_data_map.get(nid, {})
            degree = sum(
                1 for other in community
                if other != nid and self.get_relation(nid, other).affinity > 0
            )
            wisdom = npc.get("wisdom", 50)
            ambition = npc.get("ambition", 30)
            score = degree * 2 + wisdom * 0.5 + ambition * 0.3

            if score > best_score:
                best_score = score
                best_npc = nid

        return best_npc

    def _classify_faction_type(
        self, community: list[str], npc_data_map: dict[str, dict]
    ) -> FactionType:
        """根据 NPC 属性分类派系类型"""
        military_count = 0
        civil_count = 0
        avg_loyalty = 0
        avg_ambition = 0

        for nid in community:
            npc = npc_data_map.get(nid, {})
            role = npc.get("role", "")
            if role in ("general", "strategist"):
                military_count += 1
            else:
                civil_count += 1
            avg_loyalty += npc.get("loyalty", 50)
            avg_ambition += npc.get("ambition", 30)

        n = len(community)
        avg_loyalty /= n
        avg_ambition /= n

        if military_count > civil_count:
            return FactionType.MILITARY
        elif avg_ambition > 60:
            return FactionType.OPPORTUNIST
        elif avg_loyalty > 75:
            return FactionType.LOYALIST
        else:
            return FactionType.REFORM

    # ================================================================
    # 廷议后的关系更新
    # ================================================================

    def update_after_debate(
        self, debate_results: list[dict], round_number: int = 0
    ):
        """
        廷议结束后更新 NPC 间关系

        基于廷议中各 NPC 的观点，分析他们之间的支持/反对关系，
        自动调整 NPC 间的好感度。
        """
        # 简单的文本相似度分析来判断观点是否一致
        npc_opinions = {
            r["npc_id"]: r.get("opinion", "")
            for r in debate_results if "npc_id" in r
        }

        npc_ids = list(npc_opinions.keys())
        for i, nid_a in enumerate(npc_ids):
            for nid_b in npc_ids[i + 1:]:
                text_a = npc_opinions.get(nid_a, "")
                text_b = npc_opinions.get(nid_b, "")

                if not text_a or not text_b:
                    continue

                # 简单关键词重叠度判断观点一致性
                overlap = self._text_overlap_score(text_a, text_b)

                if overlap > 0.4:
                    # 观点相似 → 关系改善
                    self.record_agreement(nid_a, nid_b, round_number)
                elif overlap < 0.1:
                    # 观点差异大 → 关系可能恶化
                    self.record_disagreement(nid_a, nid_b, round_number)

    @staticmethod
    def _text_overlap_score(text_a: str, text_b: str) -> float:
        """计算两个文本的关键词重叠度"""
        # 提取关键词（简化版）
        def extract_keywords(text: str) -> set:
            keywords = {"攻", "守", "和", "战", "盟", "粮", "兵", "城",
                       "伐", "征", "抚", "剿", "赏", "罚", "升", "贬"}
            return {kw for kw in keywords if kw in text}

        kw_a = extract_keywords(text_a)
        kw_b = extract_keywords(text_b)

        if not kw_a and not kw_b:
            return 0.5
        if not kw_a or not kw_b:
            return 0.0

        intersection = kw_a & kw_b
        union = kw_a | kw_b
        return len(intersection) / len(union) if union else 0.0

    # ================================================================
    # 已知关系初始化
    # ================================================================

    def _init_known_relations(self):
        """初始化基于历史设定的已知关系"""
        # 如果已从磁盘加载了关系数据，跳过
        if self._relations:
            return

        known_relations = [
            # 朱元璋势力：刘基与李善长 — 亦敌亦友
            ("liu_ji", "li_shanchang", -10, RelationType.RIVAL, "浙东与淮西之争"),
            # 徐达与常遇春 — 战友情
            ("xu_da", "chang_yuchun", 60, RelationType.FRIEND, "并肩作战"),
            # 刘基与宋濂 — 文友
            ("liu_ji", "song_lian", 40, RelationType.FRIEND, "浙东文人"),
        ]

        for npc_a, npc_b, affinity, rel_type, reason in known_relations:
            rel = self.get_relation(npc_a, npc_b)
            rel.affinity = affinity
            rel.relation_type = rel_type
            rel.interactions.append({
                "delta": affinity,
                "reason": reason,
                "round": 0,
                "timestamp": time.time(),
            })
            self._try_persist_relation(npc_a, npc_b)

        logger.info(f"初始化 {len(known_relations)} 条已知 NPC 关系")

    # ================================================================
    # 持久化
    # ================================================================

    def _persist_path(self, filename: str) -> Path:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        return self._persist_dir / filename

    def _try_persist_relation(self, npc_a: str, npc_b: str):
        """持久化单条关系"""
        try:
            key = self._relation_key(npc_a, npc_b)
            rel = self._relations.get(key)
            if not rel:
                return
            path = self._persist_path(f"rel_{key.replace(':', '_')}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rel.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"关系持久化失败 ({npc_a}-{npc_b}): {e}")

    def _try_persist_factions(self):
        """持久化派系数据"""
        try:
            path = self._persist_path("factions.json")
            data = {
                "factions": [f.to_dict() for f in self._factions.values()],
                "npc_faction_map": self._npc_faction_map,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"派系持久化失败: {e}")

    def _load_all(self):
        """从磁盘加载所有持久化数据"""
        if not self._persist_dir.exists():
            return

        # 加载关系
        try:
            for file_path in self._persist_dir.glob("rel_*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    rel = NPCRelation.from_dict(data)
                    key = self._relation_key(rel.npc_id_a, rel.npc_id_b)
                    self._relations[key] = rel
                except Exception as e:
                    logger.warning(f"加载关系失败 ({file_path}): {e}")
        except Exception as e:
            logger.warning(f"批量加载关系失败: {e}")

        # 加载派系
        try:
            factions_path = self._persist_path("factions.json")
            if factions_path.exists():
                with open(factions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for fd in data.get("factions", []):
                    faction = NPCFaction.from_dict(fd)
                    self._factions[faction.faction_id] = faction
                self._npc_faction_map = data.get("npc_faction_map", {})
        except Exception as e:
            logger.warning(f"加载派系失败: {e}")

        loaded = len(self._relations) + len(self._factions)
        if loaded > 0:
            logger.info(
                f"从磁盘加载 NPC 关系数据: "
                f"{len(self._relations)} 条关系, "
                f"{len(self._factions)} 个派系"
            )

    def persist_all(self):
        """持久化所有数据"""
        for key, rel in self._relations.items():
            path = self._persist_path(f"rel_{key.replace(':', '_')}.json")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(rel.to_dict(), f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"关系持久化失败 ({key}): {e}")

        self._try_persist_factions()
        logger.info("NPC 关系数据全部持久化完成")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_relations": len(self._relations),
            "total_factions": len(self._factions),
            "npc_with_faction": len(self._npc_faction_map),
            "avg_affinity": (
                sum(r.affinity for r in self._relations.values()) / len(self._relations)
                if self._relations else 0
            ),
        }


# ================================================================
# 模块级便捷函数
# ================================================================

def get_npc_relation_manager() -> NPCRelationManager:
    """获取当前会话的 NPC 关系管理器（多玩家隔离）

    优先从当前请求会话获取独立实例；
    无会话上下文时回退到全局单例（兼容启动/测试等场景）。
    """
    # 尝试通过会话上下文获取玩家独立实例
    try:
        from server.session_manager import get_current_session_id, get_session_manager
        sid = get_current_session_id()
        if sid:
            sm = get_session_manager()
            session = sm.get(sid)
            if session and hasattr(session, "npc_relation_manager") and session.npc_relation_manager is not None:
                return session.npc_relation_manager
            # 延迟创建（需要 persist_dir，由 SessionManager 统一管理）
            if session:
                return sm._ensure_npc_relation_manager(sid)
    except Exception:
        logger.warning("NPC关系管理器创建失败，降级为全局单例（无会话持久化）", exc_info=True)
    # 回退：全局单例
    return NPCRelationManager()
