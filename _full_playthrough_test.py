"""
全势力游玩测试脚本 v2
按照 docs/九大势力完整游玩方案.md 的顺序，逐一测试9个势力
修复: 使用正确的 command API 格式 (action + params + faction_id)
"""
import requests
import json
import time
import traceback
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ["no_proxy"] = "localhost,127.0.0.1"

BASE_URL = "http://localhost:8800"
TIMEOUT = 300
NO_PROXY = {"http": None, "https": None}

FACTIONS = [
    {"id": "faction_zhuyuanzhang", "name": "朱元璋", "difficulty": "普通"},
    {"id": "faction_zhangshicheng", "name": "张士诚", "difficulty": "简单"},
    {"id": "faction_mingyuzhen", "name": "明玉珍", "difficulty": "简单"},
    {"id": "faction_fangguozhen", "name": "方国珍", "difficulty": "中等"},
    {"id": "faction_wangbaobao", "name": "王保保", "difficulty": "中等"},
    {"id": "faction_chenyouliang", "name": "陈友谅", "difficulty": "困难"},
    {"id": "faction_xushouhui", "name": "徐寿辉", "difficulty": "困难"},
    {"id": "faction_mobei", "name": "漠北诸部", "difficulty": "困难"},
    {"id": "faction_yuan", "name": "元廷", "difficulty": "地狱"},
]

# 每个势力的测试操作: (action, params)
FACTION_ACTIONS = {
    "faction_zhuyuanzhang": [
        ("develop", {"tile_id": "应天府", "amount": 500}),
        ("recruit", {"amount": 2000}),
        ("train_troops", {"tile_id": "应天府"}),
        ("tax", {}),
        ("scout", {"target_faction": "faction_chenyouliang"}),
    ],
    "faction_zhangshicheng": [
        ("trade", {"tile_id": "杭州"}),
        ("develop", {"tile_id": "平江", "amount": 500}),
        ("tax", {}),
        ("recruit", {"amount": 1500}),
        ("scout", {"target_faction": "faction_zhuyuanzhang"}),
    ],
    "faction_mingyuzhen": [
        ("develop", {"tile_id": "成都", "amount": 500}),
        ("fortify", {"tile_id": "夔州"}),
        ("recruit", {"amount": 2000}),
        ("relief", {}),
    ],
    "faction_fangguozhen": [
        ("trade", {}),
        ("scout", {"target_faction": "faction_zhangshicheng"}),
        ("fortify", {"tile_id": "庆元"}),
        ("recruit", {"amount": 1000}),
        ("diplomacy", {"target_faction": "faction_zhangshicheng", "type": "improve"}),
    ],
    "faction_wangbaobao": [
        ("recruit", {"amount": 2000}),
        ("buy_horses", {"amount": 100}),
        ("train_troops", {"tile_id": "太原"}),
        ("scout", {"target_faction": "faction_xushouhui"}),
        ("fortify", {"tile_id": "太原"}),
    ],
    "faction_chenyouliang": [
        ("recruit", {"amount": 3000}),
        ("train_troops", {"tile_id": "武昌"}),
        ("scout", {"target_faction": "faction_zhuyuanzhang"}),
        ("relief", {"tile_id": "武昌"}),
        ("fortify", {"tile_id": "江州"}),
    ],
    "faction_xushouhui": [
        ("recruit", {"amount": 3000}),
        ("develop", {"tile_id": "襄阳", "amount": 500}),
        ("train_troops", {"tile_id": "襄阳"}),
        ("fortify", {"tile_id": "襄阳"}),
        ("scout", {"target_faction": "faction_chenyouliang"}),
    ],
    "faction_mobei": [
        ("raid", {"target_tile": "元廷边境"}),
        ("recruit", {"amount": 1000}),
        ("train", {"type": "骑兵"}),
        ("buy_horses", {"amount": 100}),
        ("scout", {"target_faction": "faction_wangbaobao"}),
    ],
    "faction_yuan": [
        ("recruit", {"amount": 3000}),
        ("relief", {"tile_id": "大都"}),
        ("tax", {}),
        ("scout", {"target_faction": "faction_xushouhui"}),
        ("purge", {}),
    ],
}


