"""
战略 MCTS 搜索器 (Strategic Monte Carlo Tree Search)

基于 autonomous-agent-gaming skill 的 MCTS 模式：
- 四阶段算法：Selection → Expansion → Simulation → Backpropagation
- UCT 公式平衡探索/利用
- 轻量化：使用简化的势力状态模型，不依赖完整 WorldState
- 专注战略决策：不模拟具体战斗细节，只评估方向性选择

用于在 A2 君主决策前进行有限深度的战略树搜索，
输出最优战略方向 + 备选方案排名，注入到 LLM prompt 中提升决策质量。

优化特性（基于 skill 中的 performance_optimizer）：
- 置换表 (Transposition Table)：缓存已评估的战略状态
- 杀手启发 (Killer Heuristic)：优先评估高价值走法
- 时间预算控制：可配置搜索时间上限
"""

from __future__ import annotations
import math
import random
import time
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("yuanmo.agent.strategic_mcts")


# ============================================================
# 战略动作定义
# ============================================================

class StrategicAction(str, Enum):
    """战略动作（简化模型）"""
    EXPAND = "expand"            # 扩张：进攻邻国
    CONSOLIDATE = "consolidate"  # 休整：内政发展
    DIPLOMACY = "diplomacy"     # 外交：结盟/示好
    MOBILIZE = "mobilize"       # 动员：征兵备战
    FORTIFY = "fortify"         # 筑防：加固城防
    RAID = "raid"               # 劫掠：骚扰敌方经济


@dataclass
class StrategicState:
    """简化的战略状态（用于 MCTS 搜索）"""
    faction_id: str
    troops: int = 0
    treasury: int = 0
    grain: int = 0
    tile_count: int = 0
    stability: int = 50          # 0-100
    reputation: int = 50         # 0-100
    allies: list[str] = field(default_factory=list)
    enemies: list[str] = field(default_factory=list)
    neighbor_troops: dict[str, int] = field(default_factory=dict)  # 邻国兵力
    is_terminal: bool = False    # 是否终局（灭亡或统一）
    score: float = 0.0           # 当前估值

    def hash(self) -> str:
        """生成状态哈希（用于置换表）"""
        data = f"{self.faction_id}|{self.troops}|{self.tile_count}|{self.stability}|{len(self.allies)}|{len(self.enemies)}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

    def copy(self) -> "StrategicState":
        return StrategicState(
            faction_id=self.faction_id,
            troops=self.troops,
            treasury=self.treasury,
            grain=self.grain,
            tile_count=self.tile_count,
            stability=self.stability,
            reputation=self.reputation,
            allies=list(self.allies),
            enemies=list(self.enemies),
            neighbor_troops=dict(self.neighbor_troops),
            is_terminal=self.is_terminal,
            score=self.score,
        )


# ============================================================
# MCTS 节点
# ============================================================

@dataclass
class MCTSNode:
    """MCTS 树节点"""
    state: StrategicState
    parent: Optional["MCTSNode"] = None
    action: Optional[StrategicAction] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    total_value: float = 0.0
    untried_actions: list[StrategicAction] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.total_value / self.visits

    def uct_value(self, parent_visits: int, exploration_c: float = 1.414) -> float:
        """UCT 估值：平衡探索与利用"""
        if self.visits == 0:
            return float("inf")  # 未访问节点优先
        exploitation = self.mean_value
        exploration = exploration_c * math.sqrt(math.log(parent_visits) / self.visits)
        return exploitation + exploration

    def best_child(self, exploration_c: float = 1.414) -> "MCTSNode":
        """选择 UCT 值最高的子节点"""
        return max(self.children, key=lambda c: c.uct_value(self.visits, exploration_c))


# ============================================================
# 评估函数
# ============================================================

