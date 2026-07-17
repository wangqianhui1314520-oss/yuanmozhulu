"""
元末逐鹿 3.0 · AI 原画管道
=============================
按照 INKARNATE_AI_LAYERED_MAP_GUIDE.md 中定义的规格，
调用 AI 生成 1 张全局沙盘全景 + 6 张行省特写 PNG，
输出到 frontend/public/data/map/，供前端 MapLayerPanel 切换显示。

双通道:
  A) 腾讯混元图生图 API（首选）
  B) Pillow 程序化水墨风格生成（降级兜底）

用法:
  python -m server.services.art_pipeline          # 生成全部 7 张
  python -m server.services.art_pipeline --dry-run  # 仅打印计划
  python -m server.services.art_pipeline --province sichuan  # 单张
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "data" / "map"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[ART] %(message)s")
logger = logging.getLogger("yuanmo.art")

# ============================================================
# 输出目录
# ============================================================
FACTION_ART_DIR = PROJECT_ROOT / "frontend" / "public" / "assets" / "factions" / "ai_generated"
BATTLE_ART_DIR = PROJECT_ROOT / "frontend" / "public" / "assets" / "factions" / "ai_generated"
UI_ART_DIR = PROJECT_ROOT / "frontend" / "public" / "assets" / "ui"
FACTION_ART_DIR.mkdir(parents=True, exist_ok=True)
UI_ART_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 九大势力配色体系
# ============================================================
FACTION_PROFILES = {
    "faction_yuan":      {"name": "元廷",   "color": "deep_crimson",   "hex": "#8B0000", "bg": (245, 232, 228), "ink": (80, 25, 20),  "accent": (180, 60, 40),   "label": "正统的黄昏"},
    "faction_wangbaobao": {"name": "王保保", "color": "cold_bluegrey",  "hex": "#666699", "bg": (230, 232, 240), "ink": (50, 50, 75),   "accent": (100, 100, 150), "label": "最后的蒙古名将"},
    "faction_mobei":     {"name": "漠北诸部","color": "earth_brown",    "hex": "#887766", "bg": (240, 228, 215), "ink": (70, 55, 40),   "accent": (150, 120, 90),  "label": "草原雄鹰"},
    "faction_zhuyuanzhang":   {"name": "朱元璋", "color": "blood_red",      "hex": "#DC143C", "bg": (242, 230, 230), "ink": (90, 20, 20),   "accent": (200, 40, 50),   "label": "布衣天子"},
    "faction_chenyouliang":    {"name": "陈友谅", "color": "deep_blue",      "hex": "#1E90FF", "bg": (228, 235, 245), "ink": (30, 45, 80),   "accent": (50, 120, 200),  "label": "鄱阳湖之王"},
    "faction_zhangshicheng":   {"name": "张士诚", "color": "warm_orange",    "hex": "#FF8C00", "bg": (248, 238, 225), "ink": (80, 50, 25),   "accent": (200, 120, 40),  "label": "江南首富"},
    "faction_xushouhui": {"name": "徐寿辉", "color": "earth_red",      "hex": "#996633", "bg": (242, 235, 225), "ink": (70, 45, 25),   "accent": (160, 90, 50),   "label": "红巾先驱"},
    "faction_fangguozhen":{"name": "方国珍","color": "sea_green",      "hex": "#20B2AA", "bg": (225, 240, 238), "ink": (25, 60, 55),   "accent": (40, 150, 140),  "label": "海商之王"},
    "faction_mingyuzhen":    {"name": "明玉珍", "color": "earth_gold",     "hex": "#B8860B", "bg": (242, 235, 218), "ink": (65, 50, 25),   "accent": (170, 120, 40),  "label": "蜀道之主"},
}

# ============================================================
# 七张 AI 原画规格（来自 INKARNATE 手册）
# ============================================================
ART_SPECS = [
    {
        "id": "ai_panorama_global",
        "file": "ai_panorama_global.png",
        "width": 2800,
        "height": 2100,
        "label": "全局沙盘全景",
        "prompt": (
            "俯视视角，古风水墨风格，元代至正年间中国疆域全景地图。"
            "宣纸底色，水墨晕染，淡彩。"
            "标注元顺帝（大都）、朱元璋（应天）、陈友谅（武昌）、"
            "张士诚（苏州）、王保保（汴梁）、明玉珍（重庆）六大势力范围。"
            "北方蒙古高原用枯笔皴擦，中原用淡墨晕染，江南用水墨点染。"
            "黄河长江蜿蜒贯穿，太行秦岭横亘。"
            "无文字标注，纯绘画风格，绢本质感，轻微旧化做旧。"
            "画幅比例4:3，全景俯视。"
        ),
        "color_palette": "warm_parchment",
    },
    {
        "id": "ai_province_zhongshu",
        "file": "ai_province_zhongshu.png",
        "width": 2000,
        "height": 1500,
        "label": "中书省特写",
        "province": "中书省",
        "prompt": (
            "俯视视角，古风水墨风格，元大都及中书省腹地特写。"
            "华北平原广袤，太行山脉西侧屏障，燕山北面拱卫。"
            "大都城（北京）居画面中央偏上，永定河环绕。"
            "黄土色调，枯笔皴擦表现平原，浓墨点染太行。"
        ),
        "color_palette": "loess_yellow",
    },
    {
        "id": "ai_province_henanjiang",
        "file": "ai_province_henanjiang.png",
        "width": 2000,
        "height": 1500,
        "label": "河南江北特写",
        "province": "河南江北",
        "prompt": (
            "俯视视角，古风水墨风格，河南江北行省中原腹地特写。"
            "黄河蜿蜒横贯，开封（汴梁）居中，洛阳在西。"
            "黄淮平原广阔，大别山南缘。"
            "黄土色主调，黄河用淡赭石晕染。"
        ),
        "color_palette": "loess_yellow",
    },
    {
        "id": "ai_province_jiangzhe",
        "file": "ai_province_jiangzhe.png",
        "width": 2000,
        "height": 1500,
        "label": "江浙特写",
        "province": "江浙",
        "prompt": (
            "俯视视角，古风水墨风格，江浙行省江南水乡特写。"
            "太湖居中，杭州（临安）在画面下方，应天（南京）在左上方。"
            "水网密布，长江下游横贯，江南丘陵起伏。"
            "青绿淡彩，水墨淋漓，湿润感。"
        ),
        "color_palette": "jade_green",
    },
    {
        "id": "ai_province_huguang",
        "file": "ai_province_huguang.png",
        "width": 2000,
        "height": 1500,
        "label": "湖广特写",
        "province": "湖广",
        "prompt": (
            "俯视视角，古风水墨风格，湖广行省荆楚大地特写。"
            "长江中游横贯，武昌（武汉）居中，洞庭湖在左。"
            "江汉平原广袤，幕阜山南缘，武陵山西侧。"
            "水墨晕染，江湖水汽蒸腾感。"
        ),
        "color_palette": "mist_blue",
    },
    {
        "id": "ai_province_sichuan",
        "file": "ai_province_sichuan.png",
        "width": 2000,
        "height": 1500,
        "label": "四川特写",
        "province": "四川",
        "prompt": (
            "俯视视角，古风水墨风格，四川行省巴蜀盆地特写。"
            "成都平原居中，重庆（夔州）在右下，长江三峡贯穿。"
            "四面环山（秦岭、大巴山、横断山），盆地内沃野千里。"
            "淡墨晕染盆地，浓墨皴擦四围山脉。"
        ),
        "color_palette": "mountain_grey",
    },
    {
        "id": "ai_province_jiangxi",
        "file": "ai_province_jiangxi.png",
        "width": 2000,
        "height": 1500,
        "label": "江西特写",
        "province": "江西",
        "prompt": (
            "俯视视角，古风水墨风格，江西行省鄱阳湖区特写。"
            "鄱阳湖居中偏上，南昌（龙兴）在湖西南。"
            "赣江纵贯南北，武夷山东缘，南岭南下。"
            "青绿淡彩，湖光山色，水汽氤氲。"
        ),
        "color_palette": "jade_green",
    },
]

# ============================================================
# 九大势力君主立绘规格 (1024×1024)
# ============================================================
FACTION_PORTRAIT_SPECS = [
    {
        "id": "portrait_yuan", "faction": "faction_yuan", "file": "ai_portrait_yuan.png",
        "width": 1024, "height": 1024,
        "label": "元顺帝立绘",
        "prompt": "A middle-aged Mongolian emperor in his 40s, wearing golden imperial dragon robes with intricate cloud patterns, sitting on a dragon throne in a dim palace hall. The emperor has a worried expression, with deep-set eyes, a thin mustache, and a tired but dignified bearing. Dark Chinese ink wash art style, side lighting from lanterns casting long shadows. The background is a grand but decaying Yuan Dynasty palace interior with silk curtains and bronze incense burners. Palette: deep crimson (#8B0000), dark gold (#C9A96E), ink black. Inspired by Yuan Dynasty portrait paintings, with textured brushstrokes.",
    },
    {
        "id": "portrait_wangbaobao", "faction": "faction_wangbaobao", "file": "ai_portrait_wangbaobao.png",
        "width": 1024, "height": 1024,
        "label": "王保保立绘",
        "prompt": "A fierce Mongolian warrior-general in his 30s, wearing ornate lamellar armor with fur-trimmed collar, holding a Mongolian saber. He has a proud, defiant expression, with a scar on his cheek, strong jaw, intense dark eyes. Standing on a snow-covered cliff overlooking the northern steppes. Dark Chinese ink wash style, cold blue-grey (#666699) and dark gold (#C9A96E) palette. Wind sweeping snow and horsehair standard behind him. Heroic composition, dynamic pose.",
    },
    {
        "id": "portrait_mobei", "faction": "faction_mobei", "file": "ai_portrait_mobei.png",
        "width": 1024, "height": 1024,
        "label": "漠北大汗立绘",
        "prompt": "A weathered Mongolian tribal chieftain in his 50s, wearing traditional fur and leather nomadic warrior attire, with a bow slung across his back. He has a thick beard, weather-beaten face, fierce hawk-like eyes gazing at the distant horizon. Standing beside a Mongolian horse on the vast green steppe under a stormy sky. Dark ink wash style, earthy brown (#887766) and dark gold palette. Yurt tents and galloping horses in distant background.",
    },
    {
        "id": "portrait_zhuyuan", "faction": "faction_zhuyuanzhang", "file": "ai_portrait_zhuyuan.png",
        "width": 1024, "height": 1024,
        "label": "朱元璋立绘",
        "prompt": "A determined Chinese rebel leader in his early 40s, wearing deep red battle robes with simple leather armor, standing in a war council tent. He has a long face with prominent cheekbones, penetrating eyes showing both wisdom and ruthlessness, a thin mustache. Behind him is a partially visible map on a wooden table. Dark Chinese ink wash style, crimson (#DC143C) and ink black palette. Candlelight illumination. Historically-inspired portrait style, dignified but not ostentatious.",
    },
    {
        "id": "portrait_chenyd", "faction": "faction_chenyouliang", "file": "ai_portrait_chenyd.png",
        "width": 1024, "height": 1024,
        "label": "陈友谅立绘",
        "prompt": "A fierce Chinese warlord in his 40s, wearing ornate blue battle armor with gold trim, standing on the deck of a massive war junk ship. He has a sharp, ambitious face with piercing eyes and a thin black beard. Behind him are towering warship masts, lake waters churning, and distant naval battle smoke. Dark Chinese ink wash style, deep blue (#1E90FF) and dark gold palette. Dramatic stormy lighting.",
    },
    {
        "id": "portrait_zhangsc", "faction": "faction_zhangshicheng", "file": "ai_portrait_zhangsc.png",
        "width": 1024, "height": 1024,
        "label": "张士诚立绘",
        "prompt": "A wealthy-looking Chinese warlord in his late 30s, wearing elegant silk robes in warm orange tones with jade ornaments, sitting in a luxurious garden pavilion in Suzhou. He has a round, prosperous face, calm gentle eyes, looking slightly complacent. Behind him: Jiangnan garden with lotus pond, curved bridges, willow trees. Dark ink wash style, warm orange (#FF8C00) and dark gold palette. Soft afternoon light.",
    },
    {
        "id": "portrait_xushouhui", "faction": "faction_xushouhui", "file": "ai_portrait_xushouhui.png",
        "width": 1024, "height": 1024,
        "label": "徐寿辉立绘",
        "prompt": "A charismatic Chinese rebel leader in his 40s with a spiritual aura, wearing simple robes with Buddhist prayer beads, a red headband (red turban). He has an earnest, zealous expression, with eyes looking upward as if receiving divine mandate. Holding a Buddhist sutra in one hand and a sword in the other. Background: mountain temple with prayer flags, misty peaks. Dark ink wash style, earthy brown (#996633) and crimson palette.",
    },
    {
        "id": "portrait_fangguozhen", "faction": "faction_fangguozhen", "file": "ai_portrait_fangguozhen.png",
        "width": 1024, "height": 1024,
        "label": "方国珍立绘",
        "prompt": "A cunning Chinese maritime merchant-lord in his 40s, wearing practical coastal trader's clothing in sea-green tones with a compass hanging from his belt. He has a shrewd, calculating expression with a slight knowing smile. Standing at the bow of a Chinese junk ship, with a bustling harbor and island archipelago behind him. Dark ink wash style, sea-green (#20B2AA) and ink black palette. Sea spray and dramatic clouds.",
    },
    {
        "id": "portrait_mingyz", "faction": "faction_mingyuzhen", "file": "ai_portrait_mingyz.png",
        "width": 1024, "height": 1024,
        "label": "明玉珍立绘",
        "prompt": "A benevolent-looking Chinese ruler in his 40s, wearing modest imperial robes in dark gold with jade accessories, standing on a cliff overlooking the Sichuan basin with its winding rivers and terraced fields. He has a kind, reserved expression with calm eyes. Behind him: the majestic Three Gorges mountains shrouded in mist, stone fortress walls. Dark ink wash style, earth gold (#B8860B) and ink black palette.",
    },
]

# ============================================================
# 九大势力都城场景概念图 (1920×1080)
# ============================================================
CAPITAL_SCENE_SPECS = [
    {"id": "capital_yuan",      "faction": "faction_yuan",      "file": "ai_capital_yuan.png",       "width": 1920, "height": 1080, "label": "大都城",
     "prompt": "Chinese ink wash landscape painting of Dadu (Khanbaliq/Beijing) in the 14th century Yuan Dynasty. A grand walled city seen from outside, with towering gate towers, Mongol yurt encampments outside the walls, and the Forbidden City-like palace complex within. Snow on the northern mountains in distance. Dark, moody atmosphere. Oil-paper lanterns glowing at dusk. Cinematic wide shot. Palette: dark crimson, ink black, dark gold."},
    {"id": "capital_wangbaobao","faction": "faction_wangbaobao","file": "ai_capital_wangbaobao.png",  "width": 1920, "height": 1080, "label": "太原城",
     "prompt": "Chinese ink wash landscape painting of Taiyuan in the 14th century. A northern frontier fortress city on the edge of the steppe, with massive rammed-earth walls, cavalry training grounds with thousands of horses, and snow-capped northern mountains beyond. Mongolian yurt encampments outside the walls. Cinematic wide shot. Cold blue-grey palette."},
    {"id": "capital_mobei",     "faction": "faction_mobei",     "file": "ai_capital_mobei.png",       "width": 1920, "height": 1080, "label": "和林城",
     "prompt": "Chinese ink wash landscape painting of Karakorum in the 14th century. The ancient Mongol capital on the vast grassland steppe, a city of yurts and low wooden buildings surrounding a golden Buddhist temple, with herds of horses stretching to the horizon. Storm clouds gathering over the endless grass sea. Cinematic wide shot. Earth-brown palette."},
    {"id": "capital_zhuyuan",   "faction": "faction_zhuyuanzhang",   "file": "ai_capital_zhuyuan.png",    "width": 1920, "height": 1080, "label": "应天府",
     "prompt": "Chinese ink wash painting of Yingtian (Nanjing) in the 14th century. A fortified city on the south bank of the Yangtze River, with the massive stone city walls, drum towers, and a grand river port with hundreds of trade junks. Purple Mountain visible in background mist. Spring atmosphere with plum blossoms. Cinematic wide shot. Crimson and ink black palette."},
    {"id": "capital_chenyd",    "faction": "faction_chenyouliang",    "file": "ai_capital_chenyd.png",     "width": 1920, "height": 1080, "label": "武昌城",
     "prompt": "Chinese ink wash painting of Wuchang in the 14th century. A lakeside fortress city where the Han River meets the Yangtze, with towering warship docks, naval shipyards with massive vessels under construction, and fortified river walls. Stormy sky with lightning over the water. Cinematic wide shot. Deep blue and ink black palette."},
    {"id": "capital_zhangsc",   "faction": "faction_zhangshicheng",   "file": "ai_capital_zhangsc.png",    "width": 1920, "height": 1080, "label": "平江城",
     "prompt": "Chinese ink wash painting of Pingjiang (Suzhou) in the 14th century. A prosperous canal city with white-walled buildings, curved stone bridges, silk workshops along the waterways, and elegant garden pavilions. Merchant boats laden with goods. Cherry blossoms and willow trees. Lively market scene along the Grand Canal. Cinematic wide shot. Warm orange-golden palette."},
    {"id": "capital_xushouhui", "faction": "faction_xushouhui", "file": "ai_capital_xushouhui.png",  "width": 1920, "height": 1080, "label": "襄阳城",
     "prompt": "Chinese ink wash painting of Xiangyang in the 14th century. A strategic fortress city on the Han River, with thick stone walls pierced by arrow towers, where the river forms a natural moat. Red turban flags flying from the battlements. Temple pagodas visible within. Sunset lighting creates a dramatic silhouette. Cinematic wide shot. Earth-brown and crimson palette."},
    {"id": "capital_fangguozhen","faction":"faction_fangguozhen","file": "ai_capital_fangguozhen.png", "width": 1920, "height": 1080, "label": "庆元城",
     "prompt": "Chinese ink wash painting of Qingyuan (Ningbo) in the 14th century. A bustling coastal port city with a vast natural harbor, hundreds of ocean-going junks with battened sails, island fortifications, lighthouse tower on a hill, and warehouse districts along the waterfront. Sea mist and dramatic clouds. Cinematic wide shot. Sea-green and ink black palette."},
    {"id": "capital_mingyz",    "faction": "faction_mingyuzhen",    "file": "ai_capital_mingyz.png",     "width": 1920, "height": 1080, "label": "重庆城",
     "prompt": "Chinese ink wash painting of Chongqing in the 14th century. A mountain fortress city built on steep cliffs where two great rivers meet, connected by rope bridges and steep stone stairs. Watchtowers on every peak, surrounded by misty gorges and terraced rice fields climbing the mountainsides. Cinematic wide shot. Earth-gold and ink black palette."},
]

# ============================================================
# 四大战场场景概念图 (1920×1080)
# ============================================================
BATTLEFIELD_SPECS = [
    {"id": "battle_plain",  "file": "ai_battle_plain.png",  "width": 1920, "height": 1080, "label": "平原会战",
     "prompt": "Epic Chinese ink wash painting of a massive medieval battle. Two armies clash on a vast plain at sunset. One side: Mongol cavalry with fur banners. The other side: Chinese infantry with red turban flags. Dust clouds, cavalry charges, spear formations silhouetted against the orange sky. Very wide panoramic composition, cinematic. Dark ink and blood-red palette."},
    {"id": "battle_naval",  "file": "ai_battle_naval.png",  "width": 1920, "height": 1080, "label": "鄱阳湖水战",
     "prompt": "Epic Chinese ink wash painting of a naval battle. Hundreds of massive warships burning on a great lake. Tower ships with three decks exchanging fire arrows and grappling hooks. Smoke and flames reflecting on dark water. Ships colliding, soldiers boarding. Stormy sky and burning horizon. Blue-black and flame-orange palette."},
    {"id": "battle_siege",  "file": "ai_battle_siege.png",  "width": 1920, "height": 1080, "label": "攻城战",
     "prompt": "Epic Chinese ink wash painting of a siege battle. A massive fortified city under assault at night. Siege towers and ladders against towering stone walls. Defenders pouring boiling oil. Flaming projectiles arcing through the dark sky. Battering ram at the main gate. Dramatic firelight illumination. Ink black and fire-orange palette."},
    {"id": "battle_pass",   "file": "ai_battle_pass.png",   "width": 1920, "height": 1080, "label": "关隘争夺",
     "prompt": "Epic Chinese ink wash painting of a mountain pass battle. Two armies fighting in a narrow mountain defile between towering cliffs. Cavalry bottlenecked in the pass. Archers on high cliffs raining arrows. Stone fortifications and wooden palisades. Morning mist and mountain shadows. Cold grey and dark gold palette."},
]

# ============================================================
# 六张 UI 装饰元素
# ============================================================
UI_ELEMENT_SPECS = [
    {"id": "ui_scroll_border",  "file": "ai_ui_scroll_border.png",  "width": 1920, "height": 120,  "label": "卷轴边框",
     "prompt": "Traditional Chinese horizontal scroll ornament border, ink wash style, dark gold pattern on aged silk background. Decorative cloud motifs at scroll ends. Weathered texture, ancient manuscript aesthetic."},
    {"id": "ui_seal_stamp",     "file": "ai_ui_seal_stamp.png",     "width": 512,  "height": 512,  "label": "印章纹饰",
     "prompt": "Traditional Chinese red seal stamp pattern, square vermillion ink seal with ancient seal script characters, on aged paper texture. Square format with irregular edge wear. Dark red on parchment background."},
    {"id": "ui_cloud_bg",       "file": "ai_ui_cloud_bg.png",       "width": 512,  "height": 512,  "label": "云纹底纹",
     "prompt": "Chinese ink wash cloud pattern, subtle dark gold clouds on dark background, traditional Xiangyun auspicious cloud motif. Seamless tileable pattern, very low contrast."},
    {"id": "ui_mountain_bg",    "file": "ai_ui_mountain_bg.png",    "width": 1024, "height": 256,  "label": "水墨山川",
     "prompt": "Subtle Chinese ink wash mountain landscape silhouette, misty peaks in various opacity levels, ink black on transparent/dark background. Low contrast, decorative background."},
    {"id": "ui_war_banner",     "file": "ai_ui_war_banner.png",     "width": 512,  "height": 512,  "label": "战旗纹样",
     "prompt": "Ancient Chinese military banner design, triangular war flag with tattered edges, ink wash style. Dragon or tiger emblem in gold thread on dark crimson fabric. Flowing in the wind effect."},
    {"id": "ui_dragon_badge",   "file": "ai_ui_dragon_badge.png",   "width": 512,  "height": 512,  "label": "龙纹徽章",
     "prompt": "Traditional Chinese dragon medallion design, circular badge with coiled dragon motif in dark gold, ink wash style. Yuan Dynasty imperial style."},
]

# ============================================================
# 通道 A：腾讯混元图生图 API
# ============================================================
HUNYUAN_IMAGE_API = "https://hunyuan.tencentcloudapi.com"


async def generate_via_hunyuan(spec: dict) -> Optional[Path]:
    """
    调用混元图生图 API 生成图片。

    混元 ImageGeneration API:
      POST /openapi/v1/images/generations
      Body: { model, prompt, size, n, style }
    """
    api_key = os.getenv("TENCENT_API_KEY", "")
    api_base = os.getenv("TENCENT_TOKENHUB_URL", "")

    if not api_key:
        logger.warning(f"  ⚠ TENCENT_API_KEY 未设置，跳过混元调用 → 降级到程序化生成")
        return None

    # 尝试多种可能的API基地址
    import httpx
    candidates = []
    if api_base:
        candidates.append(api_base.rstrip("/"))
    candidates.append("https://copilot.tencent.com/v2")
    candidates.append(HUNYUAN_IMAGE_API)

    size = f"{spec['width']}x{spec['height']}"
    payload = {
        "model": "hunyuan-vision",
        "prompt": spec["prompt"],
        "size": size,
        "n": 1,
        "style": "chinese-ink-wash",
    }

    for base_url in candidates:
        url = f"{base_url}/images/generations"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
                logger.info(f"  尝试混元 API: {url}")
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    image_url = (
                        data.get("data", [{}])[0].get("url", "")
                        or data.get("data", [{}])[0].get("b64_json", "")
                    )
                    if image_url:
                        if image_url.startswith("http"):
                            # 下载图片
                            img_resp = await client.get(image_url)
                            img_resp.raise_for_status()
                            img_data = img_resp.content
                        else:
                            # Base64 编码的图片数据
                            import base64
                            img_data = base64.b64decode(image_url)

                        output_path = OUTPUT_DIR / spec["file"]
                        output_path.write_bytes(img_data)
                        logger.info(f"  ✓ 混元生成成功: {output_path} ({len(img_data)} bytes)")
                        return output_path
                elif resp.status_code == 404:
                    logger.info(f"  端点不可用 (404)，尝试下一个...")
                    continue
                else:
                    logger.warning(f"  API 返回 {resp.status_code}: {resp.text[:200]}")
                    continue
        except httpx.TimeoutException:
            logger.warning(f"  超时: {url}")
            continue
        except Exception as e:
            logger.warning(f"  异常: {type(e).__name__}: {e}")
            continue

    return None


# ============================================================
# 通道 B：Pillow 程序化水墨风格生成（降级兜底）
# ============================================================

# 六行省对应的地理位置色板
PROVINCE_COLORS = {
    "warm_parchment": {"bg": (245, 235, 210), "ink": (60, 45, 30), "accent": (150, 120, 70), "water": (160, 180, 200)},
    "loess_yellow":   {"bg": (248, 238, 210), "ink": (70, 55, 30), "accent": (180, 140, 60), "water": (160, 180, 200)},
    "jade_green":     {"bg": (235, 242, 230), "ink": (50, 60, 45), "accent": (120, 150, 100), "water": (140, 180, 200)},
    "mist_blue":      {"bg": (238, 240, 245), "ink": (45, 55, 65), "accent": (100, 130, 160), "water": (120, 170, 200)},
    "mountain_grey":  {"bg": (240, 235, 225), "ink": (55, 50, 45), "accent": (130, 120, 100), "water": (150, 170, 190)},
}


def generate_via_pillow(spec: dict) -> Path:
    """使用 Pillow 生成古风水墨风格的程序化图片"""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        logger.error("  ✗ Pillow 未安装。请运行: pip install Pillow")
        raise

    width, height = spec["width"], spec["height"]
    palette = PROVINCE_COLORS.get(spec.get("color_palette", "warm_parchment"), PROVINCE_COLORS["warm_parchment"])

    # ---- 基底：宣纸纹理 ----
    img = Image.new("RGBA", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)

    # 添加宣纸纤维噪点
    import random
    random.seed(hash(spec["id"]) % (2**31))
    pixels = img.load()
    for x in range(0, width, 4):
        for y in range(0, height, 4):
            noise = random.randint(-8, 8)
            r, g, b, a = pixels[x, y] if x < width and y < height else (palette["bg"][0], palette["bg"][1], palette["bg"][2], 255)
            r = max(0, min(255, r + noise))
            g = max(0, min(255, g + noise))
            b = max(0, min(255, b + noise))
            pixels[x, y] = (r, g, b, a)

    # ---- 水墨山脉：叠加多层渐变椭圆模拟山川 ----
    mountain_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mountain_layer)

    mountain_positions = [
        # (left%, top%, width%, height%, alpha)
        (0.05, 0.15, 0.35, 0.30, 35),    # 左上
        (0.60, 0.10, 0.35, 0.28, 40),    # 右上
        (0.10, 0.55, 0.25, 0.25, 30),    # 左下
        (0.65, 0.50, 0.30, 0.30, 35),    # 右下
        (0.30, 0.05, 0.40, 0.18, 25),    # 顶部
        (0.20, 0.70, 0.30, 0.22, 28),    # 底部
    ]

    for (ml, mt, mw, mh, alpha) in mountain_positions:
        x0 = int(ml * width)
        y0 = int(mt * height)
        x1 = int((ml + mw) * width)
        y1 = int((mt + mh) * height)
        for i in range(3):
            ox = random.randint(-20, 20)
            oy = random.randint(-10, 10)
            s = random.uniform(0.85, 1.15)
            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2
            rw = int((x1 - x0) * s / 2)
            rh = int((y1 - y0) * s / 2)
            mdraw.ellipse(
                [cx - rw + ox, cy - rh + oy, cx + rw + ox, cy + rh + oy],
                fill=(palette["ink"][0], palette["ink"][1], palette["ink"][2], alpha),
                outline=None,
            )

    mountain_layer = mountain_layer.filter(ImageFilter.GaussianBlur(radius=6))
    img = Image.alpha_composite(img, mountain_layer)

    # ---- 水系：蓝灰曲线 ----
    water_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(water_layer)

    for _ in range(3):
        start_y = random.randint(height // 4, 3 * height // 4)
        points = []
        for px in range(0, width, 40):
            py = start_y + int(30 * (random.random() - 0.5) * (1 - abs(px / width - 0.5) * 2))
            points.append((px, py))
        if len(points) >= 2:
            for j in range(len(points) - 1):
                wdraw.line(
                    [points[j], points[j + 1]],
                    fill=(palette["water"][0], palette["water"][1], palette["water"][2], 30),
                    width=random.randint(6, 14),
                )

    water_layer = water_layer.filter(ImageFilter.GaussianBlur(radius=4))
    img = Image.alpha_composite(img, water_layer)

    # ---- 水墨点染：散布深色墨点模拟植被/城池 ----
    dot_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dot_layer)
    for _ in range(40):
        dx = random.randint(50, width - 50)
        dy = random.randint(50, height - 50)
        dr = random.randint(8, 30)
        alpha_dot = random.randint(15, 45)
        ddraw.ellipse(
            [dx - dr, dy - dr, dx + dr, dy + dr],
            fill=(palette["ink"][0], palette["ink"][1], palette["ink"][2], alpha_dot),
        )
    dot_layer = dot_layer.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.alpha_composite(img, dot_layer)

    # ---- 边缘晕染 ----
    edge_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    edraw = ImageDraw.Draw(edge_layer)
    margin = 60
    for a in [25, 18, 12]:
        edraw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(30, 25, 20, a),
            width=margin // 2,
        )
    edge_layer = edge_layer.filter(ImageFilter.GaussianBlur(radius=margin // 2))
    img = Image.alpha_composite(img, edge_layer)

    # ---- 存储 ----
    output_path = OUTPUT_DIR / spec["file"]
    # 转换为 RGB 保存（PNG 无透明需要也可保留透明通道）
    img_rgb = Image.new("RGB", (width, height), palette["bg"])
    img_rgb.paste(img, (0, 0), img)
    img_rgb.save(output_path, "PNG", optimize=True)
    file_size = output_path.stat().st_size
    logger.info(f"  ✓ Pillow 生成: {output_path} ({file_size} bytes, {width}x{height})")
    return output_path


# ============================================================
# Pillow 扩展生成器：势力君主立绘
# ============================================================

def generate_faction_portrait_via_pillow(spec: dict) -> Path:
    """为单个势力生成独特的水墨风格君主立绘"""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        logger.error("  ✗ Pillow 未安装。请运行: pip install Pillow")
        raise

    import random
    faction_id = spec["faction"]
    profile = FACTION_PROFILES.get(faction_id, FACTION_PROFILES["faction_yuan"])
    width, height = spec["width"], spec["height"]
    rng = random.Random(hash(spec["id"]) % (2**31))

    # 宣纸底色
    img = Image.new("RGBA", (width, height), profile["bg"])
    pixels = img.load()

    # 噪点纹理
    for x in range(0, width, 3):
        for y in range(0, height, 3):
            noise = rng.randint(-6, 6)
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
                a,
            )

    # ---- 渐变背景光晕（圆形聚光） ----
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cx, cy = width // 2, height // 3
    for i in range(20, 3, -1):
        alpha = 2 if i > 15 else 3
        r_glow = int(width * 0.5 * i / 20)
        gdraw.ellipse(
            [cx - r_glow, cy - r_glow, cx + r_glow, cy + r_glow],
            fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=30))
    img = Image.alpha_composite(img, glow)

    # ---- 人物轮廓（抽象水墨人体） ----
    body = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)

    # 头部
    head_cx, head_cy = cx, int(height * 0.35)
    head_r = int(width * 0.12)
    bdraw.ellipse(
        [head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r],
        fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 80),
    )

    # 身体（梯形）
    body_top = head_cy + head_r
    body_bottom = int(height * 0.65)
    body_width_top = int(width * 0.18)
    body_width_bottom = int(width * 0.25)
    bdraw.polygon(
        [
            (cx - body_width_top, body_top),
            (cx + body_width_top, body_top),
            (cx + body_width_bottom, body_bottom),
            (cx - body_width_bottom, body_bottom),
        ],
        fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 60),
    )

    # 肩膀/手臂
    shoulder_y = body_top + int((body_bottom - body_top) * 0.15)
    arm_left_x = cx - body_width_top - int(width * 0.08)
    arm_right_x = cx + body_width_top + int(width * 0.08)
    bdraw.line(
        [arm_left_x, shoulder_y, cx - body_width_bottom - int(width * 0.05), body_bottom],
        fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 55),
        width=int(width * 0.04),
    )
    bdraw.line(
        [arm_right_x, shoulder_y, cx + body_width_bottom + int(width * 0.05), body_bottom],
        fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 55),
        width=int(width * 0.04),
    )

    body = body.filter(ImageFilter.GaussianBlur(radius=8))
    img = Image.alpha_composite(img, body)

    # ---- 势力专属元素 ----
    element = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    edraw = ImageDraw.Draw(element)

    # 势力背景符号（根据势力类型不同）
    if faction_id in ("faction_yuan", "faction_wangbaobao", "faction_mobei"):
        # 蒙古势力：草原+马匹暗示
        for _ in range(6):
            ex = rng.randint(int(width * 0.1), int(width * 0.9))
            ey = rng.randint(int(height * 0.55), int(height * 0.9))
            er = rng.randint(15, 40)
            edraw.ellipse(
                [ex - er, ey - er, ex + er, ey + er],
                fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 12),
            )
    elif faction_id in ("chenyd", "fangguozhen"):
        # 水师势力：波浪纹理
        for _ in range(8):
            wx = rng.randint(0, width)
            wy = rng.randint(int(height * 0.6), height)
            edraw.arc(
                [wx - 60, wy - 15, wx + 60, wy + 15],
                start=0, end=180,
                fill=(profile["accent"][0], profile["accent"][1], profile["accent"][2], 20),
                width=3,
            )
    elif faction_id in ("zhangsc",):
        # 富裕势力：柳叶/园林暗示
        for _ in range(10):
            lx = rng.randint(int(width * 0.05), int(width * 0.3))
            ly = rng.randint(int(height * 0.5), int(height * 0.9))
            edraw.ellipse(
                [lx - 10, ly - 30, lx + 10, ly + 30],
                fill=(profile["accent"][0], profile["accent"][1], profile["accent"][2], 15),
            )
    elif faction_id in ("mingyz",):
        # 蜀地势力：山峦暗示
        for _ in range(5):
            mx = rng.randint(int(width * 0.3), int(width * 0.7))
            my = rng.randint(int(height * 0.55), int(height * 0.85))
            tri = [
                (mx - 50, my + 40), (mx + 50, my + 40), (mx, my - 60)
            ]
            edraw.polygon(tri, fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 18))

    element = element.filter(ImageFilter.GaussianBlur(radius=4))
    img = Image.alpha_composite(img, element)

    # ---- 朱砂印章 ----
    seal = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    seal_size = int(width * 0.08)
    seal_x = int(width * 0.78)
    seal_y = int(height * 0.78)
    sdraw.rectangle(
        [seal_x, seal_y, seal_x + seal_size, seal_y + seal_size],
        fill=(160, 30, 20, 120),
    )
    # 印章内势力名缩写（用简单线条代替篆字）
    char_cx = seal_x + seal_size // 2
    char_cy = seal_y + seal_size // 2
    for ch_i, ch_offset in enumerate([-8, 8]):
        sdraw.line(
            [(char_cx + ch_offset, char_cy - 10), (char_cx + ch_offset, char_cy + 10)],
            fill=(240, 220, 200, 180),
            width=3,
        )
    seal = seal.filter(ImageFilter.GaussianBlur(radius=1))
    img = Image.alpha_composite(img, seal)

    # ---- 暗角晕染 ----
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    margin = 40
    for a_val in [20, 12, 6]:
        vdraw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(profile["ink"][0], profile["ink"][1], profile["ink"][2], a_val),
            width=margin,
        )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=margin))
    img = Image.alpha_composite(img, vignette)

    # ---- 存储 ----
    output_path = FACTION_ART_DIR / spec["file"]
    img_rgb = Image.new("RGB", (width, height), profile["bg"])
    img_rgb.paste(img, (0, 0), img)
    img_rgb.save(output_path, "PNG", optimize=True)
    logger.info(f"  ✓ Pillow 立绘: {output_path} ({output_path.stat().st_size} bytes)")
    return output_path


# ============================================================
# Pillow 扩展生成器：场景概念图（都城/战场）
# ============================================================

def generate_scene_via_pillow(spec: dict) -> Path:
    """生成都城或战场场景概念图（水墨风格全景）"""
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        logger.error("  ✗ Pillow 未安装。")
        raise

    import random
    rng = random.Random(hash(spec["id"]) % (2**31))
    width, height = spec["width"], spec["height"]

    # 确定配色
    if "faction" in spec:
        profile = FACTION_PROFILES.get(spec["faction"], FACTION_PROFILES["yuan"])
    else:
        # 战场用默认配色
        profile = {"bg": (240, 235, 220), "ink": (50, 40, 30), "accent": (160, 80, 40)}

    is_battle = spec["id"].startswith("battle_")

    # 基底
    img = Image.new("RGBA", (width, height), profile["bg"])
    pixels = img.load()
    for x in range(0, width, 3):
        for y in range(0, height, 3):
            noise = rng.randint(-5, 5)
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
                a,
            )

    # ---- 天空渐变 ----
    sky = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sky)
    sky_height = int(height * 0.4) if not is_battle else int(height * 0.3)
    for i in range(sky_height):
        alpha = int(15 * (1 - i / sky_height))
        sdraw.line(
            [(0, i), (width, i)],
            fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], alpha),
            width=1,
        )
    sky = sky.filter(ImageFilter.GaussianBlur(radius=2))
    img = Image.alpha_composite(img, sky)

    # ---- 远景山脉 ----
    mountains = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mountains)
    mountain_count = rng.randint(5, 9)
    mountain_layer_y = int(height * 0.35) if not is_battle else int(height * 0.25)
    for _ in range(mountain_count):
        peak_x = rng.randint(int(width * 0.05), int(width * 0.95))
        peak_y = rng.randint(mountain_layer_y, mountain_layer_y + int(height * 0.2))
        base_w = rng.randint(int(width * 0.08), int(width * 0.2))
        base_h = rng.randint(int(height * 0.15), int(height * 0.35))
        alpha_mtn = rng.randint(20, 50)
        tri_points = [
            (peak_x - base_w, peak_y + base_h),
            (peak_x + base_w, peak_y + base_h),
            (peak_x, peak_y - base_h),
        ]
        mdraw.polygon(tri_points, fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], alpha_mtn))
    mountains = mountains.filter(ImageFilter.GaussianBlur(radius=5))
    img = Image.alpha_composite(img, mountains)

    # ---- 中景建筑/城池 ----
    city = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(city)

    if not is_battle:
        # 都城：城墙+塔楼
        city_base_y = int(height * 0.65)
        wall_left = int(width * 0.2)
        wall_right = int(width * 0.8)
        wall_thickness = int(height * 0.02)
        cdraw.rectangle(
            [wall_left, city_base_y, wall_right, city_base_y + wall_thickness],
            fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 70),
        )
        # 城门塔楼
        for tx in [wall_left, (wall_left + wall_right) // 2, wall_right]:
            tower_w = rng.randint(int(width * 0.03), int(width * 0.06))
            tower_h = rng.randint(int(height * 0.08), int(height * 0.15))
            cdraw.rectangle(
                [tx - tower_w, city_base_y - tower_h, tx + tower_w, city_base_y],
                fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 60),
            )
            # 屋顶
            roof_top = city_base_y - tower_h - rng.randint(5, 15)
            cdraw.polygon(
                [(tx - tower_w - 5, city_base_y - tower_h), (tx + tower_w + 5, city_base_y - tower_h), (tx, roof_top)],
                fill=(profile["accent"][0], profile["accent"][1], profile["accent"][2], 50),
            )
    else:
        # 战场：旗帜+军队暗示
        for _ in range(8):
            fx = rng.randint(int(width * 0.1), int(width * 0.9))
            fy = rng.randint(int(height * 0.5), int(height * 0.85))
            # 旗杆
            cdraw.line([(fx, fy), (fx, fy - 30)], fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], 70), width=2)
            # 旗帜
            cdraw.polygon(
                [(fx, fy - 30), (fx + 15, fy - 20), (fx, fy - 10)],
                fill=(profile["accent"][0], profile["accent"][1], profile["accent"][2], 50),
            )

    city = city.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.alpha_composite(img, city)

    # ---- 前景地面纹理 ----
    ground = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(ground)
    for _ in range(30):
        gx = rng.randint(0, width)
        gy = rng.randint(int(height * 0.7), height)
        gr = rng.randint(15, 50)
        gdraw.ellipse(
            [gx - gr, gy - gr // 2, gx + gr, gy + gr // 2],
            fill=(profile["ink"][0], profile["ink"][1], profile["ink"][2], rng.randint(4, 12)),
        )
    ground = ground.filter(ImageFilter.GaussianBlur(radius=5))
    img = Image.alpha_composite(img, ground)

    # ---- 暗角 ----
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    margin = 60
    for a_val in [18, 10, 5]:
        vdraw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(profile["ink"][0], profile["ink"][1], profile["ink"][2], a_val),
            width=margin,
        )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=margin))
    img = Image.alpha_composite(img, vignette)

    # ---- 存储 ----
    output_dir = BATTLE_ART_DIR if is_battle else FACTION_ART_DIR
    output_path = output_dir / spec["file"]
    img_rgb = Image.new("RGB", (width, height), profile["bg"])
    img_rgb.paste(img, (0, 0), img)
    img_rgb.save(output_path, "PNG", optimize=True)
    logger.info(f"  ✓ Pillow 场景: {output_path} ({output_path.stat().st_size} bytes)")
    return output_path


# ============================================================
# Pillow 扩展生成器：UI 装饰元素
# ============================================================

def generate_ui_via_pillow(spec: dict) -> Path:
    """生成 UI 装饰元素"""
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        logger.error("  ✗ Pillow 未安装。")
        raise

    import random
    rng = random.Random(hash(spec["id"]) % (2**31))
    width, height = spec["width"], spec["height"]

    ui_id = spec["id"]
    bg_color = (240, 235, 220)
    ink = (60, 45, 30)
    accent = (180, 120, 50)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if "scroll_border" in ui_id:
        # 水平卷轴边框
        margin = 20
        draw.rectangle([margin, margin, width - margin, height - margin],
                       outline=ink + (60,), width=3)
        # 卷轴两端云纹
        for sx in [int(width * 0.02), int(width * 0.98)]:
            for sy, a_val in [(int(height * 0.3), 30), (int(height * 0.5), 25), (int(height * 0.7), 30)]:
                draw.ellipse([sx - 15, sy - 10, sx + 15, sy + 10], fill=accent + (a_val,))

    elif "seal_stamp" in ui_id:
        # 朱砂印章
        seal_margin = int(min(width, height) * 0.1)
        draw.rectangle([seal_margin, seal_margin, width - seal_margin, height - seal_margin],
                       fill=(160, 30, 20, 180))
        # 印章文字暗示
        cx, cy = width // 2, height // 2
        r_seal = int(min(width, height) * 0.3)
        for _ in range(4):
            angle = rng.uniform(0, 6.28)
            sx_line = int(cx + r_seal * 0.5 * (rng.random() - 0.5))
            draw.line([(sx_line - 8, cy - 15), (sx_line + 8, cy + 15)],
                      fill=(240, 220, 200, 100), width=2)

    elif "cloud_bg" in ui_id:
        # 云纹底纹（可平铺）
        for _ in range(8):
            clx = rng.randint(50, width - 50)
            cly = rng.randint(50, height - 50)
            for i in range(3):
                cr = rng.randint(20, 50)
                draw.ellipse([clx - cr + i * 20, cly - cr // 2, clx + cr + i * 20, cly + cr // 2],
                             fill=accent + (rng.randint(8, 20),))
        img = img.filter(ImageFilter.GaussianBlur(radius=4))

    elif "mountain_bg" in ui_id:
        # 水墨山川剪影
        for peak_x in range(0, width, 120):
            peak_h = rng.randint(40, height - 30)
            draw.polygon(
                [(peak_x - 80, height), (peak_x, height - peak_h), (peak_x + 80, height)],
                fill=ink + (rng.randint(15, 40),),
            )
        img = img.filter(ImageFilter.GaussianBlur(radius=6))

    elif "war_banner" in ui_id:
        # 战旗纹样
        cx_b, cy_b = width // 2, height // 2
        draw.polygon(
            [(cx_b - 60, cy_b + 100), (cx_b, cy_b - 120), (cx_b + 80, cy_b + 60)],
            fill=(140, 30, 20, 120),
        )
        draw.line([(cx_b, cy_b - 120), (cx_b, cy_b + 100)], fill=ink + (100,), width=3)
        # 旗上图案
        draw.ellipse([cx_b - 20, cy_b - 20, cx_b + 20, cy_b + 20],
                     fill=accent + (80,))

    elif "dragon_badge" in ui_id:
        # 龙纹徽章（圆形简化）
        dcx, dcy = width // 2, height // 2
        badge_r = int(min(width, height) * 0.35)
        draw.ellipse(
            [dcx - badge_r, dcy - badge_r, dcx + badge_r, dcy + badge_r],
            outline=accent + (120,), width=5,
        )
        draw.ellipse(
            [dcx - badge_r + 10, dcy - badge_r + 10, dcx + badge_r - 10, dcy + badge_r - 10],
            outline=ink + (60,), width=2,
        )
        # 龙形简化
        for i in range(0, 360, 30):
            import math
            rad = math.radians(i)
            px = int(dcx + (badge_r - 25) * math.cos(rad))
            py = int(dcy + (badge_r - 25) * math.sin(rad))
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=accent + (60,))

    img = img.filter(ImageFilter.GaussianBlur(radius=2))

    # 存储
    output_path = UI_ART_DIR / spec["file"]
    img_rgb = Image.new("RGB", (width, height), bg_color)
    img_rgb.paste(img, (0, 0), img)
    img_rgb.save(output_path, "PNG", optimize=True)
    logger.info(f"  ✓ Pillow UI: {output_path} ({output_path.stat().st_size} bytes)")
    return output_path


# ============================================================
# 主流程
# ============================================================

async def generate_art(spec: dict, use_ai: bool = True) -> bool:
    """为单个规格生成原画，返回是否成功。根据 spec 类型自动路由到正确目录和生成器。"""
    spec_id = spec["id"]

    # 确定输出目录
    if spec_id.startswith("portrait_") or spec_id.startswith("capital_"):
        output_dir = FACTION_ART_DIR
    elif spec_id.startswith("battle_"):
        output_dir = BATTLE_ART_DIR
    elif spec_id.startswith("ui_"):
        output_dir = UI_ART_DIR
    else:
        output_dir = OUTPUT_DIR

    output_path = output_dir / spec["file"]
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"「{spec['label']}」→ {spec['file']} ({spec['width']}x{spec['height']})")

    # 检查缓存
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"  ✓ 已存在，跳过 ({output_path.stat().st_size} bytes)")
        return True

    # 通道 A：混元 API（仅地图类支持）
    if use_ai and not spec_id.startswith(("portrait_", "capital_", "battle_", "ui_")):
        result = await generate_via_hunyuan(spec)
        if result and result.exists():
            return True

    # 通道 B：Pillow 降级 — 根据类型路由
    try:
        if spec_id.startswith("portrait_"):
            generate_faction_portrait_via_pillow(spec)
        elif spec_id.startswith(("capital_", "battle_")):
            generate_scene_via_pillow(spec)
        elif spec_id.startswith("ui_"):
            generate_ui_via_pillow(spec)
        else:
            generate_via_pillow(spec)
        return True
    except Exception as e:
        logger.error(f"  ✗ 生成失败: {e}")
        return False


async def generate_all(use_ai: bool = True, categories: list = None, faction_id: str = None) -> dict:
    """生成全部原画。categories: ['map', 'portrait', 'capital', 'battle', 'ui']
    
    Args:
        faction_id: 可选，仅生成指定势力的立绘+都城（不影响全局状态）
    """
    all_specs = []
    if categories is None:
        categories = ["map", "portrait", "capital", "battle", "ui"]

    # 局部过滤：每次调用都从原始规格复制，不会修改全局列表
    portraits = list(FACTION_PORTRAIT_SPECS)
    capitals = list(CAPITAL_SCENE_SPECS)
    if faction_id:
        portraits = [s for s in portraits if s.get("faction") == faction_id]
        capitals = [s for s in capitals if s.get("faction") == faction_id]

    category_map = {
        "map": ART_SPECS,
        "portrait": portraits,
        "capital": capitals,
        "battle": BATTLEFIELD_SPECS,
        "ui": UI_ELEMENT_SPECS,
    }

    for cat in categories:
        if cat in category_map:
            all_specs.extend(category_map[cat])
            logger.info(f"  已加载类别 '{cat}': {len(category_map[cat])} 张")

    start = time.time()
    results = {"total": len(all_specs), "success": 0, "failed": 0, "files": []}

    for spec in all_specs:
        ok = await generate_art(spec, use_ai=use_ai)
        if ok:
            results["success"] += 1
            results["files"].append(spec["file"])
        else:
            results["failed"] += 1

    elapsed = time.time() - start
    logger.info(f"\n{'='*50}")
    logger.info(f"AI 原画管道完成: {results['success']}/{results['total']} 成功, 耗时 {elapsed:.1f}s")
    if results["failed"] > 0:
        logger.warning(f"  ✗ {results['failed']} 张失败，请检查日志")
    logger.info(f"{'='*50}")

    return results


# ============================================================
# CLI
# ============================================================

async def main():
    parser = argparse.ArgumentParser(description="元末逐鹿3.0 AI原画管道")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际生成")
    parser.add_argument("--category", type=str, default=None,
                        choices=["map", "portrait", "capital", "battle", "ui", "all"],
                        help="生成类别 (默认all)")
    parser.add_argument("--faction", type=str, default=None,
                        choices=list(FACTION_PROFILES.keys()),
                        help="仅生成指定势力的立绘+都城")
    parser.add_argument("--no-ai", action="store_true", help="跳过混元 API，直接用 Pillow 生成")
    parser.add_argument("--force", action="store_true", help="强制重新生成（忽略缓存）")
    args = parser.parse_args()

    # 确定生成类别
    cat = args.category or "all"
    if cat == "all":
        categories = ["map", "portrait", "capital", "battle", "ui"]
    else:
        categories = [cat]

    if args.dry_run:
        logger.info("=== AI 原画生成计划 ===")
        category_map = {
            "map": (ART_SPECS, OUTPUT_DIR),
            "portrait": (FACTION_PORTRAIT_SPECS, FACTION_ART_DIR),
            "capital": (CAPITAL_SCENE_SPECS, FACTION_ART_DIR),
            "battle": (BATTLEFIELD_SPECS, BATTLE_ART_DIR),
            "ui": (UI_ELEMENT_SPECS, UI_ART_DIR),
        }
        for c in categories:
            if c in category_map:
                specs, out_dir = category_map[c]
                logger.info(f"\n--- {c} ({len(specs)} 张) → {out_dir} ---")
                for s in specs:
                    if args.faction and s.get("faction") != args.faction:
                        continue
                    exists = "✓已存在" if (out_dir / s["file"]).exists() else "○待生成"
                    logger.info(f"  {exists} {s['label']}: {s['file']} ({s['width']}x{s['height']})")
        return

    # 过滤：如果指定了 --faction
    faction_filter = None
    if args.faction:
        faction_filter = args.faction
        logger.info(f"仅生成势力: {FACTION_PROFILES[args.faction]['name']}")
        # 过滤类别：只保留 portrait 和 capital
        categories = [c for c in categories if c in ("portrait", "capital")]

    # 如果 --force，跳过缓存检查（简单实现：删除缓存文件）
    if args.force:
        logger.info("强制模式：清除所有缓存")
        for c in categories:
            category_map = {
                "map": (ART_SPECS, OUTPUT_DIR),
                "portrait": (FACTION_PORTRAIT_SPECS, FACTION_ART_DIR),
                "capital": (CAPITAL_SCENE_SPECS, FACTION_ART_DIR),
                "battle": (BATTLEFIELD_SPECS, BATTLE_ART_DIR),
                "ui": (UI_ELEMENT_SPECS, UI_ART_DIR),
            }
            if c in category_map:
                specs, out_dir = category_map[c]
                for s in specs:
                    fp = out_dir / s["file"]
                    if fp.exists():
                        fp.unlink()

    await generate_all(use_ai=not args.no_ai, categories=categories, faction_id=faction_filter)


if __name__ == "__main__":
    asyncio.run(main())
