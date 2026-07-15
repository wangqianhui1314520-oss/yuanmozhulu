"""元末逐鹿3.0 - 九大势力完整游玩测试（每势力2回合）"""
import json, urllib.request, time, sys, os
from datetime import datetime

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

BASE = "http://127.0.0.1:8800"
ISSUES = []

def record(faction, turn, category, severity, desc, detail=""):
    ISSUES.append({"faction": faction, "turn": turn, "category": category,
                    "severity": severity, "description": desc, "details": detail})
    tag = {"critical":"CRIT","major":"MAJ","minor":"MIN"}.get(severity,"???")
    print(f"  [{tag}] [{faction}][T{turn}] {category}: {desc}")

def post(path, data=None, timeout=120):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else b'{}'
    req = urllib.request.Request(f"{BASE}{path}", data=body,
        headers={'Content-Type':'application/json; charset=utf-8'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def init(fid):
    r = post("/api/game/init", {"faction_id": fid, "mode": "player_turn"})
    if r["code"] != 200:
        return None, r
    return r["data"], None

def cmd(fid, action, params):
    return post("/api/game/command", {"action": action, "params": params, "faction_id": fid})

def advance():
    return post("/api/game/advance-turn", {}, timeout=120)

# ===== 文档推荐指令但API不支持的黑名单 =====
VALID_ACTIONS = ['march','spy','trade','law','recruit','develop','fortify','relief',
    'diplomacy','tax','build','enfeoff','purge','amnesty','scout','buy_horses',
    'train_troops','collect_tax','attack','train','patrol','mobilize','raid',
    'ambush','transport','garrison','transfer','governor','marriage','tribute',
    'pledge','vassal','counter_spy','sabotage','bribe','assassinate','survey',
    'move_capital','decree','conscript']

def test_cmd_validity(fac_name, doc_action):
    if doc_action not in VALID_ACTIONS:
        record(fac_name, 0, "文档/API不一致", "major",
               f"文档推荐指令 '{doc_action}' 不在API valid_actions中")
        return False
    return True

# ===== 文档数据 vs 实际数据 =====
DOC_DATA = {
    "faction_zhuyuanzhang": {"name":"朱元璋","银两":8000,"粮草":4000,"兵力":3000,"领土":11},
    "faction_zhangshicheng":  {"name":"张士诚","银两":15000,"粮草":7000,"兵力":3500,"领土":9},
    "faction_mingyuzhen":     {"name":"明玉珍","银两":6500,"粮草":5000,"兵力":3000,"领土":8},
    "faction_fangguozhen":    {"name":"方国珍","银两":6000,"粮草":3000,"兵力":2000,"领土":4},
    "faction_wangbaobao":     {"name":"王保保","银两":8000,"粮草":5000,"兵力":4000,"领土":6},
    "faction_chenyouliang":   {"name":"陈友谅","银两":12000,"粮草":6000,"兵力":5000,"领土":11},
    "faction_xushouhui":      {"name":"徐寿辉","银两":6000,"粮草":4000,"兵力":3500,"领土":6},
    "faction_mobei":          {"name":"漠北诸部","银两":5000,"粮草":2000,"兵力":4500,"领土":5},
    "faction_yuan":           {"name":"元廷","银两":20000,"粮草":8000,"兵力":6000,"领土":9},
}

# ===== 各势力指令（每势力2回合，测试关键指令）=====
def get_cmds(fid, turn, fac_data):
    """返回 (action, params) 列表"""
    fac_tiles = [t.get("tile_id","") for t in fac_data.get("tiles",[])] if fac_data else []
    cap = fac_data.get("capital_tile","") if fac_data else ""
    first_tile = fac_tiles[0] if fac_tiles else cap

    cmd_map = {
        "faction_zhuyuanzhang": {
            1: [("farm",{"tile_id":cap}), ("develop",{"tile_id":cap})],
            2: [("recruit",{"count":2000}), ("train_troops",{"tile_id":cap})],
        },
        "faction_zhangshicheng": {
            1: [("trade",{"target":"杭州"}), ("trade",{"target":"扬州"})],
            2: [("develop",{"tile_id":"tile_pingjiang"}), ("tax",{"tile_id":"tile_pingjiang"})],
        },
        "faction_mingyuzhen": {
            1: [("farm",{"tile_id":"tile_chengdu"}), ("farm",{"tile_id":"tile_chongqing"})],
            2: [("develop",{"tile_id":"tile_chengdu"}), ("fortify",{"tile_id":"tile_kuizhou"})],
        },
        "faction_fangguozhen": {
            1: [("trade",{"target":"海上"}), ("scout",{"target_faction":"faction_zhangshicheng"})],
            2: [("fortify",{"tile_id":"tile_qingyuan"})],
        },
        "faction_wangbaobao": {
            1: [("recruit",{"count":2000}), ("buy_horses",{"count":100})],
            2: [("train_troops",{"tile_id":"tile_taiyuan"})],
        },
        "faction_chenyouliang": {
            1: [("recruit",{"count":3000}), ("build",{"tile_id":"tile_wuchang","building_type":"water_fort"})],
            2: [("train_troops",{"tile_id":"tile_wuchang"})],
        },
        "faction_xushouhui": {
            1: [("recruit",{"count":3000})],
            2: [("recruit",{"count":2000}), ("farm",{"tile_id":"tile_xiangyang"})],
        },
        "faction_mobei": {
            1: [("raid",{"target_tile":"边境"})],
            2: [("raid",{"target_tile":"边境"}), ("recruit",{"count":1000})],
        },
        "faction_yuan": {
            1: [("recruit",{"count":3000}), ("edict",{"content":"讨逆令"})],
            2: [("supply",{"tile_id":"tile_daming"})],
        },
    }
    return cmd_map.get(fid, {}).get(turn, [])


def test_faction(fid, info):
    fac_name = info["name"]
    print(f"\n{'#'*50}")
    print(f"# {fac_name} ({fid})")
    print(f"{'#'*50}")

    # 开局
    data, err_result = init(fid)
    if data is None:
        record(fac_name, 0, "开局", "critical", f"开局失败: {err_result.get('msg','?') if err_result else '?'}")
        return

    # 验证文档数据
    ws = data.get("world_state", {})
    fac = ws.get("factions", {}).get(fid, data.get("player_faction", {}))
    actual = {
        "银两": fac.get("treasury", -1), "粮草": fac.get("grain", -1),
        "兵力": fac.get("total_troops", -1),
        "领土": len(fac.get("tiles", [])),
    }
    print(f"  开局: 银={actual['银两']} 粮={actual['粮草']} 兵={actual['兵力']} 地={actual['领土']}")

    for key, exp in info.items():
        if key == "name": continue
        act = actual.get(key, -999)
        if act != exp:
            record(fac_name, 0, "文档数据不一致", "major",
                   f"文档:{key}={exp} 实际:{key}={act}")

    # 测试2回合
    for turn in [1, 2]:
        print(f"  --- T{turn} ---")
        cmds = get_cmds(fid, turn, fac)

        for action, params in cmds:
            # 先检查指令是否合法
            if action not in VALID_ACTIONS:
                record(fac_name, turn, "指令非法", "major",
                       f"文档推荐指令 '{action}' 不在 valid_actions (文档: 43种指令)",
                       f"valid_actions={VALID_ACTIONS}")
                print(f"    ✗ {action}: 不在合法指令列表 (文档声称可用但API拒绝)")
            else:
                r = cmd(fid, action, params)
                code = r.get("code", -1)
                if code == 200:
                    print(f"    ✓ {action} OK")
                else:
                    record(fac_name, turn, "指令提交失败", "minor",
                           f"{action}: {r.get('msg','?')}")
                    print(f"    ✗ {action}: {r.get('msg','?')[:80]}")

        # 推进
        t0 = time.time()
        rr = advance()
        elapsed = time.time() - t0
        code = rr.get("code", -1)

        if code == 200:
            dd = rr["data"]
            f2 = dd["world_state"]["factions"].get(fid, {})
            alive = f2.get("is_alive", True)
            treasury = f2.get("treasury", 0)
            troops = f2.get("total_troops", 0)
            grain = f2.get("grain", 0)
            events = dd.get("new_events", [])
            print(f"    R{dd['current_round']} ({elapsed:.0f}s) "
                  f"银={treasury} 兵={troops} 粮={grain} "
                  f"活={'✓' if alive else '✗'} 事件={len(events)}")

            if not alive:
                record(fac_name, turn, "势力覆灭", "critical", f"第{turn}回合后覆灭")
                break

            # 合理性检查
            if troops <= 0:
                record(fac_name, turn, "兵力异常", "critical", f"兵力归零")
            if treasury < 0:
                record(fac_name, turn, "经济异常", "major", f"银两为负: {treasury}")
            if grain < 0:
                record(fac_name, turn, "资源异常", "major", f"粮草为负: {grain}")

            # 检查回合摘要错误
            summary = dd.get("round_summary", {})
            for pn, pd in (summary.get("phases", {}) or {}).items():
                if isinstance(pd, dict) and pd.get("errors"):
                    record(fac_name, turn, f"阶段错误/{pn}", "major",
                           f"回合阶段异常: {pd['errors'][:2]}")

            fac = f2
        else:
            record(fac_name, turn, "回合推进失败", "major", f"code={code}: {rr.get('msg','?')}")
            print(f"    ✗ 推进失败: {rr.get('msg','?')}")
            break

        time.sleep(0.5)


def main():
    print("=" * 60)
    print(f"  元末逐鹿3.0 - 九大势力游玩测试")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for fid, info in DOC_DATA.items():
        try:
            test_faction(fid, info)
        except Exception as e:
            print(f"\n  ❌ {info['name']} 测试崩溃: {e}")
            record(info["name"], 0, "测试异常", "critical", str(e))

    # 汇总
    print("\n" + "=" * 60)
    print(f"  测试完成! 共 {len(ISSUES)} 个问题")
    print("=" * 60)

    sev = {"critical": [], "major": [], "minor": []}
    for i in ISSUES:
        sev[i["severity"]].append(i)

    print(f"  Critical: {len(sev['critical'])}")
    print(f"  Major:    {len(sev['major'])}")
    print(f"  Minor:    {len(sev['minor'])}")

    # 按问题类型分类
    cats = {}
    for i in ISSUES:
        c = i["category"]
        cats[c] = cats.get(c, 0) + 1
    print("\n  问题分类:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {c}: {n}")

    # 详细列表
    if ISSUES:
        print(f"\n{'='*60}")
        print("  详细问题列表")
        print(f"{'='*60}")
        for i in sorted(ISSUES, key=lambda x: (x["faction"], x["turn"])):
            print(f"\n  [{i['severity'].upper()}] {i['faction']} T{i['turn']} | {i['category']}")
            print(f"    {i['description']}")
            if i.get("details"): print(f"    → {i['details']}")

    # 保存
    out = {
        "test_time": datetime.now().isoformat(),
        "total": len(ISSUES),
        "severity": {k: len(v) for k, v in sev.items()},
        "categories": cats,
        "issues": ISSUES,
    }
    path = os.path.join(os.path.dirname(__file__), "_playtest_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {path}")


if __name__ == "__main__":
    main()
