"""
HaS-Anonymizer 数据脱敏工具

功能:
- 敏感字段自动识别（PII、密钥、Token）
- 可配置脱敏规则（掩码、哈希、替换、截断）
- 日志/输出流的自动脱敏
- 支持嵌套结构的递归脱敏
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any, Optional


# ============================================================
# 默认敏感字段模式
# ============================================================

# PII 模式（含中文）
PII_PATTERNS = {
    "phone": re.compile(
        r'(\+?86[\-\s]?)?1[3-9]\d[\-\s]?\d{4}[\-\s]?\d{4}'
    ),
    "email": re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    ),
    "id_card": re.compile(
        r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    ),
    "ip_v4": re.compile(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ),
    "chinese_name": re.compile(
        r'(?:[\u4e00-\u9fa5]{2,4})(?:先生|女士|同志|老师)?'
    ),
    "wechat": re.compile(
        r'wxid_[a-zA-Z0-9_]{8,}'
    ),
}

# API密钥模式
API_KEY_PATTERNS = {
    "openai_key": re.compile(r'sk-[a-zA-Z0-9]{10,}'),
    "hunyuan_key": re.compile(r'(?:secret_id|secret_key|TENCENTCLOUD_SECRET)\s*[:=]\s*["\']?[A-Za-z0-9+/=]{20,}["\']?', re.I),
    "jwt_token": re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'),
    "bearer_token": re.compile(r'bearer\s+[a-zA-Z0-9_\-\.]{20,}', re.I),
    "api_key_generic": re.compile(r'(?:api[_-]?key|apikey|access[_-]?token)\s*[:=]\s*["\']?[a-zA-Z0-9_\-\.]{16,}["\']?', re.I),
}

# 敏感字段名（英文 + 中文）
SENSITIVE_FIELD_NAMES: set[str] = {
    "password", "passwd", "pwd", "secret", "token", "apikey", "api_key",
    "private_key", "secret_key", "secret_id", "access_token", "refresh_token",
    "credential", "credentials", "authorization", "auth",
    "密码", "口令", "密钥", "令牌", "认证", "身份证", "手机号", "邮箱",
    "银行卡", "卡号", "cvv", "ssn",
}


# ============================================================
# 脱敏器
# ============================================================


class Anonymizer:
    """HaS-Anonymizer 数据脱敏工具（单例）"""

    _instance: Optional["Anonymizer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 自定义敏感字段
        self._extra_sensitive_fields: set[str] = set()

        # 脱敏开关
        self._enabled = True
        self._mask_pii = True
        self._mask_api_keys = True
        self._mask_sensitive_fields = True

        # 统计
        self._total_masked = 0
        self._total_pii_detected = 0
        self._total_keys_detected = 0

    # ---- 配置 ----

    def configure(
        self,
        enabled: bool = True,
        mask_pii: bool = True,
        mask_api_keys: bool = True,
        mask_sensitive_fields: bool = True,
        extra_fields: Optional[list[str]] = None,
    ):
        self._enabled = enabled
        self._mask_pii = mask_pii
        self._mask_api_keys = mask_api_keys
        self._mask_sensitive_fields = mask_sensitive_fields
        if extra_fields:
            self._extra_sensitive_fields.update(extra_fields)

    def add_sensitive_field(self, field_name: str):
        """添加自定义敏感字段名"""
        self._extra_sensitive_fields.add(field_name)

    # ---- 脱敏方法 ----

    def anonymize(self, data: Any, max_depth: int = 10) -> Any:
        """
        递归脱敏任意数据结构

        data: 任意类型（str/dict/list/tuple）
        max_depth: 最大递归深度
        """
        if not self._enabled or max_depth <= 0:
            return data

        if isinstance(data, str):
            return self._anonymize_string(data)
        elif isinstance(data, Mapping):
            return self._anonymize_dict(dict(data), max_depth - 1)
        elif isinstance(data, (list, tuple)):
            return type(data)(
                self.anonymize(item, max_depth - 1) for item in data
            )
        else:
            return data

    def _anonymize_string(self, text: str) -> str:
        """脱敏字符串"""
        result = text
        masked_any = False

        # 1. 脱敏API密钥
        if self._mask_api_keys:
            for name, pattern in API_KEY_PATTERNS.items():
                if pattern.search(result):
                    result = pattern.sub(self._mask_key_match, result)
                    self._total_keys_detected += 1
                    masked_any = True

        # 2. 脱敏PII
        if self._mask_pii:
            for name, pattern in PII_PATTERNS.items():
                if pattern.search(result):
                    result = pattern.sub(self._mask_pii_match, result)
                    self._total_pii_detected += 1
                    masked_any = True

        if masked_any:
            self._total_masked += 1
        return result

    def _anonymize_dict(self, data: dict, max_depth: int) -> dict:
        """脱敏字典（递归 + 敏感字段名匹配）"""
        result = {}
        for key, value in data.items():
            # 检查字段名是否敏感
            key_lower = str(key).lower()
            is_sensitive = (
                key_lower in SENSITIVE_FIELD_NAMES
                or key_lower in self._extra_sensitive_fields
            )

            if self._mask_sensitive_fields and is_sensitive:
                result[key] = self._mask_value(value)
            elif isinstance(value, str):
                result[key] = self._anonymize_string(value)
            elif isinstance(value, Mapping):
                result[key] = self._anonymize_dict(dict(value), max_depth - 1)
            elif isinstance(value, (list, tuple)):
                result[key] = type(value)(
                    self.anonymize(item, max_depth - 1) for item in value
                )
            else:
                result[key] = value
        return result

    # ---- 掩码函数 ----

    def _mask_key_match(self, match: re.Match) -> str:
        """掩码API密钥匹配"""
        matched = match.group(0)
        # 保留前缀，其余掩码
        if ':' in matched or '=' in matched:
            # key=value 格式
            parts = re.split(r'([:=])', matched, maxsplit=1)
            if len(parts) >= 3:
                return f"{parts[0]}{parts[1]}[MASKED_{len(parts[2])}]"
        return f"[MASKED_KEY_{len(matched)}]"

    def _mask_pii_match(self, match: re.Match) -> str:
        """掩码PII匹配"""
        matched = match.group(0)
        if '@' in matched:
            # 邮箱：保留首字母和域名
            parts = matched.split('@')
            return f"{parts[0][0]}***@{parts[1]}"
        elif len(matched) > 8:
            # 其他长字符串
            visible = max(2, len(matched) // 4)
            return matched[:visible] + '*' * (len(matched) - visible * 2) + matched[-visible:]
        else:
            return '*' * len(matched)

    def _mask_value(self, value: Any) -> str:
        """掩码整个字段值（敏感字段全掩码）"""
        if isinstance(value, str):
            return '*' * min(len(value), 12)
        elif isinstance(value, (int, float)):
            return "[MASKED]"
        elif isinstance(value, (list, dict)):
            return f"[MASKED_COLLECTION_{len(value)}]"
        return "[MASKED]"

    # ---- 哈希化（不可逆脱敏） ----

    @staticmethod
    def hash_value(value: str, salt: str = "yuanmo3.0") -> str:
        """SHA256 哈希化（不可逆）"""
        return hashlib.sha256(f"{value}{salt}".encode()).hexdigest()[:16]

    @staticmethod
    def hash_ip(ip: str) -> str:
        """IP哈希化（保留前缀用于地理分析）"""
        segments = ip.split('.')
        if len(segments) == 4:
            hashed = hashlib.sha256(ip.encode()).hexdigest()[:8]
            return f"{segments[0]}.{segments[1]}.0.{hashed[:4]}"
        return hashlib.sha256(ip.encode()).hexdigest()[:12]

    # ---- 安全日志输出 ----

    def safe_log(self, message: str) -> str:
        """安全日志（自动脱敏后输出）"""
        return self._anonymize_string(message)

    def safe_dict_log(self, data: dict) -> dict:
        """安全字典日志"""
        return self._anonymize_dict(data, max_depth=5)

    # ---- 统计 ----

    def get_stats(self) -> dict:
        return {
            "total_masked": self._total_masked,
            "pii_detected": self._total_pii_detected,
            "keys_detected": self._total_keys_detected,
            "enabled": self._enabled,
            "mask_pii": self._mask_pii,
            "mask_api_keys": self._mask_api_keys,
        }


# 单例获取
def get_anonymizer() -> Anonymizer:
    return Anonymizer()
