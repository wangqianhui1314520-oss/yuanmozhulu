"""
游戏初始化器 - 从配置生成完整 WorldState

职责:
1. 读取 factions.json 生成9个势力的初始 FactionState
2. 从 GeoJSON 加载 CK3 风格不规则多边形领地（替代六边形网格）
3. 建立势力间初始外交关系
4. 生成初始官员、国库数据
"""
from __future__ import annotations
import json
import uuid
import logging
import math
from pathlib import Path
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    RelationState, DiplomaticStance, Season,
    OfficialRecord, PrisonerRecord,
)

logger = logging.getLogger("yuanmo.init")

SERVER_DIR = Path(__file__).parent.parent
CONFIG_DIR = SERVER_DIR / "config"
MAP_DATA_DIR = SERVER_DIR.parent / "frontend" / "public" / "data" / "map"
SERVER_MAP_DATA_DIR = SERVER_DIR / "data" / "map"  # 服务端地图数据目录（map_final.json等）

# 势力颜色（低饱和度古风 - 九大势力 V3.0）
# 注：已统一为 factions.json 的新ID体系
FACTION_COLORS = {
    "faction_yuan":          "#8B0000",  # 元廷-暗红（蒙古铁骑）
    "faction_xushouhui":     "#996633",  # 徐寿辉-棕褐（天完/红巾正统）
    "faction_zhuyuanzhang":  "#DC143C",  # 朱元璋-深红（西吴）
    "faction_chenyouliang":  "#1E90FF",  # 陈友谅-道奇蓝（陈汉水师）
    "faction_zhangshicheng": "#FF8C00",  # 张士诚-暗橙（大周/江南富庶）
    "faction_mingyuzhen":    "#B8860B",  # 明玉珍-暗金（大夏/天府之国）
    "faction_fangguozhen":   "#20B2AA",  # 方国珍-浅海绿（海上贸易）
    "faction_wangbaobao":    "#666699",  # 王保保-紫灰（扩廓帖木儿/元廷柱石）
    "faction_mobei":         "#887766",  # 漠北诸部-灰棕（草原部落联盟）
}

# 向后兼容：保留旧ID别名（韩宋→徐寿辉, 梁王→王保保, 陈友定→漠北）
FACTION_COLORS["faction_hansong"] = FACTION_COLORS["faction_xushouhui"]
FACTION_COLORS["faction_liangwang"] = FACTION_COLORS["faction_wangbaobao"]
FACTION_COLORS["faction_chenyouding"] = FACTION_COLORS["faction_mobei"]

# 势力首都映射（语义化 tile ID）
# 注：已统一为 factions.json 的新ID体系
# 3.2修复：同时支持坐标格式（从 faction_territories.json 自动同步）
FACTION_CAPITALS_SEMANTIC = {
    "faction_yuan":          "tile_dadu",
    "faction_xushouhui":     "tile_xiangyang",
    "faction_zhuyuanzhang":  "tile_yingtian",
    "faction_chenyouliang":  "tile_wuchang",
    "faction_zhangshicheng": "tile_pingjiang",
    "faction_mingyuzhen":    "tile_chongqing",
    "faction_fangguozhen":   "tile_qingyuan",
    "faction_wangbaobao":    "tile_taiyuan",
    "faction_mobei":         "tile_helin",
}

# 向后兼容：保留旧ID别名
FACTION_CAPITALS_SEMANTIC["faction_hansong"] = FACTION_CAPITALS_SEMANTIC["faction_xushouhui"]
FACTION_CAPITALS_SEMANTIC["faction_liangwang"] = FACTION_CAPITALS_SEMANTIC["faction_wangbaobao"]
FACTION_CAPITALS_SEMANTIC["faction_chenyouding"] = FACTION_CAPITALS_SEMANTIC["faction_mobei"]

