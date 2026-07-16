"""NPC 配音批量生成 — 38位文臣武将 · 13种 ElevenLabs 音色 · 中文原生合成

用法:
    python tools/generate_npc_voices.py          # 生成全部 NPC
    python tools/generate_npc_voices.py --dry-run # 仅显示映射，不生成
    python tools/generate_npc_voices.py --force   # 强制重新生成
    python tools/generate_npc_voices.py --npc liu_ji,xu_da  # 只生成指定 NPC
"""
import asyncio, json, os, sys, time, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from server.services.tts_service import (
    generate_npc_voice, VOICE_OUTPUT_DIR,
    ELEVENLABS_VOICE_CONFIG, ELEVENLABS_MODEL_TURBO,
)

# ============================================================
# 13 种可用 ElevenLabs 男声 → NPC 智能分配
# 规则: role + personality 关键词 + wisdom/loyalty/ambition 三维
# ============================================================
AVAILABLE_VOICES = {
    # voice_id                                          name     personality-fit
    "pqHfZKP75CvOlQylNhV4": {"name": "Bill",   "desc": "睿智长者", "age": "old",      "fit": ["wise","elder","strategist_high"]},
    "pNInz6obpgDQGcFmaJgB": {"name": "Adam",   "desc": "深沉权威", "age": "middle",   "fit": ["leader","firm","chancellor_high"]},
    "SOYHLrjzK2X1ezoPC6cr": {"name": "Harry",  "desc": "激昂猛将", "age": "young",    "fit": ["fierce","aggressive","general_high_ambition"]},
    "cjVigY5qzO86Huf0OWal": {"name": "Eric",   "desc": "圆滑商贾", "age": "middle",   "fit": ["smooth","diplomat","gentle"]},
    "CwhRBWXzGAHq8TQ4Fs17": {"name": "Roger",  "desc": "慵懒浪客", "age": "middle",   "fit": ["laid_back","rebel","naval"]},
    "JBFqnCBsd6RMkjVDRZzb": {"name": "George", "desc": "温暖布道", "age": "middle",   "fit": ["warm","religious","scholar"]},
    "onwK4e9ZLuTAKqWW03F9": {"name": "Daniel", "desc": "稳重守成", "age": "middle",   "fit": ["steady","chancellor_loyal","british"]},
    "IKne3meq5aSn9XLyUdCD": {"name": "Charlie","desc": "深沉名将", "age": "young",    "fit": ["confident","general_youth","energetic"]},
    "N2lVS1w4EtoT3dr4eOWO": {"name": "Callum", "desc": "沙哑诡秘", "age": "middle",   "fit": ["husky","scheming","trickster"]},
    "nPczCjzI2devNBz1zQrb": {"name": "Brian",  "desc": "深沉共鸣", "age": "middle",   "fit": ["deep","resonant","general_loyal"]},
    "iP95p4xoKVk53GoZ742B": {"name": "Chris",  "desc": "亲切朴实", "age": "middle",   "fit": ["charming","down_to_earth","scholar_low"]},
    "TX3LPaxmHKxFdv7VOQHJ": {"name": "Liam",   "desc": "活力青年", "age": "young",    "fit": ["energetic","youth","social"]},
    "bIHbv24MWmeRgasZH58o": {"name": "Will",   "desc": "乐天逍遥", "age": "young",    "fit": ["relaxed","optimist","hedonist"]},
}

