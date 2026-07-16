"""
WorldState - 类型化的全局游戏状态
替代原 global_world_state 单一大dict
3.0 重构核心：强类型 Pydantic 模型
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime


class Season(str, Enum):
    SPRING = "春"
    SUMMER = "夏"
    AUTUMN = "秋"
    WINTER = "冬"


class TileType(str, Enum):
    FARMLAND = "farmland"
    MOUNTAIN = "mountain"
    WATER = "water"
    COAST = "coast"
    COASTAL = "coastal"
    CITY = "city"
    PASS = "pass"
    PORT = "port"
    DESERT = "desert"
    GRASSLAND = "grassland"
    HILL = "hill"
    WETLAND = "wetland"
    FOREST = "forest"
    TUNDRA_FOREST = "tundra_forest"
    OASIS = "oasis"
    SEA = "sea"             # 海洋地块 (v4.1)


class DisasterType(str, Enum):
    FLOOD = "flood"
    DROUGHT = "drought"
    LOCUST = "locust"
    PLAGUE = "plague"
    WAR_DEVASTATION = "war_devastation"
    REFUGEE_WAVE = "refugee_wave"      # 流民潮
    MUTINY = "mutiny"                   # 兵变
    BANDIT_RAID = "bandit_raid"         # 匪患劫掠
    BLIZZARD = "blizzard"               # 暴雪冻害


class BuildingType(str, Enum):
    """建筑类型枚举"""
    FARMLAND = "farmland"        # 农田 - 粮食产出
    WORKSHOP = "workshop"        # 工坊 - 银两产出 + 发展度
    BEACON = "beacon"            # 烽燧 - 视野 + 预警
    DOCK = "dock"                # 码头 - 贸易 + 水军
    BARRACKS = "barracks"        # 征兵营 - 自动募兵
    GRANARY = "granary"          # 粮仓 - 储粮上限
    CLINIC = "clinic"            # 医馆 - 瘟疫抵抗
    ARMORY = "armory"            # 军械所 - 兵器产出
    STABLE = "stable"            # 马场 - 战马产出
    TEMPLE = "temple"            # 宗庙 - 民心加成
    WALL = "wall"                 # 城墙 - 城防加成


class PolicyType(str, Enum):
    """国策类型枚举"""
    LIGHT_TAX = "light_tax"              # 轻徭薄赋
    HEAVY_AGRICULTURE = "heavy_agriculture"  # 重农抑商
    BAOJIA = "baojia"                    # 保甲连坐
    MILITARY_FARM = "military_farm"      # 军屯养兵
    CIVIL_EXAM = "civil_exam"            # 开科取士
    STRICT_LAW = "strict_law"            # 严刑峻法
    REWARD_FARM_WAR = "reward_farm_war"  # 奖励耕战
    CORVEE_LABOR = "corvee_labor"        # 徭役征发


class SiegeState(str, Enum):
    SIEGING = "sieging"
    ASSAULTING = "assaulting"
    BREACHED = "breached"
    RELIEVED = "relieved"


class DiplomaticStance(str, Enum):
    WAR = "war"
    NEUTRAL = "neutral"
    TRUCE = "truce"
    ALLIANCE = "alliance"
    VASSAL = "vassal"
    TRIBUTE = "tribute"  # 3.0: 纳贡状态


class FactionState(BaseModel):
    """势力状态"""
    model_config = {"extra": "allow"}  # 允许动态添加字段（如 ruler_age, heirs 等）

    faction_id: str
    name: str
    title: str = ""
    color: str = "#000000"
    capital_tile: str = ""
    is_player: bool = False
    is_alive: bool = True

    # 君主信息
    ruler_name: str = ""
    ruler_age: int = 40

    # 核心资源
    treasury: int = 0
    grain: int = 0
    arms: int = 0
    horses: int = 0
    reputation: int = 50
    total_troops: int = 0
    total_population: int = 0
    population: int = 0  # 总人口
    troops: int = 0  # 总兵力

    # 朝堂
    court_stability: int = 50
    realm_stability: int = 50
    development_level: int = 20

    # 派系忠诚度
    faction_loyalties: dict[str, int] = Field(default_factory=dict)

    # 人格标签
    personality_tags: list[str] = Field(default_factory=list)

    # 已解锁国策
    unlocked_policies: list[str] = Field(default_factory=list)

    # 官员列表
    officials: list[str] = Field(default_factory=list)

    # 俘虏
    prisoners: list[str] = Field(default_factory=list)

    # 宗室
    heirs: list[dict] = Field(default_factory=list)  # 皇子列表

    # 属性
    buffs: list[dict] = Field(default_factory=list)
    debuffs: list[dict] = Field(default_factory=list)

    # 地盘统计（每次回合结算时由引擎更新）
    tile_count: int = 0

    # 税收政策标记（normal / heavy），存档/读档保持
    tax_policy: str = "normal"


class TileState(BaseModel):
    """地块状态 - CK3风格自由多边形领地（替代原六边形网格）

    核心变更（3.0→3.2）：
    - 移除 q/r 六边形坐标主导地位，改用 admin_level / province_id 层级关系
    - tile_id 直接对应 GeoJSON Feature ID（如 "zhongshu" / "dadoulu"）
    - 邻接关系由 TerritoryGraph 管理，不再硬编码六边形方向
    - 保留 centroid_lon/centroid_lat 用于前端渲染定位
    - 保留 q/r 字段向后兼容（默认0）
    """
    model_config = {"extra": "allow"}  # 允许动态字段

    tile_id: str
    tile_name: str = ""
    tile_type: TileType = TileType.FARMLAND
    region: str = ""

    faction_id: str = ""
    population: int = 0
    troops: int = 0
    grain: int = 0
    morale: int = 50
    treasury: int = 0

    # CK3领地层级
    admin_level: str = "province"  # province / prefecture / county
    province_id: str = ""  # 所属行省ID（路府/州县级别）

    # 多边形质心坐标（等距矩形投影用）
    centroid_lon: float = 0.0
    centroid_lat: float = 0.0

    # 六边形坐标（Axial坐标系）- 保留兼容，新代码不应使用
    q: int = 0
    r: int = 0

    # 民生
    refugee_ratio: float = 0.0
    development_level: int = 0  # 发展度等级
    water_works: int = 0
    granary: int = 0
    clinic: int = 0

    # 军事
    fortification: int = 0
    siege_state: Optional[SiegeState] = None
    garrison_resting: bool = False
    elite_ratio: float = 0.0  # 精锐比例 0.0~1.0
    stable: int = 0  # 马场等级
    armory: int = 0  # 军械所等级

    # 灾害
    disasters: list[DisasterType] = Field(default_factory=list)

    # 城建基建
    buildings: dict[str, Building] = Field(default_factory=dict)  # building_id → Building
    public_order: int = 50        # 治安 (0~100, 越低越乱)
    corvee_burden: int = 0        # 徭役负担 (0~100, 越高民怨越大)

    # 补给
    supply_capacity: int = 100    # 补给容量
    is_supply_base: bool = False  # 是否补给基地（城池/首都自动为True）

    # 特殊
    is_capital: bool = False
    is_port: bool = False
    special_effect: Optional[str] = None
    # Bug #39修复: 显式声明neighbors字段
    neighbors: list[str] = Field(default_factory=list)
    # Bug #12修复: 围城部队归属标记
    sieging_faction: str = ""


class RelationState(BaseModel):
    """双边关系"""
    model_config = {"extra": "allow"}  # 3.0: 允许动态附加 tribute_payer/vassal_suzerain 等字段
    faction_a: str
    faction_b: str
    stance: DiplomaticStance = DiplomaticStance.NEUTRAL
    attitude: int = 0
    treaty_expiry: int = 0
    trade_active: bool = False
    coalition_id: str = ""
    hostage_sent: bool = False  # 3.2: 质子派遣状态


class SpyNetwork(BaseModel):
    """细作网络"""
    owner_faction: str
    target_faction: str
    spies_count: int = 0
    infiltration: int = 0
    action_points: int = 0  # 每回合可用行动点数
    discovered: bool = False


class SiegeRecord(BaseModel):
    """围城记录"""
    siege_id: str
    attacker_faction: str
    defender_faction: str
    tile_id: str
    siege_rounds: int = 0
    attacker_troops: int = 0
    defender_troops: int = 0
    wall_damage: float = 0.0


class TreatyRecord(BaseModel):
    """条约记录"""
    treaty_id: str
    treaty_type: str
    factions: list[str]
    signed_round: int
    expires_round: int
    terms: dict = Field(default_factory=dict)


class OfficialRecord(BaseModel):
    """官员记录"""
    official_id: str
    name: str
    faction_id: str
    position: str = ""
    loyalty: int = 50
    ability: int = 50
    is_exiled: bool = False
    faction_affiliation: str = ""


class PrisonerRecord(BaseModel):
    """俘虏记录"""
    prisoner_id: str
    name: str
    captured_from: str
    held_by: str
    rank: str = "general"
    captured_round: int = 0


class TileChangeRecord(BaseModel):
    """地盘变更记录"""
    change_id: str
    round: int = 0
    tile_id: str = ""
    tile_name: str = ""
    region: str = ""
    old_faction_id: str = ""
    new_faction_id: str = ""
    old_faction_name: str = ""
    new_faction_name: str = ""
    change_type: str = "conquer"  # conquer(占领), lose(失去), settle(开拓), abandon(放弃)
    troops_involved: int = 0
    battle_result: str = ""  # victory/defeat/stalemate/peaceful
    narrative: str = ""


class RebelArmy(BaseModel):
    """叛军"""
    rebel_id: str
    tile_id: str
    troops: int = 0
    leader: str = ""
    cause: str = ""
    spawned_round: int = 0


class Building(BaseModel):
    """地块建筑模型"""
    building_id: str
    building_type: BuildingType = BuildingType.FARMLAND
    tile_id: str = ""
    faction_id: str = ""
    level: int = 1           # 建筑等级 (1~5)
    hp: int = 100            # 耐久度
    built_round: int = 0     # 建造完成的回合


class SupplyLine(BaseModel):
    """补给线模型"""
    line_id: str
    faction_id: str
    source_tile: str        # 补给来源（城池/己方领土）
    target_tile: str        # 部队所在地块
    distance: int = 0       # 距离（格数）
    is_broken: bool = False  # 是否被切断
    attrition_rate: float = 0.0  # 逃散率 (0.0~0.15)


class WorldState(BaseModel):
    """
    全局世界状态 - 3.0 类型化核心

    替代原 global_world_state 字典
    所有子Agent通过此模型读写世界状态
    """
    model_config = {"extra": "allow"}  # 允许动态字段

    # 回合与时间
    current_round: int = 0
    current_year: int = 1351
    current_month: int = 4
    current_season: Season = Season.SPRING

    @field_validator('current_season', mode='before')
    @classmethod
    def coerce_season(cls, v):
        """确保 current_season 始终是 Season 枚举（兼容 JSON 加载时的字符串）"""
        if isinstance(v, str):
            try:
                return Season(v)
            except ValueError:
                return Season.SPRING
        return v

    # 玩家势力标识（核心规则：该势力A2 RulerAgent强制休眠，行为100%由玩家手动指令驱动）
    player_faction_id: str = ""

    # 势力
    factions: dict[str, FactionState] = Field(default_factory=dict)

    # 地块
    tiles: dict[str, TileState] = Field(default_factory=dict)

    # 外交
    relations: dict[str, RelationState] = Field(default_factory=dict)
    coalitions: dict[str, list[str]] = Field(default_factory=dict)
    alliance_treaties: list[TreatyRecord] = Field(default_factory=list)
    trade_routes: list[dict] = Field(default_factory=list)
    vassal_relations: dict[str, str] = Field(default_factory=dict)

    # 谍报
    spy_networks: dict[str, SpyNetwork] = Field(default_factory=dict)
    spy_intel: list[dict] = Field(default_factory=list)
    planted_false_intel: list[dict] = Field(default_factory=list)

    # 朝堂
    officials: dict[str, OfficialRecord] = Field(default_factory=dict)
    exiled_officials: list[str] = Field(default_factory=list)
    purges: list[dict] = Field(default_factory=list)
    new_officials: list[dict] = Field(default_factory=list)

    # 军事
    siege_states: dict[str, SiegeRecord] = Field(default_factory=dict)
    prisoners: dict[str, PrisonerRecord] = Field(default_factory=dict)
    rebel_armies: dict[str, RebelArmy] = Field(default_factory=dict)
    supply_lines: dict[str, SupplyLine] = Field(default_factory=dict)  # 补给线
    # Bug #34修复: 武将和军团数据声明为正式字段，避免__dict__绕过序列化
    generals: list[dict] = Field(default_factory=list)
    legions: list[dict] = Field(default_factory=list)

    # 国策
    faction_policies: dict[str, list[PolicyType]] = Field(default_factory=dict)  # faction_id → active policies

    # 建筑注册表
    building_registry: dict[str, Building] = Field(default_factory=dict)  # global building_id → Building

    # 事件与历史
    events_log: list[dict] = Field(default_factory=list)
    disasters: list[dict] = Field(default_factory=list)
    decrees: list[dict] = Field(default_factory=list)
    diplomatic_archive: list[dict] = Field(default_factory=list)
    governance_logs: list[dict] = Field(default_factory=list)

    # 地盘变更记录
    tile_changes: list[dict] = Field(default_factory=list)

    # 治政
    govern_merit: dict[str, int] = Field(default_factory=dict)

    # 廷议历史
    debate_history: list[dict] = Field(default_factory=list)

    # 迁都历史
    capital_history: list[dict] = Field(default_factory=list)

    # 天气
    weather: dict = Field(default_factory=dict)

    # 游戏模式
    game_mode: str = "player_turn"

    # 灾厄
    disaster_index: int = 0

    # 元数据
    created_at: str = ""
    updated_at: str = ""
    version: str = "4.0"

    def get_faction(self, faction_id: str) -> Optional[FactionState]:
        return self.factions.get(faction_id)

    def get_tile(self, tile_id: str) -> Optional[TileState]:
        return self.tiles.get(tile_id)

    def get_faction_tiles(self, faction_id: str) -> list[TileState]:
        return [t for t in self.tiles.values() if t.faction_id == faction_id]

    def get_relation(self, faction_a: str, faction_b: str) -> Optional[RelationState]:
        key = self.relation_key(faction_a, faction_b)
        return self.relations.get(key)

    def get_living_factions(self) -> list[FactionState]:
        return [f for f in self.factions.values() if f.is_alive]

    def get_player_faction(self) -> Optional[FactionState]:
        """获取玩家操控势力（优先 player_faction_id，回退 is_player 标志）

        核心规则：player_faction_id 是玩家势力唯一标识，
        在开局时由 create_world 绑定，存档/读档后持续生效。
        """
        # 优先按 player_faction_id 查找（唯一主键）
        if self.player_faction_id and self.player_faction_id in self.factions:
            faction = self.factions[self.player_faction_id]
            if faction.is_alive:
                return faction
        # 回退：按 is_player 标志查找（向后兼容旧存档）
        for f in self.factions.values():
            if f.is_player and f.is_alive:
                return f
        return None

    @staticmethod
    def relation_key(a: str, b: str) -> str:
        """生成两个势力的关系键（排序后拼接）"""
        return "|".join(sorted([a, b]))

    def mark_updated(self):
        self.updated_at = datetime.now().isoformat()

    def to_agent_snapshot(self) -> dict:
        """
        为 AI Agent 生成轻量快照（替代 model_dump()）。

        Agent 管线实际只使用以下字段：
        - A1/A2/A7: factions 摘要 + relations
        - A4: spy_networks
        - A5: disaster_index + current_season
        - A6: relations + factions
        - A8: recent_events

        不包含 tiles（~1300 地块，每个 30 字段），节省 95%+ 序列化开销。
        """
        return {
            "current_round": self.current_round,
            "current_year": self.current_year,
            "current_month": self.current_month,
            "current_season": self.current_season.value if hasattr(self.current_season, 'value') else str(self.current_season),
            "disaster_index": self.disaster_index,
            "player_faction_id": self.player_faction_id,
            # factions: 只保留 AI 决策所需的摘要字段
            "factions": {
                fid: {
                    "name": f.name,
                    "alive": f.is_alive,
                    "troops": f.troops,
                    "total_troops": f.total_troops,
                    "treasury": f.treasury,
                    "grain": f.grain,
                    "reputation": f.reputation,
                    "realm_stability": f.realm_stability,
                    "court_stability": f.court_stability,
                    "tile_count": f.tile_count,
                    "total_population": f.total_population,
                    "neighbors": getattr(f, 'neighbors', []),
                    "heirs": getattr(f, 'heirs', []),
                    "is_player": f.is_player,
                    "is_alive": f.is_alive,
                    "personality_tags": getattr(f, 'personality_tags', []),
                    "capital_tile_id": getattr(f, 'capital_tile_id', ""),
                    "navy_power": getattr(f, 'navy_power', 0),
                }
                for fid, f in self.factions.items()
            },
            # relations: 保留全量（A2/A6 需要）
            "relations": {
                k: v.model_dump() if hasattr(v, 'model_dump') else v
                for k, v in self.relations.items()
            },
            # spy_networks: 保留全量（A4 需要）
            "spy_networks": {
                k: v.model_dump() if hasattr(v, 'model_dump') else v
                for k, v in self.spy_networks.items()
            },
            # siege_states: 保留全量（A2 需要战斗上下文）
            "siege_states": {
                k: v.model_dump() if hasattr(v, 'model_dump') else v
                for k, v in self.siege_states.items()
            },
            # recent_events: 只保留最近 30 条（A8 需要）
            "recent_events": self.events_log[-30:] if self.events_log else [],
            # coalitions: 保留（A6 需要）
            "coalitions": self.coalitions,
            # vassal_relations: 保留（A6 需要）
            "vassal_relations": self.vassal_relations,
        }

    def get_intel_for_player(self, player_faction_id: str) -> dict[str, dict]:
        """
        获取玩家对各个势力的情报掩码状态。
        返回 {target_faction_id: {fields_visible: bool, intel_age: int, ...}}
        
        规则：
        - 己方势力：完全可见
        - 有细作网络且渗透度 >= 10：可见（渗透度越高数据越准确）
        - 已灭亡势力：完全可见（历史公开信息）
        - 游戏初期（前5回合）：对相邻势力给予基础可见性（天下皆知，无需谍报）
        - 否则：隐藏敏感数据
        """
        intel_map: dict[str, dict] = {}
        
        # 2026-07-15 修复: 游戏初期基础可见性
        # 前5回合内，与玩家接壤的势力（共享边界或距离较近）给予基础情报
        early_game_bonus = self.current_round <= 5
        adjacent_factions = set()
        if early_game_bonus:
            player_tiles = set()
            for tile in self.tiles.values():
                if tile.faction_id == player_faction_id:
                    player_tiles.add(tile.tile_id)
            for tile in self.tiles.values():
                if tile.faction_id and tile.faction_id != player_faction_id:
                    # 检查是否与玩家地块相邻
                    for neighbor_id in tile.neighbors:
                        if neighbor_id in player_tiles:
                            adjacent_factions.add(tile.faction_id)
                            break

        for fid, faction in self.factions.items():
            if fid == player_faction_id:
                intel_map[fid] = {"visible": True, "source": "self"}
                continue
            if not faction.is_alive:
                intel_map[fid] = {"visible": True, "source": "defunct"}
                continue

            # 游戏初期接壤势力基础可见
            if early_game_bonus and fid in adjacent_factions:
                intel_map[fid] = {
                    "visible": True,
                    "source": "early_game_adjacent",
                    "intel_age": 0,
                    "infiltration": 0,
                }
                continue

            # 检查是否有细作网络
            spy_key = f"{player_faction_id}|{fid}"
            network = self.spy_networks.get(spy_key)
            
            # 检查最近一次成功刺探的情报记录
            latest_intel = None
            for intel in reversed(self.spy_intel):
                if (intel.get("owner_faction") == player_faction_id 
                    and intel.get("target_faction") == fid
                    and intel.get("action") == "intel"
                    and intel.get("success")):
                    latest_intel = intel
                    break

            # 情报有效期：6回合
            intel_valid = False
            intel_age = 999
            if latest_intel:
                intel_age = self.current_round - latest_intel.get("round", 0)
                if intel_age <= 6:
                    intel_valid = True

            # 细作网络渗透度 >= 10 也能提供基本情报
            spy_visible = network and network.infiltration >= 10 and not network.discovered

            visible = intel_valid or spy_visible
            intel_map[fid] = {
                "visible": visible,
                "source": "intel" if intel_valid else ("spy_network" if spy_visible else "none"),
                "intel_age": intel_age if latest_intel else None,
                "infiltration": network.infiltration if network else 0,
            }

        return intel_map

    def mask_factions_for_player(self, player_faction_id: str) -> dict:
        """
        返回脱敏后的势力数据字典，用于 API 返回给前端。
        只对活着的非己方势力做脱敏，己方/已灭亡势力完全可见。
        """
        intel_map = self.get_intel_for_player(player_faction_id)
        masked = {}

        for fid, faction in self.factions.items():
            fd = faction.model_dump()
            info = intel_map.get(fid, {"visible": False})

            if info.get("visible"):
                # 完全可见：己方、已灭亡、有情报的势力
                fd["_intel_visible"] = True
                fd["_intel_source"] = info.get("source", "unknown")
                fd["_intel_age"] = info.get("intel_age")
                fd["_infiltration"] = info.get("infiltration", 0)
            else:
                # 脱敏：隐藏敏感字段
                fd["_intel_visible"] = False
                fd["_intel_source"] = "none"
                fd["_infiltration"] = info.get("infiltration", 0)
                # 只保留公开信息
                fd["treasury"] = -1       # -1 表示未知
                fd["grain"] = -1
                fd["arms"] = -1
                fd["horses"] = -1
                fd["total_troops"] = -1
                fd["total_population"] = -1
                fd["population"] = -1
                fd["troops"] = -1
                fd["court_stability"] = -1
                fd["realm_stability"] = -1
                fd["development_level"] = -1
                fd["tile_count"] = -1

            masked[fid] = fd

        return masked