def call(method, path, data=None):
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=TIMEOUT, proxies=NO_PROXY)
        else:
            r = requests.post(url, json=data, timeout=TIMEOUT, proxies=NO_PROXY)
        try:
            return r.status_code, r.json(), None
        except json.JSONDecodeError:
            return r.status_code, None, f"JSON解析失败: {r.text[:200]}"
    except requests.Timeout:
        return 0, None, "请求超时"
    except requests.ConnectionError:
        return 0, None, "连接失败"
    except Exception as e:
        return 0, None, str(e)


def test_faction(faction):
    fid = faction["id"]
    name = faction["name"]
    difficulty = faction["difficulty"]
    problems = []

    print(f"\n{'='*60}")
    print(f"  测试势力: {name} ({difficulty}) - {fid}")
    print(f"{'='*60}")

    # 1. 初始化
    print(f"  [1] 初始化游戏...")
    t0 = time.time()
    code, data, err = call("POST", "/api/game/init", {"faction_id": fid, "mode": "player_turn"})
    t1 = time.time()
    if err:
        problems.append(f"🔴 初始化失败: {err}")
        return problems
    if code != 200 or (data and data.get("code") != 200):
        problems.append(f"🔴 初始化失败: code={code}, resp={str(data)[:200]}")
        return problems
    print(f"      初始化成功 ({t1-t0:.1f}s)")

    result = data.get("data", {}) if data else {}
    ws = result.get("world_state", {})
    factions = ws.get("factions", {})
    if fid in factions:
        pf = factions[fid]
        print(f"      势力: {pf.get('name','?')}, 银两={pf.get('treasury','?')}, 兵力={pf.get('total_troops','?')}")
    else:
        problems.append(f"🔴 玩家势力{fid}不在factions中")

    tiles = ws.get("tiles", {})
    player_tiles = [k for k, v in tiles.items() if v.get("faction_id") == fid]
    print(f"      地块数: {len(player_tiles)}")

    # 2. 获取状态
    print(f"  [2] 获取游戏状态...")
    code, data, err = call("GET", "/api/game/status")
    if err or code != 200:
        problems.append(f"🔴 获取状态失败: {err or code}")
    else:
        d = data.get("data", {})
        print(f"      当前回合: {d.get('current_round','?')}")
        pf = d.get("player_faction", {})
        if pf:
            print(f"      银两={pf.get('treasury')}, 粮草={pf.get('food')}, 兵力={pf.get('troops')}")
        else:
            problems.append(f"🟡 player_faction 为空")
        dr = d.get("diplomatic_relations", [])
        if dr:
            print(f"      外交关系: {len(dr)}条")
            for rel in dr[:3]:
                print(f"        -> {rel.get('target_name','?')}: {rel.get('stance','?')}")
        else:
            problems.append(f"🟡 diplomatic_relations 为空")

    # 3. 执行操作
    actions = FACTION_ACTIONS.get(fid, [])
    print(f"  [3] 执行推荐操作 ({len(actions)}个)...")
    for i, (action, params) in enumerate(actions):
        code, data, err = call("POST", "/api/game/command", {
            "action": action,
            "params": params,
            "faction_id": fid,
        })
        if err:
            problems.append(f"🔴 操作{i+1} '{action}' 失败: {err}")
        elif data and data.get("code") != 200:
            msg = data.get("msg", "")
            if "拦截" in str(msg) or "拒绝" in str(msg):
                problems.append(f"🔴 操作{i+1} '{action}' 被拒绝: {msg[:100]}")
            else:
                problems.append(f"🟡 操作{i+1} '{action}' 返回非200: code={data.get('code')}, msg={msg[:100]}")
        else:
            inner = data.get("data", {}) if data else {}
            cid = inner.get("command_id", "?")
            warn = inner.get("warning", "")
            print(f"    ✓ {action}: id={cid}" + (f" (⚠{warn})" if warn else ""))

    # 4. 推进回合
    print(f"  [4] 推进回合...")
    t0 = time.time()
    code, data, err = call("POST", "/api/game/advance-turn")
    t1 = time.time()
    if err or code != 200:
        problems.append(f"🔴 推进回合失败: {err or code}")
    else:
        d = data.get("data", {}) if data else {}
        new_round = d.get("current_round", "?")
        phase = d.get("phase", "?")
        events = d.get("new_events", [])
        n_events = len(events) if isinstance(events, list) else 0
        print(f"      回合推进成功 ({t1-t0:.1f}s) -> 回合{new_round}, phase={phase}, 事件={n_events}条")
        if n_events == 0:
            problems.append(f"🟡 回合推进返回事件为空")
        if isinstance(events, list) and events:
            for ev in events[:3]:
                sev = ev.get("severity", "?")
                title = ev.get("title", ev.get("name", "?"))
                print(f"        [{sev}] {title}")

    # 5. 第二回合
    print(f"  [5] 推进第二回合...")
    t0 = time.time()
    code, data, err = call("POST", "/api/game/advance-turn")
    t1 = time.time()
    if err or code != 200:
        problems.append(f"🔴 第二回合失败: {err or code}")
    else:
        d = data.get("data", {}) if data else {}
        new_round = d.get("current_round", "?")
        events = d.get("new_events", [])
        n_events = len(events) if isinstance(events, list) else 0
        print(f"      第二回合成功 ({t1-t0:.1f}s) -> 回合{new_round}, 事件={n_events}条")
        if isinstance(events, list) and events:
            for ev in events[:3]:
                sev = ev.get("severity", "?")
                title = ev.get("title", ev.get("name", "?"))
                print(f"        [{sev}] {title}")

    # 6. 存档
    print(f"  [6] 存档测试...")
    code, data, err = call("POST", "/api/game/save", {"slot": f"test_{fid}"})
    if err or code != 200:
        problems.append(f"🟡 存档失败: {err or code}")
    else:
        fn = (data.get("data", {}) or {}).get("filename", "?") if data else "?"
        print(f"      存档成功: {fn}")

    return problems


