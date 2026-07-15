"""
数据交互校验器 —— 输入清洗、Schema校验、注入防御

功能:
- 请求体Schema校验（类型、范围、必需字段）
- SQL/NoSQL/命令注入防御
- XSS/HTML注入防御
- 字段长度和格式限制
- 敏感字段自动脱敏
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from .ioa_engine import get_ioa_engine
from .audit_logger import get_audit_logger


# ============================================================
# 校验规则
# ============================================================

# SQL注入模式
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\bunion\b.*\bselect\b)", re.I),
    re.compile(r"(\bdrop\b\s+\btable\b|\bdrop\b\s+\bdatabase\b)", re.I),
    re.compile(r"(\bdelete\b\s+\bfrom\b)", re.I),
    re.compile(r"(\binsert\b\s+\binto\b)", re.I),
    re.compile(r"(\bupdate\b\s+\w+\s+\bset\b)", re.I),
    re.compile(r"(--|\#|/\*.*\*/)", re.I),
    re.compile(r"(\bexec\b\s*\()", re.I),
    re.compile(r"(';\s*(drop|delete|update|insert))", re.I),
]

# 命令注入模式
# Bug #27修复: 放宽对游戏文本中 & 符号的误拦，使用更精确的模式
COMMAND_INJECTION_PATTERNS = [
    re.compile(r"\;.*\b(cat|rm|curl|wget|bash|sh|python|perl)\b"),  # 分号+命令
    re.compile(r"\|\s*\b(cat|rm|curl|wget|bash|sh)\b"),  # 管道+命令
    re.compile(r"\`[^`]*\`"),  # 反引号命令替换
    re.compile(r"\$\([^)]*\)"),  # $(...)命令替换
    re.compile(r"\.\.\/"),
    re.compile(r"%00"),
    re.compile(r"\bcat\b\s+/"),
    re.compile(r"\brm\b\s+-rf"),
    re.compile(r"\bcurl\b\s+"),
    re.compile(r"\bwget\b\s+"),
]

# XSS模式
XSS_PATTERNS = [
    re.compile(r"<\s*script", re.I),
    re.compile(r"javascript\s*:", re.I),
    re.compile(r"on\w+\s*=", re.I),
    re.compile(r"<iframe", re.I),
    re.compile(r"<embed", re.I),
    re.compile(r"<object", re.I),
    re.compile(r"eval\s*\(", re.I),
    re.compile(r"expression\s*\(", re.I),
    re.compile(r"document\.cookie", re.I),
]

# Prompt注入模式（LLM特有风险）
# Bug #30修复: 删除过于宽泛的中文模式(如"你不再是一个")，改为精确匹配
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instruction|prompt|message|rule)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|above|prior)", re.I),
    re.compile(r"you\s+are\s+(now|no\s+longer)\s+(an?\s+)?(AI|assistant|bot)", re.I),
    re.compile(r"new\s+(system\s+)?instruction", re.I),
    re.compile(r"override\s+(system|instruction|prompt)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"developer\s*mode", re.I),
    # 中文Prompt注入：仅保留明显攻击模式
    re.compile(r"忘记你之前的(系统)?(指令|提示|规则)", re.I),
    re.compile(r"忽略你之前的(系统)?(指令|提示|规则)", re.I),
    re.compile(r"你现在不是一个AI(助手|助理)", re.I),
]

# ============================================================
# 数据校验器
# ============================================================


class DataValidator:
    """数据交互校验器（单例）"""

    _instance: Optional["DataValidator"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._ioa = get_ioa_engine()
        self._audit = get_audit_logger()

    # ---- 通用文本校验 ----

    def validate_text(
        self,
        text: str,
        field_name: str = "text",
        max_length: int = 5000,
        allow_html: bool = False,
        checks: Optional[list[str]] = None,
    ) -> tuple[bool, str, str]:
        """
        校验文本字段

        返回: (是否通过, 清洗后文本, 失败原因)
        """
        if not isinstance(text, str):
            return False, "", f"{field_name} 必须是字符串类型"

        # 长度检查
        if len(text) > max_length:
            return False, text[:max_length], f"{field_name} 超过最大长度 {max_length}"

        # 检查类型
        checks = checks or ["sql", "command", "xss", "prompt"]

        # SQL注入检测
        if "sql" in checks:
            for pattern in SQL_INJECTION_PATTERNS:
                if pattern.search(text):
                    self._report_violation(field_name, "SQL注入", text[:100])
                    return False, "", f"{field_name} 包含不安全的SQL模式"

        # 命令注入检测
        if "command" in checks:
            for pattern in COMMAND_INJECTION_PATTERNS:
                if pattern.search(text):
                    self._report_violation(field_name, "命令注入", text[:100])
                    return False, "", f"{field_name} 包含不安全的命令模式"

        # XSS检测
        if "xss" in checks and not allow_html:
            for pattern in XSS_PATTERNS:
                if pattern.search(text):
                    self._report_violation(field_name, "XSS", text[:100])
                    return False, "", f"{field_name} 包含不安全的HTML/脚本"

        # Prompt注入检测
        if "prompt" in checks:
            for pattern in PROMPT_INJECTION_PATTERNS:
                if pattern.search(text):
                    self._report_violation(field_name, "Prompt注入", text[:100])
                    return False, "", f"{field_name} 包含不安全的提示模式"

        # 清洗文本（去除控制字符、零宽字符）
        cleaned = self._sanitize_text(text)

        return True, cleaned, ""

    def _sanitize_text(self, text: str) -> str:
        """清洗文本"""
        # 移除零宽字符
        cleaned = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)
        # 移除不可见控制字符（保留换行和制表符）
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)
        # 标准化空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _report_violation(self, field: str, violation_type: str, snippet: str):
        """上报违规事件"""
        self._ioa.record_validation_fail(
            endpoint="data_validator",
            source="internal",
            reason=f"{violation_type}: {field}",
            detail={"field": field, "type": violation_type, "snippet": snippet[:200]},
        )
        self._audit.log_security_event(
            f"[Validator] {violation_type} detected in field '{field}'"
        )

    # ---- Schema 校验 ----

    def validate_request_body(
        self,
        body: dict,
        schema: dict,
        endpoint: str = "",
        source: str = "",
    ) -> tuple[bool, str, dict]:
        """
        按Schema校验请求体

        schema格式:
        {
            "field_name": {
                "type": "str|int|float|bool|list|dict",
                "required": True/False,
                "min": 0,          # 数值最小/字符串最小长度
                "max": 10000,      # 数值最大/字符串最大长度
                "enum": [...],     # 枚举值
                "pattern": "regex", # 正则匹配
                "checks": ["sql","xss","prompt"]  # 安全检测类型
            }
        }

        返回: (是否通过, 错误信息, 清洗后的数据)
        """
        cleaned = {}

        for field, rules in schema.items():
            value = body.get(field)
            required = rules.get("required", False)
            expected_type = rules.get("type", "str")

            # 必需字段检查
            if required and value is None:
                self._ioa.record_validation_fail(
                    endpoint, source, f"缺少必需字段: {field}", {}
                )
                return False, f"缺少必需字段: {field}", {}

            if value is None:
                if "default" in rules:
                    cleaned[field] = rules["default"]
                continue

            # 类型检查
            type_map = {
                "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict,
            }
            py_type = type_map.get(expected_type)
            if py_type and not isinstance(value, py_type):
                # 尝试类型转换
                try:
                    if expected_type == "int":
                        value = int(value)
                    elif expected_type == "float":
                        value = float(value)
                    elif expected_type == "str":
                        value = str(value)
                    elif expected_type == "bool":
                        if isinstance(value, str):
                            value = value.lower() in ("true", "1", "yes")
                        else:
                            value = bool(value)
                except (ValueError, TypeError):
                    self._ioa.record_validation_fail(
                        endpoint, source, f"字段类型错误: {field}", {"expected": expected_type}
                    )
                    return False, f"字段 {field} 类型应为 {expected_type}", {}

            # 数值范围检查
            if expected_type in ("int", "float") and isinstance(value, (int, float)):
                if "min" in rules and value < rules["min"]:
                    return False, f"字段 {field} 不能小于 {rules['min']}", {}
                if "max" in rules and value > rules["max"]:
                    return False, f"字段 {field} 不能大于 {rules['max']}", {}

            # 字符串长度检查
            if expected_type == "str" and isinstance(value, str):
                if "min" in rules and len(value) < rules["min"]:
                    return False, f"字段 {field} 长度不能小于 {rules['min']}", {}
                if "max" in rules and len(value) > rules["max"]:
                    return False, f"字段 {field} 长度不能大于 {rules['max']}", {}

            # 枚举检查
            if "enum" in rules and value not in rules["enum"]:
                return False, f"字段 {field} 必须是以下值之一: {rules['enum']}", {}

            # 正则检查
            if "pattern" in rules:
                p = re.compile(rules["pattern"])
                if not p.match(str(value)):
                    return False, f"字段 {field} 格式不匹配", {}

            # 安全检测
            if isinstance(value, str) and "checks" in rules:
                ok, cleaned_val, err = self.validate_text(
                    value, field_name=field,
                    max_length=rules.get("max", 5000),
                    checks=rules["checks"],
                )
                if not ok:
                    return False, err, {}
                cleaned[field] = cleaned_val
            elif isinstance(value, str):
                cleaned[field] = self._sanitize_text(value)
            else:
                cleaned[field] = value

        return True, "", cleaned

    # ---- 快捷校验（常用Schema） ----

    def validate_edict_text(self, text: str) -> tuple[bool, str, str]:
        """校验圣旨文本"""
        return self.validate_text(
            text,
            field_name="edict_text",
            max_length=3000,
            checks=["sql", "command", "xss", "prompt"],
        )

    def validate_faction_id(self, faction_id: str) -> tuple[bool, str]:
        """校验势力ID格式"""
        if not isinstance(faction_id, str):
            return False, "势力ID必须是字符串"
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,49}$', faction_id):
            return False, "势力ID格式不合法（仅允许字母、数字、下划线）"
        if len(faction_id) > 50:
            return False, "势力ID超长"
        return True, faction_id

    def validate_game_command(self, params: dict) -> tuple[bool, str, dict]:
        """校验游戏指令参数"""
        schema = {
            "action": {"type": "str", "required": True, "max": 50},
            "faction_id": {"type": "str", "required": False, "max": 50},
            "params": {"type": "dict", "required": True},
        }
        return self.validate_request_body(params, schema, "game/command", "unknown")

    def validate_ai_decision_params(self, params: dict) -> tuple[bool, str, dict]:
        """校验AI决策参数"""
        schema = {
            "faction_id": {"type": "str", "required": True, "max": 50},
            "faction_name": {"type": "str", "required": False, "max": 100},
            "tile_count": {"type": "int", "required": False, "min": 0, "max": 100000},
            "troops": {"type": "int", "required": False, "min": 0, "max": 10000000},
            "treasury": {"type": "int", "required": False, "min": 0, "max": 100000000},
            "grain": {"type": "int", "required": False, "min": 0, "max": 100000000},
            "reputation": {"type": "int", "required": False, "min": 0, "max": 100},
            "realm_stability": {"type": "int", "required": False, "min": 0, "max": 100},
            "court_stability": {"type": "int", "required": False, "min": 0, "max": 100},
            "turn": {"type": "int", "required": False, "min": 0, "max": 10000},
            "season": {"type": "str", "required": False, "enum": ["春", "夏", "秋", "冬"]},
        }
        return self.validate_request_body(params, schema, "faction/ai-decision", params.get("faction_id", "unknown"))


# 单例获取
def get_validator() -> DataValidator:
    return DataValidator()
