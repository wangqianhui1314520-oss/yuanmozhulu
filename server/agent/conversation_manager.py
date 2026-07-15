"""
Conversation Manager - 独立对话上下文管理

职责：
1. 每个 NPC 独立的对话历史存储（内存 + 可选持久化）
2. Session 生命周期管理（创建/恢复/清除）
3. 对话历史裁剪与摘要
4. 跨回合对话连续性保障

从 a1_advisor.py 和 gameStore.ts 中提取，确保前后端对话管理统一。
"""
from __future__ import annotations
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.agent.conversation")


@dataclass
class ConversationTurn:
    """单轮对话记录"""
    role: str          # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    npc_name: str = ""


@dataclass
class ConversationSession:
    """单个 NPC 的对话会话"""
    npc_id: str
    faction_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)  # 可存当前回合/年份等

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def is_empty(self) -> bool:
        return len(self.turns) == 0

    def add_turn(self, role: str, content: str, npc_name: str = ""):
        self.turns.append(ConversationTurn(role=role, content=content, npc_name=npc_name))
        self.last_active_at = time.time()

    def get_history(self, max_turns: int = 12) -> list[dict]:
        """获取最近 N 轮对话历史（标准格式）"""
        recent = self.turns[-max_turns:]
        return [
            {"role": t.role, "content": t.content}
            for t in recent
        ]

    def get_textual_history(self, max_turns: int = 6) -> str:
        """获取文本格式的对话历史（用于 prompt 构建）"""
        recent = self.turns[-max_turns:]
        lines = []
        for t in recent:
            label = "主公" if t.role == "user" else (t.npc_name or "谋士")
            lines.append(f"{label}：{t.content}")
        return "\n".join(lines)

    def trim(self, max_turns: int = 30):
        """裁剪历史长度"""
        if len(self.turns) > max_turns:
            self.turns = self.turns[-max_turns:]

    def clear(self):
        self.turns.clear()


