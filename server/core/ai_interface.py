"""
AI接口引擎 - 统一JSON标准化数据交互接口（3.2 全链路AI智能体）

职责：
1. GameStateSnapshot 构建：将 WorldState 序列化为AI可读的JSON快照
2. AICommandSet 解析与分发：接收AI返回的JSON指令集
3. 双向数据同步：游戏→AI(快照) + AI→游戏(指令)
4. 视野裁剪：只发送玩家可见的地块数据
"""
from __future__ import annotations
import logging
from typing import Optional

from server.models.ai_protocol import (
    GameStateSnapshot, FactionSnapshot, TileSnapshot,
    RelationSnapshot, BattleSnapshot, WarSnapshot,
    AICommandSet, AICommand, CommandType, DelegationDomain,
    AntiCollapseConfig,
)
from server.models.world_state import WorldState, DiplomaticStance

logger = logging.getLogger("yuanmo.ai.interface")


class AIInterface:
    """
    AI接口引擎 - 游戏状态与AI智能体之间的统一数据桥梁
    
    核心功能：
    - build_snapshot(): 构建全量沙盘快照发AI
    - build_faction_snapshot(): 构建单势力视角快照
    - parse_command_set(): 解析AI返回的JSON指令
    - filter_visible_tiles(): 视野裁剪
    """

    def __init__(self, world: WorldState, anti_collapse: Optional[AntiCollapseConfig] = None):
        self.world = world
        self.anti_collapse = anti_collapse or AntiCollapseConfig()

    # ============================================================
    # 快照构建（游戏 → AI）
    # ============================================================

    def build_snapshot(self, player_faction_id: str = "", include_all: bool = False) -> GameStateSnapshot:
        """
        构建全量沙盘快照
        
        Args:
            player_faction_id: 玩家势力ID（用于视野裁剪）
            include_all: 是否包含全部地块（GM模式）
        """
        # 季节修正
        season_mods = {}
        season = self.world.current_season
        if hasattr(season, 'value'):
            season = season.value
        season_mods = {
            "season": season,
            "recruit_bonus": 1.07 if season == "春" else 1.0,
            "food_consumption": 1.4 if season == "冬" else (1.1 if season == "夏" else 1.0),
            "tax_bonus": 1.3 if season == "秋" else 1.0,
            "attack_bonus": 1.1 if season == "秋" else (0.75 if season == "冬" else 1.0),
            "defense_bonus": 1.15 if season == "冬" else 1.0,
        }

        # 势力快照
        factions = {}
        for fid, faction in self.world.factions.items():
            fs = self._build_faction_detail(fid, faction)
            factions[fid] = fs

        # 地块快照
        visible_tiles = self._build_visible_tiles(player_faction_id) if not include_all else self._build_all_tiles()
        all_tiles = self._build_all_tiles()

        # 关系快照
        relations = self._build_relations()

        # 当前征伐
        active_wars = self._build_active_wars()

        # 近期事件
        recent_events = getattr(self.world, 'events_log', [])[-20:] if hasattr(self.world, 'events_log') else []

        # 军团
        legions = []
        all_legions = self.world.__dict__.get("_legions", {})
        for fid, flist in all_legions.items():
            for l in flist:
                legions.append(l.model_dump() if hasattr(l, 'model_dump') else l)

        # 历史锚点
        triggered_anchors = []
        engine = self.world.__dict__.get("_history_anchor_engine")
        if engine:
            triggered_anchors = engine.get_triggered_anchors()

        return GameStateSnapshot(
            current_round=getattr(self.world, 'current_round', 0),
            current_year=getattr(self.world, 'current_year', 1351),
            current_season=season,
            disaster_index=getattr(self.world, 'disaster_index', 0),
            factions=factions,
            player_faction_id=player_faction_id,
            visible_tiles=visible_tiles,
            all_tiles=all_tiles if include_all else visible_tiles,
            relations=relations,
            active_wars=active_wars,
            recent_events=recent_events,
            legions=legions,
            game_mode=getattr(self.world, 'game_mode', 'player_turn') if hasattr(self.world, 'game_mode') else 'player_turn',
            season_modifiers=season_mods,
            triggered_anchors=triggered_anchors,
        )

    def build_faction_snapshot(self, faction_id: str) -> dict:
        """
        构建单势力详细快照（供AI智能体使用）
        
        包含该势力的完整资源、领地、邻国、威胁等数据。
        """
        faction = self.world.factions.get(faction_id)
        if not faction:
            return {}

        tiles = self.world.get_faction_tiles(faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        tile_ids = [t.tile_id for t in tiles]

        # 邻国分析
        neighbors = {}
        for t in tiles:
            for nid in getattr(t, 'neighbors', []):
                n_tile = self.world.tiles.get(nid) if hasattr(self.world, 'tiles') else None
                if n_tile:
                    n_fid = getattr(n_tile, 'faction_id', '')
                    if n_fid and n_fid != faction_id:
                        neighbors[n_fid] = neighbors.get(n_fid, 0) + 1

        # 威胁评估
        threats = []
        for n_fid, border_len in neighbors.items():
            n_faction = self.world.factions.get(n_fid)
            rel = self._get_relation_stance(faction_id, n_fid)
            if n_faction and n_faction.is_alive:
                threat_level = "high" if rel == "war" else ("medium" if border_len >= 3 else "low")
                threats.append({
                    "faction_id": n_fid,
                    "faction_name": n_faction.name,
                    "troops": n_faction.troops,
                    "border_tiles": border_len,
                    "stance": rel,
                    "threat_level": threat_level,
                    "power_ratio": round(faction.troops / max(1, n_faction.troops), 2),
                })

        # 资源分析
        resource_health = {
            "treasury": "healthy" if faction.treasury > 5000 else ("warning" if faction.treasury > 1000 else "critical"),
            "grain": "healthy" if faction.grain > 3000 else ("warning" if faction.grain > 500 else "critical"),
            "troops": "healthy" if faction.troops > 5000 else ("warning" if faction.troops > 1000 else "critical"),
            "population": "healthy" if faction.population > 10000 else "ok",
        }

        return {
            "faction_id": faction_id,
            "faction": self._build_faction_detail(faction_id, faction).model_dump(),
            "tiles": [self._build_tile_detail(t).model_dump() for t in tiles],
            "tile_ids": tile_ids,
            "neighbors": neighbors,
            "threats": threats,
            "resource_health": resource_health,
            "relations": [r.model_dump() for r in self._build_relations() 
                         if r.faction_a == faction_id or r.faction_b == faction_id],
        }

    # ============================================================
    # AI指令解析（AI → 游戏）
    # ============================================================

    def parse_ai_response(self, raw_response: str, faction_id: str, agent_type: str) -> AICommandSet:
        """
        解析AI原始响应为结构化指令集
        
        支持JSON格式和文本格式的自动识别。
        """
        import json as json_lib

        commands = []

        # 尝试JSON解析
        try:
            # Bug #24修复: 使用括号匹配计数提取，正确处理嵌套JSON
            start = raw_response.find("{")
            if start >= 0:
                depth = 0
                end = -1
                for i, ch in enumerate(raw_response[start:], start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                if end > start:
                    json_str = raw_response[start:end + 1]
                    data = json_lib.loads(json_str)

                if "commands" in data:
                    for cmd_data in data["commands"]:
                        cmd = self._parse_single_command(cmd_data, faction_id)
                        if cmd:
                            commands.append(cmd)
                elif "actions" in data:
                    for cmd_data in data["actions"]:
                        cmd = self._parse_single_command(cmd_data, faction_id)
                        if cmd:
                            commands.append(cmd)
                elif "decision" in data:
                    # 单条决策 — 解析为单条指令
                    cmd = self._parse_single_command(data["decision"], faction_id)
                    if cmd:
                        commands.append(cmd)

                return AICommandSet(
                    agent_type=agent_type,
                    faction_id=faction_id,
                    turn=getattr(self.world, 'current_round', 0),
                    decision_summary=data.get("summary", data.get("decision_summary", "")),
                    strategic_analysis=data.get("analysis", data.get("strategic_analysis", "")),
                    commands=commands,
                    risk_assessment=data.get("risk", "medium"),
                )
        except (json_lib.JSONDecodeError, ValueError):
            pass

        # 文本解析回退：提取关键操作关键词
        text_commands = self._parse_text_commands(raw_response, faction_id)
        commands.extend(text_commands)

        return AICommandSet(
            agent_type=agent_type,
            faction_id=faction_id,
            turn=getattr(self.world, 'current_round', 0),
            decision_summary=raw_response[:200] if raw_response else "",
            strategic_analysis="",
            commands=commands,
            risk_assessment="medium",
        )

    def _parse_single_command(self, cmd_data: dict, faction_id: str) -> Optional[AICommand]:
        """解析单条指令数据"""
        cmd_type_str = cmd_data.get("type", cmd_data.get("action", cmd_data.get("command", "")))
        if not cmd_type_str:
            return None

        # 映射命令类型
        type_map = {
            "march": CommandType.MARCH, "进攻": CommandType.MARCH, "行军": CommandType.MARCH,
            "recruit": CommandType.RECRUIT, "征兵": CommandType.RECRUIT, "募兵": CommandType.RECRUIT,
            "build": CommandType.BUILD, "建造": CommandType.BUILD,
            "develop": CommandType.DEVELOP, "开发": CommandType.DEVELOP, "屯田": CommandType.DEVELOP,
            "train": CommandType.TRAIN_TROOPS, "训练": CommandType.TRAIN_TROOPS,
            "fortify": CommandType.FORTIFY, "加固": CommandType.FORTIFY,
            "tax": CommandType.TAX, "征税": CommandType.TAX,
            "relief": CommandType.RELIEF, "赈灾": CommandType.RELIEF,
            "diplomacy": CommandType.DIPLOMACY, "外交": CommandType.DIPLOMACY,
            "spy": CommandType.SPY, "细作": CommandType.SPY,
            "ambush": CommandType.AMBUSH, "伏击": CommandType.AMBUSH,
            "plunder": CommandType.PLUNDER, "劫掠": CommandType.PLUNDER,
            "buy_horses": CommandType.BUY_HORSES, "买马": CommandType.BUY_HORSES,
            "scout": CommandType.SCOUT, "侦查": CommandType.SCOUT,
            "set_policy": CommandType.SET_POLICY, "国策": CommandType.SET_POLICY,
        }

        cmd_type = type_map.get(cmd_type_str, type_map.get(cmd_type_str.lower(), None))
        if cmd_type is None:
            logger.debug(f"无法识别的指令类型: {cmd_type_str}")
            return None

        return AICommand(
            command_id=cmd_data.get("id", f"ai_{faction_id}_{len(cmd_data)}"),
            command_type=cmd_type,
            faction_id=cmd_data.get("faction_id", faction_id),
            params=cmd_data.get("params", cmd_data.get("parameters", {})),
            reason=cmd_data.get("reason", cmd_data.get("why", "")),
            priority=cmd_data.get("priority", 5),
            estimated_cost=cmd_data.get("cost", cmd_data.get("estimated_cost", {})),
        )

    def _parse_text_commands(self, text: str, faction_id: str) -> list[AICommand]:
        """从纯文本中提取指令（回退方案）"""
        commands = []
        text_lower = text.lower()

        import uuid

        # Bug #26修复: 文本回退指令添加更具体的参数模板
        patterns = [
            (["征兵", "募兵", "扩军", "招兵"], CommandType.RECRUIT, {"auto": True, "amount": 500}),
            (["进攻", "出击", "攻打", "征讨"], CommandType.MARCH, {"auto": True, "troops": 500}),
            (["防守", "固守", "坚守", "加固"], CommandType.FORTIFY, {"auto": True, "amount": 200}),
            (["训练", "操练", "练兵"], CommandType.TRAIN_TROOPS, {"auto": True, "amount": 300}),
            (["开垦", "屯田", "垦荒", "农耕"], CommandType.DEVELOP, {"auto": True, "type": "farmland"}),
            (["建造", "修建"], CommandType.BUILD, {"auto": True, "building": "granary"}),
            (["赈灾", "赈济", "放粮"], CommandType.RELIEF, {"auto": True, "amount": 200}),
            (["结盟", "联盟", "联合"], CommandType.DIPLOMACY, {"action": "alliance"}),
            (["宣战", "讨伐"], CommandType.DIPLOMACY, {"action": "war"}),
            (["侦查", "打探"], CommandType.SCOUT, {"auto": True}),
        ]

        for keywords, cmd_type, params in patterns:
            if any(kw in text for kw in keywords):
                commands.append(AICommand(
                    command_id=f"ai_text_{faction_id}_{uuid.uuid4().hex[:8]}",
                    command_type=cmd_type,
                    faction_id=faction_id,
                    params=params,
                    reason=f"文本关键词匹配: {keywords[0]}",
                    priority=3,
                ))

        return commands

    # ============================================================
    # 内部辅助
    # ============================================================

    def _build_faction_detail(self, fid: str, faction) -> FactionSnapshot:
        """构建势力详细快照"""
        at_war_with = []
        allied_with = []
        vassal_of = ""
        vassals = []

        for key, rel in getattr(self.world, 'relations', {}).items():
            a, b = rel.faction_a, rel.faction_b
            if a == fid:
                stance = self._stance_str(rel.stance)
                if stance == "war":
                    at_war_with.append(b)
                elif stance in ("alliance", "vassal"):
                    allied_with.append(b)
                if stance == "vassal":
                    vassal_of = b
            elif b == fid:
                stance = self._stance_str(rel.stance)
                if stance == "war":
                    at_war_with.append(a)
                elif stance in ("alliance", "vassal"):
                    allied_with.append(a)
                if stance == "vassal":
                    vassal_of = a

        if hasattr(self.world, 'vassal_relations'):
            for vk, vr in self.world.vassal_relations.items():
                if vr.get("lord") == fid:
                    vassals.append(vr.get("vassal", ""))
                elif vr.get("vassal") == fid:
                    vassal_of = vr.get("lord", "")

        tiles = self.world.get_faction_tiles(fid) if hasattr(self.world, 'get_faction_tiles') else []
        tile_ids = [t.tile_id for t in tiles]

        return FactionSnapshot(
            faction_id=fid,
            name=getattr(faction, 'name', fid),
            ruler_name=getattr(faction, 'ruler_name', ''),
            is_alive=getattr(faction, 'is_alive', True),
            is_player=getattr(faction, 'is_player', False),
            personality=getattr(faction, 'personality_tags', ["steady"])[0] if hasattr(faction, 'personality_tags') and getattr(faction, 'personality_tags') else "steady",
            treasury=getattr(faction, 'treasury', 0),
            grain=getattr(faction, 'grain', 0),
            arms=getattr(faction, 'arms', 0),
            horses=getattr(faction, 'horses', 0),
            troops=getattr(faction, 'troops', 0),
            population=getattr(faction, 'population', 0),
            reputation=getattr(faction, 'reputation', 50),
            court_stability=getattr(faction, 'court_stability', 50),
            realm_stability=getattr(faction, 'realm_stability', 50),
            capital_tile=getattr(faction, 'capital_tile', ''),
            tile_count=len(tile_ids),
            tile_ids=tile_ids,
            at_war_with=at_war_with,
            allied_with=allied_with,
            vassal_of=vassal_of,
            vassals=vassals,
            active_policies=getattr(faction, 'unlocked_policies', []),
            buffs=getattr(faction, 'buffs', []),
            debuffs=getattr(faction, 'debuffs', []),
        )

    def _build_tile_detail(self, tile) -> TileSnapshot:
        """构建地块快照"""
        return TileSnapshot(
            tile_id=getattr(tile, 'tile_id', ''),
            tile_name=getattr(tile, 'tile_name', ''),
            tile_type=self._tile_type_str(getattr(tile, 'tile_type', 'farmland')),
            owner_faction=getattr(tile, 'faction_id', ''),
            troops=getattr(tile, 'troops', 0),
            development=getattr(tile, 'development_level', 20),
            fortification=getattr(tile, 'fortification', 0),
            population=getattr(tile, 'population', 0),
            buildings=list(getattr(tile, 'buildings', [])),
            active_disaster=str(getattr(tile, 'active_disaster', '')),
            x=getattr(tile, 'x', 0.0) if hasattr(tile, 'x') else 0.0,
            y=getattr(tile, 'y', 0.0) if hasattr(tile, 'y') else 0.0,
            neighbors=list(getattr(tile, 'neighbors', [])),
        )

    def _build_visible_tiles(self, player_faction_id: str) -> list[TileSnapshot]:
        """构建玩家视野内的地块"""
        if not player_faction_id:
            return self._build_all_tiles()

        visible_ids = set()
        # 玩家领地
        tiles = self.world.get_faction_tiles(player_faction_id) if hasattr(self.world, 'get_faction_tiles') else []
        for t in tiles:
            visible_ids.add(t.tile_id)
            # 邻接地块也可见
            for nid in getattr(t, 'neighbors', []):
                visible_ids.add(nid)

        # 盟友领地
        for key, rel in getattr(self.world, 'relations', {}).items():
            if self._stance_str(rel.stance) in ("alliance", "vassal"):
                other = rel.faction_b if rel.faction_a == player_faction_id else rel.faction_a
                at = self.world.get_faction_tiles(other) if hasattr(self.world, 'get_faction_tiles') else []
                for t in at:
                    visible_ids.add(t.tile_id)

        result = []
        for tid in visible_ids:
            tile = self.world.tiles.get(tid) if hasattr(self.world, 'tiles') else None
            if tile:
                result.append(self._build_tile_detail(tile))

        return result

    def _build_all_tiles(self) -> list[TileSnapshot]:
        """构建全部地块"""
        result = []
        for tid, tile in getattr(self.world, 'tiles', {}).items():
            result.append(self._build_tile_detail(tile))
        return result

    def _build_relations(self) -> list[RelationSnapshot]:
        """构建外交关系快照"""
        result = []
        for key, rel in getattr(self.world, 'relations', {}).items():
            result.append(RelationSnapshot(
                faction_a=rel.faction_a,
                faction_b=rel.faction_b,
                stance=self._stance_str(rel.stance),
                trust=getattr(rel, 'trust', 50),
                trade_active=getattr(rel, 'trade_active', False),
                marriage=getattr(rel, 'marriage', False),
            ))
        return result

    def _build_active_wars(self) -> list[WarSnapshot]:
        """构建当前征伐快照"""
        wars = []
        for key, rel in getattr(self.world, 'relations', {}).items():
            if self._stance_str(rel.stance) == "war":
                wars.append(WarSnapshot(
                    war_id=f"war_{rel.faction_a}_{rel.faction_b}",
                    attacker=rel.faction_a,
                    defender=rel.faction_b,
                    started_round=getattr(rel, 'started_round', 0),
                ))
        return wars

    def _get_relation_stance(self, fid_a: str, fid_b: str) -> str:
        """获取两势力关系"""
        for key, rel in getattr(self.world, 'relations', {}).items():
            if (rel.faction_a == fid_a and rel.faction_b == fid_b) or \
               (rel.faction_a == fid_b and rel.faction_b == fid_a):
                return self._stance_str(rel.stance)
        return "neutral"

    @staticmethod
    def _stance_str(stance) -> str:
        """立场转字符串"""
        if hasattr(stance, 'value'):
            return stance.value
        return str(stance)

    @staticmethod
    def _tile_type_str(tt) -> str:
        """地块类型转字符串"""
        if hasattr(tt, 'value'):
            return tt.value
        return str(tt)
