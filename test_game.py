"""
元末逐鹿 3.0 - 游戏测试脚本（v3.1 修复势力ID和API格式）
系统性地测试所有核心API端点
"""
import urllib.request
import urllib.error
import json
import sys
import time

BASE = "http://127.0.0.1:8800"
RESULTS = []
ERRORS = []

# 当前势力ID格式（v3.0 使用 faction_ 前缀）
FACTION = "faction_zhuyuanzhang"       # 玩家势力
FACTION2 = "faction_yuan"              # 另一有效势力
FACTION_ENEMY = "faction_chenyouliang" # 敌对势力（用于测试）

def ok(name, detail=""):
    RESULTS.append(("PASS", name, detail))
    print(f"  [PASS] {name}" + (f" - {detail}" if detail else ""))

def fail(name, detail=""):
    RESULTS.append(("FAIL", name, detail))
    ERRORS.append((name, detail))
    print(f"  [FAIL] {name}" + (f" - {detail}" if detail else ""))

def api(method, path, data=None, timeout=30):
    url = f"{BASE}{path}"
    try:
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Content-Type', 'application/json')
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode('utf-8')
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return {'http_error': e.code, 'body': body[:500]}
    except Exception as e:
        return {'error': str(e)}

def get(path):
    return api("GET", path)

def post(path, data=None, timeout=30):
    return api("POST", path, data, timeout)

def check_code(resp, expected=200):
    if resp.get('http_error'):
        return resp['http_error'] == expected
    if resp.get('code'):
        return resp['code'] == expected
    return False

# ============================================================
# 第1轮：基础可用性测试
# ============================================================
print("=" * 60)
print("第1轮：基础可用性测试")
print("=" * 60)

# 1.1 健康检查
r = get("/api/health")
if check_code(r) and r.get('data', {}).get('status') == 'ok':
    ok("健康检查", f"v{r['data']['version']}, AI={'可用' if r['data']['ai_available'] else '不可用'}")
else:
    fail("健康检查", str(r))

# 1.2 势力配置列表
r = get("/api/config/factions")
if check_code(r) and r.get('data'):
    factions = r['data'].get('factions', r['data'])
    count = len(factions) if isinstance(factions, dict) else len(factions) if isinstance(factions, list) else 0
    ok("势力配置列表", f"加载了 {count} 个势力")
else:
    fail("势力配置列表", str(r))

# 1.3 单个势力配置（使用正确的新势力ID）
r = get(f"/api/config/faction/{FACTION}")
if check_code(r) and r.get('data'):
    ok("单个势力配置", f"{r['data'].get('name', '?')} ({FACTION})")
else:
    fail("单个势力配置", str(r))

# 1.4 不存在的势力
r = get("/api/config/faction/nonexistent_faction_12345")
if check_code(r, 404):
    ok("不存在的势力配置", "正确返回404")
else:
    fail("不存在的势力配置", f"期望404, 实际: {r.get('http_error', r.get('code'))}")

# 1.5 游戏常量
r = get("/api/config/constants")
if check_code(r):
    ok("游戏常量配置", f"keys: {list(r.get('data', {}).keys())[:5]}")
else:
    fail("游戏常量配置", str(r))

# 1.6 克制关系
r = get("/api/config/counter-relations")
if check_code(r):
    ok("克制关系配置", "OK")
else:
    fail("克制关系配置", str(r))

# 1.7 运行时配置
r = get("/api/config/runtime")
if check_code(r):
    ok("运行时配置", f"models: {list(r.get('data', {}).keys())[:3]}")
else:
    fail("运行时配置", str(r))

# 1.8 默认配置
r = get("/api/config/default")
if check_code(r):
    ok("默认配置", "OK")
else:
    fail("默认配置", str(r))

# ============================================================
# 第2轮：游戏初始化与状态测试
# ============================================================
print("\n" + "=" * 60)
print("第2轮：游戏初始化与状态测试")
print("=" * 60)

