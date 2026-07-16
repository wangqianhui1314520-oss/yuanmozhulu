"""
元末逐鹿 3.0 - 安全 API 端点

提供安全仪表盘、审计日志、异常告警等监控接口
"""

from __future__ import annotations

import re
import time
from fastapi import APIRouter, Request

from server.core.response import ApiResponse

from .ioa_engine import get_ioa_engine
from .agent_guard import get_agent_guard
from .data_validator import get_validator
from .anomaly_detector import get_anomaly_detector
from .anonymizer import get_anonymizer
from .audit_logger import get_audit_logger
from .edgeone_rules import get_edgeone_policy

router = APIRouter(prefix="/api/security", tags=["security"])

# IP地址格式校验正则
_IP_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


# ============================================================
# 安全仪表盘
# ============================================================


@router.get("/dashboard")
async def security_dashboard():
    """IOA 安全态势仪表盘"""
    ioa = get_ioa_engine()
    detector = get_anomaly_detector()
    anonymizer = get_anonymizer()

    dashboard = ioa.get_dashboard()
    anomaly_report = detector.get_report()
    anonymizer_stats = anonymizer.get_stats()

    return ApiResponse.success({
        "ioa": {
            "timestamp": dashboard.timestamp,
            "risk_profile": dashboard.risk_profile.__dict__,
            "top_threats": dashboard.top_threats,
            "anomaly_count_1h": dashboard.anomaly_count_1h,
            "validation_fail_count_1h": dashboard.validation_fail_count_1h,
            "agent_suspicious_count_1h": dashboard.agent_suspicious_count_1h,
            "rate_limit_hits_1h": dashboard.rate_limit_hits_1h,
            "active_sessions": dashboard.active_sessions,
            "ai_call_stats": dashboard.ai_call_stats,
            "recommendations": dashboard.recommendations,
        },
        "anomaly": {
            "total_alerts_1h": anomaly_report.total_alerts,
            "alerts_by_severity": dict(anomaly_report.alerts_by_severity),
            "alerts_by_type": dict(anomaly_report.alerts_by_type),
            "top_alerts": anomaly_report.top_alerts[:10],
            "overall_score": anomaly_report.overall_score,
        },
        "anonymizer": anonymizer_stats,
    })


# ============================================================
# 安全事件列表
# ============================================================


@router.get("/events")
async def security_events(limit: int = 100, severity: str = "", event_type: str = ""):
    """获取安全事件列表（支持筛选）"""
    ioa = get_ioa_engine()
    events = ioa.export_events(limit=limit)

    if severity:
        events = [e for e in events if e["severity"] == severity]
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]

    return ApiResponse.success({
        "total": len(events),
        "events": events,
    })


# ============================================================
# 异常告警
# ============================================================


@router.get("/alerts")
async def anomaly_alerts(limit: int = 50):
    """获取异常告警列表"""
    detector = get_anomaly_detector()
    alerts = detector.export_alerts(limit=limit)
    return ApiResponse.success({
        "total": len(alerts),
        "alerts": alerts,
    })


# ============================================================
# Agent 行为分析
# ============================================================


@router.get("/agent/{faction_id}")
async def agent_behavior_report(faction_id: str):
    """获取指定势力的Agent行为风险报告"""
    guard = get_agent_guard()
    report = guard.analyze_faction_behavior(faction_id)
    history = guard.get_faction_history(faction_id, limit=30)

    return ApiResponse.success({
        "risk_report": report.__dict__,
        "recent_actions": history,
    })


@router.get("/agent/{faction_id}/history")
async def agent_behavior_history(faction_id: str, limit: int = 100):
    """获取指定势力的Agent行为历史"""
    guard = get_agent_guard()
    history = guard.get_faction_history(faction_id, limit=limit)
    return ApiResponse.success({
        "faction_id": faction_id,
        "total_records": len(history),
        "records": history,
    })


# ============================================================
# 审计日志
# ============================================================


@router.get("/audit/events")
async def audit_events(limit: int = 50):
    """获取审计事件"""
    audit = get_audit_logger()
    events = audit.get_recent_events(limit=limit)
    return ApiResponse.success({
        "total": len(events),
        "events": events,
    })


@router.get("/audit/alerts")
async def audit_alerts(limit: int = 50):
    """获取审计告警"""
    audit = get_audit_logger()
    alerts = audit.get_recent_alerts(limit=limit)
    return ApiResponse.success({
        "total": len(alerts),
        "alerts": alerts,
    })


# ============================================================
# 统计总览
# ============================================================


@router.get("/stats")
async def security_stats():
    """安全体系统计总览"""
    ioa = get_ioa_engine()
    guard = get_agent_guard()
    detector = get_anomaly_detector()
    anonymizer = get_anonymizer()
    audit = get_audit_logger()
    anomaly_report = detector.get_report()

    return ApiResponse.success({
        "ioa": ioa.export_stats(),
        "agent_guard": guard.get_stats(),
        "anonymizer": anonymizer.get_stats(),
        "audit": audit.get_stats(),
        "anomaly_report": {
            "total_alerts": anomaly_report.total_alerts,
        },
    })


# ============================================================
# 威胁管理
# ============================================================


@router.get("/threats/blocked")
async def blocked_entities():
    """获取封禁列表"""
    ioa = get_ioa_engine()
    return ApiResponse.success({
        "blocked_ips": list(ioa._blocked_ips),
        "suspicious_factions": list(ioa._suspicious_factions),
    })


# ============================================================
# EdgeOne 策略
# ============================================================


@router.get("/edgeone/policy")
async def edgeone_policy():
    """获取 EdgeOne 安全策略配置"""
    policy = get_edgeone_policy()
    return ApiResponse.success(policy.export_all())


@router.get("/edgeone/waf")
async def edgeone_waf_rules():
    """获取 WAF 规则"""
    policy = get_edgeone_policy()
    return ApiResponse.success(policy.get_waf_rules())


# ============================================================
# 自定义：单个IP/势力解封
# ============================================================


@router.post("/threats/unblock-ip")
async def unblock_ip(request: Request):
    """解封指定IP"""
    try:
        body = await request.json()
        ip = body.get("ip", "")
        if not ip or not isinstance(ip, str) or not _IP_PATTERN.match(ip):
            return ApiResponse.error(400, f"无效的IP地址: {ip}")
        ioa = get_ioa_engine()
        if ip in ioa._blocked_ips:
            ioa._blocked_ips.discard(ip)
            return ApiResponse.success({"unblocked": ip})
        return ApiResponse.error(404, f"IP {ip} 不在封禁列表中")
    except Exception as e:
        return ApiResponse.error(400, str(e))