class ConversationManager:
    """对话上下文管理器 —— 单例（全局）"""

    _instance: Optional["ConversationManager"] = None

    def __new__(cls) -> "ConversationManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # npc_id -> ConversationSession
        self._sessions: dict[str, ConversationSession] = {}
        # 持久化目录
        self._persist_dir = Path(__file__).parent.parent.parent / "data" / "conversations"
        self._max_turns_per_session = 40
        self._max_sessions_per_faction = 20
        logger.info("ConversationManager 初始化完成")

    # ================================================================
    # Session 管理
    # ================================================================

    def get_or_create_session(
        self, npc_id: str, faction_id: str = ""
    ) -> ConversationSession:
        """获取或创建 NPC 对话会话"""
        key = self._session_key(npc_id, faction_id)

        if key not in self._sessions:
            self._sessions[key] = ConversationSession(
                npc_id=npc_id,
                faction_id=faction_id,
            )
            logger.debug(f"创建新会话: {key}")

            # 尝试从磁盘恢复
            if faction_id:
                self._try_restore(key)

        session = self._sessions[key]
        session.last_active_at = time.time()
        return session

    def get_session(
        self, npc_id: str, faction_id: str = ""
    ) -> Optional[ConversationSession]:
        """获取已有会话（不创建）"""
        key = self._session_key(npc_id, faction_id)
        return self._sessions.get(key)

    def clear_session(self, npc_id: str, faction_id: str = ""):
        """清除指定 NPC 的对话历史"""
        key = self._session_key(npc_id, faction_id)
        if key in self._sessions:
            self._sessions[key].clear()
        self._remove_persisted(key)

    def clear_all_for_faction(self, faction_id: str):
        """清除某势力的所有会话"""
        prefix = f"{faction_id}:"
        keys_to_clear = [k for k in self._sessions if k.startswith(prefix)]
        for k in keys_to_clear:
            self._sessions[k].clear()
            self._remove_persisted(k)
        logger.info(f"清除 {len(keys_to_clear)} 个会话 ({faction_id})")

    def clear_all(self):
        """清除全部会话"""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info(f"清除全部 {count} 个会话")

    # ================================================================
    # 对话操作
    # ================================================================

    def add_exchange(
        self,
        npc_id: str,
        user_message: str,
        assistant_response: str,
        faction_id: str = "",
        npc_name: str = "",
    ):
        """添加一轮完整的对话交换"""
        session = self.get_or_create_session(npc_id, faction_id)
        session.add_turn("user", user_message)
        session.add_turn("assistant", assistant_response, npc_name)
        session.trim(self._max_turns_per_session)

        # 持久化
        if faction_id:
            self._try_persist(self._session_key(npc_id, faction_id), session)

    def add_user_message(
        self, npc_id: str, message: str, faction_id: str = ""
    ):
        """仅添加用户消息（用于异步流程）"""
        session = self.get_or_create_session(npc_id, faction_id)
        session.add_turn("user", message)

    def add_assistant_response(
        self, npc_id: str, response: str, faction_id: str = "", npc_name: str = ""
    ):
        """仅添加 AI 回复"""
        session = self.get_or_create_session(npc_id, faction_id)
        session.add_turn("assistant", response, npc_name)
        session.trim(self._max_turns_per_session)

    def get_conversation_history(
        self, npc_id: str, faction_id: str = "", max_turns: int = 12
    ) -> list[dict]:
        """获取标准格式对话历史（供 API 传输）"""
        session = self.get_session(npc_id, faction_id)
        if not session:
            return []
        return session.get_history(max_turns)

    def get_all_conversations(self) -> dict:
        """导出所有活跃对话（供存档/前端同步）"""
        result = {}
        for key, session in self._sessions.items():
            if not session.is_empty:
                result[key] = {
                    "npc_id": session.npc_id,
                    "faction_id": session.faction_id,
                    "turns": [
                        {"role": t.role, "content": t.content, "npc_name": t.npc_name}
                        for t in session.turns
                    ],
                    "turn_count": session.turn_count,
                }
        return result

    def load_conversations(self, data: dict):
        """批量恢复对话（从存档）"""
        for key, session_data in data.items():
            parts = key.split(":", 1)
            if len(parts) != 2:
                continue
            faction_id, npc_id = parts
            session = ConversationSession(
                npc_id=npc_id,
                faction_id=faction_id,
            )
            for t in session_data.get("turns", []):
                session.add_turn(
                    role=t["role"],
                    content=t["content"],
                    npc_name=t.get("npc_name", ""),
                )
            self._sessions[key] = session
        logger.info(f"批量恢复 {len(data)} 个对话会话")

    # ================================================================
    # 上下文注入（构建增强 Prompt）
    # ================================================================

    def build_context_for_npc(
        self,
        npc_id: str,
        faction_id: str,
        message: str,
        world_state_snapshot: str = "",
    ) -> str:
        """为指定 NPC 构建完整的对话上下文 Prompt

        包含：历史对话 + 世界状态 + 当前消息
        """
        session = self.get_session(npc_id, faction_id)
        parts = []

        if session and not session.is_empty:
            history_text = session.get_textual_history(max_turns=6)
            parts.append(f"【此前对话】\n{history_text}\n")

        if world_state_snapshot:
            parts.append(f"【当前局势】\n{world_state_snapshot}\n")

        parts.append(f"【主公问】{message}")

        return "\n".join(parts)

    # ================================================================
    # 持久化（文件存储）
    # ================================================================

    def _session_key(self, npc_id: str, faction_id: str) -> str:
        """生成会话唯一键"""
        fid = faction_id or "_global"
        return f"{fid}:{npc_id}"

    def _get_persist_path(self, key: str) -> Path:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        return self._persist_dir / f"{key}.json"

    def _try_persist(self, key: str, session: ConversationSession):
        """尝试持久化会话"""
        try:
            path = self._get_persist_path(key)
            data = {
                "npc_id": session.npc_id,
                "faction_id": session.faction_id,
                "created_at": session.created_at,
                "last_active_at": session.last_active_at,
                "turns": [
                    {"role": t.role, "content": t.content, "npc_name": t.npc_name}
                    for t in session.turns[-20:]  # 最多持久化20轮
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"会话持久化失败 ({key}): {e}")

    def _try_restore(self, key: str):
        """尝试从磁盘恢复会话"""
        try:
            path = self._get_persist_path(key)
            if not path.exists():
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            session = self._sessions[key]
            for t in data.get("turns", []):
                session.add_turn(
                    role=t["role"],
                    content=t["content"],
                    npc_name=t.get("npc_name", ""),
                )
            logger.debug(f"从磁盘恢复会话 ({key}): {session.turn_count} 轮")
        except Exception as e:
            logger.warning(f"会话恢复失败 ({key}): {e}")

    def _remove_persisted(self, key: str):
        """删除持久化文件"""
        try:
            path = self._get_persist_path(key)
            if path.exists():
                path.unlink()
        except Exception:
            pass

    def persist_all(self):
        """持久化所有活跃会话"""
        for key, session in self._sessions.items():
            if not session.is_empty:
                self._try_persist(key, session)

    # ================================================================
    # 统计
    # ================================================================

    def get_stats(self) -> dict:
        active = sum(1 for s in self._sessions.values() if not s.is_empty)
        total_turns = sum(s.turn_count for s in self._sessions.values())
        return {
            "active_sessions": active,
            "total_sessions": len(self._sessions),
            "total_turns": total_turns,
        }


# ================================================================
# 模块级便捷函数
# ================================================================

def get_conversation_manager() -> ConversationManager:
    return ConversationManager()
