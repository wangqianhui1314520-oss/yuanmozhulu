"""
高级功能引擎 - 实现游戏中定义但尚未实现的全部功能
包含: 叛军战斗、伏击、劫掠、吞并附庸、双面间谍、假情报、反间、
      质子、围堵、迁都、祭祀、流亡朝廷、官员俸禄、海盗、海战、移民
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional
from server.models.world_state import (
    WorldState, FactionState, TileState, TileType,
    DiplomaticStance, DisasterType, Season,
    SiegeRecord, PrisonerRecord, SiegeState, RebelArmy,
    SpyNetwork, OfficialRecord, RelationState,
)
from server.models.events import BattleEvent, EventType, EventSeverity

logger = logging.getLogger("yuanmo.advanced")


def _parse_tile_coords(tile_id: str) -> tuple[int, int] | None:
    """从 tile_id 提取六边形坐标。支持 \"q,r\" 和 \"tile_q_r\" 两种格式"""
    raw = str(tile_id).replace("tile_", "")
    if "," in raw:
        parts = raw.split(",")
    else:
        parts = raw.split("_")
    if len(parts) >= 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
    return None


# ================================================================
# 1. 叛军系统 - RebelEngine（P0 优先级）
# ================================================================

class RebelEngine:
    """叛军战斗与占地引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def spawn_rebellion(self, faction_id: str, tile_id: str = None,
                        troops: int = None, cause: str = "民变") -> Optional[dict]:
        """生成一支叛军部队"""
        faction = self.world.get_faction(faction_id)
        if not faction or not faction.is_alive:
            return None

        # 选择叛乱地块（该势力控制的地块）
        tiles = self.world.get_faction_tiles(faction_id)
        if not tiles:
            return None

        if tile_id:
            tile = self.world.get_tile(tile_id)
        else:
            # 优先选民心最低的地块
            tile = min(tiles, key=lambda t: t.morale)

        if not tile:
            return None

        if troops is None:
            troops = max(500, int(tile.population * 0.1))

        rebel_id = f"rebel_{faction_id}_{self.world.current_round}_{len(self.world.rebel_armies)}"
        leader_names = ["韩林儿旧部", "张士诚旧部", "红巾余党", "山贼首领",
                        "流民渠帅", "盐贩头领", "寨主", "土豪", "乱军之将",
                        "溃兵头目", "白莲教余孽"]
        leader = random.choice(leader_names)

        rebel = RebelArmy(
            rebel_id=rebel_id,
            tile_id=tile.tile_id,
            troops=troops,
            leader=leader,
            cause=cause,
            spawned_round=self.world.current_round,
        )
        self.world.rebel_armies[rebel_id] = rebel

        # 叛军地块不受原势力控制（叛军占据）
        # 不直接改 tile.faction_id，叛军有自己的 tile_id 标记位置

        self.world.events_log.append({
            "round": self.world.current_round,
            "year": self.world.current_year,
            "month": self.world.current_month,
            "event_type": "rebellion",
            "severity": "major",
            "faction_id": faction_id,
            "tile_id": tile.tile_id,
            "tile_name": tile.tile_name,
            "narrative": f"{tile.tile_name}爆发{leader}领导的{cause}，聚众{troops}人！",
            "rebel_id": rebel_id,
        })

        return {
            "rebel_id": rebel_id,
            "tile_id": tile.tile_id,
            "tile_name": tile.tile_name,
            "troops": troops,
            "leader": leader,
            "cause": cause,
        }

    def rebel_tick(self) -> list[dict]:
        """每回合叛军行为：移动、劫掠、攻击"""
        results = []
        expired = []

        for rebel_id, rebel in list(self.world.rebel_armies.items()):
            # 获取叛军所在地块
            tile = self.world.get_tile(rebel.tile_id)
            if not tile:
                expired.append(rebel_id)
                continue

            # 检查是否该清除（超过20回合自动消散）
            if self.world.current_round - rebel.spawned_round > 20:
                expired.append(rebel_id)
                self.world.events_log.append({
                    "round": self.world.current_round,
                    "event_type": "rebel_dispersed",
                    "narrative": f"{rebel.leader}的叛军历经鏖战，最终溃散。",
                })
                continue

            # 叛军行为：攻击当前地块守军 或 劫掠
            faction = self.world.get_faction(tile.faction_id) if tile.faction_id else None

            if tile.troops > 0:
                # 有守军 → 战斗
                battle_result = self._rebel_battle(rebel, tile)
                results.append(battle_result)

                if battle_result.get("rebel_won"):
                    # 叛军获胜，占据地块
                    old_faction = tile.faction_id
                    tile.faction_id = ""  # 叛军占据，不归属任何势力
                    tile.troops = battle_result.get("rebel_remaining", rebel.troops)
                    tile.morale = max(0, tile.morale - 20)
                    # 劫掠资源
                    looted_grain = min(tile.grain, random.randint(200, 800))
                    tile.grain -= looted_grain
                    if faction:
                        faction.grain = max(0, faction.grain - looted_grain)

                    self.world.events_log.append({
                        "round": self.world.current_round,
                        "event_type": "rebel_capture",
                        "severity": "critical",
                        "tile_id": tile.tile_id,
                        "tile_name": tile.tile_name,
                        "narrative": f"{rebel.leader}的叛军攻占{tile.tile_name}！劫掠粮草{looted_grain}。",
                    })
                elif battle_result.get("rebel_destroyed"):
                    expired.append(rebel_id)
            else:
                # 无守军 → 直接占据并劫掠
                if tile.faction_id:
                    old_faction = tile.faction_id
                    tile.faction_id = ""
                    tile.morale = max(0, tile.morale - 15)
                    looted = min(tile.grain, random.randint(100, 500))
                    tile.grain -= looted
                    if faction:
                        faction.grain = max(0, faction.grain - looted)
                    results.append({
                        "rebel_id": rebel_id,
                        "action": "occupy",
                        "tile_name": tile.tile_name,
                        "looted": looted,
                    })

        # 清除过期叛军
        for rid in expired:
            if rid in self.world.rebel_armies:
                del self.world.rebel_armies[rid]

        return results

    def _rebel_battle(self, rebel: RebelArmy, tile: TileState) -> dict:
        """叛军与守军战斗"""
        # 叛军战力：人数 + 地形加成
        terrain_bonus = {
            TileType.MOUNTAIN: 1.3,
            TileType.PASS: 1.2,
            TileType.CITY: 0.8,  # 叛军攻城劣势
        }.get(tile.tile_type, 1.0)

        rebel_power = rebel.troops * terrain_bonus * (0.7 + random.random() * 0.6)
        defender_power = tile.troops * (1.0 + tile.fortification * 0.1) * (0.6 + random.random() * 0.8)

        # 城防加成
        if tile.tile_type == TileType.CITY:
            defender_power *= 1.3

        rebel_losses = int(rebel.troops * random.uniform(0.15, 0.5))
        defender_losses = int(tile.troops * random.uniform(0.1, 0.45))

        rebel_remaining = rebel.troops - rebel_losses
        defender_remaining = tile.troops - defender_losses

        result = {
            "rebel_id": rebel.rebel_id,
            "tile_name": tile.tile_name,
            "rebel_losses": rebel_losses,
            "defender_losses": defender_losses,
        }

        if rebel_power > defender_power * 1.1:
            # 叛军胜利
            tile.troops = max(0, defender_remaining)
            rebel.troops = max(0, rebel_remaining)
            result["rebel_won"] = True
            result["rebel_remaining"] = max(0, rebel_remaining)
        elif defender_power > rebel_power * 1.1:
            # 守军胜利
            tile.troops = max(0, defender_remaining)
            rebel.troops = max(0, rebel_remaining)
            result["rebel_won"] = False
            if rebel.troops <= 0:
                result["rebel_destroyed"] = True
        else:
            # 僵持
            tile.troops = max(0, defender_remaining)
            rebel.troops = max(0, rebel_remaining)
            result["stalemate"] = True
            if rebel.troops <= 0:
                result["rebel_destroyed"] = True

        return result

    def suppress_rebellion(self, faction_id: str, rebel_id: str, troops: int) -> dict:
        """主动镇压叛军"""
        rebel = self.world.rebel_armies.get(rebel_id)
        if not rebel:
            return {"success": False, "message": "叛军不存在"}

        tile = self.world.get_tile(rebel.tile_id)
        if not tile:
            return {"success": False, "message": "叛军所在地块不存在"}

        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        # 从势力总兵力中扣除
        if faction.total_troops < troops:
            return {"success": False, "message": f"兵力不足（可用{faction.total_troops}）"}

        # 简单战力对比
        atk_power = troops * (0.8 + random.random() * 0.4)
        def_power = rebel.troops * (0.7 + random.random() * 0.6)

        atk_loss = int(troops * random.uniform(0.1, 0.35))
        rebel_loss = int(rebel.troops * random.uniform(0.2, 0.6))

        if atk_power > def_power:
            # 镇压成功
            del self.world.rebel_armies[rebel_id]
            faction.total_troops -= atk_loss
            # 恢复对该地块的控制
            tile.faction_id = faction_id
            tile.troops = troops - atk_loss

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "rebel_suppressed",
                "narrative": f"{faction.name}成功镇压{rebel.leader}叛乱，收复{tile.tile_name}。",
            })

            return {"success": True, "suppressed": True,
                    "losses": atk_loss, "message": f"成功镇压叛军，损失{atk_loss}人"}
        else:
            # 镇压失败
            faction.total_troops -= atk_loss
            rebel.troops -= rebel_loss
            if rebel.troops <= 0:
                del self.world.rebel_armies[rebel_id]
                tile.faction_id = faction_id

            return {"success": False, "suppressed": False,
                    "losses": atk_loss, "message": f"镇压失败，损失{atk_loss}人，叛军残部仍在顽抗"}

    # ================================================================
    # 战时叛乱增强 - 征伐AI联动
    # ================================================================

    def evaluate_war_rebellion_risks(self, faction_id: str,
                                      war_duration: int = 0,
                                      is_frontline: callable = None) -> list[dict]:
        """
        征伐AI联动：评估势力所有地块的战时叛乱风险

        战时叛乱概率大幅提升：
        - 基础概率 +50%（相对于和平时期）
        - 前线地块额外 +30%
        - 每持续1回合战争 +5%（最多+30%）
        - 民心<40的地块概率翻倍
        - 粮草<100的地块概率 +25%

        Returns:
            [{"tile_id": ..., "risk": ..., "triggered": bool, "rebel_result": ...}]
        """
        risks = []
        faction = self.world.get_faction(faction_id)
        if not faction or not faction.is_alive:
            return risks

        # 是否为前线地块的判断函数
        if is_frontline is None:
            border_tiles = set()
            own = {t.tile_id for t in self.world.get_faction_tiles(faction_id)}
            for tid in own:
                tile = self.world.get_tile(tid)
                if not tile:
                    continue
                col, row = tile.col, tile.row
                for dc, dr in [(+1, 0), (+1, -1), (0, -1),
                               (-1, 0), (-1, +1), (0, +1)]:
                    for nid, nt in self.world.tiles.items():
                        if nt.col == col + dc and nt.row == row + dr:
                            if nid not in own and nt.faction_id:
                                border_tiles.add(tid)
                                break

            def is_frontline(tile_id): return tile_id in border_tiles

        for tile in self.world.get_faction_tiles(faction_id):
            # 基础风险计算
            base_risk = 0.05  # 和平时期基础叛乱概率

            # 战时加成
            war_multiplier = 1.5  # 战时基础 +50%

            # 前线加成
            if is_frontline and is_frontline(tile.tile_id):
                war_multiplier += 0.3

            # 战争持续时间加成（每回合+5%，最高+30%）
            duration_bonus = min(0.3, war_duration * 0.05)
            war_multiplier += duration_bonus

            # 民心因子
            morale_factor = 1.0
            if tile.morale < 30:
                morale_factor = 2.0
            elif tile.morale < 50:
                morale_factor = 1.5

            # 粮草因子
            grain_factor = 1.0
            if tile.grain < 100:
                grain_factor = 1.25

            # 综合风险
            risk = base_risk * war_multiplier * morale_factor * grain_factor
            risk = min(risk, 0.6)  # 最高60%概率

            risks.append({
                "tile_id": tile.tile_id,
                "tile_name": tile.tile_name,
                "risk": round(risk, 3),
                "factors": {
                    "war_multiplier": round(war_multiplier, 2),
                    "morale_factor": round(morale_factor, 2),
                    "grain_factor": round(grain_factor, 2),
                    "is_frontline": is_frontline(tile.tile_id) if is_frontline else False,
                },
            })

            # 触发判定
            if random.random() < risk:
                cause = random.choice([
                    f"战火蔓延，{tile.tile_name}民不聊生，揭竿而起",
                    f"败军退至此地，{tile.tile_name}兵民哗变",
                    f"粮饷断绝，{tile.tile_name}守军叛变",
                    f"久战生厌，{tile.tile_name}百姓聚众抗税",
                ])

                troops = max(400, int(tile.population * 0.15))
                rebel_result = self.spawn_rebellion(
                    faction_id=faction_id,
                    tile_id=tile.tile_id,
                    troops=troops,
                    cause=cause,
                )

                if rebel_result:
                    risks[-1]["triggered"] = True
                    risks[-1]["rebel_result"] = rebel_result
                    logger.warning(
                        f"[战时叛乱] {tile.tile_name}({faction.name}) "
                        f"risk={risk:.1%}, cause={cause}"
                    )

        return risks





# ================================================================
# 2. 伏击与劫掠 - AmbushRaidEngine（P1 优先级）
# ================================================================

def _flatten_game_const(raw: dict) -> dict:
    """将嵌套 YAML 配置扁平化为一级字典（合并所有子键）"""
    if not raw:
        return {}
    flat = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            flat.update(val)
        else:
            flat[key] = val
    return flat


class AmbushRaidEngine:
    """伏击、劫掠、边境劫掠引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def attempt_ambush(self, attacker_fid: str, target_fid: str,
                       tile_id: str, ambush_troops: int) -> dict:
        """伏击：在险要地形（山地/关隘）设伏"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return {"success": False, "message": "地块不存在"}

        # 只能在山地、关隘、丘陵设伏
        if tile.tile_type not in (TileType.MOUNTAIN, TileType.PASS):
            return {"success": False, "message": "只能在山地或关隘设伏"}

        # 必须在己方控制或邻接地块
        faction = self.world.get_faction(attacker_fid)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        if faction.total_troops < ambush_troops:
            return {"success": False, "message": f"兵力不足（可用{faction.total_troops}）"}

        # 伏击成功概率：地形 + 兵力对比
        ambush_mult = self.const.get("ambush_damage_mult", 1.8)
        base_success = 0.5
        if tile.tile_type == TileType.PASS:
            base_success = 0.65  # 关隘伏击更有效

        # 查找经过该地块的敌军
        target_tiles = self.world.get_faction_tiles(target_fid)
        nearby = any(
            self._is_adjacent(tile_id, t.tile_id)
            for t in target_tiles
        )

        if not nearby:
            return {"success": False, "message": "附近没有敌军可伏击"}

        if random.random() < base_success:
            # 伏击成功，造成额外伤害
            damage = int(ambush_troops * ambush_mult * random.uniform(0.8, 1.2))
            faction.total_troops -= int(ambush_troops * 0.1)  # 伏击方轻微损失

            target = self.world.get_faction(target_fid)
            if target:
                target.total_troops = max(0, target.total_troops - damage)

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "ambush",
                "severity": "major",
                "attacker": attacker_fid,
                "target": target_fid,
                "tile_name": tile.tile_name,
                "narrative": f"{faction.name}在{tile.tile_name}设伏成功，歼敌{damage}人！",
            })

            return {"success": True, "ambush_successful": True,
                    "damage_dealt": damage, "message": f"伏击成功！歼敌{damage}人"}
        else:
            # 伏击失败
            faction.total_troops -= int(ambush_troops * 0.05)
            return {"success": False, "ambush_successful": False,
                    "message": "伏击失败，敌军有所警觉"}

    def raid_supply_line(self, raider_fid: str, target_fid: str,
                         raid_troops: int = 0) -> dict:
        """劫掠补给线：袭击敌方后勤。
        
        成功率由以下因素决定：
        1. 派遣兵力（基数）：兵力越多，成功率越高
        2. 细作情报：有渗透度 >= 10 或 6回合内成功刺探情报，成功率+15%
        3. 敌方防御兵力：目标总兵力越高，劫掠越困难
        
        被发现后影响双方好感度（attitude）。
        """
        raider = self.world.get_faction(raider_fid)
        target = self.world.get_faction(target_fid)
        if not raider or not target:
            return {"success": False, "message": "势力不存在"}

        # 校验兵力
        if raid_troops < 100:
            return {"success": False, "message": "至少需要100兵力执行劫掠"}
        if raider.total_troops < raid_troops:
            return {"success": False, "message": f"兵力不足（可用{raider.total_troops}）"}

        raid_ratio = self.const.get("raid_supply_steal_ratio", 0.3)

        # ===== 成功率计算 =====
        # 1. 兵力因素：劫掠兵力 vs 敌方总兵力
        troop_ratio = raid_troops / max(target.total_troops, 1)
        base_chance = min(0.70, 0.30 + troop_ratio * 0.40)  # 30%~70% 基于兵力比

        # 2. 细作情报加成
        intel_bonus = 0.0
        intel_source = "无情报"
        spy_key = f"{raider_fid}|{target_fid}"
        network = self.world.spy_networks.get(spy_key)
        if network and network.infiltration >= 10 and not network.discovered:
            intel_bonus = 0.15
            intel_source = f"细作网络(渗透度{network.infiltration})"

        # 检查最近刺探情报
        latest_intel_round = 0
        for intel in reversed(self.world.spy_intel):
            if (intel.get("owner_faction") == raider_fid
                    and intel.get("target_faction") == target_fid
                    and intel.get("action") == "intel"
                    and intel.get("success")):
                latest_intel_round = intel.get("round", 0)
                break
        if latest_intel_round and (self.world.current_round - latest_intel_round) <= 6:
            intel_bonus = max(intel_bonus, 0.15)
            intel_source = f"细作情报(第{latest_intel_round}回合)"

        # 3. 敌方防御修正：目标兵力越多越难
        defense_penalty = min(0.15, target.total_troops / max(raider.total_troops, 1) * 0.10)

        success_chance = min(0.85, max(0.15, base_chance + intel_bonus - defense_penalty))

        # ===== 执行劫掠 =====
        rolled = random.random()
        if rolled < success_chance:
            # 成功
            stolen = int(target.grain * raid_ratio * random.uniform(0.5, 1.0))
            target.grain = max(0, target.grain - stolen)
            raider.grain += stolen

            # 损失少量兵力
            raider_loss = int(raid_troops * random.uniform(0.03, 0.08))
            raider.total_troops = max(0, raider.total_troops - raider_loss)

            # 好感度影响：劫掠成功也会降低双方好感，但相对较小
            relation_penalty = random.randint(5, 12)
            self._modify_relation(raider_fid, target_fid, -relation_penalty)

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "raid",
                "raider": raider_fid,
                "target": target_fid,
                "narrative": (f"{raider.name}派兵{raid_troops}人劫掠{target.name}粮道，"
                              f"夺得粮草{stolen}，损失{raider_loss}人。"),
            })

            return {"success": True, "stolen_grain": stolen,
                    "raider_losses": raider_loss,
                    "success_chance": round(success_chance, 2),
                    "intel_source": intel_source,
                    "relation_change": -relation_penalty,
                    "message": f"劫掠成功！夺得粮草{stolen}（成功率{int(success_chance*100)}%，{intel_source}）"}

        else:
            # 失败：被发现
            raider_loss = int(raid_troops * random.uniform(0.10, 0.25))
            raider.total_troops = max(0, raider.total_troops - raider_loss)
            raider.reputation = max(0, raider.reputation - 3)

            # 好感度影响：被发现后大幅降低双方好感
            relation_penalty = random.randint(15, 30)
            self._modify_relation(raider_fid, target_fid, -relation_penalty)

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "raid_failed",
                "raider": raider_fid,
                "target": target_fid,
                "narrative": (f"{raider.name}劫掠{target.name}粮道失败，"
                              f"斥候暴露，损失{raider_loss}人，双方关系恶化。"),
            })

            return {"success": False,
                    "raider_losses": raider_loss,
                    "discovered": True,
                    "success_chance": round(success_chance, 2),
                    "intel_source": intel_source,
                    "relation_change": -relation_penalty,
                    "message": (f"劫掠失败，斥候暴露！损失{raider_loss}兵力，"
                                f"双方好感度{relation_penalty}（成功率{int(success_chance*100)}%，{intel_source}）")}

    def _modify_relation(self, faction_a: str, faction_b: str, delta: int):
        """修改双方关系值（attitude），确保 RelationState 存在"""
        key = self.world.relation_key(faction_a, faction_b)
        rel = self.world.relations.get(key)
        if not rel:
            from server.models.world_state import RelationState
            rel = RelationState(faction_a=faction_a, faction_b=faction_b)
            self.world.relations[key] = rel
        rel.attitude = max(-100, min(100, rel.attitude + delta))

    def border_raid(self, raider_fid: str, target_fid: str,
                    raid_troops: int) -> dict:
        """边境劫掠：派遣部队劫掠敌方边境"""
        raider = self.world.get_faction(raider_fid)
        target = self.world.get_faction(target_fid)
        if not raider or not target:
            return {"success": False, "message": "势力不存在"}

        if raider.total_troops < raid_troops:
            return {"success": False, "message": f"兵力不足（可用{raider.total_troops}）"}

        raid_damage = self.const.get("border_raid_damage", 0.15)

        # 找到边境地块
        raider_tiles = self.world.get_faction_tiles(raider_fid)
        target_tiles = self.world.get_faction_tiles(target_fid)
        border_found = False
        for rt in raider_tiles:
            for tt in target_tiles:
                if self._is_adjacent(rt.tile_id, tt.tile_id):
                    border_found = True
                    break
            if border_found:
                break

        if not border_found:
            return {"success": False, "message": "两国没有接壤边境"}

        # 劫掠效果
        raider_loss = int(raid_troops * random.uniform(0.05, 0.15))
        target_loss = int(raid_troops * raid_damage * random.uniform(0.8, 1.5))

        raider.total_troops -= raider_loss
        target.total_troops = max(0, target.total_troops - target_loss)

        # 劫掠资源
        stolen_grain = int(target.grain * 0.1 * random.uniform(0.5, 1.0))
        stolen_gold = int(target.treasury * 0.05 * random.uniform(0.5, 1.0))
        target.grain = max(0, target.grain - stolen_grain)
        target.treasury = max(0, target.treasury - stolen_gold)
        raider.grain += stolen_grain
        raider.treasury += stolen_gold

        # 降低被劫掠方边境民心
        for tt in target_tiles[:3]:
            tt.morale = max(0, tt.morale - 10)

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "border_raid",
            "severity": "major",
            "narrative": (f"{raider.name}派兵{raid_troops}人劫掠{target.name}边境，"
                          f"杀敌{target_loss}，掠银{stolen_gold}粮{stolen_grain}。"),
        })

        return {"success": True, "raider_losses": raider_loss,
                "target_losses": target_loss, "stolen_grain": stolen_grain,
                "stolen_gold": stolen_gold, "message": "边境劫掠成功！"}

    def _is_adjacent(self, tile_a: str, tile_b: str) -> bool:
        """判断两个地块是否相邻（简化版六边形邻接）"""
        try:
            coords_a = _parse_tile_coords(tile_a)
            coords_b = _parse_tile_coords(tile_b)
            if coords_a and coords_b:
                qa, ra = coords_a
                qb, rb = coords_b
                # 六边形轴向坐标邻接判断
                directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
                return (qa - qb, ra - rb) in directions
        except (ValueError, IndexError):
            pass
        return False


# ================================================================
# 3. 吞并附庸 - VassalAnnexEngine（P1 优先级）
# ================================================================

class VassalAnnexEngine:
    """附庸吞并与附庸独立战争引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def annex_vassal(self, suzerain_id: str, vassal_id: str) -> dict:
        """吞并附庸"""
        # 检查附庸关系
        if self.world.vassal_relations.get(vassal_id) != suzerain_id:
            return {"success": False, "message": "该势力不是你的附庸"}

        vassal = self.world.get_faction(vassal_id)
        suzerain = self.world.get_faction(suzerain_id)
        if not vassal or not suzerain:
            return {"success": False, "message": "势力不存在"}

        annex_threshold = self.const.get("vassal_annex_threshold", 80)
        annex_cost = self.const.get("vassal_annex_cost", 5000)

        # 计算忠诚度
        key = self.world.relation_key(suzerain_id, vassal_id)
        rel = self.world.relations.get(key)
        loyalty = rel.attitude if rel else 50

        if loyalty < annex_threshold:
            return {"success": False,
                    "message": f"附庸忠诚度不足（需要{annex_threshold}，当前{loyalty}）"}

        if suzerain.treasury < annex_cost:
            return {"success": False,
                    "message": f"银两不足（需要{annex_cost}，当前{suzerain.treasury}）"}

        # 执行吞并
        suzerain.treasury -= annex_cost

        # 转移所有地块
        vassal_tiles = self.world.get_faction_tiles(vassal_id)
        for tile in vassal_tiles:
            tile.faction_id = suzerain_id
            # 同步更新地块上建筑的归属
            for bld in tile.buildings.values():
                bld.faction_id = suzerain_id
                if bld.building_id in self.world.building_registry:
                    self.world.building_registry[bld.building_id].faction_id = suzerain_id

        # 转移资源
        suzerain.treasury += vassal.treasury
        suzerain.grain += vassal.grain
        suzerain.total_troops += vassal.total_troops

        # Bug #46修复: 转移官员并同步双方官员列表
        for oid, off in list(self.world.officials.items()):
            if off.faction_id == vassal_id:
                off.faction_id = suzerain_id
                off.loyalty = max(0, off.loyalty - 20)  # 忠诚度降低
                # 同步suzerain的官员列表
                if oid not in suzerain.officials:
                    suzerain.officials.append(oid)
        # 清空vassal的官员列表
        vassal.officials.clear()

        # 标记附庸为灭亡
        vassal.is_alive = False
        vassal.realm_stability = 0

        # 清除附庸关系
        if vassal_id in self.world.vassal_relations:
            del self.world.vassal_relations[vassal_id]

        # 外交事件
        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "vassal_annexed",
            "severity": "critical",
            "narrative": f"{suzerain.name}正式吞并附庸{vassal.name}，国力大增！",
        })

        # 其他势力反应：好感降低
        for fid, faction in self.world.factions.items():
            if fid not in (suzerain_id, vassal_id) and faction.is_alive:
                rkey = self.world.relation_key(suzerain_id, fid)
                r = self.world.relations.get(rkey)
                if r:
                    r.attitude = max(-100, r.attitude - 15)

        return {"success": True, "message": f"成功吞并{vassal.name}！",
                "tiles_gained": len(vassal_tiles)}

    def check_vassal_independence(self, suzerain_id: str, vassal_id: str) -> Optional[dict]:
        """检查附庸是否发动独立战争"""
        if self.world.vassal_relations.get(vassal_id) != suzerain_id:
            return None

        vassal = self.world.get_faction(vassal_id)
        suzerain = self.world.get_faction(suzerain_id)
        if not vassal or not suzerain:
            return None

        key = self.world.relation_key(suzerain_id, vassal_id)
        rel = self.world.relations.get(key)
        loyalty = rel.attitude if rel else 50

        independence_chance = self.const.get("vassal_independence_war_chance", 0.3)

        # 忠诚度越低，独立概率越高
        if loyalty < 30:
            independence_chance *= 2.0
        elif loyalty < 50:
            independence_chance *= 1.5

        # 附庸实力对比
        power_ratio = (vassal.total_troops + 1) / max(1, suzerain.total_troops)
        if power_ratio > 0.5:
            independence_chance *= 1.5

        if random.random() < independence_chance:
            # 发动独立战争
            self.world.vassal_relations.pop(vassal_id, None)
            if rel:
                rel.stance = DiplomaticStance.WAR
                rel.attitude = -80

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "vassal_independence_war",
                "severity": "critical",
                "narrative": f"{vassal.name}不堪忍受{suzerain.name}的统治，举兵独立！",
            })

            return {"success": True, "independence_declared": True,
                    "vassal": vassal_id, "suzerain": suzerain_id,
                    "message": f"{vassal.name}发动独立战争！"}

        return None


