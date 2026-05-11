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
TEXT_DIM = (130, 130, 148)

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

    # --- Avatar (use original decoration size 179x190 for best quality) ---
    user_avatar = await get_cached_avatar(ev, ev.user_id)
    avatar_img = draw_decorated_avatar(user_avatar, 179)  # Original size, no scaling
    ax = 80
    ay = 130
    canvas.alpha_composite(avatar_img, (ax, ay))

    # --- Nickname ---
    name_x = ax + 200  # Right side of avatar (179 width + spacing)
    name_y = ay + 20   # Aligned with avatar top
    draw.text((name_x, name_y), nickname, font=_font(40), fill=TEXT_WHITE)

    # --- Level badge (same row as nickname, after the name) ---
    level_bg_path = TITLE_DIR / "level_bg.png"
    name_width = int(draw.textlength(nickname, font=_font(40)))
    level_x = name_x + name_width + 20
    level_y = name_y + 5

    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        # Keep original aspect ratio, scale height to match text
        level_bg = level_bg.resize((90, 30), Image.Resampling.LANCZOS)
        canvas.alpha_composite(level_bg, (level_x, level_y))

    level_text = f"Lv.{level}"
    draw.text((level_x + 45, level_y + 5), level_text, font=_font(18), fill=TEXT_WHITE)

    # --- UID and Server (below nickname) ---
    uid_text = f"{region_name}  UID: {uid}" if region_name else f"UID: {uid}"
    draw.text((name_x, name_y + 55), uid_text, font=_font(24), fill=TEXT_GRAY)

    # --- Evaluation icon (right side) ---
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = EVAL_ICON_DIR / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA")
        # Use larger size for better quality
        eval_icon = eval_icon.resize((140, 140), Image.Resampling.LANCZOS)
        ex = canvas.width - 200
        ey = 140
        canvas.alpha_composite(eval_icon, (ex, ey))

    return canvas


async def draw_info_section(
    index_data: Dict,
    char_count: int,
) -> Image.Image:
    """Draw info section with stats like active days and armor count.

    Returns an RGBA image with 2 info cards side by side.
    Each card: title at top, value in info_bg below.
    """
    stats = index_data.get("stats", {})
    active_days = stats.get("active_day_number", "?")

    # Dimensions
    info_w = 174
    info_h = 100
    gap = 30
    total_w = info_w * 2 + gap
    total_h = info_h + 30  # Extra space for title above

    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    info_bg_path = INFO_DIR / "info_bg.png"
    info_bg_img = None
    if info_bg_path.exists():
        info_bg_img = Image.open(info_bg_path).convert("RGBA")

    # Info 1: 累计登舰
    card1_x = 0
    title1_y = 0
    bg1_y = 25

    # Title above bg
    draw.text((card1_x + info_w // 2, title1_y + 12), "累计登舰", font=_font(18), fill=TEXT_DIM)
    # Info bg
    if info_bg_img:
        canvas.alpha_composite(info_bg_img, (card1_x, bg1_y))
    # Value inside bg (centered)
    draw.text((card1_x + info_w // 2, bg1_y + 55), f"{active_days}天", font=_font(32), fill=TEXT_WHITE)

    # Info 2: 装甲数
    card2_x = info_w + gap
    # Title above bg
    draw.text((card2_x + info_w // 2, title1_y + 12), "装甲数", font=_font(18), fill=TEXT_DIM)
    # Info bg
    if info_bg_img:
        canvas.alpha_composite(info_bg_img, (card2_x, bg1_y))
    # Value inside bg (centered)
    draw.text((card2_x + info_w // 2, bg1_y + 55), str(char_count), font=_font(32), fill=TEXT_WHITE)

    return canvas
