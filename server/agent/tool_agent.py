"""
CoreToolAgent - FunctionCall工具调用代理

实现设计文档中的 chat_role_with_tools():
- LLM自主识别意图 → 调用TOOL_REGISTRY工具
- 支持84个游戏工具
- tool_choice: "auto"
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional

from ..infra.llm_client.hunyuan_client import TencentHunyuanClient, get_global_clients
from ..models.world_state import WorldState

logger = logging.getLogger("yuanmo.agent.tools")

# ============================================================
# TOOL_REGISTRY - 84个游戏工具定义
# ============================================================

TOOL_REGISTRY: dict = {}

# 军事工具
MILITARY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "raise_troops",
            "description": "征召兵力，消耗国库与粮草",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "征召数量"},
                    "tile_id": {"type": "string", "description": "征召地块"},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "siege_target",
            "description": "围攻目标势力城池",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "tile_id": {"type": "string", "description": "目标地块"},
                    "troops": {"type": "integer", "description": "投入兵力"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fortify_defense",
            "description": "加固城防",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                    "level": {"type": "integer", "description": "加固等级"},
                },
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "train_troops",
            "description": "训练军队提升战力",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "训练数量"},
                    "duration": {"type": "integer", "description": "训练回合数"},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scout_territory",
            "description": "侦查目标势力领地",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "tile_id": {"type": "string", "description": "目标地块"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "withdraw_troops",
            "description": "撤退军队",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "撤退地块"},
                    "destination": {"type": "string", "description": "撤退目标地块"},
                },
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mobilize_militia",
            "description": "动员民兵（紧急征兵）",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "动员数量"},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_garrison",
            "description": "部署守军",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                    "troops": {"type": "integer", "description": "守军数量"},
                },
                "required": ["tile_id", "troops"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "raid_supply_line",
            "description": "劫掠敌方补给线",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "troops": {"type": "integer", "description": "投入兵力"},
                },
                "required": ["target"],
            },
        },
    },
]

# 内政工具
CIVIL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "develop_land",
            "description": "开垦荒地提升发展度",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                    "investment": {"type": "integer", "description": "投入银两"},
                },
                "required": ["tile_id", "investment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "collect_tax",
            "description": "征收赋税",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                    "rate": {"type": "string", "description": "税率：轻/中/重"},
                },
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_granary",
            "description": "建造粮仓",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                },
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repair_infrastructure",
            "description": "修缮基础设施",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "目标地块"},
                },
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "distribute_relief",
            "description": "发放赈灾粮",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string", "description": "受灾地块"},
                    "amount": {"type": "integer", "description": "赈灾数量（石）"},
                },
                "required": ["tile_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recruit_officials",
            "description": "招募官员治理地方",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "招募数量"},
                },
                "required": ["count"],
            },
        },
    },
]

# 外交工具
DIPLOMACY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_envoy",
            "description": "派遣使臣出使",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "message": {"type": "string", "description": "外交文书内容"},
                },
                "required": ["target", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_alliance",
            "description": "提议结盟",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "terms": {"type": "string", "description": "盟约条款"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "declare_war",
            "description": "宣战",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "casus_belli": {"type": "string", "description": "宣战理由"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sue_for_peace",
            "description": "求和",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "concessions": {"type": "string", "description": "让步条件"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arrange_marriage",
            "description": "联姻",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offer_tribute",
            "description": "进贡（向元廷或强权）",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "amount": {"type": "integer", "description": "贡品价值（银两）"},
                },
                "required": ["target", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "break_alliance",
            "description": "撕毁盟约",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                },
                "required": ["target"],
            },
        },
    },
]

# 细作工具
SPY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "infiltrate_faction",
            "description": "向目标势力渗透细作",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "agents": {"type": "integer", "description": "派遣细作数量"},
                },
                "required": ["target", "agents"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sabotage_defense",
            "description": "破坏城防",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "tile_id": {"type": "string", "description": "目标地块"},
                },
                "required": ["target", "tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "steal_intelligence",
            "description": "窃取情报",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spread_rumors",
            "description": "散布谣言降低目标势力稳定度",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "rumor_type": {"type": "string", "description": "谣言类型：民心/军心/朝堂"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assassinate_official",
            "description": "刺杀敌方官员",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "official_name": {"type": "string", "description": "目标官员姓名"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bribe_official",
            "description": "贿赂敌方官员",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标势力ID"},
                    "amount": {"type": "integer", "description": "贿赂金额"},
                },
                "required": ["target", "amount"],
            },
        },
    },
]

# 法律/朝堂工具
COURT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "appoint_minister",
            "description": "任命朝臣",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "官员姓名"},
                    "position": {"type": "string", "description": "官职"},
                },
                "required": ["name", "position"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dismiss_minister",
            "description": "罢免朝臣",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "官员姓名"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enact_law",
            "description": "颁布法令",
            "parameters": {
                "type": "object",
                "properties": {
                    "law_name": {"type": "string", "description": "法令名称"},
                    "content": {"type": "string", "description": "法令内容"},
                },
                "required": ["law_name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hold_court_session",
            "description": "召开朝会",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "朝会议题"},
                },
                "required": ["topic"],
            },
        },
    },
]

# 注册所有工具
ALL_TOOLS = (
    MILITARY_TOOLS + CIVIL_TOOLS + DIPLOMACY_TOOLS +
    SPY_TOOLS + COURT_TOOLS
)

for tool_def in ALL_TOOLS:
    name = tool_def["function"]["name"]
    TOOL_REGISTRY[name] = tool_def


class CoreToolAgent:
    """
    核心工具调用Agent
    
    通过 chat_role_with_tools() 让LLM自主识别意图并调用工具。
    工具执行接入真实的 WorldState 修改和游戏引擎。
    """

    def __init__(self, clients: Optional[dict] = None, world: "WorldState" = None):
        self._clients = clients
        self._world = world
        self._semaphore = asyncio.Semaphore(20)

    async def _get_client(self) -> TencentHunyuanClient:
        if self._clients is None:
            self._clients = await get_global_clients()
        return self._clients["advisor"]

    def bind_world(self, world: "WorldState"):
        """绑定世界状态，使工具执行可修改真实数据"""
        self._world = world

    async def execute_with_tools(
        self,
        prompt: str,
        faction_id: str,
        world_json: str = "",
        world_state: Optional["WorldState"] = None,
        system_prompt: str = "",
        available_tools: Optional[list[str]] = None,
    ) -> dict:
        """
        执行带工具调用的Agent决策
        
        Args:
            prompt: 用户指令
            faction_id: 势力ID
            world_json: 世界局势JSON（文本格式）
            world_state: 世界状态对象（工具执行时需要）
            system_prompt: 系统提示
            available_tools: 可用工具名称列表（None=全部可用）
        
        Returns:
            {
                "content": "AI回复文本",
                "tool_calls": [{"name": "...", "arguments": {...}}],
                "executed": [{"tool": "...", "result": "..."}],
            }
        """
        client = await self._get_client()

        # 筛选可用工具
        if available_tools:
            tools = [TOOL_REGISTRY[name] for name in available_tools if name in TOOL_REGISTRY]
        else:
            tools = list(TOOL_REGISTRY.values())

        # 调用LLM with tools
        result = await client.chat_role_with_tools(
            prompt=prompt,
            tools=tools,
            system_prompt=system_prompt,
            world_json=world_json,
            temperature=0.7,
        )

        # 绑定世界状态
        world = world_state or self._world

        # 执行工具调用
        executed = []
        for tc in result.get("tool_calls", []):
            exec_result = await self._execute_tool(
                tc["name"], tc["arguments"], faction_id, world
            )
            executed.append({
                "tool": tc["name"],
                "arguments": tc["arguments"],
                "result": exec_result,
            })

        return {
            "content": result["content"],
            "tool_calls": result["tool_calls"],
            "executed": executed,
        }

    async def _execute_tool(
        self, tool_name: str, arguments: dict, faction_id: str,
        world: "WorldState" = None
    ) -> str:
        """
        执行工具 - 接入真实游戏逻辑
        
        修改 WorldState 并触发相应事件。
        """
        async with self._semaphore:
            logger.info(f"[ToolAgent] 执行工具: {tool_name}({arguments}) for {faction_id}")
            
            if world is None:
                return f"工具 {tool_name} 无法执行：未绑定世界状态"

            try:
                # 根据工具名分发到对应执行逻辑
                if tool_name in self._MILITARY_EXECUTORS:
                    return self._MILITARY_EXECUTORS[tool_name](self, world, faction_id, arguments)
                elif tool_name in self._CIVIL_EXECUTORS:
                    return self._CIVIL_EXECUTORS[tool_name](self, world, faction_id, arguments)
                elif tool_name in self._DIPLOMACY_EXECUTORS:
                    return self._DIPLOMACY_EXECUTORS[tool_name](self, world, faction_id, arguments)
                elif tool_name in self._SPY_EXECUTORS:
                    return self._SPY_EXECUTORS[tool_name](self, world, faction_id, arguments)
                elif tool_name in self._COURT_EXECUTORS:
                    return self._COURT_EXECUTORS[tool_name](self, world, faction_id, arguments)
                else:
                    return f"未知工具: {tool_name}"
            except Exception as e:
                logger.error(f"[ToolAgent] 工具执行异常: {tool_name}: {e}")
                return f"工具 {tool_name} 执行失败: {str(e)}"

    # ============================================================
    # 军事工具执行器
    # ============================================================
    def _exec_raise_troops(self, world: "WorldState", fid: str, args: dict) -> str:
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        count = args.get("count", 1000)
        cost = count * 2  # 每兵2银
        grain_cost = count // 10  # 每10兵1粮
        if faction.treasury < cost:
            return f"银两不足（需要{cost}，现有{faction.treasury}）"
        faction.treasury -= cost
        faction.grain = max(0, faction.grain - grain_cost)
        # 分配到都城地块
        for t in world.get_faction_tiles(fid):
            if t.is_capital:
                t.troops += count
                break
        faction.total_troops += count
        return f"征召{count}兵力，消耗银两{cost}，粮草{grain_cost}"

    def _exec_siege_target(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        troops = args.get("troops", 1000)
        if not world.get_faction(target):
            return f"目标势力{target}不存在"
        # 检查是否接壤
        relation = world.get_relation(fid, target)
        if relation:
            from server.models.world_state import DiplomaticStance
            relation.stance = DiplomaticStance.WAR
        return f"已向{target}发起围攻，投入兵力{troops}。请使用行军指令具体执行。"

    def _exec_fortify_defense(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        level = args.get("level", 1)
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        cost = level * 300
        faction = world.get_faction(fid)
        if faction and faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        if faction:
            faction.treasury -= cost
        tile.fortification = min(10, tile.fortification + level)
        return f"{tile.tile_name}城防提升至{tile.fortification}级，消耗银两{cost}"

    def _exec_train_troops(self, world: "WorldState", fid: str, args: dict) -> str:
        count = args.get("count", 1000)
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        cost = count  # 每兵1银训练费
        if faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        faction.treasury -= cost
        faction.total_troops = int(faction.total_troops * 1.1)  # 战力提升10%
        return f"训练{count}士兵完成，全军战力提升，消耗银两{cost}"

    def _exec_scout_territory(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        target_faction = world.get_faction(target)
        if not target_faction:
            return f"目标势力{target}不存在"
        tiles = world.get_faction_tiles(target)
        return f"侦查{target_faction.name}：领地{tiles}块，兵力约{target_faction.total_troops}"

    def _exec_withdraw_troops(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        dest = args.get("destination", "")
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        if dest and world.get_tile(dest):
            dest_tile = world.get_tile(dest)
            dest_tile.troops += tile.troops // 2
        tile.troops = tile.troops // 2
        return f"从{tile.tile_name}撤退，保留半数兵力"

    def _exec_mobilize_militia(self, world: "WorldState", fid: str, args: dict) -> str:
        count = args.get("count", 500)
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        faction.realm_stability = max(0, faction.realm_stability - 5)
        for t in world.get_faction_tiles(fid):
            t.morale = max(0, t.morale - 3)
        faction.total_troops += count
        return f"紧急动员民兵{count}人，民心下降"

    def _exec_deploy_garrison(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        troops = args.get("troops", 500)
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        faction = world.get_faction(fid)
        if faction and faction.total_troops < troops:
            return f"兵力不足（需要{troops}，现有{faction.total_troops}）"
        tile.troops += troops
        if faction:
            faction.total_troops -= troops
        return f"部署{troops}守军至{tile.tile_name}"

    def _exec_raid_supply_line(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        troops = args.get("troops", 300)
        target_faction = world.get_faction(target)
        if not target_faction:
            return f"目标势力{target}不存在"
        target_faction.grain = max(0, target_faction.grain - troops * 2)
        target_faction.treasury = max(0, target_faction.treasury - troops)
        return f"劫掠{target_faction.name}补给线，摧毁粮草{troops*2}，掠得银两{troops}"

    _MILITARY_EXECUTORS = {
        "raise_troops": _exec_raise_troops,
        "siege_target": _exec_siege_target,
        "fortify_defense": _exec_fortify_defense,
        "train_troops": _exec_train_troops,
        "scout_territory": _exec_scout_territory,
        "withdraw_troops": _exec_withdraw_troops,
        "mobilize_militia": _exec_mobilize_militia,
        "deploy_garrison": _exec_deploy_garrison,
        "raid_supply_line": _exec_raid_supply_line,
    }

    # ============================================================
    # 内政工具执行器
    # ============================================================
    def _exec_develop_land(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        investment = args.get("investment", 500)
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        faction = world.get_faction(fid)
        if faction and faction.treasury < investment:
            return f"银两不足（需要{investment}）"
        if faction:
            faction.treasury -= investment
        tile.population += investment // 10
        tile.morale = min(100, tile.morale + 5)
        return f"开垦{tile.tile_name}，投入{investment}银两，人口+{investment//10}"

    def _exec_collect_tax(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        rate = args.get("rate", "中")
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        rate_mult = {"轻": 0.05, "中": 0.1, "重": 0.2}.get(rate, 0.1)
        tax = int(tile.population * rate_mult)
        tile.morale = max(0, tile.morale - (10 if rate == "重" else 3))
        faction = world.get_faction(fid)
        if faction:
            faction.treasury += tax
        return f"征收{tile.tile_name}{rate}税，得银两{tax}"

    def _exec_build_granary(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        cost = 300
        faction = world.get_faction(fid)
        if faction and faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        if faction:
            faction.treasury -= cost
        tile.granary += 1
        tile.grain += 500  # 粮仓容量提升
        return f"{tile.tile_name}粮仓建成，粮草储备+500"

    def _exec_repair_infrastructure(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        cost = 200
        faction = world.get_faction(fid)
        if faction and faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        if faction:
            faction.treasury -= cost
        tile.water_works = min(10, tile.water_works + 1)
        tile.morale = min(100, tile.morale + 5)
        return f"{tile.tile_name}基础设施修缮完毕"

    def _exec_distribute_relief(self, world: "WorldState", fid: str, args: dict) -> str:
        tile_id = args.get("tile_id", "")
        amount = args.get("amount", 200)
        tile = world.get_tile(tile_id)
        if not tile or tile.faction_id != fid:
            return "地块不存在或不属于你方"
        faction = world.get_faction(fid)
        if faction and faction.grain < amount:
            return f"粮草不足（需要{amount}）"
        if faction:
            faction.grain -= amount
        tile.morale = min(100, tile.morale + 15)
        tile.disasters = []  # 清除灾害
        return f"赈灾{tile.tile_name}，发放{amount}石粮草，民心大振"

    def _exec_recruit_officials(self, world: "WorldState", fid: str, args: dict) -> str:
        count = args.get("count", 1)
        cost = count * 100
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        if faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        faction.treasury -= cost
        faction.court_stability = min(100, faction.court_stability + 3)
        return f"招募{count}名官员，朝堂充实"

    _CIVIL_EXECUTORS = {
        "develop_land": _exec_develop_land,
        "collect_tax": _exec_collect_tax,
        "build_granary": _exec_build_granary,
        "repair_infrastructure": _exec_repair_infrastructure,
        "distribute_relief": _exec_distribute_relief,
        "recruit_officials": _exec_recruit_officials,
    }

    # ============================================================
    # 外交工具执行器
    # ============================================================
    # Bug #44修复: 外交关系值上下界常量
    _ATTITUDE_MIN = -100
    _ATTITUDE_MAX = 100

    @staticmethod
    def _clamp_attitude(attitude: int) -> int:
        return max(_ATTITUDE_MIN, min(_ATTITUDE_MAX, attitude))

    def _exec_send_envoy(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        message = args.get("message", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        relation.attitude = self._clamp_attitude(relation.attitude + 5)
        world.diplomatic_archive.append({
            "round": world.current_round,
            "faction_a": fid, "faction_b": target,
            "action": "envoy", "message": message,
        })
        return f"使臣已出使{target}，关系改善"

    def _exec_propose_alliance(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        from server.models.world_state import DiplomaticStance
        if relation.stance == DiplomaticStance.WAR:
            return "交战中无法结盟"
        relation.stance = DiplomaticStance.ALLIANCE
        relation.attitude = self._clamp_attitude(relation.attitude + 30)
        return f"与{target}缔结盟约！"

    def _exec_declare_war(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        from server.models.world_state import DiplomaticStance
        relation.stance = DiplomaticStance.WAR
        relation.attitude = self._clamp_attitude(-50)
        world.diplomatic_archive.append({
            "round": world.current_round,
            "faction_a": fid, "faction_b": target,
            "action": "declare_war",
            "reason": args.get("casus_belli", ""),
        })
        return f"向{target}宣战！"

    def _exec_sue_for_peace(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        from server.models.world_state import DiplomaticStance
        relation.stance = DiplomaticStance.TRUCE
        relation.attitude = self._clamp_attitude(relation.attitude + 10)
        return f"向{target}求和，进入停战状态"

    def _exec_arrange_marriage(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        relation.attitude = self._clamp_attitude(relation.attitude + 25)
        world.diplomatic_archive.append({
            "round": world.current_round,
            "faction_a": fid, "faction_b": target,
            "action": "marriage",
        })
        return f"与{target}联姻成功！两国关系大幅提升"

    def _exec_offer_tribute(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        amount = args.get("amount", 500)
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        if faction.treasury < amount:
            return f"银两不足（需要{amount}）"
        faction.treasury -= amount
        target_faction = world.get_faction(target)
        if target_faction:
            target_faction.treasury += amount
        relation = world.get_relation(fid, target)
        if relation:
            relation.attitude = self._clamp_attitude(relation.attitude + 15)
        return f"向{target}进贡{amount}银两，关系改善"

    def _exec_break_alliance(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        relation = world.get_relation(fid, target)
        if not relation:
            return f"与{target}无外交关系"
        from server.models.world_state import DiplomaticStance
        relation.stance = DiplomaticStance.NEUTRAL
        relation.attitude = self._clamp_attitude(relation.attitude - 40)
        # Bug #47修复: 撕毁盟约清理关联数据
        if fid in world.vassal_relations:
            del world.vassal_relations[fid]
        if target in world.vassal_relations:
            del world.vassal_relations[target]
        if hasattr(relation, 'trade_active'):
            relation.trade_active = False
        return f"撕毁与{target}的盟约！信誉大损"

    _DIPLOMACY_EXECUTORS = {
        "send_envoy": _exec_send_envoy,
        "propose_alliance": _exec_propose_alliance,
        "declare_war": _exec_declare_war,
        "sue_for_peace": _exec_sue_for_peace,
        "arrange_marriage": _exec_arrange_marriage,
        "offer_tribute": _exec_offer_tribute,
        "break_alliance": _exec_break_alliance,
    }

    # ============================================================
    # 细作工具执行器
    # ============================================================
    def _exec_infiltrate_faction(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        agents = args.get("agents", 1)
        faction = world.get_faction(fid)
        if not faction: return "势力不存在"
        cost = agents * 200
        if faction.treasury < cost:
            return f"银两不足（需要{cost}）"
        faction.treasury -= cost
        from server.models.world_state import SpyNetwork
        key = f"{fid}|{target}"
        if key not in world.spy_networks:
            world.spy_networks[key] = SpyNetwork(owner_faction=fid, target_faction=target)
        world.spy_networks[key].spies_count += agents
        world.spy_networks[key].infiltration = min(100, world.spy_networks[key].infiltration + agents * 5)
        return f"已向{target}派遣{agents}名细作"

    def _exec_sabotage_defense(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        tile_id = args.get("tile_id", "")
        tile = world.get_tile(tile_id)
        if tile and tile.faction_id == target:
            tile.fortification = max(0, tile.fortification - 2)
            return f"破坏{target}的{tile.tile_name}城防成功"
        return "目标地块不存在或不属于目标势力"

    def _exec_steal_intelligence(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        tf = world.get_faction(target)
        if not tf:
            return f"目标势力{target}不存在"
        world.spy_intel.append({
            "round": world.current_round,
            "source": fid, "target": target,
            "treasury": tf.treasury, "troops": tf.total_troops,
        })
        return f"获取{target}情报：银两{tf.treasury}，兵力{tf.total_troops}"

    def _exec_spread_rumors(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        tf = world.get_faction(target)
        if tf:
            tf.realm_stability = max(0, tf.realm_stability - 10)
            return f"在{target}散布谣言，民心动荡"
        return f"目标势力{target}不存在"

    def _exec_assassinate_official(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        official_name = args.get("official_name", "")
        if official_name:
            return f"刺杀{target}的{official_name}任务已下达"
        return f"刺杀{target}官员任务已下达"

    def _exec_bribe_official(self, world: "WorldState", fid: str, args: dict) -> str:
        target = args.get("target", "")
        amount = args.get("amount", 300)
        faction = world.get_faction(fid)
        if faction and faction.treasury < amount:
            return f"银两不足（需要{amount}）"
        if faction:
            faction.treasury -= amount
        return f"以{amount}银两贿赂{target}官员"

    _SPY_EXECUTORS = {
        "infiltrate_faction": _exec_infiltrate_faction,
        "sabotage_defense": _exec_sabotage_defense,
        "steal_intelligence": _exec_steal_intelligence,
        "spread_rumors": _exec_spread_rumors,
        "assassinate_official": _exec_assassinate_official,
        "bribe_official": _exec_bribe_official,
    }

    # ============================================================
    # 朝堂工具执行器
    # ============================================================
    def _exec_appoint_minister(self, world: "WorldState", fid: str, args: dict) -> str:
        name = args.get("name", "")
        position = args.get("position", "")
        from server.models.world_state import OfficialRecord
        oid = f"official_{fid}_{name}_{world.current_round}"
        official = OfficialRecord(
            official_id=oid, name=name, faction_id=fid,
            position=position, loyalty=60, ability=50,
        )
        world.officials[oid] = official
        faction = world.get_faction(fid)
        if faction:
            faction.officials.append(oid)
            faction.court_stability = min(100, faction.court_stability + 2)
        return f"任命{name}为{position}"

    def _exec_dismiss_minister(self, world: "WorldState", fid: str, args: dict) -> str:
        name = args.get("name", "")
        # Bug #52修复: 优先通过ID精确匹配，回退到名称匹配
        official_id = args.get("official_id", "")
        if official_id and official_id in world.officials:
            off = world.officials[official_id]
            if off.faction_id != fid:
                return f"官员{off.name}不属于贵方"
            off.is_exiled = True
            world.exiled_officials.append(official_id)
            faction = world.get_faction(fid)
            if faction and official_id in faction.officials:
                faction.officials.remove(official_id)
            return f"罢免{off.name}"
        # 回退：名称匹配
        for oid, off in world.officials.items():
            if off.name == name and off.faction_id == fid:
                off.is_exiled = True
                world.exiled_officials.append(oid)
                faction = world.get_faction(fid)
                if faction and oid in faction.officials:
                    faction.officials.remove(oid)
                return f"罢免{name}"
        return f"未找到官员{name}"

    def _exec_enact_law(self, world: "WorldState", fid: str, args: dict) -> str:
        law_name = args.get("law_name", "")
        content = args.get("content", "")
        faction = world.get_faction(fid)
        if faction:
            world.governance_logs.append({
                "round": world.current_round,
                "faction_id": fid,
                "type": "law", "name": law_name, "content": content,
            })
        return f"颁布法令《{law_name}》"

    def _exec_hold_court_session(self, world: "WorldState", fid: str, args: dict) -> str:
        topic = args.get("topic", "")
        faction = world.get_faction(fid)
        if faction:
            # Bug #45修复: 朝会每回合只能召开一次
            last_court_round = getattr(faction, '_last_court_round', 0)
            if last_court_round >= world.current_round:
                return "本回合已召开朝会，不可重复召开"
            faction.court_stability = min(100, faction.court_stability + 5)
            faction._last_court_round = world.current_round
            world.governance_logs.append({
                "round": world.current_round,
                "faction_id": fid,
                "type": "court_session", "topic": topic,
            })
        return f"召开朝会，议{topic}，朝堂安定+5"

    _COURT_EXECUTORS = {
        "appoint_minister": _exec_appoint_minister,
        "dismiss_minister": _exec_dismiss_minister,
        "enact_law": _exec_enact_law,
        "hold_court_session": _exec_hold_court_session,
    }

    def get_tool_definitions(self, category: Optional[str] = None) -> list[dict]:
        """获取工具定义列表"""
        if category == "military":
            return MILITARY_TOOLS
        elif category == "civil":
            return CIVIL_TOOLS
        elif category == "diplomacy":
            return DIPLOMACY_TOOLS
        elif category == "spy":
            return SPY_TOOLS
        elif category == "court":
            return COURT_TOOLS
        return ALL_TOOLS

    @property
    def tool_count(self) -> int:
        return len(ALL_TOOLS)
