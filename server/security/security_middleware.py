"""
FastAPI 安全中间件 —— Security Headers、Rate Limiting、请求审计

基于 EdgeOne 安全加速最佳实践的中间件层:
- 安全响应头注入（CSP, HSTS, X-Frame-Options 等）
- 请求速率限制（滑动窗口 + Token Bucket）
- 请求/响应审计日志
- IP 黑白名单
- 请求体大小限制
"""

from __future__ import annotations

import time
import asyncio
from collections import defaultdict
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .ioa_engine import get_ioa_engine
from .agent_guard import get_agent_guard
from .anomaly_detector import get_anomaly_detector
from .data_validator import get_validator
from .anonymizer import get_anonymizer
from .audit_logger import get_audit_logger


# ============================================================
# EdgeOne 安全响应头
# ============================================================

EDGEONE_SECURITY_HEADERS: dict[str, str] = {
    # 内容安全策略（宽松版 - 游戏前端需要）
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "connect-src 'self' ws: wss: https:; "
        "media-src 'self' blob:; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'"
    ),
    # HTTPS 严格传输安全（一年）
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    # 禁止 MIME 类型嗅探
    "X-Content-Type-Options": "nosniff",
    # 禁止嵌入 iframe（防点击劫持）
    "X-Frame-Options": "DENY",
    # XSS 过滤器
    "X-XSS-Protection": "1; mode=block",
    # 引用策略
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # 权限策略
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), "
        "interest-cohort=(), autoplay=*"
    ),
    # 缓存控制（API响应不缓存）
    "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
    "Pragma": "no-cache",
    # EdgeOne 特定头
    "X-EdgeOne-Security": "enabled",
    # 服务器信息隐藏
    "Server": "EdgeOne",
}


# ============================================================
# 速率限制（Token Bucket）
# ============================================================


