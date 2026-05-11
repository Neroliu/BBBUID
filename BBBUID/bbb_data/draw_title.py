"""Common title rendering module for BBBUID cards."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.fonts.fonts import core_font

from .avatar_utils import get_cached_avatar, draw_decorated_avatar

# Resource paths
RES_DIR = Path(__file__).parent / "res"
TITLE_DIR = RES_DIR / "title"
EVAL_ICON_DIR = RES_DIR / "eval_icon"
INFO_DIR = RES_DIR / "info"

# Colors
TEXT_WHITE = (240, 240, 245)
TEXT_GRAY = (180, 180, 195)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


# Evaluation rating to icon mapping
EVAL_RATING_TO_ICON = {
    "C": "SealedDanIcon01.png",
    "B": "SealedDanIcon02.png",
    "A": "SealedDanIcon03.png",
    "S": "SealedDanIcon04.png",
    "SS": "SealedDanIcon06.png",
    "SSS": "SealedDanIcon07.png",
}


async def draw_title(
    ev,
    uid: str,
    nickname: str,
    level: int,
    rating: str,
    region_name: str = "",
) -> Image.Image:
    """Draw title section with avatar, name, UID, level, and evaluation.

    Returns a 1000x450 RGBA image.
    """
    # Load background
    bg_path = TITLE_DIR / "title_bg.png"
    if bg_path.exists():
        canvas = Image.open(bg_path).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (1000, 450), (28, 28, 38, 255))

    draw = ImageDraw.Draw(canvas)

    # --- Avatar ---
    user_avatar = await get_cached_avatar(ev, ev.user_id)
    avatar_img = draw_decorated_avatar(user_avatar, 100)
    ax = 60
    ay = 170
    canvas.alpha_composite(avatar_img, (ax, ay))

    # --- Nickname ---
    name_x = ax + 110
    name_y = ay + 15
    draw.text((name_x, name_y), nickname, font=_font(36), fill=TEXT_WHITE)

    # --- UID and Server ---
    uid_text = f"{region_name}  UID: {uid}" if region_name else f"UID: {uid}"
    draw.text((name_x, name_y + 48), uid_text, font=_font(22), fill=TEXT_GRAY)

    # --- Level badge ---
    level_bg_path = TITLE_DIR / "level_bg.png"
    level_x = name_x + int(draw.textlength(nickname, font=_font(36))) + 16
    level_y = name_y + 5

    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        # Scale to fit
        level_bg = level_bg.resize((100, 32), Image.Resampling.LANCZOS)
        canvas.alpha_composite(level_bg, (level_x, level_y))

    level_text = f"Lv.{level}"
    draw.text((level_x + 50, level_y + 6), level_text, font=_font(18), fill=TEXT_WHITE, anchor="mt")

    # --- Evaluation icon ---
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = EVAL_ICON_DIR / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA")
        eval_icon = eval_icon.resize((128, 128), Image.Resampling.LANCZOS)
        ex = canvas.width - 180
        ey = 170
        canvas.alpha_composite(eval_icon, (ex, ey))

    return canvas


async def draw_info_section(
    index_data: Dict,
    char_count: int,
) -> Image.Image:
    """Draw info section with stats like active days and armor count.

    Returns an RGBA image with 2 info cards side by side.
    """
    stats = index_data.get("stats", {})
    active_days = stats.get("active_day_number", "?")

    # Create canvas for info row
    info_w = 174
    info_h = 100
    gap = 20
    total_w = info_w * 2 + gap

    canvas = Image.new("RGBA", (total_w, info_h), (0, 0, 0, 0))

    info_bg_path = INFO_DIR / "info_bg.png"

    # Info 1: 累计登舰
    if info_bg_path.exists():
        info_bg = Image.open(info_bg_path).convert("RGBA")
        canvas.alpha_composite(info_bg, (0, 0))

    draw = ImageDraw.Draw(canvas)
    draw.text((87, 30), "累计登舰", font=_font(16), fill=TEXT_GRAY, anchor="mt")
    draw.text((87, 60), f"{active_days}天", font=_font(28), fill=TEXT_WHITE, anchor="mt")

    # Info 2: 装甲数
    if info_bg_path.exists():
        info_bg = Image.open(info_bg_path).convert("RGBA")
        canvas.alpha_composite(info_bg, (info_w + gap, 0))

    draw.text((info_w + gap + 87, 30), "装甲数", font=_font(16), fill=TEXT_GRAY, anchor="mt")
    draw.text((info_w + gap + 87, 60), f"{char_count}", font=_font(28), fill=TEXT_WHITE, anchor="mt")

    return canvas
