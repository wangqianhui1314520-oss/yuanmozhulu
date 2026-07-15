"""
圣旨自然语言处理增强模块

提供圣旨文本的预处理、实体提取、智能补全和本地回退解析能力。
作为 edict_engine 的 NLP 层，提升 AI 解析准确率并确保离线可用。
"""
from __future__ import annotations
import json
import re
import logging
from typing import Optional, Union

logger = logging.getLogger("yuanmo.edict_nlp")

# ============================================================
# 中文数字转换
# ============================================================

CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000, "万": 10000,
    "廿": 20, "卅": 30, "卌": 40,
}

CN_DIGIT_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "叁": 3, "三": 3,
    "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def cn_num_to_int(text: str) -> Optional[int]:
    """将中文数字字符串转为整数，如 '三千' → 3000, '五百' → 500"""
    if not text:
        return None
    # 先尝试纯数字
    try:
        return int(text.replace(",", "").replace("，", ""))
    except ValueError:
        pass

    # 中文数字转换
    total = 0
    current = 0
    for ch in text:
        if ch in CN_DIGIT_MAP:
            current = CN_DIGIT_MAP[ch]
        elif ch in ("十", "百", "千", "万"):
            multiplier = CN_NUM_MAP[ch]
            if current == 0:
                current = 1
            if ch == "万":
                total = (total + current) * multiplier
                current = 0
            else:
                current *= multiplier
                total += current
                current = 0
        else:
            if current > 0:
                total += current
                current = 0
    total += current
    return total if total > 0 else None


# ============================================================
# 实体提取
# ============================================================

# 常见元末势力名 → 别名列表（按优先级排序，越具体越靠前）
# 优先级规则：长别名 > 短别名，含姓氏+名字的 > 仅姓氏的
# V3.0 已更新为九大势力新ID体系
FACTION_NAME_ALIASES: dict[str, list[str]] = {
    "朱元璋":   ["朱元璋", "朱重八", "洪武", "大明", "朱"],
    "陈友谅":   ["陈友谅", "陈汉", "陈"],
    "张士诚":   ["张士诚", "张九四", "张周", "张"],
    "方国珍":   ["方国珍", "方谷珍", "方"],
    "徐寿辉":   ["徐寿辉", "天完", "徐"],
    "明玉珍":   ["明玉珍", "大夏"],
    "王保保":   ["王保保", "扩廓帖木儿", "帖木儿", "保保"],
    "漠北诸部": ["漠北诸部", "漠北", "草原部落", "和林"],
    "刘福通":   ["刘福通", "韩林儿", "刘"],
    "朱文正":   ["朱文正"],
    "察罕帖木儿": ["察罕帖木儿", "察罕"],
    "元廷":     ["元廷", "元顺帝", "大都", "元"],
}

# 歧义别名→优先级分辨率（当短别名冲突时）
# 格式: { "短别名": {"context_keywords": [...], "prefer_faction": "xxx"} }
AMBIGUITY_RESOLVERS: dict[str, dict] = {
    "明": {
        "primary": "朱元璋",  # 默认指朱元璋的"大明"
        "contexts": {
            "明玉珍": "明玉珍",
            "明夏": "明玉珍",
            "大夏": "明玉珍",
            "四川": "明玉珍",
        },
    },
    "元": {
        "primary": "元廷",
        "contexts": {
            "察罕": "察罕帖木儿",
            "帖木儿": "王保保",
            "王保保": "王保保",
            "扩廓": "王保保",
            "漠北": "漠北诸部",
        },
    },
    "陈": {
        "primary": "陈友谅",
        "contexts": {
            "友定": "陈友谅",
        },
    },
}

# 单字别名（需要额外验证才能采纳）
SINGLE_CHAR_ALIASES = {"朱", "陈", "张", "方", "徐", "刘", "明", "元"}


def extract_numbers(text: str) -> list[dict]:
    """
    提取文本中的所有数字（含中文数字）
    Returns: [{"raw": "三千", "value": 3000, "span": (0, 2)}, ...]
    """
    results = []
    # 阿拉伯数字
    for m in re.finditer(r'(\d{1,6})', text):
        results.append({
            "raw": m.group(1),
            "value": int(m.group(1)),
            "span": m.span(),
        })

    # 中文数字组合
    cn_pattern = r'[一二两三四五六七八九][十百千万]?[一二两三四五六七八九]?(?:[十百千]?(?:[一二两三四五六七八九])?)?'
    for m in re.finditer(cn_pattern, text):
        raw = m.group()
        val = cn_num_to_int(raw)
        if val and val > 0:
            # 避免重复匹配（如 "一" 已作为阿拉伯数字匹配）
            overlap = any(abs(m.start() - r["span"][0]) < 2 for r in results)
            if not overlap:
                results.append({"raw": raw, "value": val, "span": m.span()})

    return sorted(results, key=lambda x: x["span"][0])


