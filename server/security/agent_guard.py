"""
Agent 行为安全守卫 —— AI 智能 NPC / 游戏 Bot 行为风控

功能:
- NPC AI 决策合法性校验（行为边界、资源约束）
- Bot 行为模式识别（机械重复、异常频率）
- 决策行为评分（合理性、一致性、历史锚定）
- 行动序列异常检测
"""

from __future__ import annotations

import hashlib
import re
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
class AgentBehaviorRecord:
    """Agent（NPC/玩家）行为记录"""
    timestamp: float
    faction_id: str
    action_type: str       # recruit / march / attack / build / edict / ai_decision
    params: dict
    result: Optional[dict] = None
    decision_hash: str = ""


@dataclass
class AgentRiskReport:
    """Agent 风险报告"""
    faction_id: str
    overall_risk: float           # 0-100
    pattern_score: float          # 模式异常分
    frequency_score: float        # 频率异常分
    boundary_score: float         # 边界违规分
    consistency_score: float      # 一致性分
    flags: list[str] = field(default_factory=list)
    recommendation: str = ""


# ============================================================
# Agent 行为守卫
# ============================================================


class AgentGuard:
    """Agent 行为安全守卫（单例）"""

    _instance: Optional["AgentGuard"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 行为历史
        self._history: dict[str, deque[AgentBehaviorRecord]] = defaultdict(
            lambda: deque(maxlen=500)
        )
        # 决策指纹（去重/防重放）
        self._decision_fingerprints: deque[str] = deque(maxlen=10000)
        # 行动频率计数器
        self._action_counter: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # 已知合法行动类型（与 api_server.py valid_actions 保持同步）
        self._valid_actions = {
            "recruit", "march", "attack", "build", "farm", "trade",
            "diplomacy", "edict", "ai_decision", "policy_unlock",
            "appoint", "dismiss", "execute", "prisoner_action",
            "court_settlement", "supply", "reinforce", "retreat",
            # api_server.py 使用的指令类型
            "spy", "law", "develop", "fortify", "relief", "tax",
            "enfeoff", "purge", "amnesty", "scout",
            "buy_horses", "train_troops",
            # AI Agent 工具调用映射
            "collect_tax",
            # 2026-07-15 修复: 补充缺失的合法行动类型
            "train", "patrol", "mobilize", "raid", "ambush",
            "transport", "garrison", "transfer", "governor",
            "marriage", "tribute", "pledge", "vassal",
            "counter_spy", "sabotage", "bribe", "assassinate",
            "survey", "move_capital", "decree", "conscript",
        }

        self._ioa = get_ioa_engine()
        self._audit = get_audit_logger()

    # ---- 行为记录 ----

    def record_action(
        self,
        faction_id: str,
        action_type: str,
        params: dict,
        result: Optional[dict] = None,
    ) -> str:
        """记录一次Agent行为，返回记录指纹"""
        fingerprint = self._make_fingerprint(faction_id, action_type, params)

        record = AgentBehaviorRecord(
            timestamp=time.time(),
            faction_id=faction_id,
            action_type=action_type,
            params=params,
            result=result,
            decision_hash=fingerprint,
        )

        self._history[faction_id].append(record)
        self._decision_fingerprints.append(fingerprint)
        self._action_counter[faction_id][action_type].append(time.time())

        # 清理过期频率数据（保留1小时）
        self._clean_expired_counters(faction_id)

        return fingerprint

    def _make_fingerprint(self, faction_id: str, action_type: str, params: dict) -> str:
        """生成行为指纹"""
        raw = f"{faction_id}|{action_type}|{sorted(params.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _clean_expired_counters(self, faction_id: str) -> None:
        cutoff = time.time() - 3600
        for action_type in self._action_counter[faction_id]:
            self._action_counter[faction_id][action_type] = [
                t for t in self._action_counter[faction_id][action_type] if t > cutoff
            ]

    # ---- 行为校验 ----

    def validate_npc_decision(
        self, faction_id: str, faction_name: str, decision: dict
    ) -> tuple[bool, str, float]:
        """
        校验NPC AI决策合法性

        返回: (是否通过, 原因, 风险分)
        """
        flags = []
        risk_score = 0.0

        # 1. 检测空决策
        if not decision or not isinstance(decision, dict):
            return False, "空决策或格式错误", 100.0

        # 2. 检测异常关键词（提示注入/越狱）
        decision_text = str(decision).lower()
        suspicious_keywords = [
            "ignore previous", "ignore all", "disregard", "system prompt",
            "you are now", "new instruction", "bypass", "override",
            "jailbreak", "dan ", "developer mode", "sudo ",
            "忽略之前的", "无视规则", "系统指令", "你不再是",
        ]
        for kw in suspicious_keywords:
            if kw in decision_text:
                flags.append(f"疑似提示注入: {kw}")
                risk_score += 60.0  # 提示注入直接高风险

        # 3. 检测资源异常（数值爆炸/负数）
        resource_fields = ["troops", "treasury", "grain", "reputation", "stability"]
        for field in resource_fields:
            val = decision.get(field)
            if val is not None:
                try:
                    num = float(val)
                    if num < 0:
                        flags.append(f"资源字段异常(负数): {field}={num}")
                        risk_score += 70.0  # 负数直接判定违规
                    elif num > 1_000_000:
                        flags.append(f"资源字段异常(过大): {field}={num}")
                        risk_score += 70.0  # 数值爆炸直接判定违规
                except (ValueError, TypeError):
                    flags.append(f"资源字段非数值: {field}={val}")
                    risk_score += 45.0

        # 4. 检测重复决策（防重放）
        fp = self._make_fingerprint(faction_id, "ai_decision", decision)
        recent_count = sum(1 for f in self._decision_fingerprints if f == fp)
        if recent_count > 2:
            flags.append("重复决策（疑似重放攻击）")
            risk_score += 50.0

        # 5. 检测异常频率
        freq_score = self._check_action_frequency(faction_id, "ai_decision")
        if freq_score > 50:
            flags.append(f"AI决策频率异常 (分={freq_score:.0f})")
            risk_score += freq_score

        # 风险分上限截断（0-100），防止多个高分项叠加超过100
        risk_score = min(risk_score, 100.0)

        is_valid = risk_score < 60.0
        reason = "; ".join(flags) if flags else "行为正常"

        if risk_score >= 30:
            self._ioa.record_event(
                "agent_suspicious",
                "high" if risk_score >= 60 else "medium",
                faction_id,
                {"faction_name": faction_name, "flags": flags, "risk_score": risk_score},
                risk_score=risk_score,
            )

        if not is_valid:
            self._ioa.mark_faction_suspicious(faction_id)
            self._audit.log_alert(
                f"[AgentGuard] NPC决策拦截: faction={faction_id}({faction_name}) "
                f"risk={risk_score:.0f} reason={reason}"
            )

        return is_valid, reason, risk_score

    def validate_player_action(
        self, faction_id: str, action_type: str, params: dict
    ) -> tuple[bool, str, float]:
        """
        校验玩家行为合法性

        返回: (是否通过, 原因, 风险分)
        """
        flags = []
        risk_score = 0.0

        # 1. 行动类型合法性
        if action_type not in self._valid_actions:
            return False, f"非法行动类型: {action_type}", 100.0

        # 2. 参数注入检测
        for key, val in params.items():
            val_str = str(val)
            # XSS检测
            if re.search(r'<script|javascript:|onerror=|onload=|alert\(', val_str, re.I):
                flags.append(f"参数含XSS: {key}")
                risk_score += 80.0
            # SQL注入检测
            if re.search(r"(\bunion\b.*\bselect\b|\bdrop\b|\bdelete\b.*\bfrom\b|--|;--)", val_str, re.I):
                flags.append(f"参数含SQL注入模式: {key}")
                risk_score += 80.0
            # 命令注入检测
            if re.search(r'[;&|`$]|\.\.\/|%00', val_str):
                flags.append(f"参数含命令注入模式: {key}")
                risk_score += 70.0

        # 3. 参数长度限制
        for key, val in params.items():
            val_str = str(val)
            if len(val_str) > 10000:
                flags.append(f"参数过长: {key} ({len(val_str)} chars)")
                risk_score += 15.0

        # 4. 频率检测
        freq_score = self._check_action_frequency(faction_id, action_type)
        if freq_score > 50:
            flags.append(f"操作频率异常 (分={freq_score:.0f})")
            risk_score += freq_score

        # 5. 重复操作检测
        fp = self._make_fingerprint(faction_id, action_type, params)
        match_count = sum(1 for f in self._decision_fingerprints if f == fp)
        if match_count > 5:
            flags.append("重复操作过多")
            risk_score += 30.0

        is_valid = risk_score < 70.0
        reason = "; ".join(flags) if flags else "行为正常"

        if risk_score >= 30:
            self._ioa.record_event(
                "agent_suspicious",
                "high" if risk_score >= 70 else "medium",
                faction_id,
                {"action_type": action_type, "flags": flags, "risk_score": risk_score},
                risk_score=risk_score,
            )

        return is_valid, reason, risk_score

    def _check_action_frequency(self, faction_id: str, action_type: str) -> float:
        """检测行动频率异常（返回0-100风险分）"""
        times = self._action_counter.get(faction_id, {}).get(action_type, [])
        now = time.time()
        recent = [t for t in times if now - t < 60]  # 1分钟内

        n = len(recent)
        if n > 30:
            return 90.0   # 每秒超0.5次
        elif n > 15:
            return 60.0   # 每4秒一次
        elif n > 8:
            return 30.0   # 每7.5秒一次
        return 0.0

    # ---- 行为模式分析 ----

    def analyze_faction_behavior(self, faction_id: str) -> AgentRiskReport:
        """分析势力行为模式，返回风险报告"""
        records = list(self._history.get(faction_id, []))
        if not records:
            return AgentRiskReport(
                faction_id=faction_id,
                overall_risk=0,
                pattern_score=0,
                frequency_score=0,
                boundary_score=0,
                consistency_score=0,
                recommendation="暂无行为数据",
            )

        now = time.time()
        recent = [r for r in records if now - r.timestamp < 3600]

        # 模式异常分：检测高度重复的行为模式
        pattern_score = self._calc_pattern_anomaly(recent)

        # 频率异常分
        freq_score = 0.0
        for action_type in self._valid_actions:
            freq_score = max(freq_score, self._check_action_frequency(faction_id, action_type))

        # 边界违规分：参数范围检测
        boundary_score = self._calc_boundary_violations(recent)

        # 一致性分：连续决策是否一致
        consistency_score = self._calc_consistency(recent)

        overall = (
            pattern_score * 0.30
            + freq_score * 0.30
            + boundary_score * 0.25
            + consistency_score * 0.15
        )

        flags = []
        if pattern_score > 50:
            flags.append("行为模式高度重复")
        if freq_score > 50:
            flags.append("操作频率异常")
        if boundary_score > 50:
            flags.append("参数边界违规")
        if consistency_score > 50:
            flags.append("决策一致性异常")

        rec = (
            "建议人工审查该势力行为日志"
            if flags
            else "行为模式正常"
        )

        return AgentRiskReport(
            faction_id=faction_id,
            overall_risk=round(overall, 1),
            pattern_score=round(pattern_score, 1),
            frequency_score=round(freq_score, 1),
            boundary_score=round(boundary_score, 1),
            consistency_score=round(consistency_score, 1),
            flags=flags,
            recommendation=rec,
        )

    def _calc_pattern_anomaly(self, records: list[AgentBehaviorRecord]) -> float:
        """计算模式重复度"""
        if len(records) < 3:
            return 0
        hashes = [r.decision_hash for r in records]
        unique_ratio = len(set(hashes)) / len(hashes)
        # 唯一率越低，重复度越高
        return max(0, (1 - unique_ratio) * 100)

    def _calc_boundary_violations(self, records: list[AgentBehaviorRecord]) -> float:
        """边界违规检测"""
        violations = 0
        for r in records:
            for k, v in r.params.items():
                if isinstance(v, (int, float)):
                    if v < 0:
                        violations += 1
                    elif v > 100000:
                        violations += 1
                if isinstance(v, str) and len(str(v)) > 5000:
                    violations += 1
        return min(100, violations * 10)

    def _calc_consistency(self, records: list[AgentBehaviorRecord]) -> float:
        """决策一致性检测（过度一致的决策可能表示Bot）"""
        if len(records) < 5:
            return 0
        action_types = [r.action_type for r in records]
        # 如果90%以上操作是同一类型，可能有问题
        from collections import Counter
        counter = Counter(action_types)
        most_common_ratio = counter.most_common(1)[0][1] / len(action_types)
        return max(0, (most_common_ratio - 0.7) * 150)

    # ---- 数据导出 ----

    def get_faction_history(self, faction_id: str, limit: int = 50) -> list[dict]:
        records = list(self._history.get(faction_id, []))[-limit:]
        return [
            {
                "timestamp": r.timestamp,
                "action_type": r.action_type,
                "params": str(r.params)[:200],
                "decision_hash": r.decision_hash,
            }
            for r in records
        ]

    def get_stats(self) -> dict:
        return {
            "total_records": sum(len(v) for v in self._history.values()),
            "factions_tracked": len(self._history),
            "unique_fingerprints": len(self._decision_fingerprints),
        }


# 单例获取
def get_agent_guard() -> AgentGuard:
    return AgentGuard()
