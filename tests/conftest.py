"""
测试共享 Fixtures — 元末逐鹿

提供最小化的 mock WorldState/TileState/FactionState/HexCoord，
核心模块测试零外部依赖、毫秒级执行。
"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, PropertyMock


# ============================================================
# 六边形网格 Fixtures
# ============================================================

@pytest.fixture
def sample_coords():
    """典型六边形坐标集合"""
    from server.map.hex_grid import HexCoord
    return {
        "origin": HexCoord(0, 0),
        "center": HexCoord(21, 15),
        "edge_left": HexCoord(0, 15),
        "edge_right": HexCoord(41, 0),
        "edge_bottom": HexCoord(10, 31),
        "dadu": HexCoord(20, 14),     # 大都
        "yingtian": HexCoord(27, 20), # 应天
        "wuchang": HexCoord(20, 23),  # 武昌
    }


@pytest.fixture
def hex_coord_pairs():
    """用于邻居/距离测试的坐标对（由 HexCoord.neighbors() 计算保证相邻）"""
    from server.map.hex_grid import HexCoord
    center = HexCoord(10, 10)
    neighbors = center.neighbors(territory_only=False)
    return [(center, n) for n in neighbors]


# ============================================================
# 世界状态 Mock Fixtures
# ============================================================

@pytest.fixture
def mock_tile():
    """模拟单个地块"""
    tile = MagicMock()
    tile.tile_id = "21,15"
    tile.tile_name = "大都"
    tile.faction_id = "faction_yuan"
    tile.population = 5000
    tile.troops = 300
    tile.grain = 2000
    tile.treasury = 5000
    tile.morale = 60
    tile.tile_type = "city"
    tile.is_capital = True
    tile.is_supply_base = False
    tile.q = 21
    tile.r = 15
    tile.col = 21
    tile.row = 15
    tile.buildings = {}
    tile.development_level = 2
    tile.neighbors = ["20,14", "22,15", "21,16", "20,15", "21,14"]
    return tile


@pytest.fixture
def mock_faction():
    """模拟势力状态"""
    faction = MagicMock()
    faction.faction_id = "faction_yuan"
    faction.name = "元廷"
    faction.is_alive = True
    faction.treasury = 10000
    faction.grain = 50000
    faction.total_population = 500000
    faction.diplomatic_stances = {}
    faction.diplomatic_relations = {}
    faction.trade_partners = []
    faction.spy_network = {}
    faction.morale = 50
    faction.troops_total = 5000
    faction.tiles_count = 45
    return faction


@pytest.fixture
def mock_world_state(mock_tile, mock_faction):
    """模拟完整世界状态"""
    world = MagicMock()
    world.current_round = 1
    world.current_season = "春"
    world.tiles = {mock_tile.tile_id: mock_tile}
    world.factions = {mock_faction.faction_id: mock_faction}
    world.supply_lines = {}
    world.road_network = {}

    def _get_tile(tid):
        return world.tiles.get(tid)

    def _get_faction_tiles(fid):
        return [t for t in world.tiles.values() if t.faction_id == fid]

    world.get_tile = _get_tile
    world.get_faction_tiles = _get_faction_tiles
    return world


@pytest.fixture
def nine_faction_tiles():
    """9势力各1个地块，用于经济/Gini测试"""
    tiles = []
    factions = [
        ("faction_yuan", "大都", 10000),
        ("faction_zhuyuanzhang", "应天", 8000),
        ("faction_chenyouliang", "武昌", 9000),
        ("faction_zhangshicheng", "平江", 12000),
        ("faction_fangguozhen", "庆元", 6000),
        ("faction_xushouhui", "襄阳", 4000),
        ("faction_mingyuzhen", "重庆", 5000),
        ("faction_wangbaobao", "太原", 7000),
        ("faction_mobei", "和林", 3000),
    ]
    for fid, name, treasury in factions:
        tile = MagicMock()
        tile.tile_id = fid.replace("faction_", "") + "_cap"
        tile.tile_name = name
        tile.faction_id = fid
        tile.population = 50000
        tile.troops = 500
        tile.grain = 10000
        tile.morale = 50
        tile.tile_type = "city"
        tile.is_capital = True
        tile.is_supply_base = False
        tile.q = 20
        tile.r = 15
        tile.col = 20
        tile.row = 15
        tile.buildings = {}
        tile.development_level = 1
        tile.treasury = treasury
        tiles.append(tile)
    return tiles


# ============================================================
# 战斗系统 Fixtures
# ============================================================

@pytest.fixture
def unit_types():
    """四种基础兵种"""
    from server.core.combat_utils import UnitType
    return {
        "cavalry": UnitType.CAVALRY,
        "infantry": UnitType.INFANTRY,
        "naval": UnitType.NAVAL,
        "archer": UnitType.ARCHER,
    }


@pytest.fixture
def counter_table():
    """兵种克制表"""
    from server.core.combat_modifiers import COUNTER_TABLE
    return COUNTER_TABLE


# ============================================================
# 寻路 Fixtures
# ============================================================

@pytest.fixture
def pathfinding_world():
    """简化寻路测试网格（3x3 区域）"""
    from server.map.hex_grid import HexCoord
    # 3x3 九宫格
    center = HexCoord(21, 15)
    neighbors = center.neighbors(territory_only=True)
    all_coords = [center] + neighbors if neighbors else []
    return {"center": center, "all": all_coords, "neighbors": neighbors}
