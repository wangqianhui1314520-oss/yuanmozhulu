"""
执行反馈闭环层（4.0 新增）

负责阶段3：圣旨执行后的反馈闭环
- 对比 AI 推演预期 vs 实际执行结果
- 生成古风文言执行奏报
- 偏差分析 → 自动建议调整
- 将反馈写入 EdictContext，影响下回合 AI 决策

不修改任何现有文件的核心逻辑。
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from server.core.edict_nlp import get_edict_context

logger = logging.getLogger("yuanmo.edict_feedback")


@dataclass
class EdictReport:
    """圣旨执行奏报"""
    edict_text: str = ""
    
    # 执行摘要
    total_planned: int = 0        # 计划指令数
    total_executed: int = 0       # 实际执行数
    total_failed: int = 0         # 执行失败数
    total_skipped: int = 0        # 被跳过数
    
    # 资源变化
    treasury_change: int = 0
    grain_change: int = 0
    troops_change: int = 0
    
    # 偏差分析
    deviation_level: str = ""     # none / minor / moderate / significant
    deviation_details: list[str] = field(default_factory=list)
    
    # 文言奏报
    report_text: str = ""         # 古风文言执行奏报
    narrative: str = ""           # 首辅口吻的批复
    
    # 建议
    adjustment_suggestion: str = ""
    next_turn_hint: str = ""
    
    # 上下文
    should_record: bool = True


def generate_execution_report(
    edict_text: str,
    plan_commands: list[dict],
    execution_result: dict,
) -> EdictReport:
    """
    生成圣旨执行奏报（本地计算版，无 LLM 依赖）。
    
    对比 StrategicPlan 中的预期指令与实际执行结果，
    计算偏差并生成结构化报告。
    
    Args:
        edict_text: 原始圣旨文本
        plan_commands: 计划执行的指令列表
        execution_result: 实际执行结果（来自 execute_edict_commands）
    
    Returns:
        EdictReport 对象
    """
    report = EdictReport(edict_text=edict_text)
    
    executed = execution_result.get("executed", [])
    failed = execution_result.get("failed", [])
    
    report.total_planned = len(plan_commands)
    report.total_executed = len(executed)
    report.total_failed = len(failed)
    report.total_skipped = report.total_planned - report.total_executed - report.total_failed
    
    # 计算资源变化
    for ex in executed:
        result = ex.get("result", {})
        # 从执行结果中提取资源变化（如果有）
        report.treasury_change -= result.get("cost_silver", 0)
        report.grain_change -= result.get("cost_grain", 0)
        if ex.get("action") == "recruit":
            report.troops_change += result.get("recruited", 0)
        if ex.get("action") == "plunder":
            report.treasury_change += result.get("loot_silver", 0)
            report.grain_change += result.get("loot_grain", 0)
    
    # 偏差分析
    deviation_details = []
    success_rate = report.total_executed / max(1, report.total_planned)
    
    if report.total_failed > 0:
        deviation_details.append(f"共计{report.total_failed}条政令未能施行")
        for f in failed[:3]:  # 最多显示3条失败原因
            deviation_details.append(
                f"「{f.get('action', '')}」— {f.get('reason', '未知原因')[:60]}"
            )
    
    if report.total_skipped > 0:
        deviation_details.append(f"{report.total_skipped}条政令因校验未通过而跳过")
    
    # 偏差等级
    if success_rate >= 0.9:
        report.deviation_level = "none"
        deviation_details.insert(0, "圣意施行顺利，诸般政令尽数落地。")
    elif success_rate >= 0.7:
        report.deviation_level = "minor"
    elif success_rate >= 0.4:
        report.deviation_level = "moderate"
    else:
        report.deviation_level = "significant"
    
    report.deviation_details = deviation_details
    
    # 文言奏报（不依赖 LLM 的模板生成）
    report.report_text = _generate_report_text(report)
    report.narrative = _generate_narrative(report)
    
    # 建议
    report.adjustment_suggestion = _generate_adjustment(report, execution_result)
    report.next_turn_hint = _generate_next_hint(report)
    
    return report


def _generate_report_text(report: EdictReport) -> str:
    """生成本地古风执行奏报"""
    lines = ["【尚书省奏报】", ""]
    
    lines.append(f"  奉旨拟就{report.total_planned}条政令，")
    
    if report.deviation_level == "none":
        lines.append(f"  全数施行无碍。")
        lines.append(f"  已行{report.total_executed}条，悉数落地。")
    else:
        lines.append(f"  已行{report.total_executed}条，")
        if report.total_failed > 0:
            lines.append(f"  未行{report.total_failed}条。")
        if report.total_skipped > 0:
            lines.append(f"  另有{report.total_skipped}条因校验未通过而暂缓。")
    
    # 资源变动
    changes = []
    if report.treasury_change != 0:
        changes.append(f"府库{'增' if report.treasury_change > 0 else '减'}银{abs(report.treasury_change)}两")
    if report.grain_change != 0:
        changes.append(f"仓廪{'增' if report.grain_change > 0 else '减'}粮{abs(report.grain_change)}石")
    if report.troops_change != 0:
        changes.append(f"营伍{'增' if report.troops_change > 0 else '减'}兵{abs(report.troops_change)}人")
    
    if changes:
        lines.append("")
        lines.append(f"  财力变动：{'，'.join(changes)}。")
    
    # 偏差
    if report.deviation_details:
        lines.append("")
        for detail in report.deviation_details[:5]:
            lines.append(f"  {detail}")
    
    lines.append("")
    lines.append("  臣等恭呈御览，伏惟圣裁。")
    
    return "\n".join(lines)


def _generate_narrative(report: EdictReport) -> str:
    """生成首辅口吻的批复"""
    if report.deviation_level == "none":
        return f"臣谨奏：圣意煌煌，{report.total_executed}条政令尽数施行。各部司职，各安其位。请陛下御览。"
    elif report.deviation_level == "minor":
        return f"臣谨奏：圣意大略已行，{report.total_executed}条政令落地。惟{report.total_failed}条受阻，臣已另拟补奏。"
    else:
        return f"臣谨奏：圣意施行遇阻，{report.total_executed}条已行，{report.total_failed}条未果。恳请陛下明示是否调整方略。"


def _generate_adjustment(report: EdictReport, execution_result: dict) -> str:
    """生成调整建议"""
    failed = execution_result.get("failed", [])
    
    suggestions = []
    
    for f in failed:
        reason = f.get("reason", "")
        action = f.get("action", "")
        
        if "银两不足" in reason:
            suggestions.append(f"府库空虚，建议先加税或劫掠富庶之地以充实国库，再行「{action}」之事")
        elif "粮草不足" in reason:
            suggestions.append(f"粮草不继，建议先屯田开发或建造粮仓，储备充足后再「{action}」")
        elif "兵力不足" in reason:
            suggestions.append(f"营中空虚，建议先征兵扩军，积蓄兵力后再议出征")
        elif "军械不足" in reason:
            suggestions.append(f"军械短缺，建议先建造军械所补充装备")
        elif "不属于己方" in reason:
            suggestions.append(f"此地块非我疆土，若欲取之，需先行出兵攻占")
        elif "重复" in reason:
            suggestions.append(f"此令与前旨重复，已自动合并，无需另行颁布")
    
    if not suggestions:
        if report.deviation_level == "none":
            return "一切顺利，可继续推行既定方略。"
        else:
            return "建议根据执行效果调整后续指令。"
    
    return "；".join(suggestions[:3])


def _generate_next_hint(report: EdictReport) -> str:
    """生成下回合行动提示"""
    if report.deviation_level == "none":
        return "既定方略推行顺利，可继续下一阶段部署。"
    elif report.deviation_level == "minor":
        return "略有阻碍，可稍作调整后继续推进。"
    elif report.deviation_level == "moderate":
        return "多项政令受阻，建议审视当前策略，调整方针。"
    else:
        return "政令多有不济，建议重新评估局势后再颁新旨。"


# ============================================================
# 反馈写入上下文
# ============================================================

def write_feedback_to_context(
    edict_text: str,
    plan_commands: list[dict],
    execution_result: dict,
    report: EdictReport,
) -> None:
    """
    将执行反馈写入 EdictContext，供下回合 AI 决策使用。
    
    写入内容：
    - 已执行的指令列表（去重用）
    - 执行成功率（AI 可据此调整风险偏好）
    - 资源变动方向（AI 可据此调整资源分配策略）
    """
    try:
        ctx = get_edict_context()
        
        executed_actions = [
            e.get("action", "") for e in execution_result.get("executed", [])
        ]
        failed_actions = [
            f.get("action", "") for f in execution_result.get("failed", [])
        ]
        
        # 记录圣旨
        ctx.record_edict(
            text=edict_text,
            actions=executed_actions,
            intent=report.deviation_level,
            summary=f"已行{report.total_executed}/计划{report.total_planned}条"
        )
        
        logger.debug(
            f"反馈写入上下文: {edict_text[:30]}... "
            f"已行{report.total_executed} 未行{report.total_failed}"
        )
        
    except Exception as e:
        logger.debug(f"反馈写入上下文跳过: {e}")


# ============================================================
# AI 增强文言奏报（可选，LLM 依赖）
# ============================================================

async def generate_ai_report(
    edict_text: str,
    plan_commands: list[dict],
    execution_result: dict,
    llm_client,
) -> EdictReport:
    """
    调用 LLM 生成更精美的古风文言执行奏报。
    
    仅在 LLM 可用时使用，否则降级到本地模板生成。
    
    Args:
        edict_text: 原始圣旨文本
        plan_commands: 计划执行的指令列表
        execution_result: 实际执行结果
        llm_client: LLM 客户端
    
    Returns:
        EdictReport 对象
    """
    # 先生成本地基础报告
    report = generate_execution_report(edict_text, plan_commands, execution_result)
    
    # 如果偏差不大，不需要 AI 增强
    if report.deviation_level in ("none", "minor"):
        return report
    
    try:
        executed = execution_result.get("executed", [])
        failed = execution_result.get("failed", [])
        
        executed_str = "\n".join(
            f"- {e.get('action', '')}: {e.get('result', {}).get('message', '')[:80]}"
            for e in executed[:5]
        )
        failed_str = "\n".join(
            f"- {f.get('action', '')}: {f.get('reason', '')[:80]}"
            for f in failed[:5]
        )
        
        prompt = f"""你是尚书省首辅。请对以下圣旨执行结果撰写古风文言奏报。

## 圣旨原文
「{edict_text}」

## 已行政令
{executed_str or '无'}

## 未行政令
{failed_str or '无'}

## 要求
- 用典雅的古文撰写奏报（80字以内）
- 包含"启奏陛下"等套语
- 若有不济之处，需委婉指出原因
- 若有建议，以"臣以为…"引出

请直接输出文言奏报，不要 JSON 格式。"""

        result = await llm_client.chat_role(
            prompt=prompt,
            system_prompt="你是尚书省首辅，精通明代奏疏文体。请用典雅的文言撰写执行奏报。",
            temperature=0.5,
        )
        
        if result and result.strip():
            report.narrative = result.strip()[:300]
            logger.debug("AI文言奏报生成成功")
        
    except Exception as e:
        logger.debug(f"AI文言奏报生成跳过: {e}")
    
    return report
