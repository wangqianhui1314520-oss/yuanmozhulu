"""
AI协议模型 - 统一JSON标准化数据交互接口（3.2 全链路AI智能体）

定义游戏引擎与AI智能体之间的：
1. GameStateSnapshot - 游戏→AI 的沙盘全量快照
2. AICommand / AICommandSet - AI→游戏 的可执行指令
3. DelegationConfig - 委任权限配置
4. ValidationResult - 校验结果
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


# ============================================================
# 委任权限等级
# ============================================================

class DelegationLevel(str, Enum):
    """委任权限等级"""
    FULL_MANUAL = "full_manual"       # 全手动：玩家全部亲自操作
    ADVISORY = "advisory"             # 建议模式：AI推荐，玩家确认
    SEMI_AUTO = "semi_auto"           # 半委任：AI自动执行低风险操作，高风险需确认
    FULL_AUTO = "full_auto"           # 全委任：AI全权代理


class DelegationDomain(str, Enum):
    """委任领域"""
    CIVIL = "civil"                   # 内政（城建/资源/民心）
    MILITARY = "military"             # 军事（征兵/行军/战斗）
    DIPLOMACY = "diplomacy"           # 外交（结盟/宣战/贸易）
    ESPIONAGE = "espionage"           # 谍报（细作/情报）
    ECONOMY = "economy"               # 经济（税收/贸易/开发）


# ============================================================
# AI 人格类型
# ============================================================

class AIPersonality(str, Enum):
    """AI势力人格"""
    AGGRESSIVE = "aggressive"         # 激进：频繁扩张，主动进攻
    STEADY = "steady"                 # 稳健：平衡发展，伺机而动
    CONSERVATIVE = "conservative"     # 苟分：固守发展，避免冲突
    OPPORTUNIST = "opportunist"       # 投机：见风使舵，趁火打劫
    DIPLOMATIC = "diplomatic"         # 外交：合纵连横，以势压人


# ============================================================
# GameStateSnapshot - 游戏→AI 沙盘快照
# ============================================================

class FactionSnapshot(BaseModel):
    """势力快照"""
    faction_id: str
    name: str
    ruler_name: str = ""
    is_alive: bool = True
    is_player: bool = False
    personality: str = "steady"
    # 核心资源
    treasury: int = 0
    grain: int = 0
    arms: int = 0
    horses: int = 0
    troops: int = 0
    population: int = 0
    reputation: int = 50
    # 朝堂
    court_stability: int = 50
    realm_stability: int = 50
    # 领地
    capital_tile: str = ""
    tile_count: int = 0
    tile_ids: list[str] = Field(default_factory=list)
    # 外交
    at_war_with: list[str] = Field(default_factory=list)
    allied_with: list[str] = Field(default_factory=list)
    vassal_of: str = ""
    vassals: list[str] = Field(default_factory=list)
    # 国策
    active_policies: list[str] = Field(default_factory=list)
    # Buff/Debuff
    buffs: list[dict] = Field(default_factory=list)
    debuffs: list[dict] = Field(default_factory=list)


class TileSnapshot(BaseModel):
    """地块快照"""
    tile_id: str
    tile_name: str = ""
    tile_type: str = "farmland"
    owner_faction: str = ""
    troops: int = 0
    development: int = 20
    fortification: int = 0
    population: int = 0
    # 建筑
    buildings: list[str] = Field(default_factory=list)
    # 灾害
    active_disaster: str = ""
    # 坐标（用于AI推断距离）
    x: float = 0.0
    y: float = 0.0
    # 邻接地块
    neighbors: list[str] = Field(default_factory=list)


class RelationSnapshot(BaseModel):
    """外交关系快照"""
    faction_a: str
    faction_b: str
    stance: str = "neutral"  # war/neutral/truce/alliance/vassal
    trust: int = 50
    trade_active: bool = False
    marriage: bool = False


class BattleSnapshot(BaseModel):
    """战斗快照"""
    battle_id: str = ""
    attacker_faction: str
    defender_faction: str
    tile_id: str
    attacker_troops: int
    defender_troops: int
    status: str = "ongoing"  # ongoing/sieging/resolved


class WarSnapshot(BaseModel):
    """征伐快照"""
    war_id: str = ""
    attacker: str
    defender: str
    started_round: int = 0
    battles: list[BattleSnapshot] = Field(default_factory=list)


class GameStateSnapshot(BaseModel):
    """
    游戏→AI 统一沙盘快照
    
    提供给所有AI智能体的标准化数据接口，
    包含完整的沙盘地图、资源、兵力、视野数据。
    """
    # 回合信息
    current_round: int = 0
    current_year: int = 1351
    current_season: str = "春"
    disaster_index: int = 0
    
    # 势力数据
    factions: dict[str, FactionSnapshot] = Field(default_factory=dict)
    player_faction_id: str = ""
    
    # 地图地块（玩家视野内）
    visible_tiles: list[TileSnapshot] = Field(default_factory=list)
    all_tiles: list[TileSnapshot] = Field(default_factory=list)
    
    # 外交关系
    relations: list[RelationSnapshot] = Field(default_factory=list)
    
    # 当前征伐
    active_wars: list[WarSnapshot] = Field(default_factory=list)
    
    # 近期事件
    recent_events: list[dict] = Field(default_factory=list)
    
    # 武将军团
    legions: list[dict] = Field(default_factory=list)
    
    # 全局模式
    game_mode: str = "player_turn"
    
    # 天气/季节修正
    season_modifiers: dict = Field(default_factory=dict)
    
    # 历史锚点
    triggered_anchors: list[str] = Field(default_factory=list)


# ============================================================
# AICommand - AI→游戏 可执行指令
# ============================================================

class CommandType(str, Enum):
    """指令类型枚举（与 round_engine 对齐）"""
    # 军事
    MARCH = "march"
    RECRUIT = "recruit"
    BUY_HORSES = "buy_horses"
    TRAIN_TROOPS = "train_troops"
    FORTIFY = "fortify"
    SCOUT = "scout"
    # 内政
    DEVELOP = "develop"
    BUILD = "build"
    RELIEF = "relief"
    TAX = "tax"
    CONVICT_LABOR = "convict_labor"
    CULTURAL_POLICY = "cultural_policy"
    SEA_POLICY = "sea_policy"
    MEDICAL = "medical"
    # 外交
    DIPLOMACY = "diplomacy"
    # 细作
    SPY = "spy"
    AMBUSH = "ambush"
    PLUNDER = "plunder"
    # 朝堂
    ENFEOFF = "enfeoff"
    AMNESTY = "amnesty"
    MOVE_CAPITAL = "move_capital"
    LAW = "law"                  # 律法审判
    PURGE = "purge"              # 清洗官员
    # 国策
    SET_POLICY = "set_policy"


class AICommand(BaseModel):
    """
    AI返回的单条可执行指令
    
    引擎会对每条指令做资源、地形、权限合法性校验，
    校验失败的指令会被拒绝并记录原因。
    """
    command_id: str = ""                    # 唯一ID
    command_type: CommandType               # 指令类型
    faction_id: str                         # 执行势力
    params: dict = Field(default_factory=dict)  # 指令参数
    
    # 元信息
    reason: str = ""                        # AI决策理由
    priority: int = 5                       # 优先级 1-10
    estimated_cost: dict = Field(default_factory=dict)  # 预估消耗
    
    class Config:
        use_enum_values = True


class AICommandSet(BaseModel):
    """
    AI返回的指令集
    
    包含一组可执行指令，以及AI的决策摘要。
    """
    # 元信息
    agent_type: str = ""                    # 来源智能体类型
    faction_id: str = ""                    # 目标势力
    turn: int = 0                           # 回合号
    
    # 决策摘要（给人看的）
    decision_summary: str = ""
    strategic_analysis: str = ""
    
    # 指令列表
    commands: list[AICommand] = Field(default_factory=list)
    
    # 风险评估
    risk_assessment: str = "low"            # low/medium/high/critical
    fallback_suggestions: list[str] = Field(default_factory=list)


# ============================================================
# ValidationResult - 校验结果
# ============================================================

class SingleValidation(BaseModel):
    """单条指令校验结果"""
    command_id: str
    command_type: str
    passed: bool
    reason: str = ""                        # 失败原因
    warnings: list[str] = Field(default_factory=list)
    # 修正后的参数（引擎自动修正）
    corrected_params: Optional[dict] = None
    # 实际消耗
    actual_cost: dict = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """批量校验报告"""
    total: int = 0
    passed: int = 0
    rejected: int = 0
    corrected: int = 0
    results: list[SingleValidation] = Field(default_factory=list)
    # 防崩坏检查
    balance_check: dict = Field(default_factory=dict)
    # 总结
    summary: str = ""


# ============================================================
# DelegationConfig - 委任配置
# ============================================================

class DomainDelegation(BaseModel):
    """单领域委任配置"""
    domain: DelegationDomain
    level: DelegationLevel = DelegationLevel.ADVISORY
    # 半委任下的自动执行阈值
    auto_approve_below_gold: int = 500      # 低于此消耗自动执行
    auto_approve_below_troops: int = 200    # 低于此兵力风险自动执行
    # 通知设置
    notify_on_action: bool = True
    notify_on_recommendation: bool = True


class FullDelegationConfig(BaseModel):
    """全委任配置"""
    faction_id: str
    domains: dict[str, DomainDelegation] = Field(default_factory=dict)
    
    @classmethod
    def default_for(cls, faction_id: str) -> "FullDelegationConfig":
        """默认委任配置（全建议模式）"""
        return cls(
            faction_id=faction_id,
            domains={
                "civil": DomainDelegation(domain=DelegationDomain.CIVIL, level=DelegationLevel.ADVISORY),
                "military": DomainDelegation(domain=DelegationDomain.MILITARY, level=DelegationLevel.ADVISORY),
                "diplomacy": DomainDelegation(domain=DelegationDomain.DIPLOMACY, level=DelegationLevel.ADVISORY),
                "espionage": DomainDelegation(domain=DelegationDomain.ESPIONAGE, level=DelegationLevel.ADVISORY),
                "economy": DomainDelegation(domain=DelegationDomain.ECONOMY, level=DelegationLevel.ADVISORY),
            }
        )


# ============================================================
# NL 自然语言指令路由
# ============================================================

class NLCommandRequest(BaseModel):
    """自然语言指令请求"""
    text: str                               # 自然语言指令
    faction_id: str                         # 玩家势力ID
    context: dict = Field(default_factory=dict)  # 上下文（可选）
    # 路由偏好（可选，为空则自动判断）
    preferred_agents: list[str] = Field(default_factory=list)


class NLCommandResult(BaseModel):
    """自然语言指令执行结果"""
    original_text: str
    parsed_intent: str = ""                 # AI解析的意图
    routed_agents: list[str] = Field(default_factory=list)  # 路由到的智能体
    command_sets: list[AICommandSet] = Field(default_factory=list)
    validation: Optional[ValidationReport] = None
    execution_summary: str = ""
    narrative: str = ""                     # AI生成的叙事描述
    suggestions: list[str] = Field(default_factory=list)


# ============================================================
# 防崩坏配置
# ============================================================

class AntiCollapseConfig(BaseModel):
    """防崩坏机制配置"""
    # 单回合资源变化上限（百分比）
    max_treasury_change_pct: float = 0.50       # 银两单回合最多变化50%
    max_grain_change_pct: float = 0.60          # 粮草单回合最多变化60%
    max_troops_change_pct: float = 0.40         # 兵力单回合最多变化40%
    max_population_change_pct: float = 0.30     # 人口单回合最多变化30%
    
    # 绝对值上限
    max_troops_per_tile: int = 50000            # 单地块最大兵力
    max_gold_per_faction: int = 1000000         # 单势力最大银两
    max_grain_per_faction: int = 5000000        # 单势力最大粮草
    
    # AI操作频率限制
    max_commands_per_turn: int = 50             # 单势力单回合最大指令数
    max_march_per_turn: int = 10                # 单势力单回合最大行军数
    max_recruit_per_turn: int = 5               # 单势力单回合最大征兵次数
    
    # 冷却机制
    command_cooldown_rounds: int = 0            # 重复指令冷却回合
    
    # 自动熔断
    enable_circuit_breaker: bool = True
    max_consecutive_failures: int = 5           # 连续失败上限
