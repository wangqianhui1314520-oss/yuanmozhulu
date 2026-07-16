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

# 超时设置（秒）— 按模型分组区分
API_TIMEOUT = 90                 # 默认超时
API_TIMEOUT_ADVISOR = 90         # 角色对话：允许较长时间生成
API_TIMEOUT_LAW = 120            # 战略推演：超长上下文，需更多时间
API_TIMEOUT_ENEMY = 45           # 快速推演：预期快速返回


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
        base = self.api_base.rstrip("/")
        # 避免重复拼接: 若 api_base 已以 /chat/completions 结尾则直接使用
        if base.endswith("/chat/completions"):
            url = base
        else:
            url = base + "/chat/completions"
        return {
            "base_url": url,
            "api_key": self.api_key,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass
class LLMRuntimeConfig:
    """
    运行时LLM配置 - 三套模型客户端 + 圣旨解析
    对应设计文档中的三层模型体系:
    - advisor: 君主/文臣/百姓对话/廷议辩论 (chat_role)
    - law:     年度战略推演/合纵判定/结局传记 (chat_strategy)
    - enemy:   瞬时灾害/单地块事件/战斗结算/贪腐判定/寿命检查/瘟疫传播 (chat_fast)
    - edict:   圣旨自然语言解析
    """
    advisor: LLMConfig   # 角色对话模型
    law: LLMConfig        # 战略推演模型
    enemy: LLMConfig      # 快速推演模型
    edict: LLMConfig = None  # 圣旨解析模型（可选，默认复用 advisor）
    max_concurrent: int = MAX_CONCURRENT_AGENTS
    fallback_enabled: bool = True

    def __post_init__(self):
        if self.edict is None:
            self.edict = LLMConfig(
                provider=self.advisor.provider,
                api_base=self.advisor.api_base,
                api_key=self.advisor.api_key,
                model_name=self.advisor.model_name,
                temperature=self.advisor.temperature,
                max_tokens=self.advisor.max_tokens,
            )

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
                config = cls._from_dict(runtime_data, api_key, api_base)
            except Exception as e:
                logger.warning(f"llm_runtime.json 解析失败: {e}，使用环境变量")
                config = cls._from_env_vars(api_key, api_base)
        else:
            # 从环境变量构建
            config = cls._from_env_vars(api_key, api_base)

        # 关键检查：API Key 为空时明确警告
        if not config.advisor.api_key:
            logger.warning(
                "LLM API Key 未配置！请设置环境变量 TENCENT_API_KEY "
                "或在 server/config/llm_runtime.json 中配置 api_key。"
                "所有 AI 功能将不可用（返回空文本/降级响应）。"
            )
        return config

    @classmethod
    def _from_env_vars(cls, api_key: str, api_base: str) -> "LLMRuntimeConfig":
        """从环境变量构建配置"""
        role_model = os.getenv("ROLE_AGENT_MODEL", MODEL_ROLE)
        strategy_model = os.getenv("STRATEGY_AGENT", MODEL_STRATEGY)
        fast_model = os.getenv("FAST_AGENT", MODEL_FAST)

        return cls(
            advisor=LLMConfig(
                provider="hunyuan",
                api_base=api_base,
                api_key=api_key,
                model_name=role_model,
                temperature=TEMP_ROLE,
                max_tokens=4096,
            ),
            law=LLMConfig(
                provider="hunyuan",
                api_base=api_base,
                api_key=api_key,
                model_name=strategy_model,
                temperature=TEMP_STRATEGY,
                max_tokens=8192,
            ),
            enemy=LLMConfig(
                provider="hunyuan",
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
        edict_data = data.get("edict", {})

        def _val(d: dict, key: str, default):
            """dict.get 但空字符串视为不存在（防 llm_runtime.json 的空 api_key 覆盖 env）"""
            v = d.get(key, "")
            return v if v else default

        return cls(
            advisor=LLMConfig(
                provider=_val(advisors, "provider", "hunyuan"),
                api_base=_val(advisors, "api_base", api_base),
                api_key=_val(advisors, "api_key", api_key),
                model_name=_val(advisors, "model", MODEL_ROLE),
                temperature=_val(advisors, "temperature", TEMP_ROLE),
                max_tokens=_val(advisors, "max_tokens", 4096),
            ),
            law=LLMConfig(
                provider=_val(laws, "provider", "hunyuan"),
                api_base=_val(laws, "api_base", api_base),
                api_key=_val(laws, "api_key", api_key),
                model_name=_val(laws, "model", MODEL_STRATEGY),
                temperature=_val(laws, "temperature", TEMP_STRATEGY),
                max_tokens=_val(laws, "max_tokens", 8192),
            ),
            enemy=LLMConfig(
                provider=_val(enemies, "provider", "hunyuan"),
                api_base=_val(enemies, "api_base", api_base),
                api_key=_val(enemies, "api_key", api_key),
                model_name=_val(enemies, "model", MODEL_FAST),
                temperature=_val(enemies, "temperature", TEMP_FAST),
                max_tokens=_val(enemies, "max_tokens", 2048),
            ),
            edict=LLMConfig(
                provider=_val(edict_data, "provider", _val(advisors, "provider", "hunyuan")),
                api_base=_val(edict_data, "api_base", api_base),
                api_key=_val(edict_data, "api_key", api_key),
                model_name=_val(edict_data, "model", _val(advisors, "model", MODEL_ROLE)),
                temperature=_val(edict_data, "temperature", _val(advisors, "temperature", TEMP_ROLE)),
                max_tokens=_val(edict_data, "max_tokens", _val(advisors, "max_tokens", 4096)),
            ),
            max_concurrent=data.get("max_concurrent", MAX_CONCURRENT_AGENTS),
            fallback_enabled=data.get("fallback_enabled", True),
        )


def create_clients_from_runtime(config: LLMRuntimeConfig) -> dict:
    """
    从运行时配置创建三套LLM客户端 + 圣旨解析

    Returns:
        {"advisor": HunyuanClient, "law": HunyuanClient, "enemy": HunyuanClient, "edict": HunyuanClient}
    """
    from .factory import create_llm_client

    return {
        "advisor": create_llm_client(config.advisor, agent_group="advisor"),
        "law": create_llm_client(config.law, agent_group="law"),
        "enemy": create_llm_client(config.enemy, agent_group="enemy"),
        "edict": create_llm_client(config.edict, agent_group="advisor"),
    }
