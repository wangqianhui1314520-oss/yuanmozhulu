"""
六边形网格寻路与连通性检测工具

功能:
1. A* 寻路 - 带移动代价的地块间最短路径
2. 领土补给连通性检测 - 判断两个地块是否在同一连通区域内
3. BFS 连通分量分析 - 获取某势力所有连通领土块
4. 距离计算 - 两地块间最短六边形距离
"""

from __future__ import annotations
import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from server.map.hex_grid import HexCoord, iter_all_coords, TOTAL_TILES


# ============================================================
# 数据结构
# ============================================================

@dataclass(order=True)
class _PriorityItem:
    """A* 优先队列项"""
    f_score: float
    coord: HexCoord = field(compare=False)


@dataclass
class PathResult:
    """寻路结果"""
    path: list[HexCoord]        # 路径坐标列表 (含起点和终点)
    cost: float                  # 总移动代价
    steps: int                   # 步数
    found: bool                  # 是否找到路径


@dataclass
class ConnectivityResult:
    """连通性检测结果"""
    connected: bool              # 是否连通
    component_size: int          # 连通分量大小
    component_tiles: list[str]   # 连通分量中的所有格子键


# ============================================================
# 辅助函数
# ============================================================

def _parse_tile_key(key: str) -> tuple[int, int]:
    """解析 tile key，兼容两种格式:
    - "col,row" (邻接表格式)
    - "hex_col_row" (tile_id 格式)
    """
    if key.startswith("hex_"):
        parts = key[4:].split("_")
        return int(parts[0]), int(parts[1])
    else:
        parts = key.split(",")
        return int(parts[0]), int(parts[1])


def _tile_key_to_offset_key(key: str) -> str:
    """将 hex_col_row 转换为 col,row 格式"""
    if key.startswith("hex_"):
        parts = key[4:].split("_")
        return f"{parts[0]},{parts[1]}"
    return key


# ============================================================
# A* 寻路
# ============================================================

def a_star_pathfind(
    start: HexCoord,
    end: HexCoord,
    blocked: set[str] | None = None,
    move_costs: dict[str, float] | None = None,
    max_steps: int = 500,
) -> PathResult:
    """
    A* 寻路算法 (六边形网格)
    
    Args:
        start: 起点坐标
        end: 终点坐标
        blocked: 不可通行格子键集合 {"col,row", ...}
        move_costs: 各格子移动代价 {"col,row": cost, ...}，默认每步代价=1
        max_steps: 最大搜索步数限制
    
    Returns:
        PathResult 包含路径、代价、步数和是否成功
    """
    blocked = blocked or set()
    move_costs = move_costs or {}
    
    start_key = start.to_key()
    end_key = end.to_key()
    
    # 起点/终点被阻挡
    if start_key in blocked or end_key in blocked:
        return PathResult(path=[], cost=float('inf'), steps=0, found=False)
    
    # 起点=终点
    if start_key == end_key:
        return PathResult(path=[start], cost=0.0, steps=0, found=True)
    
    # A* 核心
    open_set: list[_PriorityItem] = []
    heapq.heappush(open_set, _PriorityItem(
        f_score=start.distance_to(end),
        coord=start,
    ))
    
    came_from: dict[str, str] = {}
    g_score: dict[str, float] = {start_key: 0.0}
    
    while open_set:
        if len(came_from) > max_steps:
            break
        
        current_item = heapq.heappop(open_set)
        current = current_item.coord
        current_key = current.to_key()
        
        if current_key == end_key:
            # 重建路径
            path = _reconstruct_path(came_from, current_key, start_key)
            return PathResult(
                path=path,
                cost=g_score[current_key],
                steps=len(path) - 1,
                found=True,
            )
        
        current_g = g_score.get(current_key, float('inf'))
        
        for neighbor in current.neighbors():
            n_key = neighbor.to_key()
            if n_key in blocked:
                continue
            
            # 移动代价
            step_cost = move_costs.get(n_key, 1.0)
            tentative_g = current_g + step_cost
            
            if tentative_g < g_score.get(n_key, float('inf')):
                came_from[n_key] = current_key
                g_score[n_key] = tentative_g
                f_score = tentative_g + neighbor.distance_to(end)
                heapq.heappush(open_set, _PriorityItem(f_score=f_score, coord=neighbor))
    
    return PathResult(path=[], cost=float('inf'), steps=0, found=False)


def _reconstruct_path(came_from: dict[str, str], end_key: str, start_key: str) -> list[HexCoord]:
    """从 came_from 字典重建路径"""
    path_keys = [end_key]
    current = end_key
    while current != start_key:
        current = came_from[current]
        path_keys.append(current)
    path_keys.reverse()
    
    path = []
    for key in path_keys:
        parts = key.split(",")
        path.append(HexCoord(col=int(parts[0]), row=int(parts[1])))
    return path


# ============================================================
# 领土补给连通性检测
# ============================================================

