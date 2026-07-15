"""Quick test of edict execute API"""
import httpx, json, asyncio

async def test():
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            'http://localhost:8800/api/edict/execute',
            json={'edict_text': '征兵三千', 'faction_id': 'faction_fangguozhen'}
        )
        data = resp.json()
        ai = data.get('data', {}).get('ai_analysis', {})
        exe = data.get('data', {}).get('execution', {})
        print('code:', data.get('code'))
        print('msg:', data.get('msg', ''))
        print('ai_generated:', ai.get('ai_generated'))
        print('intent:', str(ai.get('intent_analysis', ''))[:100])
        print('commands_count:', ai.get('commands_count'))
        print('executed:', exe.get('total_executed'))
        print('failed:', exe.get('total_failed'))
        for e in exe.get('executed', []):
            r = e.get('result', {})
            if isinstance(r, dict):
                print('  OK:', e['action'], '->', r.get('message', ''))
        for f in exe.get('failed', []):
            print('  FAIL:', f.get('action'), '->', f.get('reason', ''))

asyncio.run(test())