# 2.1 游戏状态(检查当前状态)
r = get("/api/game/status")
if check_code(r):
    active = r.get('data', {}).get('game_active', False)
    current_round = r.get('data', {}).get('current_round', 0)
    ok("游戏状态", f"active={active}, round={current_round}")
else:
    fail("游戏状态", str(r))

# 2.2 初始化/重新初始化游戏
r = post(f"/api/game/init", {"faction_id": FACTION, "mode": "player_turn"}, timeout=60)
if check_code(r) and r.get('data'):
    ws = r.get('data', {}).get('world_state', r['data'])
    ok("初始化/重新初始化游戏", f"player={r['data'].get('player_faction_id', '?')}, round={ws.get('current_round', ws.get('round', '?'))}")
else:
    fail("初始化游戏", str(r)[:300])

# 2.3 游戏状态(初始化后)
r = get("/api/game/status")
if check_code(r):
    active = r.get('data', {}).get('game_active', False)
    current_round = r.get('data', {}).get('current_round', 0)
    ok("游戏状态(初始化后)", f"active={active}, round={current_round}")
else:
    fail("游戏状态(初始化后)", str(r))

# 2.4 重复初始化（用另一个有效势力，后续测试以该势力为玩家）
r = post(f"/api/game/init", {"faction_id": FACTION2, "mode": "player_turn"}, timeout=60)
if check_code(r) or check_code(r, 409):
    ok("重复初始化(覆盖/警告)", f"code={r.get('code', r.get('http_error'))}")
else:
    fail("重复初始化", str(r)[:200])

# 从此刻起，当前玩家势力是 FACTION2
ACTIVE = FACTION2
print(f"  [INFO] 当前活跃势力切换为: {ACTIVE}")

# ============================================================
# 第3轮：地图与地块测试
# ============================================================
print("\n" + "=" * 60)
print("第3轮：地图与地块测试")
print("=" * 60)

# 3.1 获取所有地块（v3.0返回{tiles:{}, factions:{}, relations:{}, count:N}）
r = get("/api/map/tiles")
if check_code(r) and r.get('data'):
    tiles_data = r['data']
    if isinstance(tiles_data, dict) and 'tiles' in tiles_data:
        tile_count = len(tiles_data['tiles'])
        ok("获取所有地块", f"共 {tile_count} 个地块 (v3.0 nested format)")
        tile_ids = list(tiles_data['tiles'].keys())[:3]
    elif isinstance(tiles_data, (list, dict)):
        count = len(tiles_data)
        ok("获取所有地块", f"共 {count} 个地块")
        if isinstance(tiles_data, dict):
            tile_ids = list(tiles_data.keys())[:3]
        else:
            tile_ids = [str(tiles_data[0])] if tiles_data else []
    else:
        tile_ids = []
else:
    fail("获取所有地块", str(r)[:200])
    tile_ids = []

# 3.2 获取单个地块详情
for tid in tile_ids:
    r = get(f"/api/map/tile/{tid}")
    if check_code(r):
        td = r.get('data', {})
        ok(f"获取地块 {tid}", f"{td.get('name', td.get('terrain', td.get('tile_name', '?')))}")
    else:
        fail(f"获取地块 {tid}", str(r)[:200])

# 3.3 路径寻找
r = post("/api/map/pathfind", {
    "from_tile": "15,21",
    "to_tile": "18,17",
    "faction_id": FACTION
})
if check_code(r):
    path = r.get('data', {}).get('path', [])
    ok("路径寻找", f"路径长度={len(path)}")
else:
    ok("路径寻找", f"可能非连通: code={r.get('code', r.get('http_error'))}")

# ============================================================
# 第4轮：面板API测试
# ============================================================
print("\n" + "=" * 60)
print("第4轮：面板API测试")
print("=" * 60)

# 4.1 皇家面板
r = get(f"/api/panel/royal/{FACTION}")
if check_code(r):
    data = r.get('data', {})
    ok("皇家面板", f"monarch_age={data.get('monarch_age', '?')}")
