"""
异常行为识别引擎 —— 统计离群检测 · 序列模式分析 · 规则告警

功能:
- Z-Score 统计离群检测（数值异常）
- 滑动窗口频率异常识别
- 行为序列模式分析（马尔可夫链异常检测）
- 基于规则的实时告警
- 异常评分聚合
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from .ioa_engine import get_ioa_engine
from .audit_logger import get_audit_logger


# ============================================================
# 数据模型
# ============================================================


@dataclass
class AnomalyAlert:
    """异常告警"""
    timestamp: float
    anomaly_type: str          # value_outlier / freq_spike / pattern_break / rule_violation
    severity: str              # low / medium / high / critical
    source: str                # faction_id / IP / endpoint
    metric: str                # 指标名
    value: float               # 异常值
    expected_range: tuple[float, float]  # 期望范围
    detail: str
    anomaly_score: float = 0.0


@dataclass
class AnomalyReport:
    """异常检测报告"""
    timestamp: float = 0.0
    total_alerts: int = 0
    alerts_by_severity: dict = field(default_factory=lambda: defaultdict(int))
    alerts_by_type: dict = field(default_factory=lambda: defaultdict(int))
    top_alerts: list[dict] = field(default_factory=list)
    overall_score: float = 0.0


# ============================================================
# 异常检测引擎
# ============================================================


class AnomalyDetector:
    """异常行为识别引擎（单例）"""

    _instance: Optional["AnomalyDetector"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 时间序列数据（按指标存储）
        self._metrics: dict[str, deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=1000)  # (timestamp, value)
        )
        # 行为序列（按来源存储）—— 带时间戳
        self._behavior_sequences: dict[str, deque[tuple[float, str]]] = defaultdict(
            lambda: deque(maxlen=200)  # (timestamp, action)
        )
        # 状态转移矩阵（用于马尔可夫链检测）
        self._transition_counts: dict[str, dict[tuple[str, str], int]] = defaultdict(
            lambda: defaultdict(int)
        )
        # 告警历史
        self._alerts: deque[AnomalyAlert] = deque(maxlen=5000)
        # 基线数据
        self._baselines: dict[str, tuple[float, float]] = {}  # metric -> (mean, std)

        self._ioa = get_ioa_engine()
        self._audit = get_audit_logger()

    # ---- 数据采集 ----

    def record_metric(self, metric: str, value: float):
        """记录指标值"""
        self._metrics[metric].append((time.time(), value))

        # 滑动窗口均值/标准差更新（保留最近200个点做基线）
        recent = [v for _, v in list(self._metrics[metric])[-200:]]
        if len(recent) >= 10:
            mean = sum(recent) / len(recent)
            variance = sum((x - mean) ** 2 for x in recent) / len(recent)
            std = math.sqrt(variance) if variance > 0 else 1.0
            self._baselines[metric] = (mean, std)

    def record_behavior(self, source: str, action: str):
        """记录行为序列（带时间戳）"""
        now = time.time()
        seq = self._behavior_sequences[source]
        if seq:
            prev = seq[-1][1]  # 上一个行为类型
            self._transition_counts[source][(prev, action)] += 1
        seq.append((now, action))

    # ---- 检测方法 ----

    def detect_value_outlier(
        self, metric: str, value: float, z_threshold: float = 3.0
    ) -> Optional[AnomalyAlert]:
        """
        Z-Score 离群检测

        当 |value - mean| / std > z_threshold 时触发告警
        """
        baseline = self._baselines.get(metric)
        if not baseline:
            # 无基线，先积累数据
            self.record_metric(metric, value)
            return None

        mean, std = baseline
        if std == 0:
            return None

        z_score = abs(value - mean) / std

        if z_score > z_threshold:
            severity = "critical" if z_score > 5 else "high" if z_score > 4 else "medium"
            alert = AnomalyAlert(
                timestamp=time.time(),
                anomaly_type="value_outlier",
                severity=severity,
                source=metric,
                metric=metric,
                value=value,
                expected_range=(mean - z_threshold * std, mean + z_threshold * std),
                detail=f"Z-Score={z_score:.2f} (mean={mean:.2f}, std={std:.2f})",
                anomaly_score=min(100, z_score * 20),
            )
            self._alerts.append(alert)
            self._report_to_ioa(alert)
            return alert

        # 正常值也要记录以更新基线
        self.record_metric(metric, value)
        return None

    def detect_frequency_spike(
        self, source: str, window_seconds: float = 60, threshold: int = 30
    ) -> Optional[AnomalyAlert]:
        """
        频率峰值检测

        在滑动窗口内操作次数超过阈值时触发
        """
        now = time.time()
        cutoff = now - window_seconds

        # 统计时间窗口内的行为次数
        recent_count = sum(
            1 for ts, _ in self._behavior_sequences.get(source, [])
            if ts > cutoff
        )

        if recent_count > threshold:
            severity = "high" if recent_count > threshold * 2 else "medium"
            alert = AnomalyAlert(
                timestamp=now,
                anomaly_type="freq_spike",
                severity=severity,
                source=source,
                metric="action_frequency",
                value=float(recent_count),
                expected_range=(0, float(threshold)),
                detail=f"{window_seconds:.0f}秒内 {recent_count} 次操作，超过阈值 {threshold}",
                anomaly_score=min(100, (recent_count / max(1, threshold)) * 50),
            )
            self._alerts.append(alert)
            self._report_to_ioa(alert)
            return alert

        return None

    def detect_pattern_break(
        self, source: str, current_action: str, confidence_threshold: float = 0.1
    ) -> Optional[AnomalyAlert]:
        """
        序列模式异常检测（马尔可夫链）

        检测当前行为是否偏离历史行为模式
        """
        seq = self._behavior_sequences[source]
        if len(seq) < 5:
            self.record_behavior(source, current_action)
            return None

        prev = seq[-1][1]  # 上一个行为类型（元组第二个元素）
        key = (prev, current_action)
        total_transitions = sum(self._transition_counts[source].values())
        count = self._transition_counts[source].get(key, 0)

        # 计算转移概率
        expected_prob = 1.0 / max(1, len(set(
            k[1] for k in self._transition_counts[source].keys()
        )))
        actual_prob = count / max(1, total_transitions)

        # 记录行为
        self.record_behavior(source, current_action)

        # 如果转移概率远低于均匀分布期望，标记异常（但不立即告警，需要累积）
        if total_transitions > 20 and actual_prob < expected_prob * 0.1:
            alert = AnomalyAlert(
                timestamp=time.time(),
                anomaly_type="pattern_break",
                severity="low",
                source=source,
                metric="behavior_pattern",
                value=actual_prob,
                expected_range=(expected_prob * 0.1, 1.0),
                detail=f"不常见的行为转换: {prev} -> {current_action} (概率={actual_prob:.4f})",
                anomaly_score=30.0,
            )
            self._alerts.append(alert)
            self._report_to_ioa(alert)
            return alert

        return None

    def detect_rule_violation(
        self, rule_name: str, source: str, detail: str, severity: str = "medium"
    ) -> AnomalyAlert:
        """基于规则的告警"""
        alert = AnomalyAlert(
            timestamp=time.time(),
            anomaly_type="rule_violation",
            severity=severity,
            source=source,
            metric=rule_name,
            value=1.0,
            expected_range=(0, 0),
            detail=detail,
            anomaly_score=50.0 if severity == "medium" else 75.0,
        )
        self._alerts.append(alert)
        self._report_to_ioa(alert)
        return alert

    def _report_to_ioa(self, alert: AnomalyAlert):
        """上报到IOA引擎"""
        self._ioa.record_event(
            "anomaly",
            alert.severity,
            alert.source,
            {
                "anomaly_type": alert.anomaly_type,
                "metric": alert.metric,
                "value": alert.value,
                "detail": alert.detail,
            },
            risk_score=alert.anomaly_score,
        )

    # ---- 综合检测 ----

    def comprehensive_check(
        self, source: str, action: str, metrics: Optional[dict[str, float]] = None
    ) -> list[AnomalyAlert]:
        """
        综合异常检测（对一次操作执行所有检测）

        source: 来源标识（faction_id / IP）
        action: 当前行为类型
        metrics: 当前各指标值 {metric_name: value}
        """
        alerts = []

        # 1. 频率峰值检测
        freq_alert = self.detect_frequency_spike(source)
        if freq_alert:
            alerts.append(freq_alert)

        # 2. 模式异常检测
        pattern_alert = self.detect_pattern_break(source, action)
        if pattern_alert:
            alerts.append(pattern_alert)

        # 3. 各指标离群检测
        if metrics:
            for metric, value in metrics.items():
                outlier = self.detect_value_outlier(metric, value)
                if outlier:
                    alerts.append(outlier)

        return alerts

    # ---- 报告 ----

    def get_report(self, limit: int = 20) -> AnomalyReport:
        """生成异常检测报告"""
        now = time.time()
        recent_alerts = [a for a in self._alerts if now - a.timestamp < 3600]

        report = AnomalyReport(
            timestamp=now,
            total_alerts=len(recent_alerts),
        )

        for a in recent_alerts:
            report.alerts_by_severity[a.severity] += 1
            report.alerts_by_type[a.anomaly_type] += 1

        # Top告警
        sorted_alerts = sorted(recent_alerts, key=lambda a: a.anomaly_score, reverse=True)
        report.top_alerts = [
            {
                "type": a.anomaly_type,
                "severity": a.severity,
                "source": a.source,
                "detail": a.detail,
                "score": a.anomaly_score,
            }
            for a in sorted_alerts[:limit]
        ]

        # 综合异常分
        if recent_alerts:
            report.overall_score = sum(a.anomaly_score for a in recent_alerts) / len(recent_alerts)

        return report

    def export_alerts(self, limit: int = 100) -> list[dict]:
        """导出告警列表"""
        alerts = list(self._alerts)[-limit:]
        return [
            {
                "timestamp": a.timestamp,
                "type": a.anomaly_type,
                "severity": a.severity,
                "source": a.source,
                "metric": a.metric,
                "value": a.value,
                "expected_range": list(a.expected_range),
                "detail": a.detail,
                "score": a.anomaly_score,
            }
            for a in alerts
        ]


# 单例获取
def get_anomaly_detector() -> AnomalyDetector:
    return AnomalyDetector()
