"""
建筑配置常量（零依赖模块）· 元末逐鹿 4.0

从 building_system.py 抽离 BUILDING_CONFIG，消除 policy_system → building_system 延迟导入。
本模块不导入任何 core 模块，可被任意模块安全引用。
"""

from __future__ import annotations
from server.models.world_state import BuildingType


BUILDING_CONFIG = {
    BuildingType.FARMLAND: {
        "name": "农田",
        "build_cost": 300,
        "build_time": 1,
        "upkeep": 0,
        "max_level": 5,
        "effects": {
            "grain_per_level": 80,
            "spring_bonus": 0.2,
            "autumn_bonus": 0.3,
            "winter_penalty": 0.4,
        },
        "description": "耕种田地，每级产粮80石/回合",
        "requires": [],
    },
    BuildingType.WORKSHOP: {
        "name": "工坊",
        "build_cost": 500,
        "build_time": 2,
        "upkeep": 20,
        "max_level": 4,
        "effects": {
            "treasury_per_level": 60,
            "development_per_level": 1,
        },
        "description": "百工坊市，每级产银60两/回合",
        "requires": [],
    },
    BuildingType.BEACON: {
        "name": "烽燧",
        "build_cost": 200,
        "build_time": 1,
        "upkeep": 5,
        "max_level": 3,
        "effects": {
            "vision_range_per_level": 2,
            "early_warning_chance": 0.3,
            "bandit_resist_per_level": 0.15,
        },
        "description": "烽火传讯，每级视野+2",
        "requires": [],
    },
    BuildingType.DOCK: {
        "name": "码头",
        "build_cost": 400,
        "build_time": 2,
        "upkeep": 15,
        "max_level": 3,
        "effects": {
            "trade_bonus_per_level": 0.25,
            "naval_capacity": 1,
        },
        "description": "沿水码头，通商贸易，水军可用",
        "requires": [],
    },
    BuildingType.BARRACKS: {
        "name": "征兵营",
        "build_cost": 350,
        "build_time": 2,
        "upkeep": 30,
        "max_level": 4,
        "effects": {
            "recruit_per_level": 15,
            "training_morale": 1,
        },
        "description": "练兵之所，每级每回合自动募兵15人",
        "requires": [],
    },
    BuildingType.GRANARY: {
        "name": "粮仓",
        "build_cost": 250,
        "build_time": 2,
        "upkeep": 5,
        "max_level": 5,
        "effects": {
            "capacity_per_level": 500,
            "grain_per_level": 50,
            "spring_penalty": 0.3,
            "autumn_bonus": 0.8,
        },
        "description": "储粮之所，每级储粮+500，产粮+50",
        "requires": [],
    },
    BuildingType.CLINIC: {
        "name": "医馆",
        "build_cost": 200,
        "build_time": 1,
        "upkeep": 10,
        "max_level": 3,
        "effects": {
            "plague_resist_per_level": 0.3,
            "population_growth_per_level": 0.005,
        },
        "description": "悬壶济世，抵抗瘟疫，促进人口",
        "requires": [],
    },
    BuildingType.ARMORY: {
        "name": "军械所",
        "build_cost": 800,
        "build_time": 3,
        "upkeep": 50,
        "max_level": 4,
        "effects": {
            "arms_per_level": 5,
            "winter_penalty": 0.33,
        },
        "description": "锻造军械，每级产兵器5件/回合",
        "requires": [],
    },
    BuildingType.STABLE: {
        "name": "马场",
        "build_cost": 600,
        "build_time": 2,
        "upkeep": 40,
        "max_level": 4,
        "effects": {
            "horses_per_level": 2,
            "spring_summer_bonus": 0.5,
            "winter_penalty": 0.5,
        },
        "description": "养马育驹，每级产战马2匹/回合",
        "requires": [],
    },
    BuildingType.TEMPLE: {
        "name": "宗庙",
        "build_cost": 400,
        "build_time": 2,
        "upkeep": 15,
        "max_level": 3,
        "effects": {
            "morale_per_level": 2,
            "public_order_per_level": 1,
            "ceremony_reputation": 3,
        },
        "description": "敬天法祖，每级民心+2，治安+1",
        "requires": [],
    },
    BuildingType.WALL: {
        "name": "城墙",
        "build_cost": 600,
        "build_time": 3,
        "upkeep": 25,
        "max_level": 5,
        "effects": {
            "fortification_per_level": 1,
            "siege_resist_per_level": 0.1,
            "defense_bonus_per_level": 0.05,
        },
        "description": "坚城壁垒，每级城防+1，抵御围城",
        "requires": [],
    },
}
