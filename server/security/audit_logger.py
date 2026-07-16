"""
安全审计日志系统

功能:
- 结构化安全事件记录（JSON Lines）
- 操作审计跟踪（谁、什么操作、什么时间、什么结果）
- 日志轮转和保留策略
- 与IOA引擎联动
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.audit")

from .anonymizer import get_anonymizer


class AuditLogger:
    """安全审计日志（单例，线程安全）"""

    _instance: Optional["AuditLogger"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 日志目录
        base = Path(__file__).parent.parent.parent
        self._log_dir = base / "logs" / "security"
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # 日志文件（按日期轮转）
        self._date_str = datetime.now().strftime("%Y%m%d")
        self._audit_file = self._log_dir / f"audit_{self._date_str}.jsonl"
        self._alert_file = self._log_dir / f"alert_{self._date_str}.jsonl"

        # 写入锁
        self._write_lock = threading.Lock()

        self._anonymizer = get_anonymizer()
        self._total_events = 0
        self._total_alerts = 0

    # ---- 日志写入 ----

    def _rotate_if_needed(self):
        """按日期轮转日志文件"""
        today = datetime.now().strftime("%Y%m%d")
        if today != self._date_str:
            self._date_str = today
            self._audit_file = self._log_dir / f"audit_{self._date_str}.jsonl"
            self._alert_file = self._log_dir / f"alert_{self._date_str}.jsonl"

    def _write_line(self, target: Path, record: dict):
        """写入一行JSON"""
        self._rotate_if_needed()
        # 脱敏处理
        safe_record = self._anonymizer.safe_dict_log(record)
        try:
            with self._write_lock:
                with open(target, "a", encoding="utf-8") as f:
                    f.write(json.dumps(safe_record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"审计日志写入失败（非关键路径）: {e}")

    # ---- 审计事件 ----

    def log_operation(
        self,
        action: str,
        source: str,
        detail: dict,
        result: str = "success",
    ):
        """记录操作审计"""
        self._total_events += 1
        record = {
            "event": "operation",
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "source": source,
            "result": result,
            "detail": detail,
        }
        self._write_line(self._audit_file, record)

    def log_security_event(self, message: str, severity: str = "info"):
        """记录安全事件"""
        self._total_events += 1
        record = {
            "event": "security",
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "message": message,
        }
        self._write_line(self._audit_file, record)

    def log_alert(self, message: str):
        """记录告警（同时写入审计日志和告警日志）"""
        self._total_alerts += 1
        record = {
            "event": "alert",
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        self._write_line(self._audit_file, record)
        self._write_line(self._alert_file, record)

    def log_request(
        self,
        method: str,
        path: str,
        client_ip: str,
        status: int,
        latency_ms: float,
        faction_id: Optional[str] = None,
    ):
        """记录API请求审计"""
        self._total_events += 1
        record = {
            "event": "request",
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "client_ip": self._anonymizer.hash_ip(client_ip),
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "faction_id": faction_id,
        }
        self._write_line(self._audit_file, record)

    def log_ai_call(
        self,
        model: str,
        prompt_len: int,
        response_len: int,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """记录AI调用审计"""
        self._total_events += 1
        record = {
            "event": "ai_call",
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "prompt_len": prompt_len,
            "response_len": response_len,
            "latency_ms": round(latency_ms, 2),
            "success": success,
            "error": error,
        }
        self._write_line(self._audit_file, record)

    # ---- 统计 ----

    def get_stats(self) -> dict:
        return {
            "total_events": self._total_events,
            "total_alerts": self._total_alerts,
            "log_dir": str(self._log_dir),
            "current_date": self._date_str,
        }

    def get_recent_events(self, limit: int = 50) -> list[dict]:
        """读取最近的审计事件"""
        events = []
        try:
            if self._audit_file.exists():
                with open(self._audit_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"读取审计事件失败: {e}")
        return events

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        """读取最近的告警"""
        alerts = []
        try:
            if self._alert_file.exists():
                with open(self._alert_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            alerts.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"读取告警记录失败: {e}")
        return alerts


# 单例获取
def get_audit_logger() -> AuditLogger:
    return AuditLogger()
