"""
AI 全局战略推演层（4.0 新增）

核心理念：将"关键词匹配 → 意图分类 → 拆解指令"的规则驱动流程，
升级为"AI 全局态势推演 → 战略方案生成 → 指令执行与反馈"的认知增强管道。

本模块负责阶段1：AI 战略推演
- 接收圣旨文本 + 完整世界状态
- LLM 以首辅身份做全局战略推演
- 输出结构化 StrategicPlan（含主方案、备选方案、风险评估、资源投影）

与现有 edict_engine / unified_edict_engine 协同：
- 当 USE_AI_SIMULATION=True 且 LLM 可用时，本模块作为第一道处理层
- 当 AI 不可用时，自动降级到原有 parse_edict_locally 管道
- 不修改任何现有文件的核心逻辑
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from server.core.edict_nlp import (
    extract_numbers, extract_faction_names, extract_action_intents,
    build_preprocess_hint, robust_json_parse, classify_edict,
    get_edict_context,
)
from server.core.edict_engine import AVAILABLE_ACTIONS, build_world_summary, validate_commands

logger = logging.getLogger("yuanmo.strategic_simulation")


# ============================================================
# 数据模型
# ============================================================

class SimulationPhase(str, Enum):
    """推演阶段"""
    SITUATION_ANALYSIS = "situation_analysis"    # 态势分析
    INTENT_UNDERSTANDING = "intent_understanding"  # 意图理解
    CONSEQUENCE_SIMULATION = "consequence_simulation"  # 后果推演
    PLAN_GENERATION = "plan_generation"           # 方案生成


@dataclass
class StrategicRisk:
    """单个风险评估"""
    step_index: int = 0
    risk_type: str = ""              # military / economic / diplomatic / stability
    description: str = ""
    probability: float = 0.0         # 0-1
    impact: str = ""                 # low / medium / high / critical
    mitigation: str = ""             # 缓解措施


@dataclass
class ResourceProjection:
    """资源投影"""
    treasury_before: int = 0
    treasury_after: int = 0
    grain_before: int = 0
    grain_after: int = 0
    troops_before: int = 0
    troops_after: int = 0
    stability_before: int = 0
    stability_after: int = 0
    arms_before: int = 0
    arms_after: int = 0
    deficit_warning: str = ""


@dataclass
class GeopoliticalImpact:
    """地缘影响分析"""
    faction_id: str = ""
    faction_name: str = ""
    reaction: str = ""               # hostile / neutral / friendly / opportunistic
    description: str = ""
    probability: float = 0.0


@dataclass
class StrategicStep:
    """战略方案中的单步"""
    step: int = 0
    turn_offset: int = 0            # 相对当前回合的偏移
    description: str = ""           # 中文描述
    commands: list[dict] = field(default_factory=list)  # 该步骤对应的指令
    expected_effect: str = ""       # 预期效果
    prerequisites: list[str] = field(default_factory=list)  # 前提条件


@dataclass
class StrategicPlan:
    """AI 推演生成的完整战略方案"""
    # 元信息
    edict_text: str = ""
    ai_confidence: float = 0.0       # 方案可靠性 0-1
    
    # 态势分析
    situation_analysis: str = ""
    intent_understanding: str = ""
    key_observations: list[str] = field(default_factory=list)
    
    # 主方案
    primary_plan: list[StrategicStep] = field(default_factory=list)
    plan_narrative: str = ""
    
    # 备选方案
    alternative_plans: list[list[StrategicStep]] = field(default_factory=list)
    alternative_narratives: list[str] = field(default_factory=list)
    
    # 风险评估
    risk_matrix: list[StrategicRisk] = field(default_factory=list)
    overall_risk_level: str = ""     # low / medium / high / critical
    
    # 资源投影
    resource_projection: Optional[ResourceProjection] = None
    
    # 地缘影响
    geopolitical_impacts: list[GeopoliticalImpact] = field(default_factory=list)
    
    # AI 分析文本
    consequence_analysis: str = ""
    resource_assessment: str = ""
    follow_up_suggestion: str = ""
    
    # 古风输出
    edict_language: str = ""          # 文言圣旨正文
    narrative: str = ""              # 首辅批复
    
    # 所有步骤合并的指令列表（兼容现有管道）
    merged_commands: list[dict] = field(default_factory=list)


# ============================================================
# AI 推演 Prompt 构建
# ============================================================

def build_simulation_system_prompt(faction_name: str, world_summary: str) -> str:
    """构建 AI 战略推演的系统提示词"""
    
    actions_desc = []
    for name, info in AVAILABLE_ACTIONS.items():
        actions_desc.append(
            f"- **{name}**: {info['desc']}\n"
            f"  参数: {', '.join(info['params'])}\n"
            f"  消耗: {info['costs']}"
        )
    
    return f"""你是元末乱世中的尚书省首辅，身兼兵部、户部、礼部之责，精通战略推演与庙堂决策。
