"""
统一圣旨自然语言引擎（3.2 重构版）

核心闭环流程：
1. 接收任意自然语言文本（白话/文言/长篇叙事）
2. 五类意图识别（单地操作/军事行动/外交/人事/国策/谋略问询）
3. 实体提取（势力ID、地块ID、人物、资源数值、约束条件）
4. 前置校验（领地权限、国库资源、行军路径、重复冗余）
5. 拆解为标准化指令队列
6. 信息缺失 → 古风文言弹窗提示补全
7. 支持批量解析、撤回作废、长篇战略分步拆解

与现有 edict_engine.py / nl_command_router.py 协同工作，不替代而是增强。
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
    build_preprocess_hint, parse_edict_locally, robust_json_parse,
    classify_edict, cn_num_to_int, get_edict_context,
)
from server.core.edict_engine import (
    AVAILABLE_ACTIONS, build_system_prompt, build_user_prompt,
    build_world_summary, validate_commands, call_ai_edict,
    execute_edict_commands,
)

logger = logging.getLogger("yuanmo.unified_edict")

# AI 战略推演全局开关（可通过环境变量覆盖）
import os as _os
USE_AI_SIMULATION = _os.environ.get("EDICT_AI_SIMULATION", "true").lower() != "false"
SIMULATION_MIN_CONFIDENCE = 0.3  # AI 推演最低置信度阈值


# ============================================================
# 意图分类 — 五大类 + 细分
# ============================================================

class EdictIntentCategory(str, Enum):
    """圣旨意图大类"""
    SINGLE_TILE = "single_tile"       # 单地块操作（征兵/屯田/筑城/赈灾/迁徙/工坊）
    MILITARY = "military"             # 跨地块军事行动（军团/出征/征伐/分路/断后）
    DIPLOMACY = "diplomacy"           # 外交交互（宣战/同盟/通商/纳贡/联姻）
    PERSONNEL = "personnel"           # 人事任免（提拔/贬谪/审讯/招安/皇子调度）
    NATIONAL_POLICY = "national_policy"  # 全局国策（赋税/律法/全域屯田/募兵）
    STRATEGIC_CONSULT = "strategic_consult"  # 谋略问询（向谋臣求取战略方案）
    MIXED = "mixed"                   # 混合指令
    CANCEL = "cancel"                 # 撤回/作废指令
    UNKNOWN = "unknown"


class EdictSubIntent(str, Enum):
    """细分操作意图"""
    # 单地块
    RECRUIT = "recruit"
    FARM = "farm"
    FORTIFY = "fortify"
    RELIEF = "relief"
    MIGRATE = "migrate"
    WORKSHOP = "workshop"
    BUILD = "build"
    DEVELOP = "develop"
    TRAIN = "train"
    # 军事
    MARCH = "march"
    FORM_LEGION = "form_legion"
    MULTI_ROUTE = "multi_route"
    REARGUARD = "rearguard"
    SCOUT = "scout"
    AMBUSH = "ambush"
    PLUNDER = "plunder"
    # 外交
    ALLIANCE = "alliance"
    WAR = "war"
    TRADE = "trade"
    TRIBUTE = "tribute"
    MARRIAGE = "marriage"
    VASSAL = "vassal"
    TRUCE = "truce"
    # 人事
    APPOINT = "appoint"
    DISMISS = "dismiss"
    PROMOTE = "promote"
    DEMOTE = "demote"
    INTERROGATE = "interrogate"
    RECRUIT_TALENT = "recruit_talent"
    PRINCE_DISPATCH = "prince_dispatch"
    ENFEOFF = "enfeoff"
    # 国策
    TAX_ADJUST = "tax_adjust"
    LAW_PROMULGATE = "law_promulgate"
    GLOBAL_FARM = "global_farm"
    GLOBAL_RECRUIT = "global_recruit"
    AMNESTY = "amnesty"
    MOVE_CAPITAL = "move_capital"
    CULTURAL = "cultural"
    SEA = "sea"
    MEDICAL = "medical"
    # 谋略
    ASK_STRATEGY = "ask_strategy"
    ASK_SITUATION = "ask_situation"
    # 元
    CANCEL_COMMAND = "cancel_command"


# 类别 → 子意图映射
CATEGORY_SUB_INTENTS: dict[EdictIntentCategory, list[EdictSubIntent]] = {
    EdictIntentCategory.SINGLE_TILE: [
        EdictSubIntent.RECRUIT, EdictSubIntent.FARM, EdictSubIntent.FORTIFY,
        EdictSubIntent.RELIEF, EdictSubIntent.MIGRATE, EdictSubIntent.WORKSHOP,
        EdictSubIntent.BUILD, EdictSubIntent.DEVELOP, EdictSubIntent.TRAIN,
    ],
    EdictIntentCategory.MILITARY: [
        EdictSubIntent.MARCH, EdictSubIntent.FORM_LEGION, EdictSubIntent.MULTI_ROUTE,
        EdictSubIntent.REARGUARD, EdictSubIntent.SCOUT, EdictSubIntent.AMBUSH,
        EdictSubIntent.PLUNDER,
    ],
    EdictIntentCategory.DIPLOMACY: [
        EdictSubIntent.ALLIANCE, EdictSubIntent.WAR, EdictSubIntent.TRADE,
        EdictSubIntent.TRIBUTE, EdictSubIntent.MARRIAGE, EdictSubIntent.VASSAL,
        EdictSubIntent.TRUCE,
    ],
    EdictIntentCategory.PERSONNEL: [
        EdictSubIntent.APPOINT, EdictSubIntent.DISMISS, EdictSubIntent.PROMOTE,
        EdictSubIntent.DEMOTE, EdictSubIntent.INTERROGATE, EdictSubIntent.RECRUIT_TALENT,
        EdictSubIntent.PRINCE_DISPATCH, EdictSubIntent.ENFEOFF,
    ],
    EdictIntentCategory.NATIONAL_POLICY: [
        EdictSubIntent.TAX_ADJUST, EdictSubIntent.LAW_PROMULGATE,
        EdictSubIntent.GLOBAL_FARM, EdictSubIntent.GLOBAL_RECRUIT,
        EdictSubIntent.AMNESTY, EdictSubIntent.MOVE_CAPITAL,
        EdictSubIntent.CULTURAL, EdictSubIntent.SEA, EdictSubIntent.MEDICAL,
    ],
    EdictIntentCategory.STRATEGIC_CONSULT: [
        EdictSubIntent.ASK_STRATEGY, EdictSubIntent.ASK_SITUATION,
    ],
}


# ============================================================
# 关键词增强模式库
# ============================================================

CATEGORY_KEYWORDS: dict[EdictIntentCategory, list[str]] = {
    EdictIntentCategory.SINGLE_TILE: [
        "征兵", "募兵", "招兵", "屯田", "开垦", "筑城", "加固", "城防",
        "赈灾", "赈济", "救灾", "迁徙", "移民", "工坊", "建造", "修建",
        "兴建", "开发", "训练", "操练", "买马", "购马",
    ],
    EdictIntentCategory.MILITARY: [
        "出兵", "进攻", "攻打", "征讨", "讨伐", "征伐", "出征", "行军",
        "编组", "军团", "分路", "两路", "三路", "多路", "合围", "夹击",
        "断后", "布防", "先锋", "前哨", "侦查", "刺探", "伏击", "设伏",
        "劫掠", "劫营", "起点", "终点", "途经", "路线",
    ],
    EdictIntentCategory.DIPLOMACY: [
        "宣战", "结盟", "联盟", "同盟", "通商", "贸易", "纳贡", "称臣",
        "联姻", "和亲", "停战", "求和", "议和", "休战", "附庸", "宗主",
        "遣使", "使臣", "盟约", "缔约", "远交近攻", "合纵连横",
    ],
    EdictIntentCategory.PERSONNEL: [
        "任命", "提拔", "升迁", "贬谪", "罢免", "撤职", "审讯", "审问",
        "招安", "招降", "收编", "皇子", "藩王", "分封", "调度", "调遣",
        "册封", "封赏", "恩赏", "大赦",
    ],
    EdictIntentCategory.NATIONAL_POLICY: [
        "赋税", "税率", "征税", "减税", "免税", "律法", "法令", "颁布",
        "国策", "全域", "全国", "全民", "天下", "改元", "迁都", "移都",
        "科举", "文教", "书院", "海策", "禁海", "开海", "医政", "防疫",
        "徭役", "修路", "水利", "河工",
    ],
    EdictIntentCategory.STRATEGIC_CONSULT: [
        "谋略", "战略", "计策", "方略", "局势", "大势", "天下形势",
        "如何", "怎么", "建议", "献策", "求策", "问策", "分析",
        "请教", "咨询", "推演",
    ],
}

CANCEL_KEYWORDS = [
    "撤回", "作废", "取消", "收回", "撤销", "废黜", "收回成命",
    "前旨作废", "收回前旨", "罢黜前令",
]


# ============================================================
# 实体提取
# ============================================================

@dataclass
class EdictEntity:
    """从圣旨文本中提取的实体"""
    faction_ids: list[str] = field(default_factory=list)
    tile_ids: list[str] = field(default_factory=list)
    character_names: list[str] = field(default_factory=list)
    numbers: dict[str, int] = field(default_factory=dict)  # 数值类型 → 值
    constraints: list[str] = field(default_factory=list)   # 约束条件文本
    raw_text: str = ""


def extract_edict_entities(text: str, world_state: dict) -> EdictEntity:
    """
    从圣旨文本中提取结构化实体。

    利用 edict_nlp 的已有能力 + 补充提取。
    """
    entity = EdictEntity(raw_text=text)

    # 1. 提取势力名称（使用现有 NLP）
    faction_names = extract_faction_names(text)
    factions = world_state.get("factions", {})
    for fid, f in factions.items():
        fname = f.get("name", "")
        if fname and fname in text:
            entity.faction_ids.append(fid)

    # 2. 提取地块ID（匹配 tiles 字典中的名称）
    tiles = world_state.get("tiles", {})
    for tid, t in tiles.items():
        tname = t.get("tile_name", "")
        if tname and tname in text:
            entity.tile_ids.append(tid)

    # 3. 提取数值（extract_numbers 返回 list[dict]，按 raw → value 存入）
    nums = extract_numbers(text)
    for item in nums:
        entity.numbers[item["raw"]] = item["value"]

    # 也直接匹配阿拉伯数字
    for m in re.finditer(r'(\d{1,6})\s*([人骑名匹两石件个支路])', text):
        val = int(m.group(1))
        unit = m.group(2)
        if unit in ('人', '名'):
            entity.numbers.setdefault('troops', val)
        elif unit == '骑':
            entity.numbers.setdefault('horses', val)
        elif unit in ('两',):
            entity.numbers.setdefault('silver', val)
        elif unit == '石':
            entity.numbers.setdefault('grain', val)
        elif unit == '路':
            entity.numbers.setdefault('routes', val)

    # 4. 提取约束条件
    constraint_hints = [
        r'(?:不可|不得|禁止|切勿|勿要|切莫)([^，。；\n]+)',
        r'(?:务必|必须|一定|确保)([^，。；\n]+)',
        r'(?:优先|首先|先)([^，。；\n]+)',
        r'(?:若|如|倘|如果)([^，。；\n]+)',
    ]
    for pattern in constraint_hints:
        for m in re.finditer(pattern, text):
            entity.constraints.append(m.group(0).strip())

    return entity


# ============================================================
# 意图分类器（加权关键词 + 结构特征）
# ============================================================

def classify_edict_intent(text: str, entity: EdictEntity) -> dict:
    """
    增强版圣旨意图分类。

    Returns:
        {
            "primary": EdictIntentCategory,
            "sub_intents": [EdictSubIntent, ...],
            "confidence": float (0-1),
            "all_scores": {category: score, ...},
        }
    """
    # 首先检查撤回
    if any(kw in text for kw in CANCEL_KEYWORDS):
        return {
            "primary": EdictIntentCategory.CANCEL,
            "sub_intents": [EdictSubIntent.CANCEL_COMMAND],
            "confidence": 0.95,
            "all_scores": {EdictIntentCategory.CANCEL: 1.0},
        }

    # 检查是否问句（谋略问询）
    if any(kw in text for kw in ["如何", "怎么", "请教", "献策", "求策", "问策", "分析形势"]):
        return {
            "primary": EdictIntentCategory.STRATEGIC_CONSULT,
            "sub_intents": [EdictSubIntent.ASK_STRATEGY],
            "confidence": 0.85,
            "all_scores": {EdictIntentCategory.STRATEGIC_CONSULT: 1.0},
        }

    # 加权计分
    scores: dict[EdictIntentCategory, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        total = 0.0
        matched = 0
        for kw in keywords:
            if kw in text:
                weight = min(len(kw), 4)
                total += weight
                matched += 1
        if total > 0:
            normalized = total / (len(text) ** 0.3 + 1)
            if matched >= 3:
                normalized *= 1.2
            scores[category] = normalized

    if not scores:
        # 利用 edict_nlp.classify_edict 的回退
        legacy = classify_edict(text)
        legacy_primary = legacy.get("primary", "内政")
        cat_map = {
            "军事": EdictIntentCategory.MILITARY,
            "内政": EdictIntentCategory.SINGLE_TILE,
            "外交": EdictIntentCategory.DIPLOMACY,
            "朝堂": EdictIntentCategory.PERSONNEL,
        }
        return {
            "primary": cat_map.get(legacy_primary, EdictIntentCategory.UNKNOWN),
            "sub_intents": [],
            "confidence": legacy.get("confidence", 0.3),
            "all_scores": {},
        }

    # 取最高分
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    primary = sorted_scores[0][0]
    best = sorted_scores[0][1]
    second = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    ratio = best / (best + second + 0.01)
    confidence = min(0.95, ratio * 0.9 + 0.05)

    # 检测混合意图
    is_mixed = second > best * 0.5 and len(scores) >= 2
    if is_mixed:
        primary = EdictIntentCategory.MIXED

    # 映射子意图
    sub_intents = []
    sub_keywords = {
        EdictSubIntent.RECRUIT: ["征兵", "募兵", "招兵", "扩军"],
        EdictSubIntent.FARM: ["屯田", "开垦", "垦荒"],
        EdictSubIntent.FORTIFY: ["筑城", "加固", "城防", "修墙"],
        EdictSubIntent.RELIEF: ["赈灾", "赈济", "救灾", "放粮"],
        EdictSubIntent.BUILD: ["建造", "修建", "兴建", "营造"],
        EdictSubIntent.DEVELOP: ["开发", "水利", "灌溉"],
        EdictSubIntent.MARCH: ["出兵", "进攻", "攻打", "征讨", "出征", "行军"],
        EdictSubIntent.FORM_LEGION: ["编组", "军团", "组建"],
        EdictSubIntent.MULTI_ROUTE: ["分路", "两路", "三路", "多路", "合围", "夹击"],
        EdictSubIntent.ALLIANCE: ["结盟", "联盟", "同盟"],
        EdictSubIntent.WAR: ["宣战", "开战"],
        EdictSubIntent.TRADE: ["通商", "贸易"],
        EdictSubIntent.TRIBUTE: ["纳贡", "称臣"],
        EdictSubIntent.MARRIAGE: ["联姻", "和亲"],
        EdictSubIntent.APPOINT: ["任命", "提拔", "升迁"],
        EdictSubIntent.DISMISS: ["贬谪", "罢免", "撤职"],
        EdictSubIntent.TAX_ADJUST: ["赋税", "税率", "征税", "减税"],
        EdictSubIntent.LAW_PROMULGATE: ["律法", "法令", "颁布"],
        EdictSubIntent.AMNESTY: ["大赦", "赦免"],
        EdictSubIntent.MOVE_CAPITAL: ["迁都", "移都"],
        EdictSubIntent.SCOUT: ["侦查", "刺探", "打探"],
        EdictSubIntent.AMBUSH: ["伏击", "设伏", "埋伏"],
        EdictSubIntent.PLUNDER: ["劫掠", "掠夺", "抢粮"],
    }
    for si, kws in sub_keywords.items():
        if any(kw in text for kw in kws):
            sub_intents.append(si)

    return {
        "primary": primary,
        "sub_intents": sub_intents,
        "confidence": round(confidence, 2),
        "all_scores": {k: round(v, 2) for k, v in sorted_scores},
    }


# ============================================================
# 前置校验器
# ============================================================

class EdictValidator:
    """
    前置校验器 — 在拆解指令前验证可行性。

    校验维度：
    1. 领地权限：目标地块是否属于玩家
    2. 资源校验：国库/粮草/军械/兵力余量
    3. 行军路径：连通性
    4. 重复冗余：同回合同类操作过滤
    """

    def __init__(self, world_state: dict, pending_commands: list = None):
        self.ws = world_state
        self.pending = pending_commands or []
        self.player_fid = world_state.get("player_faction_id", "")
        self.player = world_state.get("factions", {}).get(self.player_fid, {})
        self.tiles = world_state.get("tiles", {})
        # 构建地名→tile_id 映射（AI可能使用中文地名而非坐标ID）
        self._name_to_id: dict[str, str] = {}
        for tid, t in self.tiles.items():
            if isinstance(t, dict) and t.get("tile_name"):
                self._name_to_id[t.get("tile_name")] = tid

    def _resolve_tile_id(self, tile_id: str) -> str:
        """将可能的地名解析为实际tile_id（坐标格式）"""
        if not tile_id:
            return tile_id
        # 直接匹配坐标ID
        if tile_id in self.tiles:
            return tile_id
        # 尝试地名→ID映射
        if tile_id in self._name_to_id:
            return self._name_to_id[tile_id]
        # 模糊匹配（去除后缀如"路"、"府"等）
        for name, tid in self._name_to_id.items():
            if tile_id in name or name in tile_id:
                return tid
        # 无法解析，返回原始值（后续会报"地块不存在"）
        return tile_id

    def check_territory(self, tile_id: str) -> tuple[bool, str]:
        """检查地块归属"""
        resolved = self._resolve_tile_id(tile_id)
        tile = self.tiles.get(resolved)
        if not tile:
            return False, f"舆图中未见「{tile_id}」此地"
        if tile.get("faction_id") != self.player_fid:
            tile_name = tile.get("tile_name", resolved)
            return False, f"「{tile_name}」非我疆土，何以令之"
        return True, ""

    def check_resources(self, action: str, params: dict) -> tuple[bool, str]:
        """检查资源是否充足"""
        treasury = self.player.get("treasury", 0)
        grain = self.player.get("grain", 0)
        arms = self.player.get("arms", 0)

        cost_checks = {
            "recruit": lambda p: (
                p.get("amount", 0) * 3 <= treasury,
                f"府库银两不足（需{p.get('amount',0)*3}两，现有{treasury}两）"
            ),
            "build": lambda p: (
                800 <= treasury,
                f"银两不足（需800两以上，现有{treasury}两）"
            ),
            "develop": lambda p: (
                500 <= treasury,
                f"银两不足（需500两，现有{treasury}两）"
            ),
            "buy_horses": lambda p: (
                p.get("amount", 0) * 5 <= treasury,
                f"银两不足（需{p.get('amount',0)*5}两，现有{treasury}两）"
            ),
            "fortify": lambda p: (
                300 <= treasury,
                f"银两不足（需300两以上，现有{treasury}两）"
            ),
            "march": lambda p: (
                p.get("troops", 0) * 2 <= grain,
                f"粮草不足，行军需粮（缺{p.get('troops',0)*2 - grain}石）"
            ),
            "move_capital": lambda p: (
                3000 <= treasury and 500 <= grain,
                f"迁都耗费巨大（需银3000两、粮500石，现有银{treasury}两、粮{grain}石）"
            ),
        }

        checker = cost_checks.get(action)
        if checker:
            ok, msg = checker(params)
            return ok, msg
        return True, ""

    def check_path(self, from_tile: str, to_tile: str) -> tuple[bool, str]:
        """检查行军路径连通性（基础检查）"""
        if from_tile not in self.tiles:
            return False, f"出发地「{from_tile}」不明"
        if to_tile not in self.tiles:
            return False, f"目的地「{to_tile}」不明"
        # 基本连通检查：两地必须存在
        # 详细的路径查找由 round_engine 的 _resolve_march 处理
        return True, ""

    def check_duplicate(self, action: str, params: dict) -> tuple[bool, str]:
        """检查是否与待执行队列中的指令重复"""
        for cmd in self.pending:
            if cmd.get("action") == action:
                p = cmd.get("params", {})
                # 相同动作+相同目标 = 重复
                if action in ("recruit", "develop", "build", "fortify", "train_troops", "relief"):
                    if p.get("tile_id") == params.get("tile_id"):
                        return False, "此令与前旨重复，已自动合并"
                if action == "march":
                    if p.get("from_tile") == params.get("from_tile") and p.get("to_tile") == params.get("to_tile"):
                        return False, "此行军令与前旨重复，已自动合并"
                if action == "diplomacy":
                    if p.get("target_faction") == params.get("target_faction") and p.get("diplomacy_type") == params.get("diplomacy_type"):
                        return False, "此邦交令与前旨重复"
        return True, ""

    def validate_all(self, commands: list[dict]) -> list[dict]:
        """
        对一组指令做完整前置校验。
        
        Returns:
            [
                {
                    "command": {...},
                    "valid": bool,
                    "error": str,  # 古风文言错误信息
                    "warning": str,
                },
                ...
            ]
        """
        results = []
        for cmd in commands:
            action = cmd.get("action", "")
            params = cmd.get("params", {})
            errors = []
            warnings = []

            # 1. 领地校验（并解析地名→坐标ID）
            tile_id = params.get("tile_id") or params.get("from_tile")
            if tile_id and action not in ("march", "scout", "diplomacy", "spy", "plunder"):
                resolved = self._resolve_tile_id(tile_id)
                if resolved != tile_id:
                    # 回写解析后的坐标ID到params，确保后续执行正确
                    if "tile_id" in params:
                        params["tile_id"] = resolved
                    elif "from_tile" in params:
                        params["from_tile"] = resolved
                    cmd["original_tile_name"] = tile_id  # 保留原始名称用于日志
                ok, err = self.check_territory(resolved)
                if not ok:
                    errors.append(err)

            # 2. 资源校验
            ok, err = self.check_resources(action, params)
            if not ok:
                errors.append(err)

            # 3. 路径校验
            if action == "march":
                ok, err = self.check_path(
                    params.get("from_tile", ""),
                    params.get("to_tile", ""),
                )
                if not ok:
                    errors.append(err)

            # 4. 重复校验
            ok, err = self.check_duplicate(action, params)
            if not ok:
                warnings.append(err)

            results.append({
                "command": cmd,
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            })

        return results


# ============================================================
# 古风文言错误消息模板
# ============================================================

class EdictResponseFormatter:
    """将校验结果格式化为古风文言提示"""

    @staticmethod
    def format_validation_error(errors: list[str]) -> str:
        """格式化校验错误为文言提示"""
        if not errors:
            return ""

        templates = {
            "非我疆土": "启奏陛下：此地非我朝疆土，臣等不敢擅专。",
            "银两不足": "启奏陛下：府库空虚，银两不足以支应此令。",
            "粮草不足": "启奏陛下：仓廪不实，粮草难继此役。",
            "兵力不足": "启奏陛下：营中兵士不足，恐难成军。",
            "军械不足": "启奏陛下：军械短缺，难以武装新兵。",
            "重复指令": "启奏陛下：此令与前旨相重，臣已合并处置。",
            "路径不通": "启奏陛下：两地关山阻隔，行军难以直达。",
            "人口不足": "启奏陛下：此地人丁稀少，不宜再行征调。",
            "未知地块": "启奏陛下：舆图中未见此地，请陛下明示。",
            "未知势力": "启奏陛下：此势力名号未有所闻，请陛下核实。",
        }

        lines = ["【尚书省奏报】"]
        for err in errors:
            matched = False
            for key, template in templates.items():
                if key in err:
                    lines.append(f"  {template}")
                    matched = True
                    break
            if not matched:
                lines.append(f"  {err}")
        return "\n".join(lines)

    @staticmethod
    def format_missing_info(missing: dict) -> str:
        """
        格式化缺失信息提示。

        Args:
            missing: {"field": str, "hint": str, "example": str}
        """
        templates = {
            "tile_id": ("地块不明", "请陛下明示何地，如「应天」「大都」「汴梁」等"),
            "amount": ("数目未详", "请陛下示下数额，如「征兵三千」「拨银五百两」"),
            "target_faction": ("目标势力未明", "请陛下指明势力，如「向陈友谅宣战」「与方国珍结盟」"),
            "diplomacy_type": ("邦交之意未明", "请陛下明示是欲宣战、结盟、通商，抑或纳贡联姻"),
            "from_tile": ("出发地未明", "请陛下示下从何处出兵"),
            "to_tile": ("目的地未明", "请陛下示下征伐何处"),
            "building": ("建筑未明", "请陛下示下欲建何物，如「粮仓」「军械所」「马场」"),
        }

        lines = ["【尚书省请旨】", "臣等恭读圣意，然有以下不明之处，恳请陛下明示：", ""]
        for field, (title, hint) in templates.items():
            if field in missing:
                lines.append(f"  一、{title}")
                lines.append(f"     {hint}")
                if missing.get(f"{field}_example"):
                    lines.append(f"     示例：「{missing[f'{field}_example']}」")
                lines.append("")

        if not missing:
            lines.append("  圣意煌煌，臣等已尽数领会。")
        else:
            lines.append("  待陛下明示后，臣等即刻拟旨施行。")

        return "\n".join(lines)

    @staticmethod
    def format_success_summary(edict_text: str, classification: dict, cmd_count: int) -> str:
        """格式化成功解析的摘要"""
        primary_cn = {
            EdictIntentCategory.SINGLE_TILE: "地方治理",
            EdictIntentCategory.MILITARY: "军事征伐",
            EdictIntentCategory.DIPLOMACY: "邦交纵横",
            EdictIntentCategory.PERSONNEL: "人事调度",
            EdictIntentCategory.NATIONAL_POLICY: "国策大政",
            EdictIntentCategory.STRATEGIC_CONSULT: "谋略问策",
            EdictIntentCategory.MIXED: "综合施政",
            EdictIntentCategory.CANCEL: "撤回前旨",
            EdictIntentCategory.UNKNOWN: "待议",
        }

        primary = classification.get("primary", "UNKNOWN")
        cat_name = primary_cn.get(primary, primary.value if hasattr(primary, 'value') else str(primary))
        confidence = classification.get("confidence", 0)

        lines = ["【尚书省拟旨】", ""]
        lines.append(f"  圣意类别：{cat_name}")
        lines.append(f"  解析确度：{confidence:.0%}")
        lines.append(f"  拆解政令：{cmd_count} 条")
        lines.append("")
        lines.append(f"  圣旨原文：「{edict_text[:80]}{'…' if len(edict_text) > 80 else ''}」")
        lines.append("")
        lines.append("  臣等即刻拟旨，交付有司施行。")

        return "\n".join(lines)


# ============================================================
# 长篇战略分步拆解
# ============================================================

class StrategicDecomposer:
    """
    将长篇战略规划拆解为多回合分步指令。

    例如：
    "先征兵三千固守应天，次与方国珍结盟牵制陈友谅，待秋收后出师北伐"
    → 拆解为 3 步：当前回合（征兵固守）→ 下回合（结盟）→ 秋收后（北伐）
    """

    # 分步关键词及其回合偏移
    STEP_MARKERS = [
        (r'(?:先|首|第一|首先|当前|即刻)', 0),
        (r'(?:其次|而后|然后|接着|再|二|第二|随即)', 1),
        (r'(?:然后|第三步|三|第三|之后|继而)', 2),
        (r'(?:最后|终|最终|末|收官|四|第四)', 3),
        (r'(?:待|等到|待到|来年|明年|下回合|下回|秋收后|开春后)', 1),
        (r'(?:三年|五年|十年|数年|长期)', 5),
    ]

    @classmethod
    def decompose(cls, text: str) -> list[dict]:
        """
        拆解长文本为多步计划。

        Returns:
            [
                {"step": 0, "turn_offset": 0, "text": "第一步内容", "desc": "当前"},
                ...
            ]
        """
        # 简单分句策略
        sentences = re.split(r'[。；;；\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [{"step": 0, "turn_offset": 0, "text": text, "desc": "即刻施行"}]

        steps = []
        current_offset = 0
        current_texts = []

        for sent in sentences:
            matched_offset = None
            for pattern, offset in cls.STEP_MARKERS:
                if re.search(pattern, sent):
                    matched_offset = offset
                    break

            if matched_offset is not None and matched_offset != current_offset:
                # 保存当前步骤
                if current_texts:
                    desc_map = {0: "即刻施行", 1: "次回施行", 2: "后续施行", 3: "末步施行", 5: "长远规划"}
                    steps.append({
                        "step": len(steps),
                        "turn_offset": current_offset,
                        "text": "；".join(current_texts),
                        "desc": desc_map.get(current_offset, f"第{current_offset+1}步"),
                    })
                current_texts = [sent]
                current_offset = matched_offset
            else:
                current_texts.append(sent)

        # 保存最后一步
        if current_texts:
            desc_map = {0: "即刻施行", 1: "次回施行", 2: "后续施行", 3: "末步施行", 5: "长远规划"}
            steps.append({
                "step": len(steps),
                "turn_offset": current_offset,
                "text": "；".join(current_texts),
                "desc": desc_map.get(current_offset, f"第{current_offset+1}步"),
            })

        return steps


# ============================================================
# 统一圣旨处理管道
# ============================================================

async def process_unified_edict(
    edict_text: str,
    world_state: dict,
    world_state_obj=None,
    round_engine=None,
    llm_client=None,
    pending_commands: list = None,
    edict_history: list = None,
    use_ai: bool = True,
) -> dict:
    """
    统一圣旨处理管道（3.2 重构版）。

    单次调用完成：识别 → 提取 → 校验 → 拆解 → 执行/入队 全流程。

    Args:
        edict_text: 原始自然语言圣旨文本
        world_state: 游戏世界状态字典
        world_state_obj: WorldState 实例（用于直接执行）
        round_engine: RoundEngine 实例
        llm_client: LLM客户端
        pending_commands: 当前待执行指令队列
        edict_history: 历史圣旨记录
        use_ai: 是否使用 AI 解析

    Returns:
        {
            "original_text": str,
            "classification": {...},
            "entities": {...},
            "validation": [...],
            "commands": [...],
            "decomposed_steps": [...],      # 长文本拆解结果
            "ai_analysis": {...},           # AI 分析结果
            "execution": {...},             # 执行结果（如直接执行）
            "edict_language": str,          # 古风文言正式圣旨
            "error_prompt": str,            # 文言错误提示
            "missing_info": {...},          # 缺失信息
            "summary": str,
            "is_cancel": bool,             # 是否为撤回指令
            "needs_clarification": bool,    # 是否需要玩家补充信息
        }
    """
    result = {
        "original_text": edict_text,
        "classification": {},
        "entities": {},
        "validation": [],
        "commands": [],
        "decomposed_steps": [],
        "ai_analysis": {},
        "execution": {},
        "edict_language": "",
        "error_prompt": "",
        "missing_info": {},
        "summary": "",
        "is_cancel": False,
        "needs_clarification": False,
    }

    # 1. 实体提取
    entity = extract_edict_entities(edict_text, world_state)
    result["entities"] = {
        "faction_ids": entity.faction_ids,
        "tile_ids": entity.tile_ids,
        "numbers": entity.numbers,
        "constraints": entity.constraints,
    }

    # 2. 意图分类
    classification = classify_edict_intent(edict_text, entity)
    result["classification"] = {
        "primary": classification["primary"].value if hasattr(classification["primary"], 'value') else str(classification["primary"]),
        "sub_intents": [si.value for si in classification.get("sub_intents", [])],
        "confidence": classification["confidence"],
    }

    # 3. 处理撤回指令
    if classification["primary"] == EdictIntentCategory.CANCEL:
        result["is_cancel"] = True
        result["summary"] = "前旨已撤回，相关政令作废。"
        result["edict_language"] = f"奉天承运皇帝，诏曰：前旨收回，着各有司停止施行，以候后命。钦此。"
        return result

    # 4. 处理谋略问询 → 路由到谋臣
    if classification["primary"] == EdictIntentCategory.STRATEGIC_CONSULT:
        result["summary"] = "已将圣意转呈谋臣，静候献策。"
        result["edict_language"] = f"奉天承运皇帝，诏曰：朕欲问策于谋臣，着翰林院即刻召对。钦此。"
        result["needs_clarification"] = False
        # 标记需要额外调用 advisor
        result["route_to_advisor"] = True
        return result

    # 5. 长篇战略拆解
    if len(edict_text) > 150 or len(re.split(r'[。；;；\n]', edict_text)) > 3:
        result["decomposed_steps"] = StrategicDecomposer.decompose(edict_text)

    # 6. 信息缺失检测
    missing = {}
    sub_intents = classification.get("sub_intents", [])

    # 军事类需要目标
    if EdictSubIntent.MARCH in sub_intents and not entity.tile_ids:
        missing["to_tile"] = True
        missing["to_tile_example"] = "出兵三千攻打高邮"

    if EdictSubIntent.WAR in sub_intents and not entity.faction_ids:
        missing["target_faction"] = True
        missing["target_faction_example"] = "向陈友谅宣战"

    # 单地块操作需要地块
    tile_actions = [EdictSubIntent.RECRUIT, EdictSubIntent.FARM, EdictSubIntent.FORTIFY,
                    EdictSubIntent.RELIEF, EdictSubIntent.BUILD, EdictSubIntent.DEVELOP]
    if any(si in sub_intents for si in tile_actions) and not entity.tile_ids:
        missing["tile_id"] = True
        missing["tile_id_example"] = "在应天征兵三千"

    # 数值缺失
    if EdictSubIntent.RECRUIT in sub_intents and not entity.numbers.get("troops"):
        missing["amount"] = True
        missing["amount_example"] = "征兵三千"

    if missing:
        result["missing_info"] = missing
        result["needs_clarification"] = True
        result["error_prompt"] = EdictResponseFormatter.format_missing_info(missing)
        # 仍尝试本地解析
        if not use_ai:
            return result

    # 7. AI 解析 + 执行（4.0 增强：AI 战略推演管道优先）
    simulation_used = False
    commands = []
    invalid = []

    if use_ai and llm_client and USE_AI_SIMULATION:
        # ===== 新增：AI 战略推演管道（阶段1+2） =====
        try:
            from server.core.strategic_simulation import (
                simulate_strategic_consequences,
                SIMULATION_MIN_CONFIDENCE as _SIM_MIN_CONF,
            )

            logger.info(f"启用AI战略推演管道: {edict_text[:50]}...")
            strategic_plan = await simulate_strategic_consequences(
                edict_text=edict_text,
                world_state=world_state,
                llm_client=llm_client,
                edict_history=edict_history,
            )

            if strategic_plan.ai_confidence >= _SIM_MIN_CONF and strategic_plan.merged_commands:
                # 推演成功，使用 AI 推演结果
                simulation_used = True
                commands = strategic_plan.merged_commands

                # 富文本 AI 分析结果
                geo_summary = ""
                if strategic_plan.geopolitical_impacts:
                    geo_parts = []
                    for g in strategic_plan.geopolitical_impacts[:3]:
                        geo_parts.append(f"{g.faction_name}: {g.description[:40]}")
                    geo_summary = "；".join(geo_parts)

                risk_summary = ""
                if strategic_plan.risk_matrix:
                    high_risks = [r for r in strategic_plan.risk_matrix if r.impact in ("high", "critical")]
                    if high_risks:
                        risk_summary = f"⚠ 高风险项: {'; '.join(r.description[:30] for r in high_risks[:3])}"

                result["ai_analysis"] = {
                    "intent_analysis": strategic_plan.intent_understanding or strategic_plan.situation_analysis,
                    "narrative": strategic_plan.narrative or f"臣谨领圣意，已完成战略推演。共拟{len(strategic_plan.primary_plan)}步方案，当前回合即刻施行。",
                    "resource_assessment": strategic_plan.resource_assessment,
                    "edict_language": strategic_plan.edict_language,
                    "risk_warning": risk_summary,
                    "follow_up_suggestion": strategic_plan.follow_up_suggestion,
                    "summary": f"AI战略推演完成（置信度{strategic_plan.ai_confidence:.0%}），主方案{len(strategic_plan.primary_plan)}步，备选{len(strategic_plan.alternative_plans)}个",
                    "ai_generated": True,
                    "hybrid_mode": False,
                    "simulation_used": True,
                }
                # 附加推演详情
                result["simulation"] = {
                    "situation_analysis": strategic_plan.situation_analysis,
                    "key_observations": strategic_plan.key_observations,
                    "primary_plan_steps": [
                        {"step": s.step, "description": s.description, "expected_effect": s.expected_effect}
                        for s in strategic_plan.primary_plan
                    ],
                    "alternative_plans": [
                        {"narrative": strategic_plan.alternative_narratives[i] if i < len(strategic_plan.alternative_narratives) else "",
                         "steps": [{"description": s.description} for s in steps]}
                        for i, steps in enumerate(strategic_plan.alternative_plans)
                    ],
                    "risk_matrix": [
                        {"type": r.risk_type, "description": r.description,
                         "probability": r.probability, "impact": r.impact}
                        for r in strategic_plan.risk_matrix
                    ],
                    "overall_risk_level": strategic_plan.overall_risk_level,
                    "geopolitical_impacts": [
                        {"faction": g.faction_name, "reaction": g.reaction, "description": g.description}
                        for g in strategic_plan.geopolitical_impacts
                    ],
                    "consequence_analysis": strategic_plan.consequence_analysis,
                    "ai_confidence": strategic_plan.ai_confidence,
                    "resource_projection": {
                        "treasury": {"before": strategic_plan.resource_projection.treasury_before,
                                     "after": strategic_plan.resource_projection.treasury_after},
                        "grain": {"before": strategic_plan.resource_projection.grain_before,
                                  "after": strategic_plan.resource_projection.grain_after},
                        "troops": {"before": strategic_plan.resource_projection.troops_before,
                                   "after": strategic_plan.resource_projection.troops_after},
                    } if strategic_plan.resource_projection else None,
                    "deficit_warning": strategic_plan.resource_projection.deficit_warning if strategic_plan.resource_projection else "",
                }
                logger.info(
                    f"AI战略推演成功: 置信度{strategic_plan.ai_confidence:.0%}, "
                    f"主方案{len(strategic_plan.primary_plan)}步, "
                    f"指令{len(commands)}条"
                )
            else:
                # 推演置信度过低，降级到原管道
                logger.warning(
                    f"AI战略推演置信度过低({strategic_plan.ai_confidence:.0%})，"
                    f"降级到原有AI解析管道"
                )
                simulation_used = False

        except Exception as e:
            logger.error(f"AI战略推演失败，降级到原有管道: {e}", exc_info=True)
            simulation_used = False

    # 原有管道：AI 解析 或 本地解析（当推演未使用或不可用时）
    if not simulation_used:
        if use_ai and llm_client:
            try:
                ai_result = await call_ai_edict(
                    edict_text=edict_text,
                    world_state=world_state,
                    llm_client=llm_client,
                    edict_history=edict_history,
                    use_local_fallback=True,
                )
                result["ai_analysis"] = {
                    "intent_analysis": ai_result.get("intent_analysis", ""),
                    "narrative": ai_result.get("narrative", ""),
                    "resource_assessment": ai_result.get("resource_assessment", ""),
                    "edict_language": ai_result.get("edict_language", ""),
                    "risk_warning": ai_result.get("risk_warning", ""),
                    "follow_up_suggestion": ai_result.get("follow_up_suggestion", ""),
                    "summary": ai_result.get("summary", ""),
                    "ai_generated": ai_result.get("ai_generated", False),
                    "hybrid_mode": ai_result.get("hybrid_mode", False),
                }
                commands = ai_result.get("commands", [])
                invalid = ai_result.get("invalid_commands", [])

            except Exception as e:
                logger.error(f"统一圣旨AI解析失败: {e}", exc_info=True)
                # 降级到本地解析（增强版）
                local = parse_edict_locally(edict_text, world_state)
                commands = local.get("commands", [])
                invalid = []
                result["ai_analysis"] = {
                    "intent_analysis": f"AI服务暂不可用，以本地解析代行。{local.get('intent_analysis', '')}",
                    "narrative": local.get("narrative", ""),
                    "resource_assessment": local.get("resource_assessment", ""),
                    "edict_language": local.get("edict_language", f"奉天承运皇帝，诏曰：{edict_text}钦此。"),
                    "risk_warning": local.get("risk_warning", ""),
                    "follow_up_suggestion": local.get("follow_up_suggestion", ""),
                    "summary": local.get("summary", ""),
                    "ai_generated": False,
                    "hybrid_mode": False,
                }
                if local.get("strategic_analysis"):
                    result["simulation"] = local["strategic_analysis"]
                if local.get("edict_style"):
                    result["edict_style"] = local["edict_style"]
        else:
            # 纯本地解析（增强版：含文体选择、文言生成、资源评估、战略推演）
            local = parse_edict_locally(edict_text, world_state)
            commands = local.get("commands", [])
            invalid = []
            result["ai_analysis"] = {
                "intent_analysis": local.get("intent_analysis", "本地解析模式"),
                "narrative": local.get("narrative", ""),
                "resource_assessment": local.get("resource_assessment", ""),
                "edict_language": local.get("edict_language", f"奉天承运皇帝，诏曰：{edict_text}钦此。"),
                "risk_warning": local.get("risk_warning", ""),
                "follow_up_suggestion": local.get("follow_up_suggestion", ""),
                "summary": local.get("summary", ""),
                "ai_generated": False,
            }
            # 传递战略推演结果
            if local.get("strategic_analysis"):
                result["simulation"] = local["strategic_analysis"]
            if local.get("edict_style"):
                result["edict_style"] = local["edict_style"]

    result["edict_language"] = result["ai_analysis"].get("edict_language", "")

    # 8. 前置校验
    validator = EdictValidator(world_state, pending_commands)
    validation_results = validator.validate_all(commands)
    result["validation"] = validation_results

    # 收集错误
    all_errors = []
    for vr in validation_results:
        all_errors.extend(vr.get("errors", []))
    if all_errors:
        result["error_prompt"] = EdictResponseFormatter.format_validation_error(all_errors)

    # 只保留合法的指令
    valid_commands = [
        vr["command"] for vr in validation_results if vr["valid"]
    ]
    result["commands"] = valid_commands

    # 9. 直接执行（如果提供了 world_state_obj 和 round_engine）
    if world_state_obj is not None and round_engine is not None and valid_commands:
        try:
            execution = execute_edict_commands(
                commands=valid_commands,
                world_state_obj=world_state_obj,
                round_engine=round_engine,
            )
            result["execution"] = execution
        except Exception as e:
            logger.error(f"统一圣旨执行失败: {e}", exc_info=True)
            result["execution"] = {
                "executed": [],
                "failed": [{"reason": f"执行异常: {str(e)[:50]}"}],
                "total_executed": 0,
                "total_failed": 1,
            }

    # 10. 生成摘要
    cmd_count = len(valid_commands)
    result["summary"] = EdictResponseFormatter.format_success_summary(
        edict_text, classification, cmd_count
    )

    return result


# ============================================================
# 批量圣旨解析（多条连续文本）
# ============================================================

def split_multi_edict(text: str) -> list[str]:
    """
    将一段包含多条圣旨的文本拆分为独立圣旨列表。

    分隔标记：分号、换行、"另"、"又"、"再"、"此外"
    """
    # 尝试按明确分隔符拆分
    parts = re.split(r'(?:[;；]\s*(?=征兵|出兵|命|令|着|敕|与|向|在|对|大赦|迁都|赋税|律法|谋))', text)
    if len(parts) == 1:
        parts = re.split(r'\n{2,}', text)
    if len(parts) == 1:
        # 按"另命""又命""再命"拆分
        parts = re.split(r'(?:另|又|再|此外)(?:命|令|着)', text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 3]


async def batch_process_edicts(
    texts: list[str],
    world_state: dict,
    world_state_obj=None,
    round_engine=None,
    llm_client=None,
    pending_commands: list = None,
    use_ai: bool = True,
) -> dict:
    """
    批量处理多条圣旨。

    Returns:
        {
            "total": int,
            "processed": int,
            "results": [{...one edict result...}, ...],
            "merged_commands": [...],
            "summary": str,
        }
    """
    results = []
    all_commands = []
    # 复制一份 pending，避免修改外部引用，并在遍历中累积更新
    _pending = list(pending_commands) if pending_commands else []

    for i, text in enumerate(texts):
        r = await process_unified_edict(
            edict_text=text,
            world_state=world_state,
            world_state_obj=world_state_obj,
            round_engine=round_engine,
            llm_client=llm_client,
            pending_commands=_pending,
            use_ai=use_ai,
        )
        results.append(r)
        cmds = r.get("commands", [])
        all_commands.extend(cmds)
        for cmd in cmds:
            if cmd not in _pending:
                _pending.append(cmd)

    return {
        "total": len(texts),
        "processed": sum(1 for r in results if r.get("commands")),
        "results": results,
        "merged_commands": all_commands,
        "summary": f"共颁{len(texts)}道圣旨，拆解{len(all_commands)}条政令，即刻施行。",
    }
