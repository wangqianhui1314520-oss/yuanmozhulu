"""
3.2 历史动态剧情锚点系统
根据玩家沙盘局势改写元末历史走向
支持不同割据、决战、大一统剧情分支
"""
from __future__ import annotations
import random
import uuid
import logging
from typing import Optional
from server.models.world_state import WorldState, FactionState, DiplomaticStance
from server.models.generals import StoryBranch, HistoryAnchor

logger = logging.getLogger("yuanmo.history_anchors")


# ============================================================
# 预设历史锚点
# ============================================================

HISTORY_ANCHORS = [
    # ---- 早期锚点 (1351-1356) ----
    {
        "anchor_id": "anchor_red_turban_rise",
        "title": "红巾再起",
        "description": "天下大乱，红巾军席卷中原。玩家需要在乱世中站稳脚跟。",
        "trigger_year": 1351,
        "conditions": {
            "min_round": 1,
            "player_tiles_min": 3,  # 玩家拥有至少3地块
            "auto_trigger": True,   # 开局自动触发
        },
        "branches": [
            {
                "id": "branch_join_revolt",
                "name": "加入红巾",
                "narrative": "红巾军如野火燎原，天下反元之势已成。你决定高举义旗，汇入这股洪流之中。",
                "effects": {"reputation": 10, "realm_stability": 5},
                "leads_to": ["anchor_poyang"],
            },
            {
                "id": "branch_support_yuan",
                "name": "效力元廷",
                "narrative": "虽天下大乱，但你选择效忠元廷，以朝廷之名平定叛乱。",
                "effects": {"reputation": 5, "court_stability": 10},
                "leads_to": ["anchor_yuan_decline"],
            },
            {
                "id": "branch_stay_neutral",
                "name": "静观其变",
                "narrative": "乱世之中，你选择积蓄力量，暂不表态。",
                "effects": {"treasury": 2000, "grain": 1000},
                "leads_to": ["anchor_three_kingdoms"],
            },
        ],
    },
    {
        "anchor_id": "anchor_poyang",
        "title": "鄱阳湖决战",
        "description": "朱元璋与陈友谅在鄱阳湖展开决定天下归属的大决战。",
        "trigger_year": 1363,
        "conditions": {
            "min_round": 48,  # 约第48回合
            "requires_factions_alive": ["faction_zhuyuanzhang", "faction_chenyouliang"],
        },
        "branches": [
            {
                "id": "branch_zhu_wins",
                "name": "朱元璋获胜",
                "narrative": "鄱阳湖一战，朱元璋以少胜多，陈友谅中箭身亡。西吴势不可挡！",
                "effects": {"faction_chenyouliang_destroyed": True},
                "leads_to": ["anchor_northern_expedition"],
            },
            {
                "id": "branch_chen_wins",
                "name": "陈友谅获胜",
                "narrative": "陈友谅的水师在鄱阳湖取得决定性胜利，朱元璋势力大损。天下格局为之一变！",
                "effects": {"faction_zhuyuanzhang_weakened": True},
                "leads_to": ["anchor_chen_dominance"],
            },
        ],
    },
    {
        "anchor_id": "anchor_chen_dominance",
        "title": "陈友谅霸业",
        "description": "鄱阳湖一役陈友谅大获全胜，朱元璋元气大伤。陈汉势力如日中天，天下格局彻底改写。",
        "trigger_year": 1365,
        "conditions": {
            "min_round": 56,
            "requires_factions_alive": ["faction_chenyouliang"],
            "auto_trigger": False,  # 仅通过鄱阳湖分支链触发
        },
        "branches": [
            {
                "id": "branch_chen_emperor",
                "name": "陈友谅称帝",
                "narrative": "扫平朱元璋后，陈友谅在江州登基称帝，国号大汉。天下震动，群雄俯首！",
                "effects": {"reputation": 15, "court_stability": 10},
                "leads_to": [],
                "is_ending": False,
            },
            {
                "id": "branch_chen_overreach",
                "name": "陈友谅冒进",
                "narrative": "陈友谅急于求成，挥师北上与元廷决战。劳师远征，后防空虚，给了其他势力可乘之机。",
                "effects": {"reputation": -5, "realm_stability": -15, "treasury": -5000, "grain": -3000},
                "leads_to": [],
                "is_ending": False,
            },
        ],
    },
    {
        "anchor_id": "anchor_northern_expedition",
        "title": "北伐中原",
        "description": "南方已定，大军北上驱逐元廷。",
        "trigger_year": 1367,
        "conditions": {
            "min_round": 64,
            "player_controls_south": True,  # 玩家控制淮河以南
            "yuan_alive": True,
        },
        "branches": [
            {
                "id": "branch_unification",
                "name": "北伐成功",
                "narrative": "北伐大军势如破竹，元顺帝仓皇北逃。天下重归一统！",
                "effects": {"endgame_unification": True},
                "leads_to": [],
                "is_ending": True,
                "ending_title": "大一统 · 新朝肇建",
            },
            {
                "id": "branch_yuan_holds",
                "name": "元廷坚守",
                "narrative": "元廷虽衰但未亡，北方仍在蒙古铁骑控制之下。南北对峙格局形成。",
                "effects": {"north_south_divide": True},
                "leads_to": ["anchor_final_showdown"],
            },
        ],
    },
    {
        "anchor_id": "anchor_yuan_decline",
        "title": "元廷衰落",
        "description": "大元帝国风雨飘摇，各地的元廷势力逐渐分崩离析。",
        "trigger_year": 1355,
        "conditions": {
            "min_round": 16,
            "yuan_tiles_lost": 5,  # 元廷失去5个以上地块
        },
        "branches": [
            {
                "id": "branch_coup",
                "name": "元廷内乱",
                "narrative": "元廷内斗加剧，权臣之间互相倾轧，国力进一步削弱。",
                "effects": {"yuan_court_stability": -20},
                "leads_to": ["anchor_northern_expedition"],
            },
            {
                "id": "branch_yuan_revival",
                "name": "元廷中兴",
                "narrative": "贤相力挽狂澜，推行新政，元廷出现中兴迹象！",
                "effects": {"yuan_revival": True},
                "leads_to": [],
                "is_ending": False,
            },
        ],
    },
    {
        "anchor_id": "anchor_three_kingdoms",
        "title": "三国鼎立",
        "description": "天下三分，群雄割据，谁将最终一统？",
        "trigger_year": 1360,
        "conditions": {
            "min_round": 36,
            "three_major_factions": True,  # 至少3个势力存活且实力相当
        },
        "branches": [
            {
                "id": "branch_diplomacy_win",
                "name": "外交统一",
                "narrative": "通过合纵连横，你成功说服其他势力归附。不战而屈人之兵！",
                "effects": {"diplomatic_victory": True},
                "leads_to": [],
                "is_ending": True,
                "ending_title": "外交统一 · 天下归心",
            },
            {
                "id": "branch_military_win",
                "name": "武力统一",
                "narrative": "天下纷争，唯强者可定乾坤。你决意以武力统一天下！",
                "effects": {"total_war_begins": True},
                "leads_to": ["anchor_final_showdown"],
            },
        ],
    },
    {
        "anchor_id": "anchor_final_showdown",
        "title": "天下一决",
        "description": "最后的决战时刻。胜者王侯，败者寇！",
        "trigger_year": 1370,
        "conditions": {
            "min_round": 76,
            "max_alive_factions": 3,  # 最多3个势力存活
        },
        "branches": [
            {
                "id": "branch_ultimate_victory",
                "name": "问鼎天下",
                "narrative": "历经血战，你终于扫平群雄，一统天下！新的王朝由此开启。",
                "effects": {"endgame_unification": True},
                "leads_to": [],
                "is_ending": True,
                "ending_title": "天下一统 · 开国称帝",
            },
            {
                "id": "branch_last_defeat",
                "name": "功败垂成",
                "narrative": "决战功亏一篑，你的势力在最后一战中崩溃。",
                "effects": {"game_over": True},
                "leads_to": [],
                "is_ending": True,
                "ending_title": "功败垂成 · 出师未捷",
            },
        ],
    },
]


