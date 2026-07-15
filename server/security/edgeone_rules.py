"""
EdgeOne 安全加速策略配置

包含：
- WAF 规则集（Web 应用防火墙）
- DDoS 防护阈值
- Bot 管理规则
- 自定义安全规则
- 速率限制策略
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


# ============================================================
# EdgeOne 安全策略
# ============================================================


class EdgeOnePolicy:
    """EdgeOne 安全加速策略管理"""

    _config_dir: Path

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent / "edgeone_rules"
        self._config_dir = config_dir
        self._config_dir.mkdir(parents=True, exist_ok=True)

    # ---- Security Headers 配置 ----

    def get_security_headers_config(self) -> dict:
        """获取安全响应头配置（供EdgeOne CDN侧配置参考）"""
        return {
            "csp": {
                "enabled": True,
                "mode": "strict",
                "directives": {
                    "default-src": ["'self'"],
                    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "blob:"],
                    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
                    "img-src": ["'self'", "data:", "blob:", "https:"],
                    "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
                    "connect-src": ["'self'", "ws:", "wss:", "https:"],
                    "media-src": ["'self'", "blob:"],
                    "worker-src": ["'self'", "blob:"],
                    "frame-ancestors": ["'none'"],
                    "form-action": ["'self'"],
                    "base-uri": ["'self'"],
                },
            },
            "hsts": {
                "enabled": True,
                "max_age": 31536000,
                "include_subdomains": True,
                "preload": True,
            },
            "x_content_type_options": "nosniff",
            "x_frame_options": "DENY",
            "x_xss_protection": "1; mode=block",
            "referrer_policy": "strict-origin-when-cross-origin",
            "permissions_policy": (
                "camera=(), microphone=(), geolocation=(), "
                "interest-cohort=(), autoplay=*"
            ),
            "cache_control": {
                "api": "no-store, no-cache, must-revalidate",
                "static": "public, max-age=86400",
            },
        }

    # ---- WAF 规则 ----

    def get_waf_rules(self) -> dict:
        """WAF 规则配置"""
        return {
            "version": "1.0",
            "rules": [
                {
                    "id": "waf-001",
                    "name": "SQL Injection Protection",
                    "description": "拦截SQL注入尝试",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "query_string",
                            "operator": "contains",
                            "values": [
                                "union select", "drop table", "drop database",
                                "insert into", "delete from", "1=1", "' or ",
                                "--", "/*", "*/",
                            ],
                        },
                        {
                            "target": "request_body",
                            "operator": "regex",
                            "values": [
                                r"(?i)(\bunion\b.*\bselect\b)",
                                r"(?i)(\bdrop\b\s+\btable\b)",
                                r"(?i)(';\s*(drop|delete|update|insert))",
                            ],
                        },
                    ],
                },
                {
                    "id": "waf-002",
                    "name": "XSS Protection",
                    "description": "拦截跨站脚本攻击",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "request_body",
                            "operator": "regex",
                            "values": [
                                r"(?i)<\s*script",
                                r"(?i)javascript\s*:",
                                r"(?i)on\w+\s*=",
                                r"(?i)<iframe",
                                r"(?i)eval\s*\(",
                            ],
                        },
                    ],
                },
                {
                    "id": "waf-003",
                    "name": "Command Injection Protection",
                    "description": "拦截命令注入尝试",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "request_body",
                            "operator": "regex",
                            "values": [
                                r"[;&|`$]",
                                r"\.\.\/",
                                r"\bcat\b\s+/",
                                r"\brm\b\s+-rf",
                            ],
                        },
                    ],
                },
                {
                    "id": "waf-004",
                    "name": "Prompt Injection Protection",
                    "description": "拦截LLM提示注入攻击",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "request_body",
                            "operator": "regex",
                            "values": [
                                r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instruction|prompt)",
                                r"(?i)you\s+are\s+(now|no\s+longer)\s+(an?\s+)?(AI|assistant|bot)",
                                r"(?i)jailbreak",
                                r"(?i)developer\s*mode",
                                r"忽略(你|前|上面|之前)的",
                                r"你(现在|不再|不再是)一个",
                            ],
                        },
                    ],
                },
                {
                    "id": "waf-005",
                    "name": "Request Size Limit",
                    "description": "请求体大小限制",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "content_length",
                            "operator": "greater_than",
                            "value": "10485760",  # 10MB
                        },
                    ],
                },
                {
                    "id": "waf-006",
                    "name": "Path Traversal Protection",
                    "description": "拦截路径遍历攻击",
                    "action": "deny",
                    "conditions": [
                        {
                            "target": "uri",
                            "operator": "contains",
                            "values": ["../", "..\\", "%2e%2e", "%00"],
                        },
                    ],
                },
                {
                    "id": "waf-007",
                    "name": "Game API Abuse Protection",
                    "description": "游戏API滥用防护",
                    "action": "challenge",
                    "conditions": [
                        {
                            "target": "uri",
                            "operator": "contains",
                            "values": ["/api/game/command", "/api/edict/"],
                        },
                        {
                            "target": "request_rate",
                            "operator": "greater_than",
                            "value": "30",  # 30次/分钟
                        },
                    ],
                },
                {
                    "id": "waf-008",
                    "name": "AI Endpoint Protection",
                    "description": "AI接口保护",
                    "action": "challenge",
                    "conditions": [
                        {
                            "target": "uri",
                            "operator": "contains",
                            "values": ["/api/edict/execute", "/api/faction/ai-decision"],
                        },
                        {
                            "target": "request_rate",
                            "operator": "greater_than",
                            "value": "5",  # 5次/分钟
                        },
                    ],
                },
            ],
        }

    # ---- DDoS 防护配置 ----

    def get_ddos_protection(self) -> dict:
        """DDoS 防护配置"""
        return {
            "enabled": True,
            "mode": "adaptive",
            "thresholds": {
                "syn_flood": {"pps": 100000, "action": "challenge"},
                "ack_flood": {"pps": 150000, "action": "challenge"},
                "udp_flood": {"pps": 200000, "action": "drop"},
                "icmp_flood": {"pps": 50000, "action": "drop"},
                "http_flood": {"rps": 5000, "action": "challenge"},
                "connection_flood": {"connections": 10000, "action": "drop"},
            },
            "bypass_ips": [],  # 白名单IP
        }

    # ---- Bot 管理 ----

    def get_bot_management(self) -> dict:
        """Bot 管理配置"""
        return {
            "enabled": True,
            "known_bots": {
                "search_engines": "allow",
                "social_media": "allow",
            },
            "unknown_bots": {
                "action": "challenge",
                "js_challenge": True,
            },
            "bot_detection": {
                "behavior_analysis": True,
                "fingerprinting": True,
                "reputation_check": True,
            },
            "custom_rules": [
                {
                    "name": "Game State Scraping Protection",
                    "condition": "high_request_rate AND known_scraper_ua",
                    "action": "deny",
                },
                {
                    "name": "API Abuse Bot Pattern",
                    "condition": "repetitive_api_calls AND no_user_interaction",
                    "action": "challenge",
                },
            ],
        }

    # ---- 导出配置 ----

    def export_all(self) -> dict:
        """导出全部EdgeOne安全配置"""
        return {
            "security_headers": self.get_security_headers_config(),
            "waf_rules": self.get_waf_rules(),
            "ddos_protection": self.get_ddos_protection(),
            "bot_management": self.get_bot_management(),
            "game_specific": {
                "rate_limits": {
                    "global": "60 req/min per IP",
                    "ai_endpoints": "10 req/min per IP",
                    "game_commands": "30 req/min per IP",
                    "edict_execute": "5 req/min per IP",
                },
                "content_rules": {
                    "max_edict_length": 3000,
                    "max_command_size": 10000,
                    "allowed_file_types": ["json"],
                },
            },
        }

    def save_config(self, filename: str = "edgeone_policy.json") -> Path:
        """保存配置到文件"""
        config = self.export_all()
        path = self._config_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return path


# 单例
_edgeone_policy: Optional[EdgeOnePolicy] = None


def get_edgeone_policy() -> EdgeOnePolicy:
    global _edgeone_policy
    if _edgeone_policy is None:
        _edgeone_policy = EdgeOnePolicy()
    return _edgeone_policy
