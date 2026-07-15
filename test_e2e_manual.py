"""端到端手动测试 - 模拟完整游戏流程"""
import requests
import json
import time

BASE = "http://localhost:8800/api"
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")

def api(method, path, data=None):
    url = f"{BASE}{path}"
    if method == "GET":
        r = requests.get(url, timeout=10)
    else:
        r = requests.post(url, json=data, timeout=30)
    r.encoding = 'utf-8'
    return r.json()

print("=" * 60)
print("  元末逐鹿 3.0 · 端到端测试")
print("=" * 60)

# ========== 1. 主页/健康检查 ==========
print("\n>>> 1. 主页 · 健康检查")
r = api("GET", "/health")
check("健康端点返回成功", r["code"] == 200, f"code={r['code']}")
check("版本号正确", r["data"]["version"] == "3.0.0")
check("AI可用", r["data"]["ai_available"] == True)
check("势力加载成功", r["data"]["factions_loaded"] == 9)
check("游戏未开始", r["data"]["game_active"] == False)

# ========== 2. 势力选择页 ==========
print("\n>>> 2. 势力选择页 · 获取势力列表")
r = api("GET", "/config/factions")
check("势力配置返回成功", r["code"] == 200)
factions = r["data"]["factions"]
check("有9个势力", len(factions) == 9, f"实际={len(factions)}")
check("元顺帝存在", "ruler_yuan" in factions)
check("朱元璋存在", "ruler_zhuyuanzhang" in factions)
check("张士诚存在", "ruler_zhangshicheng" in factions)
check("方国珍存在", "ruler_fangguozhen" in factions)

# ========== 3. 初始化游戏（选择元顺帝） ==========
print("\n>>> 3. 初始化游戏 · 选择元顺帝")
r = api("POST", "/game/init", {"faction_id": "ruler_yuan", "mode": "player_turn"})
check("初始化返回成功", r["code"] == 200, f"code={r['code']} msg={r['msg']}")
data = r["data"]
ws = data["world_state"]
check("回合为0", ws["current_round"] == 0, f"round={ws['current_round']}")
check("年份为1351", ws.get("current_year", 0) == 1351, f"year={ws.get('current_year')}")
check("有9个势力", len(ws["factions"]) == 9, f"实际={len(ws['factions'])}")
check("地块数量>0", len(ws["tiles"]) > 0, f"实际={len(ws['tiles'])}")
check("玩家势力=ruler_yuan", data.get("player_faction_id") == "ruler_yuan")
check("模式=player_turn", data.get("mode") == "player_turn")

# 检查元顺帝的初始状态
yuan = ws["factions"].get("ruler_yuan", {})
check("元顺帝有初始领土", yuan.get("tile_count", 0) > 0, f"tile_count={yuan.get('tile_count')}")
check("元顺帝有初始兵力", yuan.get("total_troops", 0) > 0, f"troops={yuan.get('total_troops')}")
check("元顺帝有初始国库", yuan.get("treasury", 0) > 0, f"treasury={yuan.get('treasury')}")
check("元顺帝首都是hex_2_20", yuan.get("capital_tile") == "hex_2_20")

# ========== 4. 游戏状态查询 ==========
print("\n>>> 4. 游戏状态查询")
r = api("GET", "/game/status")
check("状态查询成功", r["code"] == 200)
check("游戏活跃", r["data"]["game_active"] == True)
check("回合=0", r["data"]["current_round"] == 0)

# ========== 5. 地图/地块查询 ==========
print("\n>>> 5. 地图/地块查询")
r = api("GET", "/map/tile/hex_2_20")
check("查询大都地块成功", r["code"] == 200, f"code={r['code']}")
tile = r.get("data") or {}
check("地块名正确", tile.get("tile_name") == "大都", f"name={tile.get('tile_name')}")
check("地块归属正确", tile.get("faction_id") == "ruler_yuan", f"faction={tile.get('faction_id')}")

r = api("GET", "/map/tiles")
check("获取所有地块成功", r["code"] == 200)

# ========== 6. 提交指令 ==========
print("\n>>> 6. 提交指令 · 政令系统")
cmd = api("POST", "/game/command", {
    "action": "recruit",
    "params": {"count": 100, "tile_id": "hex_dadu"}
})
check("征募指令提交成功", cmd["code"] == 200, f"code={cmd['code']} msg={cmd.get('msg')}")

cmd = api("POST", "/game/command", {
    "action": "tax_adjust",
    "params": {"rate": 10, "tile_id": "hex_dadu"}
})
check("税率调整指令提交成功", cmd["code"] == 200, f"code={cmd['code']}")

