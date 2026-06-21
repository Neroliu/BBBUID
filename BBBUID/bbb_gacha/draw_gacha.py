"""崩坏3抽卡记录 PIL 渲染模块。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from ..bbb_data.draw_title import draw_title

# --- Resource Paths ---
RES_DIR = Path(__file__).parent / "res"

# --- Canvas ---
W = 1080

# --- Colors ---
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (200, 200, 210)
TEXT_DIM = (160, 160, 175)
GOLD_YELLOW = (254, 231, 114)  # #FEE772
PITY_RED = (255, 80, 80)

# --- Font Cache ---
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_italic_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

SKEW = 0.25  # italic slant factor

# --- Pool type hints ---
POOL_HINTS = {
    "char": "S角色",
    "weapon": "5星武器",
    "partner": "协同者",
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


def _ifont(size: int) -> ImageFont.FreeTypeFont:
    if size not in _italic_font_cache:
        _italic_font_cache[size] = core_font(size)
    return _italic_font_cache[size]


def _draw_italic_text(
    canvas: Image.Image,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...],
    anchor: str | None = None,
) -> None:
    """Draw text with an italic slant by applying an affine skew transform."""
    if not text:
        return

    PAD = 16
    draw = ImageDraw.Draw(canvas)
    glyph_bbox = draw.textbbox((0, 0), text, font=font)
    gx0, gy0, gx1, gy1 = glyph_bbox
    gw = gx1 - gx0
    gh = gy1 - gy0

    tmp_w = gw + PAD + int(gh * SKEW) + PAD
    tmp_h = gh + PAD + PAD
    ink_x = PAD - gx0
    ink_y = PAD - gy0

    tmp = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    tmp_draw.text((ink_x, ink_y), text, font=font, fill=fill)

    pivot_y = PAD + gh
    skewed = tmp.transform(
        (tmp_w, tmp_h),
        Image.AFFINE,
        (1, SKEW, -SKEW * pivot_y, 0, 1, 0),
        Image.Resampling.BICUBIC,
    )

    bbox = draw.textbbox(xy, text, font=font, anchor=anchor)
    canvas.alpha_composite(skewed, (bbox[0] - PAD, bbox[1] - PAD))


def _get_emotion_icon(avg_pulls: float) -> Path | None:
    """根据平均抽数获取对应的表情图标路径。"""
    emotion_dir = RES_DIR / "servantemoticon"
    if avg_pulls < 50:
        name = "Emotion1_Type7_4.png"
    elif avg_pulls < 60:
        name = "Emotion1_Type7_2.png"
    elif avg_pulls < 70:
        name = "Emotion1_Type7_7.png"
    elif avg_pulls < 80:
        name = "Emotion1_Type8_1.png"
    elif avg_pulls < 90:
        name = "Emotion1_Type7_1.png"
    else:
        name = "Emotion1_Type7_14.png"

    path = emotion_dir / name
    return path if path.exists() else None


def _load_background() -> Image.Image:
    """加载背景图，按宽度1080等比缩放，居中裁剪到画布高度。"""
    bg_path = RES_DIR / "bg.jpg"
    if bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA")
        iw, ih = bg.size
        # 等比缩放：宽度适配 W
        scale = W / iw
        new_w = W
        new_h = round(ih * scale)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
    else:
        bg = Image.new("RGBA", (W, 800), (30, 35, 50, 255))
    return bg


async def _draw_pool_section(pool: Dict) -> Image.Image:
    """绘制单个卡池区域。"""
    pool_type = pool.get("type", "char")
    pool_name = pool.get("name", "未知卡池")
    items = pool.get("items", [])
    total_pulls = pool.get("total_pulls", 0)
    gold_count = pool.get("gold_count", 0)
    avg_pulls = pool.get("avg_pulls", 0)
    max_pulls = pool.get("max_pulls", 0)
    avg_rate = pool.get("avg_rate", "0%")
    start_time = pool.get("start_time", "")
    end_time = pool.get("end_time", "")
    current_pity = pool.get("current_pity", 0)

    # 卡片宽度
    card_w = W - 60  # 左右各30px边距

    # 计算网格区域高度
    items_per_row = 8
    item_size = 100
    item_gap = 10
    num_rows = (len(items) + items_per_row - 1) // items_per_row if items else 1
    grid_h = num_rows * (item_size + item_gap) + item_gap

    # 标题区高度
    banner_h = 80

    # 统计区高度
    stats_h = 60

    # 总高度
    total_h = banner_h + stats_h + grid_h + 30

    # 创建画布
    canvas = Image.new("RGBA", (card_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 绘制 banner 背景
    banner_path = RES_DIR / "banner.png"
    if banner_path.exists():
        banner_bg = Image.open(banner_path).convert("RGBA")
        banner_bg = banner_bg.resize((card_w, banner_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(banner_bg, (0, 0))

    # --- Banner 区域：全部斜体 ---
    # 卡池名称 (46px, #FEE772)
    _draw_italic_text(canvas, (20, 17), pool_name, _ifont(46), GOLD_YELLOW)

    # "已x抽未出" — x 是红色 34px，其他白色 28px
    hint = POOL_HINTS.get(pool_type, "S角色")
    pity_x = 200
    # "已"
    _draw_italic_text(canvas, (pity_x, 26), "已", _ifont(28), TEXT_WHITE)
    pity_x += 30
    # 抽数（红色 34px）
    pity_text = str(current_pity)
    _draw_italic_text(canvas, (pity_x, 22), pity_text, _ifont(34), PITY_RED)
    pity_bbox = draw.textbbox((0, 0), pity_text, font=_ifont(34))
    pity_x += pity_bbox[2] - pity_bbox[0] + 8
    # "抽未出"
    _draw_italic_text(canvas, (pity_x, 26), "抽未出", _ifont(28), TEXT_WHITE)

    # 抽卡时间范围（斜体 18px 暗灰）
    time_text = f"{start_time} ~ {end_time}"
    _draw_italic_text(canvas, (500, 35), time_text, _ifont(18), TEXT_DIM)

    # 右侧表情图标
    emotion_path = _get_emotion_icon(avg_pulls)
    if emotion_path:
        emotion_img = Image.open(emotion_path).convert("RGBA")
        emotion_img = emotion_img.resize((60, 60), Image.Resampling.LANCZOS)
        canvas.alpha_composite(emotion_img, (card_w - 80, 10))

    # 统计数据区
    stats_y = banner_h + 10
    stats_items = [
        ("平均抽数", f"{avg_pulls:.1f}"),
        ("最高抽数", str(max_pulls)),
        ("平均出率", avg_rate),
    ]

    stat_x = 30
    for label, value in stats_items:
        draw.text((stat_x, stats_y), value, font=_font(26), fill=TEXT_WHITE)
        draw.text((stat_x, stats_y + 32), label, font=_font(16), fill=TEXT_DIM)
        stat_x += 200

    # 角色/武器网格
    grid_y = banner_h + stats_h + 10
    grid_start_x = (card_w - (items_per_row * (item_size + item_gap) - item_gap)) // 2

    # 加载边框
    frame_path = RES_DIR / "char_frame2.png"
    frame_img = None
    if frame_path.exists():
        frame_img = Image.open(frame_path).convert("RGBA")

    for i, item in enumerate(items):
        row = i // items_per_row
        col = i % items_per_row

        item_x = grid_start_x + col * (item_size + item_gap)
        item_y = grid_y + row * (item_size + item_gap)

        # 绘制边框背景
        if frame_img:
            framed = frame_img.resize((item_size, item_size + 25), Image.Resampling.LANCZOS)
            canvas.alpha_composite(framed, (item_x, item_y))

        # 绘制角色/武器图标
        icon_path = item.get("icon_path")
        if icon_path and isinstance(icon_path, Path) and icon_path.exists():
            try:
                icon = Image.open(icon_path).convert("RGBA")
                icon = icon.resize((item_size - 10, item_size - 10), Image.Resampling.LANCZOS)
                canvas.alpha_composite(icon, (item_x + 5, item_y + 5))
            except Exception:
                pass

        # 绘制抽数标注
        pulls = item.get("pulls", 0)
        pulls_text = f"{pulls}抽"
        draw.text(
            (item_x + item_size // 2, item_y + item_size + 5),
            pulls_text,
            font=_font(14),
            fill=TEXT_WHITE,
            anchor="mt",
        )

    return canvas


async def draw_gacha_img(data: Dict, ev=None) -> bytes:
    """绘制抽卡记录图片，返回 PNG 字节流。"""
    # 加载背景（等比缩放，不拉伸）
    bg = _load_background()
    bg_w, bg_h = bg.size

    # 获取 index_data 用于 draw_title
    index_data = data.get("index_data", {})
    uid = data.get("uid", "")
    nickname = data.get("nickname", "未知舰长")
    level = data.get("level", 0)
    rating = data.get("rating", "C")

    # 复用 bbbmr 的玩家信息条
    try:
        title_img = await draw_title(
            ev=ev,
            uid=uid,
            nickname=nickname,
            level=level,
            rating=rating,
            region_name="",
            index_data=index_data,
            char_count=0,
        )
    except Exception as e:
        logger.warning(f"[崩坏3] [抽卡渲染] draw_title 失败: {e}")
        title_img = Image.new("RGBA", (W, 180), (30, 35, 50, 255))

    # 如果 title_img 宽度不等于 W，等比缩放
    if title_img.width != W:
        scale = W / title_img.width
        new_h = round(title_img.height * scale)
        title_img = title_img.resize((W, new_h), Image.Resampling.LANCZOS)

    title_h = title_img.height

    # 计算总高度：标题 + 卡池区域
    pool_heights = []
    for pool in data.get("pools", []):
        pool_img = await _draw_pool_section(pool)
        pool_heights.append(pool_img)

    total_h = title_h + sum(p.height for p in pool_heights) + 20 * len(pool_heights) + 40

    # 创建最终画布，从背景中裁剪（不拉伸）
    final_h = max(total_h, bg_h)
    canvas = Image.new("RGBA", (W, final_h), (30, 35, 50, 255))

    # 背景居中铺设（超出部分截断）
    bg_y = (final_h - bg_h) // 2
    canvas.alpha_composite(bg, (0, bg_y))

    # 绘制玩家信息条
    canvas.alpha_composite(title_img, (0, 0))

    # 绘制每个卡池
    current_y = title_h + 20
    for pool_img in pool_heights:
        canvas.alpha_composite(pool_img, (30, current_y))
        current_y += pool_img.height + 20

    # 裁剪到实际内容高度
    canvas = canvas.crop((0, 0, W, current_y + 20))

    return await convert_img(canvas)
