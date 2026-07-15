"""
邻接表生成器 v4.1 - 府州级六向邻接关系

为每个格子预计算完整的邻居列表，输出标准化邻接表 JSON。
"""

from __future__ import annotations
import json
from pathlib import Path
from server.map.hex_grid import (
    HexCoord, iter_all_coords, get_row_width,
    GRID_ROWS, GRID_MAX_COLS, GRID_ODD_COLS,
    TOTAL_TILES, TOTAL_TILES_RECT,
)


def build_adjacency_table(tile_set: set = None) -> dict[str, list[str]]:
    """
    构建完整邻接表

    Args:
        tile_set: 可选 - 要包含的 tile 集合 {(col, row), ...}
                  如果不提供, 使用 iter_all_coords() (可能不含疆域过滤)

    Returns:
        { "col,row": ["col,row", ...] }
    """
    adj = {}
    if tile_set is not None:
        # 使用显式 tile 集合
        from server.map.hex_grid import HexCoord
        for col, row in tile_set:
            coord = HexCoord(col, row)
            key = coord.to_key()
            neighbors = coord.neighbors(territory_only=True)
            # 进一步过滤：邻居也必须在 tile_set 内
            adj[key] = [n.to_key() for n in neighbors
                       if (n.col, n.row) in tile_set]
    else:
        for coord in iter_all_coords():
            key = coord.to_key()
            neighbors = coord.neighbors()
            adj[key] = [n.to_key() for n in neighbors]

    total = len(adj)
    print(f"  邻接表生成完成: {total} 个格子")

    neighbor_counts = {}
    for key, nbrs in adj.items():
        cnt = len(nbrs)
        neighbor_counts[cnt] = neighbor_counts.get(cnt, 0) + 1

    for cnt in sorted(neighbor_counts.keys()):
        print(f"    {cnt} 邻居: {neighbor_counts[cnt]} 个格子")

    return adj


def build_adjacency_matrix() -> list[list[int]]:
    """构建邻接矩阵 (用于快速图算法)"""
    all_coords = list(iter_all_coords())
    coord_to_idx = {c.to_key(): i for i, c in enumerate(all_coords)}

    matrix = []
    for coord in all_coords:
        neighbors = coord.neighbors()
        neighbor_indices = [coord_to_idx[n.to_key()] for n in neighbors]
        matrix.append(neighbor_indices)

    return matrix


def export_adjacency_json(
    adj: dict[str, list[str]] = None,
    output_path: str = "server/data/map/adjacency.json",
) -> dict:
    """
    导出邻接表为 JSON

    Args:
        adj: 已构建的邻接表 (如不提供则重新构建)
        output_path: 输出路径
    """
    if adj is None:
        adj = build_adjacency_table()

    data = {
        "meta": {
            "total_tiles": len(adj),
            "grid_rows": GRID_ROWS,
            "grid_max_cols": GRID_MAX_COLS,
            "grid_odd_cols": GRID_ODD_COLS,
            "stagger_axis": "X",
            "stagger_index": "Odd",
            "hex_orientation": "Flat-Top",
            "coordinate_system": "Offset (col, row)",
            "hex_size": 72,
            "description": "文明6风格六边形网格邻接表 - 府州级东亚全域",
        },
        "adjacency": adj,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  邻接表已导出: {output_path}")
    return data