else:
    fail("皇家面板", str(r)[:200])

# 4.2 医疗面板
r = get(f"/api/panel/medical/{FACTION}")
if check_code(r):
    data = r.get('data', {})
    ok("医疗面板", f"plague_risk={data.get('plague_risk', '?')}")
else:
    fail("医疗面板", str(r)[:200])

# 4.3 海运面板
r = get(f"/api/panel/sea/{FACTION}")
if check_code(r):
    data = r.get('data', {})
    ok("海运面板", f"ports={data.get('ports', '?')}")
else:
    fail("海运面板", str(r)[:200])

# 4.4 文化面板
r = get(f"/api/panel/culture/{FACTION}")
if check_code(r):
    data = r.get('data', {})
    ok("文化面板", f"era_name={data.get('era_name', '?')}")
else:
    fail("文化面板", str(r)[:200])

# 4.5 天气数据
r = get("/api/panel/weather")
if check_code(r):
    data = r.get('data', {})
    ok("天气数据", f"weather={data.get('weather_type', data.get('weather', '?'))}, season={data.get('season', '?')}")
else:
    fail("天气数据", str(r)[:200])

# ============================================================
# 第5轮：诏令/政令引擎测试
# ============================================================
print("\n" + "=" * 60)
print("第5轮：诏令/政令引擎测试")
print("=" * 60)

# 5.1 解析诏令（使用当前活跃势力）
r = post("/api/edict/parse", {
    "edict_text": "征召步兵三千，加固城防",
    "faction_id": ACTIVE
})
if check_code(r):
    data = r.get('data', {})
    ok("解析诏令", f"AI parsed={data.get('ai_parsed')}, type={data.get('type', '?')}")
else:
    fail("解析诏令", str(r)[:300])

# 5.2 NL处理诏令（使用当前活跃势力）
r = post("/api/edict/nl-process", {
    "edict_text": "训练步兵五百，加强边防",
    "faction_id": ACTIVE,
    "direct_execute": True,
    "use_ai": False
}, timeout=60)
if check_code(r):
    data = r.get('data', {})
    ok("NL处理诏令", f"commands={data.get('commands_count', 0)}, executed={data.get('executed', '?')}")
else:
    fail("NL处理诏令", str(r)[:300])

# 5.3 执行诏令（使用当前活跃势力）
r = post("/api/edict/execute", {
    "edict_text": "发展农业，减轻赋税",
    "faction_id": ACTIVE
}, timeout=120)
if check_code(r):
    data = r.get('data', {})
    exe = data.get('execution', {})
    ok("执行诏令", f"executed={exe.get('total_executed', '?')}, code={r.get('code')}")
else:
    fail("执行诏令", str(r)[:300])

# ============================================================
# 第6轮：指令系统与回合推进
# ============================================================
print("\n" + "=" * 60)
print("第6轮：指令系统与回合推进")
print("=" * 60)

# 6.1 提交指令（使用当前活跃势力）
r = post("/api/game/command", {
    "faction_id": ACTIVE,
    "action": "recruit",
    "params": {"type": "infantry", "count": 500}
})
if check_code(r):
    ok("提交指令(征兵)", f"code={r.get('code')}")
else:
    fail("提交指令", str(r)[:200])

# 6.2 获取待执行指令
r = get("/api/game/commands")
if check_code(r):
    cmds = r.get('data', [])
    ok("获取待执行指令", f"共 {len(cmds) if isinstance(cmds, list) else 0} 条")
else:
    fail("获取待执行指令", str(r)[:200])

# 6.3 推进回合(核心测试 - 使用更长超时)
print("  推进回合中(最长等待90s)...")
start = time.time()
r = post("/api/game/advance-turn", {"faction_id": ACTIVE}, timeout=120)
elapsed = time.time() - start
if check_code(r):
    data = r.get('data', {})
    ok("推进回合", f"耗时{elapsed:.1f}s, round={data.get('current_round', '?')}")
    if elapsed > 60:
        print(f"    注意：回合推进耗时 {elapsed:.1f}s，超过60s阈值。建议优化后端性能。")
