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
# 主流程
# ============================================================

async def generate_art(spec: dict, use_ai: bool = True) -> bool:
    """为单个规格生成原画，返回是否成功"""
    output_path = OUTPUT_DIR / spec["file"]
    logger.info(f"「{spec['label']}」→ {spec['file']} ({spec['width']}x{spec['height']})")

    # 检查缓存
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"  ✓ 已存在，跳过 ({output_path.stat().st_size} bytes)")
        return True

    # 通道 A：混元 API
    if use_ai:
        result = await generate_via_hunyuan(spec)
        if result and result.exists():
            return True

    # 通道 B：Pillow 降级
    try:
        generate_via_pillow(spec)
        return True
    except Exception as e:
        logger.error(f"  ✗ 生成失败: {e}")
        return False


async def generate_all(use_ai: bool = True) -> dict:
    """生成全部 7 张原画"""
    start = time.time()
    results = {"total": len(ART_SPECS), "success": 0, "failed": 0, "files": []}

    for spec in ART_SPECS:
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
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info(f"{'='*50}")

    return results


# ============================================================
# CLI
# ============================================================

async def main():
    parser = argparse.ArgumentParser(description="元末逐鹿3.0 AI原画管道")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际生成")
    parser.add_argument("--province", type=str, default=None,
                        choices=["panorama", "zhongshu", "henanjiang", "jiangzhe", "huguang", "sichuan", "jiangxi"],
                        help="仅生成指定行省")
    parser.add_argument("--no-ai", action="store_true", help="跳过混元 API，直接用 Pillow 生成")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== 原画生成计划 ===")
        for s in ART_SPECS:
            exists = "✓已存在" if (OUTPUT_DIR / s["file"]).exists() else "○待生成"
            logger.info(f"  {exists} {s['label']}: {s['file']} ({s['width']}x{s['height']})")
        return

    if args.province:
        # 单张生成
        for s in ART_SPECS:
            if args.province in s["id"]:
                await generate_art(s, use_ai=not args.no_ai)
                break
    else:
        # 批量生成
        await generate_all(use_ai=not args.no_ai)


if __name__ == "__main__":
    asyncio.run(main())
