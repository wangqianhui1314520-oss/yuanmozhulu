"""
全势力游玩流程测试 v3 - 修正函数名 + tile_count问题分析
"""
import sys
import os
import io
import time
import asyncio
import traceback

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

FACTIONS = [
    ("faction_yuan", "元廷"),
    ("faction_zhuyuanzhang", "朱元璋"),
    ("faction_chenyouliang", "陈友谅"),
    ("faction_zhangshicheng", "张士诚"),
    ("faction_fangguozhen", "方国珍"),
    ("faction_xushouhui", "徐寿辉"),
    ("faction_mingyuzhen", "明玉珍"),
    ("faction_wangbaobao", "王保保"),
    ("faction_mobei", "漠北诸部"),
]

all_results = {}
all_issues = []
total_ok = 0
total_fail = 0

for fid, fname in FACTIONS:
    print(f"\n{'='*60}")
    print(f"  测试势力: {fname} ({fid})")
    print(f"{'='*60}")
    
    issues = []
    ok_count = 0
    fail_count = 0
    
    try:
        import server.api_server as api
        import importlib
        importlib.reload(api)
        
        # === 1. Init ===
        print(f"\n  [1/6] Init 开局...")
        r = asyncio.run(api.init_game({
            "faction_id": fid,
            "mode": "player_turn",
        }))
        
        if r.get("code") != 200:
            msg = r.get("msg", "?")
            issues.append(f"INIT失败: {msg}")
            fail_count += 1
            all_results[fname] = {"issues": issues, "ok": ok_count, "fail": fail_count}
            all_issues.extend([f"[{fname}] {i}" for i in issues])
            total_ok += ok_count
            total_fail += fail_count
            continue
        ok_count += 1
        
        data = r.get("data", {})
        pf = data.get("player_faction", {})
        
        tile_count = pf.get("tile_count", 0)
        treasury = pf.get("treasury", 0)
        arms = pf.get("arms", 0)
        horses = pf.get("horses", 0)
        total_troops = pf.get("total_troops", 0)
        reputation = pf.get("reputation", 0)
        capital_tile = pf.get("capital_tile", "?")
        grain = pf.get("grain", 0)
        
        tiles = data.get("tiles", {})
        faction_tiles = {k: v for k, v in tiles.items() if v.get("faction_id") == fid}
        actual_tile_count = len(faction_tiles)
        
        print(f"    tile_count: 声称{tile_count} | 全局实际{actual_tile_count} | 国库{treasury}银 | 军械{arms} | 战马{horses}")
        print(f"    兵力{total_troops} | 声望{reputation} | 粮草{grain} | 都城{capital_tile}")
        
        # tile_count不一致是已知Bug：初始化用FACTION_STARTER_TILES长度，实际地块来自map_final.json
        if tile_count != actual_tile_count:
            issues.append(f"tile_count≠实际: {tile_count} vs {actual_tile_count} (初始核心 vs 全领地)")
            fail_count += 1
        else:
            ok_count += 1
        
        if actual_tile_count == 0:
            issues.append("势力无地块!")
            fail_count += 1
        else:
            ok_count += 1
        
        if total_troops == 0:
            issues.append("初始兵力为0!")
            fail_count += 1
        else:
            ok_count += 1
        
        if treasury == 0:
            issues.append("初始国库为0!")
            fail_count += 1
        else:
            ok_count += 1
        
        if arms == 0 and fid != "faction_mobei":
            issues.append("初始军械为0!")
            fail_count += 1
        else:
            ok_count += 1
        
        if grain == 0:
            issues.append("初始粮草为0!")
            fail_count += 1
        else:
            ok_count += 1
        
        if reputation == 0 and fid != "faction_mobei":
            issues.append("初始声誉为0!")
            fail_count += 1
        else:
            ok_count += 1
        
        # === 2. Status ===
        print(f"  [2/6] Status 状态查询...")
        r = asyncio.run(api.get_game_status())
        
        if r.get("code") != 200:
            issues.append(f"STATUS失败: {r.get('msg','?')}")
            fail_count += 1
        else:
            sd = r.get("data", {}).get("world_state", {})
            fs = sd.get("factions", {})
            my_f = fs.get(fid, {})
            intel = my_f.get("_intel_visible", None)
            print(f"    intel={intel}")
            if intel is not True:
                issues.append(f"己方intel不是True: {intel}")
                fail_count += 1
            else:
                ok_count += 1
        
        # === 3. Command: Recruit ===
        print(f"  [3/6] 征兵指令...")
        recruit_amount = min(200, max(50, total_troops // 10))
        r = asyncio.run(api.submit_command({
            "action": "recruit",
            "params": {"tile_id": capital_tile, "amount": recruit_amount},
            "faction_id": fid,
        }))
        
        if r.get("code") != 200:
            issues.append(f"征兵失败: {r.get('msg','?')}")
            fail_count += 1
            print(f"    FAIL: {r.get('msg','?')}")
        else:
            ok_count += 1
            print(f"    征兵{recruit_amount}人 -> OK")
        
        # === 4. Command: Train ===
        print(f"  [4/6] 训练指令...")
        r = asyncio.run(api.submit_command({
            "action": "train",
            "params": {"tile_id": capital_tile, "amount": 50},
            "faction_id": fid,
        }))
        
        if r.get("code") != 200:
            issues.append(f"训练失败: {r.get('msg','?')}")
            fail_count += 1
            print(f"    FAIL: {r.get('msg','?')}")
        else:
            ok_count += 1
            print(f"    训练50人 -> OK")
        
        # === 5. Command: Patrol ===
        print(f"  [5/6] 巡查指令...")
        r = asyncio.run(api.submit_command({
            "action": "patrol",
            "params": {"tile_id": capital_tile},
            "faction_id": fid,
        }))
        
        if r.get("code") != 200:
            issues.append(f"巡查失败: {r.get('msg','?')}")
            fail_count += 1
            print(f"    FAIL: {r.get('msg','?')}")
        else:
            ok_count += 1
            print(f"    巡查 -> OK")
        
        # === 6. Advance Turn ===
        print(f"  [6/6] 推进回合...")
        start = time.time()
        r = asyncio.run(api.advance_turn())
        elapsed = time.time() - start
        
        if r.get("code") != 200:
            issues.append(f"回合推进失败: {r.get('msg','?')}")
            fail_count += 1
        else:
            rd = r.get("data", {})
            current_round = rd.get("current_round", "?")
            new_events = rd.get("new_events", [])
            ending = rd.get("ending", {})
            print(f"    回合: {current_round} | 耗时: {elapsed:.1f}s | 事件: {len(new_events) if new_events else 0}")
            
            if ending and ending.get("game_over"):
                issues.append(f"游戏结束: {ending.get('reason','?')}")
                fail_count += 1
            else:
                ok_count += 1
            
            # 结算后状态
            r2 = asyncio.run(api.get_game_status())
            if r2.get("code") == 200:
                sd2 = r2.get("data", {}).get("world_state", {})
                fs2 = sd2.get("factions", {})
                my_f2 = fs2.get(fid, {})
                tc2 = my_f2.get("tile_count", "?")
                tt2 = my_f2.get("total_troops", "?")
                tr2 = my_f2.get("treasury", "?")
                ar2 = my_f2.get("arms", "?")
                print(f"    结算后: tiles={tc2}, troops={tt2}, treasury={tr2}, arms={ar2}")
    
    except Exception as e:
        issues.append(f"异常: {str(e)[:200]}")
        fail_count += 1
        traceback.print_exc()
    
    all_results[fname] = {"issues": issues, "ok": ok_count, "fail": fail_count}
    all_issues.extend([f"[{fname}] {i}" for i in issues])
    total_ok += ok_count
    total_fail += fail_count

# === 汇总 ===
print("\n\n" + "=" * 60)
print("  全势力测试汇总报告")
print("=" * 60)
print(f"\n总检查项: {total_ok + total_fail} | ✅ 通过: {total_ok} | ❌ 失败: {total_fail}")

# 分类问题
bug_tile = [i for i in all_issues if "tile_count" in i]
bug_other = [i for i in all_issues if "tile_count" not in i]

if bug_tile:
    print(f"\n🔴 Bug #1 - tile_count 初始化不一致 (影响全部9势力):")
    print(f"   FACTION_STARTER_TILES 定义的是核心地块，map_final.json 包含全领地")
    print(f"   初始时 tile_count 取自前者，回合结算后由 settle_engine 修正为后者")
    for i in bug_tile:
        print(f"   {i}")

if bug_other:
    print(f"\n🔴 其他问题 ({len(bug_other)} 项):")
    for i, issue in enumerate(bug_other, 1):
        print(f"  {i}. {issue}")

print(f"\n各势力详情:")
for fname, result in all_results.items():
    pf = result["fail"]
    other_fails = sum(1 for i in result["issues"] if "tile_count" not in i)
    icon = "✅" if pf == 0 else ("⚠️" if other_fails == 0 else "🔴")
    print(f"  {icon} {fname}: 通过{result['ok']}/失败{result['fail']}")
    for iss in result["issues"]:
        print(f"       - {iss}")
