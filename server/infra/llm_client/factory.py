"""
LLM客户端工厂

支持:
- "hunyuan"  → TencentHunyuanClient (完整HTTP实现)
- "deepseek" → TencentHunyuanClient (暂用混元回退)
- "openai"   → TencentHunyuanClient (暂用混元回退)
- "ollama"   → TencentHunyuanClient (暂用混元回退)
"""
from __future__ import annotations
import logging
from .config import LLMConfig
from .hunyuan_client import TencentHunyuanClient

logger = logging.getLogger("yuanmo.llm.factory")


def create_llm_client(config: LLMConfig):
    """
    根据provider创建LLM客户端
    
    当前所有provider统一使用 TencentHunyuanClient，
    后续可扩展 DeepSeek/OpenAI/Ollama 专用客户端。
    """
    provider = config.provider.lower()

    if provider == "hunyuan":
        logger.info(f"创建混元客户端: {config.model_name}")
        return TencentHunyuanClient(config)

    elif provider == "deepseek":
        logger.info(f"创建DeepSeek客户端(混元回退): {config.model_name}")
        return TencentHunyuanClient(config)

    elif provider == "openai":
        logger.info(f"创建OpenAI客户端(混元回退): {config.model_name}")
        return TencentHunyuanClient(config)

    elif provider == "ollama":
        logger.info(f"创建Ollama客户端(混元回退): {config.model_name}")
        return TencentHunyuanClient(config)

    else:
        logger.warning(f"未知provider '{provider}'，使用混元回退")
        return TencentHunyuanClient(config)
