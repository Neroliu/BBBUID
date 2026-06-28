"""Character card rendering module for BBBUID."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.utils.fonts.fonts import core_font

from ..utils.RESOURCE_PATH import WIKI_PATH
from ..bbb_alias.name_convert import alias_to_char_name, char_name_to_content_id

# Project resource paths
PROJECT_RES_DIR = Path(__file__).parent / "res"
CHAR_RES_DIR = PROJECT_RES_DIR / "char"
STAR_ICON_RES_DIR = PROJECT_RES_DIR / "char" / "star_icon"

# Wiki icon cache
CHAR_ICON_CACHE_DIR = WIKI_PATH / "角色" / "icons"

# Colors
TEXT_WHITE = (240, 240, 245)
TEXT_BLACK = (30, 30, 30)

_font_cache: dict[int, Image.Font.FreeTypeFont] = {}


def _font(size: int) -> Image.Font.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


# Star mapping: API star value (1-5) -> icon filename
STAR_TO_ICON = {
    1: "StarElf_B.png",   # 1 star = B
    2: "StarElf_A.png",   # 2 star = A
    3: "StarElf_S.png",   # 3 star = S
    4: "StarElf_SS.png",  # 4 star = SS
    5: "StarElf_SSS.png", # 5 star = SSS
}


async def _get_cached_char_icon(char_name: str) -> Image.Image:
    """Get character icon from wiki cache by character name (supports alias lookup)."""
    # Resolve alias to standard name, then get content_id
    standard_name = alias_to_char_name(char_name)
    if not standard_name:
        standard_name = char_name

    content_id = char_name_to_content_id(standard_name)
    if content_id:
        cache_path = CHAR_ICON_CACHE_DIR / f"{content_id}.png"
        if cache_path.exists():
            try:
                return Image.open(cache_path).convert("RGBA")
            except Exception:
                pass

    return Image.new("RGBA", (100, 100), (100, 100, 100, 255))


async def _get_cached_star_icon(star: int) -> Image.Image | None:
    """Get star icon from project resources."""
    star_icon_name = STAR_TO_ICON.get(star, "StarElf_B.png")
    star_path = STAR_ICON_RES_DIR / star_icon_name

    if star_path.exists():
        try:
            return Image.open(star_path).convert("RGBA")
        except Exception:
            pass

    return None


def _add_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
    """Add rounded corners to an image."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


async def draw_character_card(
    char_name: str,
    star: int,
    level: int,
    show_name: bool = True,
    show_level: bool = True,
    star_left: bool = False,
) -> Image.Image:
    """Draw a character card with avatar background, character icon, star rating, and name."""
    bg_path = CHAR_RES_DIR / "avatar_bg.png"
    canvas = Image.open(bg_path).convert("RGBA") if bg_path.exists() else Image.new("RGBA", (182, 276), (28, 28, 38, 255))
    draw = ImageDraw.Draw(canvas)
    W, H = canvas.size

    # Get character icon from wiki cache by name (with alias support)
    char_icon = await _get_cached_char_icon(char_name)

    # Resize character icon: width fills card, maintain aspect ratio
    icon_width = W - 23
    icon_height = char_icon.height * icon_width // char_icon.width + 4
    char_icon = char_icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)

    # Position
    icon_x = (W - icon_width) // 2 + 1
    icon_y = 17

    # Add rounded corners (radius 1)
    char_icon = _add_rounded_corners(char_icon, 1)

    canvas.alpha_composite(char_icon, (icon_x, icon_y))

    # Draw star icon
    star_icon = await _get_cached_star_icon(star)
    star_render_height = 40
    if star_icon:
        orig_w, orig_h = star_icon.size
        scale = star_render_height / orig_h
        star_render_w = int(orig_w * scale)
        star_icon = star_icon.resize((star_render_w, star_render_height), Image.Resampling.LANCZOS)
        star_x = 5 if star_left else (W - star_render_w) // 2
        star_y = icon_y + icon_height + 2
        canvas.alpha_composite(star_icon, (star_x, star_y))

    # Draw level text
    if show_level:
        level_text = f"Lv.{level}"
        level_x = W - 30
        level_y = icon_y + icon_height + 20
        draw.text((level_x, level_y), level_text, font=_font(26), fill=TEXT_BLACK, anchor="rm")

    # Draw character name at bottom
    if show_name:
        name_y = H - 35
        draw.text((W // 2, name_y), char_name, font=_font(22), fill=TEXT_WHITE, anchor="mt")

    return canvas
