"""
全局推演引擎 - 圣旨颁布后的天下大势演变

核心功能：
1. 接收玩家圣旨执行结果 + 世界状态
2. 调用 AI 推演圣旨对全局产生的影响
3. 各势力据此调整外交态度、军事部署、内政方向
4. 触发连锁事件（谣言传播、边境摩擦、贸易波动等）
5. 将推演结果写入世界状态（外交关系、事件日志等）

数据流：
  玩家圣旨执行完毕 → 全局推演引擎 → 各势力反应 → 外交/军事/经济连锁效应
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("yuanmo.global_deduction")


async def run_global_deduction(
    edict_text: str,
    ai_analysis: dict,
    execution: dict,
    world_state_obj,  # WorldState 实例
    llm_client,       # advisor LLM 客户端
) -> dict:
    """
    执行一次全局推演，返回推演报告

    Args:
        edict_text: 原始圣旨文本
        ai_analysis: AI 解析结果（intent_analysis, narrative, commands 等）
        execution: 执行结果（executed, failed, total_executed 等）
        world_state_obj: WorldState 实例
        llm_client: LLM 客户端（advisor）

    Returns:
        {
            "global_narrative": "全局推演叙事（文言文，200字以内）",
            "faction_reactions": [
                {"faction_name": "陈友谅", "stance": "警觉", "narrative": "...", "likely_action": "加强江防", "color": "#1E90FF"}
            ],
            "diplomatic_shifts": [
                {"from": "朱元璋", "to": "张士诚", "change": 5, "reason": "..."}
            ],
            "event_triggers": [
                {"event_type": "rumor", "title": "...", "description": "...", "severity": "minor"}
            ],
            "economic_ripples": "经济连锁效应描述",
            "strategic_advice": "谋士对全局形势的建议",
            "summary": "局势推演摘要（50字以内）",
        }
    """
    player = world_state_obj.get_player_faction()
    if not player:
        return _empty_result("无玩家势力")

    player_name = player.name
    player_fid = player.faction_id

    # 构建全局推演的 prompt
    system_prompt = _build_global_system_prompt(player_name)
    user_prompt = _build_global_user_prompt(edict_text, ai_analysis, execution, world_state_obj)

    try:
        result_text = await llm_client.chat_role(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        parsed = _parse_deduction_response(result_text)

        # 将推演结果应用到世界状态
        _apply_deduction_to_world(parsed, world_state_obj, player_fid, edict_text)

        return parsed

    except Exception as e:
        logger.error(f"全局推演失败: {e}", exc_info=True)
        return _empty_result(f"全局推演异常: {str(e)[:50]}")


def _build_global_system_prompt(player_name: str) -> str:
    """构建全局推演系统提示词"""
    return f"""你是元末天下的推演谋士，在「{player_name}」颁布一道圣旨后，你负责推演这道圣旨将如何震动天下，引起各方势力怎样的连锁反应。

你需要像一个真正的乱世谋士一样，思考天下各方的反应：
- 敌人会如何解读这道圣旨？
- 盟友会安心还是疑虑？
- 百姓会拥护还是恐慌？
- 商贾会囤积居奇还是开仓放粮？

## 输出格式（严格 JSON）：
```json
{{
  "global_narrative": "全局态势综述——用古文笔法描述天下因这道圣旨而发生的微妙变化（150字以内）",
  "faction_reactions": [
    {{
      "faction_id": "势力ID",
      "faction_name": "势力名称",
      "stance": "态度变化（如：警觉/敌视/亲近/中立/恐慌/嘲笑）",
      "narrative": "该势力的反应描述（50字以内）",
      "likely_action": "可能采取的行动（20字以内）",
      "color": "势力颜色hex（如#DC143C）"
    }}
  ],
  "diplomatic_shifts": [
    {{
      "from": "势力A名称",
      "to": "势力B名称",
      "change": 数值(-20到+20),
      "reason": "外交变化原因（20字以内）"
    }}
  ],
  "event_triggers": [
    {{
      "event_type": "事件类型（rumor/border/trade/civil/diplomacy）",
      "title": "事件标题（10字以内）",
      "description": "事件描述（60字以内）",
      "severity": "major|minor|trivial",
      "affected_faction": "受影响的势力名称"
    }}
  ],
  "economic_ripples": "经济连锁效应描述（80字以内）",
  "strategic_advice": "对{{玩家势力}}下一步行动的建议（80字以内）",
  "summary": "局势推演摘要（40字以内）"
}}
```