# 势力首都映射（坐标格式 — 从 faction_territories.json 动态加载或使用硬编码回退）
# 3.2修复：运行时自动从 faction_territories.json 同步，解决 tile_yingtian vs "26,15" 不一致
FACTION_CAPITALS = {
    "faction_yuan":          "24,8",
    "faction_xushouhui":     "22,13",
    "faction_zhuyuanzhang":  "26,15",
    "faction_chenyouliang":  "20,17",
    "faction_zhangshicheng": "28,16",
    "faction_mingyuzhen":    "14,14",
    "faction_fangguozhen":   "29,18",
    "faction_wangbaobao":    "14,18",
    "faction_mobei":         "18,4",
}
FACTION_CAPITALS["faction_hansong"] = FACTION_CAPITALS["faction_xushouhui"]
FACTION_CAPITALS["faction_liangwang"] = FACTION_CAPITALS["faction_wangbaobao"]
FACTION_CAPITALS["faction_chenyouding"] = FACTION_CAPITALS["faction_mobei"]

# 势力初始地块
# 注：已统一为 factions.json 的新ID体系，与 factions.json 的 initial_territory 保持一致
FACTION_STARTER_TILES = {
    "faction_yuan": [
        "tile_dadu",
        "tile_jinan", "tile_zhending", "tile_baoding", "tile_hejian",
        "tile_daming", "tile_xian",
        "tile_suzhou_gs", "tile_ningxia",
    ],
    "faction_xushouhui": [
        "tile_xiangyang", "tile_huangzhou", "tile_de_an", "tile_runing",
        "tile_yingzhou", "tile_nanyang",
    ],
    "faction_zhuyuanzhang": [
        "tile_yingtian", "tile_chuzhou", "tile_hezhou", "tile_taiping",
        "tile_zhenjiang", "tile_changzhou", "tile_huizhou", "tile_ningguo",
        "tile_guangde", "tile_raozhou", "tile_xinzhou",
    ],
    "faction_chenyouliang": [
        "tile_wuchang", "tile_jiangzhou", "tile_yuezhou", "tile_changsha",
        "tile_hengzhou", "tile_jingjiang", "tile_longxing", "tile_jian",
        "tile_ganzhou_jx", "tile_jingzhou", "tile_yichang",
    ],
    "faction_zhangshicheng": [
        "tile_pingjiang", "tile_hangzhou", "tile_songjiang", "tile_huzhou",
        "tile_jiaxin", "tile_shaoxing", "tile_gaoyou", "tile_yangzhou",
        "tile_taizhou_js",
    ],
    "faction_mingyuzhen": [
        "tile_chongqing", "tile_chengdu", "tile_kuizhou", "tile_baoning",
        "tile_xuzhou_sc", "tile_zunyi", "tile_shunqing", "tile_jiading",
    ],
    "faction_fangguozhen": [
        "tile_qingyuan", "tile_taizhou_zj", "tile_wenzhou", "tile_zhoushan",
    ],
    "faction_wangbaobao": [
        "tile_taiyuan", "tile_datong", "tile_pingyang", "tile_yanan",
        "tile_ganzhou", "tile_lintao",
    ],
    "faction_mobei": [
        "tile_helin", "tile_karakorum", "tile_shangdu",
        "tile_liaoyang", "tile_shenyang",
    ],
}

# 向后兼容：保留旧ID别名
FACTION_STARTER_TILES["faction_hansong"] = FACTION_STARTER_TILES["faction_xushouhui"]
FACTION_STARTER_TILES["faction_liangwang"] = FACTION_STARTER_TILES["faction_wangbaobao"]
FACTION_STARTER_TILES["faction_chenyouding"] = FACTION_STARTER_TILES["faction_mobei"]


