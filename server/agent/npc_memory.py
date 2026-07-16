"""
NPC 记忆与情感系统 · 元末逐鹿 3.0

职责：
1. NPC好感度系统：-100 到 +100，受对话/廷议/赏罚影响
2. 对话语义摘要：超过阈值时压缩旧对话
3. 关键记忆标记：记住重要承诺/侮辱/赏赐
4. 情感状态：高兴/愤怒/恐惧/忠诚/失望等动态情绪
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("yuanmo.npc.memory")


class Emotion(Enum):
    """NPC 情绪状态"""
    HAPPY = "happy"           # 高兴
    ANGRY = "angry"           # 愤怒
    FEARFUL = "fearful"       # 恐惧
    LOYAL = "loyal"           # 忠诚
    DISAPPOINTED = "disappointed"  # 失望
    NEUTRAL = "neutral"       # 中立
    GRATEFUL = "grateful"     # 感激
    SUSPICIOUS = "suspicious" # 猜疑


class MemoryType(Enum):
    """记忆类型"""
    PROMISE = "promise"           # 君主的承诺
    INSULT = "insult"             # 侮辱/冒犯
    REWARD = "reward"             # 赏赐
    PUNISHMENT = "punishment"     # 惩罚
    PROMOTION = "promotion"       # 升迁
    BETRAYAL = "betrayal"         # 背叛
    COURT_DEBATE = "court_debate" # 廷议发言
    BATTLE = "battle"             # 战斗经历


@dataclass
class KeyMemory:
    """关键记忆条目"""
    memory_type: MemoryType
    content: str
    round_num: int
    importance: int = 1          # 重要性 1-10
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": self.memory_type.value,
            "content": self.content,
            "round": self.round_num,
            "importance": self.importance,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KeyMemory":
        return cls(
            memory_type=MemoryType(data["type"]),
            content=data["content"],
            round_num=data["round"],
            importance=data.get("importance", 1),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class NPCMemory:
    """
    单个NPC的记忆与情感状态

    好感度范围: -100（极度敌视） ~ +100（极度忠诚）
    情感状态根据好感度变化自动推断
    """
    npc_id: str
    npc_name: str
    faction_id: str

    # 好感度
    affection: int = 0               # 对玩家的好感度

    # 当前情绪
    emotion: Emotion = Emotion.NEUTRAL

    # 关键记忆
    key_memories: list[KeyMemory] = field(default_factory=list)
    max_key_memories: int = 20

    # 对话历史摘要（压缩后的旧对话）
    dialogue_summary: str = ""

    # 与玩家的互动统计
    total_conversations: int = 0
    rewards_received: int = 0
    punishments_received: int = 0
    promises_made_to: int = 0
    promises_kept: int = 0

    # 最后一次互动回合
    last_interaction_round: int = 0

    def change_affection(self, delta: int, reason: str, round_num: int):
        """修改好感度"""
        old = self.affection
        self.affection = max(-100, min(100, self.affection + delta))
        self._update_emotion()

        logger.info(
            f"[NPC情感] {self.npc_name}({self.npc_id}): "
            f"好感度 {old:+d} → {self.affection:+d} (Δ{delta:+d}) - {reason}"
        )

        # 重要变化记录为记忆
        if abs(delta) >= 10:
            mem_type = MemoryType.REWARD if delta > 0 else MemoryType.PUNISHMENT
            self.add_key_memory(mem_type, reason, round_num, importance=min(abs(delta) // 5, 10))

    def add_key_memory(self, mem_type: MemoryType, content: str, round_num: int, importance: int = 1):
        """添加关键记忆"""
        memory = KeyMemory(
            memory_type=mem_type,
            content=content,
            round_num=round_num,
            importance=importance,
        )
        self.key_memories.append(memory)

        # 保留最重要的记忆
        if len(self.key_memories) > self.max_key_memories:
            self.key_memories.sort(key=lambda m: m.importance, reverse=True)
            self.key_memories = self.key_memories[:self.max_key_memories]

    def _update_emotion(self):
        """根据好感度自动推断情绪"""
        if self.affection >= 80:
            self.emotion = Emotion.LOYAL
        elif self.affection >= 50:
            self.emotion = Emotion.GRATEFUL
        elif self.affection >= 20:
            self.emotion = Emotion.HAPPY
        elif self.affection >= -20:
            self.emotion = Emotion.NEUTRAL
        elif self.affection >= -50:
            self.emotion = Emotion.SUSPICIOUS
        elif self.affection >= -80:
            self.emotion = Emotion.DISAPPOINTED
        elif self.affection >= -95:
            self.emotion = Emotion.ANGRY
        else:
            self.emotion = Emotion.FEARFUL  # 好感度 < -95 时触发（之前因 >= -100 覆盖全区间而不可达）

    def get_emotional_tone(self) -> str:
        """获取情感语气描述（用于Prompt注入）"""
        tone_map = {
            Emotion.LOYAL: "忠心耿耿，对君主极为忠诚",
            Emotion.GRATEFUL: "心怀感激，对君主颇有好感",
            Emotion.HAPPY: "心情愉悦，态度友好",
            Emotion.NEUTRAL: "态度中立，公事公办",
            Emotion.SUSPICIOUS: "心存疑虑，言语间有所保留",
            Emotion.DISAPPOINTED: "略带失望，语气冷淡",
            Emotion.ANGRY: "心怀不满，言辞尖锐",
            Emotion.FEARFUL: "心存畏惧，谨小慎微",
        }
        return tone_map.get(self.emotion, "态度不明")

    def get_key_memories_summary(self, max_items: int = 5) -> str:
        """获取关键记忆摘要（用于Prompt注入）"""
        if not self.key_memories:
            return ""

        # 按重要性排序，取最重要的几条
        sorted_memories = sorted(self.key_memories, key=lambda m: m.importance, reverse=True)[:max_items]
        lines = ["【重要往事】"]
        for m in sorted_memories:
            type_label = {
                MemoryType.PROMISE: "承诺",
                MemoryType.INSULT: "冒犯",
                MemoryType.REWARD: "赏赐",
                MemoryType.PUNISHMENT: "惩罚",
                MemoryType.PROMOTION: "升迁",
                MemoryType.BETRAYAL: "背叛",
                MemoryType.COURT_DEBATE: "廷议",
                MemoryType.BATTLE: "战事",
            }.get(m.memory_type, "事件")
            lines.append(f"- [{type_label}] 第{m.round_num}回合: {m.content}")
        return "\n".join(lines)

    def generate_dialogue_summary(self, old_messages: list[dict]) -> str:
        """
        生成对话摘要（将旧对话压缩为简短摘要）
        注意：实际LLM摘要生成由调用方处理，此处只标记需要压缩的消息
        """
        if not old_messages:
            return self.dialogue_summary

        # 提取关键信息
        topics = set()
        for msg in old_messages:
            content = msg.get("content", "")
            if "赏赐" in content or "赏" in content:
                topics.add("曾获赏赐")
            if "惩罚" in content or "罚" in content:
                topics.add("曾受惩罚")
            if "承诺" in content or "许诺" in content:
                topics.add("君主有过承诺")
            if "封" in content or "升" in content:
                topics.add("有过升迁")

        if topics:
            new_summary = "、".join(topics)
            if self.dialogue_summary:
                self.dialogue_summary += "；" + new_summary
            else:
                self.dialogue_summary = new_summary

        return self.dialogue_summary

    def get_personality_prompt_addition(self) -> str:
        """获取人格相关的Prompt补充"""
        parts = []

        # 情感语气
        parts.append(f"当前对君主的态度：{self.get_emotional_tone()}。")

        # 好感度暗示
        if self.affection >= 70:
            parts.append("你愿意为君主赴汤蹈火。")
        elif self.affection >= 30:
            parts.append("你倾向于支持君主的决策。")
        elif self.affection <= -70:
            parts.append("你暗中对君主极为不满，可能在寻找背叛的机会。")
        elif self.affection <= -30:
            parts.append("你对君主有所不满，言语间可能流露。")

        # 关键记忆
        memories = self.get_key_memories_summary(3)
        if memories:
            parts.append(memories)

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "npc_name": self.npc_name,
            "faction_id": self.faction_id,
            "affection": self.affection,
            "emotion": self.emotion.value,
            "key_memories": [m.to_dict() for m in self.key_memories],
            "dialogue_summary": self.dialogue_summary,
            "total_conversations": self.total_conversations,
            "rewards_received": self.rewards_received,
            "punishments_received": self.punishments_received,
            "promises_made_to": self.promises_made_to,
            "promises_kept": self.promises_kept,
            "last_interaction_round": self.last_interaction_round,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCMemory":
        mem = cls(
            npc_id=data["npc_id"],
            npc_name=data["npc_name"],
            faction_id=data["faction_id"],
            affection=data.get("affection", 0),
            emotion=Emotion(data.get("emotion", "neutral")),
            dialogue_summary=data.get("dialogue_summary", ""),
            total_conversations=data.get("total_conversations", 0),
            rewards_received=data.get("rewards_received", 0),
            punishments_received=data.get("punishments_received", 0),
            promises_made_to=data.get("promises_made_to", 0),
            promises_kept=data.get("promises_kept", 0),
            last_interaction_round=data.get("last_interaction_round", 0),
        )
        mem.key_memories = [KeyMemory.from_dict(m) for m in data.get("key_memories", [])]
        return mem


class NPCMemoryManager:
    """
    NPC记忆管理器

    管理所有NPC的记忆和情感状态，支持持久化
    """

    def __init__(self, data_dir: str = "data/npc_memory"):
        self.data_dir = data_dir
        self._memories: dict[str, NPCMemory] = {}  # npc_id -> NPCMemory
        os.makedirs(data_dir, exist_ok=True)

    def get_or_create(self, npc_id: str, npc_name: str, faction_id: str) -> NPCMemory:
        """获取或创建NPC记忆"""
        if npc_id not in self._memories:
            # 尝试从文件加载
            loaded = self._load_from_file(npc_id)
            if loaded:
                self._memories[npc_id] = loaded
            else:
                self._memories[npc_id] = NPCMemory(
                    npc_id=npc_id,
                    npc_name=npc_name,
                    faction_id=faction_id,
                )
        return self._memories[npc_id]

    def get(self, npc_id: str) -> Optional[NPCMemory]:
        """获取NPC记忆"""
        return self._memories.get(npc_id)

    def modify_affection(
        self, npc_id: str, delta: int, reason: str, round_num: int,
        npc_name: str = "", faction_id: str = ""
    ):
        """修改NPC好感度"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.change_affection(delta, reason, round_num)
        mem.last_interaction_round = round_num

    def record_promise(self, npc_id: str, content: str, round_num: int,
                        npc_name: str = "", faction_id: str = ""):
        """记录君主对NPC的承诺"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.add_key_memory(MemoryType.PROMISE, content, round_num, importance=7)
        mem.promises_made_to += 1
        mem.change_affection(5, f"君主许诺：{content}", round_num)

    def record_promise_kept(self, npc_id: str, round_num: int,
                            npc_name: str = "", faction_id: str = ""):
        """记录承诺兑现"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.promises_kept += 1
        mem.change_affection(10, "君主兑现了承诺", round_num)

    def record_reward(self, npc_id: str, amount: int, round_num: int,
                      npc_name: str = "", faction_id: str = ""):
        """记录赏赐"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.rewards_received += 1
        affection_gain = min(amount // 50, 20)  # 每50银两+1好感，最多+20
        mem.add_key_memory(MemoryType.REWARD, f"获赏{amount}银两", round_num, importance=5)
        mem.change_affection(affection_gain, f"获赏{amount}银两", round_num)

    def record_punishment(self, npc_id: str, reason: str, round_num: int,
                          npc_name: str = "", faction_id: str = ""):
        """记录惩罚"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.punishments_received += 1
        mem.add_key_memory(MemoryType.PUNISHMENT, reason, round_num, importance=6)
        mem.change_affection(-15, f"受罚：{reason}", round_num)

    def record_court_performance(self, npc_id: str, agreed_with_ruler: bool, round_num: int,
                                  npc_name: str = "", faction_id: str = ""):
        """记录廷议表现"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        if agreed_with_ruler:
            mem.change_affection(2, "廷议中支持君主", round_num)
        else:
            mem.change_affection(-3, "廷议中反对君主", round_num)

    def record_battle_experience(self, npc_id: str, victory: bool, battle_desc: str, round_num: int,
                                  npc_name: str = "", faction_id: str = ""):
        """记录战斗经历"""
        mem = self.get_or_create(npc_id, npc_name, faction_id)
        mem.add_key_memory(MemoryType.BATTLE, battle_desc, round_num, importance=4)
        if victory:
            mem.change_affection(3, f"战斗中获胜：{battle_desc}", round_num)
        else:
            mem.change_affection(-5, f"战斗中失利：{battle_desc}", round_num)

    def get_npc_prompt_context(self, npc_id: str) -> str:
        """获取NPC的完整Prompt上下文"""
        mem = self._memories.get(npc_id)
        if not mem:
            return ""
        return mem.get_personality_prompt_addition()

    def build_affection_context(self, npc_id: str, current_round: int) -> str:
        """构建NPC好感度上下文，用于廷议辩论提示注入"""
        mem = self._memories.get(npc_id)
        if not mem:
            return ""
        parts = []
        affections = getattr(mem, "affections", {})
        for target, val in affections.items():
            if abs(val) > 20:
                parts.append(f"对{target}好感度{val}")
        return "；".join(parts) if parts else ""

    def get_debate_bias(self, npc_id: str) -> str:
        """获取NPC辩论倾向（支持/反对/中立）"""
        mem = self._memories.get(npc_id)
        if not mem:
            return "中立"
        return getattr(mem, "debate_bias", "中立")

    def save_all(self):
        """保存所有NPC记忆到文件"""
        for npc_id, mem in self._memories.items():
            self._save_to_file(npc_id, mem)
        logger.info(f"[NPC记忆] 已保存 {len(self._memories)} 个NPC的记忆")

    def load_all(self):
        """从文件加载所有NPC记忆"""
        if not os.path.exists(self.data_dir):
            return
        count = 0
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".json"):
                npc_id = filename[:-5]
                mem = self._load_from_file(npc_id)
                if mem:
                    self._memories[npc_id] = mem
                    count += 1
        if count:
            logger.info(f"[NPC记忆] 已加载 {count} 个NPC的记忆")

    def reset_all(self):
        """重置所有NPC记忆（新游戏）"""
        self._memories.clear()
        if os.path.exists(self.data_dir):
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.data_dir, filename))

    def _save_to_file(self, npc_id: str, mem: NPCMemory):
        """保存单个NPC记忆"""
        filepath = os.path.join(self.data_dir, f"{npc_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(mem.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存NPC记忆失败 {npc_id}: {e}")

    def _load_from_file(self, npc_id: str) -> Optional[NPCMemory]:
        """从文件加载单个NPC记忆"""
        filepath = os.path.join(self.data_dir, f"{npc_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return NPCMemory.from_dict(data)
        except Exception as e:
            logger.error(f"加载NPC记忆失败 {npc_id}: {e}")
            return None


# 全局单例
_global_memory_manager: Optional[NPCMemoryManager] = None


def get_npc_memory_manager() -> NPCMemoryManager:
    """获取当前会话的 NPC 记忆管理器（多玩家隔离）

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
            if session and hasattr(session, "npc_memory_manager") and session.npc_memory_manager is not None:
                return session.npc_memory_manager
            # 延迟创建
            if session:
                return sm._ensure_npc_memory_manager(sid)
    except Exception:
        logger.warning("NPC记忆管理器创建失败，降级为全局单例（无会话持久化）", exc_info=True)
    # 回退：全局单例
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = NPCMemoryManager()
    return _global_memory_manager


def reset_npc_memory_manager():
    """重置全局NPC记忆管理器（仅影响全局单例，不影响玩家会话实例）"""
    global _global_memory_manager
    if _global_memory_manager:
        _global_memory_manager.reset_all()
    _global_memory_manager = NPCMemoryManager()
