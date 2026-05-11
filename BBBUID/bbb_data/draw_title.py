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
    region_name: str,
    index_data: Dict,
    char_count: int,
) -> Image.Image:
    """Draw title section with avatar, name, UID, level, evaluation, and info.

    Returns a 1000x450 RGBA image (title_bg size).
    """
    # Load background
    bg_path = TITLE_DIR / "title_bg.png"
    if bg_path.exists():
        canvas = Image.open(bg_path).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (1000, 450), (28, 28, 38, 255))

    draw = ImageDraw.Draw(canvas)
    W, H = canvas.size

    # --- Avatar (keep position unchanged) ---
    user_avatar = await get_cached_avatar(ev, ev.user_id)
    avatar_img = draw_decorated_avatar(user_avatar, 179)
    ax = 80
    ay = 130
    canvas.alpha_composite(avatar_img, (ax, ay))

    # --- Nickname (adjusted position relative to avatar) ---
    name_x = ax + 200
    name_y = ay + 10
    draw.text((name_x, name_y), nickname, font=_font(40), fill=TEXT_WHITE)

    # --- UID (no region) ---
    uid_text = f"UID: {uid}"
    draw.text((name_x, name_y + 50), uid_text, font=_font(24), fill=TEXT_GRAY)

    # --- Evaluation icon (top-right) ---
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = EVAL_ICON_DIR / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA")
        eval_icon = eval_icon.resize((130, 130), Image.Resampling.LANCZOS)
        ex = W - 200
        ey = 80
        canvas.alpha_composite(eval_icon, (ex, ey))

    # --- Level badge (top-right, below eval) ---
    level_bg_path = TITLE_DIR / "level_bg.png"
    level_x = W - 200
    level_y = 220

    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        orig_w, orig_h = level_bg.size
        scale = 130 / orig_w
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        level_bg = level_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(level_bg, (level_x, level_y))

        level_text = f"Lv.{level}"
        draw.text((level_x + new_w // 2, level_y + new_h // 2), level_text, font=_font(24), fill=TEXT_WHITE, anchor="mm")

    # --- Info Section ---
    stats = index_data.get("stats", {})
    active_days = stats.get("active_day_number", "?")

    info_bg_path = INFO_DIR / "info_bg.png"
    info_bg_img = None
    info_w = 174
    info_h = 100
    if info_bg_path.exists():
        info_bg_img = Image.open(info_bg_path).convert("RGBA")
        info_w, info_h = info_bg_img.size

    # Left-aligned layout
    info_start_x = 100
    info_y = H - info_h - 20
    info_gap = 30

    # Info 1: 累计登舰
    card1_x = info_start_x
    if info_bg_img:
        canvas.alpha_composite(info_bg_img, (card1_x, info_y))
    draw.text((card1_x + info_w // 2, info_y + 40), f"{active_days}天", font=_font(28), fill=TEXT_WHITE, anchor="mm")
    draw.text((card1_x + info_w // 2, info_y + 70), "累计登舰", font=_font(16), fill=TEXT_DIM, anchor="mm")

    # Info 2: 装甲数
    card2_x = info_start_x + info_w + info_gap
    if info_bg_img:
        canvas.alpha_composite(info_bg_img, (card2_x, info_y))
    draw.text((card2_x + info_w // 2, info_y + 40), str(char_count), font=_font(28), fill=TEXT_WHITE, anchor="mm")
    draw.text((card2_x + info_w // 2, info_y + 70), "装甲数", font=_font(16), fill=TEXT_DIM, anchor="mm")

    return canvas