def evaluate_state(state: StrategicState) -> float:
    """
    战略状态评估函数（启发式）

    综合评估：
    - 军事实力（兵力 × 权重30%）
    - 经济基础（国库+粮草 × 权重25%）
    - 领土规模（地块数 × 权重25%）
    - 稳定度（民心 × 权重15%）
    - 外交态势（盟友-敌人 × 权重5%）
    """
    # 终局处理
    if state.troops <= 0 or state.tile_count <= 0:
        return -1000.0  # 灭亡
    if state.is_terminal:
        return 1000.0    # 统一

    # 归一化评分
    military_score = min(state.troops / 50000, 1.0) * 30
    econ_score = min((state.treasury / 50000 + state.grain / 100000), 1.0) * 25
    territory_score = min(state.tile_count / 500, 1.0) * 25
    stability_score = (state.stability / 100) * 15
    diplomacy_score = (
        (len(state.allies) * 3 - len(state.enemies) * 2) / max(len(state.allies) + len(state.enemies), 1)
    ) * 5

    # 邻国威胁修正：如果邻国兵力远超自身，降低评分
    threat_penalty = 0.0
    for n_troops in state.neighbor_troops.values():
        if n_troops > state.troops * 1.5:
            threat_penalty -= 10

    return military_score + econ_score + territory_score + stability_score + diplomacy_score + threat_penalty


# ============================================================
# 置换表 (Transposition Table)
# ============================================================

class TranspositionTable:
    """置换表：缓存已评估的战略状态"""

    def __init__(self, max_size: int = 10000):
        self._table: dict[str, tuple[float, int]] = {}  # hash → (score, depth)
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def store(self, state_hash: str, score: float, depth: int):
        """存储评估结果"""
        if len(self._table) >= self._max_size:
            # LRU 简化：随机淘汰
            key_to_evict = next(iter(self._table))
            del self._table[key_to_evict]
        self._table[state_hash] = (score, depth)

    def lookup(self, state_hash: str, min_depth: int = 0) -> Optional[float]:
        """查找缓存"""
        entry = self._table.get(state_hash)
        if entry and entry[1] >= min_depth:
            self._hits += 1
            return entry[0]
        self._misses += 1
        return None

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(total, 1)

    def clear(self):
        self._table.clear()
        self._hits = 0
        self._misses = 0


# ============================================================
# 杀手启发 (Killer Heuristic)
# ============================================================

class KillerHeuristic:
    """杀手启发：记录导致剪枝/高分走法的动作"""

    def __init__(self, max_depth: int = 10):
        self._killers: dict[int, list[StrategicAction]] = {d: [] for d in range(max_depth)}
        self._max_per_depth = 2

    def record(self, action: StrategicAction, depth: int):
        """记录杀手走法"""
        killers = self._killers.get(depth, [])
        if action not in killers:
            killers.insert(0, action)
            if len(killers) > self._max_per_depth:
                killers.pop()
        self._killers[depth] = killers

    def get_killers(self, depth: int) -> list[StrategicAction]:
        """获取当前深度的杀手走法"""
        return self._killers.get(depth, [])

    def is_killer(self, action: StrategicAction, depth: int) -> bool:
        return action in self.get_killers(depth)


# ============================================================
# 战略 MCTS 搜索器
# ============================================================