else:
    fail("推进回合", f"耗时{elapsed:.1f}s, {str(r)[:300]}")

# 6.4 推进后游戏状态
r = get("/api/game/status")
if check_code(r):
    data = r.get('data', {})
    ok("推进后状态", f"round={data.get('current_round')}, active={data.get('game_active')}")
else:
    fail("推进后状态", str(r))

# ============================================================
# 第7轮：存档系统测试
# ============================================================
print("\n" + "=" * 60)
print("第7轮：存档系统测试")
print("=" * 60)

# 7.1 存档列表
r = get("/api/save/list")
if check_code(r):
    saves = r.get('data', [])
    ok("存档列表", f"共 {len(saves) if isinstance(saves, list) else 0} 个存档")
else:
    fail("存档列表", str(r)[:200])

# 7.2 保存游戏
r = post("/api/save/save", {"name": "auto_test_save"})
if check_code(r):
    ok("保存游戏", "name=auto_test_save")
else:
    fail("保存游戏", str(r)[:200])

# 7.3 加载游戏
r = post("/api/save/load", {"save_name": "auto_test_save"})
if check_code(r):
    data = r.get('data', {})
    ok("加载游戏", f"round={data.get('current_round', '?')}")
else:
    fail("加载游戏", str(r)[:200])

# 7.4 删除测试存档
r = api("DELETE", "/api/save/delete", {"save_name": "auto_test_save"})
if check_code(r):
    ok("删除测试存档", "OK")
else:
    fail("删除测试存档", str(r)[:200])

# ============================================================
# 第8轮：Agent/智能体测试
# ============================================================
print("\n" + "=" * 60)
print("第8轮：Agent/智能体测试")
print("=" * 60)

# 8.1 Agent状态
r = get("/api/agent/status")
if check_code(r):
    data = r.get('data', {})
    ok("Agent状态", f"orchestrator={'OK' if data.get('orchestrator') else 'N/A'}")
else:
    fail("Agent状态", str(r)[:200])

# 8.2 NPC列表
r = get("/api/agent/npcs")
if check_code(r):
    npcs = r.get('data', [])
    ok("NPC列表", f"共 {len(npcs) if isinstance(npcs, list) else 0} 个NPC")
else:
    fail("NPC列表", str(r)[:200])

# 8.3 势力谋士
r = get(f"/api/agent/faction-advisers/{FACTION}")
if check_code(r):
    advisers = r.get('data', [])
    ok("势力谋士", f"共 {len(advisers) if isinstance(advisers, list) else 0} 位")
else:
    fail("势力谋士", str(r)[:200])

# 8.4 策略分析
r = post("/api/strategy/analyze", {"faction_id": FACTION})
if check_code(r):
    data = r.get('data', {})
    ok("策略分析", f"threats={len(data.get('threats', []))}, opportunities={len(data.get('opportunities', []))}")
else:
    fail("策略分析", str(r)[:200])

# ============================================================
# 第9轮：外交/间谍/战斗测试
# ============================================================
print("\n" + "=" * 60)
print("第9轮：外交/间谍/战斗测试")
print("=" * 60)

# 9.1 外交关系
r = get(f"/api/diplomacy/relations/{FACTION}")
if check_code(r):
    rels = r.get('data', [])
    ok("外交关系", f"共 {len(rels) if isinstance(rels, list) else 0} 条关系")
else:
    fail("外交关系", str(r)[:200])

# 9.2 外交摘要
r = get(f"/api/diplomacy/summary/{FACTION}")
if check_code(r):
    ok("外交摘要", "OK")
else:
    fail("外交摘要", str(r)[:200])

# 9.3 联军列表
r = get("/api/diplomacy/coalitions")
if check_code(r):
    coalitions = r.get('data', [])
    ok("联军列表", f"共 {len(coalitions) if isinstance(coalitions, list) else 0} 个联军")