def extract_faction_names(text: str) -> list[str]:
    """
    从圣旨文本中提取提及的势力名，含歧义消解。

    策略：
    1. 优先匹配长别名（如"朱元璋" > "朱"）
    2. 单字别名需额外验证（如"陈"需配合"友谅"才分配给陈友谅）
    3. 歧义别名（如"明"→朱元璋/明玉珍）根据上下文消歧
    """
    found: list[str] = []
    matched_positions: set[int] = set()  # 已匹配的字符位置，避免重复

    # 第一遍：精确匹配全名/长别名（优先级最高）
    exact_matches: list[tuple[str, str, int, int]] = []  # (alias, faction, start, end)
    for faction_name, aliases in FACTION_NAME_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):  # 长优先
            if len(alias) <= 1:
                continue  # 跳过单字，留到第二遍
            idx = text.find(alias)
            while idx != -1:
                span_start, span_end = idx, idx + len(alias)
                # 检查是否与已有匹配重叠
                if not any(max(span_start, ms) < min(span_end, me)
                           for _, _, ms, me in exact_matches):
                    exact_matches.append((alias, faction_name, span_start, span_end))
                idx = text.find(alias, idx + 1)

    for _, faction_name, _, _ in exact_matches:
        if faction_name not in found:
            found.append(faction_name)

    # 第二遍：单字/歧义别名匹配（需消歧）
    for faction_name, aliases in FACTION_NAME_ALIASES.items():
        if faction_name in found:
            continue  # 已在第一遍中匹配
        for alias in sorted(aliases, key=len, reverse=True):
            if len(alias) > 1 or alias not in SINGLE_CHAR_ALIASES:
                continue
            idx = text.find(alias)
            while idx != -1:
                span_start, span_end = idx, idx + len(alias)
                # 检查重叠
                if any(max(span_start, ms) < min(span_end, me)
                       for _, _, ms, me in exact_matches):
                    idx = text.find(alias, idx + 1)
                    continue

                # 单字别名：需上下文确认
                if alias in AMBIGUITY_RESOLVERS:
                    resolver = AMBIGUITY_RESOLVERS[alias]
                    resolved = resolver.get("primary", faction_name)
                    # 检查上下文关键词
                    for ctx_kw, ctx_faction in resolver.get("contexts", {}).items():
                        if ctx_kw in text:
                            resolved = ctx_faction
                            break
                    if resolved not in found:
                        found.append(resolved)
                else:
                    if faction_name not in found:
                        found.append(faction_name)
                break  # 单字别名只匹配一次
            if faction_name not in found:
                idx = text.find(alias, idx + 1)
            else:
                break

    return found


