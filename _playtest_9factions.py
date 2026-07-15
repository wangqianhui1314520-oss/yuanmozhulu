"""
元末逐鹿3.0 - 九大势力游玩流程测试
根据 docs/九大势力完整游玩方案.md 逐势力测试，记录所有问题
使用 urllib 绕过代理问题
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8800"
ISSUES = []
RESULTS = {}


def record_issue(faction, turn, category, severity, description, details=None):
    issue = {
        "faction": faction, "turn": turn, "category": category,
        "severity": severity, "description": description,
        "details": details or "", "timestamp": datetime.now().isoformat(),
    }
    ISSUES.append(issue)
    tag = {"critical": "❌", "major": "⚠", "minor": "•"}.get(severity, "?")
    print(f"  {tag} [{severity.upper()}] [{faction}][T{turn}] {category}: {description}")


def api_post(path, data=None, timeout=90):
    """同步POST请求"""
    try:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else b'{}'
        req = urllib.request.Request(f"{BASE_URL}{path}", data=body,
                                     headers={'Content-Type': 'application/json; charset=utf-8'},
                                     method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')
            return json.loads(body) if body else {"code": -1, "msg": f"HTTP {e.code}"}
        except:
            return {"code": -1, "msg": f"HTTP {e.code}"}
    except Exception as e:
        return {"code": -1, "msg": f"请求异常: {e}"}


def api_get(path, timeout=30):
    """同步GET请求"""
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"code": -1, "msg": f"GET异常: {e}"}


def check_server():
    result = api_get("/api/health")
    if result.get("code") == 200:
        print(f"服务器在线: {result.get('msg', 'OK')}")
        return True
    print(f"服务器不可用: {result}")
    return False


def init_game(faction_id):
    """开局"""
    result = api_post("/api/game/init", {"faction_id": faction_id, "mode": "player_turn"})
    if result.get("code") != 200:
        return None, result
    return result.get("data", {}), None


def send_command(faction_id, action, params):
    """提交指令"""
    return api_post("/api/game/command", {
        "action": action, "params": params, "faction_id": faction_id,
    })


def advance_turn():
    """推进回合"""
    return api_post("/api/game/advance-turn", {})


def get_status():
    """获取游戏状态"""
    return api_get("/api/game/status")


# ============================================================
# 势力指令定义
# ============================================================

def zhuyuanzhang_cmds(turn, pf):
    capital = pf.get("capital_tile", "tile_yingtian")
    return {
        1: [("farm", {"tile_id": capital}), ("develop", {"tile_id": capital})],
        2: [("recruit", {"count": 2000}), ("train_troops", {"tile_id": capital})],
        3: [("tax", {"tile_id": capital}), ("build", {"tile_id": capital, "building_type": "wall"})],
        4: [("scout", {"target_faction": "faction_chenyouliang"})],
        5: [("fortify", {"tile_id": "tile_taiping"}), ("appoint", {"person_name": "徐达", "position": "将军"})],
        6: [("relief", {"tile_id": capital}), ("develop", {"tile_id": "tile_zhenjiang"})],
        7: [("recruit", {"count": 2000}), ("buy_horses", {"count": 50})],
        8: [("train_troops", {"tile_id": "tile_taiping"})],
        9: [("diplomacy", {"target_faction": "faction_mingyuzhen", "intent": "friendly"}),
            ("scout", {"target_faction": "faction_zhangshicheng"})],
        10: [("scout", {"target_faction": "faction_chenyouliang"})],
    }.get(turn, [])


def zhangshicheng_cmds(turn, pf):
    return {
        1: [("trade", {"target": "杭州"}), ("trade", {"target": "扬州"})],
        2: [("develop", {"tile_id": "tile_pingjiang"}), ("tax", {"tile_id": "tile_pingjiang"})],
        3: [("build", {"tile_id": "tile_pingjiang", "building_type": "wall"}),
            ("farm", {"tile_id": "tile_shaoxing"})],
        4: [("recruit", {"count": 1500}), ("train_troops", {"tile_id": "tile_pingjiang"})],
        5: [("buy_horses", {"count": 80})],
        6: [("fortify", {"tile_id": "tile_changzhou"}),
            ("scout", {"target_faction": "faction_zhuyuanzhang"})],
        7: [("diplomacy", {"target_faction": "faction_fangguozhen", "intent": "friendly"})],
        8: [("develop", {"tile_id": "tile_hangzhou"}), ("tax", {"tile_id": "tile_pingjiang"})],
        9: [("trade", {"target": "海上"})],
        10: [("relief", {"tile_id": "tile_pingjiang"})],
    }.get(turn, [])


def mingyuzhen_cmds(turn, pf):
    return {
        1: [("farm", {"tile_id": "tile_chengdu"}), ("farm", {"tile_id": "tile_chongqing"})],
        2: [("develop", {"tile_id": "tile_chengdu"}), ("fortify", {"tile_id": "tile_kuizhou"})],
        3: [("recruit", {"count": 2000}), ("train_troops", {"tile_id": "tile_chongqing"})],
        4: [("build", {"tile_id": "tile_kuizhou", "building_type": "wall"})],
        5: [("fortify", {"tile_id": "tile_baoning"}), ("scout", {"target": "汉中"})],
        6: [("relief", {"tile_id": "tile_chengdu"}), ("tax", {"tile_id": "tile_chongqing"})],
        7: [("develop", {"tile_id": "tile_jiading"}), ("farm", {"tile_id": "tile_chengdu"})],
        8: [("train_troops", {"tile_id": "tile_kuizhou"}), ("garrison", {"tile_id": "tile_kuizhou"})],
        9: [("appoint", {"person_name": "刘桢", "position": "宰相"})],
        10: [("scout", {"target_faction": "faction_xushouhui"})],
    }.get(turn, [])


def fangguozhen_cmds(turn, pf):
    return {
        1: [("trade", {"target": "海上"}), ("scout", {"target_faction": "faction_zhangshicheng"})],
        2: [("fortify", {"tile_id": "tile_qingyuan"})],
        3: [("recruit", {"count": 1000}), ("train_troops", {"tile_id": "tile_qingyuan"})],
        4: [("diplomacy", {"target_faction": "faction_zhangshicheng", "intent": "improve"})],
        5: [("trade", {"target": "海上"}), ("buy_horses", {"count": 30})],
        6: [("develop", {"tile_id": "tile_qingyuan"})],
        7: [("scout", {"target_faction": "faction_zhuyuanzhang"}),
            ("diplomacy", {"target_faction": "faction_zhuyuanzhang", "intent": "friendly"})],
        8: [("fortify", {"tile_id": "tile_wenzhou"}), ("garrison", {"tile_id": "tile_zhoushan"})],
        9: [("tax", {"tile_id": "tile_qingyuan"}), ("relief", {"tile_id": "tile_qingyuan"})],
        10: [("spy", {"target_faction": "faction_zhangshicheng"})],
    }.get(turn, [])


def wangbaobao_cmds(turn, pf):
    return {
        1: [("recruit", {"count": 2000}), ("buy_horses", {"count": 100})],
        2: [("train_troops", {"tile_id": "tile_taiyuan"})],
        3: [("fortify", {"tile_id": "tile_taiyuan"}),
            ("scout", {"target_faction": "faction_xushouhui"})],
        4: [("march", {"to_tile": "tile_datong", "from_tile": "tile_taiyuan"})],
        5: [("garrison", {"tile_id": "tile_taiyuan"})],
        6: [("train", {"unit_type": "cavalry"})],
        7: [("develop", {"tile_id": "tile_taiyuan"}), ("tax", {"tile_id": "tile_taiyuan"})],
        8: [("scout", {"target_faction": "faction_mobei"}),
            ("fortify", {"tile_id": "tile_datong"})],
        9: [("diplomacy", {"target_faction": "faction_yuan", "intent": "loyalty"})],
        10: [("scout", {"target_faction": "faction_xushouhui"})],
    }.get(turn, [])


def chenyouliang_cmds(turn, pf):
    return {
        1: [("recruit", {"count": 3000}),
            ("build", {"tile_id": "tile_wuchang", "building_type": "water_fort"})],
        2: [("train_troops", {"tile_id": "tile_wuchang"})],
        3: [("scout", {"target_faction": "faction_zhuyuanzhang"})],
        4: [("fortify", {"tile_id": "tile_jiangzhou"}), ("buy_horses", {"count": 60})],
        5: [("farm", {"tile_id": "tile_changsha"})],
        6: [("train", {"unit_type": "navy"}), ("garrison", {"tile_id": "tile_wuchang"})],
        7: [("relief", {"tile_id": "tile_wuchang"})],
        8: [("spy", {"target_faction": "faction_zhuyuanzhang"}),
            ("develop", {"tile_id": "tile_jiangzhou"})],
        9: [("recruit", {"count": 2000})],
        10: [("scout", {"target_faction": "faction_zhuyuanzhang"})],
    }.get(turn, [])


def xushouhui_cmds(turn, pf):
    return {
        1: [("recruit", {"count": 3000})],
        2: [("recruit", {"count": 2000}), ("farm", {"tile_id": "tile_xiangyang"})],
        3: [("train_troops", {"tile_id": "tile_xiangyang"}),
            ("develop", {"tile_id": "tile_xiangyang"})],
        4: [("fortify", {"tile_id": "tile_xiangyang"}),
            ("scout", {"target_faction": "faction_chenyouliang"})],
        5: [("relief", {"tile_id": "tile_xiangyang"})],
        6: [("recruit", {"count": 1500})],
        7: [("supply", {"tile_id": "tile_nanyang"}), ("edict", {"content": "弥勒号召"})],
        8: [("scout", {"target_faction": "faction_wangbaobao"}),
            ("fortify", {"tile_id": "tile_nanyang"})],
        9: [("diplomacy", {"target_faction": "faction_zhuyuanzhang", "intent": "friendly"})],
        10: [("scout", {"target_faction": "faction_chenyouliang"})],
    }.get(turn, [])


def mobei_cmds(turn, pf):
    return {
        1: [("raid", {"target_tile": "边境"})],
        2: [("raid", {"target_tile": "边境"}), ("recruit", {"count": 1000})],
        3: [("train", {"unit_type": "cavalry"})],
        4: [("scout", {"target_faction": "faction_wangbaobao"})],
        5: [("buy_horses", {"count": 100})],
        6: [("raid", {"target_tile": "边境"})],
        7: [("fortify", {"tile_id": "tile_helin"}), ("develop", {"tile_id": "tile_helin"})],
        8: [("recruit", {"count": 2000}), ("train", {"unit_type": "cavalry"})],
        9: [("scout", {"target_faction": "faction_yuan"}),
            ("diplomacy", {"target_faction": "faction_wangbaobao", "intent": "neutral"})],
        10: [("raid", {"target_tile": "边境"})],
    }.get(turn, [])


def yuan_cmds(turn, pf):
    return {
        1: [("recruit", {"count": 3000}), ("edict", {"content": "讨逆令"})],
        2: [("supply", {"tile_id": "tile_daming"})],
        3: [("recruit", {"count": 2000})],
        4: [("fortify", {"tile_id": "tile_dadu"}), ("relief", {"tile_id": "tile_dadu"})],
        5: [("tax", {"tile_id": "tile_dadu"}), ("develop", {"tile_id": "tile_jinan"})],
        6: [("scout", {"target_faction": "faction_zhuyuanzhang"})],
        7: [("purge", {"target": "贪官"})],
        8: [("diplomacy", {"target_faction": "faction_wangbaobao", "intent": "loyalty"})],
        9: [("relief", {"tile_id": "tile_jinan"})],
        10: [("scout", {"target_faction": "faction_xushouhui"})],
    }.get(turn, [])


FACTIONS = {
    "faction_zhuyuanzhang": {"name": "朱元璋", "doc": "势力一", "cmds": zhuyuanzhang_cmds, "turns": 10},
    "faction_zhangshicheng": {"name": "张士诚", "doc": "势力二", "cmds": zhangshicheng_cmds, "turns": 10},
    "faction_mingyuzhen": {"name": "明玉珍", "doc": "势力三", "cmds": mingyuzhen_cmds, "turns": 10},
    "faction_fangguozhen": {"name": "方国珍", "doc": "势力四", "cmds": fangguozhen_cmds, "turns": 10},
    "faction_wangbaobao": {"name": "王保保", "doc": "势力五", "cmds": wangbaobao_cmds, "turns": 10},
    "faction_chenyouliang": {"name": "陈友谅", "doc": "势力六", "cmds": chenyouliang_cmds, "turns": 10},
    "faction_xushouhui": {"name": "徐寿辉", "doc": "势力七", "cmds": xushouhui_cmds, "turns": 10},
    "faction_mobei": {"name": "漠北诸部", "doc": "势力八", "cmds": mobei_cmds, "turns": 10},
    "faction_yuan": {"name": "元廷", "doc": "势力九", "cmds": yuan_cmds, "turns": 10},
}


def verify_doc_vs_actual(faction_id, fac_name, init_data):
    """验证文档中的初始数据 vs 实际开局数据"""
    doc_data = {
        "faction_zhuyuanzhang": {"银两": 8000, "粮草": 4000, "兵力": 3000, "兵器": 80, "战马": 30, "声望": 40, "领土": 11},
        "faction_zhangshicheng": {"银两": 15000, "粮草": 7000, "兵力": 3500, "兵器": 100, "战马": 40, "声望": 45, "领土": 9},
        "faction_mingyuzhen": {"银两": 6500, "粮草": 5000, "兵力": 3000, "兵器": 90, "战马": 30, "声望": 40, "领土": 8},
        "faction_fangguozhen": {"银两": 6000, "粮草": 3000, "兵力": 2000, "兵器": 60, "战马": 20, "声望": 30, "领土": 4},
        "faction_wangbaobao": {"银两": 8000, "粮草": 5000, "兵力": 4000, "兵器": 120, "战马": 150, "声望": 45, "领土": 6},
        "faction_chenyouliang": {"银两": 12000, "粮草": 6000, "兵力": 5000, "兵器": 150, "战马": 50, "声望": 35, "领土": 11},
        "faction_xushouhui": {"银两": 6000, "粮草": 4000, "兵力": 3500, "兵器": 90, "战马": 40, "声望": 35, "领土": 6},
        "faction_mobei": {"银两": 5000, "粮草": 2000, "兵力": 4500, "兵器": 80, "战马": 200, "声望": 25, "领土": 5},
        "faction_yuan": {"银两": 20000, "粮草": 8000, "兵力": 6000, "兵器": 300, "战马": 200, "声望": 60, "领土": 9},
    }
    expected = doc_data.get(faction_id, {})
    if not expected:
        return

    pf = init_data.get("player_faction", {})
    ws = init_data.get("world_state", {})
    factions = ws.get("factions", {})
    fac = factions.get(faction_id, pf)

    actual = {
        "银两": fac.get("treasury", -1),
        "粮草": fac.get("grain", -1),
        "兵力": fac.get("total_troops", -1),
        "兵器": fac.get("arms", -1),
        "战马": fac.get("horses", -1),
        "声望": fac.get("reputation", -1),
        "领土": len(fac.get("tiles", [])),
    }

    for key, exp_val in expected.items():
        act_val = actual.get(key, -999)
        if act_val != exp_val:
            record_issue(fac_name, 0, "文档数据一致性", "major",
                         f"文档声称 {key}={exp_val}，实际开局 {key}={act_val}",
                         f"expected={exp_val} actual={act_val}")


def test_faction(faction_id, info):
    """测试单个势力"""
    fac_name = info["name"]
    turns = info["turns"]
    cmd_func = info["cmds"]

    print(f"\n{'#'*60}")
    print(f"# {info['doc']} / {fac_name} ({faction_id})")
    print(f"{'#'*60}")

    # 开局
    data, err = init_game(faction_id)
    if err or not data:
        record_issue(fac_name, 0, "开局", "critical", f"开局失败: {err.get('msg','?') if err else 'NO_DATA'}")
        return {"faction": fac_name, "status": "FAIL", "turns_completed": 0}

    # 验证文档数据一致性
    verify_doc_vs_actual(faction_id, fac_name, data)

    pf = data.get("player_faction", {})
    ws = data.get("world_state", {})
    facets = ws.get("factions", {})
    fac = facets.get(faction_id, pf)

    treasury = fac.get("treasury", 0)
    troops = fac.get("total_troops", 0)
    grain = fac.get("grain", 0)
    print(f"  初始: 银两={treasury}, 粮草={grain}, 兵力={troops}")

    # 逐回合
    for turn in range(1, turns + 1):
        print(f"\n--- 第{turn}回合 ---")
        turn_cmds = cmd_func(turn, fac)

        if not turn_cmds:
            print(f"  无指令，直接推进")
            result = advance_turn()
            if result.get("code") != 200:
                record_issue(fac_name, turn, "回合推进", "major",
                             f"推进失败(无指令): {result.get('msg','?')}")
                break
            # Update fac data from result
            ws = result.get("data", {}).get("world_state", {})
            facets = ws.get("factions", {})
            fac = facets.get(faction_id, {})
            if not fac.get("is_alive", True):
                record_issue(fac_name, turn, "势力覆灭", "critical",
                             f"在第{turn}回合覆灭!")
                break
            print(f"  → R{result['data'].get('current_round','?')} "
                  f"银={fac.get('treasury','?')} 兵={fac.get('total_troops','?')} "
                  f"粮={fac.get('grain','?')}")
            continue

        # 提交指令
        for action, params in turn_cmds:
            r = send_command(faction_id, action, params)
            code = r.get("code", -1)
            if code != 200:
                record_issue(fac_name, turn, "指令提交", "minor",
                             f"指令 '{action}' 被拒绝: {r.get('msg','?')}",
                             f"params={params}")
                print(f"  ✗ {action}: {r.get('msg','?')}")
            else:
                print(f"  ✓ {action} OK")

        # 推进回合
        result = advance_turn()
        code = result.get("code", -1)
        if code != 200:
            record_issue(fac_name, turn, "回合推进", "major",
                         f"回合推进失败: {result.get('msg','?')}")
            print(f"  ❌ 推进失败!")
            break

        d = result.get("data", {})
        rnd = d.get("current_round", "?")
        ws = d.get("world_state", {})
        facets_r = ws.get("factions", {})
        fac = facets_r.get(faction_id, {})
        treasury = fac.get("treasury", 0)
        troops = fac.get("total_troops", 0)
        grain = fac.get("grain", 0)
        alive = fac.get("is_alive", True)

        print(f"  → R{rnd} 银={treasury} 兵={troops} 粮={grain} "
              f"活={'✓' if alive else '✗'}")

        if not alive:
            record_issue(fac_name, turn, "势力覆灭", "critical",
                         f"第{turn}回合后势力覆灭!")
            break

        if treasury < 0:
            record_issue(fac_name, turn, "经济", "major",
                         f"银两为负: {treasury}")
        if grain < 0:
            record_issue(fac_name, turn, "资源", "major",
                         f"粮草为负: {grain}")

        # 检查AI推演结果（回合摘要是否有错误）
        summary = d.get("round_summary", {})
        phases = summary.get("phases", {})
        for pname, pdata in (phases or {}).items():
            if isinstance(pdata, dict) and pdata.get("errors"):
                record_issue(fac_name, turn, f"阶段/{pname}", "major",
                             f"回合阶段异常: {pdata['errors'][:2]}")

        time.sleep(0.3)  # 不要请求太密集

    print(f"\n  ✓ {fac_name} 测试完成 ({turns}回合)")
    return {"faction": fac_name, "status": "OK", "turns_completed": turns}


def main():
    print("=" * 70)
    print("  元末逐鹿3.0 - 九大势力游玩流程测试")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if not check_server():
        print("请先启动: python server.py")
        return

    for fid, info in FACTIONS.items():
        try:
            result = test_faction(fid, info)
            RESULTS[fid] = result
        except Exception as e:
            print(f"\n❌ {info['name']} 测试崩溃: {e}")
            record_issue(info["name"], 0, "测试异常", "critical", str(e))
            RESULTS[fid] = {"faction": info["name"], "status": "CRASH", "error": str(e)}

    # 汇总
    print("\n" + "=" * 70)
    print("  测试报告")
    print("=" * 70)
    print(f"总问题: {len(ISSUES)}")
    sev = {"critical": [], "major": [], "minor": []}
    for i in ISSUES:
        sev[i["severity"]].append(i)
    print(f"  Critical: {len(sev['critical'])}")
    print(f"  Major:    {len(sev['major'])}")
    print(f"  Minor:    {len(sev['minor'])}")

    print("\n  各势力结果:")
    for fid, r in RESULTS.items():
        info = FACTIONS[fid]
        cnt = len([i for i in ISSUES if i["faction"] == info["name"]])
        print(f"    {info['name']}: {r.get('status','?')} "
              f"({r.get('turns_completed',0)}回合, {cnt}问题)")

    if ISSUES:
        print(f"\n{'='*70}")
        print("  详细问题")
        print(f"{'='*70}")
        for i in sorted(ISSUES, key=lambda x: (x["faction"], x["turn"])):
            print(f"\n  [{i['severity'].upper()}] {i['faction']}/{i['category']} T{i['turn']}")
            print(f"    {i['description']}")
            if i.get("details"):
                print(f"    详情: {i['details']}")

    output = {
        "test_time": datetime.now().isoformat(),
        "total_issues": len(ISSUES),
        "severity": {k: len(v) for k, v in sev.items()},
        "results": {fid: r for fid, r in RESULTS.items()},
        "issues": ISSUES,
    }
    out_path = Path(__file__).parent / "_playtest_9factions_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果: {out_path}")


if __name__ == "__main__":
    main()
