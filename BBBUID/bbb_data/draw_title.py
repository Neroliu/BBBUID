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
    sss_count: int = 0,
    five_star_stigma: int = 0,
    five_star_weapon: int = 0,
) -> Image.Image:
    """Draw title section with avatar, name, UID, level, evaluation, and info."""
    bg_path = TITLE_DIR / "title_bg.png"
    canvas = Image.open(bg_path).convert("RGBA") if bg_path.exists() else Image.new("RGBA", (1000, 450), (28, 28, 38, 255))
    draw = ImageDraw.Draw(canvas)
    W, H = canvas.size

    # Avatar
    user_avatar = await get_cached_avatar(ev, ev.user_id)
    avatar_img = draw_decorated_avatar(user_avatar, 179)
    ax, ay = 80, 80
    canvas.alpha_composite(avatar_img, (ax, ay))

    # Nickname
    name_x = ax + 200
    name_y = 130
    draw.text((name_x, name_y), nickname, font=_font(40), fill=TEXT_WHITE)

    # UID (below nickname)
    draw.text((name_x, name_y + 58), f"UID: {uid}", font=_font(24), fill=TEXT_GRAY)

    # Evaluation icon
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = EVAL_ICON_DIR / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA").resize((130, 130), Image.Resampling.LANCZOS)
        canvas.alpha_composite(eval_icon, (W - 210, 90))

    # Level badge
    level_bg_path = TITLE_DIR / "level_bg.png"
    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        orig_w, orig_h = level_bg.size
        scale = 130 / orig_w
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        level_bg = level_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(level_bg, (W - 210, 230))
        draw.text((W - 210 + new_w // 2, 230 + new_h // 2), f"Lv.{level}", font=_font(24), fill=TEXT_WHITE, anchor="mm")

    # Info Section - 5 cards
    stats = index_data.get("stats", {})
    active_days = stats.get("active_day_number", "?")

    info_bg_path = INFO_DIR / "info_bg.png"
    info_bg_img = None
    info_w, info_h = 174, 100
    if info_bg_path.exists():
        info_bg_img = Image.open(info_bg_path).convert("RGBA")
        info_w, info_h = info_bg_img.size

    info_start_x = 65  # Distance from left edge
    info_y = H - info_h - 60  # Distance from bottom: 60
    info_gap = 5

    # Calculate positions: 8px gap between value bottom and title top
    value_y = info_y + 35
    value_bottom = value_y + 18
    title_y = value_bottom + 8 + 14

    # Info data: (value, title)
    info_items = [
        (f"{active_days}天", "累计登舰"),
        (str(char_count), "装甲数"),
        (str(sss_count), "SSS女武神"),
        (str(five_star_stigma), "五星圣痕"),
        (str(five_star_weapon), "五星武器"),
    ]

    for i, (value, title) in enumerate(info_items):
        card_x = info_start_x + i * (info_w + info_gap)
        if info_bg_img:
            canvas.alpha_composite(info_bg_img, (card_x, info_y))
        draw.text((card_x + info_w // 2, value_y), value, font=_font(36), fill=TEXT_WHITE, anchor="mm")
        draw.text((card_x + info_w // 2, title_y), title, font=_font(28), fill=TEXT_DIM, anchor="mm")

    return canvas