# ================================================================
# 4. 双面间谍 + 假情报 + 反间 - AdvancedSpyEngine（P1 优先级）
# ================================================================

class AdvancedSpyEngine:
    """高级谍报引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def turn_double_agent(self, owner_fid: str, target_fid: str) -> dict:
        """策反双面间谍：将目标势力的细作策反为己用"""
        owner = self.world.get_faction(owner_fid)
        if not owner:
            return {"success": False, "message": "势力不存在"}

        turn_cost = self.const.get("double_agent_turn_cost", 400)
        if owner.treasury < turn_cost:
            return {"success": False, "message": f"银两不足（需要{turn_cost}）"}

        # 查找目标势力部署在我方的细作
        spy_key = f"{target_fid}|{owner_fid}"
        enemy_spy = self.world.spy_networks.get(spy_key)

        if not enemy_spy or enemy_spy.spies_count <= 0:
            return {"success": False, "message": "目标势力未在你处部署细作，或已被清除"}

        success_chance = 0.4 + (enemy_spy.infiltration * 0.03)
        owner.treasury -= turn_cost

        if random.random() < success_chance:
            # 成功策反
            enemy_spy.spies_count -= 1
            enemy_spy.discovered = True

            # 建立双面间谍网络（标记为已策反）
            double_key = f"double_{owner_fid}|{target_fid}"
            if double_key not in self.world.spy_networks:
                self.world.spy_networks[double_key] = SpyNetwork(
                    owner_faction=owner_fid,
                    target_faction=target_fid,
                    infiltration=min(80, enemy_spy.infiltration + 20),
                )
            self.world.spy_networks[double_key].spies_count += 1

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "double_agent_turned",
                "narrative": f"{owner.name}成功策反了{target_fid}的细作，建立双面间谍网络。",
            })

            return {"success": True, "message": "成功策反敌方细作！获得双面间谍",
                    "new_infiltration": self.world.spy_networks[double_key].infiltration}
        else:
            # 策反失败，暴露
            enemy_spy.discovered = True
            return {"success": False, "message": "策反失败，对方细作察觉后自尽"}

    def plant_false_intel(self, planter_fid: str, target_fid: str,
                          intel_type: str, fake_data: dict) -> dict:
        """植入假情报"""
        planter = self.world.get_faction(planter_fid)
        if not planter:
            return {"success": False, "message": "势力不存在"}

        cost = self.const.get("false_intel_plant_cost", 300)
        if planter.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        # 需要渗透度
        spy_key = f"{planter_fid}|{target_fid}"
        spy_net = self.world.spy_networks.get(spy_key)
        if not spy_net or spy_net.infiltration < 30:
            return {"success": False, "message": "渗透度不足（需要30+）"}

        planter.treasury -= cost

        success_chance = 0.5 + (spy_net.infiltration * 0.04)
        if random.random() < success_chance:
            false_entry = {
                "round": self.world.current_round,
                "planter": planter_fid,
                "target": target_fid,
                "type": intel_type,
                "data": fake_data,
                "expires_round": self.world.current_round + 6,
            }
            self.world.planted_false_intel.append(false_entry)

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "false_intel_planted",
                "narrative": f"{planter.name}向{target_fid}植入假情报：{intel_type}。",
            })

            return {"success": True, "message": f"假情报已植入，类型：{intel_type}"}
        else:
            spy_net.discovered = True
            return {"success": False, "message": "假情报植入失败，细作暴露"}

    def counter_spy(self, owner_fid: str, target_fid: str) -> dict:
        """反间行动：清除敌方在我方的细作网络"""
        owner = self.world.get_faction(owner_fid)
        if not owner:
            return {"success": False, "message": "势力不存在"}

        cost = self.const.get("expose_cost", 150)
        if owner.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        spy_key = f"{target_fid}|{owner_fid}"
        enemy_spy = self.world.spy_networks.get(spy_key)

        if not enemy_spy or enemy_spy.spies_count <= 0:
            return {"success": False, "message": "未发现敌方细作"}

        owner.treasury -= cost
        success_chance = 0.5 + (100 - enemy_spy.infiltration) * 0.004

        if random.random() < success_chance:
            removed = enemy_spy.spies_count
            enemy_spy.spies_count = 0
            enemy_spy.discovered = True

            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "counter_spy",
                "narrative": f"{owner.name}反间成功，清除{target_fid}细作{removed}人。",
            })

            return {"success": True, "spies_removed": removed,
                    "message": f"反间成功！清除{removed}名敌方细作"}
        else:
            return {"success": False, "message": "反间行动失败，打草惊蛇"}


# ================================================================
# 5. 质子 + 围堵 - AdvancedDiplomacyEngine（P2 优先级）
# ================================================================

class AdvancedDiplomacyEngine:
    """高级外交引擎：质子、围堵"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def send_hostage(self, sender_fid: str, receiver_fid: str) -> dict:
        """派遣质子"""
        sender = self.world.get_faction(sender_fid)
        receiver = self.world.get_faction(receiver_fid)
        if not sender or not receiver:
            return {"success": False, "message": "势力不存在"}

        # 需要同盟或附庸关系
        key = self.world.relation_key(sender_fid, receiver_fid)
        rel = self.world.relations.get(key)
        if not rel:
            return {"success": False, "message": "无外交关系"}

        if rel.stance not in (DiplomaticStance.ALLIANCE, DiplomaticStance.VASSAL,
                              DiplomaticStance.TRUCE):
            return {"success": False, "message": "需要同盟、附庸或停战关系才能派遣质子"}

        # 检查是否已有质子
        if rel.hostage_sent:
            return {"success": False, "message": "已有质子在此国"}

        hostage_bonus = self.const.get("hostage_relation_bonus", 15)
        rel.attitude = min(100, rel.attitude + hostage_bonus)
        rel.hostage_sent = True

        sender.reputation = min(100, sender.reputation + 3)

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "hostage_sent",
            "narrative": f"{sender.name}派遣质子至{receiver.name}，以示诚意。两国关系+{hostage_bonus}。",
        })

        return {"success": True, "relation_change": hostage_bonus,
                "message": f"质子已派遣至{receiver.name}，关系+{hostage_bonus}"}

    def recall_hostage(self, sender_fid: str, receiver_fid: str) -> dict:
        """召回质子"""
        sender = self.world.get_faction(sender_fid)
        receiver = self.world.get_faction(receiver_fid)
        if not sender or not receiver:
            return {"success": False, "message": "势力不存在"}

        key = self.world.relation_key(sender_fid, receiver_fid)
        rel = self.world.relations.get(key)
        if not rel or not rel.hostage_sent:
            return {"success": False, "message": "无质子可召回"}

        rel.hostage_sent = False
        rel.attitude = max(-100, rel.attitude - 25)
        sender.reputation = max(0, sender.reputation - 5)

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "hostage_recalled",
            "narrative": f"{sender.name}召回质子，{receiver.name}大怒，两国关系急剧恶化。",
        })

        return {"success": True, "message": "质子已召回，关系-25"}

    def apply_encircle_penalty(self) -> dict:
        """围堵机制：检测并应用围堵关系惩罚"""
        changes = []
        living = self.world.get_living_factions()

        for faction in living:
            fid = faction.faction_id
            faction_tiles = self.world.get_faction_tiles(fid)
            if not faction_tiles:
                continue

            # 统计邻接的敌对势力数量
            adjacent_enemies = set()
            for tile in faction_tiles:
                neighbors = self._get_neighbor_tiles(tile.tile_id)
                for nid in neighbors:
                    nt = self.world.get_tile(nid)
                    if nt and nt.faction_id and nt.faction_id != fid:
                        nkey = self.world.relation_key(fid, nt.faction_id)
                        nrel = self.world.relations.get(nkey)
                        if nrel and nrel.stance == DiplomaticStance.WAR:
                            adjacent_enemies.add(nt.faction_id)

            # 如果被2+敌国包围，降低与其他国家的关系
            if len(adjacent_enemies) >= 2:
                penalty = self.const.get("encircle_relation_penalty", -10)
                for other in living:
                    if other.faction_id == fid or other.faction_id in adjacent_enemies:
                        continue
                    # Bug #50修复: 围堵惩罚跳过同盟/附庸/联邦成员
                    rkey = self.world.relation_key(fid, other.faction_id)
                    rel = self.world.relations.get(rkey)
                    if rel and rel.stance not in (DiplomaticStance.ALLIANCE,):
                        # 检查附庸关系
                        is_vassal = (self.world.vassal_relations.get(fid) == other.faction_id or
                                    self.world.vassal_relations.get(other.faction_id) == fid)
                        if not is_vassal:
                            rel.attitude = max(-100, rel.attitude + penalty)
                        changes.append({
                            "faction": fid, "affected": other.faction_id,
                            "penalty": penalty,
                        })

        if changes:
            logger.info(f"围堵机制触发：{len(changes)} 组关系受影响")

        return {"changes": changes, "count": len(changes)}

    def _get_neighbor_tiles(self, tile_id: str) -> list[str]:
        """获取邻接地块ID列表"""
        try:
            coords = _parse_tile_coords(tile_id)
            if not coords:
                return []
            q, r = coords
            directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
            neighbors = []
            for dq, dr in directions:
                nq, nr = q + dq, r + dr
                neighbors.append(f"{nq},{nr}")
            return neighbors
        except (ValueError, IndexError):
            return []


