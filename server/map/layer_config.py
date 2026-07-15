"""
地图图层系统配置 v4.1 - 三级缩放 + 6层图层 (行省/路/府州)

按沙盘地图系统文档 v3.0:
- 6 层图层 (从底到顶): 地形底色→势力着色→行政边界→疆域迷雾→战略标记→六边形网格
- 三级缩放: world(0.25~0.55x) → circuit(0.50~0.90x) → prefecture(0.85~3.50x)
- 势力ID体系: 统一 faction_ 前缀 (9势力)
"""

from __future__ import annotations
import json
from typing import Dict, List, Any

from server.map.hex_grid import GRID_ROWS, GRID_MAX_COLS, DEFAULT_HEX_SIZE


# ============================================================
# 6层图层定义 (按文档 3.9 节规范)
# ============================================================

LAYER_DEFINITIONS: List[Dict[str, Any]] = [
    # [1] 地形底色 — 陆地地形颜色填充
    {
        "key": "terrain",
        "name": "地形底色",
        "type": "fill",
        "z_index": 0,
        "default_visible": True,
        "colors": {
            "flatland": "#C8A96E",
            "mountain": "#8B7355",
            "hill": "#A0906E",
            "forest": "#2D5A27",
            "wetland": "#4A7C59",
            "desert": "#D4B896",
            "coastal": "#A8C8A0",
            "steppe": "#B5B84C",
            "taiga": "#3D5C3A",
            "oasis": "#6B8E4E",
            "water_river": "#4A90D9",
            "water_lake": "#3A7CC3",
            "sea": "#284458",
            "unknown": "#808080",
        },
        "stroke": {"color": "#333333", "width": 0.5},
    },
    # [2] 势力着色 — 当前实际控制势力颜色覆盖
    {
        "key": "faction",
        "name": "势力着色",
        "type": "fill",
        "z_index": 1,
        "default_visible": True,
    },
    # [3] 行政边界 — 行省界 + 路界
    {
        "key": "admin_boundary",
        "name": "行政边界",
        "type": "line",
        "z_index": 2,
        "default_visible": True,
        "levels": {
            "province": {
                "name": "行省边界",
                "color": "#FF4444",
                "line_width": 3,
                "dash": [8, 4],
            },
            "circuit": {
                "name": "路边界",
                "color": "#FFAA00",
                "line_width": 2,
                "dash": [4, 4],
            },
        },
    },
    # [4] 疆域迷雾 — 战争迷雾/视野系统
    {
        "key": "fog",
        "name": "疆域迷雾",
        "type": "overlay",
        "z_index": 3,
        "default_visible": True,
        "config": {
            "color": "rgba(0,0,0,0.6)",
            "explore_radius": 2,
            "capital_vision": 4,
            "faction_shared_vision": True,
            "permanent": False,
        },
    },
    # [5] 战略标记 — 首都/港口/关隘/渡口/战略据点
    {
        "key": "strategic",
        "name": "战略标记",
        "type": "marker",
        "z_index": 4,
        "default_visible": True,
        "icons": {
            "capital":   {"symbol": "★", "color": "#FFD700", "size": 22},
            "port":      {"symbol": "◎", "color": "#4FC3F7", "size": 16},
            "pass":      {"symbol": "▲", "color": "#FF8A65", "size": 16},
            "ferry":     {"symbol": "~", "color": "#81C784", "size": 14},
            "strategic": {"symbol": "●", "color": "#FFD54F", "size": 14},
        },
    },
    # [6] 六边形网格 — 格子边框
    {
        "key": "hex_grid",
        "name": "六边形网格",
        "type": "line",
        "z_index": 5,
        "default_visible": True,
        "stroke": {"color": "#555555", "width": 0.5},
    },
]


# ============================================================
# 三级缩放配置 (按文档 3.9 节规范)
# ============================================================

ADMIN_ZOOM_CONFIG: List[Dict[str, Any]] = [
    {
        "key": "world",
        "name": "天下大势",
        "admin_level": "province",
        "min_scale": 0.25,
        "max_scale": 0.55,
        "show_boundaries": ["province"],
        "show_labels": ["province"],
        "show_markers": ["capital"],
    },
    {
        "key": "circuit",
        "name": "各路形势",
        "admin_level": "circuit",
        "min_scale": 0.50,
        "max_scale": 0.90,
        "show_boundaries": ["province", "circuit"],
        "show_labels": ["province", "circuit"],
        "show_markers": ["capital", "port", "pass"],
    },
    {
        "key": "prefecture",
        "name": "府州详情",
        "admin_level": "prefecture",
        "min_scale": 0.85,
        "max_scale": 3.50,
        "show_boundaries": ["province", "circuit"],
        "show_labels": ["province", "circuit", "prefecture"],
        "show_markers": ["capital", "port", "pass", "ferry", "strategic"],
    },
]


# ============================================================
# 势力图层配色 (内部使用，前端渲染通过 faction_colors 字段获取)
# ============================================================

FACTION_LAYER_COLORS: Dict[str, Dict[str, Any]] = {
    "faction_yuan":          {"fill": "#8B0000", "border": "#FF4444", "fill_opacity": 0.35},
    "faction_xushouhui":     {"fill": "#B8860B", "border": "#FFD700", "fill_opacity": 0.35},
    "faction_zhuyuanzhang":  {"fill": "#006400", "border": "#32CD32", "fill_opacity": 0.35},
    "faction_chenyouliang":  {"fill": "#00008B", "border": "#4169E1", "fill_opacity": 0.35},
    "faction_zhangshicheng": {"fill": "#8B008B", "border": "#FF69B4", "fill_opacity": 0.35},
    "faction_fangguozhen":   {"fill": "#2F4F4F", "border": "#20B2AA", "fill_opacity": 0.35},
    "faction_wangbaobao":    {"fill": "#4B0082", "border": "#9370DB", "fill_opacity": 0.35},
    "faction_mingyuzhen":    {"fill": "#8B4513", "border": "#DEB887", "fill_opacity": 0.35},
    "faction_mobei":         {"fill": "#556B2F", "border": "#9ACD32", "fill_opacity": 0.35},
    "neutral":               {"fill": "#666666", "border": "#999999", "fill_opacity": 0.15},
}


# ============================================================
# 迷雾配置
# ============================================================

FOG_OF_WAR_CONFIG = {
    "explore_radius": 2,
    "capital_vision": 4,
    "faction_shared_vision": True,
    "permanent": False,
    "color": "rgba(0,0,0,0.6)",
}


# ============================================================
# 导出
# ============================================================

def export_layer_config_json(
    output_path: str = "server/data/map/layer_config.json",
):
    """导出图层系统配置 JSON (6层 + 三级缩放)"""
    output = {
        "version": "4.1",
        "level": "prefecture",
        "zoom_levels": 3,
        "meta": {
            "grid_rows": GRID_ROWS,
            "grid_max_cols": GRID_MAX_COLS,
            "hex_size": int(DEFAULT_HEX_SIZE),
            "hex_size_px": int(DEFAULT_HEX_SIZE),
        },
        "layers": LAYER_DEFINITIONS,
        "zoom_config": ADMIN_ZOOM_CONFIG,
        "faction_colors": FACTION_LAYER_COLORS,
        "fog_of_war": FOG_OF_WAR_CONFIG,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [图层] 导出完成: {output_path}")
    print(f"    - {len(LAYER_DEFINITIONS)} 个图层")
    print(f"    - {len(ADMIN_ZOOM_CONFIG)} 级缩放")
