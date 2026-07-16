"""诊断 AI 调用状态 - 详细版"""
import asyncio, httpx, time, json

async def test():
    pid = f'diag_{int(time.time())}'
    async with httpx.AsyncClient(headers={'X-Player-ID': pid}) as c:
        # 1. 创建游戏
        r = await c.post('http://127.0.0.1:8800/api/game/init',
                         json={'faction_id': 'faction_yuan', 'mode': 'player_turn'})
        data = r.json()
        print('1. Init:', data.get('code'), data.get('msg'))
        
        # 获取 faction config 结构
        r = await c.get('http://127.0.0.1:8800/api/config/factions')
        fc = r.json().get('data', {})
        factions_dict = fc.get('factions', {})
        print(f'   Config has "factions" key: {"factions" in fc}')
        print(f'   Config faction IDs: {list(factions_dict.keys())}')
        
        # 2. 推进回合
        t0 = time.time()
        r = await c.post('http://127.0.0.1:8800/api/game/advance-turn', json={})
        elapsed = time.time() - t0
        resp_data = r.json().get('data', {})
        summary = resp_data.get('round_summary', {})
        phases = summary.get('phases', {})
        ai_step = phases.get('ai_step', {})
        
        print(f'\n2. Turn completed in {elapsed:.1f}s')
        
        # 检查所有 phase keys in ai_step
        if isinstance(ai_step, dict):
            for key in sorted(ai_step.keys()):
                val = ai_step[key]
                if isinstance(val, dict):
                    if key == 'A2_warlords':
                        print(f'   {key}: agents_ran={val.get("agents_ran",0)}, results={len(val.get("results",[]))}')
                        for r in val.get('results', [])[:3]:
                            resp = r.get('full_response', '') if isinstance(r, dict) else ''
                            fid = r.get('faction_id', '?') if isinstance(r, dict) else '?'
                            print(f'     [{fid}] response_len={len(resp)}')
                    elif key in ('A1_advisor', 'A4_espionage', 'A6_diplomacy', 'A5_events', 'A5_situation',
                               'A7_royal', 'A8_history', 'A8_faction_chronicles', 'court_debate',
                               'public_sentiment', 'general_chronicles', 'game_phase', 'mcts_precompute',
                               'event_bus'):
                        size = len(json.dumps(val, ensure_ascii=False))
                        klist = list(val.keys())[:5]
                        print(f'   {key}: size={size}B, keys={klist}')
                    else:
                        print(f'   {key}: dict with keys={list(val.keys())[:5]}')
                else:
                    print(f'   {key}: {str(val)[:80]} (type={type(val).__name__})')
        
        ai_text = json.dumps(ai_step, ensure_ascii=False) if isinstance(ai_step, dict) else str(ai_step)
        print(f'\n   Full ai_step size: {len(ai_text)} chars')
        degraded = ai_step.get('degraded_from', 'none') if isinstance(ai_step, dict) else 'N/A'
        print(f'   Degraded from: {degraded}')
        
        # 3. 检查 agent stats
        r = await c.get('http://127.0.0.1:8800/api/agent/stats')
        stats = r.json().get('data', {})
        print(f'\n3. Agent total_calls: {stats.get("total_calls", 0)}')
        agents_list = stats.get('agents', [])
        if isinstance(agents_list, list):
            for a in agents_list:
                if isinstance(a, dict):
                    print(f'   {a.get("agent_id","?")}: calls={a.get("call_count",0)}')
                else:
                    print(f'   {a}')
        else:
            print(f'   agents type: {type(agents_list).__name__}')

asyncio.run(test())