def extract_action_intents(text: str) -> list[str]:
    """
    从圣旨文本中提取意图关键词，映射为可用操作类型（加权消歧版）。

    改进点：
    1. 按关键词长度加权，长关键词可信度更高
    2. 单字关键词需"交叉验证"（至少再匹配一个同领域关键词）
    3. 否定句式检测（"不要征兵" → 不触发 recruit）
    4. 常见同义词/口语化表达扩展
    """
    # 操作类型 → [(关键词, 权重), ...]
    # 权重：≥3字=3，2字=2，1字=-1（需交叉验证）
    ACTION_KEYWORDS: dict[str, list[tuple[str, int]]] = {
        "recruit": [
            ("征兵", 3), ("募兵", 3), ("扩军", 3), ("招兵", 3),
            ("增兵", 2), ("补充兵力", 3), ("招募", 2), ("扩充军队", 3),
            ("扩编", 2), ("征募", 2), ("招兵买马", 3), ("补充兵员", 3),
            ("拉壮丁", 2), ("增援", 2), ("补员", 2), ("扩充", 1),
        ],
        "train_troops": [
            ("训练", 3), ("操练", 3), ("练兵", 3), ("整训", 3),
            ("强化训练", 3), ("提升战力", 3), ("提高士气", 3),
            ("整军", 2), ("操演", 2), ("军备", 2), ("备战", 2),
            ("强化", 1), ("精锐", 1), ("加强军备", 3),
        ],
        "buy_horses": [
            ("买马", 3), ("购马", 3), ("购买战马", 3), ("购置马匹", 3),
            ("补充战马", 3), ("扩充马队", 3), ("采购马匹", 3),
            ("买战马", 3), ("购战马", 3),
        ],
        "march": [
            ("进攻", 3), ("攻打", 3), ("出兵", 3), ("征讨", 3), ("讨伐", 3),
            ("出征", 3), ("调兵", 2), ("进兵", 2), ("征伐", 3),
            ("占领", 2), ("攻取", 2), ("围攻", 2), ("攻占", 2),
            ("进军", 2), ("扑向", 1), ("拿下来", 2),
        ],
        "fortify": [
            ("加固城防", 3), ("加固城墙", 3), ("修筑工事", 3),
            ("城防", 2), ("防御工事", 3), ("修缮城墙", 3),
            ("加固", 2), ("坚壁", 2), ("高墙", 2), ("修城墙", 3),
            ("巩固城防", 3), ("筑城", 2), ("修缮", 2),
        ],
        "scout": [
            ("侦查", 3), ("侦察", 3), ("刺探军情", 3), ("侦探", 2),
            ("打探军情", 3), ("打探", 2), ("探明", 2), ("前哨", 2),
            ("探察", 2), ("探路", 2), ("了解敌情", 3),
        ],
        "develop": [
            ("屯田", 3), ("开垦", 3), ("垦荒", 3), ("兴修水利", 3),
            ("灌溉", 2), ("开渠", 2), ("发展农业", 3), ("开发", 2),
            ("垦殖", 2), ("拓荒", 2), ("修水利", 3), ("垦田", 2),
        ],
        "build": [
            ("建造", 3), ("修建", 3), ("兴建", 3), ("构筑", 3),
            ("建设", 2), ("营造", 3), ("盖", 1), ("造", 1),
        ],
        "relief": [
            ("赈灾", 3), ("赈济", 3), ("救济", 2), ("灾民", 2),
            ("开仓放粮", 3), ("开仓", 2), ("放粮", 2), ("抚恤", 2),
            ("安抚百姓", 3), ("救灾", 2), ("抚民", 2),
        ],
        "tax": [
            ("税", 1), ("征税", 3), ("赋税", 2), ("课税", 2),
            ("加税", 3), ("减税", 3), ("轻徭薄赋", 3), ("免税", 3),
            ("重税", 3), ("调整税率", 3), ("收税", 2), ("税赋", 2),
        ],
        "convict_labor": [
            ("徭役", 3), ("征发民夫", 3), ("征夫", 2), ("征调民夫", 3),
            ("民夫", 2), ("劳役", 2), ("征徭", 2),
        ],
        "cultural_policy": [
            ("文教", 2), ("科举", 3), ("书院", 3), ("修史", 3),
            ("兴学", 2), ("教化", 2), ("开科举", 3), ("办书院", 3),
        ],
        "sea_policy": [
            ("海", 1), ("水师", 3), ("海贸", 3), ("禁海", 3),
            ("开海", 3), ("航海", 2), ("港口", 2), ("船厂", 2),
            ("海军", 2), ("海防", 2), ("海禁", 3),
        ],
        "medical": [
            ("医", 1), ("疫", 1), ("瘟疫", 3), ("医药", 2),
            ("郎中", 2), ("治病", 2), ("防治疫情", 3), ("防疫", 2),
            ("医馆", 2),
        ],
        "diplomacy": [
            ("结盟", 3), ("联盟", 3), ("宣战", 3), ("开战", 2),
            ("求和", 2), ("和谈", 3), ("联姻", 3), ("和亲", 3),
            ("纳贡", 2), ("通商", 2), ("贸易", 2), ("同盟", 3),
            ("停战", 3), ("罢兵", 2), ("议和", 2), ("外交", 2),
        ],
        "spy": [
            ("间谍", 3), ("细作", 3), ("密探", 2), ("渗透", 2),
            ("潜伏", 2), ("谍报", 2), ("暗探", 2), ("派细作", 3),
            ("安插", 2), ("卧底", 2),
        ],
        "ambush": [
            ("伏击", 3), ("设伏", 3), ("埋伏", 3), ("截击", 2),
            ("伏兵", 2), ("打埋伏", 2),
        ],
        "plunder": [
            ("劫掠", 3), ("掠夺", 2), ("抢夺", 2), ("洗劫", 2),
            ("烧杀", 2), ("劫", 1), ("抢粮", 2), ("掳掠", 2),
        ],
        "enfeoff": [
            ("分封", 3), ("封赏", 2), ("封官", 2), ("任命", 2),
            ("册封", 3),
        ],
        "amnesty": [
            ("大赦", 3), ("赦免", 2), ("免罪", 2), ("开释", 2),
            ("免刑", 2), ("大赦天下", 3),
        ],
        "move_capital": [
            ("迁都", 3), ("移都", 3), ("更换都城", 3), ("徙都", 3),
            ("搬迁都城", 3), ("换都城", 2),
        ],
    }

    # 否定模式：这些词出现在关键词前表示否定
    NEGATION_PATTERNS = ["不要", "别", "勿", "切勿", "不可", "不能", "不得", "不许", "停止", "暂停",
                         "取消", "撤回", "暂缓"]

    text_lower = text

    # 收集所有候选匹配: (action, keyword, weight, position, length)
    candidates: list[tuple[str, str, int, int, int]] = []
    negated_spans: list[tuple[int, int]] = []  # 被否定的文本范围

    # 先检测否定区域
    for neg in NEGATION_PATTERNS:
        idx = text_lower.find(neg)
        while idx != -1:
            # 否定范围：从否定词之后到句子结束（。！？\n）
            rest = text_lower[idx + len(neg):]
            end_markers = [rest.find(c) for c in "。！？\n，,;；"]
            end_markers = [m for m in end_markers if m >= 0]
            neg_end = idx + len(neg) + (min(end_markers) if end_markers else len(rest))
            negated_spans.append((idx + len(neg), neg_end))
            idx = text_lower.find(neg, idx + 1)

    for action, kw_list in ACTION_KEYWORDS.items():
        for kw, weight in kw_list:
            idx = text_lower.find(kw)
            while idx != -1:
                kw_end = idx + len(kw)
                # 检查是否在被否定范围内
                negated = any(ns <= idx < ne for ns, ne in negated_spans)
                if not negated:
                    candidates.append((action, kw, weight, idx, len(kw)))
                idx = text_lower.find(kw, idx + 1)

    if not candidates:
        return []

    # 按位置排序，然后按权重/长度排序
    candidates.sort(key=lambda x: (x[3], -x[2], -x[4]))

    # 消歧：处理重叠匹配
    # 规则：长关键词优先；同位置取权重高的
    resolved: dict[str, tuple[int, int]] = {}  # action → (total_weight, position)

    for action, kw, weight, pos, length in candidates:
        if action in resolved:
            old_weight, old_pos = resolved[action]
            # 如果新匹配位置与已有匹配位置相近(<5字符)，合并权重
            if abs(pos - old_pos) < 5:
                resolved[action] = (max(old_weight, weight) + 1, old_pos)
            else:
                resolved[action] = (max(old_weight, weight), min(old_pos, pos))
        else:
            resolved[action] = (weight, pos)

    # 过滤低权重单字匹配（需交叉验证）
    # 单字关键词：-1权重，需同一领域有其他关键词匹配才采纳
    low_confidence = [a for a, (w, _) in resolved.items() if w <= 0]

    # 领域分组
    domain_groups = {
        "military": ["recruit", "train_troops", "buy_horses", "march", "fortify", "scout", "ambush", "plunder"],
        "civil": ["develop", "build", "relief", "tax", "convict_labor", "cultural_policy", "sea_policy", "medical"],
        "court": ["enfeoff", "amnesty", "move_capital"],
        "diplomacy_group": ["diplomacy"],
        "espionage": ["spy"],
    }

    domain_map = {}
    for domain, actions in domain_groups.items():
        for a in actions:
            domain_map[a] = domain

    # 过滤：低权重单字需同领域有其他匹配
    filtered = {}
    for action, (weight, pos) in resolved.items():
        if weight <= 0:
            domain = domain_map.get(action, "")
            # 检查同领域是否有其他匹配
            same_domain = [a for a in domain_groups.get(domain, [])
                           if a in resolved and resolved[a][0] > 0]
            if not same_domain:
                # 没有同领域确认 → 丢弃此匹配
                continue
        filtered[action] = (weight, pos)

    # 按出现位置排序
    sorted_actions = sorted(filtered.items(), key=lambda x: x[1][1])

    return [a for a, _ in sorted_actions]


