"""
多智能体权责体系 - 唯一主责AI规则

核心规则:
1. 一类事件 = 唯一主责AI = 仅该AI计算，其余AI仅同步状态不计算
2. 杜绝多层重复推演：EventAgent、CivilAgent、地块AI等不同模块重复计算同一事件

权责分配:
- EventAgent(A5): 全局事件叙事、灾害触发、祥瑞异象
- CivilAgent:      地块民生演化（人口、民心、产出独立迭代）
- RulerAgent(A2):  列国战略决策（外交方向、军事目标、内政方针）
- MinisterAgent:   朝堂派系博弈（党争、弹劾、进言、势力制衡）
- MilitaryAgent:   军事攻防推演（行军、战斗、围城、驻防）
- DiplomacyAgent(A6): 外交缔约（盟约、通商、联姻、纳贡）
- SpyAgent(A4):    谍报细作（情报搜集、渗透、破坏、反间）
- RoyalAgent(A7):  宗室管理（继承、培养、宗室纠纷）
- HistoryAgent(A8): 国史修撰（大事记录、结局编撰）
"""
from __future__ import annotations
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("yuanmo.responsibility")


class EventDomain(str, Enum):
    """事件领域 - 每个领域有唯一主责Agent"""
    # A5 司天台
    DISASTER = "disaster"               # 天灾（洪水/旱灾/蝗灾/瘟疫）
    AUSPICIOUS = "auspicious"           # 祥瑞异象
    RANDOM_EVENT = "random_event"       # 随机事件
    
    # CivilAgent (地块AI)
    POPULATION_CHANGE = "population"    # 人口变化
    MORALE_CHANGE = "morale"            # 民心变化
    PRODUCTION = "production"           # 产出变化
    REFUGEE = "refugee"                 # 流民
    TILE_DEVELOPMENT = "tile_dev"       # 地块发展
    
    # A2 群雄殿
    FACTION_STRATEGY = "faction_strategy"   # 势力战略
    FACTION_EXPANSION = "faction_expand"    # 势力扩张
    FACTION_INTERNAL = "faction_internal"   # 势力内政
    
    # MinisterAgent (朝堂AI)
    COURT_FACTION = "court_faction"     # 派系博弈
    COURT_IMPEACH = "court_impeach"     # 弹劾
    COURT_ADVICE = "court_advice"       # 进言
    COURT_PURGE = "court_purge"         # 清洗
    
    # MilitaryAgent
    BATTLE = "battle"                   # 战斗
    SIEGE = "siege"                     # 围城
    MARCH = "march"                     # 行军
    GARRISON = "garrison"               # 驻防
    REBELLION = "rebellion"             # 叛乱
    
    # A6 外交署
    ALLIANCE = "alliance"               # 结盟
    TRADE = "trade"                     # 通商
    MARRIAGE = "marriage"               # 联姻
    TRIBUTE = "tribute"                 # 纳贡
    TRUCE = "truce"                     # 停战
    
    # A4 谍报司
    INFILTRATION = "infiltration"       # 渗透
    INTEL_GATHER = "intel"              # 情报搜集
    SABOTAGE = "sabotage"               # 破坏
    COUNTER_SPY = "counter_spy"         # 反间
    
    # A7 宗室府
    SUCCESSION = "succession"           # 继承
    ROYAL_EDUCATION = "royal_edu"       # 培养
    ROYAL_CONFLICT = "royal_conflict"   # 宗室纠纷
    
    # A8 国史馆
    CHRONICLE = "chronicle"             # 大事记录
    BIOGRAPHY = "biography"             # 人物传记