你的使命：在君主颁布圣旨之前，以首辅身份做完整战略推演，评估可行性、预测后果、给出建议。

当前你辅佐的势力是「{faction_name}」。

## 输出合约（最高优先级）
1. 整个回复必须是纯 JSON 对象，禁止任何前言/后语/Markdown 包装
2. 必须包含所有字段（共19个），字段名严格匹配

## 当前天下局势
{world_summary}

## 核心职责

### 一、态势感知
- 分析天下大势：实力对比、关键地理节点、外交格局
- 评估己方资源（银两、粮草、兵力、民心）是否足够
- 识别关键约束（季节、行军距离、外交牵制）

### 二、意图理解
- 解读君主真实战略意图（可能是多层嵌套的）
- 模糊指令合理展开，矛盾指令指出问题并给替代建议

### 三、后果推演
- 推演 1-3 回合后的态势变化
- 预测其他势力反应（趁虚而入/结盟对抗/坐观虎斗）
- 评估资源消耗可持续性

### 四、方案生成
- 主方案+1-2个备选（保守/激进）
- 每个方案标注风险等级和预期效果

## 可用政令类型（共{len(AVAILABLE_ACTIONS)}种）
{chr(10).join(actions_desc)}

## 输出格式（纯 JSON，禁止 Markdown 包装）
{{
  "situation_analysis": "全局态势分析（150字以内）",
  "intent_understanding": "意图解读（100字以内）",
  "key_observations": ["发现1", "发现2", "发现3"],
  "primary_plan": {{
    "narrative": "主方案文言描述（80字以内）",
    "steps": [{{
      "step": 1,
      "turn_offset": 0,
      "description": "操作描述",
      "commands": [{{"action": "操作类型", "params": {{"参数": "值"}}, "reason": "理由", "priority": "high|medium|low"}}],
      "expected_effect": "预期效果"
    }}]
  }},
  "alternative_plans": [{{"narrative": "备选描述", "steps": [...]}}],
  "risk_matrix": [{{"step_index": 0, "risk_type": "military|economic|diplomatic|stability", "description": "风险描述", "probability": 0.3, "impact": "low|medium|high|critical", "mitigation": "缓解建议"}}],
  "overall_risk_level": "low|medium|high|critical",
  "resource_projection": {{"treasury_before": 0, "treasury_after": 0, "grain_before": 0, "grain_after": 0, "troops_before": 0, "troops_after": 0, "stability_before": 0, "stability_after": 0, "arms_before": 0, "arms_after": 0, "deficit_warning": "资源不足警示"}},
  "geopolitical_impacts": [{{"faction_name": "势力名", "reaction": "hostile|neutral|friendly|opportunistic", "description": "反应描述", "probability": 0.5}}],
  "consequence_analysis": "后果推演（100字以内）",
  "resource_assessment": "资源评估（80字以内）",
  "follow_up_suggestion": "下一步建议（50字以内）",
  "ai_confidence": 0.85,
  "edict_language": "文言圣旨正文（150-250字，三段结构）",
  "narrative": "首辅古风批复（100字以内）"
}}

## 核心规则
1. action 必须来自可用政令类型列表，禁止编造
2. params 参数名与可用政令定义一致
3. 资源投影基于玩家实际数据计算
4. 风险评估概率有依据：国库空虚时 economic risk >0.5
5. 地缘影响具体到势力名
6. 资源不匹配时：primary_plan 给节制版本，alternative_plans 给原始意图版本
7. edict_language 按类别选文体：军事→敕曰、内政→令曰、恩赏→诰曰/制曰、外交→诏曰、细作→密敕。严禁一律用"诏曰"
8. alternative_plans 至少1个、最多2个
9. 咨询性问题（如何/怎么/分析）时 primary_plan steps 可为空
10. 单步 commands≤5条，总计≤12条