class GameInitializer:
    """从配置文件生成初始 WorldState"""

    def __init__(self):
        self._factions_config: dict = {}
        self._game_const: dict = {}
        self._load_configs()

    def _load_configs(self):
        try:
            with open(CONFIG_DIR / "factions.json", "r", encoding="utf-8") as f:
                self._factions_config = json.load(f)
        except Exception as e:
            logger.warning(f"势力配置加载失败: {e}")
            self._factions_config = {"factions": {}}

        try:
            import yaml
            with open(CONFIG_DIR / "game_const.yaml", "r", encoding="utf-8") as f:
                self._game_const = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"游戏常量加载失败: {e}")
            self._game_const = {}

    def create_world(
        self,
        player_faction_id: str,
        game_mode: str = "player_turn",
        custom_faction: Optional[dict] = None,
    ) -> WorldState:
        """
        生成完整初始 WorldState

        Args:
            player_faction_id: 玩家选择的势力ID（历史开局）或自定义ID（自创开局）
            game_mode: player_turn / ai_watch
            custom_faction: 自创王朝参数（可选）
        """
        world = WorldState(
            current_round=0,
            current_year=1351,
            current_month=4,
            current_season=Season.SPRING,
            player_faction_id=player_faction_id,  # 核心规则：标记玩家操控势力
            game_mode=game_mode,
            version="4.0",
        )

        # 1. 生成势力
        self._init_factions(world, player_faction_id, custom_faction)

        # 2. 生成地块
        self._init_tiles(world)

        # 3. 建立初始外交关系
        self._init_relations(world)

        # 4. 生成初始官员
        self._init_officials(world)

        # 5. 初始化武将（3.0 各势力初始武将）
        self._init_generals(world)

        # 6. 初始日志
        world.events_log.append({
            "event_id": "game_start_0",
            "event_type": "game_start",
            "round": 0,
            "year": 1351,
            "month": 4,
            "season": "春",
            "title": "至正十一年·天下大乱",
            "description": "黄河泛滥，韩山童刘福通揭竿而起，红巾起义席卷中原。元廷衰微，群雄逐鹿天下。",
            "severity": "major",
            "faction_id": "",
            "tile_id": "",
            "effects": {},
            "narrative": "至正十一年（1351年），黄河决口，韩山童、刘福通以「石人一只眼，挑动黄河天下反」为号，在颍州揭竿而起。红巾军起义席卷中原，天下群雄并起，元廷统治摇摇欲坠。",
        })

        world.mark_updated()
        return world

    def _init_factions(self, world: WorldState, player_id: str, custom: Optional[dict]):
        """初始化所有势力"""
        factions_cfg = self._factions_config.get("factions", {})

        for fid, cfg in factions_cfg.items():
            is_player = (fid == player_id)
            starter_tiles = FACTION_STARTER_TILES.get(fid, [])
            tile_count = len(starter_tiles)

            # 从配置读取初始资源（兼容 resources 嵌套对象 和 平铺字段两种格式）
            resources = cfg.get("resources", {})
            treasury = resources.get("treasury") or cfg.get("initial_treasury", 5000)
            grain = resources.get("grain") or cfg.get("initial_grain", 3000)
            arms = resources.get("arms") or cfg.get("initial_arms", 500)
            horses = resources.get("horses") or cfg.get("initial_horses", 200)
            troops = resources.get("troops") or cfg.get("initial_troops", 3000)
            reputation = cfg.get("base_reputation") or cfg.get("initial_reputation", 50)
            # 3.2修复: 确保 troops 和 total_troops 使用相同值，population 正确设置
            total_pop = tile_count * 50000
            # P3: 防御 cfg 为非 dict 类型导致的 AttributeError
            if not isinstance(cfg, dict):
                logger.warning(f"势力 {fid} 配置不是 dict 类型（{type(cfg).__name__}），跳过")
                continue
            try:
                faction = FactionState(
                    faction_id=fid,
                    name=cfg.get("name", fid),
                    title=cfg.get("title", ""),
                    color=FACTION_COLORS.get(fid, "#666666"),
                    capital_tile=FACTION_CAPITALS.get(fid, ""),
                    is_player=is_player,
                    is_alive=True,
                    treasury=treasury,
                    grain=grain,
                    arms=arms,
                    horses=horses,
                    reputation=reputation,
                    troops=troops,            # 3.2修复: 同时设置 troops 字段
                    total_troops=troops,
                    population=total_pop,      # 3.2修复: 同时设置 population 字段
                    total_population=total_pop,
                    ruler_name=cfg.get("ruler_name", cfg.get("name", fid)),  # Bug #36修复: 设置统治者名称
                    court_stability=cfg.get("base_stability", 50),
                    realm_stability=cfg.get("base_stability", 50),
                    development_level=cfg.get("base_development", 20),
                    tile_count=tile_count,
                    personality_tags=cfg.get("personality_tags", []),
                    buffs=[{**b, "source": "开局特性"} for b in cfg.get("buffs", [])],
                    debuffs=[{**d, "source": "开局特性"} for d in cfg.get("debuffs", [])],
                )
                world.factions[fid] = faction
            except Exception as e:
                logger.error(f"创建势力 {fid} 失败（跳过）: {type(e).__name__}: {e}", exc_info=True)

        # 自创王朝：覆盖或新增势力
        if custom:
            custom_id = custom.get("faction_id", "custom_player")
            custom_faction = FactionState(
                faction_id=custom_id,
                name=custom.get("name", "新朝"),
                title=custom.get("title", "开国君主"),
                color=custom.get("color", "#B89B68"),
                capital_tile=custom.get("capital_tile", ""),
                is_player=True,
                is_alive=True,
                treasury=custom.get("treasury", 2000),
                grain=custom.get("grain", 1500),
                arms=custom.get("arms", 200),
                horses=custom.get("horses", 100),
                reputation=40,
                total_troops=custom.get("troops", 1500),
                total_population=100000,
                court_stability=60,
                realm_stability=55,
                development_level=15,
            )
            world.factions[custom_id] = custom_faction

    def _init_tiles(self, world: WorldState):
        """CK3风格初始化 - 从GeoJSON加载真实多边形领地（替代六边形网格）

        加载顺序：
        1. 行省级GeoJSON → 行省级TileState
        2. 路府级GeoJSON → 路府级TileState
        3. 根据 factions.json 的 provinces/prefectures 分配势力归属
        """
        import random
        rng = random.Random(1351)

        # 构建势力→领地映射（从factions.json读取）
        faction_territories = self._build_faction_territories()

        # 1. 加载行省GeoJSON
        provinces_path = MAP_DATA_DIR / "provinces.geojson"
        province_data = []
        if provinces_path.exists():
            try:
                with open(provinces_path, "r", encoding="utf-8") as f:
                    geojson = json.load(f)
                province_data = geojson.get("features", [])
            except Exception as e:
                logger.error(f"加载行省GeoJSON失败: {e}")

        # 2. 生成行省级地块
        for feature in province_data:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            pid = props.get("id", "")
            if not pid:
                continue

            centroid = self._calc_centroid(geom)
            faction_id = self._resolve_faction(pid, faction_territories)

            tile = self._create_tile_from_geojson(
                tile_id=pid,
                props=props,
                centroid=centroid,
                admin_level="province",
                province_id="",
                faction_id=faction_id,
                rng=rng,
            )
            world.tiles[pid] = tile

        # 3. 加载路府GeoJSON
        prefectures_path = MAP_DATA_DIR / "prefectures.geojson"
        pref_data = []
        if prefectures_path.exists():
            try:
                with open(prefectures_path, "r", encoding="utf-8") as f:
                    geojson = json.load(f)
                pref_data = geojson.get("features", [])
            except Exception as e:
                logger.warning(f"加载路府GeoJSON失败（非致命）: {e}")

        for feature in pref_data:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            pid = props.get("id", "")
            if not pid:
                continue

            centroid = self._calc_centroid(geom)
            faction_id = self._resolve_faction(pid, faction_territories)
            province_id = props.get("province", "")

            tile = self._create_tile_from_geojson(
                tile_id=pid,
                props=props,
                centroid=centroid,
                admin_level="prefecture",
                province_id=province_id,
                faction_id=faction_id,
                rng=rng,
            )
            world.tiles[pid] = tile

        # FALLBACK: GeoJSON 不可用时从 map_final.json + faction_territories.json 初始化
        if len(world.tiles) == 0:
            self._init_tiles_from_map_final(world, rng)
            return

        logger.info(f"CK3领地初始化完成: {len(world.tiles)} 个领地（行省+路府）")

    def _init_tiles_from_map_final(self, world: WorldState, rng):
        """
        GeoJSON 数据不可用时的回退方案：
        优先从 server/data/map/map_full.json (含海域) 加载，
        回退到 map_final.json + sea_generator。
        
        faction_territories 使用 "col,row" 格式引用格子，
        需要与 map_final.json 中每格的 col/row 进行匹配。
        """
        # 优先加载含海域的完整地图
        map_full_path = SERVER_MAP_DATA_DIR / "map_full.json"
        map_final_path = SERVER_MAP_DATA_DIR / "map_final.json"

        if map_full_path.exists():
            map_path = map_full_path
            logger.info("使用 map_full.json (含海域)")
        elif map_final_path.exists():
            map_path = map_final_path
            logger.info("使用 map_final.json (仅陆地)")
        else:
            logger.warning("map_final.json 也不存在，无法初始化地块")
            return

        try:
            with open(map_path, "r", encoding="utf-8") as f:
                map_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"地图数据 JSON 解析失败 ({map_path}): {e}")
            return
        except (IOError, OSError) as e:
            logger.error(f"地图文件读取失败 ({map_path}): {e}")
            return

        # 加载势力领地映射（col,row → faction_id）
        faction_tile_map: dict[str, str] = {}
        ft_path = SERVER_MAP_DATA_DIR / "faction_territories.json"
        if ft_path.exists():
            with open(ft_path, "r", encoding="utf-8") as f:
                ft_data = json.load(f)
            for fid, fdata in ft_data.get("factions", {}).items():
                for coord_str in fdata.get("tiles", []):
                    faction_tile_map[coord_str.strip()] = fid

        # 地形字符串 → TileType 枚举映射
        terrain_map: dict[str, TileType] = {
            "farmland": TileType.FARMLAND,
            "mountain": TileType.MOUNTAIN,
            "water":     TileType.WATER,
            "coast":     TileType.COAST,
            "city":      TileType.CITY,
            "pass":      TileType.PASS,
            "port":      TileType.PORT,
            "desert":    TileType.DESERT,
            "grassland": TileType.GRASSLAND,
            "sea":       TileType.SEA,
        }

        tiles_data = map_data.get("tiles", [])
        assigned_count = 0
        # 首都集合：优先使用 faction_territories.json 的 capital 字段，回退到首格
        capital_set: set[str] = set()
        if ft_path.exists():
            for fid, fdata in ft_data.get("factions", {}).items():
                capital_coord = fdata.get("capital", "").strip()
                if capital_coord:
                    capital_set.add(capital_coord)
                else:
                    tile_coords = fdata.get("tiles", [])
                    if tile_coords:
                        capital_set.add(tile_coords[0].strip())  # 回退：首格为首都

        for t in tiles_data:
            tile_id = str(t.get("tile_id", ""))
            if not tile_id:
                continue

            tile_name = t.get("tile_name", tile_id)
            terrain_str = t.get("terrain", "farmland")
            tile_type = terrain_map.get(terrain_str.lower(), TileType.FARMLAND)

            # 通过 col,row 坐标匹配势力归属
            col = int(t.get("col", 0))
            row = int(t.get("row", 0))
            coord_key = f"{col},{row}"
            faction_id = faction_tile_map.get(coord_key, "")

            # 数值初始化
            is_sea = (terrain_str.lower() == "sea")
            is_capital = t.get("is_capital", False) or (coord_key in capital_set)
            is_city = (tile_type == TileType.CITY or is_capital)

            if is_sea:
                # 海域地块：无人口/驻军/粮草，但拥有海洋资源
                pop = 0
                troops_val = 0
                grain_val = 0
                morale_val = 0
                treasury_val = 0
                fort_val = 0
                faction_id = ""  # 海域无势力归属
                supply_capacity = 0
                is_supply_base = False
            else:
                pop = t.get("population") or (rng.randint(80000, 200000) if is_city else rng.randint(10000, 60000))
                troops_val = t.get("troops") or (rng.randint(2000, 4000) if is_city and faction_id else rng.randint(200, 1000) if faction_id else 0)
                grain_val = t.get("grain") or (rng.randint(1500, 3000) if is_city else rng.randint(300, 1000))
                morale_val = t.get("morale") or (rng.randint(55, 75) if is_city else rng.randint(40, 55))
                treasury_val = t.get("treasury") or (rng.randint(3000, 8000) if is_city else rng.randint(500, 2000))
                fort_val = t.get("fortification") or (5 if is_capital else 3 if is_city else rng.randint(0, 2))
                supply_capacity = 200 if is_city else 100
                is_supply_base = is_city

            # 邻居列表（map_final.json 中预计算）
            neighbors = t.get("neighbors", [])
            if isinstance(neighbors, list):
                neighbors = [str(n) for n in neighbors]

            tile = TileState(
                tile_id=tile_id,
                tile_name=tile_name,
                tile_type=tile_type,
                region=t.get("province", ""),
                faction_id=faction_id,
                population=int(pop),
                troops=int(troops_val),
                grain=int(grain_val),
                morale=int(morale_val),
                treasury=int(treasury_val),
                fortification=int(fort_val),
                admin_level="county",
                province_id=str(t.get("province_id", "")),
                q=int(t.get("q", 0)),
                r=int(t.get("r", 0)),
                is_capital=is_capital,
                is_port=bool(t.get("is_port", False)),
                # Bug #38修复: pixel_x/pixel_y → 使用centroid_lon/centroid_lat字段名
                centroid_lon=float(t.get("centroid_lon", t.get("pixel_x", 0))),
                centroid_lat=float(t.get("centroid_lat", t.get("pixel_y", 0))),
                neighbors=neighbors,
                supply_capacity=supply_capacity,
                is_supply_base=is_supply_base,
            )
            world.tiles[tile_id] = tile
            if faction_id:
                assigned_count += 1

        logger.info(f"从 map_final.json 初始化地块完成: {len(world.tiles)} 个（{assigned_count} 个有主，覆盖 {len(faction_tile_map)} 个势力格子）")
        # Bug #40修复: 清理死代码 — mapping构建逻辑已移至_build_faction_territories()

    def _build_faction_territories(self) -> dict[str, str]:
        """构建 tile_id → faction_id 映射（从 factions.json 的 initial_territory 读取）"""
        mapping: dict[str, str] = {}
        factions_dict = self._factions_config.get("factions", {})
        if isinstance(factions_dict, dict):
            for fid, fcfg in factions_dict.items():
                if not isinstance(fcfg, dict):
                    continue
                for tid in fcfg.get("initial_territory", []):
                    if tid not in mapping:
                        mapping[tid] = fid
        return mapping

    def _resolve_faction(self, territory_id: str, mapping: dict) -> str:
        """解析领地归属势力"""
        return mapping.get(territory_id, "")

    def _calc_centroid(self, geometry: dict) -> tuple[float, float]:
        """计算多边形质心（用于前端渲染定位）"""
        coords = []
        if geometry.get("type") == "Polygon":
            rings = geometry.get("coordinates", [])
            if rings:
                coords = rings[0]
        elif geometry.get("type") == "MultiPolygon":
            # 取第一个多边形的外环
            rings = geometry.get("coordinates", [[]])
            if rings and rings[0]:
                coords = rings[0][0]

        if not coords:
            return 0.0, 0.0

        n = len(coords)
        if n == 0:
            return 0.0, 0.0

        # 简单算术平均质心
        sum_lon = sum(c[0] for c in coords)
        sum_lat = sum(c[1] for c in coords)
        return sum_lon / n, sum_lat / n

    def _create_tile_from_geojson(
        self, tile_id: str, props: dict, centroid: tuple,
        admin_level: str, province_id: str, faction_id: str,
        rng,
    ) -> TileState:
        """从GeoJSON属性创建TileState"""
        name = props.get("name", tile_id)
        population = props.get("population", rng.randint(50000, 200000))
        garrison = props.get("garrison", 0)
        morale = props.get("morale", 50)
        tax = props.get("tax_revenue", 0)

        # 地形推断：根据行省位置大致判定
        region = tile_id
        tile_type = self._infer_tile_type_from_province(tile_id, props)

        # 城池判定
        is_capital = False
        capitals = props.get("capitals", [])
        if isinstance(capitals, list):
            # 路府首都匹配
            if admin_level == "prefecture" and tile_id in capitals:
                is_capital = True
            # 行省都府（其路府列表的首个即为行省治所）
            if admin_level == "province" and capitals:
                # 行省级别的首府标记
                is_capital = True

        # 覆盖：势力首都强制标记
        if FACTION_CAPITALS.get(faction_id) == tile_id:
            is_capital = True

        # 数值计算
        is_city = (tile_type == TileType.CITY or is_capital)
        pop = population if population > 0 else (150000 if is_city else rng.randint(30000, 120000))
        troops_val = garrison if garrison > 0 else (3000 if is_city else rng.randint(500, 2000)) if faction_id else 0
        grain_val = tax // 3 if tax > 0 else (2000 if is_city else rng.randint(500, 1500))
        morale_val = morale if morale > 0 else (65 if is_city else rng.randint(40, 60))
        treasury_val = tax if tax > 0 else (5000 if is_city else rng.randint(1000, 3000))
        fort_val = 5 if is_capital else (3 if is_city else rng.randint(0, 2))

        # 特殊效果
        special_effect = None
        if tile_type == TileType.PASS:
            special_effect = "关隘天险·守军防御+40%"
        elif tile_id in ("lingbei", "xiyu", "liaoyang"):
            special_effect = "边境行省·征募骑兵+20%"
        elif tile_id in ("jiangzhe", "jiangxi", "huguang"):
            special_effect = "富庶之地·税收+15%"

        return TileState(
            tile_id=tile_id,
            tile_name=name,
            tile_type=tile_type,
            region=region,
            faction_id=faction_id,
            admin_level=admin_level,
            province_id=province_id,
            centroid_lon=centroid[0],
            centroid_lat=centroid[1],
            population=pop,
            troops=troops_val,
            grain=grain_val,
            morale=morale_val,
            treasury=treasury_val,
            fortification=fort_val,
            is_capital=is_capital,
            is_port=(tile_type == TileType.PORT),
            special_effect=special_effect,
        )

    def _infer_tile_type_from_province(self, tile_id: str, props: dict) -> TileType:
        """根据行省/路府名称推断地块类型"""
        # 行省级别地形
        province_terrain = {
            "zhongshu": TileType.FARMLAND,      # 华北平原
            "henanjiang": TileType.FARMLAND,     # 中原
            "jiangzhe": TileType.FARMLAND,       # 江南
            "jiangxi": TileType.FARMLAND,        # 江西
            "huguang": TileType.FARMLAND,        # 湖广
            "sichuan": TileType.MOUNTAIN,        # 四川盆地周边多山
            "shanxi": TileType.GRASSLAND,        # 关中/陕西
            "gansu": TileType.DESERT,            # 河西走廊
            "yunnan": TileType.MOUNTAIN,         # 云贵高原
            "liaoyang": TileType.GRASSLAND,      # 东北平原
            "lingbei": TileType.GRASSLAND,       # 蒙古草原
            "xuanzheng": TileType.MOUNTAIN,      # 青藏高原
            "xiyu": TileType.DESERT,             # 西域
        }

        # 路府级别地形（部分重要路府）
        prefecture_terrain = {
            "dadoulu": TileType.CITY,            # 大都
            "bianlianglu": TileType.CITY,        # 汴梁
            "jiqinglu": TileType.CITY,           # 集庆/南京
            "hangzhoulu": TileType.CITY,         # 杭州
            "wuchanglu": TileType.CITY,          # 武昌
            "chengdulu": TileType.CITY,          # 成都
            "chongqinglu": TileType.CITY,        # 重庆
            "fengyuanlu": TileType.CITY,         # 奉元/西安
            "guangzhoulu": TileType.CITY,        # 广州
            "fuzhoulu": TileType.COAST,          # 福州（沿海）
            "ganzhoulu": TileType.GRASSLAND,     # 甘州
            "liaoyanglu": TileType.GRASSLAND,    # 辽阳
            "zhongqinglu": TileType.MOUNTAIN,    # 中庆/昆明
        }

        if tile_id in prefecture_terrain:
            return prefecture_terrain[tile_id]
        if tile_id in province_terrain:
            return province_terrain[tile_id]
        return TileType.FARMLAND

    def _init_relations(self, world: WorldState):
        """建立势力间初始外交关系"""
        # 从配置读取初始关系（兼容 attacker/defender 和 faction_a/faction_b 两种字段名）
        counter_relations = self._factions_config.get("counter_relations", [])
        rel_map = {}
        for cr in counter_relations:
            a = cr.get("faction_a") or cr.get("attacker", "")
            b = cr.get("faction_b") or cr.get("defender", "")
            stance = cr.get("stance", "neutral")
            attitude = cr.get("attitude", cr.get("relation", 0))
            if not a or not b:
                continue
            key = WorldState.relation_key(a, b)
            rel_map[key] = (stance, attitude)

        faction_ids = list(world.factions.keys())
        for i in range(len(faction_ids)):
            for j in range(i + 1, len(faction_ids)):
                a, b = faction_ids[i], faction_ids[j]
                key = WorldState.relation_key(a, b)
                stance_str, attitude = rel_map.get(key, ("neutral", 0))

                try:
                    stance = DiplomaticStance(stance_str)
                except ValueError:
                    stance = DiplomaticStance.NEUTRAL

                world.relations[key] = RelationState(
                    faction_a=a,
                    faction_b=b,
                    stance=stance,
                    attitude=attitude,
                )

    def _init_generals(self, world: WorldState):
        """为每个势力生成初始武将（3.0 武将人格战术系统）"""
        from server.core.general_engine import GeneralEngine
        engine = GeneralEngine(world)

        # 初始化 generals 存储字典
        if "_generals" not in world.__dict__:
            world.__dict__["_generals"] = {}
        if "_legions" not in world.__dict__:
            world.__dict__["_legions"] = {}

        for fid in world.factions:
            faction_generals = engine.init_faction_generals(fid)
            world.__dict__["_generals"][fid] = faction_generals
            logger.info(f"势力 {fid} 初始武将: {len(faction_generals)} 人")

    def _init_officials(self, world: WorldState):
        """为每个势力生成初始文臣武将（从 factions.json 的 adviser_team 加载）"""
        # 从 NPC 数据中获取谋士团
        npc_path = SERVER_DIR / "data" / "npc_ministers.json"
        npc_map = {}
        try:
            with open(npc_path, "r", encoding="utf-8") as f:
                npc_data = json.load(f)
            npc_map = {npc["npc_id"]: npc for npc in npc_data.get("ministers", [])}
        except Exception as e:
            logger.warning(f"加载 NPC 谋士数据失败: {e}")

        # 从 factions.json 读取各势力 adviser_team
        factions_config = self._factions_config.get("factions", {})
        for fid, fconfig in factions_config.items():
            adviser_ids = fconfig.get("adviser_team", [])
            for idx, aid in enumerate(adviser_ids):
                npc = npc_map.get(aid, {})
                oid = f"adviser_{fid}_{aid}"
                name = npc.get("name", aid)
                pos = npc.get("title", "谋臣")
                loyalty = npc.get("loyalty", 60)
                ability = npc.get("wisdom", 60)
                aff = npc.get("role_label", "文臣")

                world.officials[oid] = OfficialRecord(
                    official_id=oid,
                    name=name,
                    faction_id=fid,
                    position=pos,
                    loyalty=loyalty,
                    ability=ability,
                    faction_affiliation=aff,
                )
                if fid in world.factions:
                    world.factions[fid].officials.append(oid)

            logger.info(f"势力 {fid} 初始谋士团: {len(adviser_ids)} 人")


# 全局单例
_initializer: Optional[GameInitializer] = None


def get_initializer() -> GameInitializer:
    global _initializer
    if _initializer is None:
        _initializer = GameInitializer()
    return _initializer
