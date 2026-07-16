"""测试 edge-tts 配音生成与状态"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test():
    from server.services.tts_service import (
        generate_faction_voice, list_available_voices, VOICE_OUTPUT_DIR
    )
    
    print(f"Voice output dir: {VOICE_OUTPUT_DIR}")
    print(f"Dir exists: {VOICE_OUTPUT_DIR.exists()}")
    
    # 查看当前状态
    status = list_available_voices()
    ready = sum(1 for v in status if v["status"] == "ready")
    print(f"\n=== Current Voice Status ===")
    print(f"{ready}/{len(status)} factions have voices")
    for v in status:
        size_kb = v["size_bytes"] / 1024 if v["size_bytes"] else 0
        print(f"  {v['faction_id']:30s} | {v['role']:8s} | {v['status']:8s} | {size_kb:.1f}KB | edge: {v['voice_edge']}")
    
    # 强制重新生成一个测试
    print("\n=== Test generate faction_yuan (edge-tts, force=True) ===")
    result = await generate_faction_voice("faction_yuan", force=True, provider="edge")
    print(f"  generated: {result['generated']}")
    print(f"  cached: {result['cached']}")
    print(f"  voice: {result['voice']}")
    print(f"  role: {result['role']}")
    print(f"  size: {result['size_bytes']/1024:.1f}KB" if result["size_bytes"] else "  size: 0")
    print(f"  error: {result['error']}")

asyncio.run(test())