## 禁止事项
- 禁止在 JSON 外输出任何文字或 Markdown 标记
- 禁止编造不存在的 action
- 禁止讨论元末（1368年）以后的内容"""


def build_simulation_user_prompt(
    edict_text: str,
    world_state: dict,
    nlp_hint: str = "",
) -> str:
    """构建 AI 战略推演的用户提示词"""
    
    player_fid = world_state.get("player_faction_id", "")
    factions = world_state.get("factions", {})
    tiles = world_state.get("tiles", {})
    player = factions.get(player_fid, {})
    
    # 玩家地块
    player_tiles = {
        tid: t for tid, t in tiles.items()
        if t.get("faction_id") == player_fid
    }
    
    # 其他势力
    other_factions = []
    for fid, f in factions.items():
        if fid != player_fid and f.get("is_alive", False):
            other_factions.append(
                f"{f.get('name', fid)}: "
                f"兵力{f.get('total_troops', 0)} "
                f"城池{f.get('tile_count', 0)} "
                f"态度{world_state.get('relations', {}).get(f'{player_fid}|{fid}', {}).get('stance', 'neutral')}"
            )
    
    # 地块详情
    tile_summary = []
    for tid, t in player_tiles.items():
        detail = (
            f"  {t.get('tile_name', tid)}({tid}): "
            f"兵力{t.get('troops', 0)} 人口{t.get('population', 0)} "
            f"民心{t.get('morale', 50)} 城防{t.get('fortification', 0)}"
        )
        if t.get('is_capital'):
            detail += " [都城]"
        if t.get('disasters'):
            detail += f" ⚠{','.join(t.get('disasters', []))}"
        tile_summary.append(detail)
    
    # 外交关系
    relations = world_state.get("relations", {})
    diplomacy_summary = []
    for key, rel in relations.items():
        a, b = key.split("|") if "|" in key else ("", "")
        if a == player_fid or b == player_fid:
            other = b if a == player_fid else a
            other_f = factions.get(other, {})
            diplomacy_summary.append(
                f"  vs {other_f.get('name', other)}: "
                f"{rel.get('stance', 'neutral')} (态度{rel.get('attitude', 0)})"
            )
    
    season = world_state.get('current_season', '春')
    season_hints = {
        "春": "募兵恢复快(+7%)、人口增长旺盛(×1.6)。春汛融雪可能引发洪水。",
        "夏": "粮耗略增(×1.1)、洪水蝗灾高发。海运贸易繁忙(港口收入100银)。",
        "秋": "秋高气爽宜出征(攻方×1.1)、税收最高(×1.3)、粮仓产出大增(×1.8)。",
        "冬": "严冬耗粮大增(×1.4)、进攻削弱(×0.85)、守城有利(×1.10)。宜休养生息，但非不可战。",
    }
    
    prompt = f"""## 📜 圣旨内容
「{edict_text}」

## ⚔️ 本方实力
势力: {player.get('name', '未知')} ({player_fid})
银两: {player.get('treasury', 0)}  粮草: {player.get('grain', 0)}
军械: {player.get('arms', 0)}  战马: {player.get('horses', 0)}
总兵力: {player.get('total_troops', 0)}  总人口: {player.get('total_population', 0)}
民心: {player.get('realm_stability', 50)}  声望: {player.get('reputation', 50)}
回合: {world_state.get('current_round', 0)}  时间: {world_state.get('current_year', 1351)}年{world_state.get('current_month', 1)}月
季节: {season} — {season_hints.get(season, '')}

## 🏰 己方城池
{chr(10).join(tile_summary) if tile_summary else '无'}

## 🌍 其他势力
{chr(10).join(other_factions) if other_factions else '无'}

## 🤝 外交关系
{chr(10).join(diplomacy_summary) if diplomacy_summary else '无'}

{nlp_hint}

