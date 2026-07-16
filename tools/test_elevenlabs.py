"""测试 ElevenLabs TTS 和音色列表（需有效 API Key）"""
import asyncio, aiohttp, json, os

key = os.environ.get("ELEVENLABS_API_KEY", "")
if not key:
    print("[SKIP] No ELEVENLABS_API_KEY found in environment or .env")
    exit(0)

async def test():
    headers = {"xi-api-key": key, "Accept": "application/json"}
    
    # 1. 获取音色列表
    async with aiohttp.ClientSession() as s:
        async with s.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                data = await r.json()
                voices = data.get("voices", [])
                male = [v for v in voices if (v.get("labels",{}).get("gender","") or "").lower() == "male"]
                print(f"[OK] Total voices: {len(voices)}, Male: {len(male)}")
                print(f"\n{'voice_id':<28s} {'name':<20s} {'age':<10s} {'accent':<15s} description")
                print("-" * 120)
                for v in sorted(male, key=lambda x: x["name"]):
                    lab = v.get("labels", {})
                    desc = (lab.get("description", "") or "")[:55]
                    print(f"{v['voice_id']:<28s} {v['name']:<20s} {lab.get('age','?'):<10s} {lab.get('accent','?'):<15s} {desc}")
            else:
                txt = await r.text()
                print(f"[FAIL] Voices HTTP {r.status}: {txt[:200]}")
    
    # 2. 测试 TTS 生成
    print("\n--- Testing TTS (Adam, multilingual_v2) ---")
    test_text = "朕承大元社稷，君临天下。然乱世汹汹，红巾四起。"
    test_voice_id = "pNInz6obpgDQGcFmaJgB"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{test_voice_id}"
    payload = {
        "text": test_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.05, "use_speaker_boost": True},
    }
    async with aiohttp.ClientSession() as s:
        t0 = asyncio.get_event_loop().time()
        h = {**headers, "Content-Type": "application/json", "Accept": "audio/mpeg"}
        async with s.post(url, json=payload, headers=h, timeout=aiohttp.ClientTimeout(total=30)) as r:
            elapsed = asyncio.get_event_loop().time() - t0
            if r.status == 200:
                data = await r.read()
                out = os.path.join(os.path.dirname(__file__), "test_tts_output.mp3")
                with open(out, "wb") as f:
                    f.write(data)
                print(f"[OK] Generated {len(data)/1024:.1f}KB in {elapsed:.1f}s -> {out}")
            else:
                txt = await r.text()
                print(f"[FAIL] TTS HTTP {r.status} ({elapsed:.1f}s): {txt[:300]}")

asyncio.run(test())
