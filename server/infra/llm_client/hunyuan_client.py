"""
LLM客户端 - 完整HTTP实现（通过CodeBuddy API代理调用DeepSeek-V3）

三层模型分组:
- chat_role():   角色对话模型 (advisor, 默认 t=0.7, max_tokens=4096)
- chat_strategy(): 战略推演模型 (law, 默认 t=0.6, max_tokens=8192)
- chat_fast():   快速推演模型 (enemy, 默认 t=0.65, max_tokens=2048)
- chat_role_with_tools(): FunctionCall工具调用模式
- _concurrency_semaphore: 并发限流 (asyncio.Semaphore(20))
- TokenUsage: Token消耗追踪（从API response usage字段提取）
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Any

import httpx

from .config import (
    LLMConfig, HUNYUAN_API_BASE, API_TIMEOUT,
    API_TIMEOUT_ADVISOR, API_TIMEOUT_LAW, API_TIMEOUT_ENEMY,
)
from .cost_tracker import get_cost_tracker

logger = logging.getLogger("yuanmo.llm.hunyuan")

# 全局并发信号量 — 按 agent_group 分组，避免 advisor 组占满全部槽位阻塞 law/enemy
MAX_CONCURRENT_AGENTS = 20
_CONCURRENCY_BY_GROUP = {
    "advisor": asyncio.Semaphore(10),  # 角色对话：最多10个并发
    "law": asyncio.Semaphore(5),       # 战略推演：最多5个并发
    "enemy": asyncio.Semaphore(5),     # 快速推演：最多5个并发
}
# 向后兼容的通用信号量（用于未分组的调用）
_concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)

def _get_concurrency_semaphore(agent_group: str = "") -> asyncio.Semaphore:
    """根据 agent_group 返回对应的并发信号量"""
    return _CONCURRENCY_BY_GROUP.get(agent_group, _concurrency_semaphore)


@dataclass
class TokenUsage:
    """单次API调用的Token消耗记录"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


# 全局Token消耗计数器（线程安全的简单计数）
_global_token_usage = TokenUsage()
_global_token_lock = asyncio.Lock()
_global_call_count = 0

_last_call_result: dict = {"label": "", "tokens": 0, "latency": 0.0, "ts": 0.0}

# 违规词模式 — 复用 prompt_registry 中的统一定义
from .prompt_registry import FORBIDDEN_TERMS as FORBIDDEN_PATTERNS

# 古文清洗映射
TEXT_CLEAN_MAP = {
    "OK": "善",
    "ok": "善",
    "666": "甚善",
    "bug": "疏漏",
    "Bug": "疏漏",
    "BUG": "疏漏",
    "error": "差池",
    "Error": "差池",
}