请以尚书省首辅身份，对上述圣旨进行一次完整的战略推演，输出结构化 JSON。"""

    return prompt


# ============================================================
# 核心推演函数
# ============================================================

async def simulate_strategic_consequences(
    edict_text: str,
    world_state: dict,
    llm_client,
    edict_history: list = None,
    max_retries: int = 2,
) -> StrategicPlan:
    """
    AI 全局战略推演 —— 阶段1核心函数。
    
    调用 LLM 进行完整的战略推演，输出结构化 StrategicPlan。
    
    Args:
        edict_text: 圣旨原始文本
        world_state: 游戏世界状态字典
        llm_client: LLM 客户端（需支持 chat_role 接口）
        edict_history: 历史圣旨记录
        max_retries: JSON 解析失败时的最大重试次数
    
    Returns:
        StrategicPlan 对象，或标记 confidence=0 的空计划（失败时）
    """
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    faction_name = player.get("name", "义军")
    
    # NLP 预处理提示
    nlp_hint = build_preprocess_hint(edict_text, world_state)
    
    # 构建 prompt
    world_summary = build_world_summary(world_state)
    system_prompt = build_simulation_system_prompt(faction_name, world_summary)
    user_prompt = build_simulation_user_prompt(edict_text, world_state, nlp_hint)
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"AI战略推演 第{attempt+1}次尝试: {edict_text[:50]}...")
            
            result = await llm_client.chat_role(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.35 if attempt == 0 else 0.5,
            )
            
            if not result or not result.strip():
                logger.warning("AI战略推演返回空文本")
                last_error = "AI返回空文本"
                continue
            
            # JSON 解析
            parsed = robust_json_parse(result)
            if not parsed:
                logger.warning(f"AI战略推演JSON解析失败，文本前200: {result[:200]}")
                last_error = "JSON解析失败"
                continue
            
            # 构建 StrategicPlan
            plan = _parse_strategic_plan(parsed, edict_text, world_state)
            
            if plan and plan.ai_confidence > 0:
                logger.info(
                    f"AI战略推演成功: 置信度{plan.ai_confidence:.0%}, "
                    f"主方案{len(plan.primary_plan)}步, "
                    f"备选{len(plan.alternative_plans)}个, "
                    f"风险{len(plan.risk_matrix)}项"
                )
                return plan
            else:
                logger.warning("AI战略推演解析后为空计划")
                last_error = "解析后计划为空"
                
        except Exception as e:
            logger.error(f"AI战略推演异常 (尝试{attempt+1}): {e}", exc_info=True)
            last_error = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1.5 * (attempt + 1))
    
    # 推演失败，返回空计划
    logger.warning(f"AI战略推演全部失败: {last_error}")
    return StrategicPlan(
        edict_text=edict_text,
        ai_confidence=0.0,
        situation_analysis=f"推演失败: {last_error}",
        intent_understanding="未能完成推演",
        primary_plan=[],
    )


def _parse_strategic_plan(parsed: dict, edict_text: str, world_state: dict) -> StrategicPlan:
    """将 LLM 返回的 JSON 解析为 StrategicPlan 对象"""
    
    plan = StrategicPlan(
        edict_text=edict_text,
        ai_confidence=parsed.get("ai_confidence", 0.7),
        situation_analysis=parsed.get("situation_analysis", ""),
        intent_understanding=parsed.get("intent_understanding", ""),
        key_observations=parsed.get("key_observations", []),
        overall_risk_level=parsed.get("overall_risk_level", "medium"),
        consequence_analysis=parsed.get("consequence_analysis", ""),
        resource_assessment=parsed.get("resource_assessment", ""),
        follow_up_suggestion=parsed.get("follow_up_suggestion", ""),
        edict_language=parsed.get("edict_language", ""),
        narrative=parsed.get("narrative", ""),
    )
    
    # 解析主方案
    primary = parsed.get("primary_plan", {})
    plan.plan_narrative = primary.get("narrative", "")
    for step_data in primary.get("steps", []):
        step = StrategicStep(
            step=step_data.get("step", 0),
            turn_offset=step_data.get("turn_offset", 0),
            description=step_data.get("description", ""),
            commands=step_data.get("commands", []),
            expected_effect=step_data.get("expected_effect", ""),
            prerequisites=step_data.get("prerequisites", []),
        )
        plan.primary_plan.append(step)
    
    # 合并所有当前回合(turn_offset=0)的指令
    for step in plan.primary_plan:
        if step.turn_offset == 0:
            # 验证每条指令
            valid_cmds, _ = validate_commands(step.commands, world_state)
            plan.merged_commands.extend(valid_cmds)
    
    # 解析备选方案
    for alt_data in parsed.get("alternative_plans", []):
        alt_steps = []
        for sd in alt_data.get("steps", []):
            alt_steps.append(StrategicStep(
                step=sd.get("step", 0),
                turn_offset=sd.get("turn_offset", 0),
                description=sd.get("description", ""),
                commands=sd.get("commands", []),
                expected_effect=sd.get("expected_effect", ""),
            ))
        plan.alternative_plans.append(alt_steps)
        plan.alternative_narratives.append(alt_data.get("narrative", ""))
    
    # 解析风险矩阵
    for risk_data in parsed.get("risk_matrix", []):
        plan.risk_matrix.append(StrategicRisk(
            step_index=risk_data.get("step_index", 0),
            risk_type=risk_data.get("risk_type", ""),
            description=risk_data.get("description", ""),
            probability=risk_data.get("probability", 0.0),
            impact=risk_data.get("impact", "medium"),
            mitigation=risk_data.get("mitigation", ""),
        ))
    
    # 解析资源投影
    rp = parsed.get("resource_projection", {})
    if rp:
        plan.resource_projection = ResourceProjection(
            treasury_before=rp.get("treasury_before", 0),
            treasury_after=rp.get("treasury_after", 0),
            grain_before=rp.get("grain_before", 0),
            grain_after=rp.get("grain_after", 0),
            troops_before=rp.get("troops_before", 0),
            troops_after=rp.get("troops_after", 0),
            stability_before=rp.get("stability_before", 0),
            stability_after=rp.get("stability_after", 0),
            arms_before=rp.get("arms_before", 0),
            arms_after=rp.get("arms_after", 0),
            deficit_warning=rp.get("deficit_warning", ""),
        )
    
    # 解析地缘影响
    for geo_data in parsed.get("geopolitical_impacts", []):
        plan.geopolitical_impacts.append(GeopoliticalImpact(
            faction_name=geo_data.get("faction_name", ""),
            reaction=geo_data.get("reaction", "neutral"),
            description=geo_data.get("description", ""),
            probability=geo_data.get("probability", 0.0),
        ))
    
    # 如果没有通过 primary_plan.steps 获得指令，尝试从 parsed.commands 获取（兼容旧格式）
    if not plan.merged_commands and parsed.get("commands"):
        valid_cmds, _ = validate_commands(parsed["commands"], world_state)
        plan.merged_commands = valid_cmds
    
    return plan


# ============================================================
# 轻量预览（用于前端实时校验）
# ============================================================

async def preview_simulation(
    edict_text: str,
    world_state: dict,
    llm_client,
) -> dict:
    """
    轻量级战略预览 —— 用于前端实时校验。
    
    不进行完整的战略推演，只快速评估：
    - 意图分类
    - 资源可行性
    - 潜在风险
    
    相比完整推演，Token 消耗减少约 70%。
    
    Returns:
        {
            "intent_category": str,
            "sub_intents": [str],
            "confidence": float,
            "feasibility": "feasible|constrained|infeasible",
            "feasibility_reason": str,
            "risk_flags": [str],
            "suggested_actions": [str],
            "resource_warning": str,
            "needs_clarification": bool,
        }
    """
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    faction_name = player.get("name", "义军")
    
    # 快速世界摘要
    world_summary = build_world_summary(world_state)
    
    preview_prompt = f"""你是「{faction_name}」势力的翰林学士。请快速评估以下圣旨的可行性。

