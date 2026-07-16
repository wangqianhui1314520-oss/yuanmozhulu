"""
战争迷雾系统测试 — FogTileRecord + FogOfWarEngine 核心行为

覆盖: server/core/fog_of_war.py
"""
import pytest
from server.core.fog_of_war import (
    VisibilityLevel, FogTileRecord, FogOfWarEngine,
)


# ================================================================
# VisibilityLevel 枚举
# ================================================================
class TestVisibilityLevel:
    def test_4_levels(self):
        assert len(VisibilityLevel) == 4

    def test_ordering(self):
        assert VisibilityLevel.HIDDEN < VisibilityLevel.FOGGY
        assert VisibilityLevel.FOGGY < VisibilityLevel.DIM
        assert VisibilityLevel.DIM < VisibilityLevel.VISIBLE

    def test_int_values(self):
        assert int(VisibilityLevel.HIDDEN) == 0
        assert int(VisibilityLevel.VISIBLE) == 3


# ================================================================
# FogTileRecord 数据类
# ================================================================
class TestFogTileRecord:
    def test_default_values(self):
        record = FogTileRecord()
        assert record.visibility == VisibilityLevel.HIDDEN
        assert record.last_seen_round == -1
        assert record.last_seen_owner == ""
        assert record.last_seen_troops == 0
        assert record.last_seen_buildings == {}

    def test_to_dict(self):
        record = FogTileRecord(visibility=VisibilityLevel.VISIBLE, last_seen_round=5)
        d = record.to_dict()
        assert d["visibility"] == 3
        assert d["last_seen_round"] == 5

    def test_from_dict_roundtrip(self):
        original = FogTileRecord(
            visibility=VisibilityLevel.DIM,
            last_seen_round=10,
            last_seen_owner="faction_yuan",
            last_seen_troops=300,
            last_seen_buildings={"beacon": 2},
        )
        d = original.to_dict()
        restored = FogTileRecord.from_dict(d)
        assert restored.visibility == original.visibility
        assert restored.last_seen_round == original.last_seen_round
        assert restored.last_seen_owner == original.last_seen_owner
        assert restored.last_seen_troops == original.last_seen_troops
        assert restored.last_seen_buildings == original.last_seen_buildings

    def test_to_dict_json_serializable(self):
        """to_dict() 输出必须可 JSON 序列化"""
        import json
        record = FogTileRecord(visibility=VisibilityLevel.VISIBLE, last_seen_round=3)
        s = json.dumps(record.to_dict())
        assert "visibility" in s