class TencentHunyuanClient:
    """
    腾讯混元大模型客户端
    
    通过 httpx 异步HTTP调用混元API
    支持三层模型体系 + FunctionCall工具调用
    """

    def __init__(self, config: LLMConfig, agent_group: str = "unknown"):
        self.config = config
        self.api_base = config.api_base.rstrip("/")
        self.api_key = config.api_key
        self.model_name = config.model_name
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.agent_group = agent_group  # advisor / law / enemy
        self.fallback_mode = False
        self._fallback_since: float = 0.0  # P3: 记录降级时间，用于自动恢复
        self._fallback_recovery_interval: float = 60.0  # 60秒后尝试恢复（原600s过于保守）
        self._fallback_lock = asyncio.Lock()  # 保护 fallback_mode 读写竞争
        self._client: Optional[httpx.AsyncClient] = None
        self._set_fallback = self._set_fallback_mode  # 便捷别名
        # Token 消耗追踪
        self._token_usage = TokenUsage()
        self._call_count = 0
        self._total_latency = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """懒加载httpx客户端（标准 Bearer Token 认证），按分组使用不同超时"""
        if self._client is None:
            # 按 agent_group 选择超时时间
            timeout_map = {
                "advisor": API_TIMEOUT_ADVISOR,
                "law": API_TIMEOUT_LAW,
                "enemy": API_TIMEOUT_ENEMY,
            }
            group_timeout = timeout_map.get(self.agent_group, API_TIMEOUT)
            # 3.2 修复: 使用配置的超时 + 连接池限制，防止资源耗尽
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(group_timeout, connect=15.0),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=30,
                    keepalive_expiry=30.0,
                ),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _set_fallback_mode(self):
        """线程安全地设置降级模式"""
        async with self._fallback_lock:
            self.fallback_mode = True
            self._fallback_since = time.time()

    # ============================================================
    # 三层模型调用接口
    # ============================================================

    async def chat_role(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        world_json: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        角色对话模型 (deepseek-v3 via CodeBuddy)
        
        用途: 君主自主推演 / 战报生成 / 群聊 / 廷议辩论 / 百姓对话
        
        Args:
            prompt: 用户输入（人设+记忆+局势+指令）
            system_prompt: 系统人设底座
            temperature: 温度参数(默认0.7，agent_config可覆盖)
            world_json: 世界局势JSON（可选，注入system）
            model: 模型名覆盖（None=使用客户端默认模型）
        """
        messages = self._build_messages(
            system_prompt=system_prompt,
            user_prompt=prompt,
            world_json=world_json,
        )
        return await self._call_api(
            messages=messages,
            temperature=temperature or self.temperature,
            label="chat_role",
            model=model,
        )

    async def chat_strategy(
        self,
        prompt: str,
        world_json: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        战略推演模型 (deepseek-v3 via CodeBuddy)
        
        用途: 年度战略推演 / 合纵判定 / 结局传记
        
        Args:
            prompt: 战略分析指令
            world_json: 完整世界局势JSON（注入system message）
            system_prompt: 额外系统提示
            temperature: 温度参数(默认0.6)
            model: 模型名覆盖（None=使用客户端默认模型）
        """
        # 战略推演使用超长上下文，world_json注入system
        full_system = world_json
        if system_prompt:
            full_system = f"{system_prompt}\n\n{world_json}"

        messages = self._build_messages(
            system_prompt=full_system,
            user_prompt=prompt,
        )
        return await self._call_api(
            messages=messages,
            temperature=temperature or 0.6,
            label="chat_strategy",
            model=model,
        )

    async def chat_fast(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        快速推演模型 (deepseek-v3 via CodeBuddy)
        
        用途: 天灾叙事 / 谍报行动 / 流民事件 / 祥瑞凶兆
        
        Args:
            prompt: 快速推演指令
            system_prompt: 系统提示
            temperature: 温度参数(默认0.65)
            model: 模型名覆盖（None=使用客户端默认模型）
        """
        messages = self._build_messages(
            system_prompt=system_prompt,
            user_prompt=prompt,
        )
        return await self._call_api(
            messages=messages,
            temperature=temperature or 0.65,
            label="chat_fast",
            model=model,
        )

    async def chat_role_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str = "",
        world_json: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """
        角色对话 + FunctionCall工具调用 (hunyuan-role)
        
        用途: Agent自主识别意图 → 调用TOOL_REGISTRY工具
        
        Returns:
            {
                "content": "AI回复文本",
                "tool_calls": [{"name": "raise_troops", "arguments": {"count": 5000}}, ...]
            }
        """
        messages = self._build_messages(
            system_prompt=system_prompt,
            user_prompt=prompt,
            world_json=world_json,
        )
        return await self._call_api_with_tools(
            messages=messages,
            tools=tools,
            temperature=temperature or self.temperature,
        )

    # ============================================================
    # 内部实现
    # ============================================================

    def _build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        world_json: Optional[str] = None,
    ) -> list[dict]:
        """构建messages数组（3.0 增强：注入检测 + 长度限制）"""
        from .prompt_registry import sanitize_user_input, INJECTION_PATTERNS
        
        messages = []
        
        # 安全检测：system prompt 中的注入模式
        if system_prompt and INJECTION_PATTERNS.search(system_prompt):
            logger.warning("检测到 system_prompt 中疑似注入模式，已清理")
            system_prompt = INJECTION_PATTERNS.sub("[已过滤]", system_prompt)
        
        # 安全检测：user prompt 净化
        user_prompt = sanitize_user_input(user_prompt, max_length=4000)
        
        # 限制 system prompt 总长度（防止上下文溢出）
        MAX_SYSTEM_LENGTH = 8000
        system_content = system_prompt or ""
        if world_json:
            json_str = world_json if isinstance(world_json, str) else json.dumps(world_json, ensure_ascii=False)
            if len(json_str) > 6000:
                logger.warning(f"world_json 过长 ({len(json_str)} 字符)，智能精简中")
                try:
                    wd = json.loads(json_str) if isinstance(json_str, str) else world_json
                    slim = {
                        "round": wd.get("round", 0),
                        "factions": {
                            k: {"name": v.get("name", k), "troops": v.get("troops", 0),
                                "territory": v.get("territory_count", 0),
                                "grain": v.get("grain", 0), "gold": v.get("gold", 0),
                                "stability": v.get("realm_stability", 50)}
                            for k, v in wd.get("factions", {}).items()
                        },
                        "summary": f"(共{len(wd.get('tiles', {}))}个地块细节省略)",
                    }
                    json_str = json.dumps(slim, ensure_ascii=False)
                except Exception:
                    json_str = json_str[:6000] + "..."
            if system_content:
                system_content = f"{system_content}\n\n当前天下全局局势沙盘数据:\n{json_str}"
            else:
                system_content = f"当前天下全局局势沙盘数据:\n{json_str}"
        
        if len(system_content) > MAX_SYSTEM_LENGTH:
            logger.warning(f"system_content 超长 ({len(system_content)} > {MAX_SYSTEM_LENGTH})，截断")
            system_content = system_content[:MAX_SYSTEM_LENGTH] + "\n...(截断)"

        if system_content:
            messages.append({"role": "system", "content": system_content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def _call_api(
        self,
        messages: list[dict],
        temperature: float,
        label: str = "chat",
        max_retries: int = 2,
        model: Optional[str] = None,
    ) -> str:
        """
        调用API（优先流式，失败回退非流式）

        带降级兜底:
        - Timeout → fallback_mode=True
        - 401/403 → 密钥错误 → 全局标记不可用 + 返回空文本
        - 429 → 额度耗尽 → 返回空文本
        - 其他异常 → 返回空文本

        每次成功调用自动从API响应提取usage并累计Token消耗
        """
        if not self.api_key:
            logger.warning(f"[{label}] API Key未配置，返回空文本")
            return ""

        async with self._fallback_lock:
            if self.fallback_mode:
                # P3: 自动恢复 — 降级超过 N 分钟后尝试重新调用 API
                if time.time() - self._fallback_since > self._fallback_recovery_interval:
                    logger.info(f"[{label}] 尝试从 fallback_mode 恢复...")
                    self.fallback_mode = False
                    # 不直接 return，继续走正常 API 调用流程
                else:
                    return self._local_fallback(label)

        start_ts = time.time()

        # 优先流式调用（带完整异常防护）
        skip_non_stream = False  # True 表示流式遇到401/403等不可重试错误
        try:
            result, usage = await asyncio.wait_for(
                self._call_api_stream(messages, temperature, label, max_retries, model),
                timeout=API_TIMEOUT + 30,  # 兜底超时（内层 httpx timeout 更短，先触发）
            )
            if result:
                await self._record_usage(usage, label, time.time() - start_ts)
                return result
            # result 为 None → 流式失败但可回退；result 为 "" → 401/403 等不可重试
            # 检查 result 是 None 还是 "" 来决定是否跳过非流式
            if result is not None:
                # result 是 ""，说明遇到了 401/403 等认证错误，不回退非流式
                skip_non_stream = True
            # 注意: result is None → 流式失败但可回退非流式
            #       result is "" → 认证错误，不回退（避免重复无效调用）
        except asyncio.TimeoutError:
            logger.warning(f"[{label}] 流式调用外层超时，回退非流式")
        except Exception as e:
            logger.warning(f"[{label}] 流式调用异常: {type(e).__name__}: {e}，回退非流式")

        # 流式失败，回退非流式（兼容旧版API）
        if not skip_non_stream:
            try:
                result, usage = await asyncio.wait_for(
                    self._call_api_non_stream(messages, temperature, label, max_retries, model),
                    timeout=API_TIMEOUT + 30,
                )
                if result is not None:
                    await self._record_usage(usage, label, time.time() - start_ts)
                    return result
            except asyncio.TimeoutError:
                logger.error(f"[{label}] 非流式调用也超时，降至本地fallback")
            except Exception as e:
                logger.error(f"[{label}] 非流式调用异常: {type(e).__name__}: {e}")

        # 全部失败，降级
        async with self._fallback_lock:
            self.fallback_mode = True
            self._fallback_since = time.time()
        return self._local_fallback(label)

    async def _call_api_non_stream(
        self,
        messages: list[dict],
        temperature: float,
        label: str,
        max_retries: int,
        model: Optional[str] = None,
    ) -> tuple[Optional[str], TokenUsage]:
        """非流式调用，返回 (文本, TokenUsage)"""
        usage = TokenUsage()
        effective_model = model or self.model_name
        payload = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        sem = _get_concurrency_semaphore(self.agent_group)
        async with sem:
            for attempt in range(max_retries + 1):
                try:
                    client = await self._get_client()
                    url = f"{self.api_base}/chat/completions"

                    logger.info(
                        f"[{label}] 非流式调用 {effective_model} "
                        f"(attempt={attempt+1}, t={temperature})"
                    )

                    response = await client.post(url, json=payload)
                    status = response.status_code

                    if status == 200:
                        data = response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        # 提取 Token 消耗
                        usage = _extract_usage(data)

                        logger.info(
                            f"[{label}] 成功 (content_len={len(content)}, "
                            f"tokens={usage.total_tokens} "
                            f"prompt={usage.prompt_tokens} completion={usage.completion_tokens})"
                        )
                        return self._clean_text(content), usage

                    elif status == 429:
                        logger.warning(f"[{label}] 额度耗尽(429): {response.text[:200]}")
                        await self._set_fallback_mode()
                        return self._local_fallback(label), usage

                    elif status in (401, 403):
                        logger.error(f"[{label}] 密钥错误({status}): {response.text[:200]}")
                        return "", usage

                    else:
                        logger.warning(f"[{label}] HTTP {status}: {response.text[:200]}")
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return None, usage

                except httpx.TimeoutException:
                    logger.warning(f"[{label}] 非流式超时 (attempt={attempt+1})")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None, usage

                except Exception as e:
                    logger.error(f"[{label}] 非流式异常: {type(e).__name__}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None, usage

        return None, usage

    async def _call_api_stream(
        self,
        messages: list[dict],
        temperature: float,
        label: str,
        max_retries: int,
        model: Optional[str] = None,
    ) -> tuple[str, TokenUsage]:
        """流式调用，返回 (文本, TokenUsage)"""
        usage = TokenUsage()
        effective_model = model or self.model_name
        payload = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        sem = _get_concurrency_semaphore(self.agent_group)
        async with sem:
            for attempt in range(max_retries + 1):
                try:
                    client = await self._get_client()
                    url = f"{self.api_base}/chat/completions"

                    logger.info(
                        f"[{label}] 流式调用 {effective_model} "
                        f"(attempt={attempt+1}, t={temperature})"
                    )

                    full_content = ""
                    last_usage_raw = {}
                    async with client.stream("POST", url, json=payload) as response:
                        status = response.status_code

                        if status == 200:
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str.strip() == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(data_str)
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            full_content += content
                                        # 流式最后一个chunk可能包含usage
                                        if "usage" in chunk:
                                            last_usage_raw = chunk["usage"]
                                    except json.JSONDecodeError:
                                        continue
                            # 从最后一个chunk提取usage
                            usage = _extract_usage({"usage": last_usage_raw} if last_usage_raw else {})
                            # 如果流式未返回usage，尝试从响应头估算
                            if usage.total_tokens == 0:
                                logger.debug(f"[{label}] 流式未返回usage，使用估算")
                                prompt_est = sum(len(m.get("content", "")) // 2 for m in messages)
                                comp_est = len(full_content) // 2
                                usage = TokenUsage(
                                    prompt_tokens=prompt_est,
                                    completion_tokens=comp_est,
                                    total_tokens=prompt_est + comp_est,
                                )
                            logger.info(
                                f"[{label}] 流式成功 (content_len={len(full_content)}, "
                                f"tokens={usage.total_tokens} "
                                f"prompt={usage.prompt_tokens} completion={usage.completion_tokens})"
                            )
                            return self._clean_text(full_content), usage

                        elif status == 429:
                            body = await response.aread()
                            logger.warning(f"[{label}] 流式额度耗尽(429): {body.decode()[:200]}")
                            await self._set_fallback_mode()
                            return self._local_fallback(label), usage

                        elif status in (401, 403):
                            body = await response.aread()
                            logger.error(f"[{label}] 流式密钥错误({status}): {body.decode()[:200]}")
                            return "", usage

                        else:
                            body = await response.aread()
                            logger.warning(f"[{label}] 流式HTTP {status}: {body.decode()[:200]}")
                            if attempt < max_retries:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            # 返回 None 而非 ""，让 _call_api 尝试非流式回退
                            return None, usage

                except httpx.TimeoutException:
                    logger.warning(f"[{label}] 流式超时 (attempt={attempt+1})")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    # 流式超时 → 设置降级但返回 None，让 _call_api 尝试非流式回退
                    await self._set_fallback_mode()
                    return None, usage

                except Exception as e:
                    logger.error(f"[{label}] 流式异常: {type(e).__name__}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None, usage

        return None, usage

    async def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_retries: int = 2,
    ) -> dict:
        """
        调用腾讯混元API（FunctionCall工具模式，优先非流式）

        Returns:
            {"content": "...", "tool_calls": [...]}
        """
        if not self.api_key:
            return {"content": "", "tool_calls": []}

        if self.fallback_mode:
            return {"content": self._local_fallback("tools"), "tool_calls": []}

        # 先尝试非流式
        result = await self._call_tools_non_stream(messages, tools, temperature, max_retries)
        if result is not None:
            return result

        # 非流式失败，尝试流式
        logger.info("[chat_role_with_tools] 非流式失败，尝试流式模式")
        return await self._call_tools_stream(messages, tools, temperature, max_retries)

    async def _call_tools_non_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_retries: int,
    ) -> Optional[dict]:
        """非流式工具调用"""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
        }

        sem = _get_concurrency_semaphore(self.agent_group)
        async with sem:
            for attempt in range(max_retries + 1):
                try:
                    client = await self._get_client()
                    url = f"{self.api_base}/chat/completions"

                    logger.info(
                        f"[chat_role_with_tools] 非流式调用 {self.model_name} "
                        f"(tools={len(tools)}, attempt={attempt+1})"
                    )

                    response = await client.post(url, json=payload)
                    status = response.status_code

                    if status == 200:
                        data = response.json()
                        msg = data.get("choices", [{}])[0].get("message", {})
                        content = msg.get("content", "")
                        raw_tool_calls = msg.get("tool_calls", [])

                        # 提取 Token 消耗
                        usage = _extract_usage(data)

                        tool_calls = []
                        for tc in raw_tool_calls:
                            fn = tc.get("function", {})
                            try:
                                args = json.loads(fn.get("arguments", "{}"))
                            except json.JSONDecodeError:
                                args = {}
                            tool_calls.append({
                                "name": fn.get("name", ""),
                                "arguments": args,
                            })

                        logger.info(
                            f"[chat_role_with_tools] 非流式成功 "
                            f"(content_len={len(content)}, tool_calls={len(tool_calls)}, "
                            f"tokens={usage.total_tokens})"
                        )
                        await self._record_usage(usage, "chat_role_with_tools", 0)
                        return {"content": self._clean_text(content), "tool_calls": tool_calls}

                    elif status == 429:
                        logger.warning(f"[chat_role_with_tools] 非流式额度耗尽(429): {response.text[:200]}")
                        await self._set_fallback_mode()
                        return {"content": self._local_fallback("tools"), "tool_calls": []}

                    elif status in (401, 403):
                        logger.error(f"[chat_role_with_tools] 非流式密钥错误({status}): {response.text[:200]}")
                        return {"content": "", "tool_calls": []}

                    else:
                        logger.warning(f"[chat_role_with_tools] 非流式HTTP {status}: {response.text[:200]}")
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return None

                except httpx.TimeoutException:
                    logger.warning(f"[chat_role_with_tools] 非流式超时 (attempt={attempt+1})")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None

                except Exception as e:
                    logger.error(f"[chat_role_with_tools] 非流式异常: {type(e).__name__}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None

        return None

    async def _call_tools_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_retries: int,
    ) -> dict:
        """流式工具调用"""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "stream": True,
        }

        sem = _get_concurrency_semaphore(self.agent_group)
        async with sem:
            for attempt in range(max_retries + 1):
                try:
                    client = await self._get_client()
                    url = f"{self.api_base}/chat/completions"

                    logger.info(
                        f"[chat_role_with_tools] 流式调用 {self.model_name} "
                        f"(tools={len(tools)}, attempt={attempt+1})"
                    )

                    full_content = ""
                    tool_calls_acc: dict[int, dict] = {}
                    last_usage_raw = {}

                    async with client.stream("POST", url, json=payload) as response:
                        status = response.status_code

                        if status == 200:
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str.strip() == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(data_str)
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            full_content += content
                                        for tc in delta.get("tool_calls", []):
                                            idx = tc.get("index", 0)
                                            if idx not in tool_calls_acc:
                                                tool_calls_acc[idx] = {
                                                    "id": tc.get("id", ""),
                                                    "name": "",
                                                    "arguments": "",
                                                }
                                            if tc.get("id"):
                                                tool_calls_acc[idx]["id"] = tc["id"]
                                            if tc.get("function", {}).get("name"):
                                                tool_calls_acc[idx]["name"] = tc["function"]["name"]
                                            if tc.get("function", {}).get("arguments"):
                                                tool_calls_acc[idx]["arguments"] += tc["function"]["arguments"]
                                        # 流式最后一个chunk可能包含usage
                                        if "usage" in chunk:
                                            last_usage_raw = chunk["usage"]
                                    except json.JSONDecodeError:
                                        continue

                            tool_calls = []
                            for idx in sorted(tool_calls_acc.keys()):
                                tc = tool_calls_acc[idx]
                                try:
                                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                                except json.JSONDecodeError:
                                    args = {}
                                tool_calls.append({
                                    "name": tc["name"],
                                    "arguments": args,
                                })

                            # 提取usage
                            usage = _extract_usage({"usage": last_usage_raw} if last_usage_raw else {})
                            logger.info(
                                f"[chat_role_with_tools] 流式成功 "
                                f"(content_len={len(full_content)}, tool_calls={len(tool_calls)}, "
                                f"tokens={usage.total_tokens})"
                            )
                            await self._record_usage(usage, "chat_role_with_tools", 0)
                            return {"content": self._clean_text(full_content), "tool_calls": tool_calls}

                        elif status == 429:
                            body = await response.aread()
                            logger.warning(f"[chat_role_with_tools] 流式额度耗尽(429): {body.decode()[:200]}")
                            await self._set_fallback_mode()
                            return {"content": self._local_fallback("tools"), "tool_calls": []}

                        elif status in (401, 403):
                            body = await response.aread()
                            logger.error(f"[chat_role_with_tools] 流式密钥错误({status}): {body.decode()[:200]}")
                            return {"content": "", "tool_calls": []}

                        else:
                            body = await response.aread()
                            logger.warning(f"[chat_role_with_tools] 流式HTTP {status}: {body.decode()[:200]}")
                            if attempt < max_retries:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {"content": "", "tool_calls": []}

                except httpx.TimeoutException:
                    logger.warning(f"[chat_role_with_tools] 流式超时 (attempt={attempt+1})")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    await self._set_fallback_mode()
                    return {"content": self._local_fallback("tools"), "tool_calls": []}

                except Exception as e:
                    logger.error(f"[chat_role_with_tools] 流式异常: {type(e).__name__}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return {"content": "", "tool_calls": []}

        return {"content": "", "tool_calls": []}

    # ============================================================
    # Token 消耗追踪
    # ============================================================

    async def _record_usage(self, usage: TokenUsage, label: str, latency: float):
        """记录一次API调用的Token消耗（使用异步锁保护全局计数器）+ 成本追踪"""
        global _global_token_usage, _global_call_count, _last_call_result
        self._token_usage += usage
        self._call_count += 1
        self._total_latency += latency
        async with _global_token_lock:
            _global_token_usage += usage
            _global_call_count += 1
        _last_call_result = {
            "label": label,
            "tokens": usage.total_tokens,
            "latency": round(latency, 3),
            "ts": time.time(),
        }
        # 集成成本追踪器
        try:
            cost_tracker = get_cost_tracker()
            cost_tracker.record(
                agent_group=self.agent_group,
                model=self.model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency=latency,
                label=label,
            )
        except Exception as e:
            logger.debug(f"成本追踪写入失败（不影响主流程）: {e}")
        if usage.total_tokens > 0:
            logger.info(
                f"[TOKEN] {label} 消耗 {usage.total_tokens} tokens "
                f"(prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
                f"latency={latency:.2f}s 累计={self._token_usage.total_tokens})"
            )

    def get_token_stats(self) -> dict:
        """获取当前客户端Token消耗统计"""
        return {
            "total_tokens": self._token_usage.total_tokens,
            "prompt_tokens": self._token_usage.prompt_tokens,
            "completion_tokens": self._token_usage.completion_tokens,
            "call_count": self._call_count,
            "avg_latency": round(self._total_latency / max(self._call_count, 1), 3),
            "last_call": _last_call_result,
        }

    @staticmethod
    def get_global_token_stats() -> dict:
        """获取全局Token消耗统计（所有客户端汇总）"""
        return {
            "total_tokens": _global_token_usage.total_tokens,
            "prompt_tokens": _global_token_usage.prompt_tokens,
            "completion_tokens": _global_token_usage.completion_tokens,
            "total_calls": _global_call_count,
            "last_call": _last_call_result,
        }

    # ============================================================
    # 文本清洗
    # ============================================================

    def _clean_text(self, text: str) -> str:
        """
        清洗AI回复文本:
        - 现代词汇 → 古文映射 (OK→善, 666→甚善, bug→疏漏)
        - 去除Markdown标记
        - 违规词拦截
        """
        if not text:
            return ""

        # 现代词汇映射（使用词边界匹配，避免误伤包含这些字母的正常词）
        for modern, ancient in TEXT_CLEAN_MAP.items():
            text = re.sub(r'\b' + re.escape(modern) + r'\b', ancient, text)

        # 去除Markdown标记
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # **粗体**
        text = re.sub(r"\*(.+?)\*", r"\1", text)        # *斜体*
        text = re.sub(r"`(.+?)`", r"\1", text)           # `代码`
        text = re.sub(r"#{1,6}\s?", "", text)            # # 标题
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)  # [链接](url)

        # 违规词拦截
        if FORBIDDEN_PATTERNS.search(text):
            logger.warning("检测到违规词，已拦截")
            return "（内容已过滤）"

        return text.strip()

    def _local_fallback(self, label: str = "") -> str:
        """本地降级兜底 — 按 Agent 分组和标签提供更智能的降级文本"""
        # 按模型分组提供上下文降级
        if self.agent_group == "advisor":
            # 角色对话类 — 保持角色沉浸感
            advisor_fallbacks = {
                "chat_role": "时局未明，容臣思之。",
                "advisor": "主公当务之急：稳固根基，静待天时。臣以为，不可冒进，当以守为攻。",
                "law": "此案证据不足，本官需再行查证，不可草率定谳。",
                "ruler": "今日暂且休朝。诸卿各司其职，有事明日再议。",
                "royal": "宗室之事，事关重大。容臣仔细斟酌，再行禀报。",
                "tools": "暂且按兵不动。",
            }
            return advisor_fallbacks.get(label, "时局未明，容臣思之。")
        
        elif self.agent_group == "law":
            # 战略推演类 — 提供有实质内容的分析
            strategy_fallbacks = {
                "chat_strategy": (
                    "主公当务之急有三：其一，稳固根基，广积粮草，精练士卒；"
                    "其二，静观天下大势，不可贸然出击；"
                    "其三，加强与盟友之联络，以防不测。"
                    "天下大势，分久必合，合久必分。此刻当以守为攻，蓄势待发。"
                ),
                "diplomacy": "当前外交局势复杂，宜以静制动。保持现有盟约，同时密派使臣探查各方动态。",
                "history": "史官秉笔直书，此间大事当如实记载，传之后世。",
                "tools": "暂且观望。",
            }
            return strategy_fallbacks.get(label, strategy_fallbacks.get("chat_strategy", "容臣思之。"))
        
        elif self.agent_group == "enemy":
            # 快速推演类 — 简洁明了
            enemy_fallbacks = {
                "chat_fast": "无事。",
                "espionage": "禀主公：暂无紧要军情。各处眼线皆无异动。",
                "event": "今日无事。",
                "tools": "暂且按兵不动。",
            }
            return enemy_fallbacks.get(label, "无事。")
        
        # 通用降级
        fallbacks = {
            "chat_role": "时局未明，容臣思之。",
            "chat_strategy": "主公当务之急：稳固根基，广积粮草，精练士卒，静待天时。",
            "chat_fast": "无事。",
            "tools": "暂且按兵不动。",
        }
        return fallbacks.get(label, "——")




# ============================================================
# Token 提取工具函数
# ============================================================

def _extract_usage(data: dict) -> TokenUsage:
    """从API响应中提取Token消耗信息"""
    usage_raw = data.get("usage", {})
    if not usage_raw:
        return TokenUsage()
    return TokenUsage(
        prompt_tokens=usage_raw.get("prompt_tokens", 0),
        completion_tokens=usage_raw.get("completion_tokens", 0),
        total_tokens=usage_raw.get("total_tokens", 0),
    )


def get_global_token_usage() -> TokenUsage:
    """获取全局Token消耗累计"""
    return _global_token_usage


def reset_global_token_usage():
    """重置全局Token计数器"""
    global _global_token_usage, _global_call_count, _last_call_result
    _global_token_usage = TokenUsage()
    _global_call_count = 0
    _last_call_result = {"label": "", "tokens": 0, "latency": 0.0, "ts": 0.0}


# ============================================================
# 全局客户端管理
# ============================================================

_global_clients: Optional[dict] = None
_global_lock = asyncio.Lock()


def reset_global_clients():
    """清除全局客户端缓存（热更新后调用，强制从文件重建）"""
    global _global_clients
    _global_clients = None
    logger.info("全局LLM客户端缓存已清除")


async def get_global_clients() -> dict:
    """获取或初始化全局LLM客户端"""
    global _global_clients
    if _global_clients is not None:
        return _global_clients

    async with _global_lock:
        if _global_clients is not None:
            return _global_clients

        from .config import LLMRuntimeConfig, create_clients_from_runtime

        runtime_config = LLMRuntimeConfig.from_env()
        _global_clients = create_clients_from_runtime(runtime_config)

        ai_available = bool(runtime_config.advisor.api_key)
        logger.info(
            f"全局LLM客户端初始化完成 "
            f"(advisor={runtime_config.advisor.model_name}, "
            f"law={runtime_config.law.model_name}, "
            f"enemy={runtime_config.enemy.model_name}, "
            f"ai_available={ai_available})"
        )
        return _global_clients


async def close_global_clients():
    """关闭所有全局LLM客户端"""
    global _global_clients
    if _global_clients:
        for key, client in _global_clients.items():
            if hasattr(client, "close"):
                await client.close()
        _global_clients = None
        logger.info("全局LLM客户端已关闭")
