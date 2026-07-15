# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import urllib.request, json

def post(path, data, timeout=30):
    url = f'http://127.0.0.1:8800/api{path}'
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    r = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(r.read().decode('utf-8'))

def get(path):
    url = f'http://127.0.0.1:8800/api{path}'
    r = urllib.request.urlopen(url, timeout=30)
    return json.loads(r.read().decode('utf-8'))

# 1. 检查 tile_yingtian 是否存在
print('=== 地图地块ID检查 ===')
r = get('/map/tiles')
tiles = r.get('data', {}).get('tiles', {})
sample_keys = list(tiles.keys())[:10]
print(f'地块总数: {len(tiles)}')
print(f'前10个地块ID: {sample_keys}')
# 搜索应天府
yingtian_keys = [k for k in tiles.keys() if 'yingtian' in k.lower()]
print(f'包含yingtian的地块: {yingtian_keys}')

# 尝试找首都/应天府
for k, v in tiles.items():
    if isinstance(v, dict):
        name = v.get('name', '')
        if '应天' in str(name) or 'yingtian' in str(name).lower():
            print(f'找到应天府: key={k}, data={v}')
            break
else:
    print('未找到应天府，搜索含capital的地块...')
    for k, v in tiles.items():
        if isinstance(v, dict) and v.get('is_capital'):
            print(f'首都: key={k}, data={v}')
            break

# 2. 检查世界状态中势力数据
print('\n=== 势力数据详情 ===')
r = get('/game/status')
ws = r.get('data', {}).get('world_state', {})
factions = ws.get('factions', {})
for fid, f in factions.items():
    if fid == 'faction_zhuyuanzhang':
        # 只取非列表/非字典字段
        simple = {}
        for k, v in f.items():
            if not isinstance(v, (list, dict)):
                simple[k] = v
            elif isinstance(v, list):
                simple[k] = f'list({len(v)} items)'
            elif isinstance(v, dict):
                simple[k] = f'dict({len(v)} keys)'
        print(f'朱元璋数据: {json.dumps(simple, ensure_ascii=False)}')
        print(f'领地tiles前5个: {f.get("tiles", [])[:5]}')
        break

# 3. 检查init返回的mode
print('\n=== Init返回值检查 ===')
r = post('/game/init', {'faction_id': 'faction_zhuyuanzhang', 'mode': 'player_turn'})
d = r.get('data', {})
print(f'mode字段: {d.get("mode")}')
print(f'init返回的所有顶层key: {list(d.keys())}')
# 检查是否有 player_turn 相关
for k, v in d.items():
    if 'mode' in str(k).lower() or 'turn' in str(k).lower() or 'player' in str(k).lower():
        print(f'  相关字段 {k}: {v}')

# 4. 检查strategic-advice
print('\n=== 战略建议返回详情 ===')
r = post('/agent/strategic-advice', {'faction_id': 'faction_zhuyuanzhang'}, timeout=120)
d = r.get('data', {})
print(f'strategic-advice返回keys: {list(d.keys())}')
for k in ['response', 'advice', 'analysis', 'content', 'text']:
    if d.get(k):
        print(f'  字段 {k}: {str(d.get(k))[:300]}')
        break

# 5. 检查存档列表
print('\n=== 存档列表 ===')
r = get('/save/list')
print(f'存档返回: {json.dumps(r, ensure_ascii=False)[:500]}')

# 6. 检查所有势力是否有领地
print('\n=== 势力领地检查 ===')
for fid, f in factions.items():
    name = f.get('name', fid)
    tiles_list = f.get('tiles', [])
    print(f'  {name}: tiles={len(tiles_list)}, troops={f.get("troops")}')
    if len(tiles_list) == 0:
        print(f'    >>> 无领地!')
