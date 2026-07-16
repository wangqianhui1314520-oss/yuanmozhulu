"""一键重新生成全部九大势力 ElevenLabs 配音"""
import asyncio, sys, os, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env 中的 API Key
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

async def main():
    from server.services.tts_service import generate_faction_voice, ELEVENLABS_VOICE_CONFIG

    factions = list(ELEVENLABS_VOICE_CONFIG.keys())
    total = len(factions)
    ok = 0
    fail = 0
    t0 = time.time()

    print(f"{'='*60}")
    print(f"  元末逐鹿 — ElevenLabs 九大势力配音生成")
    print(f"{'='*60}")
    print()

    for i, fid in enumerate(factions, 1):
        cfg = ELEVENLABS_VOICE_CONFIG[fid]
        voice = cfg.get("voice_id", "?")[:12]
        role = cfg.get("role", fid)
        desc = cfg.get("desc", "")

        print(f"[{i}/{total}] {fid} ({role})")
        print(f"        {desc}")
        print(f"        voice_id={voice}... stability={cfg['stability']:.2f} style={cfg['style']:.2f}")
        print(f"        Generating...", end=" ", flush=True)

        t1 = time.time()
        result = await generate_faction_voice(fid, force=True, provider="elevenlabs")
        elapsed = time.time() - t1

        if result.get("generated"):
            kb = result.get("size_bytes", 0) / 1024
            print(f"OK ({kb:.1f}KB, {elapsed:.1f}s)")
            ok += 1
        else:
            err = result.get("error", "unknown")
            print(f"FAIL — {err}")
            fail += 1

    total_time = time.time() - t0
    print()
    print(f"{'='*60}")
    print(f"  完成: {ok}/{total} 成功, {fail} 失败 ({total_time:.1f}s)")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