# ================================================================
# 6. 迁都 + 祭祀 + 流亡朝廷 - RoyalAdvancedEngine（P2 优先级）
# ================================================================

class RoyalAdvancedEngine:
    """宗室高级功能引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def move_capital(self, faction_id: str, new_tile_id: str) -> dict:
        """迁都"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        new_tile = self.world.get_tile(new_tile_id)
        if not new_tile:
            return {"success": False, "message": "目标地块不存在"}

        if new_tile.faction_id != faction_id:
            return {"success": False, "message": "目标地块不在你控制下"}

        # 统一使用正式字段 capital_tile，兼容老存档的 capital 动态字段
        old_capital = faction.capital_tile or getattr(faction, 'capital', '')
        if not old_capital:
            # 从 tiles 中查找 is_capital 的城池
            for t in self.world.get_faction_tiles(faction_id):
                if getattr(t, 'is_capital', False):
                    old_capital = t.tile_id
                    break
        if not old_capital:
            # 完全没有旧都：用第一个城池兜底
            faction_tiles = [t for t in self.world.get_faction_tiles(faction_id) if t.tile_type in (TileType.CITY, TileType.CAPITAL)]
            if faction_tiles:
                old_capital = faction_tiles[0].tile_id

        if old_capital == new_tile_id:
            return {"success": False, "message": "新都与旧都相同"}

        cost = self.const.get("move_capital_cost", 10000)
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}，当前{faction.treasury}）"}

        faction.treasury -= cost
        faction.capital_tile = new_tile_id
        # 同步动态字段（兼容老代码）
        faction.capital = new_tile_id

        # 民心短期震荡
        morale_drops = {}
        for tile in self.world.get_faction_tiles(faction_id):
            old_morale = tile.morale
            drop = random.randint(5, 15)
            tile.morale = max(0, tile.morale - drop)
            morale_drops[tile.tile_id] = {"name": tile.tile_name, "old": old_morale, "new": tile.morale, "drop": drop}

        # 旧都：取消首都标识、降城防
        old_tile = self.world.get_tile(old_capital)
        old_tile_name = ""
        if old_tile:
            old_tile_name = old_tile.tile_name or old_capital
            old_tile.is_capital = False
            old_tile.fortification = max(0, old_tile.fortification - 1)

        # 新都：设置首都标识、提升城防
        new_tile.is_capital = True
        new_cap_fort_before = new_tile.fortification
        new_tile.fortification = min(10, new_tile.fortification + 2)
        # 新都治安提升
        new_tile.public_order = min(100, new_tile.public_order + 10)

        # 朝纲震荡
        old_court = faction.court_stability
        faction.court_stability = max(0, min(100, faction.court_stability - random.randint(3, 8)))
        court_change = faction.court_stability - old_court

        # 民心震荡
        old_realm = faction.realm_stability
        faction.realm_stability = max(0, min(100, faction.realm_stability - random.randint(5, 10)))
        realm_change = faction.realm_stability - old_realm

        # 记录迁都历史
        capital_record = {
            "record_id": f"capmove_{self.world.current_round}_{len(self.world.capital_history) + 1}",
            "round": self.world.current_round,
            "faction_id": faction_id,
            "faction_name": faction.name,
            "old_capital": old_capital,
            "old_capital_name": old_tile_name,
            "new_capital": new_tile_id,
            "new_capital_name": new_tile.tile_name,
            "cost": cost,
            "court_stability_change": court_change,
            "realm_stability_change": realm_change,
            "fortification_gained": new_tile.fortification - new_cap_fort_before,
            "year": self.world.current_year,
            "season": str(self.world.current_season.value) if hasattr(self.world.current_season, 'value') else str(self.world.current_season),
        }
        self.world.capital_history.append(capital_record)

        # 事件日志
        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "capital_moved",
            "severity": "major",
            "narrative": f"{faction.name}迁都至{new_tile.tile_name}，耗银{cost}。朝野震动，朝纲{court_change:+d}，民心{realm_change:+d}。",
        })

        return {
            "success": True,
            "old_capital": old_capital,
            "old_capital_name": old_tile_name,
            "new_capital": new_tile_id,
            "new_capital_name": new_tile.tile_name,
            "cost": cost,
            "court_stability": faction.court_stability,
            "court_stability_change": court_change,
            "realm_stability": faction.realm_stability,
            "realm_stability_change": realm_change,
            "fortification": new_tile.fortification,
            "fortification_gained": new_tile.fortification - new_cap_fort_before,
            "public_order": new_tile.public_order,
            "morale_impacts": len(morale_drops),
            "capital_record": capital_record,
            "message": f"已迁都至{new_tile.tile_name}",
        }

    def perform_sacrifice(self, faction_id: str) -> dict:
        """祭祀天地"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        cost = self.const.get("sacrifice_cost", 500)
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}）"}

        faction.treasury -= cost

        # 降低灾厄指数
        disaster_reduction = self.const.get("sacrifice_disaster_reduction", 0.2)
        old_index = self.world.disaster_index
        self.world.disaster_index = max(0, int(self.world.disaster_index * (1 - disaster_reduction)))

        # 民心提升
        for tile in self.world.get_faction_tiles(faction_id):
            tile.morale = min(100, tile.morale + random.randint(3, 8))

        # 声望提升
        faction.reputation = min(100, faction.reputation + 5)

        # 清除一个灾害
        cleared = []
        for tile in self.world.get_faction_tiles(faction_id):
            if tile.disasters:
                cleared.append({"tile": tile.tile_name, "disaster": tile.disasters[0].value})
                tile.disasters.pop(0)
                break

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "sacrifice",
            "narrative": (f"{faction.name}举行盛大祭祀，耗银{cost}。"
                          f"灾厄指数 {old_index} → {self.world.disaster_index}。"
                          + (f"消除{cleared[0]['tile']}的{cleared[0]['disaster']}。" if cleared else "")),
        })

        return {"success": True, "disaster_index_before": old_index,
                "disaster_index_after": self.world.disaster_index,
                "disasters_cleared": cleared,
                "message": "祭祀完成，天地感应，灾厄消退"}

    def activate_exile_court(self, faction_id: str) -> dict:
        """流亡朝廷：势力失去所有领土后的流亡机制"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        tiles = self.world.get_faction_tiles(faction_id)
        if tiles:
            return {"success": False, "message": "势力仍有领土，无需流亡"}

        if not faction.is_alive:
            return {"success": False, "message": "势力已灭亡"}

        maintenance = self.const.get("exile_court_maintenance", 200)

        # 流亡朝廷维持费
        if faction.treasury >= maintenance:
            faction.treasury -= maintenance

            # 尝试寻找流亡地（有同盟关系的地块）
            exiled = False
            for fid, other in self.world.factions.items():
                if fid == faction_id or not other.is_alive:
                    continue
                rkey = self.world.relation_key(faction_id, fid)
                rel = self.world.relations.get(rkey)
                if rel and rel.stance == DiplomaticStance.ALLIANCE:
                    # 在盟国地块中流亡
                    other_tiles = self.world.get_faction_tiles(fid)
                    if other_tiles:
                        target = random.choice(other_tiles)
                        self.world.events_log.append({
                            "round": self.world.current_round,
                            "event_type": "exile_court",
                            "severity": "critical",
                            "narrative": (f"{faction.name}流亡朝廷寄居{other.name}的{target.tile_name}，"
                                          f"每回合耗费{maintenance}银两维持。"),
                        })
                        exiled = True
                        break

            if not exiled:
                # 无处流亡，灭亡
                faction.is_alive = False
                faction.realm_stability = 0
                self.world.events_log.append({
                    "round": self.world.current_round,
                    "event_type": "faction_destroyed",
                    "severity": "critical",
                    "narrative": f"{faction.name}流亡朝廷无依无靠，最终消散于历史长河。",
                })

            return {"success": True, "exiled": exiled,
                    "maintenance_paid": maintenance,
                    "message": "流亡朝廷艰难维持" if exiled else "流亡朝廷最终消亡"}
        else:
            # 无力维持，灭亡
            faction.is_alive = False
            faction.realm_stability = 0
            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "faction_destroyed",
                "severity": "critical",
                "narrative": f"{faction.name}流亡朝廷财尽粮绝，彻底灭亡。",
            })
            return {"success": True, "exiled": False,
                    "message": "流亡朝廷因资财耗尽而灭亡"}


