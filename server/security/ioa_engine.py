"""
IOA (Intelligent Operations Analysis) 智能运营分析引擎

游戏安全态势感知 · 多维度风险评分 · 实时威胁监控 · 运营决策支持

功能:
- 实时采集游戏运行指标（AI调用次数、异常行为数、数据变更量）
- 多维度风险评分（行为风险、数据风险、AI风险、网络风险）
- 趋势分析（滑动窗口异常率、高频操作检测）
- 安全仪表盘数据生成
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .audit_logger import get_audit_logger

# ============================================================
# 数据模型
# ============================================================


@dataclass
class SecurityEvent:
    """安全事件"""
    timestamp: float
    event_type: str  # validation_fail / anomaly / agent_suspicious / rate_limit / injection_attempt
    severity: str     # low / medium / high / critical
    source: str       # IP / faction_id / endpoint
    detail: dict
    risk_score: float = 0.0


@dataclass
class RiskProfile:
    """风险画像"""
    overall_score: float = 0.0         # 0-100 综合风险分
    behavior_risk: float = 0.0         # 行为风险
    data_risk: float = 0.0             # 数据风险
    ai_risk: float = 0.0               # AI调用风险
    network_risk: float = 0.0          # 网络层风险
    active_threats: int = 0            # 活跃威胁数
    events_24h: int = 0                # 24小时内事件数
    trend: str = "stable"              # stable / rising / falling


@dataclass
class IOADashboard:
    """安全仪表盘"""
    timestamp: float = 0.0
    risk_profile: RiskProfile = field(default_factory=RiskProfile)
    top_threats: list[dict] = field(default_factory=list)
    anomaly_count_1h: int = 0
    validation_fail_count_1h: int = 0
    agent_suspicious_count_1h: int = 0
    rate_limit_hits_1h: int = 0
    active_sessions: int = 0
    ai_call_stats: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


# ============================================================
# IOA 引擎
# ============================================================


class IOAEngine:
    """IOA 智能运营分析引擎（单例）"""

    _instance: Optional["IOAEngine"] = None
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

        self._events: deque[SecurityEvent] = deque(maxlen=10000)
        self._ip_activity: dict[str, list[float]] = defaultdict(list)
        self._faction_activity: dict[str, list[float]] = defaultdict(list)
        self._endpoint_hits: dict[str, list[float]] = defaultdict(list)
        self._ai_call_times: list[dict] = []
        self._validation_fails: deque[dict] = deque(maxlen=5000)

        # 威胁情报
        self._blocked_ips: set[str] = set()
        self._suspicious_factions: set[str] = set()
        self._active_sessions: dict[str, float] = {}  # session_id -> last_active
        # Bug #29修复: IP封禁过期机制
        self._blocked_ips_expiry: dict[str, float] = {}  # IP -> 过期时间戳

        # 窗口统计
        self._window_events: deque[SecurityEvent] = deque(maxlen=5000)

        # 线程安全锁（所有数据写入和读取均持锁）
        self._data_lock = threading.Lock()

        self._audit = get_audit_logger()
        self._last_dashboard: Optional[IOADashboard] = None

    # ---- 事件采集 ----

    def record_event(
        self,
        event_type: str,
        severity: str,
        source: str,
        detail: dict,
        risk_score: float = 0.0,
    ):
        """记录安全事件（线程安全）"""
        evt = SecurityEvent(
            timestamp=time.time(),
            event_type=event_type,
            severity=severity,
            source=source,
            detail=detail,
            risk_score=risk_score,
        )
        with self._data_lock:
            self._events.append(evt)
            self._window_events.append(evt)

            # 更新来源维度的活跃记录
            now = time.time()
            self._ip_activity[source].append(now)
            if detail.get("faction_id"):
                self._faction_activity[detail["faction_id"]].append(now)
            if detail.get("endpoint"):
                self._endpoint_hits[detail["endpoint"]].append(now)

        if severity in ("high", "critical"):
            self._audit.log_alert(
                f"[IOA] {event_type} | severity={severity} | source={source} | {detail}"
            )

    def record_validation_fail(self, endpoint: str, source: str, reason: str, detail: dict):
        """记录数据校验失败（线程安全）"""
        with self._data_lock:
            self._validation_fails.append({
                "timestamp": time.time(),
                "endpoint": endpoint,
                "source": source,
                "reason": reason,
                "detail": detail,
            })
        self.record_event("validation_fail", "medium", source, {
            "endpoint": endpoint,
            "reason": reason,
            **detail,
        }, risk_score=30.0)

    def record_ai_call(self, model: str, latency_ms: float, success: bool) -> None:
        """记录AI调用（线程安全）"""
        with self._data_lock:
            self._ai_call_times.append({
                "timestamp": time.time(),
                "model": model,
                "latency_ms": latency_ms,
                "success": success,
            })

    def record_session(self, session_id: str) -> None:
        """记录活跃会话（线程安全）"""
        with self._data_lock:
            self._active_sessions[session_id] = time.time()
            # 清理过期会话 (> 30 min)
            cutoff = time.time() - 1800
            expired = [sid for sid, ts in self._active_sessions.items() if ts < cutoff]
            for sid in expired:
                del self._active_sessions[sid]

    # ---- 风险分析 ----

    def compute_risk_profile(self) -> RiskProfile:
        """计算当前风险画像（线程安全）"""
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400

        with self._data_lock:
            recent = [e for e in self._window_events if e.timestamp > hour_ago]
            day_events = [e for e in self._events if e.timestamp > day_ago]
            validation_snapshot = list(self._validation_fails)
            ip_snapshot = dict(self._ip_activity)

        # 行为风险：高频操作 + 异常行为密度
        behavior_risk = self._calc_behavior_risk(recent)
        # 数据风险：校验失败率
        data_risk = self._calc_data_risk(hour_ago, validation_snapshot)
        # AI风险：调用异常率
        ai_risk = self._calc_ai_risk(recent)
        # 网络风险：IP高频访问
        network_risk = self._calc_network_risk(hour_ago, ip_snapshot)

        # 综合风险分（加权）
        overall = (
            behavior_risk * 0.30
            + data_risk * 0.25
            + ai_risk * 0.25
            + network_risk * 0.20
        )

        # 趋势判定
        older = [e for e in self._events if day_ago < e.timestamp <= hour_ago]
        recent_count = len(recent)
        older_count = len(older)
        if older_count == 0:
            trend = "stable" if recent_count == 0 else "rising"
        elif recent_count > older_count * 1.5:
            trend = "rising"
        elif recent_count < older_count * 0.5:
            trend = "falling"
        else:
            trend = "stable"

        return RiskProfile(
            overall_score=round(overall, 1),
            behavior_risk=round(behavior_risk, 1),
            data_risk=round(data_risk, 1),
            ai_risk=round(ai_risk, 1),
            network_risk=round(network_risk, 1),
            active_threats=len([e for e in recent if e.severity in ("high", "critical")]),
            events_24h=len(day_events),
            trend=trend,
        )

    def _calc_behavior_risk(self, recent: list[SecurityEvent]) -> float:
        anomaly_count = sum(1 for e in recent if e.event_type == "anomaly")
        suspicious_count = sum(1 for e in recent if e.event_type == "agent_suspicious")
        total = len(recent) or 1
        ratio = (anomaly_count + suspicious_count) / total
        return min(100, ratio * 200 + anomaly_count * 5)

    def _calc_data_risk(self, hour_ago: float, validation_snapshot: list[dict]) -> float:
        recent_fails = [f for f in validation_snapshot if f["timestamp"] > hour_ago]
        return min(100, len(recent_fails) * 3)

    def _calc_ai_risk(self, recent: list[SecurityEvent]) -> float:
        rate_hits = sum(1 for e in recent if e.event_type == "rate_limit")
        return min(100, rate_hits * 10)

    def _calc_network_risk(self, hour_ago: float, ip_snapshot: dict[str, list[float]]) -> float:
        high_freq_ips = 0
        for ip, times in ip_snapshot.items():
            recent_hits = sum(1 for t in times if t > hour_ago)
            if recent_hits > 100:
                high_freq_ips += 1
            elif recent_hits > 50:
                high_freq_ips += 0.5
        return min(100, high_freq_ips * 15)

    # ---- 仪表盘 ----

    def get_dashboard(self) -> IOADashboard:
        """生成安全仪表盘（线程安全）"""
        now = time.time()
        hour_ago = now - 3600

        with self._data_lock:
            recent = [e for e in self._window_events if e.timestamp > hour_ago]
            validation_snapshot = list(self._validation_fails)
            ai_snapshot = list(self._ai_call_times)
            active_sessions = len(self._active_sessions)

        risk = self.compute_risk_profile()

        # 高频威胁
        threat_counter: dict[str, int] = defaultdict(int)
        for e in recent:
            if e.severity in ("high", "critical"):
                threat_counter[e.event_type] += 1
        top_threats = sorted(
            [{"type": k, "count": v} for k, v in threat_counter.items()],
            key=lambda x: x["count"], reverse=True,
        )[:5]

        # AI调用统计
        ai_recent = sum(1 for d in ai_snapshot if d.get("timestamp", 0) > hour_ago)
        ai_total = len(ai_snapshot)

        # 建议
        recommendations = self._generate_recommendations(risk, recent)

        dashboard = IOADashboard(
            timestamp=now,
            risk_profile=risk,
            top_threats=top_threats,
            anomaly_count_1h=sum(1 for e in recent if e.event_type == "anomaly"),
            validation_fail_count_1h=sum(
                1 for f in validation_snapshot if f["timestamp"] > hour_ago
            ),
            agent_suspicious_count_1h=sum(
                1 for e in recent if e.event_type == "agent_suspicious"
            ),
            rate_limit_hits_1h=sum(
                1 for e in recent if e.event_type == "rate_limit"
            ),
            active_sessions=active_sessions,
            ai_call_stats={
                "last_hour": ai_recent,
                "total": ai_total,
            },
            recommendations=recommendations,
        )

        self._last_dashboard = dashboard
        return dashboard

    def _generate_recommendations(
        self, risk: RiskProfile, recent: list[SecurityEvent]
    ) -> list[str]:
        recs = []
        if risk.overall_score > 70:
            recs.append("⚠ 综合风险较高，建议检查近期异常事件详情")
        if risk.behavior_risk > 60:
            recs.append("行为风险偏高，建议审查Agent行为日志")
        if risk.data_risk > 50:
            recs.append("数据校验失败率较高，可能存在注入攻击尝试")
        if risk.ai_risk > 40:
            recs.append("AI调用触发限流，建议调整max_concurrent或检查模型可用性")
        if risk.network_risk > 50:
            recs.append("检测到高频网络请求，建议启用EdgeOne速率限制")
        if risk.trend == "rising":
            recs.append("安全态势呈上升趋势，建议持续监控")
        if not recs:
            recs.append("✓ 当前安全态势正常，各项指标在可控范围内")
        return recs

    # ---- 威胁封禁 ----
    # Bug #29修复: _blocked_ips_expiry 已在 __init__ 中初始化



    def block_ip(self, ip: str, reason: str, duration: float = 86400.0) -> None:
        """Bug #29修复: 添加封禁过期时间，默认24小时（线程安全）"""
        import time as _time
        with self._data_lock:
            self._blocked_ips.add(ip)
            self._blocked_ips_expiry[ip] = _time.time() + duration
        self._audit.log_alert(f"[IOA] IP封禁: {ip} | 原因: {reason} | 持续: {duration:.0f}秒")

    def is_ip_blocked(self, ip: str) -> bool:
        """Bug #29修复: 检查过期（线程安全）"""
        import time as _time
        with self._data_lock:
            if ip not in self._blocked_ips:
                return False
            if _time.time() >= self._blocked_ips_expiry.get(ip, float('inf')):
                self._blocked_ips.discard(ip)
                self._blocked_ips_expiry.pop(ip, None)
                return False
            return True

    def mark_faction_suspicious(self, faction_id: str) -> None:
        with self._data_lock:
            self._suspicious_factions.add(faction_id)

    def is_faction_suspicious(self, faction_id: str) -> bool:
        with self._data_lock:
            return faction_id in self._suspicious_factions

    # ---- 数据导出 ----

    def export_events(self, limit: int = 100) -> list[dict]:
        """导出最近安全事件（线程安全）"""
        with self._data_lock:
            events = list(self._events)[-limit:]
        return [
            {
                "timestamp": datetime.fromtimestamp(e.timestamp).isoformat(),
                "event_type": e.event_type,
                "severity": e.severity,
                "source": e.source,
                "detail": e.detail,
                "risk_score": e.risk_score,
            }
            for e in events
        ]

    def export_stats(self) -> dict:
        """导出统计摘要（线程安全）"""
        with self._data_lock:
            return {
                "total_events": len(self._events),
                "blocked_ips": list(self._blocked_ips),
                "suspicious_factions": list(self._suspicious_factions),
                "active_sessions": len(self._active_sessions),
                "total_ai_calls": len(self._ai_call_times),
                "validation_fails_total": len(self._validation_fails),
                "risk_profile": self.compute_risk_profile().__dict__,
            }


# 单例获取
def get_ioa_engine() -> IOAEngine:
    return IOAEngine()