def estimate_parameters(action: str, numbers: list[dict], text: str) -> dict:
    """
    根据提取的数字和上下文，智能估计操作参数。
    """
    params = {}

    if action in ("recruit", "train_troops"):
        # 取最大的数字作为征兵/训练数量
        if numbers:
            best = max(numbers, key=lambda n: n["value"])
            params["amount"] = min(best["value"], 5000)
        else:
            params["amount"] = 500  # 默认500

    elif action == "buy_horses":
        if numbers:
            best = max(numbers, key=lambda n: n["value"])
            params["amount"] = min(best["value"], 1000)
        else:
            params["amount"] = 100

    elif action == "march":
        if len(numbers) >= 1:
            params["troops"] = min(numbers[-1]["value"], 10000)
        else:
            params["troops"] = 1000

    elif action == "build":
        # 从文本中识别建筑类型
        building_map = {
            "粮仓": "granary", "军械所": "armory", "军械": "armory",
            "马场": "stable", "港口": "port", "医馆": "clinic",
            "农田": "farmland", "工坊": "workshop", "征兵营": "barracks",
            "烽燧": "beacon", "寺庙": "temple", "宗庙": "temple",
            "城墙": "wall", "码头": "dock",
        }
        for cn, en in building_map.items():
            if cn in text:
                params["building"] = en
                break
        if "building" not in params:
            params["building"] = "granary"  # 默认粮仓

    elif action == "develop":
        dev_map = {"水利": "water", "粮仓": "granary", "医馆": "clinic", "农田": "farmland", "屯田": "farmland"}
        for cn, en in dev_map.items():
            if cn in text:
                params["type"] = en
                break
        if "type" not in params:
            params["type"] = "farmland"

    elif action == "tax":
        if "重税" in text or "加税" in text or "增税" in text:
            params["tax_type"] = "heavy"
        elif "减税" in text or "轻税" in text or "免税" in text:
            params["tax_type"] = "light"
        else:
            params["tax_type"] = "normal"

    elif action == "diplomacy":
        if any(kw in text for kw in ["结盟", "联盟", "同盟"]):
            params["diplomacy_type"] = "alliance"
        elif any(kw in text for kw in ["宣战", "开战"]):
            params["diplomacy_type"] = "war"
        elif any(kw in text for kw in ["求和", "和谈", "停战"]):
            params["diplomacy_type"] = "truce"
        elif any(kw in text for kw in ["通商", "贸易"]):
            params["diplomacy_type"] = "trade"
        elif any(kw in text for kw in ["联姻", "和亲"]):
            params["diplomacy_type"] = "marriage"
        elif any(kw in text for kw in ["纳贡"]):
            params["diplomacy_type"] = "tribute"

    elif action == "spy":
        if any(kw in text for kw in ["刺杀", "暗杀"]):
            params["spy_action"] = "assassinate"
        elif any(kw in text for kw in ["破坏", "捣毁"]):
            params["spy_action"] = "sabotage"
        elif any(kw in text for kw in ["情报", "打探"]):
            params["spy_action"] = "intel"
        else:
            params["spy_action"] = "deploy"

    elif action == "convict_labor":
        if any(kw in text for kw in ["筑城", "修城", "城墙"]):
            params["project"] = "筑城"
        elif "修路" in text:
            params["project"] = "修路"
        else:
            params["project"] = "开渠"

    elif action == "cultural_policy":
        if "科举" in text:
            params["policy_type"] = "开科举"
        elif "书院" in text:
            params["policy_type"] = "兴书院"
        elif "修史" in text:
            params["policy_type"] = "修史书"
        else:
            params["policy_type"] = "开科举"

    elif action == "sea_policy":
        if any(kw in text for kw in ["水师", "海军", "建水师"]):
            params["policy_type"] = "建水师"
        elif any(kw in text for kw in ["禁海", "海禁"]):
            params["policy_type"] = "禁海"
        else:
            params["policy_type"] = "开海贸"

    elif action == "ambush" or action == "plunder":
        if numbers:
            params["troops"] = min(numbers[-1]["value"], 5000)
        else:
            params["troops"] = 500

    return params


# ============================================================
# 会话上下文管理器（多轮对话连贯性）
# ============================================================