def main():
    print("=" * 60)
    print("  元末逐鹿 3.0 — 九大势力完整游玩测试 v2")
    print("=" * 60)

    # 检查服务器
    print("\n检查服务器状态...")
    code, data, err = call("GET", "/api/health")
    if err or code != 200:
        print(f"❌ 服务器不可用: {err or code}")
        return
    info = data.get("data", {}) if data else {}
    print(f"✅ 服务器正常: ai={info.get('ai_available')}, factions={info.get('factions_loaded')}")

    all_problems = {}
    for faction in FACTIONS:
        try:
            problems = test_faction(faction)
            all_problems[faction["name"]] = problems
        except Exception as e:
            all_problems[faction["name"]] = [f"🔴 测试异常: {traceback.format_exc()}"]

    # 汇总
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)

    total_issues = 0
    for name, problems in all_problems.items():
        if problems:
            total_issues += len(problems)
            has_critical = any("🔴" in p for p in problems)
            print(f"\n{'🔴' if has_critical else '🟡'} {name}: {len(problems)}个问题")
            for p in problems:
                print(f"    {p}")
        else:
            print(f"\n✅ {name}: 无问题")

    print(f"\n总计: {total_issues}个问题")
    print(f"测试势力: {len(FACTIONS)}个")
    print(f"有问题势力: {sum(1 for p in all_problems.values() if p)}个")

    with open("_playthrough_problems.json", "w", encoding="utf-8") as f:
        json.dump(all_problems, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存到 _playthrough_problems.json")


if __name__ == "__main__":
    main()