# NPC → voice_id 智能映射规则
def assign_voice(npc: dict) -> dict:
    """根据 NPC 角色类型 + 性格 + 属性 三维匹配最佳音色"""
    role = npc.get("role", "general")
    personality = npc.get("personality", "")
    wisdom = npc.get("wisdom", 70)
    loyalty = npc.get("loyalty", 70)
    ambition = npc.get("ambition", 40)
    speaking = npc.get("speaking_style", "")

    # --- 角色类型分流 ---
    if role == "strategist":
        if wisdom >= 90:
            voice_id = "pqHfZKP75CvOlQylNhV4"  # Bill - 神机军师
            s, sb, st = 0.52, 0.78, 0.0
        elif "传教" in personality or "信仰" in personality:
            voice_id = "JBFqnCBsd6RMkjVDRZzb"  # George - 布道军师
            s, sb, st = 0.50, 0.76, 0.05
        else:
            voice_id = "CwhRBWXzGAHq8TQ4Fs17"  # Roger - 隐逸谋士
            s, sb, st = 0.42, 0.74, 0.06

    elif role == "general":
        if ambition >= 80:
            voice_id = "SOYHLrjzK2X1ezoPC6cr"  # Harry - 野心猛将
            s, sb, st = 0.22, 0.85, 0.18
        elif loyalty >= 90:
            voice_id = "nPczCjzI2devNBz1zQrb"  # Brian - 忠勇宿将
            s, sb, st = 0.52, 0.78, 0.0
        elif wisdom >= 75:
            voice_id = "IKne3meq5aSn9XLyUdCD"  # Charlie - 智勇名将
            s, sb, st = 0.35, 0.78, 0.08
        else:
            voice_id = "pNInz6obpgDQGcFmaJgB"  # Adam - 普通武将
            s, sb, st = 0.45, 0.75, 0.0

    elif role in ("chancellor", "ruler"):
        if ambition >= 70:
            voice_id = "N2lVS1w4EtoT3dr4eOWO"  # Callum - 权臣
            s, sb, st = 0.30, 0.82, 0.10
        elif loyalty >= 80:
            voice_id = "onwK4e9ZLuTAKqWW03F9"  # Daniel - 忠诚宰辅
            s, sb, st = 0.56, 0.74, 0.0
        elif "骄奢" in personality or "享乐" in personality:
            voice_id = "bIHbv24MWmeRgasZH58o"  # Will - 享乐宗室
            s, sb, st = 0.35, 0.72, 0.10
        elif "温和" in personality or "宽厚" in personality:
            voice_id = "iP95p4xoKVk53GoZ742B"  # Chris - 温和文臣
            s, sb, st = 0.50, 0.72, 0.0
        elif "精明" in personality or "干练" in personality:
            voice_id = "cjVigY5qzO86Huf0OWal"  # Eric - 精明辅臣
            s, sb, st = 0.48, 0.76, 0.0
        else:
            voice_id = "onwK4e9ZLuTAKqWW03F9"  # Daniel
            s, sb, st = 0.55, 0.74, 0.0

    elif role == "diplomat":
        voice_id = "cjVigY5qzO86Huf0OWal"  # Eric - 外交说客
        s, sb, st = 0.48, 0.74, 0.0

    elif role == "scholar":
        if wisdom >= 85:
            voice_id = "JBFqnCBsd6RMkjVDRZzb"  # George - 儒雅文宗
            s, sb, st = 0.54, 0.76, 0.0
        else:
            voice_id = "iP95p4xoKVk53GoZ742B"  # Chris - 文臣学者
            s, sb, st = 0.50, 0.72, 0.0

    elif role == "reformer":
        voice_id = "N2lVS1w4EtoT3dr4eOWO"  # Callum - 改革权臣
        s, sb, st = 0.28, 0.82, 0.12

    else:
        voice_id = "nPczCjzI2devNBz1zQrb"  # Brian - 默认
        s, sb, st = 0.48, 0.75, 0.0

    # --- 性格关键词微调（优先级高于角色类型） ---
    # 刚烈/性烈如火 → Harry (激昂猛将)
    if "性烈" in personality or "刚烈" in personality or "勇猛果敢" in personality:
        if ambition >= 50 or loyalty >= 85:
            voice_id = "SOYHLrjzK2X1ezoPC6cr"  # Harry
            s, sb, st = 0.22, 0.85, 0.15
    # 少年英雄 → Charlie (深沉名将青年版)
    if "少年英雄" in personality or "少年" in personality:
        if role == "general":
            voice_id = "IKne3meq5aSn9XLyUdCD"  # Charlie
            s, sb, st = 0.32, 0.78, 0.10
    # 精于算计/算计 → Callum (诡秘谋士)
    if "算计" in personality or "揣摩" in personality:
        if role not in ("strategist",):  # strategist 已有专门映射
            voice_id = "N2lVS1w4EtoT3dr4eOWO"  # Callum
            s, sb, st = 0.30, 0.80, 0.10
    # 沉稳/持重/稳重 → 提高 stability
    if "沉稳" in personality or "持重" in personality or "稳重" in personality:
        s = min(0.65, s + 0.08); st = max(0.0, st - 0.03)
    # 跋扈/骄横 → Harry 或 Callum
    if "跋扈" in personality or "骄横" in personality or "骄奢" in personality:
        if voice_id not in ("SOYHLrjzK2X1ezoPC6cr", "N2lVS1w4EtoT3dr4eOWO"):
            voice_id = "N2lVS1w4EtoT3dr4eOWO"  # Callum
            s, sb, st = 0.28, 0.82, 0.12

    # --- 野心微调 ---
    if ambition >= 70 and voice_id not in ("SOYHLrjzK2X1ezoPC6cr", "N2lVS1w4EtoT3dr4eOWO"):
        st = min(0.25, st + 0.03)

    return {
        "voice_id": voice_id,
        "voice_name": AVAILABLE_VOICES.get(voice_id, {}).get("name", "?"),
        "stability": round(s, 2),
        "similarity_boost": round(sb, 2),
        "style": round(st, 2),
    }


def build_npc_text(npc: dict) -> str:
    """根据 NPC 数据构建朗读文本（中文自我介绍）"""
    name = npc.get("name", "")
    style = npc.get("style_name", "")
    label = npc.get("role_label", "")
    greeting = npc.get("greeting", "")

    # 优先使用 greeting（已有第一人称台词）
    if greeting and len(greeting) >= 10:
        return greeting

    # 构造自我介绍
    full_name = f"{name}"
    if style and style != "不详":
        full_name += f"，字{style}"
    return f"在下{full_name}。{npc.get('personality', '')}。"


