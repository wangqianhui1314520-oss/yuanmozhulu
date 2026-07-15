"""
地图图层系统配置 v4.0 - 三级缩放 (行省/路/府州)

v4.0 变更:
- 缩放层级从四级精简为三级: world → circuit → prefecture
- 府州级 = 最高缩放 (显示府州标签)
- 移除县级边界/标签
"""

from __future__ import annotations
import json
from typing import Dict, List, Any

from server.map.hex_grid import GRID_ROWS, GRID_MAX_COLS, DEFAULT_HEX_SIZE


# ============================================================
# 图层定义
# ============================================================

LAYER_DEFINITIONS: List[Dict[str, Any]] = [
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
            "unknown": "#808080",
        },
        "stroke": {"color": "#333333", "width": 0.5},
    },
    {
        "key": "faction",
        "name": "势力着色",
        "type": "fill",
        "z_index": 1,
        "default_visible": True,
        "factions": {
            "faction_yuan":          {"fill": "#8B0000", "border": "#FF4444", "fill_opacity": 0.35},
            "faction_xushouhui":     {"fill": "#B8860B", "border": "#FFD700", "fill_opacity": 0.35},
            "faction_zhuyuanzhang":  {"fill": "#006400", "border": "#32CD32", "fill_opacity": 0.35},
            "faction_chenyouliang":  {"fill": "#00008B", "border": "#4169E1", "fill_opacity": 0.35},
            "faction_zhangshicheng": {"fill": "#8B008B", "border": "#FF69B4", "fill_opacity": 0.35},
            "faction_fangguozhen":   {"fill": "#2F4F4F", "border": "#20B2AA", "fill_opacity": 0.35},
            "faction_mobei":         {"fill": "#556B2F", "border": "#9ACD32", "fill_opacity": 0.35},
            "faction_mingyuzhen":    {"fill": "#8B4513", "border": "#DEB887", "fill_opacity": 0.35},
            "faction_wangbaobao":    {"fill": "#4B0082", "border": "#9370DB", "fill_opacity": 0.35},
            "neutral":               {"fill": "#666666", "border": "#999999", "fill_opacity": 0.15},
        },
    },
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
                "scale_min": 0.25,
            },
            "circuit": {
                "name": "路边界",
                "color": "#FFAA00",
                "line_width": 2,
                "dash": [4, 4],
                "scale_min": 0.5,
            },
        },
    },
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
    {
        "key": "strategic",
        "name": "战略标记",
        "type": "marker",
        "z_index": 4,
        "default_visible": True,
        "icons": {
            "capital":   {"symbol": "★", "color": "#FFD700", "size": 22},
            "port":      {"symbol": "⚓", "color": "#4FC3F7", "size": 16},
            "pass":      {"symbol": "🏔", "color": "#FF8A65", "size": 16},
            "ferry":     {"symbol": "⛵", "color": "#81C784", "size": 14},
            "strategic": {"symbol": "🏰", "color": "#FFD54F", "size": 14},
        },
    },
    {
        "key": "hex_grid",
        "name": "六边形网格",
        "type": "line",
        "z_index": 5,
        "default_visible": True,
        "stroke": {"color": "#444444", "width": 0.5},
    },
]


# ============================================================
# 三级缩放配置 (v4.0)
# ============================================================

ADMIN_ZOOM_CONFIG: List[Dict[str, Any]] = [
    {
        "key": "world",
        "name": "天下大势",
        "admin_level": "province",
        "min_scale": 0.25,
        "max_scale": 0.55,
        "default_scale": 0.30,
        "show_boundaries": ["province"],
        "show_labels": ["province"],
        "show_hexes": True,
        "show_markers": ["capital"],
        "label_scale": 1.0,
    },
    {
        "key": "circuit",
        "name": "各路形势",
        "admin_level": "circuit",
        "min_scale": 0.50,
        "max_scale": 0.90,
        "default_scale": 0.65,
        "show_boundaries": ["province", "circuit"],
        "show_labels": ["province", "circuit"],
        "show_hexes": True,
        "show_markers": ["capital", "port", "pass"],
        "label_scale": 1.2,
    },
    {
        "key": "prefecture",
        "name": "府州详情",
        "admin_level": "prefecture",
        "min_scale": 0.85,
        "max_scale": 3.50,
        "default_scale": 1.0,
        "show_boundaries": ["province", "circuit"],
        "show_labels": ["province", "circuit", "prefecture"],
        "show_hexes": True,
        "show_markers": ["capital", "port", "pass", "ferry", "strategic"],
        "label_scale": 1.5,
    },
]


# ============================================================
# 势力图层配置
# ============================================================

FACTION_LAYER_COLORS: Dict[str, Dict[str, Any]] = {
    "faction_yuan":          {"fill": "#8B0000", "border": "#FF4444", "fill_opacity": 0.35},
    "faction_xushouhui":     {"fill": "#B8860B", "border": "#FFD700", "fill_opacity": 0.35},
    "faction_zhuyuanzhang":  {"fill": "#006400", "border": "#32CD32", "fill_opacity": 0.35},
    "faction_chenyouliang":  {"fill": "#00008B", "border": "#4169E1", "fill_opacity": 0.35},
    "faction_zhangshicheng": {"fill": "#8B008B", "border": "#FF69B4", "fill_opacity": 0.35},
    "faction_fangguozhen":   {"fill": "#2F4F4F", "border": "#20B2AA", "fill_opacity": 0.35},
    "faction_mobei":         {"fill": "#556B2F", "border": "#9ACD32", "fill_opacity": 0.35},
    "faction_mingyuzhen":    {"fill": "#8B4513", "border": "#DEB887", "fill_opacity": 0.35},
    "faction_wangbaobao":    {"fill": "#4B0082", "border": "#9370DB", "fill_opacity": 0.35},
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
    """导出图层系统配置 JSON"""
    output = {
        "version": "4.0",
        "level": "prefecture",
        "zoom_levels": 3,  # 三级缩放
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
