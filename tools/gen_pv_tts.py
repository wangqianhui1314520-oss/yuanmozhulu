"""Generate Chinese TTS narration for 元末逐鹿 PV using edge-tts."""
import asyncio
import json
import os
import edge_tts

VOICE = "zh-CN-YunxiNeural"
OUT_DIR = r"d:\AI\元末逐鹿\videos\yuanmo-promo\audio"
OUT_FILE = os.path.join(OUT_DIR, "narration.mp3")
META_FILE = r"d:\AI\元末逐鹿\videos\yuanmo-promo\audio_meta.json"

LINES = [
    "公元一三五一年，红巾军起义，天下大乱。",
    "蒙古铁骑的余威散尽，帝国的版图燃烧殆尽。十八路反王，六方割据，逐鹿中原。",
    "朱元璋、陈友谅、张士诚……六方诸侯，各怀天命。而你，将是其中之一。",
    "元末逐鹿 —— 一款元末历史大战略游戏。",
    "六边形战略沙盘，纵横千里江山。十四行省，四百九十六座城池 —— 每一步，都牵动天下。",
    "以帝王口吻发号施令 —— 自然语言圣旨系统。你的每一道圣旨，都将化为千军万马。",
    "经济、军事、外交、朝堂、城建、国策 —— 六大维度，环环相扣，牵一发而动全身。",
    "十大AI智能体，各怀谋略。MCTS博弈树推演，兰彻斯特战斗方程 —— 你的对手，绝非等闲。",
    "战争迷雾遮天蔽日，补给线千里绵延。你不只要打赢一场仗 —— 你要打赢整场战争。",
    "每一个决策，都将改变历史。北伐中原，一统天下 —— 还是偏安一隅，苟且偷生？",
    "元末逐鹿。",
    "天命，由你书写。元末逐鹿 —— 即刻开启你的帝王史诗。",
]


async def synthesize_line(voice: str, text: str, out_path: str):
    """Synthesize one line to an audio file."""
    communicate = edge_tts.Communicate(text, voice, rate="-5%")
    await communicate.save(out_path)
    return out_path


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Generate individual lines
    tasks = []
    for i, line in enumerate(LINES):
        out = os.path.join(OUT_DIR, f"line_{i+1:02d}.mp3")
        tasks.append(synthesize_line(VOICE, line, out))

    results = await asyncio.gather(*tasks)
    print(f"Generated {len(results)} audio files")

    # Generate combined narration
    combined_out = os.path.join(OUT_DIR, "narration_full.mp3")
    combined_text = " ".join(LINES)
    communicate = edge_tts.Communicate(combined_text, VOICE, rate="-5%")
    await communicate.save(combined_out)
    print(f"Combined narration: {combined_out}")

    # Update audio meta for hyperframes
    meta = {
        "bgm": None,
        "voices": [
            {
                "file": "audio/narration_full.mp3",
                "provider": "edge-tts",
                "voice": VOICE,
                "total_duration_s": len(combined_text) * 0.25,  # rough estimate ~60s
            }
        ],
        "sfx": [],
        "narration_file": "audio/narration_full.mp3",
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Updated {META_FILE}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
