"""
元末逐鹿 3.0 - AI 语音合成服务

支持双提供商：
  - edge-tts（免费，Microsoft Edge TTS，默认）
  - elevenlabs（高品质，需 API Key，https://elevenlabs.io）

每个角色根据身份/性格/台词匹配不同的音色和语调参数。
ElevenLabs 模式下使用 5 种不同 voice_id + stability/similarity 差异化塑造 9 大势力人声。
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import tempfile
import hashlib
from contextvars import ContextVar
from pathlib import Path

logger = logging.getLogger("yuanmo.tts")

# ============================================================
# ElevenLabs API Key 管理（ContextVar per-session 隔离 + .env 兜底）
# ============================================================
_current_elevenlabs_key: ContextVar[str] = ContextVar("elevenlabs_key", default="")

def set_elevenlabs_key(key: str):
    """由中间件/API端点调用，设置当前请求的 ElevenLabs API Key"""
    _current_elevenlabs_key.set(key)

def get_elevenlabs_key() -> str:
    """获取当前会话的 ElevenLabs API Key，优先读 ContextVar，回退环境变量"""
    key = _current_elevenlabs_key.get()
    if key:
        return key
    return os.environ.get("ELEVENLABS_API_KEY", "")

# ============================================================
# ElevenLabs 模型选择
# ============================================================
ELEVENLABS_MODEL_DEFAULT = "eleven_multilingual_v2"       # 品质最优，29 语言含中文
ELEVENLABS_MODEL_TURBO = "eleven_turbo_v2_5"              # 低延迟，32 语言
ELEVENLABS_MODEL_FLASH = "eleven_flash_v2_5"              # 实时，适用预览

ELEVENLABS_MODEL_MAP = {
    "quality": ELEVENLABS_MODEL_DEFAULT,
    "turbo": ELEVENLABS_MODEL_TURBO,
    "flash": ELEVENLABS_MODEL_FLASH,
}

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


# ============================================================
# ElevenLabs 音色映射 — 九大势力 × 九种独立音色
#
# voice_id 来源：账户实际可用男声（https://elevenlabs.io/app/voice-lab）
# 每个势力通过 stability(稳定性)/similarity_boost(相似度)/style(夸张度) 塑造性格
#
# stability 低 → 更富有表现力（激昂/粗犷用低值）
# stability 高 → 更平稳一致（庄重/沉稳用高值）
# ============================================================
# 九种独立 ElevenLabs 男声：
#   Bill    (pqHfZKP75CvOlQylNhV4) — 睿智沉稳·老年智者声
#   Adam    (pNInz6obpgDQGcFmaJgB) — 深沉权威·中年霸主声
#   Harry   (SOYHLrjzK2X1ezoPC6cr) — 激昂好战·青年武士声
#   Eric    (cjVigY5qzO86Huf0OWal) — 圆滑可信·中年商贾声
#   Roger   (CwhRBWXzGAHq8TQ4Fs17) — 慵懒不羁·中年浪客声
#   George  (JBFqnCBsd6RMkjVDRZzb) — 温暖故事·中年布道声
#   Daniel  (onwK4e9ZLuTAKqWW03F9) — 稳重播报·中年守成声
#   Charlie (IKne3meq5aSn9XLyUdCD) — 深沉自信·青年猛将声
#   Callum  (N2lVS1w4EtoT3dr4eOWO) — 沙哑诡秘·中年枭雄声
# ============================================================
ELEVENLABS_VOICE_CONFIG: dict[str, dict] = {
    "faction_yuan": {
        "voice_id": "pqHfZKP75CvOlQylNhV4",   # Bill — 睿智苍凉的老皇帝
        "role": "大元皇帝",
        "desc": "沉稳凝重 · 帝国将倾的苍凉帝王",
        "stability": 0.45, "similarity_boost": 0.78, "style": 0.03,
    },
    "faction_zhuyuanzhang": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",   # Adam — 深沉坚毅的布衣天子
        "role": "吴国公",
        "desc": "内敛坚毅 · 布衣提剑的草莽雄主",
        "stability": 0.50, "similarity_boost": 0.75, "style": 0.0,
    },
    "faction_chenyouliang": {
        "voice_id": "SOYHLrjzK2X1ezoPC6cr",   # Harry — 激昂好战的枭雄
        "role": "汉帝",
        "desc": "激昂锐利 · 野心勃勃的枭雄之声",
        "stability": 0.28, "similarity_boost": 0.82, "style": 0.15,
    },
    "faction_zhangshicheng": {
        "voice_id": "cjVigY5qzO86Huf0OWal",   # Eric — 圆滑可信的盐商
        "role": "周王",
        "desc": "从容温厚 · 富甲江南的盐商之主",
        "stability": 0.55, "similarity_boost": 0.70, "style": 0.0,
    },
    "faction_fangguozhen": {
        "voice_id": "CwhRBWXzGAHq8TQ4Fs17",   # Roger — 慵懒不羁的海上浪子
        "role": "浙东节度",
        "desc": "潇洒不羁 · 纵横海上的弄潮枭雄",
        "stability": 0.35, "similarity_boost": 0.72, "style": 0.10,
    },
    "faction_xushouhui": {
        "voice_id": "JBFqnCBsd6RMkjVDRZzb",   # George — 温暖悲悯的布道者
        "role": "天完皇帝",
        "desc": "庄重悲悯 · 弥勒降世的红巾明王",
        "stability": 0.50, "similarity_boost": 0.76, "style": 0.05,
    },
    "faction_mingyuzhen": {
        "voice_id": "onwK4e9ZLuTAKqWW03F9",   # Daniel — 稳重持守的蜀中王
        "role": "大夏皇帝",
        "desc": "沉稳持重 · 蜀道天险的守成之君",
        "stability": 0.58, "similarity_boost": 0.73, "style": 0.0,
    },
    "faction_wangbaobao": {
        "voice_id": "IKne3meq5aSn9XLyUdCD",   # Charlie — 深沉自信的末代名将
        "role": "河南王",
        "desc": "刚毅豪迈 · 大元最后的铁骑名将",
        "stability": 0.35, "similarity_boost": 0.78, "style": 0.10,
    },
    "faction_mobei": {
        "voice_id": "N2lVS1w4EtoT3dr4eOWO",   # Callum — 沙哑粗犷的草原之主
        "role": "草原大汗",
        "desc": "粗犷豪放 · 草原雄鹰的驰骋之音",
        "stability": 0.22, "similarity_boost": 0.85, "style": 0.22,
    },
}
# 默认 voice_id（Adam — 深沉权威男声）
ELEVENLABS_DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"

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


async def _generate_mp3_elevenlabs(
    text: str,
    voice_id: str,
    stability: float,
    similarity_boost: float,
    output_path: str,
    model: str = ELEVENLABS_MODEL_DEFAULT,
    style: float = 0.0,
) -> bool:
    """使用 ElevenLabs API 生成 MP3 文件
    
    Args:
        text: 要合成的中文文本
        voice_id: ElevenLabs 音色 ID
        stability: 稳定性 0.0-1.0（低=更表现力，高=更平稳）
        similarity_boost: 相似度 0.0-1.0（高=更贴近原声）
        output_path: MP3 输出路径
        model: 模型 ID（quality/turbo/flash）
        style: 风格夸张度 0.0-1.0（仅 multilingual_v2 支持）
    """
    api_key = get_elevenlabs_key()
    if not api_key:
        logger.warning("[TTS-ElevenLabs] 未配置 API Key，跳过")
        return False

    try:
        import aiohttp
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        voice_settings = {
            "stability": max(0.0, min(1.0, stability)),
            "similarity_boost": max(0.0, min(1.0, similarity_boost)),
        }
        # style 参数仅 multilingual_v2 模型支持
        if model in (ELEVENLABS_MODEL_DEFAULT, "eleven_multilingual_v2"):
            voice_settings["style"] = max(0.0, min(1.0, style))
            voice_settings["use_speaker_boost"] = True
        
        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": voice_settings,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    # 确保输出目录存在
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    file_size = len(audio_data)
                    logger.info(
                        f"[TTS-ElevenLabs] ✓ {os.path.basename(output_path)} "
                        f"({file_size/1024:.1f}KB) voice={voice_id[:8]}... "
                        f"stability={stability:.2f} sim={similarity_boost:.2f}"
                    )
                    return True
                elif resp.status == 401:
                    logger.error("[TTS-ElevenLabs] ✗ 401 Unauthorized — API Key 无效或已过期")
                    return False
                elif resp.status == 429:
                    logger.error("[TTS-ElevenLabs] ✗ 429 Rate Limited — 超出配额，等待后重试")
                    return False
                else:
                    error_text = await resp.text()
                    logger.error(f"[TTS-ElevenLabs] ✗ HTTP {resp.status}: {error_text[:300]}")
                    return False
    except ImportError:
        logger.error("[TTS-ElevenLabs] aiohttp 未安装，请执行: pip install aiohttp")
        return False
    except asyncio.TimeoutError:
        logger.error("[TTS-ElevenLabs] ✗ 请求超时（60秒）")
        return False
    except Exception as e:
        logger.error(f"[TTS-ElevenLabs] ✗ 生成失败: {output_path} — {type(e).__name__}: {e}")
        return False


async def generate_faction_voice(faction_id: str, force: bool = False, provider: str = "edge") -> dict:
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

    if provider == "elevenlabs":
        eleven_cfg = ELEVENLABS_VOICE_CONFIG.get(faction_id, {})
        voice_id = eleven_cfg.get("voice_id", ELEVENLABS_DEFAULT_VOICE_ID)
        stability = eleven_cfg.get("stability", 0.5)
        similarity_boost = eleven_cfg.get("similarity_boost", 0.75)
        style = eleven_cfg.get("style", 0.0)
        model = ELEVENLABS_MODEL_DEFAULT  # 品质优先
        result["voice"] = f"elevenlabs:{voice_id[:12]}..."
        result["role"] = eleven_cfg.get("role", faction_id)
        result["desc"] = eleven_cfg.get("desc", "")
        result["provider"] = "elevenlabs"
        result["model"] = model

        success = await _generate_mp3_elevenlabs(
            text=text,
            voice_id=voice_id,
            stability=stability,
            similarity_boost=similarity_boost,
            output_path=str(output_path),
            model=model,
            style=style,
        )
        if not success:
            result["error"] = "ElevenLabs 生成失败（请检查 API Key 或网络连接）"
    else:
        # 默认 edge-tts
        voice_cfg = get_voice_config(faction_id)
        if not voice_cfg:
            result["error"] = f"未找到势力 {faction_id} 的音色配置"
            return result
        result["voice"] = voice_cfg["voice"]
        result["role"] = voice_cfg["role"]
        result["desc"] = voice_cfg.get("desc", "")
        result["provider"] = "edge"

        success = await _generate_mp3(
            text=text,
            voice=voice_cfg["voice"],
            rate=voice_cfg["rate"],
            pitch=voice_cfg["pitch"],
            output_path=str(output_path),
        )
        if not success:
            result["error"] = "edge-tts 生成失败"

    elapsed = time.time() - t0
    if success:
        result["generated"] = True
        result["size_bytes"] = output_path.stat().st_size
        logger.info(f"[TTS] {faction_id} 生成完成 (耗时 {elapsed:.1f}s, {result['size_bytes']} bytes, provider={provider})")
    return result


async def generate_all_faction_voices(force: bool = False, provider: str = "edge") -> list[dict]:
    """批量生成全部九大势力的 AI 配音"""
    tasks = [generate_faction_voice(fid, force=force, provider=provider) for fid in FACTION_VOICE_CONFIG]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            faction_id = list(FACTION_VOICE_CONFIG.keys())[i]
            final.append({"faction_id": faction_id, "error": str(r), "generated": False})
        else:
            final.append(r)
    return final


async def generate_npc_voice(
    npc_name: str,
    text: str,
    personality: str = "neutral",
    force: bool = False,
) -> dict:
    """
    为 NPC/事件角色生成配音 MP3（使用 ElevenLabs）。
    
    Args:
        npc_name: NPC 名称（用于文件名，如 "刘伯温"）
        text: 要朗读的文本（中文）
        personality: 性格标签（wise/aggressive/gentle/scheming/neutral）
        force: 是否强制重新生成
    
    返回: { npc_name, output_path, generated, cached, voice_id, size_bytes, error }
    """
    result = {
        "npc_name": npc_name,
        "output_path": "",
        "generated": False,
        "cached": False,
        "voice_id": "",
        "size_bytes": 0,
        "error": None,
    }

    # 生成稳定的文件名哈希
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    safe_name = "".join(c if c.isalnum() else "_" for c in npc_name)
    filename = f"npc_{safe_name}_{text_hash}.mp3"
    
    VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = VOICE_OUTPUT_DIR / filename
    result["output_path"] = str(output_path)

    # 性格 → 音色 + 参数映射（使用账户实际可用音色）
    personality_config = {
        "wise":       {"voice_id": "pqHfZKP75CvOlQylNhV4", "stability": 0.55, "similarity_boost": 0.75, "style": 0.0},   # Bill - 长者智者
        "aggressive": {"voice_id": "SOYHLrjzK2X1ezoPC6cr", "stability": 0.28, "similarity_boost": 0.82, "style": 0.12},  # Harry - 激昂猛将
        "gentle":     {"voice_id": "cjVigY5qzO86Huf0OWal", "stability": 0.52, "similarity_boost": 0.70, "style": 0.0},   # Eric - 温和商贾
        "scheming":   {"voice_id": "N2lVS1w4EtoT3dr4eOWO", "stability": 0.32, "similarity_boost": 0.80, "style": 0.10},  # Callum - 诡秘谋士
        "neutral":    {"voice_id": "nPczCjzI2devNBz1zQrb", "stability": 0.45, "similarity_boost": 0.75, "style": 0.0},   # Brian - 中性沉稳
    }
    cfg = personality_config.get(personality, personality_config["neutral"])
    result["voice_id"] = cfg["voice_id"]

    # 检查缓存
    if not force and output_path.exists() and output_path.stat().st_size > 100:
        result["cached"] = True
        result["generated"] = True
        result["size_bytes"] = output_path.stat().st_size
        return result

    t0 = time.time()
    success = await _generate_mp3_elevenlabs(
        text=text,
        voice_id=cfg["voice_id"],
        stability=cfg["stability"],
        similarity_boost=cfg["similarity_boost"],
        output_path=str(output_path),
        model=ELEVENLABS_MODEL_TURBO,  # NPC 用 turbo 更快
        style=cfg.get("style", 0.0),
    )
    elapsed = time.time() - t0

    if success:
        result["generated"] = True
        result["size_bytes"] = output_path.stat().st_size
        logger.info(f"[TTS-NPC] {npc_name}({personality}) 生成完成 (耗时 {elapsed:.1f}s, {result['size_bytes']} bytes)")
    else:
        result["error"] = "ElevenLabs 生成失败"
    return result


async def search_elevenlabs_voices(query: str = "", gender: str = "") -> list[dict]:
    """搜索 ElevenLabs 音色库（需要有效的 API Key）"""
    api_key = get_elevenlabs_key()
    if not api_key:
        return [{"error": "未配置 ElevenLabs API Key"}]
    
    try:
        import aiohttp
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key, "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return [{"error": f"API 错误 {resp.status}"}]
                data = await resp.json()
                voices = data.get("voices", [])
                result = []
                for v in voices:
                    # 过滤：只返回男声 + 支持中文的
                    labels = v.get("labels", {})
                    if gender and labels.get("gender", "") != gender:
                        continue
                    # 仅保留关键字段
                    item = {
                        "voice_id": v.get("voice_id"),
                        "name": v.get("name"),
                        "labels": {
                            "gender": labels.get("gender", "unknown"),
                            "age": labels.get("age", "unknown"),
                            "accent": labels.get("accent", "unknown"),
                            "description": labels.get("description", ""),
                        },
                        "preview_url": v.get("preview_url", ""),
                    }
                    if query:
                        searchable = f"{v.get('name','')} {labels.get('description','')}".lower()
                        if query.lower() not in searchable:
                            continue
                    result.append(item)
                return result
    except ImportError:
        return [{"error": "aiohttp 未安装"}]
    except Exception as e:
        return [{"error": str(e)}]


def list_available_voices(provider: str = "all") -> list[dict]:
    """列出所有已生成的势力配音文件状态
    
    Args:
        provider: "all" | "edge" | "elevenlabs" 过滤提供商
    """
    result = []
    for faction_id, cfg in FACTION_VOICE_CONFIG.items():
        mp3_path = VOICE_OUTPUT_DIR / f"{faction_id}_intro.mp3"
        status = "ready" if (mp3_path.exists() and mp3_path.stat().st_size > 100) else "missing"
        
        # ElevenLabs 配置
        eleven_cfg = ELEVENLABS_VOICE_CONFIG.get(faction_id, {})
        el_voice_id = eleven_cfg.get("voice_id", ELEVENLABS_DEFAULT_VOICE_ID)
        
        entry = {
            "faction_id": faction_id,
            "role": cfg["role"],
            "voice_edge": cfg["voice"],       # edge-tts 音色
            "voice_elevenlabs": el_voice_id,  # ElevenLabs voice_id
            "desc": cfg.get("desc", ""),
            "desc_elevenlabs": eleven_cfg.get("desc", cfg.get("desc", "")),
            "status": status,
            "size_bytes": mp3_path.stat().st_size if status == "ready" else 0,
        }
        
        if provider == "all":
            result.append(entry)
        elif provider == "edge" and cfg.get("voice"):
            result.append(entry)
        elif provider == "elevenlabs" and el_voice_id != ELEVENLABS_DEFAULT_VOICE_ID:
            result.append(entry)
    return result