## 当前状态
银两: {player.get('treasury', 0)}  粮草: {player.get('grain', 0)}
兵力: {player.get('total_troops', 0)}  民心: {player.get('realm_stability', 50)}
季节: {world_state.get('current_season', '春')}

## 圣旨内容
「{edict_text}」

## 输出 JSON
```json
{{
  "intent_category": "military|civil|diplomacy|personnel|national_policy|strategic_consult|mixed|cancel",
  "sub_intents": ["recruit", "march"],
  "confidence": 0.85,
  "feasibility": "feasible|constrained|infeasible",
  "feasibility_reason": "简短理由",
  "risk_flags": ["国库可能不足", "冬季行军损耗大"],
  "suggested_actions": ["recruit", "march", "fortify"],
  "resource_warning": "资源警示（若有）",
  "needs_clarification": false
}}
```"""

    try:
        # 使用较低温度提高一致性
        result = await llm_client.chat_role(
            prompt=preview_prompt,
            system_prompt="你是翰林学士，负责快速审核圣旨可行性。仅输出JSON，不要任何额外内容。",
            temperature=0.2,
        )
        
        if not result or not result.strip():
            return _empty_preview(edict_text)
        
        parsed = robust_json_parse(result)
        if not parsed:
            # JSON 解析失败，回退到本地分类
            from server.core.unified_edict_engine import classify_edict_intent, extract_edict_entities, EdictIntentCategory
            entity = extract_edict_entities(edict_text, world_state)
            classification = classify_edict_intent(edict_text, entity)
            return {
                "intent_category": classification["primary"].value if hasattr(classification["primary"], 'value') else str(classification["primary"]),
                "sub_intents": [si.value for si in classification.get("sub_intents", [])],
                "confidence": classification.get("confidence", 0.5),
                "feasibility": "constrained",
                "feasibility_reason": "AI预览不可用，使用本地评估",
                "risk_flags": [],
                "suggested_actions": [],
                "resource_warning": "",
                "needs_clarification": False,
            }
        
        return {
            "intent_category": parsed.get("intent_category", "unknown"),
            "sub_intents": parsed.get("sub_intents", []),
            "confidence": parsed.get("confidence", 0.7),
            "feasibility": parsed.get("feasibility", "constrained"),
            "feasibility_reason": parsed.get("feasibility_reason", ""),
            "risk_flags": parsed.get("risk_flags", []),
            "suggested_actions": parsed.get("suggested_actions", []),
            "resource_warning": parsed.get("resource_warning", ""),
            "needs_clarification": parsed.get("needs_clarification", False),
        }
    
    except Exception as e:
        logger.warning(f"AI战略预览异常: {e}")
        return _empty_preview(edict_text)


def _empty_preview(edict_text: str) -> dict:
    """空预览结果"""
    from server.core.unified_edict_engine import classify_edict_intent, extract_edict_entities
    # 尝试本地分类作为回退
    try:
        # 简化版：仅做快速分类，不构建完整 world_state
        return {
            "intent_category": "unknown",
            "sub_intents": [],
            "confidence": 0.3,
            "feasibility": "constrained",
            "feasibility_reason": "预览服务暂不可用",
            "risk_flags": [],
            "suggested_actions": [],
            "resource_warning": "",
            "needs_clarification": False,
        }
    except Exception:
        return {
            "intent_category": "unknown",
            "sub_intents": [],
            "confidence": 0.0,
            "feasibility": "infeasible",
            "feasibility_reason": "预览服务不可用",
            "risk_flags": [],
            "suggested_actions": [],
            "resource_warning": "",
            "needs_clarification": False,
        }


# ============================================================
# 方案转指令（兼容现有管道）
# ============================================================

def plan_to_commands(plan: StrategicPlan, world_state: dict) -> tuple[list[dict], list[dict]]:
    """
    将 StrategicPlan 中的当前回合步骤转换为标准指令列表。
    
    对每条指令调用 validate_commands 做白名单校验。
    
    Returns:
        (valid_commands, invalid_commands)
    """
    if not plan.merged_commands:
        return [], []
    
    return validate_commands(plan.merged_commands, world_state)


# ============================================================
# 全局开关
# ============================================================

# 是否启用 AI 战略推演（可通过环境变量或配置覆盖）
USE_AI_SIMULATION = True

# 推演超时时间（秒）
SIMULATION_TIMEOUT = 120

# 最低 AI 置信度阈值（低于此值自动降级到本地解析）
MIN_AI_CONFIDENCE = 0.3
