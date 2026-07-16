"""
LLM 成本追踪模块
==================
基于 llm-cost-optimizer skill 指导，提供：
- 按 Agent 分组追踪 Token 消耗与成本
- 成本预算预警
- 调用统计报告
"""
from __future__ import annotations
import json
import time
import logging
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yuanmo.llm.cost_tracker")

# ============================================================
# 成本常量（DeepSeek-V3 价格，单位：元/百万token）
# 价格可能随厂商调整，以实际账单为准
# ============================================================
COST_PER_M_INPUT = 2.0    # 输入 ¥2.00/百万token
COST_PER_M_OUTPUT = 8.0   # 输出 ¥8.00/百万token


@dataclass
class AgentCostRecord:
    """单个 Agent 组别的成本记录"""
    agent_group: str                     # advisor / law / enemy
    model: str                           # 模型名
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0
    total_latency: float = 0.0
    estimated_cost_yuan: float = 0.0     # 估算费用（元）
    
    def add_call(self, prompt_tokens: int, completion_tokens: int, latency: float):
        """记录一次调用"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.call_count += 1
        self.total_latency += latency
        
        # 估算费用
        input_cost = (prompt_tokens / 1_000_000) * COST_PER_M_INPUT
        output_cost = (completion_tokens / 1_000_000) * COST_PER_M_OUTPUT
        self.estimated_cost_yuan += input_cost + output_cost
    
    @property
    def avg_latency(self) -> float:
        return self.total_latency / max(self.call_count, 1)
    
    @property
    def avg_input_tokens(self) -> int:
        return self.prompt_tokens // max(self.call_count, 1)

    @property
    def avg_output_tokens(self) -> int:
        return self.completion_tokens // max(self.call_count, 1)
    
    def to_dict(self) -> dict:
        return {
            "agent_group": self.agent_group,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count,
            "avg_latency": round(self.avg_latency, 3),
            "avg_input_tokens": self.avg_input_tokens,
            "avg_output_tokens": self.avg_output_tokens,
            "estimated_cost_yuan": round(self.estimated_cost_yuan, 4),
        }


class LLMCostTracker:
    """
    LLM 成本追踪器
    
    按 Agent 分组（advisor/law/enemy）记录 Token 消耗和估算费用。
    支持预算预警：当某组费用超过预算阈值时发出警告。
    
    使用方式:
        tracker = LLMCostTracker()
        tracker.record("advisor", "deepseek-v3", 1500, 500, 2.3)
        tracker.record("law", "deepseek-v3", 3000, 800, 4.1)
        print(tracker.report())
    """
    
    def __init__(self, budget_yuan: float = 50.0, stats_dir: str = None):
        """
        Args:
            budget_yuan: 单次会话成本预算上限（元），超过 80% 时预警
            stats_dir: 统计数据持久化目录（默认 server/logs/）
        """
        self.records: dict[str, AgentCostRecord] = {}
        self.budget_yuan = budget_yuan
        self.budget_warn_threshold = budget_yuan * 0.8
        self._start_time = time.time()
        
        # 持久化路径
        if stats_dir:
            self._stats_dir = Path(stats_dir)
        else:
            self._stats_dir = Path(__file__).parent.parent.parent.parent / "logs"
        self._stats_dir.mkdir(parents=True, exist_ok=True)
        
        # 每日调用计数
        self._daily_calls: dict[str, int] = defaultdict(int)
        self._daily_cost: dict[str, float] = defaultdict(float)
    
    def record(self, agent_group: str, model: str, 
               prompt_tokens: int, completion_tokens: int, 
               latency: float, label: str = ""):
        """记录一次 LLM 调用"""
        if agent_group not in self.records:
            self.records[agent_group] = AgentCostRecord(
                agent_group=agent_group,
                model=model,
            )
        
        record = self.records[agent_group]
        record.add_call(prompt_tokens, completion_tokens, latency)
        
        # 每日统计
        date_key = time.strftime("%Y-%m-%d")
        self._daily_calls[date_key] += 1
        cost_this_call = ((prompt_tokens / 1_000_000) * COST_PER_M_INPUT + 
                         (completion_tokens / 1_000_000) * COST_PER_M_OUTPUT)
        self._daily_cost[date_key] += cost_this_call
        
        # 预算检查
        total_cost = self.total_cost
        if total_cost > self.budget_warn_threshold:
            remaining = self.budget_yuan - total_cost
            if remaining <= 0:
                logger.warning(
                    f"[预算] 成本已超预算！总计 ¥{total_cost:.4f} / 预算 ¥{self.budget_yuan:.2f}"
                )
            else:
                logger.info(
                    f"[预算] 成本预警：已用 ¥{total_cost:.4f}，剩余 ¥{remaining:.4f}"
                )
        
        # 详细日志
        if label:
            logger.debug(
                f"[COST] {agent_group}/{label} | "
                f"输入={prompt_tokens} 输出={completion_tokens} | "
                f"¥{cost_this_call:.6f} | {latency:.2f}s"
            )
    
    @property
    def total_cost(self) -> float:
        """当前会话总估算费用"""
        return sum(r.estimated_cost_yuan for r in self.records.values())
    
    @property
    def total_tokens(self) -> int:
        """当前会话总 Token 消耗"""
        return sum(r.total_tokens for r in self.records.values())
    
    @property
    def total_calls(self) -> int:
        """当前会话总调用次数"""
        return sum(r.call_count for r in self.records.values())
    
    @property
    def session_duration_seconds(self) -> float:
        """当前会话持续时长"""
        return time.time() - self._start_time
    
    def get_group(self, agent_group: str) -> Optional[AgentCostRecord]:
        """获取某组别的统计"""
        return self.records.get(agent_group)
    
    def report(self) -> str:
        """生成简洁的成本报告"""
        lines = [
            f"=== LLM 成本报告 ===",
            f"会话时长: {self.session_duration_seconds:.0f}s",
            f"总调用次数: {self.total_calls}",
            f"总Token: {self.total_tokens:,}",
            f"估算费用: ¥{self.total_cost:.4f}",
            f"预算使用: {self.total_cost / self.budget_yuan * 100:.1f}%",
            f"",
            f"--- 分组统计 ---",
        ]
        
        for group, rec in sorted(self.records.items()):
            lines.append(
                f"[{group}] 调用{rec.call_count}次 | "
                f"Token {rec.total_tokens:,} | "
                f"费用 ¥{rec.estimated_cost_yuan:.4f} | "
                f"均值 {rec.avg_input_tokens}+{rec.avg_output_tokens} tokens/次"
            )
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """导出为完整字典（供 API 返回）"""
        return {
            "summary": {
                "total_calls": self.total_calls,
                "total_tokens": self.total_tokens,
                "estimated_cost_yuan": round(self.total_cost, 4),
                "budget_yuan": self.budget_yuan,
                "budget_used_pct": round(self.total_cost / self.budget_yuan * 100, 1),
                "session_duration_seconds": round(self.session_duration_seconds, 0),
            },
            "by_group": {
                group: rec.to_dict() 
                for group, rec in sorted(self.records.items())
            },
            "daily": {
                date: {
                    "calls": self._daily_calls.get(date, 0),
                    "cost_yuan": round(self._daily_cost.get(date, 0), 4),
                }
                for date in sorted(self._daily_calls.keys())[-7:]  # 最近7天
            },
        }
    
    def save_daily_stats(self):
        """持久化每日统计到 JSON 文件"""
        date_key = time.strftime("%Y-%m-%d")
        stats_file = self._stats_dir / f"llm_cost_{date_key}.json"
        
        data = self.to_dict()
        data["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"成本统计已保存: {stats_file}")
        except Exception as e:
            logger.warning(f"成本统计保存失败: {e}")
    
    def reset(self):
        """重置计数器（保留历史统计文件）"""
        self.records.clear()
        self._start_time = time.time()


# 全局单例
_global_tracker: Optional[LLMCostTracker] = None


def get_cost_tracker() -> LLMCostTracker:
    """获取全局成本追踪器"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LLMCostTracker()
    return _global_tracker


def reset_cost_tracker():
    """重置全局成本追踪器"""
    global _global_tracker
    if _global_tracker:
        _global_tracker.save_daily_stats()  # 保存
    _global_tracker = LLMCostTracker()
