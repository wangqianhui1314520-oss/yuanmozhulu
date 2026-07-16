"""
v4.3 LLM结算审阅引擎 — 在规则引擎计算完成后，LLM审阅并提供有界调整

设计原则：
1. LLM只提供建议调整值，引擎验证边界后才应用
2. 所有调整严格有界（经济±5%、士气±5、关系±2）
3. 每个审阅维度1次LLM调用（批量处理全部势力/配对）
4. 异常/超时自动跳过，不影响核心结算
5. 使用 chat_fast (enemy) 降低成本

模块结构：
- SettlementReview: 经济结算审阅（税/粮/人口政策微调）
- CombatReview: 战前态势分析（士气修正）
- DiplomacyReview: 外交潜意识漂移（关系微调）
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("yuanmo.core.llm_review")


def _extract_json(raw: str) -> Optional[dict]:
    """从LLM响应中提取JSON对象"""
    if not raw:
        return None
    # 优先直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 匹配JSON块
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


class SettlementReview:
    """v4.3 经济结算审阅 — 批量审阅所有势力的税收/粮食/人口政策"""

    @staticmethod
    async def review_all(
        world_state: dict,
        settlement_result: dict,
        clients: dict,
    ) -> dict:
        """
        审阅所有势力的经济结算结果，返回有界调整建议。

        Args:
            world_state: 完整世界状态
            settlement_result: SettleEngine.phase_settle() 的返回值
            clients: LLM客户端字典 (含 "enemy"/"law"/"advisor")

        Returns:
            {
                "factions": {
                    faction_id: {
                        "tax_adjustment": float,   # -0.05 ~ +0.05 (税率调整)
                        "grain_policy": str,       # "hoard"/"normal"/"relief"
                        "reasoning": str,          # 调整理由（50字内）
                    }
                },
                "narrative": str,  # 全局经济综述（150-200字）
                "reviewed_count": int,
            }
        """
        client = clients.get("law", clients.get("advisor"))
        if not client:
            logger.info("LLM不可用，跳过结算审阅")
            return {"factions": {}, "narrative": "", "reviewed_count": 0}

        factions = world_state.get("factions", {})
        living = {fid: f for fid, f in factions.items() if f.get("alive", True)}
        if not living:
            return {"factions": {}, "narrative": "", "reviewed_count": 0}

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")

        # 构建势力经济摘要
        econ_summary = ""
        for fid, f in living.items():
            name = f.get("name", fid)
            troops = f.get("troops", 0)
            grain = f.get("grain", 0)
            treasury = f.get("treasury", 0)
            pop = f.get("population", 0)
            morale = f.get("realm_stability", f.get("morale", 50))
            tax_rate = f.get("tax_rate", 0.15)
            tile_count = f.get("tile_count", 0)

            # 人均粮
            grain_per_capita = grain / max(pop, 1) if pop > 0 else 0
            famine_risk = "高" if grain_per_capita < 0.5 else ("中" if grain_per_capita < 1.0 else "低")

            econ_summary += (
                f"{name}({fid}): 兵{troops} 粮{grain}(人均{grain_per_capita:.1f}石) "
                f"库{treasury}两 人口{pop} 民心{morale} 税率{tax_rate:.0%} "
                f"领地{tile_count}块 饥荒风险={famine_risk}\n"
            )

        prompt = (
            f"=== 元末逐鹿 经济结算审阅 ===\n"
            f"第{round_num}回合，{season}季\n\n"
            f"【势力经济状况】\n{econ_summary}\n"
            f"请审阅各方势力的经济状况，为每个势力给出微调建议：\n\n"
            f"1. tax_adjustment: 税率微调（-0.05到+0.05），\n"
            f"   - 国库空虚/战争在即 → 适当加税\n"
            f"   - 民心低/饥荒风险 → 适当减税\n"
            f"2. grain_policy: 粮食政策，三选一：\n"
            f"   - hoard(囤粮备战): 减少消耗、储备战粮\n"
            f"   - normal(正常): 维持现状\n"
            f"   - relief(赈灾): 开仓放粮、稳定民心\n\n"
            f"输出格式（严格JSON，不要额外文字）：\n"
            f'{{"factions":{{"势力ID":{{"tax_adjustment":数字,"grain_policy":"hoard/normal/relief","reasoning":"理由"}}}},' 
            f'"narrative":"全局经济综述(150-200字古文)"}}'
        )

        try:
            from ..infra.llm_client.hunyuan_client import TencentHunyuanClient
            raw = await client.chat_strategy(
                prompt=prompt,
                world_json="{}",
                system_prompt=(
                    "你是元末乱世中的户部尚书，精通钱粮调度。"
                    "你审阅各方势力的经济状况后，给出审慎的微调建议。"
                    "调整必须有理有据，幅度不宜过大（±5%以内）。"
                    "输出必须是合法JSON格式。"
                ),
                temperature=0.4,  # 低温保证数值稳定
            )

            data = _extract_json(raw)
            if not data:
                logger.warning("结算审阅: LLM返回无法解析的JSON，跳过")
                return {"factions": {}, "narrative": raw[:200] if raw else "", "reviewed_count": 0}

            factions_out = data.get("factions", {})
            validated = {}
            for fid in living:
                if fid not in factions_out:
                    continue
                adj = factions_out[fid]
                tax_adj = adj.get("tax_adjustment", 0)
                grain_policy = adj.get("grain_policy", "normal")
                reasoning = adj.get("reasoning", "")[:80]

                # 边界校验
                tax_adj = max(-0.05, min(0.05, float(tax_adj)))
                if grain_policy not in ("hoard", "normal", "relief"):
                    grain_policy = "normal"

                validated[fid] = {
                    "tax_adjustment": round(tax_adj, 3),
                    "grain_policy": grain_policy,
                    "reasoning": reasoning,
                }

            logger.info(
                f"结算审阅: 已审阅 {len(validated)}/{len(living)} 个势力"
            )
            return {
                "factions": validated,
                "narrative": data.get("narrative", "")[:300],
                "reviewed_count": len(validated),
            }

        except Exception as e:
            logger.warning(f"结算审阅LLM调用失败: {e}")
            return {"factions": {}, "narrative": "", "reviewed_count": 0, "error": str(e)}

    @staticmethod
    def apply_adjustments(world_state: dict, review: dict) -> dict:
        """
        将审阅建议应用到世界状态（带边界验证）

        Args:
            world_state: 世界状态对象（会被原地修改）
            review: SettlementReview.review_all() 的返回值

        Returns:
            {"applied_count": int, "details": [...]}
        """
        factions_data = review.get("factions", {})
        if not factions_data:
            return {"applied_count": 0, "details": []}

        factions = world_state.get("factions", {})
        details = []

        for fid, adj in factions_data.items():
            faction = factions.get(fid)
            if not faction or not faction.get("alive", True):
                continue

            tax_adj = adj.get("tax_adjustment", 0)
            grain_policy = adj.get("grain_policy", "normal")
            reasoning = adj.get("reasoning", "")

            # 调整税率（严格边界）
            old_rate = faction.get("tax_rate", 0.15)
            new_rate = max(0.05, min(0.30, old_rate + tax_adj))
            faction["tax_rate"] = new_rate

            # 设置粮食策略
            old_grain_mult = faction.get("grain_consumption_mult", 1.0)
            if grain_policy == "hoard":
                faction["grain_consumption_mult"] = max(0.80, old_grain_mult - 0.05)
            elif grain_policy == "relief":
                # 赈灾：增加粮耗但提升民心趋势
                faction["grain_consumption_mult"] = min(1.20, old_grain_mult + 0.05)
                # 民心因赈灾微升
                if "realm_stability" in faction:
                    faction["realm_stability"] = min(100, faction["realm_stability"] + 2)

            details.append({
                "faction_id": fid,
                "name": faction.get("name", fid),
                "tax_rate": {"old": old_rate, "new": new_rate},
                "grain_policy": grain_policy,
                "reasoning": reasoning,
            })

        logger.info(f"结算审阅应用: 更新了 {len(details)} 个势力的经济参数")
        return {"applied_count": len(details), "details": details}


class CombatReview:
    """v4.3 战前态势分析 — 为重大战斗提供AI士气修正"""

    @staticmethod
    async def pre_battle_analysis(
        battle_context: dict,
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        战前态势分析，输出有界士气修正。

        仅在双方总兵力 > 500 时调用（小规模冲突不值得LLM分析）。

        Args:
            battle_context: {
                "attacker_faction": str,
                "defender_faction": str,
                "attacker_troops": int,
                "defender_troops": int,
                "terrain": str,
                "season": str,
                "attacker_general": str | None,
                "defender_general": str | None,
                "is_siege": bool,
                "fortification": int,
                "attacker_morale": int | None,
                "defender_morale": int | None,
            }
            world_state: 世界状态
            clients: LLM客户端

        Returns:
            {
                "attacker_morale_shift": int,  # -5 ~ +5
                "defender_morale_shift": int,  # -5 ~ +5
                "analysis": str,               # 态势分析文本（80-150字）
            }
        """
        atk_troops = battle_context.get("attacker_troops", 0)
        def_troops = battle_context.get("defender_troops", 0)
        total = atk_troops + def_troops

        if total < 500:
            return {"attacker_morale_shift": 0, "defender_morale_shift": 0, "analysis": ""}

        client = clients.get("enemy")
        if not client:
            return {"attacker_morale_shift": 0, "defender_morale_shift": 0, "analysis": ""}

        att_name = battle_context.get("attacker_name", "攻方")
        def_name = battle_context.get("defender_name", "守方")
        terrain = battle_context.get("terrain", "平原")
        season = battle_context.get("season", "春")
        is_siege = battle_context.get("is_siege", False)
        fort = battle_context.get("fortification", 0)
        atk_gen = battle_context.get("attacker_general", "未知")
        def_gen = battle_context.get("defender_general", "未知")
        atk_morale = battle_context.get("attacker_morale", 50)
        def_morale = battle_context.get("defender_morale", 50)

        battle_type = "围城战" if is_siege else "野战"
        fort_text = f" 城防{fort}级" if is_siege else ""

        prompt = (
            f"=== 战前态势分析 ===\n"
            f"【攻方】{att_name}，兵力{atk_troops}，将领{atk_gen}，士气{atk_morale}\n"
            f"【守方】{def_name}，兵力{def_troops}，将领{def_gen}，士气{def_morale}\n"
            f"【战场】{terrain}，{season}季，{battle_type}{fort_text}\n\n"
            f"请分析此战的态势，给出双方士气修正建议（-5到+5整数）：\n"
            f"- 考虑因素：地形优势、兵力对比、季节影响、将领能力、攻城/守城优劣势\n"
            f"- 正值=提振士气，负值=挫伤士气\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"attacker_morale_shift": 数字,"defender_morale_shift": 数字,'
            f'"analysis":"态势分析(100字内)"}}'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世中的军事幕僚，精通战前态势分析。"
                    "你客观评估双方优劣，给出合理的士气修正建议。"
                    "士气修正在-5到+5之间，不可过于极端。"
                ),
                temperature=0.45,
            )

            data = _extract_json(raw)
            if not data:
                return {"attacker_morale_shift": 0, "defender_morale_shift": 0, "analysis": raw[:150] if raw else ""}

            atk_shift = max(-5, min(5, int(data.get("attacker_morale_shift", 0))))
            def_shift = max(-5, min(5, int(data.get("defender_morale_shift", 0))))

            return {
                "attacker_morale_shift": atk_shift,
                "defender_morale_shift": def_shift,
                "analysis": data.get("analysis", "")[:200],
            }

        except Exception as e:
            logger.debug(f"战前态势分析失败: {e}")
            return {"attacker_morale_shift": 0, "defender_morale_shift": 0, "analysis": ""}

    @staticmethod
    def apply_morale_shift(battle_context: dict, analysis: dict) -> None:
        """
        将士气修正应用到战斗上下文（原地修改）

        Args:
            battle_context: 战斗上下文dict（会被修改，添加 morale_shift 字段）
            analysis: pre_battle_analysis() 的返回值
        """
        battle_context["attacker_morale_shift"] = analysis.get("attacker_morale_shift", 0)
        battle_context["defender_morale_shift"] = analysis.get("defender_morale_shift", 0)
        battle_context["pre_battle_analysis"] = analysis.get("analysis", "")


