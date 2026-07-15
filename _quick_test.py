"""剩余6个势力测试"""
import requests, json, time, traceback, sys, io, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ["no_proxy"] = "localhost,127.0.0.1"

BASE = "http://localhost:8800"
NP = {"http": None, "https": None}

def call(m, p, d=None):
    try:
        r = (requests.get if m=="GET" else requests.post)(f"{BASE}{p}", json=d, timeout=300, proxies=NP)
        try: return r.status_code, r.json(), None
        except: return r.status_code, None, f"JSON fail: {r.text[:200]}"
    except Exception as e: return 0, None, str(e)

def test(fid, name, actions):
    problems = []
    print(f"\n{'='*50}\n  {name} ({fid})\n{'='*50}")
    
    print("[init]", end=" ", flush=True)
    t0=time.time()
    c,d,e=call("POST","/api/game/init",{"faction_id":fid,"mode":"player_turn"})
    print(f"{time.time()-t0:.1f}s code={c}")
    if e or c!=200: return [f"INIT FAIL: {e or c}"]
    ws=(d.get("data",{}) if d else {}).get("world_state",{})
    factions=ws.get("factions",{})
    if fid in factions:
        pf=factions[fid]
        print(f"  {pf.get('name','?')} 银两={pf.get('treasury','?')} 兵力={pf.get('total_troops','?')}")
    tiles=[k for k,v in ws.get("tiles",{}).items() if v.get("faction_id")==fid]
    print(f"  地块={len(tiles)}")
    
    print("[status]", end=" ", flush=True)
    c,d,e=call("GET","/api/game/status")
    if c==200 and d:
        inner=d.get("data",{})
        pf=inner.get("player_faction",{})
        dr=inner.get("diplomatic_relations",[])
        print(f"round={inner.get('current_round')} 外交={len(dr)}条")
        if not pf: problems.append("player_faction为空")
        if not dr: problems.append("diplomatic_relations为空")
    
    print("[cmds]", end="", flush=True)
    for i,(act,params) in enumerate(actions):
        c,d,e=call("POST","/api/game/command",{"action":act,"params":params,"faction_id":fid})
        if d and d.get("code")==200:
            inner=d.get("data",{}) or {}
            warn=inner.get("warning","")
            print(f"\n    ✓ {act}{' (⚠'+warn+')' if warn else ''}", end="", flush=True)
        else:
            msg=(d or {}).get("msg","") if d else (e or "")
            print(f"\n    ✗ {act}: {msg[:80]}", end="", flush=True)
            if "拦截" in msg or "拒绝" in msg or "无权" in msg:
                problems.append(f"操作{act}被拒绝: {msg[:100]}")
    
    for rnd in [1,2]:
        print(f"\n[advance{rnd}]", end=" ", flush=True)
        t0=time.time()
        c,d,e=call("POST","/api/game/advance-turn")
        dt=time.time()-t0
        if c==200 and d:
            inner=d.get("data",{}) or {}
            ev=inner.get("new_events",[])
            n=len(ev) if isinstance(ev,list) else 0
            print(f"{dt:.1f}s round={inner.get('current_round')} phase={inner.get('phase')} events={n}")
            if n==0: problems.append(f"回合{rnd}推进返回0事件")
            if isinstance(ev,list) and ev:
                for evi in ev[:2]:
                    print(f"      [{evi.get('severity','?')}] {evi.get('title','?')}")
        else:
            problems.append(f"回合{rnd}推进失败: code={c}")
    
    return problems

all_p={}
tests=[
    ("faction_fangguozhen","方国珍",[("trade",{}),("scout",{"target_faction":"faction_zhangshicheng"}),("fortify",{"tile_id":"庆元"}),("recruit",{"amount":1000}),("diplomacy",{"target_faction":"faction_zhangshicheng","type":"improve"})]),
    ("faction_wangbaobao","王保保",[("recruit",{"amount":2000}),("buy_horses",{"amount":100}),("train_troops",{"tile_id":"太原"}),("scout",{"target_faction":"faction_xushouhui"}),("fortify",{"tile_id":"太原"})]),
    ("faction_chenyouliang","陈友谅",[("recruit",{"amount":3000}),("train_troops",{"tile_id":"武昌"}),("scout",{"target_faction":"faction_zhuyuanzhang"}),("relief",{"tile_id":"武昌"}),("fortify",{"tile_id":"江州"})]),
    ("faction_xushouhui","徐寿辉",[("recruit",{"amount":3000}),("develop",{"tile_id":"襄阳","amount":500}),("train_troops",{"tile_id":"襄阳"}),("fortify",{"tile_id":"襄阳"}),("scout",{"target_faction":"faction_chenyouliang"})]),
    ("faction_mobei","漠北诸部",[("raid",{}),("recruit",{"amount":1000}),("train",{}),("buy_horses",{"amount":100}),("scout",{"target_faction":"faction_wangbaobao"})]),
    ("faction_yuan","元廷",[("recruit",{"amount":3000}),("relief",{"tile_id":"大都"}),("tax",{}),("scout",{"target_faction":"faction_xushouhui"}),("purge",{})]),
]
for fid,name,actions in tests:
    try:
        p=test(fid,name,actions)
        all_p[name]=p
        print(f"\n  => {len(p)} problems: {p}")
    except Exception as ex:
        all_p[name]=[f"EXCEPTION: {traceback.format_exc()}"]
        print(f"\n  => EXCEPTION!")

print("\n"+"="*50)
for n,p in all_p.items():
    print(f"\n{n}: {len(p)} problems")
    for pi in p: print(f"  {pi}")

with open("_playthrough_problems_p2.json","w",encoding="utf-8") as f:
    json.dump(all_p,f,ensure_ascii=False,indent=2)