注意：
1. faction_reactions 必须包含至少 3 个其他势力的反应（玩家势力自身除外）
2. 反应需基于各势力的性格特点（如陈友谅多疑、张士诚守成、方国珍骑墙）
3. diplomatic_shifts 需合理，不可同时出现对同一势力的大幅亲近和敌视
4. 用文言文或半文言文风格写作，增强历史沉浸感
"""


def _build_global_user_prompt(
    edict_text: str,
    ai_analysis: dict,
    execution: dict,
    world_state_obj,
) -> str:
    """构建全局推演用户提示词"""
    player = world_state_obj.get_player_faction()
    if not player:
        return ""

    # 玩家基本信息
    player_info = f"""## 当前操作势力（圣旨颁布者）
- 名称：{player.name}
- 称号：{player.title}
- 府库：{player.treasury}银两
- 粮仓：{player.grain}粮草
- 兵力总计：{player.total_troops if hasattr(player, 'total_troops') else '未知'}
- 领地数：{len(world_state_obj.get_faction_tiles(player.faction_id))}
- 当前回合：第{world_state_obj.current_round}回合
- 时间：至正{world_state_obj.current_year}年{world_state_obj.current_month}月·{world_state_obj.current_season}"""

    # 其他势力
    other_factions_lines = ["## 天下各势力"]
    for fid, faction in world_state_obj.factions.items():
        if fid == player.faction_id:
            continue
        stance = "中立"
        rel = world_state_obj.relations.get(f"{player.faction_id}_{fid}", {})
        if isinstance(rel, dict):
            stance = rel.get("stance", "中立")
        tile_count = len(world_state_obj.get_faction_tiles(fid))
        other_factions_lines.append(
            f"- {faction.name}（{faction.title}）：领地{tile_count}个，态度「{stance}」"
        )

    # 圣旨内容
    edict_info = f"""## 圣旨原文
"{edict_text}"

## 尚书省批复
{ai_analysis.get('narrative', '')}

## 执行结果
- 成功执行 {execution['total_executed']} 条政令
- 失败 {execution['total_failed']} 条政令"""

    executed_details = ""
    for cmd in execution.get("executed", []):
        executed_details += f"\n  ✓ {cmd.get('action', '')}: {cmd.get('ai_reason', cmd.get('result', '') or '')}"
    if executed_details:
        edict_info += f"\n已执行详情：{executed_details}"

    failed_details = ""
    for cmd in execution.get("failed", []):
        failed_details += f"\n  ✗ {cmd.get('action', '')}: {cmd.get('reason', '')}"
    if failed_details:
        edict_info += f"\n未能执行：{failed_details}"

    # 外交关系
    relations_lines = ["## 当前外交关系"]
    for key, rel in world_state_obj.relations.items():
        if isinstance(rel, dict) and rel.get("stance"):
            parts = key.split("_")
            if len(parts) >= 2:
                f1 = world_state_obj.factions.get(parts[0])
                f2 = world_state_obj.factions.get("_".join(parts[1:]))
                if f1 and f2:
                    relations_lines.append(f"- {f1.name} ↔ {f2.name}：{rel['stance']}（友好度{rel.get('value', 0)}）")

    return f"""{player_info}

{chr(10).join(other_factions_lines)}

{edict_info}

{chr(10).join(relations_lines)}

