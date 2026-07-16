"""
宣战理由（Casus Belli）系统 · 对标 CK3

职责：
1. 定义 CB 类型及其生效条件
2. 校验 CB 是否合法
3. 根据 CB 决定战争目标（war_goal）和分数获取倍率
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("yuanmo.war.casus_belli")


class CasusBelli(Enum):
    """宣战理由类型"""
    CONQUEST = "conquest"               # 征服邻地（最常用）
    RECONQUEST = "reconquest"           # 收复故土（曾属于你）
    SUBJUGATION = "subjugation"         # 附庸征服（强对弱）
    TRADE_WAR = "trade_war"             # 贸易冲突
    HUMILIATION = "humiliation"         # 羞辱（获取声望）
    INDEPENDENCE = "independence"       # 独立战争（附庸反宗主）
    HOLY_WAR = "holy_war"               # 文化/宗教圣战
    BORDER_DISPUTE = "border_dispute"   # 边境争端
    PUNITIVE = "punitive"               # 惩戒（对方背弃盟约/劫掠你）


@dataclass
class CBConfig:
    """单个 CB 的配置"""
    name: str                           # 中文名称
    description: str                    # 描述
    requires_adjacency: bool = True     # 是否需要接壤
    requires_superior_rank: bool = False  # 是否需要排名高于对方
    requires_claimed_tile: bool = False  # 是否需要宣称
    requires_vassal_relation: bool = False  # 是否需要附庸关系
    war_score_multiplier: float = 1.0   # 战争分数获取倍率
    prestige_cost: int = 0              # 宣战声望消耗
    prestige_gain_victory: int = 5      # 胜利声望奖励
    can_seize_territory: bool = True    # 是否可以割地
    can_demand_tribute: bool = False    # 是否可以要求纳贡
    can_enforce_vassal: bool = False    # 是否可以强制附庸
    war_goal_tiles: int = 0             # 战争目标地块数（0=不限）
    defender_war_score_bonus: float = 0.0  # 防守方额外分数加成


# CB 配置表
CB_CONFIG: dict[CasusBelli, CBConfig] = {
    CasusBelli.CONQUEST: CBConfig(
        name="征服邻地",
        description="出兵攻占相邻的敌方领地，以武力开疆拓土。",
        war_score_multiplier=1.0,
        prestige_cost=0,
        prestige_gain_victory=5,
        can_seize_territory=True,
    ),
    CasusBelli.RECONQUEST: CBConfig(
        name="收复故土",
        description="收复被他人占据的祖先故地，师出有名。",
        requires_claimed_tile=True,
        war_score_multiplier=1.3,
        prestige_cost=0,
        prestige_gain_victory=8,
        can_seize_territory=True,
        defender_war_score_bonus=-0.1,  # 防守方在法理上处于劣势
    ),
    CasusBelli.SUBJUGATION: CBConfig(
        name="附庸征服",
        description="以强大军力迫使弱小势力臣服，成为我方附庸。",
        requires_superior_rank=True,
        war_score_multiplier=0.9,
        prestige_cost=10,
        prestige_gain_victory=12,
        can_seize_territory=False,
        can_enforce_vassal=True,
    ),
    CasusBelli.TRADE_WAR: CBConfig(
        name="贸易冲突",
        description="以武力迫使对方开放贸易、赔偿损失。",
        war_score_multiplier=0.8,
        prestige_cost=5,
        prestige_gain_victory=3,
        can_seize_territory=False,
        can_demand_tribute=True,
    ),
    CasusBelli.HUMILIATION: CBConfig(
        name="兴兵问罪",
        description="出兵教训傲慢的邻国，以振国威。",
        war_score_multiplier=0.7,
        prestige_cost=0,
        prestige_gain_victory=15,
        can_seize_territory=False,
    ),
    CasusBelli.INDEPENDENCE: CBConfig(
        name="揭竿而起",
        description="不堪宗主压迫，举兵争取自主。",
        requires_vassal_relation=True,
        requires_adjacency=False,
        war_score_multiplier=1.2,
        prestige_cost=0,
        prestige_gain_victory=10,
        can_seize_territory=False,
        defender_war_score_bonus=0.1,  # 宗主镇压叛乱有法理优势
    ),
    CasusBelli.HOLY_WAR: CBConfig(
        name="圣战讨伐",
        description="以文化/信仰差异为由征伐异族，实为扩张借口。",
        war_score_multiplier=1.1,
        prestige_cost=15,
        prestige_gain_victory=8,
        can_seize_territory=True,
        war_goal_tiles=3,  # 一次圣战最多占3块地
    ),
    CasusBelli.BORDER_DISPUTE: CBConfig(
        name="边境争端",
        description="以边境领土争议为名，夺取争议地块。",
        war_score_multiplier=1.0,
        prestige_cost=3,
        prestige_gain_victory=4,
        can_seize_territory=True,
        war_goal_tiles=1,
    ),
    CasusBelli.PUNITIVE: CBConfig(
        name="惩戒讨伐",
        description="对方背弃盟约/劫掠边境在先，出兵惩戒。",
        requires_adjacency=False,
        war_score_multiplier=1.15,
        prestige_cost=0,
        prestige_gain_victory=6,
        can_seize_territory=True,
        can_demand_tribute=True,
    ),
}


def validate_casus_belli(
    cb: CasusBelli,
    attacker_faction_id: str,
    defender_faction_id: str,
    world_state,
    target_tile_ids: Optional[list[str]] = None,
) -> tuple[bool, str, dict]:
    """
    校验 CB 是否合法

    返回: (valid, reason, context)
      - valid: 是否合法
      - reason: 不合法时的原因
      - context: CB 附加上下文（战争目标地块等）
    """
    from server.models.world_state import FactionState

    cfg = CB_CONFIG.get(cb)
    if not cfg:
        return False, f"未知的宣战理由: {cb.value}", {}

    attacker = world_state.factions.get(attacker_faction_id)
    defender = world_state.factions.get(defender_faction_id)

    if not attacker or not defender:
        return False, "势力不存在", {}

    if not attacker.is_alive or not defender.is_alive:
        return False, "势力已覆灭", {}

    if attacker_faction_id == defender_faction_id:
        return False, "不能对自己宣战", {}

    # 接壤检查
    if cfg.requires_adjacency:
        adjacent = _are_factions_adjacent(world_state, attacker_faction_id, defender_faction_id)
        if not adjacent:
            return False, "双方领地不接壤，无法以此理由宣战", {}

    # 排名检查
    if cfg.requires_superior_rank:
        atk_tiles = attacker.get_tile_count(world_state)
        def_tiles = defender.get_tile_count(world_state)
        if atk_tiles <= def_tiles:
            return False, f"你方势力规模({atk_tiles}块地)不大于对方({def_tiles}块地)，无法以附庸征服为由宣战", {}

    # 宣称检查
    if cfg.requires_claimed_tile:
        claimed_tiles = _get_faction_claims(world_state, attacker_faction_id, defender_faction_id)
        if not claimed_tiles:
            return False, "你没有对对方的法理宣称，无法以收复故土为由宣战", {}
        target_tile_ids = list(claimed_tiles)

    # 附庸关系检查
    if cfg.requires_vassal_relation:
        key = world_state.relation_key(attacker_faction_id, defender_faction_id)
        rel = world_state.relations.get(key)
        if not rel or not rel.vassal_suzerain:
            return False, "你并非对方的附庸，无法以独立战争为由宣战", {}
        # 确认对方是宗主
        if rel.vassal_suzerain.suzerain != defender_faction_id:
            return False, "对方不是你的宗主", {}

    # 声望消耗检查
    if cfg.prestige_cost > 0:
        if attacker.reputation < cfg.prestige_cost:
            return False, f"声望不足（需要{cfg.prestige_cost}，现有{attacker.reputation}）", {}

    context = {
        "cb_type": cb.value,
        "cb_name": cfg.name,
        "war_score_multiplier": cfg.war_score_multiplier,
        "can_seize_territory": cfg.can_seize_territory,
        "can_demand_tribute": cfg.can_demand_tribute,
        "can_enforce_vassal": cfg.can_enforce_vassal,
        "war_goal_tiles": cfg.war_goal_tiles,
        "target_tile_ids": target_tile_ids or [],
    }
    return True, "", context


def deduct_cb_prestige_cost(
    cb: CasusBelli,
    attacker_faction_id: str,
    world_state,
) -> bool:
    """宣战时扣除声望消耗（仅在实际宣战时调用）"""
    cfg = CB_CONFIG.get(cb)
    if not cfg or cfg.prestige_cost <= 0:
        return False
    attacker = world_state.factions.get(attacker_faction_id)
    if not attacker:
        return False
    attacker.reputation = max(0, attacker.reputation - cfg.prestige_cost)
    return True


def _are_factions_adjacent(world_state, faction_a: str, faction_b: str) -> bool:
    """检查两个势力是否领地接壤"""
    tiles_a = {tid for tid, t in world_state.tiles.items() if t.faction_id == faction_a}
    tiles_b = {tid for tid, t in world_state.tiles.items() if t.faction_id == faction_b}
    if not tiles_a or not tiles_b:
        return False
    for tid in tiles_a:
        neighbors = _get_neighbor_ids(world_state, tid)
        if neighbors & tiles_b:
            return True
    return False


def _get_neighbor_ids(world_state, tile_id: str) -> set[str]:
    """获取地块的邻接 ID 集合（兼容邻接矩阵和六边形邻居）"""
    neighbors = set()
    tile = world_state.tiles.get(tile_id)
    if not tile:
        return neighbors

    # 尝试从邻接矩阵获取
    if hasattr(world_state, 'adjacency') and world_state.adjacency:
        neighbors.update(world_state.adjacency.get(tile_id, []))

    # 回退：六边形坐标计算
    if not neighbors and hasattr(tile, 'col') and hasattr(tile, 'row'):
        from server.core.settle_engine import MarchEngine
        for dq, dr in MarchEngine._HEX_DIRECTIONS:
            n_col = tile.col + dq
            n_row = tile.row + dr
            n_key = f"hex_{n_col}_{n_row}"
            if n_key in world_state.tiles:
                neighbors.add(n_key)

    return neighbors


def _get_faction_claims(world_state, faction_id: str, target_faction_id: str) -> set[str]:
    """获取势力对目标势力的法理宣称地块"""
    claimed = set()

    # 方法1：检查 claim_tiles 字段
    faction = world_state.factions.get(faction_id)
    if faction and hasattr(faction, 'claim_tiles') and faction.claim_tiles:
        for tid in faction.claim_tiles:
            tile = world_state.tiles.get(tid)
            if tile and tile.faction_id == target_faction_id:
                claimed.add(tid)

    # 方法2：基于 admin_hierarchy 的法理归属
    if not claimed:
        try:
            from server.map.admin_hierarchy import get_admin_hierarchy
            hierarchy = get_admin_hierarchy()
            for tid, tile in world_state.tiles.items():
                if tile.faction_id != target_faction_id:
                    continue
                de_jure = hierarchy.get(tid, {}).get("de_jure_faction", "")
                if de_jure == faction_id:
                    claimed.add(tid)
        except Exception as e:
            logger.warning(f"法理宣称计算失败: {e}")

    return claimed


def get_available_cb_list(
    world_state, faction_id: str, target_faction_id: str,
) -> list[dict]:
    """获取某个势力对目标势力的所有可用 CB 列表（含合法性）"""
    available = []
    for cb in CasusBelli:
        valid, reason, ctx = validate_casus_belli(
            cb, faction_id, target_faction_id, world_state
        )
        cfg = CB_CONFIG[cb]
        available.append({
            "cb_type": cb.value,
            "name": cfg.name,
            "description": cfg.description,
            "valid": valid,
            "reason": reason if not valid else "",
            "prestige_cost": cfg.prestige_cost,
            "can_seize_territory": cfg.can_seize_territory,
            "can_demand_tribute": cfg.can_demand_tribute,
            "can_enforce_vassal": cfg.can_enforce_vassal,
        })
    return available
