"""Character card rendering module for BBBUID."""
from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.utils.fonts.fonts import core_font

from ..utils.RESOURCE_PATH import WIKI_PATH

# Project resource paths
PROJECT_RES_DIR = Path(__file__).parent / "res"
CHAR_RES_DIR = PROJECT_RES_DIR / "char"

# Project cache directories (independent from wiki cache)
CHAR_ICON_CACHE_DIR = PROJECT_RES_DIR / "char" / "icons"
STAR_ICON_CACHE_DIR = PROJECT_RES_DIR / "char" / "star_icon"

# External resource for star icons (fallback)
EXTERNAL_RES_DIR = Path("/root/resource/bbbResource")

# Colors
TEXT_WHITE = (240, 240, 245)
TEXT_BLACK = (30, 30, 30)

_font_cache: dict[int, Image.Font.FreeTypeFont] = {}


def _font(size: int) -> Image.Font.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


# Star mapping: star value -> icon filename
STAR_TO_ICON = {
    0: "StarElf_B.png",  # B
    1: "StarElf_A.png",  # A
    2: "StarElf_S.png",  # S
    3: "StarElf_SS.png",  # SS
    4: "StarElf_SSS.png",  # SSS
}


async def _get_cached_char_icon(content_id: str, icon_url: str | None = None) -> Image.Image:
    """Get character icon from project cache, download if missing."""
    cache_path = CHAR_ICON_CACHE_DIR / f"{content_id}.png"

    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            pass

    if icon_url:
        try:
            import httpx
            from io import BytesIO
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(icon_url)
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content)).convert("RGBA")
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    img.save(cache_path, "PNG")
                    return img
        except Exception:
            pass

    return Image.new("RGBA", (100, 100), (100, 100, 100, 255))


async def _get_cached_star_icon(star: int) -> Image.Image | None:
    """Get star icon from cache, copy from external resource if not exists."""
    star_icon_name = STAR_TO_ICON.get(star, "StarElf_B.png")
    cache_path = STAR_ICON_CACHE_DIR / star_icon_name
    external_path = EXTERNAL_RES_DIR / "elfstar" / star_icon_name

    # If cached, return it
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            pass

    # Copy from external resource to cache
    if external_path.exists():
        try:
            img = Image.open(external_path).convert("RGBA")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
            return img
        except Exception:
            pass

    return None


def _add_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
    """Add rounded corners to an image."""
    w, h = img.size
    # Create a rounded rectangle mask
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    # Apply mask
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


async def draw_character_card(
    char_name: str,
    star: int,
    level: int,
    content_id: str,
    icon_url: str | None = None,
) -> Image.Image:
    """Draw a character card with avatar background, character icon, star rating, level, and name."""
    # Load background from project directory
    bg_path = CHAR_RES_DIR / "avatar_bg.png"
    canvas = Image.open(bg_path).convert("RGBA") if bg_path.exists() else Image.new("RGBA", (182, 276), (28, 28, 38, 255))
    draw = ImageDraw.Draw(canvas)
    W, H = canvas.size

    # Get character icon from cache
    char_icon = await _get_cached_char_icon(content_id, icon_url)

    # Resize character icon: width fills card, maintain aspect ratio
    icon_width = W - 23
    icon_height = char_icon.height * icon_width // char_icon.width + 4
    char_icon = char_icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)

    # Position: shift right 1, down
    icon_x = (W - icon_width) // 2 + 1
    icon_y = 17  # 8 + 1 + 8

    # Add rounded corners (radius 4)
    char_icon = _add_rounded_corners(char_icon, 4)

    canvas.alpha_composite(char_icon, (icon_x, icon_y))

    # Draw star icon from cache - proportional scaling 0.8x
    star_icon = await _get_cached_star_icon(star)
    star_render_height = 32
    if star_icon:
        orig_w, orig_h = star_icon.size
        scale = star_render_height / orig_h
        star_render_w = int(orig_w * scale)
        star_icon = star_icon.resize((star_render_w, star_render_height), Image.Resampling.LANCZOS)
        star_x = 19  # Left margin
        star_y = icon_y + icon_height + 2
        canvas.alpha_composite(star_icon, (star_x, star_y))

    # Draw level text
    level_text = f"Lv.{level}"
    level_x = W - 30  # Right margin
    level_y = icon_y + icon_height + 20  # 20px below character icon bottom
    draw.text((level_x, level_y), level_text, font=_font(26), fill=TEXT_BLACK, anchor="rm")

    # Draw character name at bottom
    name_y = H - 35
    draw.text((W // 2, name_y), char_name, font=_font(22), fill=TEXT_WHITE, anchor="mt")

    return canvas
