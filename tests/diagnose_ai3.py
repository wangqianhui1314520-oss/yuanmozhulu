"""诊断 AI - 查看实际 LLM 响应内容"""
import asyncio, httpx, time, json

async def test():
    pid = f'diag_{int(time.time())}'
    async with httpx.AsyncClient(headers={'X-Player-ID': pid}) as c:
        # 创建游戏 + 推进回合
        await c.post('http://127.0.0.1:8800/api/game/init',
                     json={'faction_id': 'faction_yuan', 'mode': 'player_turn'})
        r = await c.post('http://127.0.0.1:8800/api/game/advance-turn', json={})
        resp_data = r.json().get('data', {})
        phases = resp_data.get('round_summary', {}).get('phases', {})
        ai_step = phases.get('ai_step', {})
        
        # 检查 A2 warlord detailed results
        a2 = ai_step.get('A2_warlords', {})
        print(f'A2 agents_ran: {a2.get("agents_ran", 0)}')
        for r in a2.get('results', []):
            if isinstance(r, dict):
                fid = r.get('faction_id', '?')
                resp = r.get('full_response', '')
                ds = r.get('decision_summary', '')
                llm_ok = r.get('llm_ok', '?')
                print(f'\n[{fid}]')
                print(f'  llm_ok: {llm_ok}')
                print(f'  full_response type: {type(resp).__name__}')
                print(f'  full_response len: {len(str(resp))}')
                print(f'  full_response: {repr(str(resp)[:200])}')
                print(f'  decision_summary: {ds[:100]}')
        
        # Check A1 also
        a1 = ai_step.get('A1_advisor', {})
        if isinstance(a1, dict):
            resp = a1.get('response', a1.get('full_response', ''))
            print(f'\n[A1] response: {str(resp)[:200]}')

asyncio.run(test())