# ========== 7. 推进回合 ==========
print("\n>>> 7. 推进回合 · 第1回合")
r = api("POST", "/game/advance-turn")
check("推进回合成功", r["code"] == 200, f"code={r['code']} msg={r.get('msg')}")
if r["code"] == 200:
    ws2 = r["data"]["world_state"]
    check("回合=1", ws2["current_round"] == 1, f"round={ws2['current_round']}")
    events = r["data"].get("events", [])
    print(f"    本回合事件数: {len(events)}")
    for e in events[:5]:
        print(f"      - {e.get('type','?')}: {e.get('description','')[:80]}")

# ========== 8. 存档功能 ==========
print("\n>>> 8. 存档功能")
# 保存
r = api("POST", "/save/save", {"slot": 0, "note": "测试存档-第1回合"})
check("存档成功", r["code"] == 200, f"code={r['code']} msg={r.get('msg')}")

# 列出存档
r = api("GET", "/save/list")
check("列出存档成功", r["code"] == 200)
saves = r.get("data", {}).get("saves", [])
check("有1个存档", len(saves) == 1, f"实际={len(saves)}")
if saves:
    s = saves[0]
    check("存档槽位=0", s.get("slot") == 0, f"slot={s.get('slot')}")
    check("存档备注正确", s.get("note") == "测试存档-第1回合", f"note={s.get('note')}")

# ========== 9. 读档功能 ==========
print("\n>>> 9. 读档功能")
r = api("POST", "/save/load", {"slot": 0})
check("读档成功", r["code"] == 200, f"code={r['code']} msg={r.get('msg')}")
if r["code"] == 200:
    ws3 = r["data"]["world_state"]
    check("读档后回合=1", ws3["current_round"] == 1, f"round={ws3['current_round']}")

# ========== 10. 再推进几个回合 ==========
print("\n>>> 10. 连续推进回合")
for i in range(3):
    r = api("POST", "/game/advance-turn")
    check(f"回合{i+2}推进成功", r["code"] == 200, f"code={r['code']}")
    if r["code"] == 200:
        ws = r["data"]["world_state"]
        print(f"    回合{ws['current_round']}: 年份{ws.get('current_year')}年{ws.get('current_month')}月")

# ========== 11. 删除存档 ==========
print("\n>>> 11. 删除存档")
r = api("DELETE", "/save/delete", {"slot": 0})
check("删除存档成功", r["code"] == 200, f"code={r['code']} msg={r.get('msg')}")

# ========== 12. 重新开始游戏 ==========
print("\n>>> 12. 重新开始游戏")
r = api("POST", "/game/restart")
check("重新开始成功", r["code"] == 200, f"code={r['code']} msg={r.get('msg')}")

# ========== 13. 初始化后直接测试 game/init 的返回结构 ==========
print("\n>>> 13. init 返回数据结构检查")
r = api("POST", "/game/init", {"faction_id": "ruler_yuan", "mode": "player_turn"})
check("第二次初始化成功", r["code"] == 200)
data = r["data"]
# 检查前端需要的字段
check("有 world_state", "world_state" in data)
check("有 player_faction_id", "player_faction_id" in data)
check("有 mode", "mode" in data)
check("有 round", "round" in data or "round" in data.get("world_state", {}))
check("有 year", "year" in data or "current_year" in data.get("world_state", {}))

ws = data["world_state"]
# 检查 world_state 的关键字段
check("world_state有factions", "factions" in ws)
check("world_state有tiles", "tiles" in ws)
check("world_state有events", "events" in ws)
check("world_state有current_round", "current_round" in ws)

# 检查 faction 结构
first_faction = list(ws["factions"].values())[0]
check("faction有tile_count", "tile_count" in first_faction, f"keys={list(first_faction.keys())[:10]}")
check("faction有total_troops", "total_troops" in first_faction)
check("faction有treasury", "treasury" in first_faction)
check("faction有capital_tile", "capital_tile" in first_faction)

# 检查 tile 结构
first_tile = list(ws["tiles"].values())[0]
check("tile有tile_name", "tile_name" in first_tile, f"keys={list(first_tile.keys())[:10]}")
check("tile有faction_id", "faction_id" in first_tile)
check("tile有tile_type", "tile_type" in first_tile)

# ========== 14. 测试异常情况 ==========
print("\n>>> 14. 异常情况测试")
# 无效势力
r = api("POST", "/game/init", {"faction_id": "nonexistent", "mode": "player_turn"})
check("无效势力初始化被拒绝", r["code"] != 200, f"code={r['code']}")

# 无效存档槽位
r = api("POST", "/save/load", {"slot": 999})
check("无效存档槽位被拒绝", r["code"] != 200, f"code={r['code']}")

# ========== 总结 ==========
print("\n" + "=" * 60)
print(f"  测试完成: 通过 {PASS} / 失败 {FAIL} (共 {PASS+FAIL})")
print("=" * 60)
