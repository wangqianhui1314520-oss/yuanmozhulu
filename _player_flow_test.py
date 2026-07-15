# -*- coding: utf-8 -*-
"""《元末逐鹿 3.0》— 玩家完整游玩流程测试
按照文档描述的完整流程走一遍，记录所有问题
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import urllib.request, urllib.error, json, time, os

BASE = "http://127.0.0.1:8800/api"
ISSUES = []  # 记录所有问题
TIMEOUT_SHORT = 30
TIMEOUT_MED = 60
TIMEOUT_LONG = 120
TIMEOUT_XL = 180

def api(method, path, body=None, timeout=TIMEOUT_SHORT):
    url = f"{BASE}{path}"
    try:
        data = json.dumps(body).encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')
        try:
            return json.loads(body_text)
        except:
            return {'http_error': e.code, 'body': body_text[:500]}
    except Exception as e:
        return {'error': str(e)}

def get(path):
    return api("GET", path)

def post(path, data=None, timeout=TIMEOUT_SHORT):
    return api("POST", path, data, timeout)

def issue(msg):
    ISSUES.append(msg)
    print(f"  >>> 问题: {msg}")

def check(msg, condition):
    if condition:
        print(f"  [OK] {msg}")
    else:
        issue(msg)

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# 一、踏入乱世：启卷入世
# ============================================================
separator("一、踏入乱世：启卷入世")

# 1.1 首页/健康检查
print("\n1.1 打开游戏首页 - 健康检查")
r = get("/health")
h = r.get('data', {})
print(f"    服务器状态: {h.get('status')}")
print(f"    版本: {h.get('version')}")
print(f"    AI可用: {h.get('ai_available')}")
print(f"    势力数: {h.get('factions_loaded')}")
print(f"    当前回合: {h.get('current_round')}")
check("服务器在线且健康", r.get('code') == 200 and h.get('status') == 'ok')
check("AI服务可用", h.get('ai_available') == True)
check("势力加载正确 (9个)", h.get('factions_loaded') == 9)

# 1.2 查看势力列表
print("\n1.2 查看势力选择页 - 获取势力配置")
r = get("/config/factions")
fc = r.get('data', {}).get('factions', {})
print(f"    势力数量: {len(fc)}")
for fid, finfo in fc.items():
    if isinstance(finfo, dict):
        name = finfo.get('name', fid)
        diff = finfo.get('difficulty', '?')
        print(f"      {name} (难度: {diff})")
check("势力配置加载成功", len(fc) > 0)

# 检查是否有难度信息
has_difficulty = any(
    isinstance(v, dict) and 'difficulty' in v 
    for v in fc.values()
)
if not has_difficulty:
    issue("势力数据缺少难度(difficulty)字段，文档中描述的难度分级可能未实现")

# 1.3 初始化游戏 - 选择朱元璋
print("\n1.3 选择朱元璋（普通难度）- 初始化游戏")
r = post("/game/init", {
    "faction_id": "faction_zhuyuanzhang",
    "mode": "player_turn"
}, timeout=TIMEOUT_MED)
code = r.get('code')
init_data = r.get('data', {})
ws = init_data.get('world_state', {})
print(f"    初始化结果: code={code}")
print(f"    玩家势力: {init_data.get('player_faction_id')}")
print(f"    势力数: {len(ws.get('factions', {}))}")
print(f"    地块数: {len(ws.get('tiles', {}))}")
print(f"    初始回合: {ws.get('current_round')}")
print(f"    当前年份: {ws.get('current_year')}")
check("游戏初始化成功", code == 200)

FID = init_data.get('player_faction_id', 'faction_zhuyuanzhang')

# 检查玩家势力详情
player_faction = ws.get('factions', {}).get(FID, {})
if player_faction:
    print(f"    势力名称: {player_faction.get('name', '?')}")
    print(f"    库银: {player_faction.get('silver', '?')}")
    print(f"    粮草: {player_faction.get('grain', '?')}")
    print(f"    兵力: {player_faction.get('troops', '?')}")
    print(f"    声望: {player_faction.get('prestige', '?')}")
    print(f"    领地数: {len(player_faction.get('tiles', []))}")
    check("玩家势力数据完整", bool(player_faction.get('name') and player_faction.get('silver') is not None))

# 检查模式
print(f"    模式: {init_data.get('mode', '?')}")
if init_data.get('mode') != 'player_turn':
    issue("模式不是 player_turn（玩家手动控制模式）")

# ============================================================
# 二、初入沙盘：第一印象
# ============================================================
separator("二、初入沙盘：第一印象")

# 2.1 获取游戏状态
print("\n2.1 查看主界面状态")
r = get("/game/status")
gs = r.get('data', {})
print(f"    游戏活跃: {gs.get('game_active')}")
print(f"    当前回合: {gs.get('current_round')}")
print(f"    玩家势力: {gs.get('player_faction_id')}")
# 查看资源
pf = gs.get('world_state', {}).get('factions', {}).get(FID, {})
resources = {
    '库银': pf.get('silver'),
    '粮草': pf.get('grain'),
    '声望': pf.get('prestige'),
    '兵力': pf.get('troops'),
    '战马': pf.get('horses'),
    '军械': pf.get('armaments'),
    '民心': pf.get('popular_support'),
    '朝纲': pf.get('court_stability'),
}
for k, v in resources.items():
    status = "✓" if v is not None else "✗ 缺失"
    print(f"    {k}: {v} {status}")
    if v is None:
        issue(f"核心资源 {k} 缺失")

# 2.2 查看地图
print("\n2.2 查看六边形沙盘舆图")
r = get("/map/tiles")
td = r.get('data', {})
if isinstance(td, dict) and 'tiles' in td:
    tcount = len(td['tiles'])
    print(f"    地块总数: {tcount}")
    # 统计玩家领地
    player_tiles = sum(
        1 for t in td['tiles'].values()
        if isinstance(t, dict) and t.get('owner') == FID
    )
    print(f"    我的领地: {player_tiles} 块")
elif isinstance(td, dict):
    tcount = len(td)
    print(f"    地块总数: {tcount}")
else:
    tcount = 0
    issue("地图数据格式异常")
check("地图数据加载成功", tcount > 0)

# 2.3 查看具体地块
print("\n2.3 点击查看应天府地块详情")
r = get("/map/tile/tile_yingtian")
tdi = r.get('data', {})
if tdi:
    print(f"    地块名: {tdi.get('name', tdi.get('tile_name', '?'))}")
    print(f"    人口: {tdi.get('population', '?')}")
    print(f"    兵力: {tdi.get('garrison', '?')}")
    print(f"    城防: {tdi.get('defense', '?')}")
    print(f"    归属: {tdi.get('owner', '?')}")
    print(f"    建筑: {tdi.get('buildings', '?')}")
    check("地块详情加载成功", bool(tdi.get('name') or tdi.get('tile_name')))
else:
    issue("无法获取应天府地块详情")

# 2.4 查看地块邻居
print("\n2.4 查看应天府周边")
r = get(f"/march/neighbors/tile_yingtian?faction_id={FID}")
nb = r.get('data', {}).get('neighbors', [])
print(f"    邻居地块数: {len(nb)}")
for n in nb[:5]:
    if isinstance(n, dict):
        print(f"      -> {n.get('tile_id', '?')} ({n.get('name', '?')})")

# ============================================================
# 三、回合循环：我的每日朝政
# ============================================================
separator("三、回合循环：下达圣旨")

# 3.1 下达第一条圣旨
print("\n3.1 圣旨①: '从应天府调拨银两五百，征兵三千，加紧训练'")
r = post("/edict/execute", {
    "edict_text": "从应天府调拨银两五百，征兵三千，加紧训练",
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
ai = d.get('ai_analysis', {})
exe = d.get('execution', {})
print(f"    AI生成: {ai.get('ai_generated')}")
print(f"    指令数: {ai.get('commands_count', 0)}")
print(f"    执行成功: {exe.get('total_executed', 0)}")
print(f"    执行失败: {exe.get('total_failed', 0)}")
if ai.get('commands'):
    for cmd in ai.get('commands', [])[:5]:
        print(f"      -> {cmd}")
check("圣旨解析成功", r.get('code') == 200)

# 检查失败的指令
failed = exe.get('failed', [])
if failed:
    for f_item in failed:
        print(f"      失败: {f_item.get('action')} - {f_item.get('reason')}")
        issue(f"圣旨指令执行失败: {f_item.get('action')} -> {f_item.get('reason')}")

# 3.2 圣旨②: 发展农业
print("\n3.2 圣旨②: '发展农业，减轻赋税，开仓赈济百姓'")
r = post("/edict/execute", {
    "edict_text": "发展农业，减轻赋税，开仓赈济百姓",
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
ai = d.get('ai_analysis', {})
exe = d.get('execution', {})
print(f"    AI生成: {ai.get('ai_generated')}")
print(f"    指令数: {ai.get('commands_count', 0)}")
print(f"    执行成功: {exe.get('total_executed', 0)}")
print(f"    执行失败: {exe.get('total_failed', 0)}")
if exe.get('results'):
    for r_item in exe.get('results', [])[:5]:
        print(f"      -> {r_item}")
failed = exe.get('failed', [])
if failed:
    for f_item in failed:
        print(f"      失败: {f_item.get('action')} - {f_item.get('reason')}")
        issue(f"圣旨指令执行失败: {f_item.get('action')} -> {f_item.get('reason')}")
check("第二条圣旨解析成功", r.get('code') == 200)

# 3.3 圣旨③: 军事行动
print("\n3.3 圣旨③: '加固应天府城防，建造军械所，侦查周边'")
r = post("/edict/execute", {
    "edict_text": "加固应天府城防，建造军械所，侦查周边",
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
ai = d.get('ai_analysis', {})
exe = d.get('execution', {})
print(f"    AI生成: {ai.get('ai_generated')}")
print(f"    指令数: {ai.get('commands_count', 0)}")
print(f"    执行成功: {exe.get('total_executed', 0)}")
print(f"    执行失败: {exe.get('total_failed', 0)}")
failed = exe.get('failed', [])
if failed:
    for f_item in failed:
        print(f"      失败: {f_item.get('action')} - {f_item.get('reason')}")
        issue(f"圣旨指令执行失败: {f_item.get('action')} -> {f_item.get('reason')}")
check("第三条圣旨解析成功", r.get('code') == 200)

# ============================================================
# 3.4 咨询谋士 (可选)
# ============================================================
separator("四、咨询谋士（A1 谋策阁）")

# 4.1 战略咨询
print("\n4.1 请求战略分析 (strategic-advice)")
r = post("/agent/strategic-advice", {
    "faction_id": FID
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
print(f"    code: {r.get('code')}")
advice_text = d.get('advice') or d.get('analysis') or d.get('content') or ''
if advice_text:
    print(f"    谋士建议: {str(advice_text)[:200]}...")
    check("战略建议获取成功", True)
else:
    print(f"    返回数据: {list(d.keys()) if isinstance(d, dict) else type(d)}")
    issue("战略建议返回为空或格式异常")

# 4.2 自由对话
print("\n4.2 自由对话 (chat)")
r = post("/agent/chat", {
    "faction_id": FID,
    "message": "刘基先生，我军当前形势如何？下一步当如何谋划？"
}, timeout=TIMEOUT_LONG)
d = r.get('data', {})
print(f"    code: {r.get('code')}")
reply = d.get('reply') or d.get('response') or d.get('content') or ''
if reply:
    print(f"    谋士回复: {str(reply)[:200]}...")
    check("谋士对话成功", True)
else:
    print(f"    返回数据keys: {list(d.keys()) if isinstance(d, dict) else type(d)}")
    issue("谋士对话返回为空或格式异常")

# 4.3 查看AI智能体状态
print("\n4.3 查看智能体仪表盘")
r = get("/agent/dashboard")
d = r.get('data', {})
print(f"    code: {r.get('code')}")
agents = d.get('agents') or d.get('agent_status') or d
if isinstance(agents, dict):
    for aname, astatus in agents.items():
        if isinstance(astatus, dict):
            print(f"      {aname}: {astatus.get('status', '?')}")
        else:
            print(f"      {aname}: {astatus}")
else:
    print(f"    返回: {str(d)[:200]}")

# ============================================================
# 五、推进回合
# ============================================================
separator("五、推进回合（8阶段自动执行）")

print("\n5.1 记录推进前状态")
r = get("/game/status")
gs = r.get('data', {})
ws_before = gs.get('world_state', {})
round_before = ws_before.get('current_round', 0)
player_before = ws_before.get('factions', {}).get(FID, {})
print(f"    推进前回合: {round_before}")
print(f"    推进前兵力: {player_before.get('troops')}")
print(f"    推进前银两: {player_before.get('silver')}")

print("\n5.2 点击'空过回合' - POST /api/game/advance-turn")
print("    (此操作会触发8阶段执行，可能需要60-120秒)...")
start = time.time()
r = post("/game/advance-turn", {"faction_id": FID}, timeout=TIMEOUT_XL)
elapsed = time.time() - start
print(f"    耗时: {elapsed:.1f}s")

d = r.get('data', {})
ws = d.get('world_state', {})
round_after = ws.get('current_round', 0)
player_after = ws.get('factions', {}).get(FID, {})
print(f"    code: {r.get('code')}")
print(f"    推进后回合: {round_after}")
print(f"    推进后兵力: {player_after.get('troops')}")
print(f"    推进后银两: {player_after.get('silver')}")

check("回合推进成功", r.get('code') == 200)
check("回合数增加", round_after > round_before)

# 查看回合结果中的事件
events = d.get('events') or ws.get('events') or []
if events:
    print(f"    本回合事件数: {len(events)}")
    for evt in events[:5]:
        if isinstance(evt, dict):
            print(f"      - {evt.get('type', '?')}: {str(evt.get('description', evt.get('narrative', '')))[:100]}")
        else:
            print(f"      - {str(evt)[:100]}")

# 检查全局推演
gd = d.get('global_deduction', {})
if gd:
    print(f"    全局推演: {str(gd.get('summary', gd.get('narrative', '')))[:200]}")

# 查看其他势力变化
print("\n5.3 查看其他势力状态变化")
for fid, finfo in ws.get('factions', {}).items():
    if fid != FID and isinstance(finfo, dict):
        name = finfo.get('name', fid)
        troops = finfo.get('troops', '?')
        tiles_count = len(finfo.get('tiles', []))
        print(f"    {name}: 兵力={troops}, 领地={tiles_count}")

# 检查是否有外交事件
print("\n5.4 查看外交状态")
diplo = d.get('diplomacy') or ws.get('diplomacy') or {}
if diplo:
    print(f"    外交数据: {str(diplo)[:300]}")
else:
    print("    无独立外交数据返回")

# ============================================================
# 六、多回合游玩
# ============================================================
separator("六、多回合连续游玩")

for turn_num in range(2, 5):
    print(f"\n--- 第 {turn_num} 回合 ---")
    
    # 下圣旨
    edicts = [
        "征兵两千，发展农业",
        "派遣细作潜入陈友谅地盘，训练士兵",
        "加固城防，建造粮仓",
    ]
    edict = edicts[turn_num - 2] if turn_num - 2 < len(edicts) else "征兵一千，发展经济"
    
    print(f"  圣旨: '{edict}'")
    r = post("/edict/execute", {
        "edict_text": edict,
        "faction_id": FID
    }, timeout=TIMEOUT_LONG)
    d = r.get('data', {})
    exe = d.get('execution', {})
    print(f"    指令: {d.get('ai_analysis', {}).get('commands_count', 0)}, 成功: {exe.get('total_executed', 0)}, 失败: {exe.get('total_failed', 0)}")
    failed = exe.get('failed', [])
    if failed:
        for f_item in failed:
            print(f"      失败: {f_item.get('action')} - {f_item.get('reason')}")
            issue(f"回合{turn_num}圣旨执行失败: {f_item.get('action')} -> {f_item.get('reason')}")
    
    # 推进回合
    print(f"  推进回合...")
    r = post("/game/advance-turn", {"faction_id": FID}, timeout=TIMEOUT_XL)
    d = r.get('data', {})
    ws = d.get('world_state', {})
    player = ws.get('factions', {}).get(FID, {})
    print(f"    回合 {ws.get('current_round')}: 兵力={player.get('troops')}, 银两={player.get('silver')}")
    
    if r.get('code') != 200:
        issue(f"回合{turn_num}推进失败: {r.get('msg')}")

# ============================================================
# 七、存档测试
# ============================================================
separator("七、存档系统")

print("\n7.1 手动存档")
r = post("/save/save", {
    "slot": "player_test_slot",
    "label": "玩家流程测试存档"
})
print(f"    code: {r.get('code')}")
print(f"    消息: {r.get('msg')}")
check("手动存档成功", r.get('code') == 200)

print("\n7.2 查看存档列表")
r = get("/save/list")
slots = r.get('data', {}).get('slots', [])
print(f"    存档数: {len(slots)}")
for s in slots:
    if isinstance(s, dict):
        print(f"      {s.get('slot', '?')}: {s.get('label', '?')} (回合{s.get('round', '?')})")

print("\n7.3 快速存档")
r = post("/save/quicksave", {})
print(f"    code: {r.get('code')}, msg: {r.get('msg')}")

# ============================================================
# 八、总结
# ============================================================
separator("游玩总结")

print(f"\n共发现 {len(ISSUES)} 个问题:")
if ISSUES:
    for i, iss in enumerate(ISSUES, 1):
        print(f"  {i}. {iss}")
else:
    print("  未发现明显问题")

# 打印最终游戏状态
print(f"\n最终游戏状态:")
r = get("/game/status")
gs = r.get('data', {})
ws = gs.get('world_state', {})
print(f"  回合: {ws.get('current_round')}")
print(f"  年份: {ws.get('current_year')}")
pf = ws.get('factions', {}).get(FID, {})
print(f"  兵力: {pf.get('troops')}")
print(f"  银两: {pf.get('silver')}")
print(f"  粮草: {pf.get('grain')}")
print(f"  声望: {pf.get('prestige')}")
print(f"  领地: {len(pf.get('tiles', []))}")

print(f"\n完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"退出码: {len(ISSUES)}")
