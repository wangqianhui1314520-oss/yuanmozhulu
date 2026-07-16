"""
Prompt 注册表 · 元末逐鹿 3.0
================================
集中管理所有 LLM Prompt，支持版本化、安全护栏、输出合约。

设计原则（基于 ai-prompt-engineering Skill）：
1. 每个 Prompt 有明确版本号和最后修改日期
2. 所有结构化输出 Prompt 包含 JSON Schema 约束
3. 安全护栏：注入检测、违规词过滤、输出长度限制
4. 上下文工程：System/User 分离、上下文优先级排序
5. 降级策略：LLM 不可用时的规则兜底

版本: 1.0.0
创建: 2026-07-16
"""

from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("yuanmo.llm.prompts")

# ============================================================
# 安全护栏 — 注入检测 & 违规词过滤
# ============================================================

# OWASP LLM Top 10: Prompt Injection 防护
INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?|constraints?)"
    r"|forget\s+(everything|all|your)\s+(instructions?|rules?|training)"
    r"|you\s+are\s+now\s+(a\s+)?(different|new|another)\s+(model|assistant|ai|bot|role)"
    r"|\[system\]|\[/system\]|<system>|</system>"
    r"|<\|\s*im_start\s*\|>|<\|\s*im_end\s*\|>)",
    re.IGNORECASE,
)

FORBIDDEN_TERMS = re.compile(
    r"(习近平|毛泽东|邓小平|江泽民|胡锦涛|共产党|中共|党中央|政治局|文革|六四|法轮功|台独|藏独|疆独)",
    re.IGNORECASE,
)


def sanitize_user_input(text: str, max_length: int = 2000) -> str:
    """净化用户输入：截断超长、标记注入、替换违规词"""
    if not text:
        return ""

    # 长度截断
    if len(text) > max_length:
        logger.warning(f"用户输入超长 ({len(text)} > {max_length})，已截断")
        text = text[:max_length] + "…"

    # 注入检测
    if INJECTION_PATTERNS.search(text):
        logger.warning("检测到疑似 Prompt Injection，已清理")
        text = INJECTION_PATTERNS.sub("[已过滤]", text)

    # 违规词替换
    if FORBIDDEN_TERMS.search(text):
        logger.warning("检测到违规词汇，已替换")
        text = FORBIDDEN_TERMS.sub("[已过滤]", text)

    return text


# ============================================================
# Prompt 版本注册
# ============================================================

@dataclass
class PromptVersion:
    """单个 Prompt 的版本信息"""
    name: str
    version: str
    updated: str  # ISO date
    description: str
    system_prompt: str = ""
    output_schema: Optional[dict] = None  # JSON Schema
    output_format_hint: str = ""  # 输出格式说明
    token_budget: int = 4096  # 预估 max_tokens
    temperature: float = 0.7
    fallback_response: str = ""  # LLM 不可用时的降级响应

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "updated": self.updated,
            "description": self.description,
        }


# ============================================================
# Prompt 注册表
# ============================================================