请推演这道圣旨颁布后，天下局势将如何演变。聚焦于：
1. 敌对势力会如何反应（陈友谅是否会趁机用兵？）
2. 中立势力可能的态度转变
3. 经济民生层面的连锁影响
4. 可能触发的事件"""


def _parse_deduction_response(raw_text: str) -> dict:
    """解析 AI 返回的全局推演结果"""
    try:
        # 尝试提取 JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            # 尝试直接解析
            data = json.loads(raw_text.strip())

        return {
            "global_narrative": data.get("global_narrative", ""),
            "faction_reactions": data.get("faction_reactions", []),
            "diplomatic_shifts": data.get("diplomatic_shifts", []),
            "event_triggers": data.get("event_triggers", []),
            "economic_ripples": data.get("economic_ripples", ""),
            "strategic_advice": data.get("strategic_advice", ""),
            "summary": data.get("summary", "天下局势因圣旨而微妙变化"),
        }

    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"全局推演JSON解析失败: {e}, 原始文本前200字符: {raw_text[:200]}")

        # 降级：从非结构化文本中提取关键信息
        return {
            "global_narrative": raw_text[:300] if raw_text else "",
            "faction_reactions": [],
            "diplomatic_shifts": [],
            "event_triggers": [],
            "economic_ripples": "",
            "strategic_advice": "",
            "summary": "天下局势暗流涌动",
        }


def _apply_deduction_to_world(
    deduction: dict,
    world_state_obj,
    player_fid: str,
    edict_text: str,
):
    """
    将全局推演结果应用到世界状态

    副作用：
    - 更新外交关系
    - 添加事件日志
    - 更新治理日志
    """
    if not deduction:
        return

    # 1. 应用外交关系变化
    for shift in deduction.get("diplomatic_shifts", []):
        from_name = shift.get("from", "")
        to_name = shift.get("to", "")
        change = shift.get("change", 0)
        reason = shift.get("reason", "")

        # 查找势力ID
        from_fid = _find_faction_id(from_name, world_state_obj)
        to_fid = _find_faction_id(to_name, world_state_obj)

        if from_fid and to_fid:
            rel_key = f"{from_fid}_{to_fid}"
            rel_key_rev = f"{to_fid}_{from_fid}"

            for key in [rel_key, rel_key_rev]:
                if key in world_state_obj.relations:
                    rel = world_state_obj.relations[key]
                    if isinstance(rel, dict):
                        old_val = rel.get("value", 0)
                        new_val = max(-100, min(100, old_val + change))
                        rel["value"] = new_val

                        # 更新立场
                        if new_val >= 60:
                            rel["stance"] = "同盟"
                        elif new_val >= 20:
                            rel["stance"] = "友善"
                        elif new_val >= -20:
                            rel["stance"] = "中立"
                        elif new_val >= -60:
                            rel["stance"] = "敌对"
                        else:
                            rel["stance"] = "死敌"

    # 2. 记录触发的事件
    for event in deduction.get("event_triggers", []):
        world_state_obj.events_log.append({
            "event_id": f"deduction_{world_state_obj.current_round}_{len(world_state_obj.events_log)}",
            "event_type": event.get("event_type", "rumor"),
            "severity": event.get("severity", "minor"),
            "round": world_state_obj.current_round,
            "title": event.get("title", "局势推演"),
            "description": event.get("description", ""),
            "faction_id": _find_faction_id(event.get("affected_faction", ""), world_state_obj) or "",
            "tile_id": "",
            "effects": {"source": "global_deduction"},
            "narrative": "",
        })

    # 3. 写入治理日志
    world_state_obj.governance_logs.append({
        "round": world_state_obj.current_round,
        "title": "全局推演",
        "description": deduction.get("summary", f"圣旨「{edict_text[:30]}」引发天下震动"),
        "narrative": deduction.get("global_narrative", ""),
        "deduction": True,
    })

    # 2.5 将 faction_reactions 写入事件日志（避免 LLM 产出浪费）
    for reaction in deduction.get("faction_reactions", []):
        faction_name = reaction.get("faction_name", "")
        stance_label = reaction.get("stance", "")
        narrative = reaction.get("narrative", "")
        likely_action = reaction.get("likely_action", "")
        if faction_name and stance_label:
            world_state_obj.events_log.append({
                "event_id": f"deduction_react_{world_state_obj.current_round}_{len(world_state_obj.events_log)}",
                "event_type": "diplomacy",
                "severity": "minor",
                "round": world_state_obj.current_round,
                "title": f"{faction_name}：{stance_label}",
                "description": narrative or f"{faction_name}对此事态度为{stance_label}",
                "faction_id": _find_faction_id(faction_name, world_state_obj) or "",
                "tile_id": "",
                "effects": {"source": "global_deduction", "stance": stance_label, "likely_action": likely_action},
                "narrative": narrative,
            })

    world_state_obj.mark_updated()
    logger.info(
        f"全局推演已应用：{len(deduction.get('faction_reactions', []))}条势力反应, "
        f"{len(deduction.get('diplomatic_shifts', []))}条外交变动, "
        f"{len(deduction.get('event_triggers', []))}条触发事件"
    )


def _find_faction_id(name: str, world_state_obj) -> Optional[str]:
    """根据势力名称查找势力ID"""
    for fid, faction in world_state_obj.factions.items():
        if faction.name == name:
            return fid
    return None


def _empty_result(reason: str = "") -> dict:
    """返回空的推演结果"""
    return {
        "global_narrative": reason or "全局推演未能执行",
        "faction_reactions": [],
        "diplomatic_shifts": [],
        "event_triggers": [],
        "economic_ripples": "",
        "strategic_advice": "",
        "summary": reason or "天下暂无波澜",
    }
