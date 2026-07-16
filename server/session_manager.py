"""
元末逐鹿 3.0 · 玩家会话管理器
多玩家数据隔离：每个玩家独立的 WorldState / LLM客户端 / 存档 / NPC 记忆

生产部署增强（2026-07-16）：
- 会话 TTL 自动过期（默认30分钟无活动）
- 过期前自动持久化 NPC 记忆/关系
- 后台定时清理任务
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.session")

# 会话 TTL（秒），通过环境变量 YUANMO_SESSION_TTL 配置，默认 1800s = 30min
_SESSION_TTL = int(os.environ.get("YUANMO_SESSION_TTL", "1800"))
# 后台清理间隔（秒）
_CLEANUP_INTERVAL = int(os.environ.get("YUANMO_CLEANUP_INTERVAL", "300"))

# ============================================================
# 当前请求的 session_id（通过 ContextVar 实现异步安全）
# ============================================================
_current_session_id: ContextVar[Optional[str]] = ContextVar("current_session_id", default=None)


def get_current_session_id() -> Optional[str]:
    """获取当前请求的 session_id（由中间件设置）"""
    return _current_session_id.get()


def set_current_session_id(sid: str):
    """由中间件调用，设置当前请求的 session_id"""
    _current_session_id.set(sid)


# ============================================================
# PlayerSession — 单个玩家的完整隔离状态
# ============================================================
@dataclass
class PlayerSession:
    session_id: str
    created_at: str = ""

    # LLM 配置
    api_key: str = ""
    llm_clients: dict = field(default_factory=dict)
    llm_available: bool = False

    # 游戏状态
    world_state: Optional[object] = None       # WorldState
    round_engine: Optional[object] = None      # RoundEngine
    pending_commands: list = field(default_factory=list)
    round_snapshots: list = field(default_factory=list)
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # NPC 感知系统（多玩家隔离：每人独立记忆/关系实例）
    npc_memory_manager: Optional[object] = None      # NPCMemoryManager
    npc_relation_manager: Optional[object] = None    # NPCRelationManager

    # 元信息
    faction_id: str = ""
    faction_name: str = ""
    mode: str = "player_turn"    # player_turn / ai_watch

    # 会话生命周期（生产部署：TTL 自动过期）
    last_active: datetime = field(default_factory=datetime.now)
    is_expired: bool = False

    def touch(self):
        """更新最后活动时间（每次 API 请求调用）"""
        self.last_active = datetime.now()
        self.is_expired = False

    def idle_seconds(self) -> float:
        """返回距上次活动的秒数"""
        return (datetime.now() - self.last_active).total_seconds()

    def to_dict(self) -> dict:
        ws = None
        if self.world_state:
            try:
                ws = self.world_state.model_dump()
            except Exception as e:
                logger.warning(f"world_state 序列化失败: {e}")
                ws = None
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "api_key_configured": bool(self.api_key),
            "llm_available": self.llm_available,
            "faction_id": self.faction_id,
            "faction_name": self.faction_name,
            "mode": self.mode,
            "current_round": ws.get("current_round", 0) if ws else 0,
            "current_year": ws.get("current_year", 0) if ws else 0,
            "current_season": ws.get("current_season", "") if ws else "",
        }


# ============================================================
# SessionManager — 多玩家会话注册表
# ============================================================
class SessionManager:
    def __init__(self, project_dir: Path):
        self._sessions: dict[str, PlayerSession] = {}
        self._lock = asyncio.Lock()
        self.project_dir = project_dir
        # 全局默认 LLM 客户端模板（由 api_server 的 startup_event 设置）
        self._default_llm_clients: dict = {}
        self._default_llm_available: bool = False
        logger.info("SessionManager 已初始化（多玩家隔离模式）")

    def set_llm_defaults(self, clients: dict, available: bool):
        """设置全局 LLM 默认值（新会话创建时复制）"""
        self._default_llm_clients = clients
        self._default_llm_available = available
        logger.info(f"LLM默认值已设置: available={available}, models={list(clients.keys())}")

    # ---- 会话 CRUD ----

    async def get_or_create(self, session_id: str) -> PlayerSession:
        """获取已有会话，不存在则创建（复制全局 LLM 默认值）"""
        if session_id in self._sessions:
            return self._sessions[session_id]
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session = PlayerSession(
                session_id=session_id,
                created_at=now,
                llm_clients=dict(self._default_llm_clients),   # 复制默认客户端
                llm_available=self._default_llm_available,
            )
            self._sessions[session_id] = session
            # 确保数据目录存在
            self._ensure_dirs(session_id)
            logger.info(f"新会话创建: {session_id} (llm_available={session.llm_available})")
            return session

    def get(self, session_id: str) -> Optional[PlayerSession]:
        return self._sessions.get(session_id)

    async def remove(self, session_id: str):
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"会话已清除: {session_id}")

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    async def list_sessions(self) -> list[dict]:
        return [s.to_dict() for s in self._sessions.values()]

    # ---- 数据目录 ----

    def get_player_dir(self, session_id: str) -> Path:
        """获取玩家的数据根目录"""
        return self.project_dir / "data" / "players" / session_id

    def get_archive_dir(self, session_id: str) -> Path:
        return self.get_player_dir(session_id) / "archives"

    def get_npc_memory_dir(self, session_id: str) -> Path:
        return self.get_player_dir(session_id) / "npc_memory"

    def get_npc_relations_dir(self, session_id: str) -> Path:
        return self.get_player_dir(session_id) / "npc_relations"

    def _ensure_dirs(self, session_id: str):
        """确保玩家的数据目录存在"""
        self.get_archive_dir(session_id).mkdir(parents=True, exist_ok=True)
        self.get_npc_memory_dir(session_id).mkdir(parents=True, exist_ok=True)
        self.get_npc_relations_dir(session_id).mkdir(parents=True, exist_ok=True)

    # ---- LLM 客户端管理 ----

    async def set_player_api_key(self, session_id: str, api_key: str) -> bool:
        """为指定会话设置 API Key 并重建 LLM 客户端"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if not api_key or not api_key.strip():
            return False

        try:
            from server.infra.llm_client.hunyuan_client import TencentHunyuanClient
            from server.infra.llm_client.config import LLMRuntimeConfig

            runtime = LLMRuntimeConfig.from_env()
            runtime.advisor.api_key = api_key
            runtime.law.api_key = api_key
            runtime.enemy.api_key = api_key
            runtime.edict.api_key = api_key

            session.llm_clients = {
                "advisor": TencentHunyuanClient(runtime.advisor),
                "law": TencentHunyuanClient(runtime.law),
                "enemy": TencentHunyuanClient(runtime.enemy),
            }
            session.llm_available = True
            session.api_key = api_key
            logger.info(f"[{session_id}] LLM客户端已用玩家Key重建 (key={api_key[:8]}...)")
            return True
        except Exception as e:
            logger.error(f"[{session_id}] LLM客户端重建失败: {e}")
            return False

    # ---- 会话 TTL 清理 ----

    async def touch_session(self, session_id: str):
        """更新会话活动时间（由中间件每次请求调用）"""
        session = self._sessions.get(session_id)
        if session:
            session.touch()

    async def cleanup_expired(self) -> int:
        """清理过期会话（TTL 超时无活动），清理前自动持久化"""
        removed = 0
        now = datetime.now()
        async with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if not s.is_expired and (now - s.last_active).total_seconds() > _SESSION_TTL
            ]
            for sid in expired_ids:
                session = self._sessions[sid]
                session.is_expired = True
                # 清理前持久化 NPC 数据
                try:
                    if session.npc_memory_manager:
                        session.npc_memory_manager.save_all()
                except Exception as e:
                    logger.warning(f"[{sid}] TTL清理前保存NPC记忆失败: {e}")
                try:
                    if session.npc_relation_manager:
                        session.npc_relation_manager.persist_all()
                except Exception as e:
                    logger.warning(f"[{sid}] TTL清理前保存NPC关系失败: {e}")
                del self._sessions[sid]
                removed += 1
                logger.info(
                    f"会话已过期清理: {sid} "
                    f"(空闲={int((now - session.last_active).total_seconds())}s, "
                    f"TTL={_SESSION_TTL}s, 势力={session.faction_name})"
                )
        if removed:
            logger.info(f"TTL清理完成: 移除 {removed} 个过期会话, 剩余 {len(self._sessions)} 个")
        return removed

    def get_stats(self) -> dict:
        """获取会话统计信息"""
        now = datetime.now()
        total = len(self._sessions)
        active = sum(1 for s in self._sessions.values() if not s.is_expired)
        with_game = sum(1 for s in self._sessions.values() if s.world_state is not None)
        return {
            "total_sessions": total,
            "active_sessions": active,
            "with_game": with_game,
            "ttl_seconds": _SESSION_TTL,
            "oldest_idle_seconds": max(
                (now - s.last_active).total_seconds() for s in self._sessions.values()
            ) if self._sessions else 0,
        }

    # ---- 便利方法：获取当前请求的会话 ----

    def current(self) -> Optional[PlayerSession]:
        """获取当前请求上下文中的会话"""
        sid = _current_session_id.get()
        if sid is None:
            return None
        return self._sessions.get(sid)

    def require_current(self) -> PlayerSession:
        """获取当前会话，不存在则抛异常"""
        session = self.current()
        if session is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="未提供 X-Player-ID 请求头，请刷新页面")
        return session

    # ---- NPC 感知系统（延迟初始化，每人独立实例） ----

    def _ensure_npc_memory_manager(self, session_id: str):
        """为会话创建 NPC 记忆管理器（懒加载，目录隔离）"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        if session.npc_memory_manager is None:
            from server.agent.npc_memory import NPCMemoryManager
            data_dir = str(self.get_npc_memory_dir(session_id))
            session.npc_memory_manager = NPCMemoryManager(data_dir=data_dir)
            logger.info(f"[{session_id}] NPC记忆管理器已创建 (dir={data_dir})")
        return session.npc_memory_manager

    def _ensure_npc_relation_manager(self, session_id: str):
        """为会话创建 NPC 关系管理器（懒加载，目录隔离）"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        if session.npc_relation_manager is None:
            from server.agent.npc_relations import NPCRelationManager
            data_dir = str(self.get_npc_relations_dir(session_id))
            session.npc_relation_manager = NPCRelationManager(persist_dir=data_dir)
            logger.info(f"[{session_id}] NPC关系管理器已创建 (dir={data_dir})")
        return session.npc_relation_manager

    # ---- 存档相关（已迁移到 per-player 目录，提供兼容方法） ----

    def get_save_dir(self, session_id: str = None) -> Path:
        """兼容旧接口：获取存档目录"""
        if session_id:
            return self.get_archive_dir(session_id)
        sid = _current_session_id.get()
        if sid:
            return self.get_archive_dir(sid)
        return self.project_dir / "data" / "archives"  # 降级

    # ---- 全局配置（非会话相关） ----
    factions_config: dict = field(default_factory=dict)
    game_const: dict = field(default_factory=dict)
    critical_modules_ok: bool = True
    critical_module_errors: list = field(default_factory=list)
    startup_status: dict = field(default_factory=dict)


# ============================================================
# 单例
# ============================================================
_session_manager: Optional[SessionManager] = None


def init_session_manager(project_dir: Path) -> SessionManager:
    global _session_manager
    _session_manager = SessionManager(project_dir)
    return _session_manager


def get_session_manager() -> SessionManager:
    """获取全局 SessionManager 实例"""
    global _session_manager
    if _session_manager is None:
        raise RuntimeError("SessionManager 未初始化！请先调用 init_session_manager()")
    return _session_manager
