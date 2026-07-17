"""
v4.3 世界叙事引擎 — 纯LLM叙事驱动，零游戏机制影响

三个子系统：
1. CourtDebateEngine  — 朝堂廷议：每势力模拟多派系朝堂辩论
2. PublicSentimentEngine — 市井舆情：全局街谈巷议/流言蜚语
3. GeneralChroniclesEngine — 将领列传：随机将领内心独白补遗

设计原则：
- 纯叙事生成，不修改任何游戏数值
- 输出存入 events_log 供前端展示
- 异步并发，异常降级，不阻塞回合
"""
from __future__ import annotations
import json
import logging
import re
import random
from typing import Optional

logger = logging.getLogger("yuanmo.agent.world_narrative")


def _extract_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.debug(f"JSON解析失败(首轮): {str(e)[:120]}")
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            logger.debug(f"JSON解析失败(正则提取后仍失败): {str(e)[:120]}")
    return None


# ============================================================
# 1. 朝堂廷议引擎
# ============================================================

class CourtDebateEngine:
    """v4.3 朝堂廷议 — 每势力模拟多派系朝堂辩论（纯叙事）"""

    @staticmethod
    async def run_faction_debate(
        faction_id: str,
        faction_config: dict,
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        为单个势力生成朝堂廷议叙事

        Returns:
            {
                "faction_id": str,
                "ruler": str,
                "debate_topic": str,
                "factions_debating": [{"name": str, "stance": str, "argument": str}],
                "ruler_verdict": str,
                "round": int,
            }
        """
        client = clients.get("enemy")
        if not client:
            return {"faction_id": faction_id, "skipped": True, "reason": "no_llm"}

        faction = world_state.get("factions", {}).get(faction_id, {})
        ruler_name = faction_config.get("ruler_name", faction.get("name", faction_id))
        faction_name = faction.get("name", faction_id)

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")
        troops = faction.get("troops", 0)
        grain = faction.get("grain", 0)
        treasury = faction.get("treasury", 0)
        at_war = faction.get("at_war", False)
        morale = faction.get("realm_stability", faction.get("morale", 50))

        # 确定廷议主题
        if at_war and troops > 500:
            topic = "战守之策"
        elif grain < troops * 2 and troops > 100:
            topic = "粮草调度"
        elif treasury < 500 and troops > 300:
            topic = "国库空虚"
        elif morale < 40:
            topic = "民心安抚"
        else:
            topics = ["来年大计", "治水屯田", "选贤任能", "边防之策", "商贸通商"]
            topic = random.choice(topics)

        prompt = (
            f"【{faction_name}】朝堂之上，君主「{ruler_name}」召集群臣，"
            f"廷议「{topic}」。\n"
            f"时{season}，第{round_num}回合。\n"
            f"国力：兵{troops} 粮{grain} 库{treasury}两 民心{morale}\n"
            f"战事：{'是' if at_war else '否'}\n\n"
            f"请生成一场朝堂辩论，包含3位大臣的发言：\n"
            f"- 保守派1人（稳重守成）\n"
            f"- 激进派1人（锐意进取）\n"
            f"- 务实派1人（折衷权衡）\n"
            f"每位大臣发言50-80字古文，最后君主总结定策（30-50字）。\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"topic":"{topic}",'
            f'"advisors":[{{"name":"大臣名","faction":"保守/激进/务实","speech":"发言内容"}}],'
            f'"verdict":"君主的定策总结",'
            f'"atmosphere":"激烈/平和/沉闷"}}'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
            system_prompt=(
                f"你是元末乱世中{faction_name}朝廷的起居注官，"
                f"负责记录朝堂辩论。"
                f"你需模拟真实的朝堂氛围，各方大臣据理力争，"
                f"君主最后权衡定策。语言为古文风格。"
            ),
                temperature=0.7,
            )

            data = _extract_json(raw)
            if not data:
                return {
                    "faction_id": faction_id,
                    "ruler": ruler_name,
                    "debate_topic": topic,
                    "narrative": raw[:400] if raw else f"{ruler_name}与群臣商议{topic}。",
                    "round": round_num,
                }

            debate_narrative = f"【{faction_name}朝堂】{ruler_name}召集群臣，廷议「{data.get('topic', topic)}」。\n"
            for i, adv in enumerate(data.get("advisors", []), 1):
                debate_narrative += (
                    f"{adv.get('faction', '')}派 {adv.get('name', f'大臣{i}')}："
                    f"「{adv.get('speech', '')}」\n"
                )
            debate_narrative += f"\n{ruler_name}曰：「{data.get('verdict', '从长计议。')}」"

            return {
                "faction_id": faction_id,
                "ruler": ruler_name,
                "debate_topic": data.get("topic", topic),
                "narrative": debate_narrative[:600],
                "atmosphere": data.get("atmosphere", "平和"),
                "advisor_count": len(data.get("advisors", [])),
                "round": round_num,
            }

        except Exception as e:
            logger.debug(f"朝堂廷议 [{faction_name}] LLM失败: {e}")
            return {
                "faction_id": faction_id,
                "ruler": ruler_name,
                "debate_topic": topic,
                "narrative": f"【{faction_name}朝堂】{ruler_name}与群臣商议{topic}，各有陈词。",
                "round": round_num,
            }

    @staticmethod
    async def run_all(
        world_state: dict,
        faction_configs: dict,
        clients: dict,
        skip_faction_id: str = "",
    ) -> list[dict]:
        """为所有NPC势力并发生成朝堂廷议"""
        import asyncio

        factions_cfg = faction_configs.get("factions", {})
        living = {
            fid: cfg
            for fid, cfg in factions_cfg.items()
            if world_state.get("factions", {}).get(fid, {}).get("alive", True)
            and fid != skip_faction_id
        }

        if not living:
            return []

        async def _one(fid: str, cfg: dict):
            return await CourtDebateEngine.run_faction_debate(fid, cfg, world_state, clients)

        tasks = [_one(fid, cfg) for fid, cfg in living.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                fid = list(living.keys())[i]
                logger.warning(f"朝堂廷议 [{fid}] 异常: {r}")
                cleaned.append({
                    "faction_id": fid,
                    "narrative": f"朝堂之上，群臣无言。",
                    "error": str(r),
                })
            else:
                cleaned.append(r)

        logger.info(f"朝堂廷议: 生成了 {len(cleaned)} 个势力的朝堂辩论")
        return cleaned


# ============================================================
# 2. 市井舆情引擎
# ============================================================

class PublicSentimentEngine:
    """v4.3 市井舆情 — 每回合生成民间街谈巷议/流言蜚语（纯叙事）"""

    RUMOR_CATEGORIES = [
        "苛政民谣",     # 税收过重时的民间怨言
        "战乱流言",     # 战争时期的恐慌
        "祥瑞传闻",     # 祥瑞吉兆的民间解读
        "英雄传说",     # 对某势力的崇拜/畏惧
        "商贾消息",     # 物价、贸易路线的信息
        "天象解读",     # 老百姓对天灾的理解
    ]

    @staticmethod
    async def generate(
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        生成本回合市井舆情（3-5条流言）

        Returns:
            {
                "rumors": [{"text": str, "category": str, "related_faction": str}, ...],
                "atmosphere": str,  # 民间氛围
                "round": int,
            }
        """
        client = clients.get("enemy")
        if not client:
            return {"rumors": [], "atmosphere": "不明", "round": world_state.get("current_round", 0)}

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")
        disaster_index = world_state.get("disaster_index", 0)

        factions = world_state.get("factions", {})
        faction_summary = ""
        for fid, f in factions.items():
            if f.get("alive", True):
                faction_summary += (
                    f"  {f.get('name', fid)}: 兵{f.get('troops', 0)} "
                    f"领{f.get('tile_count', 0)} "
                    f"声望{f.get('reputation', 50)}\n"
                )

        wars = world_state.get("active_battles", []) or []
        war_text = ""
        for w in wars[:3]:
            war_text += f"  {w.get('attacker_name', '?')} vs {w.get('defender_name', '?')}\n"
        if not war_text:
            war_text = "  暂无大战\n"

        prompt = (
            f"=== 元末市井舆情 ===\n"
            f"{season}季，第{round_num}回合，灾厄{disaster_index}/20\n\n"
            f"【天下势力】\n{faction_summary}\n"
            f"【战事】\n{war_text}\n"
            f"请以民间说书人/酒肆客商的口吻，生成3-5条市井流言和民谣。\n"
            f"风格：贴近百姓生活，有烟火气，有真有假，口口相传的质感。\n"
            f"每条30-60字，古文白话混合。\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"rumors":[{{"text":"流言内容","category":"苛政民谣/战乱流言/祥瑞传闻/英雄传说/商贾消息/天象解读","related":"势力名"}}],'
            f'"atmosphere":"太平/紧张/恐慌/期待/麻木"}}'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末乱世中的民间说书人，游走于市井酒肆之间，"
                    "收集各地流言蜚语。你的叙述要有民间智慧，"
                    "有烟火气，有夸张渲染，也有朴素的洞察。"
                ),
                temperature=0.75,
            )

            data = _extract_json(raw)
            if not data:
                return {
                    "rumors": [{"text": raw[:200] if raw else "市井之间，议论纷纷。", "category": "流言", "related": ""}],
                    "atmosphere": "不明",
                    "round": round_num,
                }

            rumors = data.get("rumors", [])
            validated = []
            for r in rumors[:5]:
                text = r.get("text", "")[:100] if isinstance(r, dict) else str(r)[:100]
                if text:
                    validated.append({
                        "text": text,
                        "category": r.get("category", "流言") if isinstance(r, dict) else "流言",
                        "related": r.get("related", "") if isinstance(r, dict) else "",
                    })

            logger.info(f"市井舆情: 生成了 {len(validated)} 条流言")
            return {
                "rumors": validated,
                "atmosphere": data.get("atmosphere", "不明"),
                "round": round_num,
            }

        except Exception as e:
            logger.warning(f"市井舆情生成失败: {e}")
            return {"rumors": [], "atmosphere": "不明", "round": round_num, "error": str(e)}


