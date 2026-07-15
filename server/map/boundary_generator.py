"""
行政区划边界线生成器 v4.1 - 两级边界 (行省 + 路) + 势力边界

按沙盘地图系统文档 v3.0 重构:
- 行省界 + 路界 + 势力边界三级边界系统
- 府州级边界 = 六边形格线本身, 无需单独渲染
- 适配府州级网格 (32行×42列)
- 边界线在前端按缩放级别切换显示
"""

from __future__ import annotations
import json
import math
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from server.map.hex_grid import (
    GRID_ROWS, GRID_MAX_COLS, DEFAULT_HEX_SIZE,
    HexCoord, iter_all_coords,
    offset_to_pixel, hex_corners_flat_top,
)


def _calc_edge_midpoint(
    c1: HexCoord, c2: HexCoord,
    hex_size: float = DEFAULT_HEX_SIZE,
) -> tuple[float, float]:
    """计算两个相邻六边形共享边的中点像素坐标"""
    px1, py1 = offset_to_pixel(c1.col, c1.row, hex_size)
    px2, py2 = offset_to_pixel(c2.col, c2.row, hex_size)
    return ((px1 + px2) / 2, (py1 + py2) / 2)


def generate_boundaries(
    tile_province_map: Dict[str, str],
    tile_circuit_map: Dict[str, str],
    tile_faction_map: Dict[str, str] = None,
) -> dict:
    """
    生成两级行政边界 + 势力边界

    Returns:
        {
            "province_boundaries": [(px, py), ...],
            "circuit_boundaries": [(px, py), ...],
            "faction_boundaries": [(px, py, type), ...],
        }
    """
    province_points: List[tuple[float, float]] = []
    circuit_points: List[tuple[float, float]] = []
    faction_points: List[tuple[float, float, str]] = []

    # 遍历所有相邻对
    processed_pairs: Set[Tuple[str, str]] = set()

    for coord in iter_all_coords():
        tile_id = coord.to_key()

        for neighbor in coord.neighbors():
            n_id = neighbor.to_key()

            # 去重
            pair_key = tuple(sorted([tile_id, n_id]))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            # 计算中点
            mx, my = _calc_edge_midpoint(coord, neighbor)

            # 省边界
            prov_a = tile_province_map.get(tile_id, "")
            prov_b = tile_province_map.get(n_id, "")
            if prov_a != prov_b:
                province_points.append((mx, my))

            # 路边界
            circ_a = tile_circuit_map.get(tile_id, "")
            circ_b = tile_circuit_map.get(n_id, "")
            if circ_a != circ_b and prov_a == prov_b:
                # 只在同省内不同路之间画边界
                circuit_points.append((mx, my))

            # 势力边界
            if tile_faction_map:
                fac_a = tile_faction_map.get(tile_id, "")
                fac_b = tile_faction_map.get(n_id, "")
                if fac_a != fac_b and fac_a and fac_b:
                    faction_points.append((mx, my, "minor"))

    result = {
        "province_boundaries": province_points,
        "circuit_boundaries": circuit_points,
    }

    if tile_faction_map:
        result["faction_boundaries"] = [
            {"x": x, "y": y, "type": t} for x, y, t in faction_points
        ]

    return result


# ============================================================
# 行省轮廓线 (可选 - 用于世界地图视图)
# ============================================================

def _gift_wrapping(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Gift Wrapping 凸包算法"""
    if len(points) < 3:
        return points

    pts = list(set(points))
    hull: List[Tuple[float, float]] = []

    # 找到最左点
    leftmost = min(pts, key=lambda p: p[0])
    current = leftmost

    max_iterations = len(pts) * 3  # 安全上限：防止全共线点无限循环
    iteration_count = 0

    while True:
        iteration_count += 1
        if iteration_count > max_iterations:
            break  # 安全退出：所有点共线时返回已收集的线段

        hull.append(current)
        candidate = pts[0]

        for p in pts:
            if candidate == current:
                candidate = p
                continue
            # 叉积判断方向
            cross = ((candidate[0] - current[0]) * (p[1] - current[1]) -
                     (candidate[1] - current[1]) * (p[0] - current[0]))
            if cross < 0:
                candidate = p
            elif cross == 0:
                d1 = ((candidate[0] - current[0]) ** 2 +
                      (candidate[1] - current[1]) ** 2)
                d2 = ((p[0] - current[0]) ** 2 +
                      (p[1] - current[1]) ** 2)
                if d2 > d1:
                    candidate = p

        current = candidate
        if current == hull[0]:
            break

    return hull


def generate_province_outlines(
    boundary_points: List[Tuple[float, float]],
    simplify: bool = True,
) -> List[Tuple[float, float]]:
    """从行省边界散点生成轮廓线 (凸包)"""
    return _gift_wrapping(boundary_points)


# ============================================================
# 导出
# ============================================================

def export_boundary_json(
    boundaries: dict,
    output_path: str = "server/data/map/boundaries.json",
):
    """导出边界配置 JSON (两级)"""
    province_count = len(boundaries.get("province_boundaries", []))
    circuit_count = len(boundaries.get("circuit_boundaries", []))
    faction_count = len(boundaries.get("faction_boundaries", []))

    output = {
        "version": "4.1",
        "levels": ["province", "circuit"],  # 两级边界
        "meta": {
            "province_border_points": province_count,
            "circuit_border_points": circuit_count,
            "faction_border_points": faction_count,
            "hex_size": int(DEFAULT_HEX_SIZE),
        },
        **boundaries,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [边界] 导出完成: {output_path}")
    print(f"    - 行省边界点: {province_count}")
    print(f"    - 路边界点: {circuit_count}")
    print(f"    - 势力边界点: {faction_count}")
