"""
元末逐鹿 3.0 - AI 语音合成服务

使用 Microsoft Edge TTS (edge-tts) 为九大势力角色生成个性化配音。
每个角色根据身份/性格/台词匹配不同的音色和语调参数。
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import tempfile
from pathlib import Path

logger = logging.getLogger("yuanmo.tts")

# 音频输出目录（Vite 静态资源目录）
VOICE_OUTPUT_DIR = Path(__file__).parent.parent.parent / "frontend" / "public" / "data" / "map" / "voice"

# ============================================================
# 九大势力角色 × AI 音色配置
# edge-tts 仅提供 4 个 zh-CN 男声，通过 rate(语速)/pitch(音高) 区分性格
# 每对共享 base 音色的角色通过差异化的 rate/pitch 塑造独立人格
# ============================================================
FACTION_VOICE_CONFIG: dict[str, dict] = {
    "faction_yuan": {
        "voice": "zh-CN-YunxiNeural",
        "rate": "-10%",
        "pitch": "-4Hz",
        "role": "大元皇帝",
        "desc": "沉稳凝重 · 帝国将倾的苍凉帝王",
    },
    "faction_zhuyuanzhang": {
        "voice": "zh-CN-YunyangNeural",
        "rate": "-3%",
        "pitch": "+0Hz",
        "role": "吴国公",
        "desc": "内敛坚毅 · 布衣提剑的草莽雄主",
    },
    "faction_chenyouliang": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "+8%",
        "pitch": "+5Hz",
        "role": "汉帝",
        "desc": "激昂锐利 · 野心勃勃的枭雄之声",
    },
    "faction_zhangshicheng": {
        "voice": "zh-CN-YunxiaNeural",
        "rate": "-5%",
        "pitch": "-2Hz",
        "role": "周王",
        "desc": "从容温厚 · 富甲江南的盐商之主",
    },
    "faction_fangguozhen": {
        "voice": "zh-CN-YunxiNeural",
        "rate": "+5%",
        "pitch": "+2Hz",
        "role": "浙东节度",
        "desc": "潇洒不羁 · 纵横海上的弄潮枭雄",
    },
    "faction_xushouhui": {
        "voice": "zh-CN-YunyangNeural",
        "rate": "-6%",
        "pitch": "-2Hz",
        "role": "天完皇帝",
        "desc": "庄重悲悯 · 弥勒降世的红巾明王",
    },
    "faction_mingyuzhen": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "-8%",
        "pitch": "-3Hz",
        "role": "大夏皇帝",
        "desc": "沉稳持重 · 蜀道天险的守成之君",
    },
    "faction_wangbaobao": {
        "voice": "zh-CN-YunxiaNeural",
        "rate": "+3%",
        "pitch": "+4Hz",
        "role": "河南王",
        "desc": "刚毅豪迈 · 大元最后的铁骑名将",
    },
    "faction_mobei": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "+14%",
        "pitch": "+8Hz",
        "role": "草原大汗",
        "desc": "粗犷豪放 · 草原雄鹰的驰骋之音",
    },
}

# 台词文件路径（备选：从 factions.json 读取）
FACTIONS_JSON_PATH = Path(__file__).parent.parent / "config" / "factions.json"


def _load_faction_voice_text(faction_id: str) -> str | None:
    """从 factions.json 加载该势力的 voice（开场台词）"""
    try:
        if FACTIONS_JSON_PATH.exists():
            data = json.loads(FACTIONS_JSON_PATH.read_text(encoding="utf-8"))
            factions = data.get("factions", {})
            faction = factions.get(faction_id, {})
            return faction.get("voice", None)
    except Exception as e:
        logger.warning(f"加载 factions.json 失败: {e}")
    return None


# 兜底台词（与前端 BUILTIN_FACTIONS 保持一致）
FALLBACK_VOICE_TEXT: dict[str, str] = {
    "faction_yuan": "朕承大元社稷，君临天下。然乱世汹汹，红巾四起。卿既来辅朕，当重整河山，中兴大元。",
    "faction_zhuyuanzhang": "孤起于淮右，布衣提三尺剑，渡江取金陵。高筑墙，广积粮，缓称王。今日择我入世，必当驱除鞑虏，恢复中华。",
    "faction_chenyouliang": "朕据荆楚，拥水师之利，志在一统。朱元璋、张士诚皆不足惧。择我者，当共图九五之尊。",
    "faction_zhangshicheng": "吾据江南膏腴之地，富甲一方。然天下未定，岂能偏安？愿与卿共治吴越，以成霸业。",
    "faction_fangguozhen": "海上有舟，舟山有兵。吾以海贸立世，进退自如。卿若随我，纵横浙东，何愁大事不成。",
    "faction_xushouhui": "弥勒降世，明王出世。吾举义旗，为天下苍生。卿来辅我，当共复光明世界。",
    "faction_mingyuzhen": "孤据蜀道天险，守大夏之土。民安物阜，关河稳固。卿来辅我，可共保西陲，以观天下之变。",
    "faction_wangbaobao": "吾乃扩廓帖木儿，大元最后的名将。铁骑所向，天下莫敢当。卿若随我，共保大元江山。",
    "faction_mobei": "草原雄鹰，驰骋万里。漠北诸部，铁骑所至，皆为牧场。卿若随我，纵横大漠，逐鹿中原。",
}


def get_voice_config(faction_id: str) -> dict | None:
    """获取指定势力的 TTS 音色配置"""
    return FACTION_VOICE_CONFIG.get(faction_id)


def get_voice_text(faction_id: str) -> str:
    """获取指定势力的开场台词"""
    text = _load_faction_voice_text(faction_id)
    return text or FALLBACK_VOICE_TEXT.get(faction_id, "")


async def _generate_mp3(text: str, voice: str, rate: str, pitch: str, output_path: str) -> bool:
    """使用 edge-tts 生成单个 MP3 文件"""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(output_path)
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        logger.info(f"[TTS] 生成成功: {output_path} ({file_size} bytes) voice={voice} rate={rate} pitch={pitch}")
        return True
    except Exception as e:
        logger.error(f"[TTS] 生成失败: {output_path} — {e}")
        return False


async def generate_faction_voice(faction_id: str, force: bool = False) -> dict:
    """
    为指定势力生成 AI 配音 MP3 文件。
    
    返回: { faction_id, output_path, generated, cached, voice, role, size_bytes, error }
    """
    result = {
        "faction_id": faction_id,
        "output_path": "",
        "generated": False,
        "cached": False,
        "voice": "",
        "role": "",
        "desc": "",
        "size_bytes": 0,
        "error": None,
    }

    voice_cfg = get_voice_config(faction_id)
    if not voice_cfg:
        result["error"] = f"未找到势力 {faction_id} 的音色配置"
        return result

    result["voice"] = voice_cfg["voice"]
    result["role"] = voice_cfg["role"]
    result["desc"] = voice_cfg.get("desc", "")

    # 输出路径: frontend/public/data/map/voice/{faction_id}_intro.mp3
    VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = VOICE_OUTPUT_DIR / f"{faction_id}_intro.mp3"
    result["output_path"] = str(output_path)

    # 检查缓存
    if not force and output_path.exists() and output_path.stat().st_size > 100:
        result["cached"] = True
        result["generated"] = True
        result["size_bytes"] = output_path.stat().st_size
        logger.info(f"[TTS] 使用缓存: {output_path}")
        return result

    # 获取台词并生成
    text = get_voice_text(faction_id)
    if not text:
        result["error"] = "未找到势力台词"
        return result

    t0 = time.time()
    success = await _generate_mp3(
        text=text,
        voice=voice_cfg["voice"],
        rate=voice_cfg["rate"],
        pitch=voice_cfg["pitch"],
        output_path=str(output_path),
    )

    elapsed = time.time() - t0
    if success:
        result["generated"] = True
        result["size_bytes"] = output_path.stat().st_size
        logger.info(f"[TTS] {faction_id} 生成完成 (耗时 {elapsed:.1f}s, {result['size_bytes']} bytes)")
    else:
        result["error"] = "edge-tts 生成失败"
    return result


async def generate_all_faction_voices(force: bool = False) -> list[dict]:
    """批量生成全部九大势力的 AI 配音"""
    tasks = [generate_faction_voice(fid, force=force) for fid in FACTION_VOICE_CONFIG]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            faction_id = list(FACTION_VOICE_CONFIG.keys())[i]
            final.append({"faction_id": faction_id, "error": str(r), "generated": False})
        else:
            final.append(r)
    return final


def list_available_voices() -> list[dict]:
    """列出所有已生成的势力配音文件状态"""
    result = []
    for faction_id, cfg in FACTION_VOICE_CONFIG.items():
        mp3_path = VOICE_OUTPUT_DIR / f"{faction_id}_intro.mp3"
        status = "ready" if (mp3_path.exists() and mp3_path.stat().st_size > 100) else "missing"
        result.append({
            "faction_id": faction_id,
            "role": cfg["role"],
            "voice": cfg["voice"],
            "desc": cfg.get("desc", ""),
            "status": status,
            "size_bytes": mp3_path.stat().st_size if status == "ready" else 0,
        })
    return result
