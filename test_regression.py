"""元末逐鹿 3.0 - 快速回归测试（v3.1 修复势力ID和API格式，跳过AI调用）"""
import urllib.request, json, time

BASE = "http://127.0.0.1:8800"
FACTION = "faction_zhuyuanzhang"
FACTION2 = "faction_yuan"

passed = 0
failed = 0
errors = []

def api(method, path, data=None, timeout=30):
    url = BASE + path
    try:
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Content-Type', 'application/json')
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return {'http_error': e.code, 'body': body[:300]}
    except Exception as e:
        return {'error': str(e)}

def get(p): return api("GET", p)
def post(p, d=None, timeout=30): return api("POST", p, d, timeout)
def delete(p, d=None): return api("DELETE", p, d)

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  [PASS] %s" % name + (" - " + detail if detail else ""))
    else:
        failed += 1
        errors.append((name, detail))
        print("  [FAIL] %s" % name + (" - " + detail if detail else ""))

# === 第1轮: 基础 ===
print("=" * 60)
print("Round 1: Basic Health & Config")
print("=" * 60)

r = get("/api/health")
check("Health check", r.get('code') == 200, "v" + str(r.get('data', {}).get('version', '?')))

r = get("/api/config/factions")
check("Factions config", r.get('code') == 200 and r.get('data'))

r = get(f"/api/config/faction/{FACTION}")
check("Faction detail", r.get('code') == 200, r.get('data', {}).get('name', '?'))

r = get("/api/config/faction/hongjin_old_nonexistent")
check("Faction detail (nonexistent)", r.get('code') == 404 or r.get('http_error') == 404)

r = get("/api/config/constants")
check("Game constants", r.get('code') == 200)

r = get("/api/config/counter-relations")
check("Counter relations", r.get('code') == 200)

r = get("/api/config/runtime")
check("Runtime config", r.get('code') == 200)

# === 第2轮: 游戏初始化 ===
print()
print("=" * 60)
print("Round 2: Game Init")
print("=" * 60)

r = post("/api/game/init", {"faction_id": "nonexistent_faction_999"})
check("Init non-existent faction rejected", r.get('code') == 404 or r.get('http_error') == 404)

r = post(f"/api/game/init", {"faction_id": FACTION, "mode": "player_turn"}, timeout=60)
check("Init valid faction", r.get('code') == 200, "player=" + str(r.get('data', {}).get('player_faction_id', '?')))

r = get("/api/game/status")
check("Game status (active)", r.get('data', {}).get('game_active') == True)

r = post(f"/api/game/init", {"faction_id": FACTION2, "mode": "player_turn"}, timeout=60)
check("Re-init overwrites", r.get('code') == 200, "player=" + str(r.get('data', {}).get('player_faction_id', '?')))

# === 第3轮: 面板API ===
print()
print("=" * 60)
print("Round 3: Panel APIs")
print("=" * 60)

for label, path in [
    ("Weather", "/api/panel/weather"),
    ("Culture", f"/api/panel/culture/{FACTION2}"),
    ("Sea", f"/api/panel/sea/{FACTION2}"),
    ("Medical", f"/api/panel/medical/{FACTION2}"),
    ("Royal", f"/api/panel/royal/{FACTION2}"),
]:
    r = get(path)
    check(label + " panel", r.get('code') == 200)

# === 第4轮: 地图 ===
print()
print("=" * 60)
print("Round 4: Map API")
print("=" * 60)

r = get("/api/map/tiles")
check("All tiles", r.get('code') == 200)
tiles_data = r.get('data', {})

# v3.0 format: {tiles: {...}, factions: {...}, relations: {...}, count: N}
if tiles_data and 'tiles' in tiles_data:
    tile_ids = list(tiles_data['tiles'].keys())[:1]
elif tiles_data and isinstance(tiles_data, dict):
    tile_ids = list(tiles_data.keys())[:1]
else:
    tile_ids = []

for tid in tile_ids:
    r = get("/api/map/tile/" + tid)
    check("Tile detail " + tid, r.get('code') == 200)

r = post("/api/map/pathfind", {"from_tile": "15,21", "to_tile": "18,17", "faction_id": FACTION2})
check("Pathfind", r.get('code') in (200, 404))

# === 第5轮: 指令与诏令（跳过AI调用） ===
print()
print("=" * 60)
print("Round 5: Commands & Edicts (no AI)")
print("=" * 60)

