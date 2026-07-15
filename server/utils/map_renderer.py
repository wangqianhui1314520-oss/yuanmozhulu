"""
地图渲染引擎 — 将游戏沙盘渲染为PNG预览图

功能：
- 读取地图数据（provinces/prefectures/cities/factions）
- 使用Pillow渲染地势、势力边界、府城标注
- 生成PNG缓存供前端预览
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from io import BytesIO
from typing import Optional

logger = logging.getLogger("yuanmo.map_renderer")

# 颜色常量
COLOR_WATER = (41, 98, 143, 255)
COLOR_OCEAN = (27, 66, 96, 255)
COLOR_LAND_BASE = (210, 180, 140, 255)
COLOR_MOUNTAIN = (139, 119, 90, 255)
COLOR_BORDER = (80, 50, 30, 128)
COLOR_FACTION_BORDER = (160, 40, 40, 200)
COLOR_TEXT = (40, 25, 10, 255)
COLOR_CITY = (200, 50, 50, 255)
COLOR_BACKGROUND = (240, 235, 225, 255)

# 元末势力配色方案（10种互反色）
FACTION_COLORS = [
    (200, 50, 50, 140),     # 朱红 — 朱元璋
    (50, 50, 200, 140),     # 湛蓝 — 元廷
    (60, 160, 60, 140),     # 翠绿 — 张士诚
    (200, 160, 40, 140),    # 金黄 — 陈友谅
    (160, 60, 160, 140),    # 紫色 — 方国珍
    (40, 160, 160, 140),    # 青蓝 — 明玉珍
    (180, 100, 60, 140),    # 橙色 —
    (60, 100, 180, 140),    # 蓝灰 —
    (140, 140, 60, 140),    # 黄绿 —
    (120, 60, 120, 140),    # 暗紫 —
]


def _map_data_dir() -> Path:
    """地图数据目录"""
    # 相对于 server/ 目录
    candidates = [
        Path(__file__).parent.parent / ".." / ".." / "data" / "map",
        Path(__file__).parent.parent / ".." / "frontend" / "public" / "data" / "map",
        Path(__file__).parent.parent / "data",
    ]
    for c in candidates:
        # 检查是否存在核心数据文件
        if (c / "tiles.json").exists() or (c / "factions.json").exists():
            return c.resolve()
    return Path(__file__).parent.parent / "data"


def _load_json(name: str) -> dict:
    """加载JSON数据文件"""
    data_dir = _map_data_dir()
    path = data_dir / name
    if not path.exists():
        # 尝试 alternate paths
        alt_paths = [
            Path("data") / name,
            Path("server/data") / name,
            Path("frontend/public/data/map") / name,
        ]
        for ap in alt_paths:
            if ap.exists():
                return json.loads(ap.read_text(encoding="utf-8"))
        logger.debug(f"[map_renderer] 数据文件不存在: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_map_png(
    width: int = 1200,
    height: int = 800,
    simplified: bool = True,
) -> bytes:
    """
    渲染沙盘地图PNG预览图
    
    Args:
        width: 图片宽度
        height: 图片高度
        simplified: True=快速轮廓模式, False=完整渲染
        
    Returns:
        PNG字节数据
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError("Pillow 未安装，请运行: pip install Pillow")

    logger.info(f"[map_renderer] 开始渲染地图 {width}x{height}, simplified={simplified}")

    # 加载数据
    tiles_data = _load_json("tiles.json") or {}
    factions_data = _load_json("factions.json") or {}

    # 创建画布
    img = Image.new("RGBA", (width, height), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(img)

    # 构建颜色映射
    faction_color_map = {}
    if isinstance(factions_data, dict):
        factions_list = factions_data.get("factions", factions_data.get("factions", []))
    else:
        factions_list = []
    
    fi = 0
    for f in factions_list:
        fid = f.get("id", f.get("faction_id", ""))
        if fid:
            faction_color_map[fid] = FACTION_COLORS[fi % len(FACTION_COLORS)]
            fi += 1

    # 计算地图边界（所有tile的q/r范围）
    all_coords = []
    tile_map = {}
    if isinstance(tiles_data, dict):
        tile_list = tiles_data.get("tiles", tiles_data.get("features", []))
    else:
        tile_list = []
    
    if not tile_list:
        # 空数据：渲染一个提示图
        draw.text((width // 2 - 100, height // 2 - 10), "[ 沙盘数据未加载 ]", fill=COLOR_TEXT)
        buf = BytesIO()
        img.save(buf, format="PNG")
        logger.info("[map_renderer] 无数据，返回空图")
        return buf.getvalue()

    for t in tile_list:
        # 支持多种数据格式
        tid = t.get("tile_id", t.get("id", ""))
        q = t.get("q", t.get("col", 0))
        r = t.get("r", t.get("row", 0))
        fid = t.get("faction_id", t.get("faction", ""))
        tile_type = t.get("tile_type", t.get("type", "plain"))
        tile_name = t.get("tile_name", t.get("name", tid))
        all_coords.append((q, r))
        tile_map[(q, r)] = {
            "tile_id": tid,
            "faction_id": fid,
            "tile_type": tile_type,
            "tile_name": tile_name,
        }

    if not all_coords:
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # 计算坐标范围和缩放
    min_q = min(c[0] for c in all_coords)
    max_q = max(c[0] for c in all_coords)
    min_r = min(c[1] for c in all_coords)
    max_r = max(c[1] for c in all_coords)

    margin = 30
    scale_x = (width - 2 * margin) / max(max_q - min_q + 1, 1)
    scale_y = (height - 2 * margin) / max(max_r - min_r + 1, 1)
    hex_size = min(scale_x, scale_y) * 0.55

    def axial_to_pixel(q, r):
        """六边形轴向坐标 → 像素坐标（flat-top）"""
        x = margin + (q - min_q) * scale_x
        y = margin + (r - min_r) * scale_y + (q - min_q) * scale_y * 0.5
        return x, y

    # 渲染每个六边形地块
    for (q, r), info in tile_map.items():
        px, py = axial_to_pixel(q, r)
        size = int(hex_size * 0.95)

        fid = info["faction_id"]
        tile_type = info["tile_type"]
        tile_name = info["tile_name"]

        # 确定地块颜色
        if tile_type == "water" or tile_type == "sea":
            fill_color = COLOR_OCEAN if tile_type == "sea" else COLOR_WATER
        elif tile_type == "mountain":
            fill_color = COLOR_MOUNTAIN
        elif fid and fid in faction_color_map:
            fill_color = faction_color_map[fid]
        else:
            fill_color = COLOR_LAND_BASE

        # 近似六边形绘制（用圆+多边形）
        bbox = [
            int(px - size), int(py - size * 0.87),
            int(px + size), int(py + size * 0.87),
        ]
        draw.ellipse(bbox, fill=fill_color[:3], outline=(180, 150, 120, 100))

        # 地块名称注释（仅在关键节点渲染）
        if tile_type in ("city", "capital", "pass", "port") or (q % 5 == 0 and r % 5 == 0):
            # 尝试加载字体
            try:
                font = ImageFont.truetype("simhei.ttf", 8)
            except (OSError, IOError):
                font = ImageFont.load_default()
            draw.text((int(px) - 10, int(py) - 4), tile_name[:4], fill=COLOR_TEXT, font=font)

    # 绘制势力图例
    legend_y = 10
    for fid, color in list(faction_color_map.items())[:10]:
        draw.rectangle([(10, legend_y), (30, legend_y + 12)], fill=color[:3])
        draw.text((35, legend_y), fid.replace("faction_", "")[:12], fill=COLOR_TEXT)
        legend_y += 15

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    logger.info(f"[map_renderer] 渲染完成: {len(tile_map)} 地块")

    return buf.getvalue()