class HistoryAnchorEngine:
    """历史剧情锚点引擎"""

    def __init__(self, world: WorldState):
        self.world = world
        self._triggered_anchors: dict[str, HistoryAnchor] = {}
        self._anchor_narratives: list[str] = []

    # ================================================================
    # 锚点检查
    # ================================================================

    def check_all_anchors(self) -> list[dict]:
        """
        每回合检查所有历史锚点是否触发
        
        返回: [{anchor_id, title, branches, ...], ...]
        """
        triggered = []

        for anchor_data in HISTORY_ANCHORS:
            aid = anchor_data["anchor_id"]

            # 跳过已触发的
            if aid in self._triggered_anchors:
                continue

            # 检查触发条件
            if self._check_anchor_conditions(anchor_data):
                anchor = HistoryAnchor(
                    anchor_id=aid,
                    title=anchor_data["title"],
                    description=anchor_data["description"],
                    trigger_year=anchor_data.get("trigger_year", self.world.current_year),
                    conditions=anchor_data.get("conditions", {}),
                    branches=anchor_data.get("branches", []),
                    triggered=True,
                )
                self._triggered_anchors[aid] = anchor
                triggered.append({
                    "anchor_id": aid,
                    "title": anchor.title,
                    "description": anchor.description,
                    "branches": [{"id": b["id"], "name": b["name"]} for b in anchor.branches],
                })

        return triggered

    def _check_anchor_conditions(self, anchor_data: dict) -> bool:
        """检查锚点触发条件"""
        cond = anchor_data.get("conditions", {})

        # 自动触发
        if cond.get("auto_trigger"):
            return True

        # 检查回合数
        min_round = cond.get("min_round", 0)
        if self.world.current_round < min_round:
            return False

        # 检查势力存活
        requires_alive = cond.get("requires_factions_alive", [])
        for fid in requires_alive:
            fac = self.world.get_faction(fid)
            if not fac or not fac.is_alive:
                return False

        # 检查玩家地块数
        player_tiles_min = cond.get("player_tiles_min", 0)
        if player_tiles_min > 0:
            player = self.world.get_player_faction()
            if player:
                player_tiles = len(self.world.get_faction_tiles(player.faction_id))
                if player_tiles < player_tiles_min:
                    return False

        # 检查势力最大存活数
        max_alive = cond.get("max_alive_factions", 99)
        alive_count = len([f for f in self.world.factions.values() if f.is_alive])
        if alive_count > max_alive:
            return False

        # 检查元廷地块丢失（净损失 = 初始地块数 - 当前地块数）
        yuan_tiles_lost = cond.get("yuan_tiles_lost", 0)
        if yuan_tiles_lost > 0:
            yuan = self.world.get_faction("faction_yuan")
            if yuan and yuan.is_alive:
                yuan_current = len(self.world.get_faction_tiles("faction_yuan"))
                # 用初始地块数计算净损失（而非 tile_changes 征服记录数）
                yuan_initial = getattr(self, "_yuan_initial_tiles", None)
                if yuan_initial is None:
                    # 首次计算：从 WorldState 初始快照估算（取所有地块中被元廷占领的）
                    yuan_initial = sum(
                        1 for t in self.world.tiles.values()
                        if getattr(t, "original_faction_id", "") == "faction_yuan"
                    )
                    if yuan_initial == 0:
                        yuan_initial = len(self.world.get_faction_tiles("faction_yuan"))
                    self._yuan_initial_tiles = yuan_initial
                net_lost = yuan_initial - yuan_current
                if net_lost < yuan_tiles_lost:
                    return False

        # 玩家控制南方（地块≥20且首都位于淮河以南）
        if cond.get("player_controls_south"):
            player = self.world.get_player_faction()
            if not player:
                return False
            player_tiles = self.world.get_faction_tiles(player.faction_id)
            if len(player_tiles) < 20:
                return False
            # 检查首都是否在南方（淮河以南，即地图 y 坐标 ≥ 淮河分界线）
            capital_tile = self.world.tiles.get(player.capital_tile_id)
            if capital_tile:
                HUAIHE_Y_DIVIDE = 12  # 淮河大致在 y=12 附近
                if capital_tile.y < HUAIHE_Y_DIVIDE:
                    return False

        # 元廷存活
        if "yuan_alive" in cond:
            yuan = self.world.get_faction("faction_yuan")
            if cond["yuan_alive"] and (not yuan or not yuan.is_alive):
                return False

        # 三国鼎立条件
        if cond.get("three_major_factions"):
            alive_factions = [f for f in self.world.factions.values() if f.is_alive]
            if len(alive_factions) < 3:
                return False
            # 检查实力差距不超过2倍
            powers = [self._calc_power(f) for f in alive_factions]
            if max(powers) > min(powers) * 3:
                return False

        # event_trigger 条件：检查对应的事件是否已触发
        event_trigger = cond.get("event_trigger", "")
        if event_trigger:
            # 在 events_log 中查找对应事件
            triggered = any(
                evt.get("event_type") == event_trigger or evt.get("event_id", "").startswith(event_trigger)
                for evt in (getattr(self.world, "events_log", None) or [])
            )
            if not triggered:
                return False

        return True

    def _calc_power(self, faction: FactionState) -> float:
        """计算势力实力（简化版）"""
        return faction.total_troops + faction.treasury * 0.01 + faction.tile_count * 100

    # ================================================================
    # 分支选择与执行
    # ================================================================

    def choose_branch(self, anchor_id: str, branch_id: str, faction_id: str = "") -> dict:
        """
        玩家选择剧情分支
        
        返回: {success, narrative, effects, ...}
        """
        if anchor_id not in self._triggered_anchors:
            return {"success": False, "message": "该锚点尚未触发"}

        anchor = self._triggered_anchors[anchor_id]
        branch = None
        for b in anchor.branches:
            if b["id"] == branch_id:
                branch = b
                break

        if not branch:
            return {"success": False, "message": f"分支{branch_id}不存在"}

        anchor.chosen_branch = branch_id
        anchor.narrative = branch["narrative"]

        result = {
            "success": True,
            "anchor_title": anchor.title,
            "chosen_branch": branch["name"],
            "narrative": branch["narrative"],
            "effects": branch.get("effects", {}),
            "is_ending": branch.get("is_ending", False),
            "ending_title": branch.get("ending_title", ""),
        }

        # 执行效果
        self._apply_branch_effects(branch.get("effects", {}), faction_id)

        # 记录日志
        self._anchor_narratives.append({
            "round": self.world.current_round,
            "year": self.world.current_year,
            "anchor_id": anchor_id,
            "branch_id": branch_id,
            "narrative": branch["narrative"],
        })

        self.world.events_log.append({
            "event_id": f"anchor_{anchor_id}_{self.world.current_round}",
            "event_type": "story",
            "severity": "critical",
            "round": self.world.current_round,
            "title": f"【历史转折】{anchor.title}",
            "description": branch["narrative"],
            "faction_id": faction_id,
            "effects": branch.get("effects", {}),
        })

        return result

    def _apply_branch_effects(self, effects: dict, faction_id: str):
        """应用分支效果到世界状态"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return

        # 资源变化
        if "reputation" in effects:
            faction.reputation = max(0, min(100, faction.reputation + effects["reputation"]))
        if "realm_stability" in effects:
            faction.realm_stability = max(0, min(100, faction.realm_stability + effects["realm_stability"]))
        if "court_stability" in effects:
            faction.court_stability = max(0, min(100, faction.court_stability + effects["court_stability"]))
        if "treasury" in effects:
            faction.treasury += effects["treasury"]
        if "grain" in effects:
            faction.grain += effects["grain"]

        # 势力灭亡/削弱
        for key, value in effects.items():
            if key.endswith("_destroyed") and value:
                target_fid = key.replace("_destroyed", "")
                target = self.world.get_faction(target_fid)
                if target:
                    target.is_alive = False
                    # 释放所有地块
                    for tile in list(self.world.tiles.values()):
                        if tile.faction_id == target_fid:
                            tile.faction_id = ""
                    self.world.events_log.append({
                        "event_id": f"destroy_{target_fid}_{self.world.current_round}",
                        "event_type": "story",
                        "severity": "critical",
                        "round": self.world.current_round,
                        "title": f"【势力灭亡】{target.name}覆灭",
                        "description": f"在历史洪流中，{target.name}势力彻底覆灭。",
                        "faction_id": faction_id,
                    })
            elif key.endswith("_weakened") and value:
                target_fid = key.replace("_weakened", "")
                target = self.world.get_faction(target_fid)
                if target:
                    target.total_troops = max(0, target.total_troops // 2)
                    target.treasury = max(0, target.treasury // 2)
                    target.grain = max(0, target.grain // 2)

        # 全局标志
        if effects.get("endgame_unification"):
            self.world.game_mode = "victory"
            # 3.3: 通知结局引擎记录叙事结局
            self._notify_ending_engine("anchor_ending", "天下一统", "历史锚点触发：北伐成功统一天下")
        if effects.get("diplomatic_victory"):
            self.world.game_mode = "victory"
            self._notify_ending_engine("anchor_ending", "天下归心", "历史锚点触发：外交合纵统一天下")
        if effects.get("game_over"):
            self.world.game_mode = "game_over"
        if effects.get("total_war_begins"):
            # 所有势力互宣战
            for fid_a in list(self.world.factions.keys()):
                for fid_b in list(self.world.factions.keys()):
                    if fid_a < fid_b:
                        rel = self.world.get_relation(fid_a, fid_b)
                        if rel and rel.stance != DiplomaticStance.WAR:
                            rel.stance = DiplomaticStance.WAR

        # 元廷稳定度调整（锚点④ 元廷内乱分支效果）
        yuan_court = effects.get("yuan_court_stability")
        if yuan_court is not None:
            yuan = self.world.get_faction("faction_yuan")
            if yuan:
                yuan.court_stability = max(0, min(100, yuan.court_stability + yuan_court))
                self.world.events_log.append({
                    "event_id": f"yuan_court_{self.world.current_round}",
                    "event_type": "story",
                    "severity": "major",
                    "round": self.world.current_round,
                    "title": "元廷政局动荡",
                    "description": f"元廷内部稳定度变化 {yuan_court:+d}，当前为 {yuan.court_stability}",
                    "faction_id": "faction_yuan",
                })

        # 南北对峙标志（锚点③ 元廷坚守分支效果）
        if effects.get("north_south_divide"):
            # 设置全局标志：南北对峙
            self.world.game_mode = "north_south_divide"
            self.world.events_log.append({
                "event_id": f"north_south_divide_{self.world.current_round}",
                "event_type": "story",
                "severity": "critical",
                "round": self.world.current_round,
                "title": "南北对峙",
                "description": "元廷虽衰未亡，北方仍在蒙古铁骑控制之下。南北对峙格局正式形成，天下进入持久战阶段。",
                "faction_id": faction_id,
            })
            self._notify_ending_engine("north_south_divide", "南北对峙", "元廷坚守漠北，南北分裂格局形成")

        # 元廷中兴标志
        if effects.get("yuan_revival"):
            yuan = self.world.get_faction("faction_yuan")
            if yuan:
                yuan.realm_stability = min(100, yuan.realm_stability + 15)
                yuan.court_stability = min(100, yuan.court_stability + 15)
                yuan.treasury += 3000
                yuan.grain += 2000

    def get_triggered_anchors(self) -> list[dict]:
        """获取已触发的锚点列表"""
        return [
            {
                "anchor_id": a.anchor_id,
                "title": a.title,
                "description": a.description,
                "triggered": a.triggered,
                "chosen_branch": a.chosen_branch,
                "narrative": a.narrative,
                "branches": [{"id": b["id"], "name": b["name"]} for b in a.branches],
            }
            for a in self._triggered_anchors.values()
        ]

    def get_next_anchors_for_branch(self, anchor_id: str, branch_id: str) -> list[dict]:
        """获取某个分支接下来可能触发的锚点"""
        if anchor_id not in self._triggered_anchors:
            return []

        anchor = self._triggered_anchors[anchor_id]
        branch = None
        for b in anchor.branches:
            if b["id"] == branch_id:
                branch = b
                break

        if not branch:
            return []

        next_ids = branch.get("leads_to", [])
        next_anchors = []
        for aid in next_ids:
            for a_data in HISTORY_ANCHORS:
                if a_data["anchor_id"] == aid:
                    next_anchors.append({
                        "anchor_id": aid,
                        "title": a_data["title"],
                        "description": a_data["description"],
                    })

        return next_anchors

    def get_anchor_narratives(self) -> list[dict]:
        """获取所有历史剧情叙述"""
        return self._anchor_narratives

    def _notify_ending_engine(self, ending_id: str, title: str, description: str):
        """3.3: 通知结局引擎记录历史锚点触发的结局"""
        try:
            from server.core.ending_system import get_ending_engine
            engine = get_ending_engine()
            if engine:
                engine._ending_history.append({
                    "ending_id": ending_id,
                    "tier": "good",
                    "round": self.world.current_round,
                    "year": self.world.current_year,
                    "title": title,
                    "source": "history_anchor",
                })
        except Exception as e:
            logger.warning(f"历史锚点写入日志失败: {e}")