# ============================================================
# 3. 将领列传补遗引擎
# ============================================================

class GeneralChroniclesEngine:
    """v4.3 将领列传补遗 — 每回合随机选取将领生成内心独白（纯叙事）"""

    @staticmethod
    async def generate(
        world_state: dict,
        clients: dict,
    ) -> dict:
        """
        为本回合选取2-3位将领生成列传补遗/内心独白

        Returns:
            {
                "entries": [{"general_name": str, "faction": str, "narrative": str, "topic": str}, ...],
                "round": int,
            }
        """
        client = clients.get("enemy")
        if not client:
            return {"entries": [], "round": world_state.get("current_round", 0)}

        round_num = world_state.get("current_round", 0)
        season = world_state.get("current_season", "春")

        # 收集所有将领
        all_generals = []
        factions = world_state.get("factions", {})
        for fid, f in factions.items():
            if not f.get("alive", True):
                continue
            generals = f.get("generals", [])
            for g in generals:
                if isinstance(g, dict):
                    all_generals.append({
                        "name": g.get("name", "无名"),
                        "faction": f.get("name", fid),
                        "faction_id": fid,
                        "might": g.get("might", g.get("combat", 50)),
                        "intellect": g.get("intellect", g.get("strategy", 50)),
                        "loyalty": g.get("loyalty", 50),
                        "age": g.get("age", 35),
                    })

        if not all_generals:
            return {"entries": [], "round": round_num}

        # 随机选取2-3位将领
        selected = random.sample(all_generals, min(3, len(all_generals)))

        general_text = ""
        for g in selected:
            topics = [
                "对时局的感慨",
                "对主君的忠心与担忧",
                "对某场战役的回忆",
                "对未来的抱负",
                "内心的矛盾与挣扎",
                "对同僚的评价",
            ]
            topic = random.choice(topics)
            general_text += (
                f"{g['name']}（{g['faction']}势力，武{g['might']}智{g['intellect']}"
                f"忠{g['loyalty']}岁{g['age']}）— {topic}\n"
            )

        prompt = (
            f"=== 元末群雄 将领列传补遗 ===\n"
            f"{season}季，第{round_num}回合\n\n"
            f"【本回将领】\n{general_text}\n"
            f"请为每位将领撰写一段列传补遗或内心独白（每人60-100字古文），"
            f"仿《史记·列传》笔法，或为第一人称内心独白。\n"
            f"展现武将的个性、困境、抱负或内心挣扎。\n\n"
            f"输出格式（严格JSON数组）：\n"
            f'[{{"name":"将领名","topic":"主题","narrative":"列传内容"}},...]'
        )

        try:
            raw = await client.chat_fast(
                prompt=prompt,
                system_prompt=(
                    "你是元末明初的史官，为《元末群雄·列传》撰写补遗。"
                    "你深入将领内心，以《史记》列传笔法，"
                    "展现乱世武将的人性光辉与阴暗。"
                ),
                temperature=0.7,
            )

            entries = _extract_json(raw)
            if not entries or not isinstance(entries, list):
                # 尝试数组匹配
                arr_match = re.search(r'\[[\s\S]*\]', raw) if raw else None
                if arr_match:
                    try:
                        entries = json.loads(arr_match.group())
                    except json.JSONDecodeError:
                        pass

            if not entries or not isinstance(entries, list):
                return {
                    "entries": [
                        {"name": g["name"], "topic": "列传", "narrative": raw[:150] if raw else "乱世武将，各怀其志。"}
                        for g in selected
                    ],
                    "round": round_num,
                }

            validated = []
            for entry in entries[:3]:
                if isinstance(entry, dict):
                    validated.append({
                        "name": entry.get("name", "无名"),
                        "topic": entry.get("topic", "列传"),
                        "narrative": entry.get("narrative", "")[:200],
                    })

            logger.info(f"将领列传: 生成了 {len(validated)} 条补遗")
            return {"entries": validated, "round": round_num}

        except Exception as e:
            logger.warning(f"将领列传生成失败: {e}")
            return {"entries": [], "round": round_num, "error": str(e)}
