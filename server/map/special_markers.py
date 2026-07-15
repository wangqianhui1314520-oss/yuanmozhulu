"""
特殊地块标记生成器 v4.0 - 府州级

v4.0 变更:
- 标记坐标重新适配府州级网格 (32×42)
- 保留: 首都、港口、关隘、渡口、战略据点
- 新增: 东亚扩展区域的标记 (朝鲜/日本/中南半岛)
"""

from __future__ import annotations
import json
from typing import Dict, List, Set, Tuple, Optional

from server.map.hex_grid import (
    DEFAULT_HEX_SIZE, HexCoord,
)
from server.map.territory_mask import INCLUDED_HEXES
from server.map.faction_territory import FACTION_CAPITALS


# ============================================================
# 势力首都标记
# ============================================================

FACTION_CAPITAL_NAMES: Dict[str, str] = {
    "faction_yuan": "大都",
    "faction_xushouhui": "汴梁",
    "faction_zhuyuanzhang": "集庆",
    "faction_chenyouliang": "武昌",
    "faction_zhangshicheng": "平江",
    "faction_fangguozhen": "庆元",
    "faction_mobei": "和林",
    "faction_mingyuzhen": "成都",
    "faction_wangbaobao": "中庆",
}

# 其他重要城市标记
IMPORTANT_CITIES: Dict[str, Tuple[int, int]] = {
    "上都": (22, 7),     # 元上都
    "太原": (19, 9),     # 太原
    "大同": (21, 8),     # 大同
    "辽阳": (28, 5),     # 辽阳
    "甘州": (8, 8),      # 张掖
    "奉元": (15, 11),    # 西安
    "洛阳": (19, 14),    # 洛阳
    "襄阳": (19, 16),    # 襄阳
    "杭州": (26, 17),    # 杭州
    "泉州": (26, 21),    # 泉州
    "广州": (22, 23),    # 广州
    "重庆": (17, 15),    # 重庆
    "大理": (10, 18),    # 大理
    "逻些": (5, 16),     # 拉萨
    "开城": (30, 7),     # 高丽都城
    "平安京": (34, 9),   # 京都
    "江户": (35, 8),     # 东京/江户
}


# ============================================================
# 港口参考点 (府州级坐标)
# ============================================================

PORT_POINTS: List[Tuple[int, int, str]] = [
    (25, 9, "直沽"),       # 天津港 (渤海湾)
    (27, 10, "登州"),      # 蓬莱港 (山东)
    (27, 16, "扬州港"),    # 扬州港 (长江口)
    (28, 17, "明州港"),    # 宁波港
    (26, 20, "泉州港"),    # 泉州港 (第一大港)
    (24, 22, "广州港"),    # 广州港
    (29, 6, "西京港"),     # 平壤/镇南浦
    (32, 9, "博多港"),     # 九州博多
    (33, 11, "堺港"),      # 大阪湾
    (14, 24, "交趾港"),    # 越南北部
    (26, 22, "澎湖港"),    # 澎湖巡检司
]


# ============================================================
# 关隘参考点
# ============================================================

PASS_POINTS: List[Tuple[int, int, str]] = [
    (16, 10, "潼关"),        # 关中门户
    (17, 11, "函谷关"),      # 关中东门
    (20, 9, "居庸关"),       # 北京北
    (24, 8, "山海关"),       # 东北门户
    (14, 13, "剑门关"),      # 蜀道
    (24, 14, "武关"),        # 河南→陕西
    (16, 15, "瞿塘关"),      # 三峡
    (21, 17, "大散关"),      # 秦岭
    (21, 13, "虎牢关"),      # 洛阳东
    (25, 18, "仙霞关"),      # 福建
    (20, 22, "梅关"),        # 江西→广东
    (13, 21, "镇南关"),      # 广西→越南
]


# ============================================================
# 战略据点
# ============================================================

STRATEGIC_POINTS: List[Tuple[int, int, str, str]] = [
    # (col, row, name, note)
    # 华北
    (23, 8, "大都", "元朝都城，北方政治中心"),
    (22, 7, "上都", "元朝夏都"),
    (24, 9, "真定", "北方重镇"),
    # 华中
    (22, 13, "汴梁", "北宋故都，中原要冲"),
    (26, 15, "集庆", "朱元璋都城"),
    (27, 15, "扬州", "漕运中枢"),
    (24, 16, "庐州", "江淮重镇"),
    # 四川
    (14, 14, "成都", "天府之国"),
    (17, 15, "重庆", "山城要塞"),
    # 湖广
    (20, 17, "武昌", "九省通衢"),
    (18, 19, "潭州", "长沙要冲"),
    # 江南
    (26, 17, "杭州", "南宋故都"),
    (28, 16, "平江", "张士诚都城"),
    # 华南
    (26, 21, "泉州", "东方第一大港"),
    (22, 23, "广州", "岭南都会"),
    # 西南
    (14, 18, "中庆", "云南都会"),
    (10, 18, "大理", "段氏故都"),
    # 西域
    (8, 8, "甘州", "丝路重镇"),
    # 辽东
    (28, 5, "辽阳", "东北都会"),
    # 朝鲜
    (30, 7, "开城", "高丽王都"),
    # 日本
    (34, 9, "平安京", "日本天皇御所"),
    (35, 8, "镰仓", "幕府所在地"),
    # 台湾/琉球
    (30, 22, "澎湖", "巡检司"),
]


