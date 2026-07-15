#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
《元末逐鹿 3.0》完整玩家游玩流程测试 v2
稳健版 — 兼容各种 API 返回格式
"""

import requests
import json
import time
import sys
import os
import traceback

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://localhost:8800"
NO_PROXY = {"http": None, "https": None}
RESULTS = []
ISSUES = []

def log(step, msg, level="INFO"):
    prefix = {"INFO": "  ", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "STEP": "▶️"}
    p = prefix.get(level, "  ")
    line = f"{p} [{step}] {msg}"
    print(line)
    RESULTS.append({"step": step, "level": level, "msg": msg})

def issue(step, msg, severity="MEDIUM"):
    i = {"step": step, "severity": severity, "msg": msg}
    ISSUES.append(i)
    log(step, f"【问题】{msg}", "WARN")

def api(method, path, data=None, timeout=180):
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout, proxies=NO_PROXY)
        else:
            r = requests.post(url, json=data, timeout=timeout, proxies=NO_PROXY)
        try:
            body = r.json()
        except:
            body = {"_raw": r.text[:500]}
        return r.status_code, body
    except requests.Timeout:
        return 0, {"error": "timeout"}
    except Exception as e:
        return 0, {"error": str(e)}

def ok(status, resp):
    """检查 API 响应是否成功"""
    if status == 0:
        return False, f"网络错误: {resp.get('error','?')}"
    if status != 200:
        return False, f"HTTP {status}"
    if resp.get("code") != 200:
        return False, f"业务code={resp.get('code')}: {resp.get('msg','?')}"
    return True, "ok"

def get_data(resp):
    """安全获取 data 字段"""
    d = resp.get("data")
    if d is None:
        return {}
    if isinstance(d, dict):
        return d
    if isinstance(d, list):
        return d
    return {"_value": d}

def safe_len(obj):
    """安全获取长度"""
    if obj is None:
        return 0
    if isinstance(obj, (dict, list)):
        return len(obj)
    return 1 if obj else 0

def first_n(obj, n=5):
    """安全获取前N项"""
    if isinstance(obj, list):
        return obj[:n]
    if isinstance(obj, dict):
        return list(obj.items())[:n]
    return []

def safe_str(obj, maxlen=200):
    """安全转为字符串"""
    if obj is None:
        return "(None)"
    if isinstance(obj, str):
        return obj[:maxlen]
    try:
        s = json.dumps(obj, ensure_ascii=False)
        return s[:maxlen]
    except:
        return str(obj)[:maxlen]

# ============================================================
print("=" * 70)
print("  《元末逐鹿 3.0》玩家完整游玩流程测试 v2")
print("=" * 70)

# ============================================================
# 阶段零：前置检查
# ============================================================
log("0.1", "健康检查...")
s, r = api("GET", "/api/health")
is_ok, reason = ok(s, r)
if is_ok:
    d = get_data(r)
    log("0.1", f"版本={d.get('version','?')}, AI={'可用' if d.get('ai_available') else '不可用'}, 回合={d.get('current_round','?')}, 势力数={d.get('factions_loaded','?')}")
    if not d.get('ai_available'):
        issue("0.1", "AI不可用，将影响后续智能体功能", "HIGH")
else:
    issue("0.1", f"健康检查失败: {reason}", "HIGH")
    log("0.1", f"原始响应: {safe_str(r)}", "ERROR")

# ============================================================
# 阶段一：势力配置
# ============================================================
print("\n" + "-" * 50)
print("  一、踏入乱世：势力配置")
print("-" * 50)

log("1.1", "获取势力配置...")
s, r = api("GET", "/api/config/factions")
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    factions_dict = data.get("factions", data)
    if isinstance(factions_dict, dict):
        log("1.1", f"势力数: {len(factions_dict)}")
        for fid, f in first_n(factions_dict, 9):
            if isinstance(f, dict):
                log("1.1", f"  {f.get('name', fid)} ({fid}) 难度={f.get('difficulty','?')} 兵力={f.get('initial_troops','?')}")
    else:
        log("1.1", f"势力数据格式异常: {type(factions_dict)}")
        issue("1.1", "势力数据不是dict格式", "HIGH")
else:
    issue("1.1", f"势力配置获取失败: {reason}", "HIGH")

# ============================================================
# 阶段二：初始化游戏（选朱元璋）
# ============================================================
print("\n" + "-" * 50)
print("  二、启卷入世：选朱元璋")
print("-" * 50)

log("2.1", "初始化游戏（朱元璋·君主亲政）...")
s, r = api("POST", "/api/game/init", {
    "faction_id": "faction_zhuyuanzhang",
    "mode": "player_turn"
})
is_ok, reason = ok(s, r)
if is_ok:
    log("2.1", f"初始化成功: {r.get('msg','ok')}")
else:
    log("2.1", f"初始化失败: {reason}", "ERROR")
    # 尝试 restart
    log("2.1b", "尝试 restart...")
    s2, r2 = api("POST", "/api/game/restart", {"faction_id": "faction_zhuyuanzhang"})
    is_ok2, reason2 = ok(s2, r2)
    if is_ok2:
        log("2.1b", "restart 成功")
    else:
        log("2.1b", f"restart 也失败: {reason2}", "ERROR")
        issue("2.1", "无法初始化游戏", "HIGH")

# ============================================================
# 阶段三：初入沙盘 — 获取游戏状态
# ============================================================
print("\n" + "-" * 50)
print("  三、初入沙盘：游戏状态")
print("-" * 50)

log("3.1", "获取游戏状态...")
s, r = api("GET", "/api/game/status")
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    pf = data.get("player_faction", {})
    if pf:
        log("3.1", f"玩家: {pf.get('name','?')} | 库银={pf.get('treasury','?')} | 粮草={pf.get('food','?')} | 兵力={pf.get('troops','?')}")
        log("3.1", f"  声望={pf.get('reputation','?')} | 战马={pf.get('horses','?')} | 军械={pf.get('arms','?')}")
    else:
        issue("3.1", "player_faction 字段为空", "HIGH")
    
    # 回合信息
    ws = data.get("world_state", {})
    if isinstance(ws, dict):
        turn = ws.get("turn", ws.get("current_turn", "?"))
        log("3.1", f"当前回合: {turn}")
    
    # 外交关系
    dr = data.get("diplomatic_relations", [])
    if dr and isinstance(dr, list):
        log("3.1", f"外交关系数: {len(dr)}")
        for rel in dr[:3]:
            if isinstance(rel, dict):
                log("3.1", f"  → {rel.get('target_name','?')}: {rel.get('stance','?')}")
    
    # 地块信息
    tiles_data = data.get("tiles", data.get("territory", {}))
    if isinstance(tiles_data, dict):
        log("3.1", f"控制地块数: {len(tiles_data)}")
else:
    issue("3.1", f"游戏状态获取失败: {reason}", "HIGH")

# ============================================================
# 阶段四：下达圣旨（第1回合）
# ============================================================
print("\n" + "-" * 50)
print("  四、第1回合：下达圣旨")
print("-" * 50)

test_commands = [
    ("4.1", "征兵", "recruit", {"amount": 500}),
    ("4.2", "开发农业", "develop", {"type": "agriculture"}),
    ("4.3", "训练", "train", {"amount": 300}),
    ("4.4", "城防加固", "fortify", {}),
    ("4.5", "侦查陈友谅", "scout", {"target_faction": "faction_chenyouliang"}),
]

for step_id, desc, action, params in test_commands:
    s, r = api("POST", "/api/game/command", {
        "faction_id": "faction_zhuyuanzhang",
        "action": action,
        "params": params
    })
    is_ok, reason = ok(s, r)
    if is_ok:
        log(step_id, f"✅ {desc}({action}) → {r.get('msg','ok')}")
    else:
        issue(step_id, f"{desc}({action}) 失败: {reason}", "MEDIUM")
        log(step_id, f"  响应: {safe_str(r)}")

# ============================================================
# 阶段五：自然语言圣旨
# ============================================================
print("\n" + "-" * 50)
print("  五、自然语言圣旨（NL命令）")
print("-" * 50)

log("5.1", "NL解析: '从应天府调拨银两五百，征兵三千，加紧训练'...")
s, r = api("POST", "/api/edict/nl-process", {
    "faction_id": "faction_zhuyuanzhang",
    "text": "从应天府调拨银两五百，征兵三千，加紧训练"
})
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    log("5.1", f"NL解析结果: {safe_str(data, 300)}")
else:
    issue("5.1", f"NL解析失败: {reason}", "MEDIUM")
    log("5.1", f"  响应: {safe_str(r)}")

# ============================================================
# 阶段六：咨询谋士（A1 谋策阁）
# ============================================================
print("\n" + "-" * 50)
print("  六、咨询谋士（A1 谋策阁）")
print("-" * 50)

log("6.1", "战略建议请求...")
s, r = api("POST", "/api/agent/strategic-advice", {
    "faction_id": "faction_zhuyuanzhang",
    "query": "请分析当前局势，给出战略建议"
}, timeout=180)
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    resp_text = data.get("response", data.get("advice", data.get("content", "")))
    if resp_text:
        log("6.1", f"谋士建议: {safe_str(resp_text, 300)}")
    else:
        issue("6.1", f"谋士回复为空，完整数据: {safe_str(data)}", "MEDIUM")
else:
    issue("6.1", f"谋士咨询失败: {reason}", "MEDIUM")

log("6.2", "谋士自由对话...")
s, r = api("POST", "/api/agent/chat", {
    "faction_id": "faction_zhuyuanzhang",
    "message": "刘基先生，请问我军当前最需要加强的是什么？"
}, timeout=180)
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    resp_text = data.get("response", data.get("reply", data.get("content", "")))
    log("6.2", f"刘基回复: {safe_str(resp_text, 200)}")
    if not resp_text:
        issue("6.2", "自由对话回复为空", "MEDIUM")
else:
    issue("6.2", f"自由对话失败: {reason}", "MEDIUM")

# ============================================================
# 阶段七：推进第1回合
# ============================================================
print("\n" + "-" * 50)
print("  七、推进第1回合（8阶段自动执行）")
print("-" * 50)

log("7.1", "推进回合...")
t0 = time.time()
s, r = api("POST", "/api/game/advance-turn", {}, timeout=300)
elapsed = time.time() - t0
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    new_round = data.get("new_round", data.get("current_round", "?"))
    log("7.1", f"✅ 回合推进成功 → 第{new_round}回合 (耗时 {elapsed:.1f}s)")
    
    # 检查事件
    events = data.get("events", data.get("new_events", []))
    if isinstance(events, list) and events:
        log("7.1", f"  本回合事件({len(events)}条):")
        for evt in events[:5]:
            if isinstance(evt, dict):
                log("7.1", f"    - {safe_str(evt.get('title', evt.get('text', str(evt))), 120)}")
    elif isinstance(events, list) and not events:
        issue("7.1", "推进回合后事件列表为空", "MEDIUM")
    
    # 检查结算信息
    settle = data.get("settlement", {})
    if settle and isinstance(settle, dict):
        log("7.1", f"  税收={settle.get('tax_income','?')} | 粮耗={settle.get('food_consumption','?')}")
    
    # 检查 AI 行动
    ai_actions = data.get("ai_actions", data.get("npc_actions", []))
    log("7.1", f"  其他势力行动数: {safe_len(ai_actions)}")
    
    # 检查 narrative
    narrative = data.get("narrative", "")
    if narrative:
        log("7.1", f"  回合叙事: {safe_str(narrative, 200)}")
    
    if elapsed > 120:
        issue("7.1", f"回合推进耗时过长: {elapsed:.1f}s", "LOW")
else:
    issue("7.1", f"回合推进失败: {reason}", "HIGH")
    log("7.1", f"  响应: {safe_str(r, 500)}")

# ============================================================
# 阶段八：第2回合 — 军事+外交
# ============================================================
print("\n" + "-" * 50)
print("  八、第2回合：军事+外交操作")
print("-" * 50)

log("8.0", "获取当前状态...")
s, r = api("GET", "/api/game/status")
is_ok, reason = ok(s, r)
if is_ok:
    pf = get_data(r).get("player_faction", {})
    log("8.0", f"当前: 库银={pf.get('treasury','?')} | 兵力={pf.get('troops','?')} | 战马={pf.get('horses','?')}")

military = [
    ("8.1", "买马", "buy_horses", {"amount": 100}),
    ("8.2", "巡查", "patrol", {}),
    ("8.3", "练兵", "train_troops", {"amount": 500}),
]
for step_id, desc, action, params in military:
    s, r = api("POST", "/api/game/command", {
        "faction_id": "faction_zhuyuanzhang",
        "action": action,
        "params": params
    })
    is_ok, reason = ok(s, r)
    if is_ok:
        log(step_id, f"✅ {desc} → ok")
    else:
        issue(step_id, f"{desc}({action}) 失败: {reason}", "MEDIUM")

log("8.4", "外交 — 向张士诚通商...")
s, r = api("POST", "/api/game/command", {
    "faction_id": "faction_zhuyuanzhang",
    "action": "trade",
    "params": {"target_faction": "faction_zhangshicheng"}
})
is_ok, reason = ok(s, r)
log("8.4", f"通商 → {reason} | {safe_str(r.get('msg',''))}")

log("8.5", "外交 — 向明玉珍求盟...")
s, r = api("POST", "/api/game/command", {
    "faction_id": "faction_zhuyuanzhang",
    "action": "alliance",
    "params": {"target_faction": "faction_mingyuzhen"}
})
is_ok, reason = ok(s, r)
log("8.5", f"同盟 → {reason} | {safe_str(r.get('msg',''))}")

# 推进第2回合
log("8.6", "推进第2回合...")
t0 = time.time()
s, r = api("POST", "/api/game/advance-turn", {}, timeout=300)
elapsed = time.time() - t0
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    log("8.6", f"✅ 第{data.get('new_round',data.get('current_round','?'))}回合 (耗时 {elapsed:.1f}s)")
    events = data.get("events", data.get("new_events", []))
    if isinstance(events, list) and events:
        log("8.6", f"  事件({len(events)}条): {safe_str(events[0].get('title','') if isinstance(events[0],dict) else events[0], 100)}")
else:
    issue("8.6", f"第2回合推进失败: {reason}", "HIGH")

# ============================================================
# 阶段九：第3回合 — 谍报+建造
# ============================================================
print("\n" + "-" * 50)
print("  九、第3回合：谍报+建造")
print("-" * 50)

log("9.1", "部署细作到陈友谅...")
s, r = api("POST", "/api/spy/deploy", {
    "faction_id": "faction_zhuyuanzhang",
    "target_faction": "faction_chenyouliang"
})
is_ok, reason = ok(s, r)
if is_ok:
    log("9.1", f"✅ 细作部署成功: {r.get('msg','ok')}")
else:
    issue("9.1", f"细作部署失败: {reason}", "MEDIUM")

log("9.2", "建造粮仓...")
s, r = api("POST", "/api/building/construct", {
    "faction_id": "faction_zhuyuanzhang",
    "building_type": "granary"
})
is_ok, reason = ok(s, r)
log("9.2", f"建造 → {reason} | {safe_str(r.get('msg',''))}")

log("9.3", "获取地图数据...")
s, r = api("GET", "/api/map/tiles")
is_ok, reason = ok(s, r)
if is_ok:
    tiles = get_data(r)
    log("9.3", f"地图格数: {safe_len(tiles)}")
else:
    issue("9.3", f"地图获取失败: {reason}", "MEDIUM")

# 推进第3回合
log("9.4", "推进第3回合...")
s, r = api("POST", "/api/game/advance-turn", {}, timeout=300)
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    log("9.4", f"✅ 第{data.get('new_round',data.get('current_round','?'))}回合 (耗时 {time.time()-t0:.1f}s)")
else:
    issue("9.4", f"第3回合推进失败: {reason}", "HIGH")

# ============================================================
# 阶段十：存档测试
# ============================================================
print("\n" + "-" * 50)
print("  十、存档测试")
print("-" * 50)

log("10.1", "快速存档...")
s, r = api("POST", "/api/save/quick-save", {})
is_ok, reason = ok(s, r)
if is_ok:
    log("10.1", f"✅ 快速存档: {r.get('msg','ok')}")
else:
    issue("10.1", f"快速存档失败: {reason}", "MEDIUM")

log("10.2", "存档列表...")
s, r = api("GET", "/api/save/list")
is_ok, reason = ok(s, r)
if is_ok:
    saves = get_data(r)
    log("10.2", f"存档数: {safe_len(saves)}")
    for item in first_n(saves, 3):
        if isinstance(item, dict):
            log("10.2", f"  {item.get('name','?')} | 回合{item.get('round','?')}")
        elif isinstance(item, tuple):
            log("10.2", f"  {item[0]}: {safe_str(item[1])}")
else:
    issue("10.2", f"存档列表获取失败: {reason}", "MEDIUM")

log("10.3", "手动存档到槽位1...")
s, r = api("POST", "/api/save/save", {"slot": 1, "label": "玩家测试-第3回合"})
is_ok, reason = ok(s, r)
log("10.3", f"手动存档 → {reason}")

# ============================================================
# 阶段十一：连续推进回合
# ============================================================
print("\n" + "-" * 50)
print("  十一、连续推进回合（测试AI世界运转）")
print("-" * 50)

for turn_num in range(4, 8):
    step_id = f"11.{turn_num-3}"
    log(step_id, f"推进第{turn_num}回合...")
    s, r = api("POST", "/api/game/advance-turn", {}, timeout=300)
    is_ok, reason = ok(s, r)
    if is_ok:
        data = get_data(r)
        nr = data.get("new_round", data.get("current_round", "?"))
        log(step_id, f"✅ 第{nr}回合")
        events = data.get("events", data.get("new_events", []))
        if isinstance(events, list) and events:
            evt0 = events[0]
            if isinstance(evt0, dict):
                log(step_id, f"  事件: {safe_str(evt0.get('title', str(evt0)), 100)}")
    else:
        issue(step_id, f"第{turn_num}回合推进失败: {reason}", "HIGH")
        log(step_id, f"  响应: {safe_str(r, 300)}")
        break

# ============================================================
# 阶段十二：面板数据检查
# ============================================================
print("\n" + "-" * 50)
print("  十二、面板数据检查")
print("-" * 50)

panels = [
    ("12.1", "皇家宗室", "/api/panel/royal/faction_zhuyuanzhang"),
    ("12.2", "朝堂总览", "/api/court/overview/faction_zhuyuanzhang"),
    ("12.3", "国策", "/api/policy/active/faction_zhuyuanzhang"),
    ("12.4", "武将", "/api/generals/faction_zhuyuanzhang"),
    ("12.5", "战争状态", "/api/war/status"),
    ("12.6", "活跃战争", "/api/war/active"),
    ("12.7", "结局进度", "/api/game/endings/progress"),
    ("12.8", "外交摘要", "/api/diplomacy/summary/faction_zhuyuanzhang"),
]

for step_id, name, path in panels:
    s, r = api("GET", path)
    is_ok, reason = ok(s, r)
    if is_ok:
        data = get_data(r)
        log(step_id, f"{name}: {safe_str(data, 150)}")
    else:
        issue(step_id, f"{name} 获取失败: {reason}", "LOW")

# ============================================================
# 阶段十三：最终状态汇总
# ============================================================
print("\n" + "-" * 50)
print("  十三、最终状态汇总")
print("-" * 50)

log("13.1", "获取最终游戏状态...")
s, r = api("GET", "/api/game/status")
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    pf = data.get("player_faction", {})
    log("13.1", f"势力: {pf.get('name','?')}")
    log("13.1", f"库银={pf.get('treasury','?')} | 粮草={pf.get('food','?')} | 兵力={pf.get('troops','?')}")
    log("13.1", f"声望={pf.get('reputation','?')} | 民心={pf.get('popularity','?')}")
    log("13.1", f"战马={pf.get('horses','?')} | 军械={pf.get('arms','?')}")
    ws = data.get("world_state", {})
    if isinstance(ws, dict):
        log("13.1", f"当前回合: {ws.get('turn', ws.get('current_turn', '?'))}")

log("13.2", "结局检查...")
s, r = api("GET", "/api/game/ending")
is_ok, reason = ok(s, r)
if is_ok:
    data = get_data(r)
    log("13.2", f"结局状态: {safe_str(data, 200)}")

log("13.3", "最终健康检查...")
s, r = api("GET", "/api/health")
is_ok, reason = ok(s, r)
if is_ok:
    d = get_data(r)
    log("13.3", f"AI={'可用' if d.get('ai_available') else '不可用'}, 回合={d.get('current_round','?')}, Token消耗={d.get('token_stats',{}).get('total_tokens_consumed','?')}")

# ============================================================
# 问题汇总
# ============================================================
print("\n" + "=" * 70)
print("  游玩问题汇总")
print("=" * 70)

if not ISSUES:
    print("  🎉 未发现明显问题！")
else:
    high = [i for i in ISSUES if i["severity"] == "HIGH"]
    medium = [i for i in ISSUES if i["severity"] == "MEDIUM"]
    low = [i for i in ISSUES if i["severity"] == "LOW"]
    
    if high:
        print(f"\n  🔴 严重问题: {len(high)} 项")
        for i, item in enumerate(high):
            print(f"    {i+1}. [{item['step']}] {item['msg']}")
    
    if medium:
        print(f"\n  🟡 中等问题: {len(medium)} 项")
        for i, item in enumerate(medium):
            print(f"    {i+1}. [{item['step']}] {item['msg']}")
    
    if low:
        print(f"\n  🟢 轻微问题: {len(low)} 项")
        for i, item in enumerate(low):
            print(f"    {i+1}. [{item['step']}] {item['msg']}")

print(f"\n总计: {len(ISSUES)} 个问题 ({len(high)}严重 / {len(medium)}中等 / {len(low)}轻微)")

# 保存结果
with open("_player_journey_result.json", "w", encoding="utf-8") as f:
    json.dump({
        "results": RESULTS,
        "issues": ISSUES,
        "total_steps": len(RESULTS),
        "total_issues": len(ISSUES),
    }, f, ensure_ascii=False, indent=2)

print(f"\n详细结果已保存到 _player_journey_result.json")