class StrategicMCTS:
    """
    战略 MCTS 搜索器

    用法:
        mcts = StrategicMCTS(iterations=200, max_depth=4)
        result = mcts.search(state)
        print(f"推荐行动: {result['best_action']}, 置信度: {result['confidence']:.2f}")

    典型配置:
        - 高质量搜索: iterations=500, max_depth=6, exploration_c=1.414
        - 快速决策: iterations=100, max_depth=3, exploration_c=2.0
        - 均衡: iterations=200, max_depth=4, exploration_c=1.414 (默认)
    """

    def __init__(
        self,
        iterations: int = 200,
        max_depth: int = 4,
        exploration_c: float = 1.414,
        time_budget_ms: float = 5000,  # 时间预算（毫秒）
    ):
        self.iterations = iterations
        self.max_depth = max_depth
        self.exploration_c = exploration_c
        self.time_budget_ms = time_budget_ms
        self._tt = TranspositionTable()
        self._killers = KillerHeuristic(max_depth)

    def search(self, state: StrategicState) -> dict:
        """
        执行 MCTS 搜索

        Args:
            state: 当前战略状态

        Returns:
            {
                "best_action": 最优行动,
                "action_scores": {action: mean_value, ...},  # 各行动评分
                "confidence": 置信度 (0-1),
                "search_stats": {...},
                "strategy_hint": 策略建议文本
            }
        """
        root = MCTSNode(state=state.copy())
        root.untried_actions = self._get_legal_actions(state)

        if not root.untried_actions:
            return self._empty_result(state)

        start_time = time.time()
        iteration = 0

        for iteration in range(self.iterations):
            # 时间预算检查
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self.time_budget_ms:
                logger.debug(f"[MCTS] 时间预算耗尽 ({elapsed_ms:.0f}ms), 已完成 {iteration} 次迭代")
                break

            # MCTS 四阶段
            node = self._select(root)
            if not self._is_terminal(node.state):
                node = self._expand(node)
            reward = self._simulate(node.state)
            self._backpropagate(node, reward)

        elapsed_ms = (time.time() - start_time) * 1000

        # 提取结果
        if not root.children:
            return self._empty_result(state)

        best_child = root.best_child(exploration_c=0.0)  # 纯利用选择
        action_scores = {
            c.action.value: round(c.mean_value, 2)
            for c in root.children if c.action
        }

        # 置信度 = 最优子节点访问占比
        confidence = best_child.visits / max(root.visits, 1)

        # 策略提示
        strategy_hint = self._action_to_hint(best_child.action, state)

        logger.info(
            f"[MCTS] {state.faction_id}: best={best_child.action.value} "
            f"score={best_child.mean_value:.2f} conf={confidence:.2f} "
            f"iters={iteration+1} time={elapsed_ms:.0f}ms "
            f"TT_hit={self._tt.hit_rate:.1%}"
        )

        return {
            "best_action": best_child.action.value,
            "best_score": round(best_child.mean_value, 2),
            "action_scores": action_scores,
            "action_rankings": sorted(action_scores.items(), key=lambda x: x[1], reverse=True),
            "confidence": round(confidence, 3),
            "strategy_hint": strategy_hint,
            "search_stats": {
                "iterations": iteration + 1,
                "time_ms": round(elapsed_ms, 0),
                "root_visits": root.visits,
                "tt_hit_rate": round(self._tt.hit_rate, 3),
                "max_depth": self.max_depth,
            },
        }

    def _select(self, node: MCTSNode) -> MCTSNode:
        """选择阶段：沿UCT值最高的路径下降到叶节点"""
        depth = 0
        current = node
        while current.children and not current.untried_actions:
            current = current.best_child(self.exploration_c)
            depth += 1
            if depth > self.max_depth:
                break
        return current

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """扩展阶段：从未尝试动作中选一个展开"""
        if not node.untried_actions:
            return node

        # 杀手启发：优先尝试杀手走法
        depth = self._node_depth(node)
        killers = self._killers.get_killers(depth)
        for killer in killers:
            if killer in node.untried_actions:
                action = killer
                node.untried_actions.remove(action)
                break
        else:
            action = random.choice(node.untried_actions)
            node.untried_actions.remove(action)

        # 模拟动作后的状态
        new_state = self._apply_action(node.state, action)
        child = MCTSNode(state=new_state, parent=node, action=action)
        child.untried_actions = self._get_legal_actions(new_state)
        node.children.append(child)
        return child

    def _simulate(self, state: StrategicState) -> float:
        """模拟阶段：快速随机走子到终局或最大深度"""
        # 先查置换表
        cached = self._tt.lookup(state.hash(), min_depth=1)
        if cached is not None:
            return cached

        current = state.copy()
        sim_depth = 0

        while not self._is_terminal(current) and sim_depth < self.max_depth:
            actions = self._get_legal_actions(current)
            if not actions:
                break
            # 带启发式的随机选择（偏好高分动作）
            action = self._biased_random_action(actions, current)
            current = self._apply_action(current, action)
            sim_depth += 1

        score = evaluate_state(current)
        self._tt.store(state.hash(), score, sim_depth)
        return score

    def _backpropagate(self, node: MCTSNode, reward: float):
        """回传阶段：将模拟结果沿路径回传"""
        current = node
        while current:
            current.visits += 1
            current.total_value += reward
            # 杀手启发：记录高回报走法
            if current.parent and current.action and reward > 50:
                depth = self._node_depth(current)
                self._killers.record(current.action, depth)
            current = current.parent

    def _get_legal_actions(self, state: StrategicState) -> list[StrategicAction]:
        """获取合法动作"""
        actions = []

        # 有邻国 → 可扩张
        if state.neighbor_troops:
            actions.append(StrategicAction.EXPAND)

        # 有邻国 → 可劫掠
        if state.neighbor_troops and state.troops > 5000:
            actions.append(StrategicAction.RAID)

        # 兵力不足 → 可征兵
        if state.troops < 50000:
            actions.append(StrategicAction.MOBILIZE)

        # 国库有余 → 可筑防
        if state.treasury > 5000:
            actions.append(StrategicAction.FORTIFY)

        # 有邻国无盟友 → 可外交
        if state.neighbor_troops and len(state.allies) < len(state.neighbor_troops):
            actions.append(StrategicAction.DIPLOMACY)

        # 始终可休整
        actions.append(StrategicAction.CONSOLIDATE)

        return actions

    def _apply_action(self, state: StrategicState, action: StrategicAction) -> StrategicState:
        """模拟动作效果（简化模型）"""
        new = state.copy()

        if action == StrategicAction.EXPAND:
            # 扩张：消耗兵力，增加地盘
            new.troops = int(state.troops * 0.85)
            new.tile_count = int(state.tile_count * 1.15)
            new.treasury = max(0, state.treasury - 3000)
            new.grain = max(0, state.grain - 5000)
            new.stability = max(0, state.stability - 3)
            # 增加敌人
            if state.neighbor_troops:
                weakest = min(state.neighbor_troops, key=state.neighbor_troops.get)
                if weakest not in new.enemies:
                    new.enemies.append(weakest)

        elif action == StrategicAction.CONSOLIDATE:
            new.treasury = int(state.treasury * 1.1)
            new.grain = int(state.grain * 1.15)
            new.stability = min(100, state.stability + 5)

        elif action == StrategicAction.MOBILIZE:
            new.troops = int(state.troops * 1.2)
            new.treasury = max(0, state.treasury - 8000)
            new.grain = max(0, state.grain - 3000)

        elif action == StrategicAction.FORTIFY:
            new.treasury = max(0, state.treasury - 5000)
            new.stability = min(100, state.stability + 8)
            new.reputation = min(100, state.reputation + 2)

        elif action == StrategicAction.DIPLOMACY:
            new.treasury = max(0, state.treasury - 2000)
            # 假设外交成功：获得一个盟友
            if state.neighbor_troops:
                potential_ally = list(state.neighbor_troops.keys())[0]
                if potential_ally not in new.allies and potential_ally not in new.enemies:
                    new.allies.append(potential_ally)
            new.reputation = min(100, state.reputation + 5)

        elif action == StrategicAction.RAID:
            new.troops = int(state.troops * 0.95)
            new.treasury = int(state.treasury * 1.15)
            new.grain = int(state.grain * 1.1)
            new.stability = max(0, state.stability - 5)
            new.reputation = max(0, state.reputation - 8)

        return new

    def _is_terminal(self, state: StrategicState) -> bool:
        """检查是否终局"""
        return state.is_terminal or state.troops <= 0 or state.tile_count <= 0

    def _node_depth(self, node: MCTSNode) -> int:
        """计算节点深度"""
        depth = 0
        current = node
        while current.parent:
            depth += 1
            current = current.parent
        return depth

    def _biased_random_action(
        self, actions: list[StrategicAction], state: StrategicState
    ) -> StrategicAction:
        """带启发式的随机动作选择"""
        # 对不同动作赋予不同权重
        weights = {
            StrategicAction.EXPAND: 3.0 if state.troops > 10000 else 1.0,
            StrategicAction.CONSOLIDATE: 2.0 if state.stability < 40 else 1.0,
            StrategicAction.MOBILIZE: 2.5 if state.troops < 15000 else 1.0,
            StrategicAction.DIPLOMACY: 2.0 if state.troops < 20000 else 1.0,
            StrategicAction.FORTIFY: 2.0 if state.treasury > 10000 else 0.5,
            StrategicAction.RAID: 1.5 if state.grain < 5000 else 0.5,
        }
        total = sum(weights.get(a, 1.0) for a in actions)
        r = random.random() * total
        cumsum = 0.0
        for a in actions:
            cumsum += weights.get(a, 1.0)
            if r <= cumsum:
                return a
        return actions[-1]

    def _action_to_hint(self, action: Optional[StrategicAction], state: StrategicState) -> str:
        """将动作转化为策略建议文本"""
        hints = {
            StrategicAction.EXPAND: "当趁势扩张，攻取邻国薄弱之处，扩大疆土。",
            StrategicAction.CONSOLIDATE: "当休养生息，发展内政，稳固根基以待时机。",
            StrategicAction.MOBILIZE: "当广募兵勇，扩充军力，为日后征战做准备。",
            StrategicAction.DIPLOMACY: "当遣使交好，结盟强邻，以外交化解兵戈之危。",
            StrategicAction.FORTIFY: "当加固城防，筑垒自守，以图长久之计。",
            StrategicAction.RAID: "当遣轻骑劫掠敌境，以战养战，缓解粮饷之困。",
        }
        return hints.get(action, "静观其变，随机应变。")

    def _empty_result(self, state: StrategicState) -> dict:
        return {
            "best_action": StrategicAction.CONSOLIDATE.value,
            "best_score": 0.0,
            "action_scores": {StrategicAction.CONSOLIDATE.value: 0.0},
            "action_rankings": [(StrategicAction.CONSOLIDATE.value, 0.0)],
            "confidence": 0.0,
            "strategy_hint": "无可用行动，保持现状。",
            "search_stats": {"iterations": 0, "time_ms": 0, "root_visits": 0, "tt_hit_rate": 0.0, "max_depth": 0},
        }

    def reset(self):
        """重置搜索器状态（新游戏）"""
        self._tt.clear()
        self._killers = KillerHeuristic(self.max_depth)