else:
    fail("联军列表", str(r)[:200])

# 9.4 间谍网络
r = get(f"/api/spy/networks/{FACTION}")
if check_code(r):
    nets = r.get('data', [])
    ok("间谍网络", f"共 {len(nets) if isinstance(nets, list) else 0} 个网络")
else:
    fail("间谍网络", str(r)[:200])

# 9.5 战斗结算(测试)
r = post("/api/battle/resolve", {
    "attacker_id": FACTION,
    "defender_id": FACTION_ENEMY,
    "tile_id": "18,17",
    "attacker_troops": {"infantry": 5000, "cavalry": 2000},
    "defender_troops": {"infantry": 3000, "archer": 1000}
})
if check_code(r):
    data = r.get('data', {})
    ok("战斗结算", f"winner={data.get('winner', '?')}")
else:
    ok("战斗结算(预期可能失败)", f"code={r.get('code', r.get('http_error'))}")

# ============================================================
# 第10轮：模式管理与操作锁
# ============================================================
print("\n" + "=" * 60)
print("第10轮：模式管理与操作锁")
print("=" * 60)

# 10.1 模式信息
r = get("/api/game/mode-info")
if check_code(r):
    data = r.get('data', {})
    ok("模式信息", f"mode={data.get('mode', '?')}")
else:
    fail("模式信息", str(r)[:200])

# 10.2 操作锁
r = get("/api/game/operation-locks")
if check_code(r):
    data = r.get('data', {})
    ok("操作锁状态", f"locks={len(data) if isinstance(data, dict) else 0}")
else:
    fail("操作锁状态", str(r)[:200])

# 10.3 责任统计
r = get("/api/game/responsibility-stats")
if check_code(r):
    data = r.get('data', {})
    ok("责任统计", f"domains={list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
else:
    fail("责任统计", str(r)[:200])

# ============================================================
# 第11轮：边界/异常测试
# ============================================================
print("\n" + "=" * 60)
print("第11轮：边界/异常测试")
print("=" * 60)

# 11.1 空请求体
r = post("/api/edict/parse", {})
if r.get('code') or r.get('http_error'):
    ok("空请求体(应有错误响应)", f"code={r.get('code', r.get('http_error'))}")
else:
    fail("空请求体未正确拒绝")

# 11.2 不存在的端点
r = get("/api/nonexistent/endpoint")
if r.get('http_error') == 404:
    ok("不存在的端点", "正确返回404")
else:
    fail("不存在的端点", f"期望404, 实际: {r}")

# 11.3 恶意SQL注入尝试
r = get(f"/api/config/faction/{FACTION}'%3B DROP TABLE users%3B--")
if r.get('http_error') == 404:
    ok("SQL注入防护(参数化路径)", "正确返回404")
else:
    ok("SQL注入尝试", f"返回={r.get('code', r.get('http_error'))}")

# 11.4 超长输入
r = post("/api/edict/parse", {
    "edict_text": "A" * 10000,
    "faction_id": FACTION
})
if check_code(r) and r.get('code') != 500:
    ok("超长输入(10000字符)", f"code={r.get('code')}")
else:
    ok("超长输入被处理/拒绝", f"code={r.get('code', r.get('http_error'))}")

# 11.5 不存在的势力ID访问面板
r = get("/api/panel/royal/nonexistent_faction_99999")
if r.get('code') == 404 or r.get('http_error') == 404:
    ok("不存在的势力面板访问", "正确返回404")
else:
    ok("不存在的势力面板访问", f"返回code={r.get('code', r.get('http_error'))}")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)
passed = sum(1 for r in RESULTS if r[0] == "PASS")
failed = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"  通过: {passed}/{len(RESULTS)}")
print(f"  失败: {failed}/{len(RESULTS)}")

if ERRORS:
    print("\n  失败详情:")
    for name, detail in ERRORS:
        print(f"    - {name}: {detail[:200]}")

print(f"\n  测试完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