def check_supply_connectivity(
    tile_a_key: str,
    tile_b_key: str,
    faction_tiles: set[str],
    blocked: set[str] | None = None,
) -> ConnectivityResult:
    """
    检测两个地块是否在同一势力连通领土内 (补给线检测)
    
    规则: 两个地块必须通过连续的本势力领土相连才算补给连通。
    
    Args:
        tile_a_key: 地块A键
        tile_b_key: 地块B键
        faction_tiles: 该势力所有领地格子键集合
        blocked: 额外阻挡 (如敌军占领、围城等)
    
    Returns:
        ConnectivityResult
    """
    blocked = blocked or set()
    
    # 统一格式: 将 faction_tiles 和 blocked 都标准化为 col,row 格式
    normalized_faction = {_tile_key_to_offset_key(k) for k in faction_tiles}
    normalized_blocked = {_tile_key_to_offset_key(k) for k in (blocked or set())}
    a_key = _tile_key_to_offset_key(tile_a_key)
    b_key = _tile_key_to_offset_key(tile_b_key)
    
    if a_key not in normalized_faction or b_key not in normalized_faction:
        return ConnectivityResult(connected=False, component_size=0, component_tiles=[])
    
    if a_key == b_key:
        return ConnectivityResult(connected=True, component_size=1, component_tiles=[tile_a_key])
    
    # BFS 从 tile_a 出发，只走 faction_tiles 中的格子
    visited = {a_key}
    queue = deque([a_key])
    
    while queue:
        current = queue.popleft()
        if current == b_key:
            return ConnectivityResult(
                connected=True,
                component_size=len(visited),
                component_tiles=sorted(visited),
            )
        
        col, row = _parse_tile_key(current)
        coord = HexCoord(col, row)
        
        for neighbor in coord.neighbors():
            n_key = neighbor.to_key()
            if n_key in visited:
                continue
            if n_key in normalized_blocked:
                continue
            if n_key not in normalized_faction:
                continue
            visited.add(n_key)
            queue.append(n_key)
    
    return ConnectivityResult(
        connected=False,
        component_size=len(visited),
        component_tiles=sorted(visited),
    )


# ============================================================
# 连通分量分析
# ============================================================

def find_connected_components(
    faction_tiles: set[str],
    blocked: set[str] | None = None,
) -> list[list[str]]:
    """
    获取某势力所有连通领土块
    
    返回按大小降序排列的连通分量列表。
    第一块为主领土，后续为飞地。
    
    Args:
        faction_tiles: 势力所有领地 (兼容 hex_ 和 col,row 两种格式)
        blocked: 额外阻挡
    
    Returns:
        [[tile_key, ...], ...] 各连通分量
    """
    normalized_blocked = {_tile_key_to_offset_key(k) for k in (blocked or set())}
    normalized_faction = {_tile_key_to_offset_key(k) for k in faction_tiles}
    
    unvisited = normalized_faction - normalized_blocked
    components = []
    
    while unvisited:
        # 从任意未访问格子开始BFS
        start = unvisited.pop()
        component = {start}
        queue = deque([start])
        
        while queue:
            current = queue.popleft()
            col, row = _parse_tile_key(current)
            coord = HexCoord(col, row)
            
            for neighbor in coord.neighbors():
                n_key = neighbor.to_key()
                if n_key in component:
                    continue
                if n_key in normalized_blocked:
                    continue
                if n_key not in normalized_faction:
                    continue
                if n_key in unvisited:
                    unvisited.discard(n_key)
                component.add(n_key)
                queue.append(n_key)
        
        components.append(sorted(component))
    
    # 按大小降序
    components.sort(key=len, reverse=True)
    return components


def is_territory_contiguous(faction_tiles: set[str]) -> bool:
    """检测势力领土是否完全连通 (无飞地)"""
    components = find_connected_components(faction_tiles)
    return len(components) <= 1


def find_enclaves(faction_tiles: set[str]) -> list[list[str]]:
    """找出所有飞地 (非主领土的连通块)"""
    components = find_connected_components(faction_tiles)
    return components[1:] if len(components) > 1 else []


# ============================================================
# 批量距离计算
# ============================================================

def hex_distance_batch(
    origin: HexCoord,
    targets: list[HexCoord],
) -> list[tuple[HexCoord, int]]:
    """
    计算原点到一组目标点的距离
    
    Returns:
        [(target, distance), ...] 按距离升序排列
    """
    results = [(t, origin.distance_to(t)) for t in targets]
    results.sort(key=lambda x: x[1])
    return results


def find_nearest_faction_tile(
    coord: HexCoord,
    faction_tiles: set[str],
) -> tuple[Optional[HexCoord], int]:
    """
    找到距离指定坐标最近的势力领土
    
    Returns:
        (nearest_coord, distance) 或 (None, inf)
    """
    if not faction_tiles:
        return None, float('inf')
    
    best_coord = None
    best_dist = float('inf')
    
    for key in faction_tiles:
        col, row = _parse_tile_key(key)
        target = HexCoord(col, row)
        dist = coord.distance_to(target)
        if dist < best_dist:
            best_dist = dist
            best_coord = target
    
    return best_coord, int(best_dist)


# ============================================================
# 行军路径验证
# ============================================================

def validate_march_path(
    path: list[HexCoord],
    faction_tiles: set[str],
    blocked: set[str] | None = None,
) -> tuple[bool, str]:
    """
    验证行军路径合法性
    
    规则:
    1. 起点必须在己方领土内
    2. 每一步必须在己方领土或中立/敌军领土 (但不能在 blocked 格子)
    3. 路径必须连续 (相邻)
    
    Returns:
        (is_valid, reason)
    """
    blocked = blocked or set()
    normalized_blocked = {_tile_key_to_offset_key(k) for k in blocked}
    normalized_faction = {_tile_key_to_offset_key(k) for k in faction_tiles}
    
    if not path:
        return False, "路径为空"
    
    if len(path) == 1:
        return True, "原地不动"
    
    # 起点必须在己方领土
    if path[0].to_key() not in normalized_faction:
        return False, f"起点 {path[0]} 不在己方领土内"
    
    # 检查每一步
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        a_key, b_key = a.to_key(), b.to_key()
        
        # 检查相邻性
        if b_key not in [n.to_key() for n in a.neighbors()]:
            return False, f"第{i+1}步: {a} → {b} 不相邻"
        
        # 检查阻挡
        if b_key in normalized_blocked:
            return False, f"第{i+1}步: {b} 被阻挡"
    
    return True, "合法路径"