# 领域→主责Agent映射表（唯一主责）
DOMAIN_OWNER: dict[EventDomain, str] = {
    # A5 司天台
    EventDomain.DISASTER: "A5_event",
    EventDomain.AUSPICIOUS: "A5_event",
    EventDomain.RANDOM_EVENT: "A5_event",
    
    # CivilAgent
    EventDomain.POPULATION_CHANGE: "CivilAgent",
    EventDomain.MORALE_CHANGE: "CivilAgent",
    EventDomain.PRODUCTION: "CivilAgent",
    EventDomain.REFUGEE: "CivilAgent",
    EventDomain.TILE_DEVELOPMENT: "CivilAgent",
    
    # A2 群雄殿
    EventDomain.FACTION_STRATEGY: "A2_warlord",
    EventDomain.FACTION_EXPANSION: "A2_warlord",
    EventDomain.FACTION_INTERNAL: "A2_warlord",
    
    # MinisterAgent
    EventDomain.COURT_FACTION: "MinisterAgent",
    EventDomain.COURT_IMPEACH: "MinisterAgent",
    EventDomain.COURT_ADVICE: "MinisterAgent",
    EventDomain.COURT_PURGE: "MinisterAgent",
    
    # MilitaryAgent
    EventDomain.BATTLE: "MilitaryAgent",
    EventDomain.SIEGE: "MilitaryAgent",
    EventDomain.MARCH: "MilitaryAgent",
    EventDomain.GARRISON: "MilitaryAgent",
    EventDomain.REBELLION: "MilitaryAgent",
    
    # A6 外交署
    EventDomain.ALLIANCE: "A6_diplomacy",
    EventDomain.TRADE: "A6_diplomacy",
    EventDomain.MARRIAGE: "A6_diplomacy",
    EventDomain.TRIBUTE: "A6_diplomacy",
    EventDomain.TRUCE: "A6_diplomacy",
    
    # A4 谍报司
    EventDomain.INFILTRATION: "A4_espionage",
    EventDomain.INTEL_GATHER: "A4_espionage",
    EventDomain.SABOTAGE: "A4_espionage",
    EventDomain.COUNTER_SPY: "A4_espionage",
    
    # A7 宗室府
    EventDomain.SUCCESSION: "A7_royal",
    EventDomain.ROYAL_EDUCATION: "A7_royal",
    EventDomain.ROYAL_CONFLICT: "A7_royal",
    
    # A8 国史馆
    EventDomain.CHRONICLE: "A8_history",
    EventDomain.BIOGRAPHY: "A8_history",
}


# Agent→领域反向映射
AGENT_DOMAINS: dict[str, list[EventDomain]] = {}
for domain, owner in DOMAIN_OWNER.items():
    AGENT_DOMAINS.setdefault(owner, []).append(domain)


class ResponsibilityTracker:
    """
    权责追踪器
    
    保证每个事件只被主责Agent处理一次，避免重复计算
    """
    
    def __init__(self):
        # 已处理事件记录: {(round, domain, entity_id): True}
        self._processed: set[tuple] = set()
        # 统计
        self._domain_counts: dict[str, int] = {}
        self._duplicate_prevented: int = 0
    
    def new_round(self):
        """新回合清空记录"""
        self._processed.clear()
    
    def can_process(self, round_num: int, domain: EventDomain, entity_id: str) -> bool:
        """
        检查是否允许处理某事件
        
        同一回合内，同一领域的同一实体只能被处理一次
        """
        key = (round_num, domain.value, entity_id)
        if key in self._processed:
            logger.debug(
                f"[权责追踪] 重复事件已阻止: round={round_num}, "
                f"domain={domain.value}, entity={entity_id}"
            )
            self._duplicate_prevented += 1
            return False
        
        self._processed.add(key)
        self._domain_counts[domain.value] = self._domain_counts.get(domain.value, 0) + 1
        return True
    
    def get_owner(self, domain: EventDomain) -> str:
        """获取某领域的主责Agent"""
        return DOMAIN_OWNER.get(domain, "unknown")
    
    def is_owner(self, agent_id: str, domain: EventDomain) -> bool:
        """检查某Agent是否为该领域的主责"""
        return DOMAIN_OWNER.get(domain) == agent_id
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_events_processed": sum(self._domain_counts.values()),
            "duplicate_prevented": self._duplicate_prevented,
            "domain_counts": dict(self._domain_counts),
        }


# 全局单例
_global_tracker: Optional[ResponsibilityTracker] = None


def get_responsibility_tracker() -> ResponsibilityTracker:
    """获取全局权责追踪器"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ResponsibilityTracker()
        logger.info("全局权责追踪器已初始化")
    return _global_tracker


def reset_responsibility_tracker():
    """重置权责追踪器"""
    global _global_tracker
    _global_tracker = ResponsibilityTracker()
    logger.info("全局权责追踪器已重置")
