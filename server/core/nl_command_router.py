"""
自然语言指令路由器 - 统一NL操控所有AI模块（3.2 全链路AI智能体）

职责：
1. 自然语言解析：识别玩家指令意图（含增强关键词+正则匹配）
2. 智能路由：将NL指令分发到对应AI智能体
3. 多智能体协同：单条NL可触发多个AI协作
4. 与圣旨引擎无缝对接
"""
from __future__ import annotations
import logging
import re
from typing import Optional

from server.models.ai_protocol import (
    NLCommandRequest, NLCommandResult, AICommandSet, AICommand, CommandType,
    DelegationLevel, DelegationDomain, GameStateSnapshot,
)
from server.models.world_state import WorldState

logger = logging.getLogger("yuanmo.ai.nl_router")


class NLCommandRouter:
    """
    自然语言指令路由器
    
    玩家通过自然语言输入指令，路由器自动：
    1. 识别意图（军事/内政/外交/谍报/全局）
    2. 路由到对应AI智能体
    3. 收集各AI的回复和指令
    4. 生成统一叙事
    """

    # 意图关键词映射（增强版 —— 更丰富的模式匹配）
    INTENT_PATTERNS = {
        "military": [
            "进攻", "攻打", "出兵", "征讨", "讨伐", "行军", "出征",
            "征兵", "募兵", "扩军", "招兵", "训练", "操练",
            "防守", "固守", "坚守", "驻防", "驰援", "支援",
            "围城", "包围", "伏击", "设伏", "劫掠", "突袭",
            "将军", "武将", "军团", "调兵", "占领", "攻取",
            "买马", "购马", "战马", "骑兵", "马队",
            "侦查", "打探", "刺探", "先锋", "前哨",
            "备战", "动员", "集结", "整军", "军备",
            "精锐", "士气", "战力", "兵锋", "军威",
            "御敌", "御寇", "御侮", "靖难", "平定",
        ],
        "civil": [
            "建造", "修建", "兴建", "发展", "开发", "开垦", "屯田",
            "赈灾", "赈济", "税收", "征税", "赋税", "徭役",
            "农田", "粮仓", "军械所", "征兵营", "医馆", "工坊",
            "民心", "治安", "人口", "繁荣", "仓库",
            "国策", "政策", "文教", "科举", "书院", "修史",
            "水利", "灌溉", "河工", "水渠", "堤坝",
            "修路", "驿道", "商路", "码头", "驿站",
            "医政", "医药", "郎中", "防疫", "瘟疫",
            "海策", "海贸", "禁海", "水师", "船厂",
        ],
        "diplomacy": [
            "结盟", "联盟", "联合", "同盟", "宣战", "开战",
            "求和", "和谈", "纳贡", "称臣", "附庸",
            "联姻", "和亲", "贸易", "通商",
            "远交近攻", "合纵", "连横", "合纵连横",
            "遣使", "出使", "使臣", "盟约", "缔约",
            "停战", "休战", "罢兵", "议和",
        ],
        "espionage": [
            "细作", "间谍", "情报", "侦察", "打探",
            "渗透", "破坏", "谣言", "策反",
            "密探", "暗杀", "毒杀", "行刺",
            "卧底", "潜伏", "谍报", "耳目",
        ],
        "global": [
            "局势", "分析", "大势", "天下",
            "历史", "剧情", "锚点",
            "全委任", "半委任", "手动",
            "自动", "AI", "代理",
            "总览", "全局", "战略", "谋略",
        ],
    }

    # 中文数字正则（用于本地解析提取数量）
    CN_NUM_RE = re.compile(
        r'([一二两三四五六七八九][十百千万]?[一二两三四五六七八九]?(?:[十百千]?(?:[一二两三四五六七八九])?)?)'
    )
    ARABIC_NUM_RE = re.compile(r'(\d{1,6})')

    def __init__(self, world: WorldState):
        self.world = world

    # ============================================================
    # NL指令路由
    # ============================================================

    def route(self, request: NLCommandRequest) -> dict:
        """
        路由自然语言指令（增强版：加权计分+交叉验证消歧）。

        Returns:
            {
                "intent": str,
                "routed_agents": [str, ...],
                "category": str,
                "confidence": float,
            }
        """
        text = request.text
        scores: dict[str, float] = {}

        for category, keywords in self.INTENT_PATTERNS.items():
            total = 0.0
            matched_count = 0
            for kw in keywords:
                if kw in text:
                    # 按关键词长度加权：≥3字=3, 2字=2, 1字=1
                    weight = min(len(kw), 3)
                    total += weight
                    matched_count += 1
            if total > 0:
                # 基础分：加权总分 / (文本长度的对数 + 1)，防止短文本得分虚高
                normalized = total / (len(text) ** 0.3 + 1)
                # 多个关键词确认 → 加成
                if matched_count >= 3:
                    normalized *= 1.15
                scores[category] = normalized

        if not scores:
            return {
                "intent": "全局咨询",
                "routed_agents": ["A1", "A5", "A8"],
                "category": "global",
                "confidence": 0.3,
            }

        # 选择最高分，但如果第二高很接近 → 降低置信度
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        best_category = sorted_scores[0][0]
        best_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

        # 区分度 = 最高分 / (最高分 + 第二高分)
        ratio = best_score / (best_score + second_score + 0.01)
        confidence = min(0.95, ratio * 0.9 + 0.05)  # 映射到 [0.05, 0.95]

        # 多智能体路由
        agent_routes = self._get_agent_routes(best_category, text)

        intent_desc = {
            "military": "军事行动",
            "civil": "内政建设",
            "diplomacy": "外交纵横",
            "espionage": "谍报密探",
            "global": "全局谋略",
        }

        return {
            "intent": intent_desc.get(best_category, "综合"),
            "routed_agents": agent_routes,
            "category": best_category,
            "confidence": round(confidence, 2),
            "all_scores": {k: round(v, 2) for k, v in sorted_scores},
        }

    def _get_agent_routes(self, category: str, text: str) -> list[str]:
        """
        根据意图类别路由到对应智能体
        
        智能体映射:
        - 军事 → A2(君主AI) + 战术AI + 武将AI
        - 内政 → 文官AI + A1(谋臣)
        - 外交 → A6(外交署) + A1(谋臣)
        - 谍报 → A4(谍报司)
        - 全局 → A1(谋臣) + A5(事件) + A8(国史)
        """
        routes = {
            "military": ["faction_ai", "tactical_ai", "general_ai"],
            "civil": ["civil_ai", "A1"],
            "diplomacy": ["A6", "A1", "faction_ai"],
            "espionage": ["A4"],
            "global": ["A1", "A5", "A8"],
        }

        # 检查是否有跨领域关键词
        cross_agents = []
        if category != "civil" and any(kw in text for kw in ["民心", "国库", "粮草", "发展"]):
            cross_agents.append("civil_ai")
        if category != "military" and any(kw in text for kw in ["兵力", "进攻", "防守"]):
            if "faction_ai" not in routes.get(category, []):
                cross_agents.append("faction_ai")

        return routes.get(category, ["A1"]) + cross_agents

    # ============================================================
    # 指令本地解析（无LLM时的回退）
    # ============================================================

    def parse_locally(self, text: str, faction_id: str) -> AICommandSet:
        """
        本地解析自然语言为指令集（无LLM回退方案，增强版）。

        使用关键词+模糊匹配识别玩家意图，支持部分同义词变体。
        """
        commands = []

        # ---- 势力名模糊匹配辅助 ----
        def _find_faction_by_name(name_fragment: str) -> Optional[str]:
            """根据名称片段查找势力ID（模糊匹配）"""
            candidates = []
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.is_alive:
                    fname = faction.name
                    # 精确匹配
                    if name_fragment in fname or fname in name_fragment:
                        candidates.append((fid, 10))
                    # 单字匹配（如"陈"）
                    elif len(name_fragment) == 1 and name_fragment in fname:
                        candidates.append((fid, 5))
                    # 首个字符匹配
                    elif fname.startswith(name_fragment):
                        candidates.append((fid, 8))
            if candidates:
                candidates.sort(key=lambda x: -x[1])
                return candidates[0][0]
            return None

        # 军事指令
        if any(kw in text for kw in ["进攻", "攻打", "出兵", "征讨", "讨伐", "征伐", "占领", "攻取"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_attack_{fid}",
                        command_type=CommandType.MARCH,
                        faction_id=faction_id,
                        params={"target_faction": fid, "auto": True},
                        reason=f"遵旨讨伐{faction.name}",
                        priority=10,
                    ))
                    break
            else:
                # 没有匹配到势力名，尝试模糊匹配
                fid = _find_faction_by_name(text.split("攻打")[-1].strip() if "攻打" in text else
                                           text.split("进攻")[-1].strip() if "进攻" in text else "")
                if fid:
                    faction = self.world.factions.get(fid)
                    if faction:
                        commands.append(AICommand(
                            command_id=f"nl_attack_{fid}",
                            command_type=CommandType.MARCH,
                            faction_id=faction_id,
                            params={"target_faction": fid, "auto": True},
                            reason=f"遵旨讨伐{faction.name}",
                            priority=10,
                        ))

        if any(kw in text for kw in ["征兵", "募兵", "扩军", "招兵", "增兵", "补充兵力"]):
            match = re.search(r'(\d+)\s*[人骑名]', text)
            count = int(match.group(1)) if match else 500
            commands.append(AICommand(
                command_id="nl_recruit",
                command_type=CommandType.RECRUIT,
                faction_id=faction_id,
                params={"count": count, "auto": True},
                reason="奉旨募兵",
                priority=8,
            ))

        if any(kw in text for kw in ["买马", "购马", "补充战马"]):
            match = re.search(r'(\d+)\s*[匹]', text)
            count = int(match.group(1)) if match else 100
            commands.append(AICommand(
                command_id="nl_buy_horses",
                command_type=CommandType.BUY_HORSES,
                faction_id=faction_id,
                params={"count": count, "auto": True},
                reason="奉旨购马",
                priority=7,
            ))

        # 内政指令
        if any(kw in text for kw in ["建造", "修建", "兴建", "营造"]):
            for btype in ["granary", "armory", "barracks", "farmland", "clinic", "workshop",
                          "stable", "wall", "beacon", "temple", "dock"]:
                btype_cn = {
                    "granary": "粮仓", "armory": "军械所", "barracks": "征兵营",
                    "farmland": "农田", "clinic": "医馆", "workshop": "工坊",
                    "stable": "马场", "wall": "城墙", "beacon": "烽燧",
                    "temple": "宗庙", "dock": "码头",
                }
                if btype_cn.get(btype, btype) in text:
                    commands.append(AICommand(
                        command_id=f"nl_build_{btype}",
                        command_type=CommandType.BUILD,
                        faction_id=faction_id,
                        params={"building_type": btype, "auto": True},
                        reason=f"兴建{btype_cn.get(btype, btype)}",
                        priority=7,
                    ))
                    break

        if any(kw in text for kw in ["开发", "屯田", "开垦", "垦荒"]):
            commands.append(AICommand(
                command_id="nl_develop",
                command_type=CommandType.DEVELOP,
                faction_id=faction_id,
                params={"auto": True},
                reason="开发领地",
                priority=6,
            ))

        if any(kw in text for kw in ["赈灾", "赈济", "救灾", "放粮"]):
            commands.append(AICommand(
                command_id="nl_relief",
                command_type=CommandType.RELIEF,
                faction_id=faction_id,
                params={"auto": True},
                reason="开仓赈灾",
                priority=9,
            ))

        if any(kw in text for kw in ["加固", "城防", "筑城", "修墙"]):
            commands.append(AICommand(
                command_id="nl_fortify",
                command_type=CommandType.FORTIFY,
                faction_id=faction_id,
                params={"auto": True},
                reason="加固城防",
                priority=7,
            ))

        if any(kw in text for kw in ["训练", "操练", "练兵"]):
            match = re.search(r'(\d+)\s*[人]', text)
            count = int(match.group(1)) if match else 500
            commands.append(AICommand(
                command_id="nl_train",
                command_type=CommandType.TRAIN_TROOPS,
                faction_id=faction_id,
                params={"count": count, "auto": True},
                reason="整训军队",
                priority=7,
            ))

        # 外交指令
        if any(kw in text for kw in ["结盟", "联盟", "联合", "同盟"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_ally_{fid}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=faction_id,
                        params={"action": "alliance", "target_faction": fid},
                        reason=f"与{faction.name}结盟",
                        priority=9,
                    ))
                    break
            else:
                fid = _find_faction_by_name(text.split("结盟")[-1].strip() if "结盟" in text else
                                           text.split("联盟")[-1].strip())
                if fid:
                    faction = self.world.factions.get(fid)
                    if faction:
                        commands.append(AICommand(
                            command_id=f"nl_ally_{fid}",
                            command_type=CommandType.DIPLOMACY,
                            faction_id=faction_id,
                            params={"action": "alliance", "target_faction": fid},
                            reason=f"与{faction.name}结盟",
                            priority=9,
                        ))

        if any(kw in text for kw in ["宣战", "开战"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_war_{fid}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=faction_id,
                        params={"action": "war", "target_faction": fid},
                        reason=f"向{faction.name}宣战",
                        priority=10,
                    ))
                    break
            else:
                fid = _find_faction_by_name(text.split("宣战")[-1].strip() if "宣战" in text else
                                           text.split("开战")[-1].strip())
                if fid:
                    faction = self.world.factions.get(fid)
                    if faction:
                        commands.append(AICommand(
                            command_id=f"nl_war_{fid}",
                            command_type=CommandType.DIPLOMACY,
                            faction_id=faction_id,
                            params={"action": "war", "target_faction": fid},
                            reason=f"向{faction.name}宣战",
                            priority=10,
                        ))

        if any(kw in text for kw in ["求和", "和谈", "停战", "休战", "议和"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_truce_{fid}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=faction_id,
                        params={"action": "truce", "target_faction": fid},
                        reason=f"与{faction.name}议和",
                        priority=9,
                    ))
                    break

        if any(kw in text for kw in ["联姻", "和亲"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_marriage_{fid}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=faction_id,
                        params={"action": "marriage", "target_faction": fid},
                        reason=f"与{faction.name}联姻",
                        priority=8,
                    ))
                    break

        if any(kw in text for kw in ["通商", "贸易"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_trade_{fid}",
                        command_type=CommandType.DIPLOMACY,
                        faction_id=faction_id,
                        params={"action": "trade", "target_faction": fid},
                        reason=f"与{faction.name}通商",
                        priority=7,
                    ))
                    break

        # 谍报指令
        if any(kw in text for kw in ["间谍", "细作", "渗透", "密探"]):
            for fid, faction in self.world.factions.items():
                if fid != faction_id and faction.name and faction.name in text and faction.is_alive:
                    commands.append(AICommand(
                        command_id=f"nl_spy_{fid}",
                        command_type=CommandType.SPY,
                        faction_id=faction_id,
                        params={"action": "deploy", "target_faction": fid},
                        reason=f"向{faction.name}派遣密探",
                        priority=7,
                    ))
                    break

        # 伏击/劫掠
        if any(kw in text for kw in ["伏击", "设伏", "埋伏"]):
            commands.append(AICommand(
                command_id="nl_ambush",
                command_type=CommandType.AMBUSH,
                faction_id=faction_id,
                params={"auto": True},
                reason="设伏待敌",
                priority=8,
            ))

        if any(kw in text for kw in ["劫掠", "掠夺", "抢粮"]):
            commands.append(AICommand(
                command_id="nl_plunder",
                command_type=CommandType.PLUNDER,
                faction_id=faction_id,
                params={"auto": True},
                reason="奉旨劫掠",
                priority=8,
            ))

        # 朝堂指令
        if any(kw in text for kw in ["大赦", "赦免"]):
            commands.append(AICommand(
                command_id="nl_amnesty",
                command_type=CommandType.AMNESTY,
                faction_id=faction_id,
                params={},
                reason="大赦天下",
                priority=8,
            ))

        if any(kw in text for kw in ["迁都", "移都"]):
            commands.append(AICommand(
                command_id="nl_move_capital",
                command_type=CommandType.MOVE_CAPITAL,
                faction_id=faction_id,
                params={"auto": True},
                reason="奉旨迁都",
                priority=10,
            ))

        # 委任指令
        if "全委任" in text:
            commands.append(AICommand(
                command_id="nl_full_auto",
                command_type=CommandType.SET_POLICY,
                faction_id=faction_id,
                params={"delegation": "full_auto", "domains": ["civil", "military", "diplomacy", "espionage"]},
                reason="全权委任AI治理",
                priority=10,
            ))

        return AICommandSet(
            agent_type="nl_router",
            faction_id=faction_id,
            decision_summary=f"解析NL指令: {text[:80]}",
            commands=commands,
            risk_assessment="medium" if len(commands) > 3 else "low",
        )

    # ============================================================
    # 委任指令处理
    # ============================================================

    def parse_delegation_command(self, text: str, faction_id: str) -> dict:
        """
        解析委任指令（如"内政全委任""军事半委任"）
        
        Returns:
            {
                "domain": str,
                "level": str,
                "parsed": bool,
            }
        """
        domain_map = {
            "内政": "civil", "城建": "civil", "民生": "civil",
            "军事": "military", "战争": "military", "军队": "military",
            "外交": "diplomacy", "纵横": "diplomacy",
            "谍报": "espionage", "情报": "espionage", "细作": "espionage",
            "经济": "economy", "财政": "economy",
        }

        level_map = {
            "全委任": "full_auto", "全自动": "full_auto",
            "半委任": "semi_auto", "半自动": "semi_auto",
            "建议": "advisory", "推荐": "advisory",
            "手动": "full_manual", "亲自动手": "full_manual",
        }

        domain = None
        level = None

        for cn, en in domain_map.items():
            if cn in text:
                domain = en
                break

        for cn, en in level_map.items():
            if cn in text:
                level = en
                break

        if domain and level:
            return {"domain": domain, "level": level, "parsed": True}

        # 全局委任
        if any(kw in text for kw in ["全委任", "全自动", "AI代理", "AI治国"]):
            return {"domain": "all", "level": "full_auto", "parsed": True}

        if any(kw in text for kw in ["半委任", "半自动"]):
            return {"domain": "all", "level": "semi_auto", "parsed": True}

        return {"parsed": False}
