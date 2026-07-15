"""
测试 AI 圣旨推演引擎 - 不依赖真实 LLM 的单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from server.core.edict_engine import (
    build_system_prompt, build_user_prompt, 
    parse_ai_response, validate_commands,
    build_world_summary
)
from server.models.world_state import WorldState, FactionState, TileState, TileType, Season

def create_test_world():
    """创建测试世界状态"""
    ws = WorldState()
    ws.current_round = 5
    ws.current_year = 1352
    ws.current_month = 6
    ws.current_season = Season.SUMMER
    ws.player_faction_id = "ruler_zhuyuan"

    # 玩家势力
    player = FactionState(
        faction_id="ruler_zhuyuan",
        name="朱元璋",
        treasury=10000,
        grain=5000,
        arms=200,
        horses=50,
        reputation=60,
        total_troops=3000,
        total_population=80000,
        realm_stability=55,
        court_stability=50,
        development_level=30,
        tile_count=3,
        is_player=True,
        is_alive=True,
    )
    ws.factions["ruler_zhuyuan"] = player

    # 敌方势力
    enemy = FactionState(
        faction_id="ruler_chenyouliang",
        name="陈友谅",
        treasury=8000,
        grain=4000,
        arms=150,
        total_troops=5000,
        total_population=60000,
        tile_count=4,
        is_alive=True,
    )
    ws.factions["ruler_chenyouliang"] = enemy

    # 玩家地块
    yingtian = TileState(
        tile_id="yingtian",
        tile_name="应天府",
        tile_type=TileType.CITY,
        faction_id="ruler_zhuyuan",
        population=40000,
        troops=1500,
        morale=60,
        fortification=2,
        is_capital=True,
        stable=1,
        armory=1,
        granary=1,
        q=0, r=0,
    )
    ws.tiles["yingtian"] = yingtian

    chuzhou = TileState(
        tile_id="chuzhou",
        tile_name="滁州",
        tile_type=TileType.CITY,
        faction_id="ruler_zhuyuan",
        population=25000,
        troops=1000,
        morale=55,
        fortification=1,
        q=1, r=0,
    )
    ws.tiles["chuzhou"] = chuzhou

    fengyang = TileState(
        tile_id="fengyang",
        tile_name="凤阳",
        tile_type=TileType.FARMLAND,
        faction_id="ruler_zhuyuan",
        population=15000,
        troops=500,
        morale=50,
        fortification=0,
        q=0, r=1,
    )
    ws.tiles["fengyang"] = fengyang

    return ws


def test_parse_ai_response():
    """测试 AI 响应解析"""
    print("=" * 60)
    print("测试 1: parse_ai_response")
    
    # 测试直接 JSON
    resp1 = '{"intent_analysis":"测试","commands":[{"action":"recruit","params":{"tile_id":"yingtian","amount":100}}]}'
    r1 = parse_ai_response(resp1)
    assert r1["intent_analysis"] == "测试"
    assert len(r1["commands"]) == 1
    assert r1["commands"][0]["action"] == "recruit"
    print("  ✅ 直接 JSON 解析通过")

    # 测试 markdown 代码块
    resp2 = '```json\n{"intent_analysis":"测试2","commands":[]}\n```'
    r2 = parse_ai_response(resp2)
    assert r2["intent_analysis"] == "测试2"
    print("  ✅ markdown 代码块解析通过")

    # 测试文本中的 JSON
    resp3 = '好的，圣旨解读如下：\n{"intent_analysis":"征兵","commands":[{"action":"recruit","params":{"tile_id":"yingtian","amount":500}}]}\n请审阅。'
    r3 = parse_ai_response(resp3)
    assert r3["intent_analysis"] == "征兵"
    print("  ✅ 文本中 JSON 解析通过")

    # 测试无效文本
    resp4 = '无效响应'
    r4 = parse_ai_response(resp4)
    assert r4 == {}
    print("  ✅ 无效文本返回空字典")


def test_validate_commands():
    """测试指令校验"""
    print("\n" + "=" * 60)
    print("测试 2: validate_commands")
    
    ws = create_test_world()
    world_dict = ws.model_dump()

    # 有效指令
    valid_cmds = [
        {"action": "recruit", "params": {"tile_id": "yingtian", "amount": 100}},
        {"action": "buy_horses", "params": {"amount": 50}},
        {"action": "develop", "params": {"tile_id": "yingtian", "type": "farmland"}},
    ]
    valid, invalid = validate_commands(valid_cmds, world_dict)
    assert len(valid) == 3
    assert len(invalid) == 0
    print(f"  ✅ 有效指令全部通过: {len(valid)}条")

    # 无效指令：未知操作
    invalid_cmds = [
        {"action": "unknown_action", "params": {}},
    ]
    valid, invalid = validate_commands(invalid_cmds, world_dict)
    assert len(valid) == 0
    assert len(invalid) == 1
    print(f"  ✅ 未知操作被拒绝: {invalid[0]['error']}")

    # 无效指令：不属于己方的地块
    bad_cmds = [
        {"action": "recruit", "params": {"tile_id": "nonexistent", "amount": 100}},
    ]
    valid, invalid = validate_commands(bad_cmds, world_dict)
    print(f"  ✅ 非己方地块操作: valid={len(valid)}, invalid={len(invalid)}")

    # 数值修正：超量征兵
    over_cmds = [
        {"action": "recruit", "params": {"tile_id": "yingtian", "amount": 10000}},
    ]
    valid, invalid = validate_commands(over_cmds, world_dict)
    if valid:
        assert valid[0]["params"]["amount"] == 5000
        print(f"  ✅ 超量征兵自动修正为5000")


def test_build_prompts():
    """测试提示词构建"""
    print("\n" + "=" * 60)
    print("测试 3: build_system_prompt & build_user_prompt")
    
    ws = create_test_world()
    world_dict = ws.model_dump()

    system_prompt = build_system_prompt("朱元璋", "当前天下大乱，群雄并起。")
    assert "朱元璋" in system_prompt
    assert "recruit" in system_prompt
    assert "march" in system_prompt
    assert "diplomacy" in system_prompt
    print(f"  ✅ system_prompt 长度: {len(system_prompt)}")

    user_prompt = build_user_prompt("征兵三千，加固应天城防", world_dict)
    assert "征兵三千" in user_prompt
    assert "朱元璋" in user_prompt
    assert "应天府" in user_prompt
    assert "银两: 10000" in user_prompt
    print(f"  ✅ user_prompt 长度: {len(user_prompt)}")


def test_build_world_summary():
    """测试世界摘要"""
    print("\n" + "=" * 60)
    print("测试 4: build_world_summary")
    
    ws = create_test_world()
    world_dict = ws.model_dump()
    summary = build_world_summary(world_dict)
    print(f"  ✅ 世界摘要:\n{summary}")


def test_full_flow_no_llm():
    """测试完整流程（无 LLM）"""
    print("\n" + "=" * 60)
    print("测试 5: 完整流程模拟（模拟 AI 返回）")
    
    ws = create_test_world()
    world_dict = ws.model_dump()

    # 模拟 AI 返回的 JSON
    ai_response = {
        "intent_analysis": "圣旨要求征兵、加固城防并买马",
        "narrative": "圣旨已阅。着兵部征兵一千，工部加固应天城防，另拨银买马百匹。",
        "commands": [
            {"action": "recruit", "params": {"tile_id": "yingtian", "amount": 1000}, "reason": "增强应天府守军"},
            {"action": "fortify", "params": {"tile_id": "yingtian"}, "reason": "加固应天城防"},
            {"action": "buy_horses", "params": {"amount": 100}, "reason": "扩充骑兵"},
            {"action": "develop", "params": {"tile_id": "fengyang", "type": "farmland"}, "reason": "开发凤阳农田"},
        ],
        "summary": "征兵一千、加固城防、买马百匹、开发农田",
    }

    # 验证指令
    valid, invalid = validate_commands(ai_response["commands"], world_dict)
    print(f"  有效指令: {len(valid)}条")
    for cmd in valid:
        print(f"    - {cmd['action']}: {cmd['reason']}")
    print(f"  无效指令: {len(invalid)}条")

    # 使用 RoundEngine 执行
    from server.core.round_engine import RoundEngine
    engine = RoundEngine(ws, {})

    from server.core.edict_engine import execute_edict_commands
    result = execute_edict_commands(valid, ws, engine)
    
    print(f"\n  执行结果:")
    print(f"    成功: {result['total_executed']}条")
    for cmd in result['executed']:
        print(f"      ✅ {cmd['action']}: {cmd['result'].get('message', '')}")
    print(f"    失败: {result['total_failed']}条")
    for cmd in result['failed']:
        print(f"      ❌ {cmd['action']}: {cmd['reason']}")

    # 验证数据变化
    player = ws.get_player_faction()
    yingtian = ws.get_tile("yingtian")
    fengyang = ws.get_tile("fengyang")

    print(f"\n  执行后数据:")
    print(f"    银两: {player.treasury} (初始10000)")
    print(f"    战马: {player.horses} (初始50)")
    print(f"    应天府兵力: {yingtian.troops} (初始1500)")
    print(f"    应天府城防: {yingtian.fortification} (初始2)")
    print(f"    凤阳开发度: {getattr(fengyang, 'development_level', 0)}")

    # 基本断言
    assert player.treasury < 10000, "银两应该被消耗"
    assert player.horses > 50, "战马应该增加"
    assert yingtian.troops > 1500, "应天府兵力应该增加"
    print("\n  ✅ 所有断言通过！数据正确变化")


if __name__ == "__main__":
    test_parse_ai_response()
    test_validate_commands()
    test_build_prompts()
    test_build_world_summary()
    test_full_flow_no_llm()
    print("\n" + "=" * 60)
    print("🎉 全部测试通过！")
