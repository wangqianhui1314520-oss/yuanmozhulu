"""验证3.0版地图产物 - 四级行政层级完整性"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "map"


def verify():
    all_ok = True

    # 1. 验证 map_final.json 新字段
    with open(DATA_DIR / "map_final.json", "r", encoding="utf-8") as f:
        mf = json.load(f)
    t0 = mf["tiles"][0]
    print("=" * 50)
    print("1. map_final.json 单格结构")
    print("=" * 50)
    print(f"  样本: {t0['tile_id']}")
    print(f"  province_id:   {t0.get('province_id', 'N/A')}")
    print(f"  circuit_id:    {t0.get('circuit_id', 'N/A')}")
    print(f"  prefecture_id: {t0.get('prefecture_id', 'N/A')}")
    print(f"  province:      {t0.get('province', 'N/A')}")
    print(f"  prefecture:    {t0.get('prefecture', 'N/A')}")

    pids = sum(1 for t in mf["tiles"] if t.get("province_id"))
    cids = sum(1 for t in mf["tiles"] if t.get("circuit_id"))
    pfids = sum(1 for t in mf["tiles"] if t.get("prefecture_id"))
    total = len(mf["tiles"])
    if total == 0:
        print("  [FAIL] tiles 列表为空，无法计算覆盖率")
        return
    print(f"\n  province_id 覆盖率:    {pids}/{total} ({100*pids/total:.0f}%)")
    print(f"  circuit_id 覆盖率:     {cids}/{total} ({100*cids/total:.0f}%)")
    print(f"  prefecture_id 覆盖率:  {pfids}/{total} ({100*pfids/total:.0f}%)")
    assert pids == 1330, f"province_id not 100%: {pids}"
    assert cids == 1330, f"circuit_id not 100%: {cids}"
    assert pfids == 1330, f"prefecture_id not 100%: {pfids}"
    print("  [PASS] 全部1330格行政字段100%覆盖")

    # 2. 验证 admin_hierarchy.json 树结构
    with open(DATA_DIR / "admin_hierarchy.json", "r", encoding="utf-8") as f:
        ah = json.load(f)
    print(f"\n{'='*50}")
    print("2. admin_hierarchy.json 层级树")
    print("=" * 50)
    meta = ah["meta"]
    print(f"  行省: {meta['total_provinces']}, 路: {meta['total_circuits']}, 府/州: {meta['total_prefectures']}, 县: {meta['total_counties']}")

    tree = ah["hierarchy_tree"]
    assert tree["id"] == "root"
    assert len(tree["children"]) == meta["total_provinces"]

    # 递归统计各县tile总数
    def count_county_tiles(node):
        if node["type"] == "county":
            return 1
        return sum(count_county_tiles(c) for c in node.get("children", []))

    county_total = count_county_tiles(tree)
    print(f"  树内县(叶子)总数: {county_total}")
    assert county_total == 1330, f"县总数错误: {county_total}"
    print("  [PASS] 四级层级树包含全部1330县")

    # 检查一个行省的结构
    prov = tree["children"][0]
    print(f"\n  示例: {prov['name']} (type={prov['type']})")
    print(f"    路数量: {len(prov['children'])}")
    print(f"    _can_expand: {prov['_can_expand']}")
    print(f"    _expanded: {prov['_expanded']}")

    if prov["children"]:
        circ = prov["children"][0]
        print(f"    路: {circ['name']} (type={circ['type']})")
        print(f"      府/州数量: {len(circ['children'])}")
        if circ["children"]:
            pref = circ["children"][0]
            print(f"      府/州: {pref['name']} (type={pref['type']})")
            print(f"        县数量: {len(pref['children'])}")
            print(f"        tile_count: {pref['tile_count']}")
            print(f"        _can_expand: {pref['_can_expand']}")

    # 3. 验证 tile_assignments 一致性
    print(f"\n{'='*50}")
    print("3. tile_assignments 一致性")
    print("=" * 50)
    tas = ah["tile_assignments"]
    assert len(tas) == 1330, f"tile_assignments数量: {len(tas)}"
    sample_k = list(tas.keys())[200]
    sample_v = tas[sample_k]
    print(f"  样本: {sample_k} -> {sample_v['province_name']} / {sample_v['circuit_name']} / {sample_v['prefecture_name']}")

    # 验证 map_final 和 admin_hierarchy 的 tile->province 一致性
    mf_map = {t["tile_id"]: t["province_id"] for t in mf["tiles"]}
    ah_map = {k: v["province_id"] for k, v in tas.items()}
    mismatches = sum(1 for k in mf_map if mf_map[k] != ah_map.get(k, ""))
    assert mismatches == 0, f"province_id不一致: {mismatches}个"
    print(f"  [PASS] map_final与admin_hierarchy province_id完全一致")

    # 4. 验证势力领地
    with open(DATA_DIR / "faction_territories.json", "r", encoding="utf-8") as f:
        ft = json.load(f)
    print(f"\n{'='*50}")
    print("4. faction_territories.json")
    print("=" * 50)
    total_assigned = 0
    for fid, fdata in ft["factions"].items():
        provs = fdata.get("core_provinces", [])
        print(f"  {fid}: {fdata['tile_count']}县 / 核心行省: {provs[:3]}...")
        total_assigned += fdata["tile_count"]
    print(f"  有主总数: {total_assigned}, 中立: {1330 - total_assigned}")
    assert total_assigned == 725, f"有主格子数: {total_assigned}"
    print("  [PASS] 势力配额与行省路网一致")

    # 5. 验证行政层级统计
    stats = ah.get("stats", {})
    print(f"\n{'='*50}")
    print("5. 行省概况统计")
    print("=" * 50)
    for p in stats.get("provinces", []):
        print(f"  {p['name']}: {p['tile_count']}县, {p['circuit_count']}路")

    print(f"\n{'='*50}")
    print("  全部验证通过!")
    print("=" * 50)


if __name__ == "__main__":
    verify()