class DiplomacyReview:
    """v4.3 外交潜意识漂移 — LLM审阅所有势力对并提供关系微调"""

    @staticmethod
    async def review_all(
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        审阅所有势力之间的关系，生成有界态度漂移。

        Args:
            world_state: 完整世界状态
            clients: LLM客户端

        Returns:
            {
                "drifts": [
                    {"from": fid1, "to": fid2, "shift": int (-2~+2), "reason": str},
                    ...
                ],
                "narrative": str,
                "reviewed_pairs": int,
            }
        """
        client = clients.get("law", clients.get("advisor"))
        if not client:
            return {"drifts": [], "narrative": "", "reviewed_pairs": 0}

        factions = world_state.get("factions", {})
        relations = world_state.get("relations", {})
        living = {fid: f for fid, f in factions.items() if f.get("alive", True)}

        if len(living) < 2:
            return {"drifts": [], "narrative": "", "reviewed_pairs": 0}

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")

        # 收集所有势力对的关系状况
        pairs_summary = ""
        pair_keys = []
        faction_ids = sorted(living.keys())
        for i, fa in enumerate(faction_ids):
            for fb in faction_ids[i + 1:]:
                fa_name = living[fa].get("name", fa)
                fb_name = living[fb].get("name", fb)

                # 获取关系数据
                rel_key = f"{fa}:{fb}"
                rel_key_rev = f"{fb}:{fa}"
                rel = relations.get(rel_key) or relations.get(rel_key_rev) or {}
                attitude = rel.get("attitude", 0)
                stance = rel.get("stance", "neutral")
                recent_events = rel.get("recent_events", [])[-3:]

                event_text = ""
                for evt in recent_events:
                    event_text += f"  {evt.get('description', str(evt))[:60]}\n"

                pairs_summary += (
                    f"{fa_name}↔{fb_name}: 态度{attitude} 状态{stance}\n"
                    f"{event_text}"
                )
                pair_keys.append((fa, fb))

        prompt = (
            f"=== 元末逐鹿 外交关系审阅 ===\n"
            f"第{round_num}回合，{season}季\n\n"
            f"【势力对关系】\n{pairs_summary}\n"
            f"请审阅以上势力对的关系，为每个势力对给出态度微小漂移（-2到+2）：\n"
            f"- 正值=关系缓和/改善（近期友好互动、共同敌人、贸易往来）\n"
            f"- 负值=关系恶化（边界摩擦、势力消长引发警惕、猜忌）\n"
            f"- 0=维持现状\n\n"
            f"输出格式（严格JSON数组）：\n"
            f'[{{"from":"势力ID1","to":"势力ID2","shift":数字,"reason":"10字以内理由"}},...]'
        )

        try:
            raw = await client.chat_strategy(
                prompt=prompt,
                world_json="{}",
                system_prompt=(
                    "你是元末乱世中的外交分析官，洞察各方势力间的微妙关系变化。"
                    "你审阅各方关系后，给出审慎的细微态度漂移建议。"
                    "每次调整在-2到+2之间，必须有理有据。"
                    "输出必须是合法JSON数组。"
                ),
                temperature=0.4,
            )

            data = _extract_json(raw)
            if not data:
                # 可能是数组或对象
                import re as _re
                arr_match = _re.search(r'\[[\s\S]*\]', raw) if raw else None
                if arr_match:
                    try:
                        data = json.loads(arr_match.group())
                    except json.JSONDecodeError:
                        pass
                if not data or not isinstance(data, list):
                    logger.warning("外交审阅: LLM返回无法解析，跳过")
                    return {"drifts": [], "narrative": raw[:200] if raw else "", "reviewed_pairs": 0}

            validated = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                from_fid = item.get("from", "")
                to_fid = item.get("to", "")
                shift = item.get("shift", 0)
                reason = item.get("reason", "")[:30]

                if from_fid not in living or to_fid not in living:
                    continue
                if from_fid == to_fid:
                    continue

                shift = max(-2, min(2, int(shift)))

                validated.append({
                    "from": from_fid,
                    "to": to_fid,
                    "shift": shift,
                    "reason": reason,
                })

            logger.info(f"外交审阅: 审阅了 {len(validated)} 对关系")
            return {
                "drifts": validated,
                "narrative": raw[:200] if raw and not isinstance(data, list) else "",
                "reviewed_pairs": len(validated),
            }

        except Exception as e:
            logger.warning(f"外交审阅LLM调用失败: {e}")
            return {"drifts": [], "narrative": "", "reviewed_pairs": 0, "error": str(e)}

    @staticmethod
    def apply_drifts(world_state: dict, review: dict) -> dict:
        """
        将关系漂移应用到世界状态（原地修改）

        Args:
            world_state: 世界状态对象
            review: DiplomacyReview.review_all() 的返回值

        Returns:
            {"applied_count": int, "details": [...]}
        """
        drifts = review.get("drifts", [])
        if not drifts:
            return {"applied_count": 0, "details": []}

        relations = world_state.get("relations", {})
        details = []

        for drift in drifts:
            fa = drift["from"]
            fb = drift["to"]
            shift = drift["shift"]

            # 标准化关系键
            rel_key = f"{fa}:{fb}"
            rel_key_rev = f"{fb}:{fa}"

            rel = relations.get(rel_key) or relations.get(rel_key_rev)
            if not rel:
                continue

            old_attitude = rel.get("attitude", 0)
            new_attitude = max(-100, min(100, old_attitude + shift))
            rel["attitude"] = new_attitude

            details.append({
                "pair": f"{fa}↔{fb}",
                "shift": shift,
                "attitude": {"old": old_attitude, "new": new_attitude},
                "reason": drift.get("reason", ""),
            })

        logger.info(f"外交审阅应用: 更新了 {len(details)} 对关系")
        return {"applied_count": len(details), "details": details}


class CombatStanceReview:
    """v4.3 战斗态势审阅 — 每回合审阅所有势力的军事态势，输出下回合士气修正"""

    @staticmethod
    async def review_all(
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        审阅所有势力的军事态势，为下回合战斗输出士气修正。

        Args:
            world_state: 完整世界状态
            clients: LLM客户端

        Returns:
            {
                "stances": {faction_id: {"morale_shift": int (-5~+5), "stance": str, "reasoning": str}},
                "narrative": str,
                "reviewed_count": int,
            }
        """
        client = clients.get("law", clients.get("advisor"))
        if not client:
            return {"stances": {}, "narrative": "", "reviewed_count": 0}

        factions = world_state.get("factions", {})
        living = {fid: f for fid, f in factions.items() if f.get("alive", True)}
        if len(living) < 2:
            return {"stances": {}, "narrative": "", "reviewed_count": 0}

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")

        # 构建军事态势摘要
        military_summary = ""
        for fid, f in living.items():
            name = f.get("name", fid)
            troops = f.get("troops", 0)
            morale = f.get("realm_stability", f.get("morale", 50))
            recent_battles = f.get("recent_battles", 0)
            at_war = f.get("at_war", False)
            neighbors = f.get("neighbors", [])

            neighbor_threat = 0
            for nid in neighbors:
                nf = living.get(nid, {})
                if nf and nf.get("troops", 0) > troops * 1.3:
                    neighbor_threat += 1

            military_summary += (
                f"{name}({fid}): 兵{troops} 士气{morale} "
                f"近战{recent_battles}场 {'战争中' if at_war else '和平'} "
                f"邻国威胁={neighbor_threat}个\n"
            )

        prompt = (
            f"=== 元末逐鹿 军事态势审阅 ===\n"
            f"第{round_num}回合，{season}季\n\n"
            f"【各方军事态势】\n{military_summary}\n"
            f"请审阅各方势力的军事态势，为每个势力输出下回合战斗士气倾向（-5到+5）：\n"
            f"- 正值=士气高涨（近期胜仗、兵力优势、秋季攻势）\n"
            f"- 负值=士气低迷（连败、邻国威胁、冬季疲敝、粮草不足）\n"
            f"- 0=平常\n"
            f"另输出 stance: aggressive(进攻)/defensive(防守)/cautious(谨慎)\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"stances":{{"势力ID":{{"morale_shift":数字,"stance":"aggressive/defensive/cautious","reasoning":"15字内理由"}}}},' 
            f'"narrative":"全局军事综述(100-150字古文)"}}'
        )

        try:
            raw = await client.chat_strategy(
                prompt=prompt,
                world_json="{}",
                system_prompt=(
                    "你是元末乱世中的兵部尚书，洞察各方军事态势。"
                    "你客观评估各方战备状态和士气倾向，给出合理的判断。"
                    "士气修正在-5到+5之间，必须有军事依据。"
                    "输出必须是合法JSON格式。"
                ),
                temperature=0.4,
            )

            data = _extract_json(raw)
            if not data:
                logger.warning("战斗态势审阅: LLM返回无法解析，跳过")
                return {"stances": {}, "narrative": raw[:200] if raw else "", "reviewed_count": 0}

            stances_in = data.get("stances", {})
            validated = {}
            for fid in living:
                if fid not in stances_in:
                    continue
                s = stances_in[fid]
                shift = max(-5, min(5, int(s.get("morale_shift", 0))))
                stance = s.get("stance", "cautious")
                if stance not in ("aggressive", "defensive", "cautious"):
                    stance = "cautious"
                reasoning = s.get("reasoning", "")[:30]

                validated[fid] = {
                    "morale_shift": shift,
                    "stance": stance,
                    "reasoning": reasoning,
                }

            logger.info(f"战斗态势审阅: 审阅了 {len(validated)}/{len(living)} 个势力")
            return {
                "stances": validated,
                "narrative": data.get("narrative", "")[:300],
                "reviewed_count": len(validated),
            }

        except Exception as e:
            logger.warning(f"战斗态势审阅LLM调用失败: {e}")
            return {"stances": {}, "narrative": "", "reviewed_count": 0, "error": str(e)}

    @staticmethod
    def apply_stances(world_state: dict, review: dict) -> dict:
        """
        将战斗态势修正应用到世界状态

        Args:
            world_state: 世界状态对象
            review: CombatStanceReview.review_all() 的返回值

        Returns:
            {"applied_count": int, "details": [...]}
        """
        stances = review.get("stances", {})
        if not stances:
            return {"applied_count": 0, "details": []}

        factions = world_state.get("factions", {})
        details = []

        for fid, s in stances.items():
            faction = factions.get(fid)
            if not faction or not faction.get("alive", True):
                continue

            # 存储到下回合战斗使用的士气修正
            faction["combat_morale_shift"] = s.get("morale_shift", 0)
            faction["combat_stance"] = s.get("stance", "cautious")

            details.append({
                "faction_id": fid,
                "name": faction.get("name", fid),
                "morale_shift": s["morale_shift"],
                "stance": s["stance"],
                "reasoning": s.get("reasoning", ""),
            })

        logger.info(f"战斗态势审阅应用: 更新了 {len(details)} 个势力的战斗士气")
        return {"applied_count": len(details), "details": details}
