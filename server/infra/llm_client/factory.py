"""
LLM客户端工厂

支持:
- "hunyuan"  → TencentHunyuanClient (通过 CodeBuddy 代理调用 DeepSeek-V3)
- "deepseek" → TencentHunyuanClient (DeepSeek API 兼容 OpenAI 格式，复用混元客户端)
- "openai"   → TencentHunyuanClient (OpenAI API 兼容格式，复用混元客户端)
- "ollama"   → TencentHunyuanClient (Ollama 本地部署，需配置本地地址)

注意：当前所有 provider 均通过 TencentHunyuanClient 发送请求。
不同 provider 的 api_base 和 model_name 由 config 层区分，客户端本身使用
OpenAI 兼容的 /chat/completions 端点，因此可以透明切换。
"""
from __future__ import annotations
import logging
from .config import LLMConfig
from .hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.llm.factory")


def create_llm_client(config: LLMConfig, agent_group: str = "unknown"):
    """
    根据provider创建LLM客户端
    
    所有 provider 统一使用 TencentHunyuanClient（OpenAI 兼容协议），
    通过 config.api_base 和 config.model_name 区分实际后端。
    
    如需接入非 OpenAI 兼容的 provider，请实现专用适配器类。
    
    Args:
        config: LLM配置
        agent_group: Agent分组标识 (advisor/law/enemy)，用于成本追踪
    
    Returns:
        TencentHunyuanClient 实例（使用完毕后需调用 close() 清理资源）
    """
    provider = config.provider.lower()

    if provider == "hunyuan":
        logger.info(f"创建混元客户端 [{agent_group}]: model={config.model_name}, base={config.api_base}")
    elif provider == "deepseek":
        logger.info(f"创建DeepSeek客户端 [{agent_group}]: model={config.model_name}, base={config.api_base}")
    elif provider == "openai":
        logger.info(f"创建OpenAI客户端 [{agent_group}]: model={config.model_name}, base={config.api_base}")
    elif provider == "ollama":
        logger.info(f"创建Ollama客户端 [{agent_group}]: model={config.model_name}, base={config.api_base}")
    else:
        logger.warning(f"未知provider '{provider}'，使用默认配置")

    return TencentHunyuanClient(config, agent_group=agent_group)
