"""
游戏阶段检测器 (Game Phase Detector)

基于 autonomous-agent-gaming skill 的 Multi-Stage Strategy 模式：
- Opening（开局）：势力数量多、地盘分散、以扩张为主
- Midgame（中期）：势力开始淘汰、同盟形成、大规模会战
- Endgame（残局）：仅剩2-3个主要势力、决战阶段

用于自适应调整 AI 策略参数：
- Opening → 激进扩张、探索型策略（高 temperature）
- Midgame → 均衡发展、博弈型策略（中 temperature）  
- Endgame → 保守精算、决战型策略（低 temperature）
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger("yuanmo.agent.phase_detector")


class GamePhase(str, Enum):
    """游戏阶段"""
    OPENING = "opening"        # 开局：势力≥5，无霸主
    MIDGAME = "midgame"        # 中期：势力3-5，有区域霸主
    ENDGAME = "endgame"        # 残局：势力≤2，或某势力占比>60%


class FactionRole(str, Enum):
    """势力角色（基于阶段+实力）"""
    HEGEMON = "hegemon"        # 霸主：实力占优，维持优势
    CHALLENGER = "challenger"  # 挑战者：第二梯队，挑战霸主
    SURVIVOR = "survivor"      # 幸存者：弱小势力，力求自保
    BALANCER = "balancer"      # 平衡者：中等势力，左右逢源


class PhaseContext:
    """阶段上下文 - 包含阶段信息 + 策略参数建议"""

    def __init__(
        self,
        phase: GamePhase,
        total_factions: int,
        alive_factions: int,
        dominant_faction_id: str = "",
        dominant_share: float = 0.0,
        temperature_mod: float = 0.0,
        expansion_bias: float = 0.0,
        diplomacy_weight: float = 0.0,
    ):
        self.phase = phase
        self.total_factions = total_factions
        self.alive_factions = alive_factions
        self.dominant_faction_id = dominant_faction_id
        self.dominant_share = dominant_share
        self.temperature_mod = temperature_mod      # LLM temperature 调整
        self.expansion_bias = expansion_bias         # 扩张倾向 (-1~+1)
        self.diplomacy_weight = diplomacy_weight     # 外交权重 (0~1)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "total_factions": self.total_factions,
            "alive_factions": self.alive_factions,
            "dominant_faction_id": self.dominant_faction_id,
            "dominant_share": round(self.dominant_share, 3),
            "temperature_mod": round(self.temperature_mod, 2),
            "expansion_bias": round(self.expansion_bias, 2),
            "diplomacy_weight": round(self.diplomacy_weight, 2),
        }

    def get_faction_role(self, faction_id: str, tile_share: float, relative_strength: float) -> FactionRole:
        """根据阶段和实力确定势力角色"""
        if self.phase == GamePhase.ENDGAME:
            if faction_id == self.dominant_faction_id or relative_strength > 1.5:
                return FactionRole.HEGEMON
            return FactionRole.CHALLENGER

        if self.phase == GamePhase.MIDGAME:
            if tile_share > 0.3:
                return FactionRole.HEGEMON
            if tile_share > 0.15:
                return FactionRole.BALANCER
            if relative_strength > 1.2:
                return FactionRole.CHALLENGER
            return FactionRole.SURVIVOR

        # Opening: 大多数是挑战者或幸存者
        if tile_share > 0.2:
            return FactionRole.CHALLENGER
        return FactionRole.SURVIVOR


class GamePhaseDetector:
    """
    游戏阶段检测器

    用法:
        detector = GamePhaseDetector()
        ctx = detector.detect(world_state, faction_configs)
        # 根据 ctx.phase 调整策略
        # 根据 ctx.get_faction_role(fid, share, strength) 确定角色
    """

    # 阶段判定阈值
    OPENING_MAX_FACTIONS = 5       # >5 势力 → Opening
    MIDGAME_MIN_FACTIONS = 3       # 3-5 势力 → Midgame
    DOMINANCE_THRESHOLD = 0.5      # 某势力地盘占比>50% → Endgame
    ENDGAME_MAX_FACTIONS = 2       # ≤2 势力 → Endgame

    def __init__(self):
        self._last_phase: Optional[GamePhase] = None
        self._phase_history: list[GamePhase] = []
        self._phase_duration: int = 0  # 当前阶段已持续回合数

    def detect(self, world_state: dict, faction_configs: dict) -> PhaseContext:
        """
        检测当前游戏阶段

        Args:
            world_state: 世界状态快照
            faction_configs: 势力配置

        Returns:
            PhaseContext 含阶段信息和策略参数建议
        """
        factions_data = world_state.get("factions", {})
        all_factions = faction_configs.get("factions", {})

        total = len(all_factions)
        alive = sum(
            1 for fid in all_factions
            if factions_data.get(fid, {}).get("alive", True)
        )

        # 计算各势力地盘占比
        total_tiles = sum(
            factions_data.get(fid, {}).get("tile_count", 0)
            for fid in all_factions
        ) or 1  # 避免除零

        shares = {}
        dominant_id = ""
        dominant_share = 0.0
        for fid in all_factions:
            share = factions_data.get(fid, {}).get("tile_count", 0) / total_tiles
            shares[fid] = share
            if share > dominant_share:
                dominant_share = share
                dominant_id = fid

        # 阶段判定
        if alive <= self.ENDGAME_MAX_FACTIONS or dominant_share >= self.DOMINANCE_THRESHOLD:
            phase = GamePhase.ENDGAME
            temp_mod = -0.15        # 降低随机性，精算决策
            exp_bias = 0.3          # 适度扩张
            dip_weight = 0.2        # 外交权重降低（决战时刻）
        elif alive >= self.OPENING_MAX_FACTIONS and dominant_share < 0.3:
            phase = GamePhase.OPENING
            temp_mod = 0.15         # 增加探索性
            exp_bias = 0.8          # 高度扩张倾向
            dip_weight = 0.5        # 中等外交权重
        else:
            phase = GamePhase.MIDGAME
            temp_mod = 0.0          # 均衡
            exp_bias = 0.5          # 均衡扩张
            dip_weight = 0.7        # 高外交权重（合纵连横关键期）

        # 阶段切换追踪
        if self._last_phase and self._last_phase != phase:
            self._phase_duration = 0
            logger.info(
                f"[PhaseDetector] 阶段切换: {self._last_phase.value} → {phase.value} "
                f"(存活势力={alive}, 霸主={dominant_id}, 占比={dominant_share:.1%})"
            )
        else:
            self._phase_duration += 1

        self._last_phase = phase
        self._phase_history.append(phase)
        # 只保留最近20回合
        if len(self._phase_history) > 20:
            self._phase_history = self._phase_history[-20:]

        ctx = PhaseContext(
            phase=phase,
            total_factions=total,
            alive_factions=alive,
            dominant_faction_id=dominant_id,
            dominant_share=dominant_share,
            temperature_mod=temp_mod,
            expansion_bias=exp_bias,
            diplomacy_weight=dip_weight,
        )

        logger.debug(
            f"[PhaseDetector] 阶段={phase.value} 存活={alive}/{total} "
            f"temp_mod={temp_mod:+.2f} exp_bias={exp_bias:.1f} dip_w={dip_weight:.1f}"
        )
        return ctx

    def get_strategy_hint(self, ctx: PhaseContext, faction_id: str, world_state: dict) -> str:
        """
        生成策略提示文本，可注入到 A2 君主 prompt 中

        Returns:
            策略提示（中文，50-100字）
        """
        factions_data = world_state.get("factions", {})
        faction = factions_data.get(faction_id, {})
        total_tiles = sum(
            factions_data.get(fid, {}).get("tile_count", 0)
            for fid in factions_data
        ) or 1
        tile_share = faction.get("tile_count", 0) / total_tiles

        # 计算相对实力
        faction_troops = faction.get("troops", 0)
        avg_troops = sum(
            factions_data.get(fid, {}).get("troops", 0)
            for fid in factions_data if factions_data.get(fid, {}).get("alive", True)
        ) / max(ctx.alive_factions, 1)
        relative_strength = faction_troops / max(avg_troops, 1)

        role = ctx.get_faction_role(faction_id, tile_share, relative_strength)

        hints = {
            (GamePhase.OPENING, FactionRole.CHALLENGER): "乱世初起，当速扩地盘、广积粮草，趁诸雄未稳抢占先机。",
            (GamePhase.OPENING, FactionRole.SURVIVOR): "势单力薄，当依附强邻或偏安一隅，养精蓄锐以待时机。",
            (GamePhase.MIDGAME, FactionRole.HEGEMON): "已据一方，当以势压人，分化瓦解诸侯联盟，各个击破。",
            (GamePhase.MIDGAME, FactionRole.BALANCER): "身处夹缝，当合纵连横，左右逢源，借力打力以求壮大。",
            (GamePhase.MIDGAME, FactionRole.CHALLENGER): "实力渐成，当联弱抗强，寻找霸主弱点施以打击。",
            (GamePhase.MIDGAME, FactionRole.SURVIVOR): "存亡之际，当灵活外交，依附强者以求生存，伺机反扑。",
            (GamePhase.ENDGAME, FactionRole.HEGEMON): "天下将定，当稳扎稳打，收拢残局，勿冒无谓之险。",
            (GamePhase.ENDGAME, FactionRole.CHALLENGER): "背水一战，当孤注一掷，集中兵力打击霸主薄弱处。",
            (GamePhase.ENDGAME, FactionRole.SURVIVOR): "大势已去，当审时度势，或降或走，保全基业为上。",
        }

        return hints.get(
            (ctx.phase, role),
            "静观其变，随机应变。",
        )

    def get_phase_summary(self) -> dict:
        """获取阶段统计摘要"""
        return {
            "current_phase": self._last_phase.value if self._last_phase else "unknown",
            "phase_duration": self._phase_duration,
            "recent_phases": [p.value for p in self._phase_history[-10:]],
        }


# 全局单例
_global_phase_detector: Optional[GamePhaseDetector] = None


def get_phase_detector() -> GamePhaseDetector:
    """获取全局阶段检测器单例"""
    global _global_phase_detector
    if _global_phase_detector is None:
        _global_phase_detector = GamePhaseDetector()
    return _global_phase_detector


def reset_phase_detector():
    """重置阶段检测器（新游戏开始时调用）"""
    global _global_phase_detector
    _global_phase_detector = GamePhaseDetector()
