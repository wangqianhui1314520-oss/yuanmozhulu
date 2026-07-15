"""Debug: check faction tile_id validity"""
import json, sys
sys.path.insert(0, '.')
from server.map.hex_grid import is_valid_coord, HexCoord

ft = json.load(open('server/data/map/faction_territories.json', 'r', encoding='utf-8'))

all_keys = set()
for fid in ft['factions']:
    for t in ft['factions'][fid]['tiles']:
        all_keys.add(t)

print(f'Total unique faction tile IDs: {len(all_keys)}')

invalid = []
for t in sorted(all_keys):
    try:
        parts = t[4:].split('_')
        c, r = int(parts[0]), int(parts[1])
        if not is_valid_coord(HexCoord(c, r)):
            invalid.append(t)
    except (IndexError, ValueError):
        invalid.append(t)

valid = len(all_keys) - len(invalid)
print(f'Valid: {valid}, Invalid: {len(invalid)}')
if invalid:
    print(f'Sample invalid: {invalid[:10]}')

# Also check in the full factions data
total_tiles = sum(len(v['tiles']) for v in ft['factions'].values())
print(f'Total tiles in factions data: {total_tiles}')
print(f'Total unique: {len(all_keys)}')