# ============================================================
# 渡口 (大河渡口)
# ============================================================

FERRY_POINTS: List[Tuple[int, int, str]] = [
    (24, 13, "黄河渡"),     # 黄河
    (26, 15, "长江渡"),     # 南京段
    (23, 16, "汉水渡"),     # 汉水
    (18, 16, "夷陵渡"),     # 三峡
    (21, 20, "赣江渡"),     # 赣江
    (16, 18, "沅江渡"),     # 沅江
]


# ============================================================
# 生成标记
# ============================================================

def generate_special_markers(
    tile_adjacency: Dict[str, List[str]] = None,
) -> Dict[str, dict]:
    """
    为疆域内每个 tile 生成特殊标记字典

    Returns:
        tile_id → {
            is_capital: bool, is_port: bool, is_pass: bool,
            is_ferry: bool, is_strategic: bool,
            strategic_name: str, strategic_note: str,
        }
    """
    markers: Dict[str, dict] = {}
    empty_marker = {
        "is_capital": False, "is_port": False, "is_pass": False,
        "is_ferry": False, "is_strategic": False,
        "strategic_name": None, "strategic_note": None,
    }

    for col, row in INCLUDED_HEXES:
        tile_id = f"{col},{row}"
        markers[tile_id] = dict(empty_marker)

    # 首都标记
    for fid, (col, row) in FACTION_CAPITALS.items():
        tile_id = f"{col},{row}"
        if tile_id in markers:
            name = FACTION_CAPITAL_NAMES.get(fid, fid)
            markers[tile_id] = {
                "is_capital": True, "is_port": False, "is_pass": False,
                "is_ferry": False, "is_strategic": True,
                "strategic_name": name, "strategic_note": f"{name} - 势力首都",
            }

    # 港口标记
    for col, row, name in PORT_POINTS:
        tile_id = f"{col},{row}"
        if tile_id in markers and not markers[tile_id].get("is_capital"):
            markers[tile_id]["is_port"] = True
            markers[tile_id]["is_strategic"] = True
            markers[tile_id]["strategic_name"] = name
            markers[tile_id]["strategic_note"] = f"{name} - 港口"

    # 关隘标记
    for col, row, name in PASS_POINTS:
        tile_id = f"{col},{row}"
        if tile_id in markers and not markers[tile_id].get("is_capital"):
            markers[tile_id]["is_pass"] = True
            markers[tile_id]["is_strategic"] = True
            markers[tile_id]["strategic_name"] = name
            markers[tile_id]["strategic_note"] = f"{name} - 关隘"

    # 渡口标记
    for col, row, name in FERRY_POINTS:
        tile_id = f"{col},{row}"
        if tile_id in markers and not markers[tile_id].get("is_capital"):
            markers[tile_id]["is_ferry"] = True
            markers[tile_id]["is_strategic"] = True
            markers[tile_id]["strategic_name"] = name
            markers[tile_id]["strategic_note"] = f"{name} - 渡口"

    # 战略据点 (不打标已有首都/港口/关隘的)
    for col, row, name, note in STRATEGIC_POINTS:
        tile_id = f"{col},{row}"
        if tile_id in markers and not markers[tile_id].get("is_strategic"):
            markers[tile_id]["is_strategic"] = True
            markers[tile_id]["strategic_name"] = name
            markers[tile_id]["strategic_note"] = note

    return markers


def export_special_markers_json(
    markers: Dict[str, dict],
    output_path: str = "server/data/map/special_markers.json",
):
    """导出特殊标记配置 JSON"""
    capital_count = sum(1 for m in markers.values() if m["is_capital"])
    port_count = sum(1 for m in markers.values() if m["is_port"])
    pass_count = sum(1 for m in markers.values() if m["is_pass"])
    ferry_count = sum(1 for m in markers.values() if m["is_ferry"])
    strategic_count = sum(1 for m in markers.values() if m["is_strategic"])

    output = {
        "version": "4.0",
        "level": "prefecture",
        "meta": {
            "capitals": capital_count,
            "ports": port_count,
            "passes": pass_count,
            "ferries": ferry_count,
            "strategic": strategic_count,
        },
        "markers": {
            tid: {k: v for k, v in m.items() if v not in (None, False)}
            for tid, m in markers.items()
            if any(m.values())
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [标记] 导出完成: {output_path}")
    print(f"    - 首都: {capital_count}, 港口: {port_count}")
    print(f"    - 关隘: {pass_count}, 渡口: {ferry_count}")
    print(f"    - 战略据点: {strategic_count}")