# ============================================================
# 全局单例与工厂函数
# ============================================================

_global_mcts: Optional[StrategicMCTS] = None


def get_strategic_mcts(
    quality: str = "balanced"
) -> StrategicMCTS:
    """
    获取战略 MCTS 搜索器

    Args:
        quality: 搜索质量 - "fast"(快速) / "balanced"(均衡) / "high"(高质量)

    Returns:
        StrategicMCTS 实例
    """
    global _global_mcts
    configs = {
        "fast": {"iterations": 80, "max_depth": 3, "exploration_c": 2.0, "time_budget_ms": 2000},
        "balanced": {"iterations": 200, "max_depth": 4, "exploration_c": 1.414, "time_budget_ms": 5000},
        "high": {"iterations": 500, "max_depth": 6, "exploration_c": 1.414, "time_budget_ms": 10000},
    }
    cfg = configs.get(quality, configs["balanced"])
    if _global_mcts is None:
        _global_mcts = StrategicMCTS(**cfg)
    return _global_mcts


def reset_strategic_mcts():
    """重置战略 MCTS"""
    global _global_mcts
    if _global_mcts:
        _global_mcts.reset()
    _global_mcts = None


def strategic_state_from_world(
    faction_id: str, world_state: dict
) -> StrategicState:
    """
    从世界状态快照构建简化的战略状态

    Args:
        faction_id: 势力ID
        world_state: 世界状态快照

    Returns:
        StrategicState 实例
    """
    factions = world_state.get("factions", {})
    faction = factions.get(faction_id, {})

    # 基础属性
    troops = faction.get("troops", 0)
    treasury = faction.get("treasury", 0)
    grain = faction.get("grain", 0)
    tile_count = faction.get("tile_count", 0)
    stability = faction.get("realm_stability", faction.get("stability", 50))
    reputation = faction.get("reputation", 50)

    # 外交关系
    allies = []
    enemies = []
    relations = world_state.get("diplomatic_relations", {})
    for other_id, rel in relations.items():
        if other_id == faction_id:
            continue
        rel_type = rel.get("type", "") if isinstance(rel, dict) else ""
        if rel_type in ("ally", "alliance"):
            allies.append(other_id)
        elif rel_type in ("war", "hostile"):
            enemies.append(other_id)

    # 邻国兵力
    neighbor_troops = {}
    neighbors = faction.get("neighbors", [])
    for nid in neighbors:
        nf = factions.get(nid, {})
        if nf.get("alive", True):
            neighbor_troops[nid] = nf.get("troops", 0)

    return StrategicState(
        faction_id=faction_id,
        troops=troops,
        treasury=treasury,
        grain=grain,
        tile_count=tile_count,
        stability=stability,
        reputation=reputation,
        allies=allies,
        enemies=enemies,
        neighbor_troops=neighbor_troops,
    )
