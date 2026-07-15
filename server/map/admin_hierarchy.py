"""
三级行政区划层级系统 v4.1 - 行省 → 路 → 府州

v4.1 变更：
- 从四级(行省→路→府州→县)精简为三级(行省→路→府州)
- 每个六边形格子 = 一个府/州
- 版图扩展至东亚全域
- 省份定义使用网格坐标区域

数据结构：
  ProvinceNode → CircuitNode → PrefectureNode (leaf)
  每个 PrefectureNode 包含 tile_ids (长度=1, 即该府州对应的唯一格子)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import json
import re

from server.map.hex_grid import (
    GRID_ROWS, GRID_MAX_COLS,
    iter_all_coords, HexCoord,
    TOTAL_TILES,
)
from server.map.territory_mask import INCLUDED_HEXES


# ============================================================
# 数据类
# ============================================================

@dataclass
class AdminNode:
    """三级行政层级树节点"""
    id: str
    name: str
    type: str  # "province" | "circuit" | "prefecture"
    meta: dict = field(default_factory=dict)
    children: List["AdminNode"] = field(default_factory=list)
    tile_ids: List[str] = field(default_factory=list)
    tile_count: int = 0

    def __post_init__(self):
        if self.tile_ids:
            self.tile_count = len(self.tile_ids)

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "meta": self.meta,
            "tile_count": self.tile_count,
            "tile_ids": self.tile_ids,
        }
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


# ============================================================
# 14省定义 (网格坐标区域)
# ============================================================
# 每个省: (col_start, row_start, col_end, row_end)  [inclusive]
# 基于实际疆域范围设定

PROVINCE_REGIONS: Dict[str, dict] = {
    "岭北行省": {
        "id": "lingbei", "order": 1,
        "bounds": (8, 0, 27, 5),       # col 8-27, row 0-5 (蒙古高原)
        "circuits": {
            "和林路": {"bounds": (8, 0, 17, 2), "capital": (13, 1)},
            "称海宣慰司": {"bounds": (18, 0, 27, 2), "capital": (22, 1)},
            "谦谦州": {"bounds": (8, 3, 17, 5), "capital": (12, 4)},
            "益兰州": {"bounds": (18, 3, 27, 5), "capital": (22, 4)},
        }
    },
    "辽阳行省": {
        "id": "liaoyang", "order": 2,
        "bounds": (26, 2, 35, 9),       # col 26-35, row 2-9 (满洲)
        "circuits": {
            "辽阳路": {"bounds": (26, 4, 30, 6), "capital": (28, 5)},
            "大宁路": {"bounds": (24, 5, 28, 8), "capital": (26, 6)},
            "开元路": {"bounds": (29, 2, 34, 5), "capital": (31, 3)},
            "水达达路": {"bounds": (31, 6, 35, 9), "capital": (33, 7)},
        }
    },
    "中书省": {
        "id": "zhongshu", "order": 3,
        "bounds": (18, 6, 29, 11),      # 河北/山东/山西 (腹里)
        "circuits": {
            "大都路": {"bounds": (22, 7, 26, 9), "capital": (24, 8)},
            "上都路": {"bounds": (20, 6, 24, 8), "capital": (22, 7)},
            "保定路": {"bounds": (22, 9, 25, 10), "capital": (23, 9)},
            "真定路": {"bounds": (20, 9, 23, 11), "capital": (21, 10)},
            "河间路": {"bounds": (24, 8, 28, 10), "capital": (26, 9)},
            "东平路": {"bounds": (22, 10, 26, 11), "capital": (24, 11)},
            "济南路": {"bounds": (24, 10, 27, 11), "capital": (25, 10)},
            "益都路": {"bounds": (26, 9, 29, 11), "capital": (27, 10)},
            "冀宁路": {"bounds": (18, 8, 21, 11), "capital": (19, 9)},
            "晋宁路": {"bounds": (18, 10, 21, 11), "capital": (19, 11)},
        }
    },
    "陕西行省": {
        "id": "shaanxi", "order": 4,
        "bounds": (10, 8, 19, 14),      # 陕西/甘肃东部
        "circuits": {
            "奉元路": {"bounds": (14, 10, 17, 12), "capital": (15, 11)},
            "延安路": {"bounds": (14, 8, 17, 10), "capital": (15, 9)},
            "兴元路": {"bounds": (12, 12, 15, 14), "capital": (13, 13)},
            "巩昌路": {"bounds": (10, 10, 14, 12), "capital": (12, 11)},
            "凤翔府": {"bounds": (12, 10, 15, 11), "capital": (13, 10)},
        }
    },
    "甘肃行省": {
        "id": "gansu", "order": 5,
        "bounds": (2, 6, 11, 11),       # 甘肃西部/西域
        "circuits": {
            "甘州路": {"bounds": (6, 8, 10, 10), "capital": (8, 8)},
            "永昌路": {"bounds": (8, 7, 11, 9), "capital": (9, 8)},
            "肃州路": {"bounds": (4, 7, 7, 9), "capital": (5, 8)},
            "沙州路": {"bounds": (2, 7, 5, 9), "capital": (3, 8)},
            "亦集乃路": {"bounds": (6, 6, 10, 8), "capital": (8, 7)},
            "哈密力": {"bounds": (0, 7, 4, 9), "capital": (2, 8)},
        }
    },
    "宣政院辖地": {
        "id": "xuanzheng", "order": 6,
        "bounds": (0, 12, 13, 19),      # 西藏/青海
        "circuits": {
            "乌思藏宣慰司": {"bounds": (2, 14, 8, 18), "capital": (5, 16)},
            "朵甘思宣慰司": {"bounds": (6, 12, 13, 16), "capital": (9, 14)},
            "朵思麻宣慰司": {"bounds": (2, 12, 8, 15), "capital": (5, 13)},
            "吐蕃等路宣慰司": {"bounds": (8, 15, 13, 19), "capital": (10, 17)},
        }
    },
    "四川行省": {
        "id": "sichuan", "order": 7,
        "bounds": (13, 12, 21, 18),     # 四川/重庆
        "circuits": {
            "成都路": {"bounds": (13, 13, 16, 15), "capital": (14, 14)},
            "重庆路": {"bounds": (16, 14, 19, 16), "capital": (17, 15)},
            "嘉定路": {"bounds": (13, 15, 15, 17), "capital": (14, 16)},
            "顺庆路": {"bounds": (15, 13, 18, 14), "capital": (16, 13)},
            "夔州路": {"bounds": (18, 14, 21, 17), "capital": (19, 15)},
            "绍庆路": {"bounds": (18, 16, 21, 18), "capital": (19, 17)},
        }
    },
    "云南行省": {
        "id": "yunnan", "order": 8,
        "bounds": (8, 16, 17, 22),      # 云南/缅甸北部
        "circuits": {
            "中庆路": {"bounds": (12, 17, 16, 19), "capital": (14, 18)},
            "大理路": {"bounds": (8, 17, 12, 19), "capital": (10, 18)},
            "威楚路": {"bounds": (12, 19, 15, 21), "capital": (13, 20)},
            "临安路": {"bounds": (14, 19, 17, 21), "capital": (15, 20)},
            "曲靖路": {"bounds": (14, 16, 17, 18), "capital": (15, 17)},
            "乌撒路": {"bounds": (12, 16, 15, 17), "capital": (13, 16)},
            "丽江路": {"bounds": (8, 15, 12, 17), "capital": (10, 16)},
            "缅中行省": {"bounds": (8, 21, 14, 23), "capital": (11, 22)},  # 缅甸北部
        }
    },
    "河南江北行省": {
        "id": "henan_jiangbei", "order": 9,
        "bounds": (18, 12, 29, 17),     # 河南/湖北/安徽北部
        "circuits": {
            "汴梁路": {"bounds": (20, 12, 24, 14), "capital": (22, 13)},
            "河南府路": {"bounds": (18, 13, 21, 15), "capital": (19, 14)},
            "襄阳路": {"bounds": (18, 15, 21, 17), "capital": (19, 16)},
            "黄州路": {"bounds": (22, 15, 25, 17), "capital": (23, 16)},
            "庐州路": {"bounds": (24, 14, 27, 16), "capital": (25, 15)},
            "安丰路": {"bounds": (22, 13, 25, 15), "capital": (23, 14)},
            "归德府": {"bounds": (23, 12, 26, 13), "capital": (24, 12)},
            "汝宁府": {"bounds": (20, 14, 23, 16), "capital": (21, 15)},
            "扬州路": {"bounds": (26, 14, 29, 16), "capital": (27, 15)},
        }
    },
    "江浙行省": {
        "id": "jiangzhe", "order": 10,
        "bounds": (24, 14, 33, 21),     # 江苏/浙江/福建/台湾
        "circuits": {
            "杭州路": {"bounds": (25, 16, 28, 18), "capital": (26, 17)},
            "集庆路": {"bounds": (25, 15, 28, 16), "capital": (26, 15)},  # 南京
            "平江路": {"bounds": (27, 15, 30, 17), "capital": (28, 16)},  # 苏州
            "庆元路": {"bounds": (28, 17, 31, 19), "capital": (29, 18)},  # 宁波
            "绍兴路": {"bounds": (26, 17, 29, 18), "capital": (27, 17)},
            "福州路": {"bounds": (26, 19, 29, 21), "capital": (27, 20)},
            "泉州路": {"bounds": (25, 20, 27, 22), "capital": (26, 21)},
            "建宁路": {"bounds": (25, 18, 28, 20), "capital": (26, 19)},
            "温州路": {"bounds": (27, 18, 30, 19), "capital": (28, 18)},
            "澎湖巡检司": {"bounds": (28, 21, 32, 23), "capital": (30, 22)},  # 台湾/琉球
        }
    },
    "江西行省": {
        "id": "jiangxi", "order": 11,
        "bounds": (18, 18, 28, 23),     # 江西/广东
        "circuits": {
            "龙兴路": {"bounds": (22, 18, 25, 20), "capital": (23, 19)},  # 南昌
            "吉安路": {"bounds": (20, 19, 23, 21), "capital": (21, 20)},
            "赣州路": {"bounds": (21, 20, 24, 22), "capital": (22, 21)},
            "广州路": {"bounds": (20, 22, 24, 24), "capital": (22, 23)},
            "潮州路": {"bounds": (24, 21, 27, 23), "capital": (25, 22)},
            "南雄路": {"bounds": (22, 21, 25, 22), "capital": (23, 21)},
            "江州路": {"bounds": (21, 17, 24, 19), "capital": (22, 18)},  # 九江
            "南康路": {"bounds": (22, 17, 24, 18), "capital": (23, 17)},
        }
    },
    "湖广行省": {
        "id": "huguang", "order": 12,
        "bounds": (12, 17, 21, 23),     # 湖南/广西/贵州/越南北部
        "circuits": {
            "武昌路": {"bounds": (19, 16, 22, 18), "capital": (20, 17)},
            "潭州路": {"bounds": (17, 18, 20, 20), "capital": (18, 19)},  # 长沙
            "衡州路": {"bounds": (17, 19, 20, 21), "capital": (18, 20)},
            "静江路": {"bounds": (14, 20, 17, 22), "capital": (15, 21)},  # 桂林
            "柳州路": {"bounds": (14, 21, 17, 23), "capital": (15, 22)},
            "南宁路": {"bounds": (12, 21, 15, 23), "capital": (13, 22)},
            "辰州路": {"bounds": (15, 17, 18, 19), "capital": (16, 18)},
            "沅州路": {"bounds": (14, 18, 17, 20), "capital": (15, 19)},
            "安南宣慰司": {"bounds": (12, 23, 17, 26), "capital": (14, 24)},  # 越南北部
            "思明路": {"bounds": (12, 22, 15, 24), "capital": (13, 23)},
        }
    },
    "征东行省": {
        "id": "zhengdong", "order": 13,
        "bounds": (28, 4, 35, 10),      # 朝鲜半岛
        "circuits": {
            "开城府": {"bounds": (29, 6, 32, 8), "capital": (30, 7)},  # 高丽都城
            "西京路": {"bounds": (28, 5, 30, 7), "capital": (29, 6)},  # 平壤
            "南京路": {"bounds": (30, 6, 33, 8), "capital": (31, 7)},  # 汉城
            "东京路": {"bounds": (32, 5, 35, 8), "capital": (33, 6)},  # 庆州
            "全罗道": {"bounds": (30, 8, 33, 10), "capital": (31, 9)},
            "交州道": {"bounds": (30, 4, 33, 6), "capital": (31, 5)},
        }
    },
    "日本": {
        "id": "japan", "order": 14,
        "bounds": (32, 5, 35, 14),      # 日本列岛 (主岛可及范围)
        "circuits": {
            "山城国": {"bounds": (33, 8, 35, 10), "capital": (34, 9)},  # 京都
            "武藏国": {"bounds": (34, 7, 36, 9), "capital": (35, 8)},  # 江户/东京
            "筑前国": {"bounds": (32, 10, 34, 12), "capital": (33, 11)},  # 九州北
            "陆奥国": {"bounds": (34, 5, 36, 7), "capital": (35, 6)},  # 东北
            "大和国": {"bounds": (33, 9, 35, 11), "capital": (34, 10)},
            "出云国": {"bounds": (32, 8, 34, 10), "capital": (33, 9)},
        }
    },
}


# 特殊名称映射 (用于替换默认的 col,row 名称)
# key: (col, row), value: (prefecture_name, circuit_id)
# 共 34 个著名地标 (按文档 3.5 节规范)
FAMOUS_PREFECTURES: Dict[Tuple[int, int], Tuple[str, str]] = {
    # 中书省核心
    (24, 8): ("大都路", "大都路"),       # 北京
    (22, 7): ("上都路", "上都路"),       # 元上都
    (19, 9): ("太原路", "冀宁路"),       # 太原
    # 河南江北
    (22, 13): ("汴梁路", "汴梁路"),      # 开封
    (19, 14): ("河南府", "河南府路"),    # 洛阳
    (19, 16): ("襄阳路", "襄阳路"),      # 襄阳
    (27, 15): ("扬州路", "扬州路"),      # 扬州
    # 江浙
    (26, 17): ("杭州路", "杭州路"),      # 临安/杭州
    (26, 15): ("集庆路", "集庆路"),      # 南京
    (28, 16): ("平江路", "平江路"),      # 苏州
    (29, 18): ("庆元路", "庆元路"),      # 宁波
    (27, 20): ("福州路", "福州路"),      # 福州
    (26, 21): ("泉州路", "泉州路"),      # 泉州
    # 湖广
    (20, 17): ("武昌路", "武昌路"),      # 武昌
    (18, 19): ("潭州路", "潭州路"),      # 长沙
    # 四川
    (14, 14): ("成都路", "成都路"),      # 成都
    (17, 15): ("重庆路", "重庆路"),      # 重庆
    # 江西
    (23, 19): ("龙兴路", "龙兴路"),      # 南昌
    (22, 23): ("广州路", "广州路"),      # 广州
    # 云南
    (14, 18): ("中庆路", "中庆路"),      # 昆明
    (10, 18): ("大理路", "大理路"),      # 大理
    # 陕西
    (15, 11): ("奉元路", "奉元路"),      # 西安
    # 甘肃
    (8, 8): ("甘州路", "甘州路"),       # 张掖
    # 宣政院
    (5, 16): ("逻些城", "乌思藏宣慰司"),  # 拉萨
    # 辽阳
    (28, 5): ("辽阳路", "辽阳路"),       # 辽阳
    # 征东 (朝鲜)
    (30, 7): ("开城府", "开城府"),       # 开城
    # 日本
    (34, 9): ("平安京", "山城国"),       # 京都
    (35, 8): ("江户", "武藏国"),        # 东京
    # 名关要地
    (16, 10): ("潼关", "奉元路"),        # 潼关
}


# ============================================================
# Grid-based prefecture name generator
# ============================================================

def _grid_prefecture_name(col: int, row: int,
                         circuit_name: str = None,
                         circuit_capital: Tuple[int, int] = None) -> str:
    """为网格坐标生成府州名称

    优先使用真实历史名称，其次基于所属路名+方位生成中文府州名
    """
    # 先查著名地标（精确历史名称）
    if (col, row) in FAMOUS_PREFECTURES:
        return FAMOUS_PREFECTURES[(col, row)][0]

    # 基于路名 + 方位生成府州名
    if circuit_name and circuit_capital:
        cap_col, cap_row = circuit_capital
        dc = col - cap_col
        dr = row - cap_row

        # 路治所在 → 直接使用路名
        if dc == 0 and dr == 0:
            return circuit_name

        # 去掉路名末尾的行政区划后缀（"路"/"司"/"府"/"道"/"州"）
        base = re.sub(r'(路|宣慰司|宣抚司|巡检司|府|道|州)$', '', circuit_name)

        # 方向判定
        dirs = []
        if dr > 0:
            dirs.append("南")
        elif dr < 0:
            dirs.append("北")
        if dc > 0:
            dirs.append("东")
        elif dc < 0:
            dirs.append("西")

        if dirs:
            direction = "".join(dirs)
            dist = max(abs(dc), abs(dr))
            if dist <= 1:
                return f"{base}{direction}"
            else:
                return f"{base}{direction}{dist}"
        else:
            return circuit_name

    # 兜底：经纬度坐标名称
    lon = 55 + (col + 0.5) / 36 * 110
    lat = 60 - (row + 0.5) / 28 * 60
    return f"{int(lon)}E{int(lat)}N"


# ============================================================
# 核心分配逻辑
# ============================================================

def _in_bounds(col: int, row: int, bounds: Tuple[int, int, int, int]) -> bool:
    """判断坐标是否在边界内 [inclusive]"""
    c_min, r_min, c_max, r_max = bounds
    return c_min <= col <= c_max and r_min <= row <= r_max


def assign_tiles_to_hierarchy(included_hexes: Set[Tuple[int, int]] = None) -> Dict[str, dict]:
    """
    将有效 tile 分配到三级行政层级

    Returns:
        {
            tile_id: {
                "province": str, "province_id": str,
                "circuit": str, "circuit_id": str,
                "prefecture": str, "prefecture_id": str,
            }
        }
    """
    if included_hexes is None:
        included_hexes = INCLUDED_HEXES

    assignments: Dict[str, dict] = {}

    for col, row in included_hexes:
        tile_id = f"{col},{row}"

        # 查找所属省份和路
        assigned_province = None
        assigned_province_id = None
        assigned_circuit = None
        assigned_circuit_id = None

        for prov_name, prov_data in PROVINCE_REGIONS.items():
            bounds = prov_data["bounds"]
            if _in_bounds(col, row, bounds):
                assigned_province = prov_name
                assigned_province_id = prov_data["id"]

                # 查找路
                for circ_name, circ_data in prov_data["circuits"].items():
                    c_bounds = circ_data["bounds"]
                    if _in_bounds(col, row, c_bounds):
                        assigned_circuit = circ_name
                        assigned_circuit_id = f"{prov_data['id']}_{circ_name}"
                        break

                # 如果没找到路（边界外但省内），用默认
                if assigned_circuit is None and prov_data["circuits"]:
                    first_circ = list(prov_data["circuits"].keys())[0]
                    assigned_circuit = first_circ
                    assigned_circuit_id = f"{prov_data['id']}_{first_circ}"
                break

        # 未分配 → 查找最近的省份和路（就近归附）
        if assigned_province is None:
            best_dist = 999
            for prov_name, prov_data in PROVINCE_REGIONS.items():
                bounds = prov_data["bounds"]
                p_cx = (bounds[0] + bounds[2]) / 2
                p_cy = (bounds[1] + bounds[3]) / 2
                dist = abs(col - p_cx) + abs(row - p_cy)
                if dist < best_dist:
                    best_dist = dist
                    assigned_province = prov_name
                    assigned_province_id = prov_data["id"]
            # 归入该省最近的路
            if assigned_province:
                best_cdist = 999
                prov_data = PROVINCE_REGIONS.get(assigned_province, {})
                for circ_name, circ_data in prov_data.get("circuits", {}).items():
                    c_bounds = circ_data["bounds"]
                    c_cx = (c_bounds[0] + c_bounds[2]) / 2
                    c_cy = (c_bounds[1] + c_bounds[3]) / 2
                    cdist = abs(col - c_cx) + abs(row - c_cy)
                    if cdist < best_cdist:
                        best_cdist = cdist
                        assigned_circuit = circ_name
                        assigned_circuit_id = f"{assigned_province_id}_{circ_name}"
            if not assigned_circuit:
                assigned_circuit = assigned_province or "未归属"
                assigned_circuit_id = f"{assigned_province_id or 'unassigned'}_{assigned_circuit}"

        # 府州名称
        if (col, row) in FAMOUS_PREFECTURES:
            pref_name, circ_id = FAMOUS_PREFECTURES[(col, row)]
            if assigned_circuit_id and circ_id:
                # 使用指定的路 (跨省边界的名城使用其历史所属路)
                assigned_circuit = circ_id
                assigned_circuit_id = f"{assigned_province_id}_{circ_id}"
        else:
            # 获取路治坐标用于方位命名
            circuit_capital = None
            if assigned_circuit and assigned_province:
                prov_data = PROVINCE_REGIONS.get(assigned_province)
                if prov_data:
                    circ_data = prov_data["circuits"].get(assigned_circuit)
                    if circ_data:
                        circuit_capital = circ_data.get("capital")
            pref_name = _grid_prefecture_name(
                col, row, assigned_circuit, circuit_capital
            )

        pref_id = f"{assigned_province_id}_{assigned_circuit_id}_{col}_{row}"

        assignments[tile_id] = {
            "province": assigned_province,
            "province_id": assigned_province_id,
            "circuit": assigned_circuit,
            "circuit_id": assigned_circuit_id,
            "prefecture": pref_name,
            "prefecture_id": pref_id,
        }

    return assignments


# ============================================================
# 构建层级树
# ============================================================

def build_hierarchy_tree(assignments: Dict[str, dict]) -> AdminNode:
    """从 tile 分配数据构建三级 AdminNode 树"""
    root = AdminNode(id="root", name="大元帝国", type="root")

    # 按 province → circuit 聚合
    prov_circuits: Dict[str, Dict[str, List[str]]] = {}  # prov_id → circ_id → [tile_ids]

    for tile_id, info in assignments.items():
        pid = info["province_id"]
        cid = info["circuit_id"]
        if pid not in prov_circuits:
            prov_circuits[pid] = {}
        if cid not in prov_circuits[pid]:
            prov_circuits[pid][cid] = []
        prov_circuits[pid][cid].append(tile_id)

    # 构建树节点
    sorted_provs = sorted(PROVINCE_REGIONS.items(),
                          key=lambda x: x[1]["order"])

    for prov_name, prov_data in sorted_provs:
        pid = prov_data["id"]
        circuits_dict = prov_circuits.get(pid, {})
        if not circuits_dict:
            continue

        prov_node = AdminNode(
            id=pid,
            name=prov_name,
            type="province",
            meta={"order": prov_data["order"]},
        )

        for circ_name in prov_data["circuits"].keys():
            cid = f"{pid}_{circ_name}"
            tile_list = circuits_dict.get(cid, [])
            if not tile_list:
                continue

            circ_node = AdminNode(
                id=cid,
                name=circ_name,
                type="circuit",
                tile_ids=tile_list,
                tile_count=len(tile_list),
            )

            # 府州节点 (每个 tile 一个)
            for tile_id in tile_list:
                info = assignments.get(tile_id, {})
                pref_name = info.get("prefecture", "未知")
                pref_id = info.get("prefecture_id", tile_id)

                pref_node = AdminNode(
                    id=pref_id,
                    name=pref_name,
                    type="prefecture",
                    tile_ids=[tile_id],
                    tile_count=1,
                )
                circ_node.children.append(pref_node)

            circ_node.tile_count = len(tile_list)
            prov_node.children.append(circ_node)

        prov_node.tile_count = sum(c.tile_count for c in prov_node.children)
        root.children.append(prov_node)

    root.tile_count = sum(c.tile_count for c in root.children)
    return root


# ============================================================
# 聚合统计
# ============================================================

def aggregate_stats(assignments: Dict[str, dict]):
    """聚合统计各级 tile 数量"""
    stats = {
        "total_tiles": len(assignments),
        "provinces": {},
        "circuits": {},
    }

    for tile_id, info in assignments.items():
        pid = info["province_id"]
        cid = info["circuit_id"]

        stats["provinces"].setdefault(pid, {
            "name": info["province"], "count": 0
        })["count"] += 1

        stats["circuits"].setdefault(cid, {
            "name": info["circuit"], "province": info["province"], "count": 0
        })["count"] += 1

    return stats


# ============================================================
# 导出与查询
# ============================================================

def export_admin_hierarchy_json(output_path: str = "server/data/map/admin_hierarchy.json"):
    """导出完整的三级行政层级 JSON"""
    print("  [层级] 分配 tile 到三级行政层级...")
    assignments = assign_tiles_to_hierarchy()

    print("  [层级] 构建层级树...")
    tree = build_hierarchy_tree(assignments)

    print("  [层级] 聚合统计...")
    stats = aggregate_stats(assignments)

    output = {
        "version": "4.1",
        "levels": ["province", "circuit", "prefecture"],
        "meta": {
            "grid_rows": GRID_ROWS,
            "grid_max_cols": GRID_MAX_COLS,
            "total_tiles": TOTAL_TILES,
            "province_count": len(PROVINCE_REGIONS),
            "hex_size": 72,
        },
        "hierarchy_tree": tree.to_dict(),
        "tile_assignments": assignments,
        "stats": stats,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [层级] 导出完成: {output_path}")
    print(f"    - {len(tree.children)} 个省")
    circuit_count = sum(len(p.children) for p in tree.children)
    print(f"    - {circuit_count} 个路")
    print(f"    - {len(assignments)} 个府州 (tile)")

    return output


# ============================================================
# 查询工具
# ============================================================

def generate_tile_province_map(assignments: Dict[str, dict] = None) -> Dict[str, str]:
    """生成 tile_id → province_id 映射"""
    if assignments is None:
        assignments = assign_tiles_to_hierarchy()
    return {tid: info["province_id"] for tid, info in assignments.items()}


def generate_tile_prefecture_map(assignments: Dict[str, dict] = None) -> Dict[str, str]:
    """生成 tile_id → prefecture_name 映射"""
    if assignments is None:
        assignments = assign_tiles_to_hierarchy()
    return {tid: info["prefecture"] for tid, info in assignments.items()}


def get_province_tiles(assignments: Dict[str, dict], province_id: str) -> List[str]:
    """获取某省所有 tile IDs"""
    return [tid for tid, info in assignments.items()
            if info["province_id"] == province_id]


def get_circuit_tiles(assignments: Dict[str, dict], circuit_id: str) -> List[str]:
    """获取某路所有 tile IDs"""
    return [tid for tid, info in assignments.items()
            if info["circuit_id"] == circuit_id]


def get_territory_graph() -> Dict[str, List[str]]:
    """
    构建领地邻接图 — tile_id → 相邻tile_id列表
    
    用于外交接壤判定和武将自主作战的邻接查询。
    自动从六边形网格邻接表生成，格式为 {tile_id: [neighbor_tile_ids]}。
    
    注意：此函数返回 dict 格式（轻量级），与 server.core.territory_graph.TerritoryGraph
    （CK3风格全功能图）不同。此处用于简单邻接查询（已包含try/except的降级逻辑）。
    """
    try:
        from server.map.adjacency import build_adjacency_table
        from server.map.territory_mask import INCLUDED_HEXES
        # 仅构建疆域遮罩内的邻接关系
        adj_raw = build_adjacency_table(tile_set=INCLUDED_HEXES if INCLUDED_HEXES else None)
        # 转换键格式: "col,row" → "tile_col_row"
        result = {}
        for key, neighbors in adj_raw.items():
            tile_id = f"tile_{key.replace(',', '_')}"
            result[tile_id] = [f"tile_{n.replace(',', '_')}" for n in neighbors]
        return result
    except Exception:
        # 回退：返回空图，调用方已有 try/except
        return {}


if __name__ == "__main__":
    export_admin_hierarchy_json()