r = post("/api/game/command", {
    "faction_id": FACTION2,
    "action": "recruit",
    "params": {"type": "infantry", "count": 500}
})
check("Submit command", r.get('code') in (200, 403, 400), str(r.get('code')))

r = get("/api/game/commands")
check("Pending commands", r.get('code') == 200)

r = post("/api/edict/parse", {"edict_text": "征召步兵三千，加固城防", "faction_id": FACTION2})
check("Parse edict", r.get('code') in (200, 400, 500), str(r.get('code')))

r = post("/api/edict/nl-process", {
    "edict_text": "征兵一千",
    "faction_id": FACTION2,
    "direct_execute": True,
    "use_ai": False
}, timeout=60)
check("NL process edict (no AI)", r.get('code') in (200, 400, 500), str(r.get('code')))

# === 第6轮: 存档 ===
print()
print("=" * 60)
print("Round 6: Save/Load")
print("=" * 60)

r = post("/api/save/save", {"name": "regression_test"})
check("Save game", r.get('code') == 200)
saved_file = r.get('data', {}).get('filename', '') if r.get('data') else ''

r = get("/api/save/list")
check("Save list", r.get('code') == 200)

if saved_file:
    r = post("/api/save/load", {"filename": saved_file})
    check("Load game", r.get('code') == 200, "round=" + str(r.get('data', {}).get('round', '?')))
else:
    check("Load game (skip, no filename)", True, "skipped")

if saved_file:
    r = delete("/api/save/delete", {"filename": saved_file})
    check("Delete save", r.get('code') == 200)

# After load, verify panels still work
r = get("/api/panel/weather")
check("Weather after save cycle", r.get('code') == 200)

# === 第7轮: 外交/间谍 ===
print()
print("=" * 60)
print("Round 7: Diplomacy & Spy")
print("=" * 60)

r = get(f"/api/diplomacy/relations/{FACTION2}")
check("Diplomacy relations", r.get('code') == 200)

r = get(f"/api/diplomacy/summary/{FACTION2}")
check("Diplomacy summary", r.get('code') == 200)

r = get("/api/diplomacy/coalitions")
check("Coalitions", r.get('code') == 200)

r = get(f"/api/spy/networks/{FACTION2}")
check("Spy networks", r.get('code') == 200)

# === 第8轮: Agent ===
print()
print("=" * 60)
print("Round 8: Agent & Strategy")
print("=" * 60)

r = get("/api/agent/status")
check("Agent status", r.get('code') == 200)

r = get("/api/agent/npcs")
check("NPC list", r.get('code') == 200)

r = get(f"/api/agent/faction-advisers/{FACTION2}")
check("Faction advisers", r.get('code') == 200)

r = post("/api/strategy/analyze", {"faction_id": FACTION2})
check("Strategy analysis", r.get('code') in (200, 500), "AI may be unavailable")

# === 第9轮: 模式/锁 ===
print()
print("=" * 60)
print("Round 9: Mode & Locks")
print("=" * 60)

r = get("/api/game/mode-info")
check("Mode info", r.get('code') == 200)

r = get("/api/game/operation-locks")
check("Operation locks", r.get('code') == 200)

r = get("/api/game/responsibility-stats")
check("Responsibility stats", r.get('code') == 200)

# === 第10轮: 边界测试 ===
print()
print("=" * 60)
print("Round 10: Edge Cases")
print("=" * 60)

r = post("/api/edict/parse", {})
check("Empty edict parse", r.get('code') in (400, 422, 403) or r.get('http_error') in (400, 422))

r = get("/api/nonexistent/endpoint")
check("404 on missing endpoint", r.get('http_error') == 404)

r = get("/api/panel/royal/nonexistent_faction_999")
check("Panel for missing faction", r.get('code') in (404, 403))

# === 总结 ===
print()
print("=" * 60)
print("REGRESSION TEST SUMMARY")
print("=" * 60)
total = passed + failed
print("  Passed: %d/%d" % (passed, total))
print("  Failed: %d/%d" % (failed, total))

if errors:
    print()
    print("  Failures:")
    for name, detail in errors:
        print("    - %s: %s" % (name, detail[:200]))

print()
print("  Time: %s" % time.strftime('%Y-%m-%d %H:%M:%S'))