class EdictContext:
    """
    圣旨多轮对话上下文管理器。

    追踪同一回合/跨回合的圣旨序列，提供：
    - 已颁布指令追踪：避免重复指令
    - 资源变动感知：对比初始资源和当前资源
    - 意图延续：支持"再来一次""加强一下"等指代性续令
    - 矛盾检测：新圣旨与上一条的冲突检测
    """

    __slots__ = (
        "_turn_buffer", "_turn_start_resources", "_last_intent",
        "_last_actions", "_intent_sequence",
    )

    def __init__(self):
        self._turn_buffer: list[dict] = []       # 当前回合已颁布的圣旨
        self._turn_start_resources: dict = {}    # 回合开始时的资源快照
        self._last_intent: str = ""              # 上一条圣旨的意图
        self._last_actions: list[str] = []       # 上一条圣旨触发的操作
        self._intent_sequence: list[str] = []    # 意图序列（用于模式识别）

    def record_edict(self, text: str, actions: list[str],
                     intent: str = "", summary: str = ""):
        """记录一条已颁布的圣旨"""
        entry = {
            "text": text,
            "actions": actions,
            "intent": intent,
            "summary": summary,
        }
        self._turn_buffer.append(entry)
        self._last_intent = intent
        self._last_actions = actions
        self._intent_sequence.append(intent or self._classify_quick(text))

    def snapshot_resources(self, treasury: int, grain: int, troops: int,
                           stability: int):
        """记录回合开始时的资源状态"""
        self._turn_start_resources = {
            "treasury": treasury, "grain": grain,
            "troops": troops, "stability": stability,
        }

    def is_duplicate(self, text: str) -> bool:
        """检测新圣旨是否与已有圣旨高度重复"""
        if not self._turn_buffer:
            return False
        # 字符级 Jaccard 相似度
        def _jaccard(a: str, b: str) -> float:
            sa, sb = set(a), set(b)
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)
        for entry in self._turn_buffer:
            sim = _jaccard(text.replace(" ", ""), entry["text"].replace(" ", ""))
            if sim > 0.75:
                return True
        return False

    def is_contradiction(self, text: str) -> str:
        """
        检测新圣旨是否与上一条矛盾。
        Returns: 矛盾描述字符串，无矛盾返回空字符串
        """
        if not self._last_actions:
            return ""
        # 常见矛盾模式
        contradictions = {
            ("march", "diplomacy"): "上一道圣旨涉及军事行动，新圣旨涉及外交——若为同一目标势力，可能矛盾",
            ("recruit", "tax"): "上一道圣旨征兵，新圣旨税政——若财政紧张可能冲突",
            ("plunder", "relief"): "上一道圣旨劫掠，新圣旨赈灾——民意导向矛盾",
            ("diplomacy", "march"): "上一道圣旨外交，新圣旨出兵——若为同一势力则矛盾",
        }
        new_actions = set(extract_action_intents(text))
        for (a1, a2), desc in contradictions.items():
            if a1 in self._last_actions and a2 in new_actions:
                return desc
            if a2 in self._last_actions and a1 in new_actions:
                return desc
        return ""

    def is_referential(self, text: str) -> bool:
        """检测是否为指代性续令（"再来""继续""加强一下"等）"""
        referential_markers = [
            "再来", "继续", "接着", "照旧", "同前", "如前",
            "加强一下", "再加", "再多", "继续做", "按上次",
            "照上一次", "跟之前一样", "维持", "追加",
        ]
        return any(m in text for m in referential_markers)

    def resolve_reference(self, text: str) -> str:
        """
        解析指代性续令，尝试还原为完整指令。
        例如：「再来一次」→ 返回上一条圣旨文本
        """
        if self._turn_buffer:
            last = self._turn_buffer[-1]
            # 如果有数量修饰词，追加到上一指令
            import re
            num_match = re.search(r'(\d+|[一二两三四五六七八九][十百千万]?)', text)
            if num_match:
                return f"{last['text']}，数量调整为{num_match.group()}"
            return last["text"]
        return text

    def build_context_hint(self) -> str:
        """构建上下文提示文本，用于追加到 AI prompt"""
        if not self._turn_buffer:
            return ""

        lines = ["## 📜 本回合已颁布圣旨（请避免重复）"]
        for i, entry in enumerate(self._turn_buffer[-5:], 1):
            actions_str = "、".join(entry["actions"][:5]) if entry["actions"] else "无操作"
            lines.append(
                f"{i}.「{entry['text'][:60]}」"
                f"→ 执行操作: {actions_str}"
            )
        lines.append("**请确保新解析的指令不与上述已执行指令重复。**")
        return "\n".join(lines)

    def get_intent_continuity(self) -> str:
        """
        分析连续意图模式，为 AI 提供策略连续性建议。
        """
        if len(self._intent_sequence) < 2:
            return ""
        recent = self._intent_sequence[-3:]
        patterns = {
            ("military", "military", "military"): "已连续三轮军事行动，建议关注内政民生",
            ("civil", "civil", "civil"): "已连续三轮内政建设，建议关注军备防务",
            ("civil", "military", "military"): "从内政转向军事，确保粮草储备充足",
            ("military", "civil", "civil"): "从军事转向内政，战后恢复期需赈灾抚民",
        }
        key = tuple(recent[:3])
        return patterns.get(key, "")

    def clear_turn(self):
        """清空本回合缓冲区（回合结束时调用）"""
        self._turn_buffer.clear()
        self._last_intent = ""
        self._last_actions = []
        # 保留意图序列（跨回合策略趋势分析用）

    @staticmethod
    def _classify_quick(text: str) -> str:
        """快速单分类（仅用于意图序列，不替代完整 classify_edict）"""
        cats = {
            "military": ["征兵", "出兵", "进攻", "攻打", "防御", "训练", "行军", "讨伐"],
            "civil": ["建造", "开发", "屯田", "税", "赈灾", "科举", "徭役"],
            "diplomacy": ["结盟", "宣战", "求和", "联姻", "通商", "纳贡"],
            "espionage": ["间谍", "细作", "密探", "情报", "渗透"],
        }
        for cat, kws in cats.items():
            if any(kw in text for kw in kws):
                return cat
        return "civil"

# 全局上下文实例（模块级单例）
_edict_context = EdictContext()


def get_edict_context() -> EdictContext:
    """获取全局圣旨上下文实例"""
    return _edict_context


# ============================================================
# JSON 修复
# ============================================================