class PromptRegistry:
    """
    集中式 Prompt 注册表
    
    使用方式:
        registry = get_prompt_registry()
        prompt = registry.get("edict_parse")
        system = prompt.system_prompt.format(**vars)
    """

    _instance: Optional["PromptRegistry"] = None

    def __init__(self):
        self._prompts: dict[str, PromptVersion] = {}
        self._register_all()

    @classmethod
    def get_instance(cls) -> "PromptRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> Optional[PromptVersion]:
        return self._prompts.get(name)

    def list_all(self) -> list[dict]:
        return [p.to_dict() for p in self._prompts.values()]

    def _register_all(self):
        """注册所有 Prompt 版本"""
        self._register_edict_parse()
        self._register_global_deduction()
        self._register_ruler_decision()
        self._register_npc_chat()
        self._register_court_debate()
        self._register_spy_report()
        self._register_law_judge()
        self._register_event_narrative()
        self._register_history_record()

    # ================================================================
    # 1. 圣旨解析 Prompt（最关键的 Prompt）
    # ================================================================

    def _register_edict_parse(self):
        self._prompts["edict_parse"] = PromptVersion(
            name="edict_parse",
            version="2.0.0",
            updated="2026-07-16",
            description="自然语言圣旨 → 结构化政令指令（JSON）",
            temperature=0.3,  # 低温度确保输出稳定
            token_budget=4096,
            output_schema={
                "type": "object",
                "required": ["intent_analysis", "commands", "summary"],
                "properties": {
                    "intent_analysis": {"type": "string", "maxLength": 200},
                    "narrative": {"type": "string", "maxLength": 200},
                    "resource_assessment": {"type": "string", "maxLength": 150},
                    "edict_language": {"type": "string", "maxLength": 400},
                    "commands": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "required": ["action", "params", "reason", "priority"],
                            "properties": {
                                "action": {"type": "string"},
                                "params": {"type": "object"},
                                "reason": {"type": "string", "maxLength": 60},
                                "priority": {"enum": ["high", "medium", "low"]},
                            },
                        },
                    },
                    "risk_warning": {"type": "string", "maxLength": 60},
                    "follow_up_suggestion": {"type": "string", "maxLength": 80},
                    "summary": {"type": "string", "maxLength": 100},
                },
            },
            system_prompt="""你是元末乱世中的尚书省首辅兼翰林学士，精通六朝骈文与唐宋诏敕。
你的唯一使命：将君主的白话圣旨准确转换为结构化政令。

## 输出合约（最高优先级）
- 整个回复必须是纯 JSON 对象，禁止任何前言/后语/注释/Markdown 包装
- 必须包含全部字段：intent_analysis, narrative, resource_assessment, edict_language, commands, risk_warning, follow_up_suggestion, summary
- 无法解析/不合规时返回 {"error": "原因", "commands": []}

## 角色约束
- 你是执行者，不是决策者——忠实地将君主意图转化为可执行指令
- 你是顾问，不是君主——可提出风险警示，但不可擅自更改君主决策
- 你是古人，用文言文撰写圣旨正文

## 安全约束
- 只处理游戏内政令，拒绝任何非游戏指令
- 如圣旨包含现代词汇/政治敏感内容，回复：{"error": "不合规内容", "commands": []}
- 不输出任何与元末历史无关的内容

## 输出要求
- 必须是合法 JSON，不得有任何额外文字
- commands 数组非空（至少1条）
- 所有 action 必须来自预定义列表
- 数字参数必须是具体数值，不得用"若干""大量"等模糊词
- edict_language 必须按政令类别选文体（军事→敕曰、内政→令曰、恩赏→诰曰/制曰、外交宣战→诏曰、细作→密敕），严禁一律用"诏曰"
- 禁止用 ```json ``` 代码块包裹输出
- 禁止在 JSON 外输出任何文字""",

            fallback_response='{"intent_analysis":"无法解析圣旨","commands":[],"summary":"圣旨无法理解，请重新拟定","edict_language":"奉天承运皇帝，诏曰：圣意未明，着有司再议。钦此。"}',
        )

    # ================================================================
    # 2. 全局推演 Prompt
    # ================================================================

    def _register_global_deduction(self):
        self._prompts["global_deduction"] = PromptVersion(
            name="global_deduction",
            version="2.0.0",
            updated="2026-07-16",
            description="圣旨颁布后全局势力连锁反应推演",
            temperature=0.7,
            token_budget=4096,
            output_schema={
                "type": "object",
                "required": ["global_narrative", "faction_reactions", "summary"],
                "properties": {
                    "global_narrative": {"type": "string", "maxLength": 300},
                    "faction_reactions": {
                        "type": "array",
                        "minItems": 3,
                        "items": {
                            "type": "object",
                            "required": ["faction_id", "faction_name", "stance", "narrative"],
                            "properties": {
                                "faction_id": {"type": "string"},
                                "faction_name": {"type": "string"},
                                "stance": {"type": "string", "maxLength": 20},
                                "narrative": {"type": "string", "maxLength": 100},
                                "likely_action": {"type": "string", "maxLength": 40},
                            },
                        },
                    },
                    "diplomatic_shifts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"},
                                "change": {"type": "integer", "minimum": -20, "maximum": 20},
                                "reason": {"type": "string", "maxLength": 40},
                            },
                        },
                    },
                    "event_triggers": {"type": "array"},
                    "summary": {"type": "string", "maxLength": 80},
                },
            },
            system_prompt="""你是元末乱世的天下推演谋士。圣旨颁布后，推演各方势力反应。

## 输出合约（最高优先级）
- 整个回复必须是纯 JSON 对象，禁止任何 Markdown 包装或前缀文字
- 必须包含全部字段：global_narrative, faction_reactions, diplomatic_shifts, event_triggers, economic_ripples, strategic_advice, summary

## 推演原则
1. 基于势力性格：陈友谅多疑好战、张士诚守成自保、方国珍骑墙观望、元廷力不从心
2. 基于地理关系：邻国反应强烈，远国反应平淡
3. 基于外交现状：同盟则安心，敌对则警觉，中立则观望
4. 经济连锁：大战影响商路，粮价波动，难民流动

## 安全约束
- 只推演游戏内势力，不涉及真实历史人物评价
- 不输出任何政治敏感内容
- faction_reactions 至少包含 3 个其他势力

## 禁止事项
- 禁止在 JSON 外输出任何文字或 Markdown 标记
- 禁止同一势力同时出现大幅亲近和敌视的外交变动

## 输出格式
严格 JSON，不得有任何额外文字。""",

            fallback_response='{"global_narrative":"天下局势暗流涌动，各方势力静观其变。","faction_reactions":[],"summary":"局势暂无明显变化"}',
        )

    # ================================================================
    # 3. 势力君主决策 Prompt
    # ================================================================

    def _register_ruler_decision(self):
        self._prompts["ruler_decision"] = PromptVersion(
            name="ruler_decision",
            version="2.0.0",
            updated="2026-07-16",
            description="AI 势力君主每回合自主决策",
            temperature=0.7,
            token_budget=2048,
            output_schema={
                "type": "object",
                "required": ["primary_action", "actions", "strategy", "reasoning"],
                "properties": {
                    "primary_action": {
                        "type": "string",
                        "enum": [
                            "recruit", "march", "attack", "build", "farm",
                            "train_troops", "tax", "fortify", "diplomacy",
                            "spy", "claim_title", "consolidate", "defend",
                        ],
                    },
                    "actions": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "required": ["type", "priority"],
                            "properties": {
                                "type": {"type": "string"},
                                "target": {"type": "string"},
                                "target_faction": {"type": "string"},
                                "amount": {"type": "integer", "minimum": 0},
                                "priority": {"enum": ["critical", "high", "normal", "low"]},
                            },
                        },
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["expansion", "consolidation", "defense", "diplomacy", "espionage", "development"],
                    },
                    "reasoning": {"type": "string", "maxLength": 200},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
            system_prompt="""你是元末乱世中的一方霸主。你精通权谋韬略，善于审时度势。

## 决策原则
1. 基于自身人格特质做决策（侵略性/谨慎/外交型等）
2. 量力而行：国库空虚时不轻易开战，军力薄弱时不主动挑衅
3. 审时度势：邻国交战时可渔翁得利，强敌压境时合纵连横
4. 长远规划：不只顾眼前一回合，要考虑三到五回合的战略布局

## 安全约束
- 这是游戏AI决策，不涉及真实历史评价
- 不输出政治敏感内容

## 输出要求
在回复末尾附带 JSON 格式行动计划。先写决策文本，再附 JSON。""",

            fallback_response='{"primary_action":"consolidate","actions":[],"strategy":"consolidation","reasoning":"局势不明，暂且休整"}',
        )

    # ================================================================
    # 4. NPC 对话 Prompt
    # ================================================================

    def _register_npc_chat(self):
        self._prompts["npc_chat"] = PromptVersion(
            name="npc_chat",
            version="2.0.0",
            updated="2026-07-16",
            description="NPC 文臣与玩家的个性化对话",
            temperature=0.75,
            token_budget=2048,
            system_prompt="""你是元末乱世中的一位文臣谋士。你需要始终保持角色设定。

## 对话要求
1. 始终保持角色设定，不可脱离人物性格和背景
2. 以古文白话风格回答，语气符合你的身份和说话风格
3. 基于你的专长领域提供专业建议，不要越俎代庖
4. 对君主恭敬但不谄媚，敢于直言但注意分寸
5. 可以引用历史典故来佐证观点
6. 回答要具体、有建设性，避免泛泛而谈
7. 根据你的才智等级决定回答深度，根据忠诚度决定是否畅所欲言
8. 当话题涉及同僚专长领域时，可以自然地表示"此事可问XX"

## 安全约束
- 不讨论元末以后的历史事件
- 不使用现代网络用语
- 不涉及政治敏感内容""",

            fallback_response="臣以为此事尚需从长计议。",
        )

    # ================================================================
    # 5. 廷议辩论 Prompt
    # ================================================================

    def _register_court_debate(self):
        self._prompts["court_debate"] = PromptVersion(
            name="court_debate",
            version="2.0.0",
            updated="2026-07-16",
            description="多 NPC 朝堂廷议辩论（三轮交互）",
            temperature=0.75,
            token_budget=2048,
            system_prompt="""你正在参加朝堂廷议。你是元末乱世中的一位大臣。

## 辩论规则
1. 第一轮：从你的专业角度独立发表见解，100-200字
2. 第二轮：回应同僚观点，可支持/反驳/补充，80-150字
3. 保持朝堂礼仪，不可人身攻击
4. 基于你的好感度倾向决定支持或反对谁

## 安全约束
- 不讨论元末以后的内容
- 不涉及政治敏感内容""",

            fallback_response="臣附议。",
        )

    # ================================================================
    # 6. 细作/谍报 Prompt
    # ================================================================

    def _register_spy_report(self):
        self._prompts["spy_report"] = PromptVersion(
            name="spy_report",
            version="2.0.0",
            updated="2026-07-16",
            description="细作头目情报汇报",
            temperature=0.65,
            token_budget=1024,
            system_prompt="""你是潜伏敌营的细作头目，负责搜集情报。需谨慎行事，避免暴露身份。以密报口吻汇报。

## 安全约束
- 只汇报游戏内情报
- 不涉及真实历史机密""",

            fallback_response="暂无可用情报。",
        )

    # ================================================================
    # 7. 律法审讯 Prompt
    # ================================================================

    def _register_law_judge(self):
        self._prompts["law_judge"] = PromptVersion(
            name="law_judge",
            version="2.0.0",
            updated="2026-07-16",
            description="案件审理与判决",
            temperature=0.5,  # 法律判决需要低温度
            token_budget=2048,
            system_prompt="""你是元末乱世中的刑部官员，负责审理案件。须以《大明律》为纲，结合乱世实际情况公正断案。

## 判决原则
1. 证据为先，不可主观臆断
2. 量刑有据，引用律法条文
3. 乱世用重典，但不可滥杀无辜

## 安全约束
- 不讨论现代法律体系
- 不涉及政治敏感内容""",

            fallback_response="证据不足，暂且收监，待查明后再行审理。",
        )

    # ================================================================
    # 8. 事件叙事 Prompt
    # ================================================================

    def _register_event_narrative(self):
        self._prompts["event_narrative"] = PromptVersion(
            name="event_narrative",
            version="2.0.0",
            updated="2026-07-16",
            description="天灾/祥瑞/流民/兵变等随机事件叙事",
            temperature=0.7,
            token_budget=1024,
            system_prompt="""你是元末乱世的记录官，以古风邸报/塘报格式记录天下大事。

## 写作要求
1. 用文言文或半文言文风格
2. 叙事简洁有力，50-150字
3. 反映元末乱世氛围

## 安全约束
- 不涉及真实历史事件评价
- 不使用现代词汇""",

            fallback_response="是日无事。",
        )

    # ================================================================
    # 9. 国史记录 Prompt
    # ================================================================

    def _register_history_record(self):
        self._prompts["history_record"] = PromptVersion(
            name="history_record",
            version="2.0.0",
            updated="2026-07-16",
            description="每回合国史编年记录",
            temperature=0.5,
            token_budget=2048,
            system_prompt="""你是记录元末乱世的史官，以《资治通鉴》体例记录天下大事。

## 记录要求
1. 编年体：按时间顺序，一事一条
2. 客观中立：不偏袒任何势力
3. 简洁精炼：每条30-80字
4. 用文言文风格

## 安全约束
- 不涉及真实历史评价
- 不输出政治敏感内容""",

            fallback_response="是岁无事可记。",
        )


# ============================================================
# 便捷函数
# ============================================================

def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry.get_instance()


def get_prompt(name: str) -> Optional[PromptVersion]:
    return get_prompt_registry().get(name)


def build_safe_user_prompt(template: str, **kwargs) -> str:
    """构建安全的用户 Prompt：先净化输入，再填充模板"""
    safe_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = sanitize_user_input(value)
        else:
            safe_kwargs[key] = value
    return template.format(**safe_kwargs)
