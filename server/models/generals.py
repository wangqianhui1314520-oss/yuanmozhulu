"""
3.2 武将人格战术系统 - 数据模型
包含: 武将、兵种、军团编制、战术特性
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================
# 兵种类型
# ============================================================

class UnitType(str, Enum):
    """元末兵种（6种 + 克制链）"""
    INFANTRY = "infantry"           # 步兵 — 克制枪兵
    CAVALRY = "cavalry"             # 骑兵 — 克制弓兵
    ARCHER = "archer"               # 弓兵 — 克制步兵
    SPEARMAN = "spearman"           # 枪兵 — 克制骑兵
    NAVY = "navy"                   # 水军 — 水域霸主
    SIEGE = "siege"                 # 攻城器 — 克制城防


# 兵种克制表: {攻击方: {被克方: 伤害倍率}}
UNIT_COUNTER_MATRIX: dict[str, dict[str, float]] = {
    "infantry":  {"spearman": 1.5, "archer": 0.7, "cavalry": 0.8, "navy": 0.9, "siege": 1.3},
    "cavalry":   {"archer": 1.5, "spearman": 0.5, "infantry": 0.9, "navy": 0.6, "siege": 1.2},
    "archer":    {"infantry": 1.5, "cavalry": 0.7, "spearman": 0.9, "navy": 1.1, "siege": 0.8},
    "spearman":  {"cavalry": 1.8, "infantry": 0.7, "archer": 0.9, "navy": 0.8, "siege": 0.9},
    "navy":      {"infantry": 1.2, "cavalry": 1.4, "archer": 1.1, "spearman": 1.1, "siege": 1.0},
    "siege":     {"fortification": 2.0, "infantry": 0.6, "cavalry": 0.5, "archer": 0.4, "spearman": 0.5, "navy": 0.3},
}

# 兵种地形适配表: {兵种: {地形: 战力倍率}}
UNIT_TERRAIN_MATRIX: dict[str, dict[str, float]] = {
    "infantry":  {"mountain": 1.3, "city": 1.2, "forest": 1.2, "wetland": 0.8, "desert": 0.7, "water": 0.2, "grassland": 0.9},
    "cavalry":   {"grassland": 1.5, "steppe": 1.4, "desert": 1.2, "mountain": 0.4, "forest": 0.5, "city": 0.7, "wetland": 0.3, "water": 0.0},
    "archer":    {"mountain": 1.4, "forest": 1.3, "city": 1.1, "grassland": 0.8, "desert": 0.9, "water": 0.6},
    "spearman":  {"city": 1.3, "grassland": 1.1, "mountain": 0.9, "forest": 0.9, "water": 0.3, "wetland": 0.7},
    "navy":      {"water": 2.0, "coastal": 1.5, "port": 1.3, "wetland": 1.2, "grassland": 0.0, "desert": 0.0, "mountain": 0.0},
    "siege":     {"city": 1.5, "pass": 1.2, "grassland": 0.8, "mountain": 0.3, "water": 0.0, "forest": 0.6},
}

# 兵种基本属性
UNIT_BASE_STATS: dict[str, dict] = {
    "infantry":  {"cost_grain": 2, "cost_gold": 1, "speed": 10, "power": 100, "defense": 80},
    "cavalry":   {"cost_grain": 4, "cost_gold": 3, "speed": 25, "power": 120, "defense": 60},
    "archer":    {"cost_grain": 2, "cost_gold": 2, "speed": 12, "power": 90, "defense": 50},
    "spearman":  {"cost_grain": 2, "cost_gold": 1, "speed": 8, "power": 85, "defense": 100},
    "navy":      {"cost_grain": 3, "cost_gold": 3, "speed": 15, "power": 80, "defense": 70},
    "siege":     {"cost_grain": 5, "cost_gold": 8, "speed": 5, "power": 60, "defense": 30},
}


# ============================================================
# 武将战术特性
# ============================================================

class TacticType(str, Enum):
    """武将战术特性"""
    # 进攻型
    SHOCK_CAVALRY = "shock_cavalry"           # 铁骑冲锋 — 骑兵伤害+20%
    AMBUSH_MASTER = "ambush_master"           # 伏击大师 — 山地/森林战力+30%
    SIEGE_EXPERT = "siege_expert"             # 攻城专家 — 围城效率+30%
    FLANK_COMMANDER = "flank_commander"       # 侧翼包抄 — 多路夹击伤害+25%
    NAVAL_RAIDER = "naval_raider"             # 水战枭雄 — 水战伤害+35%
    
    # 防守型
    FORTRESS_DEFENDER = "fortress_defender"   # 固若金汤 — 城防加成+30%
    MOUNTAIN_GUARD = "mountain_guard"         # 山地坚守 — 山地防御+40%
    RIVER_DEFENDER = "river_defender"         # 水寨固守 — 水域防御+35%
    LAST_STAND = "last_stand"                 # 背水一战 — 兵力低于30%时战力+50%
    
    # 后勤型
    LOGISTICS_MASTER = "logistics_master"     # 粮道精通 — 补给线范围+2格
    FORCED_MARCH = "forced_march"             # 强行军 — 行军速度+30%，攻-5%
    FIELD_RECRUITER = "field_recruiter"       # 就地征募 — 战后可征降卒，攻+5%
    
    # 特殊型
    FIRE_ATTACK = "fire_attack"               # 火攻 — 攻城/野战伤害+30%
    NIGHT_RAID = "night_raid"                 # 夜袭 — 首回合攻击力+40%
    PSYCHOLOGICAL_WAR = "psychological_war"   # 攻心为上 — 守军士气-15/回合
    LOYAL_COMMANDER = "loyal_commander"       # 忠勇无双 — 防御+10%，败战时减损60%+30%翻盘
    RIVER_CROSSING = "river_crossing"         # 渡河强袭 — 水域/沿海战力+50%


class GeneralRarity(str, Enum):
    """武将稀有度"""
    LEGENDARY = "legendary"     # 传奇（3个战术）
    ELITE = "elite"             # 精英（2个战术）
    VETERAN = "veteran"         # 老将（1个战术）
    COMMON = "common"           # 普通（无战术）


# ============================================================
# 武将模型
# ============================================================

class General(BaseModel):
    """武将模型 - 独立于官员/俘虏的完整将领系统"""
    model_config = {"extra": "allow"}
    
    general_id: str
    name: str
    faction_id: str
    rarity: GeneralRarity = GeneralRarity.COMMON
    
    # 五维属性 (0~100)
    command: int = 50         # 统率 — 影响军团兵力上限
    might: int = 50           # 武力 — 影响战斗伤害
    intellect: int = 50       # 智谋 — 影响伏击/战术成功率
    loyalty: int = 50         # 忠诚 — 影响背叛/被离间概率
    charisma: int = 50        # 魅力 — 影响俘虏、招降、士气恢复
    
    # 兵种专精 (0~100)
    infantry_proficiency: int = 50
    cavalry_proficiency: int = 50
    archer_proficiency: int = 50
    spearman_proficiency: int = 50
    navy_proficiency: int = 50
    siege_proficiency: int = 50
    
    # 战术特性 (0~3个)
    tactics: list[TacticType] = Field(default_factory=list)
    
    # 委任状态
    is_assigned: bool = False           # 是否已出任
    assigned_tile: str = ""             # 驻地地块ID
    assigned_legion_id: str = ""        # 所属军团ID
    
    # 历史记录
    battles_fought: int = 0             # 参战次数
    battles_won: int = 0               # 胜利次数
    cities_captured: int = 0           # 攻克城池数
    troops_killed: int = 0             # 累计歼敌
    alive: bool = True
    
    # 人格特色（影响自主行为）
    personality: str = "balanced"      # aggressive/defensive/cautious/reckless/balanced
    biography: str = ""                # 生平简介
    
    def get_best_unit_type(self) -> UnitType:
        """获取武将最擅长的兵种"""
        scores = {
            UnitType.INFANTRY: self.infantry_proficiency,
            UnitType.CAVALRY: self.cavalry_proficiency,
            UnitType.ARCHER: self.archer_proficiency,
            UnitType.SPEARMAN: self.spearman_proficiency,
            UnitType.NAVY: self.navy_proficiency,
            UnitType.SIEGE: self.siege_proficiency,
        }
        return max(scores, key=scores.get)
    
    def get_proficiency(self, unit_type: UnitType) -> int:
        """获取指定兵种熟练度"""
        mapping = {
            UnitType.INFANTRY: self.infantry_proficiency,
            UnitType.CAVALRY: self.cavalry_proficiency,
            UnitType.ARCHER: self.archer_proficiency,
            UnitType.SPEARMAN: self.spearman_proficiency,
            UnitType.NAVY: self.navy_proficiency,
            UnitType.SIEGE: self.siege_proficiency,
        }
        return mapping.get(unit_type, 50)
    
    def has_tactic(self, tactic: TacticType) -> bool:
        return tactic in self.tactics


# ============================================================
# 军团编制模型
# ============================================================

class LegionFormation(str, Enum):
    """军团阵型"""
    BALANCED = "balanced"          # 均衡阵 — 攻守兼备
    AGGRESSIVE = "aggressive"      # 锋矢阵 — 进攻+30%，防御-15%
    DEFENSIVE = "defensive"        # 方圆阵 — 防御+30%，速度-20%
    MOBILE = "mobile"              # 长蛇阵 — 速度+30%，战斗-10%
    SIEGE_MODE = "siege_mode"      # 攻城阵 — 攻城+40%，野战-20%
    NAVAL_FORM = "naval_form"      # 水阵 — 水域+25%，陆战-30%


class Legion(BaseModel):
    """军团编制模型"""
    model_config = {"extra": "allow"}
    
    legion_id: str
    name: str
    faction_id: str
    commander_id: str = ""         # 主将ID
    sub_commander_ids: list[str] = Field(default_factory=list)  # 副将
    
    # 兵力编成: {UnitType: count}
    unit_composition: dict[str, int] = Field(default_factory=dict)
    
    # 当前状态
    current_tile: str = ""
    marching_towards: str = ""     # 行军目标
    formation: LegionFormation = LegionFormation.BALANCED
    
    # 补给
    supply_grain: int = 0
    supply_range: int = 4          # 补给线最大距离
    
    # 委任
    is_autonomous: bool = False    # 是否委任自主作战
    auto_priority: str = "defensive"  # offensive/defensive/raid/support
    
    # 统计
    total_troops: int = 0
    morale: int = 60
    
    def get_total_troops(self) -> int:
        return sum(self.unit_composition.values())
    
    def get_dominant_unit(self) -> Optional[str]:
        """获取主力兵种"""
        if not self.unit_composition:
            return None
        return max(self.unit_composition, key=self.unit_composition.get)


# ============================================================
# 历史剧情锚点
# ============================================================

class StoryBranch(str, Enum):
    """剧情分支"""
    UNIFICATION = "unification"             # 大一统
    WEAKEN_YUAN = "weaken_yuan"            # 元廷衰落
    RIVAL_CONFRONTATION = "rival_confrontation"  # 群雄对决
    BARBARIAN_INVASION = "barbarian_invasion"    # 外族入侵
    PEASANT_REVOLT = "peasant_revolt"       # 农民起义再起
    DIPLOMATIC_VICTORY = "diplomatic_victory"   # 外交统一
    COLLAPSE = "collapse"                   # 势力崩溃


class HistoryAnchor(BaseModel):
    """历史剧情锚点"""
    anchor_id: str
    title: str
    description: str
    trigger_year: int = 1351           # 最早触发年
    conditions: dict = Field(default_factory=dict)   # 触发条件
    branches: list[dict] = Field(default_factory=list)  # 分支选项
    triggered: bool = False
    chosen_branch: str = ""
    narrative: str = ""


# ============================================================
# 外交权谋模型
# ============================================================

class DiscordType(str, Enum):
    """离间类型"""
    SOW_DISCORD = "sow_discord"       # 离间同盟
    BRIBE_OFFICIAL = "bribe_official" # 贿赂官员
    SPREAD_RUMOR = "spread_rumor"     # 散布谣言
    FAKE_LETTER = "fake_letter"       # 伪造书信


class CooptType(str, Enum):
    """招安类型"""
    OFFER_TITLE = "offer_title"       # 许以官爵
    OFFER_GOLD = "offer_gold"         # 重金招揽
    THREATEN = "threaten"             # 以兵威迫
    MARRY_ALLIANCE = "marry_alliance" # 联姻笼络


class FactionStrategy(str, Enum):
    """外交策略"""
    FAR_FRIEND_NEAR_ATTACK = "far_friend_near_attack"  # 远交近攻
    NEAR_FRIEND_FAR_ATTACK = "near_friend_far_attack"  # 近交远伐
    BALANCE_OF_POWER = "balance_of_power"               # 均势制衡
    EXPANSIONIST = "expansionist"                       # 步步蚕食
    ISOLATIONIST = "isolationist"                       # 闭关自守