class RateLimiter:
    """基于滑动窗口的速率限制器（P3: 并发安全）"""

    def __init__(
        self,
        max_requests: int = 60,     # 每窗口最大请求数
        window_seconds: float = 60,  # 时间窗口（秒）
        burst_multiplier: float = 2.0  # 突发倍数
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self.burst = int(max_requests * burst_multiplier)

        # IP -> [(timestamp, count), ...]
        self._windows: dict[str, list[float]] = defaultdict(list)
        # 惩罚记录
        self._penalties: dict[str, float] = {}  # IP -> penalty_until
        # Bug #28修复: 按IP分片锁，避免单锁瓶颈
        self._ip_locks: dict[str, asyncio.Lock] = {}
        self._ip_locks_lock = asyncio.Lock()  # 保护_ip_locks字典本身

    async def _get_ip_lock(self, client_id: str) -> asyncio.Lock:
        """Bug #28修复: 获取/创建IP专属锁"""
        if client_id not in self._ip_locks:
            async with self._ip_locks_lock:
                if client_id not in self._ip_locks:
                    self._ip_locks[client_id] = asyncio.Lock()
        return self._ip_locks[client_id]

    async def is_allowed(self, client_id: str) -> tuple[bool, str]:
        """
        检查请求是否允许（P3: 并发安全 + Bug #28: IP分片锁）

        返回: (是否允许, 状态消息)
        """
        ip_lock = await self._get_ip_lock(client_id)
        async with ip_lock:
            now = time.time()

            # 检查惩罚
            if client_id in self._penalties:
                if now < self._penalties[client_id]:
                    return False, "rate_limited_penalty"
                del self._penalties[client_id]

            # 清理过期记录
            cutoff = now - self.window
            self._windows[client_id] = [
                t for t in self._windows[client_id] if t > cutoff
            ]

            # 如果滑动窗口为空且不在惩罚列表中，清理以释放内存
            if not self._windows[client_id]:
                del self._windows[client_id]

            current = len(self._windows.get(client_id, []))

            # 检查突发限制
            if current >= self.burst:
                # Bug #31修复: 阶梯升级策略 — 先返回429，再逐步升级
                self._penalties[client_id] = now + 60  # 第一次1分钟
                return False, "rate_limited_burst"

            # 检查正常限制
            if current >= self.max_requests:
                # Bug #31修复: 接近限流时先返回429不惩罚
                return False, "rate_limited"

            # 允许
            self._windows[client_id].append(now)
            return True, "allowed"

    async def get_usage(self, client_id: str) -> dict:
        """获取当前使用状态（Bug #32修复: 加锁保护）"""
        ip_lock = await self._get_ip_lock(client_id)
        async with ip_lock:
            now = time.time()
            cutoff = now - self.window
            recent = [t for t in self._windows.get(client_id, []) if t > cutoff]
            return {
                "current": len(recent),
                "limit": self.max_requests,
                "burst": self.burst,
                "penalty_until": self._penalties.get(client_id, 0),
            }

    async def cleanup_expired(self, now: float | None = None) -> int:
        """清理过期 IP 条目，防止内存泄漏（Bug #28修复: IP分片锁）

        返回: 清理的条目数
        """
        if now is None:
            now = time.time()
        cutoff = now - max(self.window, 600)  # 至少保留 10 分钟未活动的 IP
        penalty_cutoff = now - 3600  # 惩罚记录保留 1 小时

        # Bug #28修复: 使用 _ip_locks_lock 保护 _windows 和 _penalties 字典
        async with self._ip_locks_lock:
            # 清理滑动窗口
            stale_ips = [
                ip for ip, timestamps in self._windows.items()
                if (not timestamps or all(t <= cutoff for t in timestamps))
            ]
            for ip in stale_ips:
                del self._windows[ip]

            # 清理过期惩罚
            stale_penalties = [
                ip for ip, until in self._penalties.items()
                if until < penalty_cutoff
            ]
            for ip in stale_penalties:
                del self._penalties[ip]

        total = len(stale_ips) + len(stale_penalties)
        if total > 0:
            import logging
            logging.getLogger("yuanmo.security").debug(
                f"RateLimiter 清理过期条目: windows={len(stale_ips)}, penalties={len(stale_penalties)}"
            )
        return total


# ============================================================
# 中间件
# ============================================================


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全防护中间件"""

    # 排除安全头的路径（静态资源等）
    EXCLUDED_PATHS: set[str] = {"/api/health", "/docs", "/openapi.json", "/redoc"}

    # 不需要限流的路径（健康检查、配置查询等轻量操作）
    RATE_LIMIT_EXCLUDED: set[str] = {
        "/api/health", "/api/config", "/api/game/status",
        "/api/game/endings/config", "/api/game/endings/progress",
        "/api/tiles", "/api/map/tiles", "/api/game/ending",
    }

    def __init__(self, app, **kwargs):
        super().__init__(app)
        self._ioa = get_ioa_engine()
        self._validator = get_validator()
        self._anonymizer = get_anonymizer()
        self._audit = get_audit_logger()

        # 全局速率限制：60次/分钟
        self._global_limiter = RateLimiter(
            max_requests=60,
            window_seconds=60,
            burst_multiplier=2.0,
        )
        # AI调用速率限制：10次/分钟
        self._ai_limiter = RateLimiter(
            max_requests=10,
            window_seconds=60,
            burst_multiplier=1.5,
        )

        # P3: 定期清理过期 IP 条目，防止 DDoS/爬虫导致内存泄漏
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 每5分钟清理一次

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # P3: 定期清理过期 IP 条目，防止内存泄漏
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._last_cleanup = now
            await self._global_limiter.cleanup_expired(now)
            await self._ai_limiter.cleanup_expired(now)

        # 1. IP封禁检查
        if self._ioa.is_ip_blocked(client_ip):
            return JSONResponse(
                status_code=403,
                content={"code": 403, "msg": "Access Denied", "data": None},
            )

        # 2. 速率限制检查
        should_rate_limit = not any(
            path.startswith(p) for p in self.RATE_LIMIT_EXCLUDED
        )
        if should_rate_limit:
            # Bug #33修复: AI接口用精确路径匹配，防止子串误拦(如edict-history)
            ai_paths = ["/api/game/edict", "/api/game/ai-decision", "/api/game/test-llm"]
            if any(path.startswith(p) or path == p for p in ai_paths):
                allowed, reason = await self._ai_limiter.is_allowed(client_ip)
            else:
                allowed, reason = await self._global_limiter.is_allowed(client_ip)

            if not allowed:
                self._ioa.record_event(
                    "rate_limit",
                    "medium",
                    client_ip,
                    {"path": path, "reason": reason},
                    risk_score=20.0,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "msg": "请求过于频繁，请稍后再试",
                        "data": None,
                    },
                )

        # 3. 请求体大小检查（限制10MB）
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={"code": 413, "msg": "请求体过大", "data": None},
            )

        # 4. 执行请求
        try:
            response = await call_next(request)
        except Exception:
            # 异常由 api_server 全局处理
            raise

        elapsed = time.time() - start_time

        # 5. 注入安全响应头
        if path not in self.EXCLUDED_PATHS:
            for header, value in EDGEONE_SECURITY_HEADERS.items():
                response.headers.setdefault(header, value)

        # 6. 审计日志
        self._audit.log_request(
            method=request.method,
            path=path,
            client_ip=client_ip,
            status=response.status_code,
            latency_ms=elapsed * 1000,
        )

        return response


def setup_security(app: FastAPI):
    """
    一键安装所有安全模块到 FastAPI 应用

    用法:
        from server.security import setup_security
        setup_security(app)
    """
    # 1. 安全中间件
    app.add_middleware(SecurityMiddleware)

    # 2. 初始化各单例
    ioa = get_ioa_engine()
    guard = get_agent_guard()       # noqa: F841
    validator = get_validator()     # noqa: F841
    detector = get_anomaly_detector()  # noqa: F841
    anonymizer = get_anonymizer()   # noqa: F841
    audit = get_audit_logger()      # noqa: F841

    audit.log_security_event("[Security] 安全体系初始化完成", severity="info")

    return ioa