# ================================================================
# 7. 官员俸禄 + 科举 - OfficialAdvancedEngine（P2 优先级）
# ================================================================

class OfficialAdvancedEngine:
    """官员高级管理引擎"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    # 官阶俸禄表（单位：银两/回合）
    OFFICIAL_SALARY_TABLE: dict[str, int] = {
        "丞相": 200, "太尉": 180, "御史大夫": 160,
        "尚书": 150, "将军": 180, "都督": 170,
        "太守": 120, "县令": 80, "谋士": 100,
        "参将": 100, "降将": 80, "使者": 60,
    }

    def pay_salaries(self) -> dict:
        """每回合支付官员俸禄"""
        total_paid = 0
        salary_details = {}

        for faction in self.world.get_living_factions():
            fid = faction.faction_id
            faction_officials = [
                o for o in self.world.officials.values()
                if o.faction_id == fid
            ]
            if not faction_officials:
                continue
            faction_total = 0
            unpaid = []

            for off in faction_officials:
                salary = self.OFFICIAL_SALARY_TABLE.get(off.position, 80)
                if faction.treasury >= salary:
                    faction.treasury -= salary
                    faction_total += salary
                else:
                    unpaid.append(off.name)
                    off.loyalty = max(0, off.loyalty - 5)  # 欠薪降忠诚

            total_paid += faction_total
            salary_details[fid] = {
                "paid": faction_total,
                "officers": len(faction_officials),
                "unpaid": unpaid,
            }

            if unpaid:
                self.world.events_log.append({
                    "round": self.world.current_round,
                    "event_type": "salary_unpaid",
                    "narrative": f"{faction.name}国库空虚，{', '.join(unpaid)}等官员俸禄未发，人心浮动。",
                })

        return {"total_paid": total_paid, "details": salary_details}

    def recruit_officials(self, faction_id: str, count: int = 1) -> dict:
        """科举/选拔官员"""
        faction = self.world.get_faction(faction_id)
        if not faction:
            return {"success": False, "message": "势力不存在"}

        cost = count * 300
        if faction.treasury < cost:
            return {"success": False, "message": f"银两不足（需要{cost}，当前{faction.treasury}）"}

        faction.treasury -= cost

        surnames = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                    "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗"]
        given_names = ["文忠", "廷玉", "伯温", "善长", "惟庸", "居正", "守仁",
                       "如晦", "玄龄", "魏徵", "敬德", "仁贵", "光弼", "子仪",
                       "仲达", "公瑾", "士元", "孝直", "文和", "奉孝"]
        positions = ["谋士", "太守", "县令", "参将", "使者"]

        recruited = []
        for _ in range(count):
            name = random.choice(surnames) + random.choice(given_names)
            position = random.choice(positions)
            ability = random.randint(40, 80)
            loyalty = random.randint(50, 80)

            oid = f"official_{faction_id}_{name}_{self.world.current_round}_{len(recruited)}"
            official = OfficialRecord(
                official_id=oid,
                name=name,
                faction_id=faction_id,
                position=position,
                loyalty=loyalty,
                ability=ability,
            )
            self.world.officials[oid] = official
            faction.officials.append(oid)
            recruited.append({"name": name, "position": position,
                              "ability": ability, "loyalty": loyalty})

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "officials_recruited",
            "narrative": f"{faction.name}选拔了{count}名新官员。",
        })

        return {"success": True, "recruited": recruited,
                "message": f"成功选拔{count}名官员"}


# ================================================================
# 8. 海盗 + 海战 + 移民 - WorldAdvancedEngine（P3 优先级）
# ================================================================

class WorldAdvancedEngine:
    """世界高级机制引擎：海盗、海战、移民"""

    def __init__(self, world: WorldState, game_const: dict = None):
        self.world = world
        self.const = _flatten_game_const(game_const or {})

    def check_piracy(self) -> list[dict]:
        """每回合检测海盗事件"""
        piracy_risk = self.const.get("maritime_piracy_risk", 0.1)
        events = []

        for tile in self.world.tiles.values():
            if not tile.faction_id:
                continue
            if tile.tile_type not in (TileType.PORT, TileType.COAST):
                continue
            if not tile.is_port:
                continue

            if random.random() < piracy_risk:
                faction = self.world.get_faction(tile.faction_id)
                loss = random.randint(50, 200)
                if faction:
                    faction.treasury = max(0, faction.treasury - loss)

                events.append({
                    "tile_id": tile.tile_id,
                    "tile_name": tile.tile_name,
                    "faction_id": tile.faction_id,
                    "loss": loss,
                })

                self.world.events_log.append({
                    "round": self.world.current_round,
                    "event_type": "piracy",
                    "narrative": f"海盗袭扰{tile.tile_name}港口，{faction.name if faction else '当地'}损失银两{loss}。",
                })

        return events

    def naval_battle(self, attacker_fid: str, defender_fid: str,
                     atk_troops: int, def_troops: int,
                     tile_id: str) -> dict:
        """海战结算"""
        tile = self.world.get_tile(tile_id)
        if not tile:
            return {"success": False, "message": "地块不存在"}

        if tile.tile_type not in (TileType.PORT, TileType.COAST, TileType.WATER):
            return {"success": False, "message": "只能在港口/海岸/水域进行海战"}

        attacker = self.world.get_faction(attacker_fid)
        defender = self.world.get_faction(defender_fid)
        if not attacker or not defender:
            return {"success": False, "message": "势力不存在"}

        water_bonus = self.const.get("naval_battle_water_bonus", 0.3)

        # 海战修正
        atk_naval = attacker.naval_power if hasattr(attacker, 'naval_power') else 1.0
        def_naval = defender.naval_power if hasattr(defender, 'naval_power') else 1.0

        atk_power = atk_troops * (1.0 + water_bonus) * atk_naval * (0.7 + random.random() * 0.6)
        def_power = def_troops * (1.0 + water_bonus) * def_naval * (0.7 + random.random() * 0.6)

        atk_loss = int(atk_troops * random.uniform(0.15, 0.45))
        def_loss = int(def_troops * random.uniform(0.15, 0.45))

        if atk_power > def_power:
            winner = attacker_fid
            atk_remaining = max(0, atk_troops - atk_loss)
            def_remaining = 0
        else:
            winner = defender_fid
            atk_remaining = 0
            def_remaining = max(0, def_troops - def_loss)

        # 损失兵力
        attacker.total_troops -= atk_loss
        defender.total_troops -= def_loss

        self.world.events_log.append({
            "round": self.world.current_round,
            "event_type": "naval_battle",
            "severity": "major",
            "narrative": (f"{attacker.name}与{defender.name}在{tile.tile_name}水域交战。"
                          f"{'攻方' if winner == attacker_fid else '守方'}获胜。"),
        })

        return {"success": True, "winner": winner,
                "attacker_losses": atk_loss, "defender_losses": def_loss,
                "attacker_remaining": atk_remaining, "defender_remaining": def_remaining}

    def process_migration(self) -> dict:
        """处理人口迁徙（流民移动）"""
        migration_cost = self.const.get("migration_cost_per_pop", 2)
        total_migrated = 0
        details = []

        # 找出民心最低的地块，人口向民心高的地块迁移
        owned_tiles = [t for t in self.world.tiles.values() if t.faction_id]
        if len(owned_tiles) < 2:
            return {"migrated": 0, "details": []}

        # 按民心排序
        low_morale = [t for t in owned_tiles if t.morale < 30 and t.population > 500]
        if not low_morale:
            return {"migrated": 0, "details": []}

        for source in low_morale[:3]:  # 最多处理3个低民心地块
            # 寻找同势力或邻接势力的高民心地块
            candidates = [
                t for t in owned_tiles
                if t.faction_id == source.faction_id
                and t.tile_id != source.tile_id
                and t.morale > 50
            ]
            if not candidates:
                # 找邻接高民心地块
                neighbors = self._get_neighbor_ids(source.tile_id)
                candidates = [
                    t for t in owned_tiles
                    if t.tile_id in neighbors and t.morale > 40
                ]

            if not candidates:
                continue

            dest = max(candidates, key=lambda t: t.morale)
            migrants = int(source.population * random.uniform(0.05, 0.15))
            migrants = min(migrants, source.population - 100)  # 留至少100人

            if migrants <= 0:
                continue

            source.population -= migrants
            dest.population += migrants

            # 民心变化
            source.morale = max(0, source.morale + 3)  # 离开后压力减小
            dest.morale = max(0, dest.morale - 2)     # 涌入后稍有压力

            total_migrated += migrants
            details.append({
                "from": source.tile_name,
                "to": dest.tile_name,
                "count": migrants,
            })

        if details:
            self.world.events_log.append({
                "round": self.world.current_round,
                "event_type": "migration",
                "narrative": f"流民迁徙：共{total_migrated}人从饥荒/战乱地区迁移至安定地区。",
            })

        return {"migrated": total_migrated, "details": details}

    def _get_neighbor_ids(self, tile_id: str) -> list[str]:
        """获取邻接地块ID列表"""
        try:
            coords = _parse_tile_coords(tile_id)
            if not coords:
                return []
            q, r = coords
            directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
            return [f"{q + dq},{r + dr}" for dq, dr in directions]
        except (ValueError, IndexError):
            return []
