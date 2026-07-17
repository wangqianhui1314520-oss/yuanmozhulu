"""
Agent配置热更新管理

支持:
- 从 agent_config.json 加载十大智能体的模型参数
- 运行时热重载（不重启服务）
- 文件监听（轮询检查 mtime 变化）
- 每Agent独立覆盖模型/温度/最大Token
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("yuanmo.agent.config")

# 默认配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "agent_config.json"


@dataclass
class AgentModelConfig:
    """单个Agent的模型配置"""
    agent_key: str                     # "A1" ~ "A10"
    model_name: str = ""               # 模型名（空=使用分组默认）
    temperature: float = -1.0          # 温度（-1=使用分组默认）
    max_tokens: int = -1               # 最大Token（-1=使用分组默认）
    enabled: bool = True               # 是否启用LLM调用
    extra_headers: dict = field(default_factory=dict)

    def get_override(self) -> dict:
        """获取有效的覆盖参数"""
        override = {}
        if self.model_name:
            override["model"] = self.model_name
        if self.temperature >= 0:
            override["temperature"] = self.temperature
        if self.max_tokens > 0:
            override["max_tokens"] = self.max_tokens
        if self.extra_headers:
            override["extra_headers"] = self.extra_headers
        return override


@dataclass
class AgentConfigSet:
    """十大智能体配置集合"""
    A1: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A1"))
    A2: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A2"))
    A3: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A3"))
    A4: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A4"))
    A5: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A5"))
    A6: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A6"))
    A7: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A7"))
    A8: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A8"))
    A9: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A9"))
    A10: AgentModelConfig = field(default_factory=lambda: AgentModelConfig(agent_key="A10"))

    def get(self, key: str) -> AgentModelConfig:
        return getattr(self, key, AgentModelConfig(agent_key=key))

    def to_dict(self) -> dict:
        result = {}
        for key in [f"A{i}" for i in range(1, 11)]:
            cfg = self.get(key)
            result[key] = {
                "model_name": cfg.model_name,
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "enabled": cfg.enabled,
            }
        return result


class AgentConfigManager:
    """
    Agent配置管理器 - 支持热更新

    用法:
        manager = AgentConfigManager()
        manager.load()  # 首次加载
        config = manager.get("A1")  # 获取A1配置
        manager.reload_if_changed()  # 检查并热更新
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._config_set = AgentConfigSet()
        self._last_mtime = 0.0
        self._lock = threading.Lock()
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_running = False

    # ========== 加载 ==========

    def load(self) -> AgentConfigSet:
        """加载配置文件"""
        with self._lock:
            if self._config_path.exists():
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._config_set = self._parse(data)
                    self._last_mtime = os.path.getmtime(self._config_path)
                    logger.info(
                        f"Agent配置加载完成 ({self._config_path}), "
                        f"agents: {[k for k in data.keys() if k.startswith('A')]}"
                    )
                except Exception as e:
                    logger.error(f"Agent配置加载失败: {e}，使用默认配置")
                    self._config_set = AgentConfigSet()
            else:
                logger.info("agent_config.json 不存在，使用默认配置")
                self._config_set = AgentConfigSet()
                self._save_default()

            return self._config_set

    def reload(self) -> AgentConfigSet:
        """强制重新加载"""
        self._last_mtime = 0.0
        return self.load()

    def reload_if_changed(self) -> bool:
        """如果文件有变化则热更新，返回是否更新"""
        if not self._config_path.exists():
            return False
        try:
            mtime = os.path.getmtime(self._config_path)
            if mtime > self._last_mtime:
                self.load()
                logger.info("检测到 agent_config.json 变更，已热更新")
                return True
        except Exception as e:
            logger.warning(f"检查配置变更失败: {e}")
        return False

    # ========== 查询 ==========

    def get(self, key: str) -> AgentModelConfig:
        with self._lock:
            return self._config_set.get(key)

    def get_all(self) -> dict[str, AgentModelConfig]:
        with self._lock:
            return {f"A{i}": self._config_set.get(f"A{i}") for i in range(1, 11)}

    def get_override(self, key: str) -> dict:
        """获取某Agent的有效模型覆盖参数"""
        cfg = self.get(key)
        if not cfg.enabled:
            return {"enabled": False}
        return cfg.get_override()

    def to_dict(self) -> dict:
        """导出所有Agent配置为字典（线程安全）"""
        with self._lock:
            return self._config_set.to_dict()

    # ========== 文件监听 ==========

    def start_watcher(self, interval: float = 5.0):
        """启动后台配置监听线程"""
        if self._watcher_running:
            return
        self._watcher_running = True
        self._watcher_thread = threading.Thread(
            target=self._watcher_loop,
            args=(interval,),
            daemon=True,
            name="agent-config-watcher",
        )
        self._watcher_thread.start()
        logger.info(f"Agent配置监听已启动 (interval={interval}s)")

    def stop_watcher(self):
        """停止配置监听"""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
            self._watcher_thread = None

    def _watcher_loop(self, interval: float):
        while self._watcher_running:
            try:
                self.reload_if_changed()
            except Exception as e:
                logger.warning(f"配置监听异常: {e}")
            time.sleep(interval)

    # ========== 内部 ==========

    def _parse(self, data: dict) -> AgentConfigSet:
        result = AgentConfigSet()
        for key in [f"A{i}" for i in range(1, 11)]:
            if key in data:
                cfg = data[key]
                agent_cfg = AgentModelConfig(
                    agent_key=key,
                    model_name=cfg.get("model_name", ""),
                    temperature=cfg.get("temperature", -1.0),
                    max_tokens=cfg.get("max_tokens", -1),
                    enabled=cfg.get("enabled", True),
                    extra_headers=cfg.get("extra_headers", {}),
                )
                setattr(result, key, agent_cfg)
        return result

    def _save_default(self):
        """保存默认配置文件"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            default = {
                "version": "1.0",
                "description": "十大智能体模型配置 - 修改后服务自动热更新",
                "A1": {"agent_name": "谋策阁", "model_group": "advisor", "model_name": "", "temperature": 0.7, "max_tokens": 4096, "enabled": True},
                "A2": {"agent_name": "群雄殿", "model_group": "advisor", "model_name": "", "temperature": 0.7, "max_tokens": 4096, "enabled": True},
                "A3": {"agent_name": "律法堂", "model_group": "advisor", "model_name": "", "temperature": 0.6, "max_tokens": 4096, "enabled": True},
                "A4": {"agent_name": "谍报司", "model_group": "enemy", "model_name": "", "temperature": 0.8, "max_tokens": 1024, "enabled": True},
                "A5": {"agent_name": "司天台", "model_group": "enemy", "model_name": "", "temperature": 0.7, "max_tokens": 1024, "enabled": True},
                "A6": {"agent_name": "外交署", "model_group": "law", "model_name": "", "temperature": 0.6, "max_tokens": 4096, "enabled": True},
                "A7": {"agent_name": "宗室府", "model_group": "advisor", "model_name": "", "temperature": 0.6, "max_tokens": 1024, "enabled": True},
                "A8": {"agent_name": "国史馆", "model_group": "law", "model_name": "", "temperature": 0.5, "max_tokens": 8192, "enabled": True},
                "A9": {"agent_name": "军机处", "model_group": "enemy", "model_name": "", "temperature": 0.6, "max_tokens": 2048, "enabled": True},
                "A10": {"agent_name": "度支司", "model_group": "law", "model_name": "", "temperature": 0.4, "max_tokens": 2048, "enabled": True},
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建默认Agent配置文件: {self._config_path}")
        except Exception as e:
            logger.warning(f"保存默认配置失败: {e}")


# ============================================================
# 全局单例
# ============================================================

_global_config_manager: Optional[AgentConfigManager] = None


def get_agent_config_manager() -> AgentConfigManager:
    """获取全局Agent配置管理器"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = AgentConfigManager()
        _global_config_manager.load()
        _global_config_manager.start_watcher(interval=5.0)
    return _global_config_manager