# ================================================================
# FogOfWarEngine 核心行为（使用 mock）
# ================================================================
class TestFogOfWarEngine:
    """FogOfWarEngine 单元测试（mock WorldState）"""

    def test_init_uses_defaults(self, mock_world_state):
        engine = FogOfWarEngine(mock_world_state)
        assert engine._beacon_vision == 2  # 默认值（无 bld cfg 时用game_const默认）
        assert engine._troop_vision == 1

    def test_init_with_custom_config(self, mock_world_state):
        cfg = {"building": {"beacon": {"vision_range_per_level": 3}}}
        engine = FogOfWarEngine(mock_world_state, game_const=cfg)
        assert engine._beacon_vision == 3

    def test_calculate_visibility_dead_faction(self, mock_world_state):
        """已灭亡势力返回空字典"""
        mock_world_state.factions = {}
        engine = FogOfWarEngine(mock_world_state)
        result = engine.calculate_visibility("faction_yuan")
        assert result == {}

    def test_own_territory_always_visible(self, mock_world_state, mock_tile):
        """己方领土永远是 VISIBLE"""
        engine = FogOfWarEngine(mock_world_state)
        fog = engine.calculate_visibility("faction_yuan")
        assert mock_tile.tile_id in fog
        assert fog[mock_tile.tile_id].visibility == VisibilityLevel.VISIBLE

    def test_get_tile_visibility_own_tile(self, mock_world_state, mock_tile):
        """即使未调用 calculate_visibility，己方地块也应可见"""
        engine = FogOfWarEngine(mock_world_state)
        # 尚未计算迷雾
        vis = engine.get_tile_visibility("faction_yuan", mock_tile.tile_id)
        assert vis == VisibilityLevel.VISIBLE

    def test_get_tile_visibility_unknown_tile(self, mock_world_state):
        """未探索地块为 HIDDEN"""
        engine = FogOfWarEngine(mock_world_state)
        vis = engine.get_tile_visibility("faction_yuan", "99,99")
        assert vis == VisibilityLevel.HIDDEN

    def test_is_tile_visible_false_for_hidden(self, mock_world_state):
        engine = FogOfWarEngine(mock_world_state)
        assert engine.is_tile_visible("faction_yuan", "99,99") is False

    def test_is_tile_visible_true_for_confirmed(self, mock_world_state):
        """调用 calculate_visibility 后确认可见"""
        engine = FogOfWarEngine(mock_world_state)
        engine.calculate_visibility("faction_yuan")
        for tid in mock_world_state.tiles:
            t = mock_world_state.tiles[tid]
            if t.faction_id == "faction_yuan":
                assert engine.is_tile_visible("faction_yuan", tid) is True

    def test_decay_reduces_visibility(self, mock_world_state):
        """迷雾衰减：非己方地块可见度-1"""
        from unittest.mock import MagicMock
        # 添加一个非己方可见记录
        engine = FogOfWarEngine(mock_world_state)
        engine._fog_layers["faction_yuan"] = {
            "20,15": FogTileRecord(
                visibility=VisibilityLevel.DIM,
                last_seen_round=1,
            )
        }
        engine.decay_fog("faction_yuan")
        assert engine._fog_layers["faction_yuan"]["20,15"].visibility == VisibilityLevel.FOGGY

    def test_decay_own_territory_no_decay(self, mock_world_state, mock_tile):
        """己方领土不衰减"""
        engine = FogOfWarEngine(mock_world_state)
        engine._fog_layers["faction_yuan"] = {
            mock_tile.tile_id: FogTileRecord(
                visibility=VisibilityLevel.VISIBLE,
                last_seen_round=1,
            )
        }
        # 确保 tile 的 faction_id 匹配
        mock_tile.faction_id = "faction_yuan"
        engine.decay_fog("faction_yuan")
        assert engine._fog_layers["faction_yuan"][mock_tile.tile_id].visibility == VisibilityLevel.VISIBLE

    def test_decay_hidden_stays_hidden(self, mock_world_state):
        """HIDDEN 不会再衰减"""
        engine = FogOfWarEngine(mock_world_state)
        engine._fog_layers["faction_yuan"] = {
            "20,15": FogTileRecord(
                visibility=VisibilityLevel.HIDDEN,
                last_seen_round=1,
            )
        }
        engine.decay_fog("faction_yuan")
        assert engine._fog_layers["faction_yuan"]["20,15"].visibility == VisibilityLevel.HIDDEN

    def test_update_on_round_end_decays_all(self, mock_world_state, mock_faction):
        """回合结束对所有存活势力衰减迷雾"""
        engine = FogOfWarEngine(mock_world_state)
        # 预置非己方可见记录
        engine._fog_layers["faction_yuan"] = {
            "99,99": FogTileRecord(visibility=VisibilityLevel.FOGGY, last_seen_round=1)
        }
        engine.update_on_round_end()
        assert engine._fog_layers["faction_yuan"]["99,99"].visibility == VisibilityLevel.HIDDEN

    def test_get_visibility_summary(self, mock_world_state):
        engine = FogOfWarEngine(mock_world_state)
        engine.calculate_visibility("faction_yuan")
        summary = engine.get_visibility_summary("faction_yuan")
        assert "total_tiles" in summary
        assert "visible" in summary
        assert "hidden" in summary
        assert summary["total_tiles"] > 0
        assert summary["visible"] >= 1  # 至少己方领土可见

    def test_get_fog_map_serializable(self, mock_world_state):
        engine = FogOfWarEngine(mock_world_state)
        engine.calculate_visibility("faction_yuan")
        fog_map = engine.get_fog_map("faction_yuan")
        assert isinstance(fog_map, dict)

    def test_get_visible_enemy_troops_empty_initial(self, mock_world_state):
        """初始状态无可见敌军"""
        engine = FogOfWarEngine(mock_world_state)
        enemies = engine.get_visible_enemy_troops("faction_yuan")
        assert enemies == []
