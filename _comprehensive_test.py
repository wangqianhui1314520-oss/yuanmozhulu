# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import urllib.request, urllib.error, json, time

BASE = "http://127.0.0.1:8800/api"
BUGS = []
TIMEOUT_SHORT = 30
TIMEOUT_LONG = 120

def api(method, path, body=None, timeout=TIMEOUT_SHORT):
    """发送 HTTP 请求（使用 urllib 避免 httpx 的 Windows 代理冲突）"""
    url = f"{BASE}{path}"
    try:
        data = json.dumps(body).encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            return json.loads(body)
        except:
            return {'http_error': e.code, 'body': body[:500]}
    except Exception as e:
        return {'error': str(e)}

def get(path):
    return api("GET", path)

def post(path, data=None, timeout=TIMEOUT_SHORT):
    return api("POST", path, data, timeout)

def bug(msg):
    BUGS.append(msg)
    print(f"  [BUG] {msg}")

# ============================================================
print("=" * 60)
print("1. Health Check /api/health")
r = get("/health")
h = r.get('data', {})
print(f"   Status: {r.get('code')}, Version: {h.get('version')}")
print(f"   AI available: {h.get('ai_available')}, Factions: {h.get('factions_loaded')}")
if r.get('code') != 200:
    bug("Health check failed")

# ============================================================
print("\n2. Factions Config /api/config/factions")
r = get("/config/factions")
fc = r.get('data', {}).get('factions', {})
print(f"   Factions: {len(fc)}, keys: {list(fc.keys())[:5]}")
if not fc:
    bug("No factions loaded")

# ============================================================
print("\n3. Game Status /api/game/status")
r = get("/game/status")
gs = r.get('data', {})
print(f"   Active: {gs.get('game_active')}, Round: {gs.get('current_round')}")

# ============================================================
print("\n4. Game Init /api/game/init (re-init if needed)")
need_init = not gs.get('game_active')
if need_init:
    r = post("/game/init", {"faction_id": "faction_zhuyuanzhang", "mode": "player_turn"}, timeout=60)
    code = r.get('code')
    ws = r.get('data', {}).get('world_state', {})
    print(f"   Init: code={code}")
    print(f"   Player: {r.get('data',{}).get('player_faction_id')}")
    print(f"   Factions: {len(ws.get('factions',{}))}")
    print(f"   Tiles: {len(ws.get('tiles',{}))}")
    if code != 200:
        bug(f"Game init failed: {r.get('msg')}")
else:
    print("   Game already active (skip init)")

# Use the current player faction
r = get("/game/status")
pfi = r.get('data', {}).get('player_faction_id', 'faction_zhuyuanzhang')
FID = pfi if pfi else "faction_zhuyuanzhang"
print(f"   Using faction: {FID}")

# ============================================================
print("\n5. Map Tiles /api/map/tiles")
r = get("/map/tiles")
td = r.get('data', {})
if isinstance(td, dict) and 'tiles' in td:
    tcount = len(td['tiles'])
    print(f"   Tiles: {tcount} (nested format)")
else:
    tcount = len(td) if isinstance(td, (dict, list)) else 0
    print(f"   Tiles: {tcount}")
if tcount == 0:
    bug("No map tiles loaded")

# ============================================================
print("\n6. Parse Edict /api/edict/parse")
r = post("/edict/parse", {
    "edict_text": "征兵三千，加固城防",
    "faction_id": FID
})
pd = r.get('data', {})
print(f"   Code: {r.get('code')}, AI parsed: {pd.get('ai_parsed')}")

# ============================================================
print("\n7. NL Process Edict /api/edict/nl-process (no AI)")
r = post("/edict/nl-process", {
    "edict_text": "发展农业，减轻赋税",
    "faction_id": FID,
    "direct_execute": True,
    "use_ai": False
}, timeout=60)
d = r.get('data', {})
print(f"   Code: {r.get('code')}, Commands: {d.get('commands_count', 0)}")
if r.get('code') != 200:
    bug(f"NL Process failed: {r.get('msg')}")

# ============================================================
print("\n8. Execute Edict /api/edict/execute (with AI)")
r = post("/edict/execute", {
    "edict_text": "颁行仁政，招贤纳士，安抚百姓",
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
ai = d.get('ai_analysis', {})
exe = d.get('execution', {})
gd = d.get('global_deduction', {})
print(f"   Code: {r.get('code')}")
print(f"   AI generated: {ai.get('ai_generated')}")
print(f"   Commands: {ai.get('commands_count')}")
print(f"   Executed: {exe.get('total_executed')}, Failed: {exe.get('total_failed')}")
print(f"   Global deduction: {bool(gd.get('summary') or gd.get('global_narrative'))}")
if r.get('code') != 200:
    bug(f"Edict execute failed: {r.get('msg')}")

# ============================================================
print("\n9. Tile Detail /api/map/tile")
r = get("/map/tiles")
td = r.get('data', {})
tile_keys = []
if isinstance(td, dict) and 'tiles' in td:
    tile_keys = list(td['tiles'].keys())[:1]
elif isinstance(td, dict):
    tile_keys = list(td.keys())[:1]

for tid in tile_keys:
    r = get(f"/map/tile/{tid}")
    tdi = r.get('data', {})
    print(f"   Tile {tid}: name={tdi.get('name', tdi.get('tile_name', '?'))}")

# ============================================================
print("\n10. Pathfind /api/march/path")
r = post("/march/path", {
    "from_tile": "tile_yingtian",
    "to_tile": "tile_wuchang",
    "troops": 1000
})
pd = r.get('data') or {}
plen = len(pd.get('path', []))
print(f"   Path length: {plen}, code: {r.get('code')}")

# ============================================================
print("\n11. Neighbors /api/march/neighbors")
r = get(f"/march/neighbors/tile_yingtian?faction_id={FID}")
nb = r.get('data', {}).get('neighbors', [])
print(f"   Neighbors: {len(nb)}")

# ============================================================
print("\n12. Edict Execute #2 (complex)")
r = post("/edict/execute", {
    "edict_text": "减税惠民，开仓放粮，修建粮仓加固城防",
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
ai2 = d.get('ai_analysis', {})
exe2 = d.get('execution', {})
print(f"   Code: {r.get('code')}")
print(f"   Commands: {ai2.get('commands_count')}")
print(f"   Executed: {exe2.get('total_executed')}, Failed: {exe2.get('total_failed')}")
for f_item in (exe2.get('failed') or []):
    print(f"   FAIL: {f_item.get('action', '?')} => {f_item.get('reason', '?')}")

# ============================================================
print("\n13. Advance Turn /api/game/advance-turn")
print("   Advancing turn (may take 60-90s with AI)...")
start = time.time()
r = post("/game/advance-turn", {"faction_id": FID}, timeout=TIMEOUT_LONG)
elapsed = time.time() - start
d = r.get('data', {})
ws = d.get('world_state', {})
print(f"   Code: {r.get('code')}, Time: {elapsed:.1f}s")
print(f"   Round: {ws.get('current_round')}, Year: {ws.get('current_year')}")
if r.get('code') != 200:
    bug(f"Advance turn failed: {r.get('msg')} (timeout={elapsed:.1f}s)")

# ============================================================
print("\n" + "=" * 60)
print("BUG SUMMARY")
print("=" * 60)
if BUGS:
    for i, b in enumerate(BUGS, 1):
        print(f"  {i}. {b}")
else:
    print("  No API bugs found.")

print(f"\n  Completed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
sys.exit(len(BUGS))
