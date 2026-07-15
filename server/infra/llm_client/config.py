"""
LLM配置模型与运行时管理
支持从 .env / llm_runtime.json 热加载
"""
from __future__ import annotations
import json
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("yuanmo.llm.config")

# ============================================================
# 模型常量
# ============================================================

# CodeBuddy API基地址（通过腾讯云CodeBuddy代理调用DeepSeek-V3）
HUNYUAN_API_BASE = "https://copilot.tencent.com/v2"

# 三层模型体系（统一使用DeepSeek-V3）
MODEL_ROLE = "deepseek-v3"           # 角色对话模型
MODEL_STRATEGY = "deepseek-v3"       # 战略推演模型
MODEL_FAST = "deepseek-v3"           # 快速推演模型

# 默认温度参数
TEMP_ROLE = 0.7       # 角色对话
TEMP_STRATEGY = 0.6   # 战略推演
TEMP_FAST = 0.65      # 快速推演

# 默认并发限制
MAX_CONCURRENT_AGENTS = 20

# 超时设置（秒）
API_TIMEOUT = 90


@dataclass
class LLMConfig:
    """单个LLM客户端配置"""
    provider: str                    # "hunyuan" | "deepseek" | "openai" | "ollama"
    api_base: str                   # API基地址
    api_key: str                    # API密钥
    model_name: str                 # 模型名称
    temperature: float = 0.7
    max_tokens: int = 4096
    extra_headers: dict = field(default_factory=dict)

    def to_openai_compatible(self) -> dict:
        """转换为OpenAI兼容格式"""
        return {
            "base_url": self.api_base.rstrip("/") + "/chat/completions",
            "api_key": self.api_key,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass
class LLMRuntimeConfig:
    """
    运行时LLM配置 - 三套模型客户端
    对应设计文档中的三层模型体系:
    - advisor: 君主/文臣/百姓对话/廷议辩论 (chat_role)
    - law:     年度战略推演/合纵判定/结局传记 (chat_strategy)
    - enemy:   瞬时灾害/单地块事件/战斗结算/贪腐判定/寿命检查/瘟疫传播 (chat_fast)
    """
    advisor: LLMConfig   # 角色对话模型
    law: LLMConfig        # 战略推演模型
    enemy: LLMConfig      # 快速推演模型
    max_concurrent: int = MAX_CONCURRENT_AGENTS
    fallback_enabled: bool = True

    @classmethod
    def from_env(cls) -> "LLMRuntimeConfig":
        """
        从环境变量加载配置
        优先级: .env > llm_runtime.json > 默认值
        """
        api_key = os.getenv("TENCENT_API_KEY", "")
        api_base = os.getenv("TENCENT_TOKENHUB_URL", HUNYUAN_API_BASE)

        # 尝试从 llm_runtime.json 加载
        runtime_json_path = Path(__file__).parent.parent.parent / "config" / "llm_runtime.json"
        if runtime_json_path.exists():
            try:
                with open(runtime_json_path, "r", encoding="utf-8") as f:
                    runtime_data = json.load(f)
                logger.info("从 llm_runtime.json 加载LLM运行时配置")
                return cls._from_dict(runtime_data, api_key, api_base)
            except Exception as e:
                logger.warning(f"llm_runtime.json 解析失败: {e}，使用环境变量")

        # 从环境变量构建
        return cls._from_env_vars(api_key, api_base)

    @classmethod
    def _from_env_vars(cls, api_key: str, api_base: str) -> "LLMRuntimeConfig":
        """从环境变量构建配置"""
        role_model = os.getenv("ROLE_AGENT_MODEL", MODEL_ROLE)
        strategy_model = os.getenv("STRATEGY_AGENT", MODEL_STRATEGY)
        fast_model = os.getenv("FAST_AGENT", MODEL_FAST)

        return cls(
            advisor=LLMConfig(
                provider="deepseek",
                api_base=api_base,
                api_key=api_key,
                model_name=role_model,
                temperature=TEMP_ROLE,
                max_tokens=4096,
            ),
            law=LLMConfig(
                provider="deepseek",
                api_base=api_base,
                api_key=api_key,
                model_name=strategy_model,
                temperature=TEMP_STRATEGY,
                max_tokens=8192,
            ),
            enemy=LLMConfig(
                provider="deepseek",
                api_base=api_base,
                api_key=api_key,
                model_name=fast_model,
                temperature=TEMP_FAST,
                max_tokens=2048,
            ),
        )

    @classmethod
    def _from_dict(cls, data: dict, api_key: str, api_base: str) -> "LLMRuntimeConfig":
        """从字典构建配置（llm_runtime.json）"""
        # 顶层 api_key / api_base 作为全局默认，可被分组块覆盖
        # 注意: json 中的空字符串不应覆盖环境变量的值
        json_api_key = data.get("api_key", "")
        if json_api_key:
            api_key = json_api_key
        json_api_base = data.get("api_base", "")
        if json_api_base:
            api_base = json_api_base
        advisors = data.get("advisors", {})
        laws = data.get("laws", {})
        enemies = data.get("enemies", {})

        return cls(
            advisor=LLMConfig(
                provider=advisors.get("provider", "hunyuan"),
                api_base=advisors.get("api_base", api_base),
                api_key=advisors.get("api_key", api_key),
                model_name=advisors.get("model", MODEL_ROLE),
                temperature=advisors.get("temperature", TEMP_ROLE),
                max_tokens=advisors.get("max_tokens", 4096),
            ),
            law=LLMConfig(
                provider=laws.get("provider", "hunyuan"),
                api_base=laws.get("api_base", api_base),
                api_key=laws.get("api_key", api_key),
                model_name=laws.get("model", MODEL_STRATEGY),
                temperature=laws.get("temperature", TEMP_STRATEGY),
                max_tokens=laws.get("max_tokens", 8192),
            ),
            enemy=LLMConfig(
                provider=enemies.get("provider", "hunyuan"),
                api_base=enemies.get("api_base", api_base),
                api_key=enemies.get("api_key", api_key),
                model_name=enemies.get("model", MODEL_FAST),
                temperature=enemies.get("temperature", TEMP_FAST),
                max_tokens=enemies.get("max_tokens", 2048),
            ),
            max_concurrent=data.get("max_concurrent", MAX_CONCURRENT_AGENTS),
            fallback_enabled=data.get("fallback_enabled", True),
        )


def create_clients_from_runtime(config: LLMRuntimeConfig) -> dict:
    """
    从运行时配置创建三套LLM客户端
    
    Returns:
        {"advisor": HunyuanClient, "law": HunyuanClient, "enemy": HunyuanClient}
    """
    from .factory import create_llm_client

    return {
        "advisor": create_llm_client(config.advisor),
        "law": create_llm_client(config.law),
        "enemy": create_llm_client(config.enemy),
    }