def repair_json(text: str) -> Optional[str]:
    """
    尝试修复 AI 返回的损坏 JSON。
    处理常见问题：尾逗号、未闭合引号、中文引号混用等。
    """
    if not text:
        return None

    # 1. 清除 BOM 和零宽字符
    text = text.replace("\ufeff", "").replace("\u200b", "")

    # 2. 将中文引号替换为英文引号（但保留内容中的中文）
    json_str = text.strip()

    # 3. 修复尾逗号（对象和数组中）
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    # 4. 修复缺失引号的键名
    json_str = re.sub(r'(?<!\w)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_str)

    # 5. 尝试找到并提取完整的 JSON 对象
    # 找最后一个 } 并截断
    last_brace = json_str.rfind('}')
    if last_brace > 0:
        json_str = json_str[:last_brace + 1]

    # 找第一个 {
    first_brace = json_str.find('{')
    if first_brace > 0:
        json_str = json_str[first_brace:]

    return json_str if json_str else None


def robust_json_parse(text: str) -> dict:
    """
    多策略鲁棒 JSON 解析（3.1 增强版）。

    按优先级尝试：直接解析 → markdown代码块 → 平衡括号提取 → 修复后解析 → 分行键值对提取
    """
    strategies = []

    # 策略0: 直接解析
    strategies.append(lambda t: json.loads(t))

    # 策略1: markdown 代码块
    strategies.append(lambda t: json.loads(
        re.search(r'```(?:json)?\s*([\s\S]*?)```', t).group(1)
    ))

    # 策略2: 平衡括号提取（替代原来的贪婪 {[\s\S]*}）
    strategies.append(lambda t: json.loads(
        _extract_balanced_json(t)
    ))

    # 策略3: 修复后解析
    strategies.append(lambda t: json.loads(repair_json(t) or "{}"))

    # 策略4: 从混合文本中提取 JSON —— 尝试修复后再平衡提取
    strategies.append(lambda t: json.loads(
        _extract_balanced_json(repair_json(t) or t)
    ))

    for i, strategy in enumerate(strategies):
        try:
            result = strategy(text)
            if isinstance(result, dict) and result:
                return result
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue

    logger.warning(f"所有JSON解析策略均失败，原始文本前200字符: {text[:200]}")
    return {}


def _extract_balanced_json(text: str) -> str:
    """
    从文本中提取第一个平衡的 JSON 对象。

    使用栈式括号匹配，替代贪婪正则 {[\s\S]*}，
    正确处理嵌套对象和数组。
    """
    start = text.find('{')
    if start == -1:
        return "{}"

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return "{}"


# ============================================================
# 完整的本地圣旨解析器（AI 不可用时的回退）
# ============================================================

def parse_edict_locally(edict_text: str, world_state: dict) -> dict:
    """
    完全在本地解析圣旨（无 LLM 依赖，3.1 增强版）。

    增强：
    - 上下文感知：避免重复已颁布指令
    - 模糊匹配：单字关键词交叉验证 + 同义词扩展
    - 指代消解：支持"再来一次"等续令

    Returns:
        与 call_ai_edict 相同的返回格式
    """
    # 处理指代性续令
    original_text = edict_text
    try:
        if _edict_context.is_referential(edict_text):
            edict_text = _edict_context.resolve_reference(edict_text)
    except Exception as e:
        logger.debug(f"指代消解跳过: {e}")

    actions = extract_action_intents(edict_text)
    numbers = extract_numbers(edict_text)
    factions = extract_faction_names(edict_text)
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    tiles = world_state.get("tiles", {})
    player_tiles = {
        tid: t for tid, t in tiles.items()
        if t.get("faction_id") == player_fid
    }

    commands = []
    tile_ids = list(player_tiles.keys())

    if not actions:
        # 没有匹配到操作类型，尝试给出更友好的提示
        hint = "请使用明确的指令词，如「征兵三千」「出兵攻打陈友谅」「建造粮仓」等"
        # 尝试检测是否完全无法理解
        if len(edict_text.strip()) < 3:
            hint = "圣旨内容过短，请详细描述您的意图"
        elif "?" in edict_text or "？" in edict_text or "怎么" in edict_text or "如何" in edict_text:
            # 是提问而非指令
            return {
                "intent_analysis": f"检测到咨询性语句「{edict_text[:40]}」，非操作性指令。",
                "narrative": "陛下此问非圣旨也。若欲咨询天下大势或治国方略，可召见幕僚商议。",
                "resource_assessment": "",
                "edict_language": f"奉天承运皇帝，诏曰：{edict_text}钦此。",
                "commands": [],
                "invalid_commands": [],
                "risk_warning": "",
                "follow_up_suggestion": "如需颁布政令，请使用祈使句，如「征兵三千」「加固城防」",
                "summary": "问题性语句，未生成指令",
                "ai_generated": False,
                "raw_response": "[本地解析 - 咨询性语句]",
            }

        return {
            "intent_analysis": f"未能识别「{original_text[:30]}」的具体指令类型，{hint}",
            "narrative": "臣愚钝，未能领会圣意。请陛下明示。",
            "resource_assessment": "",
            "edict_language": f"奉天承运皇帝，诏曰：{original_text[:40]}...钦此。",
            "commands": [],
            "invalid_commands": [],
            "risk_warning": "",
            "follow_up_suggestion": hint,
            "summary": "圣旨未能解析为具体指令",
            "ai_generated": False,
            "raw_response": "[本地解析 - 无匹配操作]",
        }

    # 上下文消重：去除已颁布的同类指令
    try:
        if _edict_context._last_actions:
            actions = [a for a in actions if a not in _edict_context._last_actions or a in ("march", "diplomacy")]
    except Exception as e:
        logger.debug(f"上下文消重跳过: {e}")

    if not actions and _edict_context._last_actions:
        return {
            "intent_analysis": f"圣旨意图与上一条重复（{', '.join(_edict_context._last_actions)}），已自动合并",
            "narrative": f"臣谨奏：此旨与上一道圣旨同义，已合并执行，无需重复颁布。",
            "resource_assessment": "",
            "edict_language": f"奉天承运皇帝，诏曰：{original_text}钦此。",
            "commands": [],
            "invalid_commands": [],
            "risk_warning": "",
            "follow_up_suggestion": "若需调整上一道圣旨的参数，请明确说明",
            "summary": "重复指令已合并",
            "ai_generated": False,
            "raw_response": "[本地解析 - 重复指令已合并]",
        }

    # 为每个识别的操作生成指令
    for action in actions:
        params = estimate_parameters(action, numbers, edict_text)
        cmd = {
            "action": action,
            "params": params,
            "reason": f"根据圣旨「{original_text[:30]}...」自动解析",
            "priority": "high" if action in ("march", "diplomacy") else "medium",
        }

        # 为需要 tile_id 的操作自动选择合适的地块
        if action in ("recruit", "train_troops", "fortify", "develop", "build", "relief",
                      "medical", "convict_labor", "ambush"):
            if tile_ids:
                best_tile = max(tile_ids, key=lambda tid: (
                    tiles[tid].get("troops", 0) + tiles[tid].get("population", 0)
                ))
                if action in ("recruit", "develop"):
                    params["tile_id"] = best_tile
                elif "tile_id" not in params:
                    params["tile_id"] = best_tile

        # 为 march/plunder 设置来源地块
        if action in ("march", "plunder"):
            if tile_ids:
                best_tile = max(tile_ids, key=lambda tid: tiles[tid].get("troops", 0))
                params["from_tile"] = best_tile

        # 为目标操作设置目标
        if action == "march":
            if factions:
                target_faction = factions[0]
                target_tiles = [tid for tid, t in tiles.items()
                                if any(alias in t.get("tile_name", "")
                                       for alias in FACTION_NAME_ALIASES.get(target_faction, []))]
                if target_tiles:
                    params["to_tile"] = target_tiles[0]
            if "to_tile" not in params and tile_ids:
                params["to_tile"] = tile_ids[0]

        if action == "diplomacy":
            if factions:
                params["target_faction"] = factions[0]
            else:
                continue

        if action == "spy":
            if factions:
                params["target_faction"] = factions[0]
            else:
                continue

        commands.append(cmd)

    # 去重
    seen_actions = set()
    deduped = []
    for cmd in commands:
        if cmd["action"] not in seen_actions:
            seen_actions.add(cmd["action"])
            deduped.append(cmd)
    commands = deduped

    # 类别描述
    category_map = {
        "recruit": "军事征兵", "train_troops": "军事训练", "buy_horses": "购买战马",
        "march": "军事行动", "fortify": "城防建设", "scout": "军事侦察",
        "develop": "内政开发", "build": "建筑营造", "relief": "赈灾抚民",
        "tax": "税政调整", "convict_labor": "徭役征发", "cultural_policy": "文教政策",
        "sea_policy": "海洋政策", "medical": "医政建设",
        "diplomacy": "外交行动", "spy": "谍报行动", "ambush": "军事伏击",
        "plunder": "军事劫掠", "enfeoff": "朝堂分封", "amnesty": "大赦天下",
        "move_capital": "迁都",
    }
    intent_parts = [category_map.get(a, a) for a in actions[:5]]
    intent_str = "、".join(intent_parts)

    if original_text != edict_text:
        intent_str += f"（续接上令：{original_text[:20]}）"

    edict_lang = f"奉天承运皇帝，诏曰：{original_text}钦此。"

    # 记录上下文
    try:
        _edict_context.record_edict(
            text=original_text,
            actions=actions,
            intent=intent_str,
            summary=f"本地解析：{intent_str}",
        )
    except Exception:
        pass

    return {
        "intent_analysis": f"识别到圣旨包含以下意图：{intent_str}（共{len(actions)}类操作，生成{len(commands)}条指令）",
        "narrative": f"臣谨领圣意，已拟就{len(commands)}条政令，请陛下御览。",
        "resource_assessment": f"当前府库银{player.get('treasury', 0)}两、粮{player.get('grain', 0)}石、兵力{player.get('total_troops', 0)}人",
        "edict_language": edict_lang,
        "commands": commands,
        "invalid_commands": [],
        "risk_warning": "（本地解析，请确认指令无误）" if len(commands) > 3 else "",
        "follow_up_suggestion": "下一回合可根据执行效果调整策略",
        "summary": f"圣旨已解析为{len(commands)}条政令：{intent_str}",
        "ai_generated": False,
        "raw_response": f"[本地解析 - 识别到{len(actions)}类操作]",
    }


# ============================================================
# 构建 AI 增强提示（预处理后提供给 AI）
# ============================================================

def build_preprocess_hint(edict_text: str, world_state: dict) -> str:
    """
    在发送给 AI 之前，预先提取关键信息作为提示（增强版：含多轮上下文）。

    这部分信息会追加到 user_prompt 中，帮助 AI 更准确地解析。
    """
    actions = extract_action_intents(edict_text)
    numbers = extract_numbers(edict_text)
    factions = extract_faction_names(edict_text)

    lines = ["## 🔍 预处理分析（辅助参考）"]

    if actions:
        lines.append(f"- 可能的操作类型: {', '.join(actions[:8])}")

    if numbers:
        num_parts = [f"{n['raw']}({n['value']})" for n in numbers[:5]]
        lines.append(f"- 提取到的数字: {', '.join(num_parts)}")

    if factions:
        lines.append(f"- 提及的势力: {', '.join(factions)}")

    # 智能建议
    player_fid = world_state.get("player_faction_id", "")
    player = world_state.get("factions", {}).get(player_fid, {})
    treasury = player.get("treasury", 0)
    grain = player.get("grain", 0)
    troops = player.get("total_troops", 0)
    stability = player.get("realm_stability", 50)

    suggestions = []
    if treasury < 1000 and any(a in actions for a in ["recruit", "build", "develop"]):
        suggestions.append("国库空虚，建议缩减开支规模")
    if grain < 500 and "march" in actions:
        suggestions.append("粮草不足，行军需谨慎（每格行军耗兵力×0.02粮草）")
    if troops < 500 and "march" in actions:
        suggestions.append("兵力薄弱，不宜贸然出征")
    if stability < 30 and "recruit" in actions:
        suggestions.append("民心低落，征兵将进一步降低民心")

    if suggestions:
        lines.append(f"- 智能提醒: {'; '.join(suggestions)}")

    # ---- 多轮上下文（来自 EdictContext） ----
    try:
        ctx = _edict_context

        # 检测重复
        if ctx.is_duplicate(edict_text):
            lines.append("- ⚠️ 警告：此圣旨与本回合已颁布圣旨高度相似，可能为重复指令")

        # 检测矛盾
        contradiction = ctx.is_contradiction(edict_text)
        if contradiction:
            lines.append(f"- ⚠️ 潜在矛盾：{contradiction}")

        # 当前回合已颁布的圣旨摘要
        ctx_hint = ctx.build_context_hint()
        if ctx_hint:
            lines.append(f"\n{ctx_hint}")

        # 意图连续性建议
        continuity = ctx.get_intent_continuity()
        if continuity:
            lines.append(f"\n💡 策略建议：{continuity}")

    except Exception:
        pass  # 上下文不可用不影响主流程

    return "\n".join(lines) if len(lines) > 1 else ""


# ============================================================
# 圣旨分类器（快速判断圣旨领域）
# ============================================================

def classify_edict(text: str) -> dict:
    """
    快速分类圣旨所属领域（增强版：加权词频 + 交叉验证）。

    Returns: {"primary": "military", "secondary": ["civil"], "confidence": 0.8}
    """
    # 领域关键词（每个关键词配权重：≥3字=3, 2字=2, 1字=-1需交叉验证）
    category_patterns: dict[str, list[tuple[str, int]]] = {
        "military": [
            ("征兵", 3), ("募兵", 3), ("出兵", 3), ("进攻", 3), ("攻打", 3),
            ("防御", 3), ("攻城", 3), ("守城", 3), ("训练", 2), ("战马", 3),
            ("出征", 3), ("行军", 3), ("将军", 2), ("军团", 2), ("劫掠", 3),
            ("伏击", 3), ("讨伐", 3), ("征伐", 3), ("占领", 3), ("攻取", 3),
            ("固守", 2), ("驻防", 2), ("围城", 2), ("扩军", 3), ("增兵", 2),
            ("买马", 3), ("购马", 3), ("骑兵", 2), ("整军", 2), ("备战", 2),
            ("动员", 2), ("集结", 2), ("士气", 2), ("战力", 2),
        ],
        "civil": [
            ("建造", 3), ("修建", 3), ("开发", 3), ("屯田", 3), ("赋税", 2),
            ("税收", 2), ("赈灾", 3), ("徭役", 2), ("科举", 3), ("文教", 2),
            ("民心", 2), ("粮仓", 2), ("水利", 2), ("道路", 2), ("工坊", 2),
            ("发展", 2), ("人口", 2), ("医馆", 2), ("瘟疫", 3), ("防疫", 2),
            ("海贸", 3), ("禁海", 3), ("水师", 3), ("船厂", 2), ("海策", 2),
            ("农田", 2), ("垦荒", 2), ("开渠", 2), ("灌溉", 2),
        ],
        "diplomacy": [
            ("结盟", 3), ("宣战", 3), ("求和", 3), ("联姻", 3), ("和亲", 3),
            ("贸易", 2), ("通商", 2), ("纳贡", 2), ("称臣", 2), ("合纵", 3),
            ("连横", 2), ("远交近攻", 3), ("同盟", 3), ("停战", 3), ("议和", 3),
            ("盟约", 2), ("遣使", 2), ("出使", 2), ("外交", 2),
        ],
        "espionage": [
            ("间谍", 3), ("细作", 3), ("密探", 2), ("渗透", 2), ("情报", 2),
            ("刺杀", 3), ("暗杀", 3), ("破坏", 2), ("策反", 2), ("侦查", 2),
            ("刺探", 2), ("卧底", 2), ("潜伏", 2), ("谍报", 2),
        ],
        "court": [
            ("分封", 3), ("大赦", 3), ("迁都", 3), ("封赏", 2), ("册封", 3),
            ("任命", 2), ("免罪", 2), ("赦免", 2), ("恩科", 2), ("赐爵", 2),
        ],
    }

    # 第一遍：计算每个领域的加权分数
    scores: dict[str, float] = {}
    matched_details: dict[str, list[str]] = {}  # 记录匹配到的关键词

    for category, kw_list in category_patterns.items():
        total = 0.0
        matched = []
        for kw, weight in kw_list:
            if kw in text:
                total += weight
                matched.append(kw)
        if total > 0:
            scores[category] = total
            matched_details[category] = matched

    if not scores:
        return {"primary": "civil", "secondary": [], "confidence": 0.25}

    # 第二遍：交叉验证 —— 相邻领域如果有共同关键词，调整分数
    # 例如 "刺探" 同时触发 espionage 和 military→scout，应增强两者
    for cat in list(scores.keys()):
        if len(matched_details.get(cat, [])) >= 2:
            scores[cat] *= 1.1  # 多个关键词确认 → 小幅加成

    # 排序
    sorted_cats = sorted(scores.items(), key=lambda x: -x[1])
    primary = sorted_cats[0][0]
    secondary = [cat for cat, score in sorted_cats[1:3] if score >= 1.5]
    # 置信度 = 最高分 / (平均分带衰减)
    max_score = sorted_cats[0][1]
    avg_other = (sum(s for _, s in sorted_cats[1:]) / max(1, len(sorted_cats) - 1)) if len(sorted_cats) > 1 else 0
    # 区分度越高 → 置信度越高
    confidence = min(0.95, max_score / (max_score + avg_other * 0.5 + 1))
    confidence = max(0.3, confidence)

    return {"primary": primary, "secondary": secondary, "confidence": round(confidence, 2)}
