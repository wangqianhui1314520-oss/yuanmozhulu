"""诊断 AI 调用状态"""
import asyncio, httpx, time, json

async def test():
    pid = f'diag_{int(time.time())}'
    async with httpx.AsyncClient(headers={'X-Player-ID': pid}) as c:
        # 1. 创建游戏
        r = await c.post('http://127.0.0.1:8800/api/game/init',
                         json={'faction_id': 'faction_yuan', 'mode': 'player_turn'})
        data = r.json()
        print('1. Init:', data.get('code'), data.get('msg'))

        # 2. 推进回合并观察耗时
        t0 = time.time()
        r = await c.post('http://127.0.0.1:8800/api/game/advance-turn', json={})
        elapsed = time.time() - t0
        resp_data = r.json().get('data', {})
        summary = resp_data.get('round_summary', {})
        phases = summary.get('phases', {})
        ai_step = phases.get('ai_step', {})
        print(f'2. Turn completed in {elapsed:.1f}s')
        print(f'   AI step keys: {list(ai_step.keys())[:8]}')
        print(f'   AI degraded_from: {ai_step.get("degraded_from", "none")}')
        print(f'   Events: {len(resp_data.get("new_events", []))}')

        # 检查 A2 warlord 结果
        a2 = phases.get('A2_warlords', {})
        print(f'   A2 agents_ran: {a2.get("agents_ran", 0)}')
        results = a2.get('results', [])
        non_empty = sum(1 for r in results if r.get('full_response', '').strip())
        print(f'   A2 non_empty: {non_empty}/{len(results)}')
        for r in results[:2]:
            print(f'     [{r.get("faction_id", "?")}] response_len={len(r.get("full_response", ""))} preview={r.get("full_response", "")[:80]}')

        # 3. 检查 agent stats
        r = await c.get('http://127.0.0.1:8800/api/agent/stats')
        stats = r.json().get('data', {})
        print(f'3. Agent stats: total_calls={stats.get("total_calls", 0)}')

        # 4. 检查 API key 状态
        r = await c.get('http://127.0.0.1:8800/api/config/api-key-status')
        key_status = r.json().get('data', {})
        print(f'4. API key: configured={key_status.get("configured")}, ai_available={key_status.get("ai_available")}')

if __name__ == '__main__':
    asyncio.run(test())