# ============================================================
# 主流程
# ============================================================
async def main():
    parser = argparse.ArgumentParser(description="NPC 配音批量生成")
    parser.add_argument("--dry-run", action="store_true", help="仅显示映射，不生成")
    parser.add_argument("--force", action="store_true", help="强制重新生成所有")
    parser.add_argument("--npc", type=str, default="", help="只生成指定 NPC (逗号分隔)")
    parser.add_argument("--limit", type=int, default=0, help="限制生成数量 (调试用)")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 个 NPC")
    args = parser.parse_args()

    # 加载 NPC 数据
    npc_file = ROOT / "server" / "data" / "npc_ministers.json"
    with open(npc_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    npcs = data.get("ministers", [])

    # 排除已有势力配音的君主（他们的 faction_intro.mp3 已生成）
    ruler_npc_ids = {
        "ming_yuzhen", "fang_guozhen", "xushou_hui", "tatar_khan",
        "wang_baobao",  # 王保保有 faction 配音但 NPC 条目独立，保留 NPC 配音
    }
    # 按名字排除（朱元璋/陈友谅/张士诚的 npc_ministers 条目）
    ruler_names = {"朱元璋", "陈友谅", "张士诚"}
    for npc in npcs:
        if npc.get("name") in ruler_names:
            ruler_npc_ids.add(npc["npc_id"])

    # 过滤
    if args.npc:
        target_ids = set(args.npc.split(","))
        npcs = [n for n in npcs if n["npc_id"] in target_ids]
    else:
        npcs = [n for n in npcs if n["npc_id"] not in ruler_npc_ids]

    if args.limit > 0:
        npcs = npcs[args.offset:args.offset + args.limit]
    elif args.offset > 0:
        npcs = npcs[args.offset:]

    total = len(npcs)
    print(f"{'='*70}")
    print(f"  元末逐鹿 — ElevenLabs NPC 角色配音生成")
    print(f"  NPC 总数: {len(data.get('ministers',[]))} | 待生成: {total} (排除{len(ruler_npc_ids)}位君主)")
    print(f"  可用音色: 13 种男声 | Key: {os.environ.get('ELEVENLABS_API_KEY','')[:14]}...")
    print(f"{'='*70}")
    print()

    if args.dry_run:
        print(f"{'npc_id':<22s} {'姓名':<8s} {'角色':<10s} {'音色':<8s} stability style 性格")
        print("-" * 100)
        for npc in npcs:
            v = assign_voice(npc)
            print(f"{npc['npc_id']:<22s} {npc['name']:<8s} {npc.get('role_label',''):<10s} "
                  f"{v['voice_name']:<8s} {v['stability']:.2f}     {v['style']:.2f}  {npc.get('personality','')[:40]}")
        return

    ok = 0
    fail = 0
    skipped = 0
    t0 = time.time()

    for i, npc in enumerate(npcs, 1):
        npc_id = npc["npc_id"]
        name = npc["name"]
        label = npc.get("role_label", npc.get("role", ""))
        personality = npc.get("personality", "")

        v = assign_voice(npc)
        text = build_npc_text(npc)

        print(f"[{i:2d}/{total}] {npc_id:<22s} {name:<6s} {label:<8s} "
              f"→ {v['voice_name']:<8s}(stab={v['stability']:.2f}) ", end="", flush=True)

        t1 = time.time()
        result = await generate_npc_voice(
            npc_name=npc_id,
            text=text,
            personality="neutral",  # 使用自定义 voice_id 覆盖
            force=args.force,
        )

        # generate_npc_voice 使用 personality_config 映射，需要绕过
        # 直接调用底层 _generate_mp3_elevenlabs
        from server.services.tts_service import _generate_mp3_elevenlabs, ELEVENLABS_MODEL_TURBO
        import hashlib

        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        safe_name = "".join(c if c.isalnum() else "_" for c in npc_id)
        filename = f"npc_{safe_name}_{text_hash}.mp3"
        VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = VOICE_OUTPUT_DIR / filename

        # 检查缓存
        if not args.force and output_path.exists() and output_path.stat().st_size > 100:
            kb = output_path.stat().st_size / 1024
            print(f"CACHED ({kb:.0f}KB)")
            skipped += 1
            continue

        success = await _generate_mp3_elevenlabs(
            text=text,
            voice_id=v["voice_id"],
            stability=v["stability"],
            similarity_boost=v["similarity_boost"],
            output_path=str(output_path),
            model=ELEVENLABS_MODEL_TURBO,
            style=v["style"],
        )

        elapsed = time.time() - t1
        if success:
            kb = output_path.stat().st_size / 1024
            print(f"OK ({kb:.0f}KB, {elapsed:.1f}s)")
            ok += 1
        else:
            print(f"FAIL ({elapsed:.1f}s)")
            fail += 1

    total_time = time.time() - t0
    print()
    print(f"{'='*70}")
    print(f"  完成: {ok} OK | {skipped} cached | {fail} FAIL | {total_time:.0f}s")
    print(f"{'='*70}")

    # 统计估算用量
    if ok > 0:
        # 每个 NPC 文本约 30-60 字符
        est_chars = ok * 45
        print(f"  估算字符消耗: ~{est_chars} / 10000 (月免费额度)")
        print(f"  音频目录: {VOICE_OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
