from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.fonts.fonts import core_font

# Resolution scale factor
S = 2

CARD_W = 900 * S
PAD = 40 * S

BG_COLOR = (28, 28, 38)
TEXT_COLOR = (230, 230, 235)
SUB_COLOR = (160, 160, 170)
ACCENT_COLOR = (80, 160, 255)
BADGE_BG = (50, 50, 65)
SECTION_BG = (36, 36, 48)
TABLE_HEADER_BG = (45, 45, 60)
TABLE_ROW_BG1 = (32, 32, 44)
TABLE_ROW_BG2 = (38, 38, 52)
SCORE_BAR_BG = (50, 50, 65)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _s(v: int) -> int:
    return v * S


def _font(size: int) -> ImageFont.FreeTypeFont:
    size = _s(size)
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


async def _download_image(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"[崩坏3] [WIKI渲染] 下载图片失败: {e}")
    return None


async def _get_icon(url: str, size: int) -> Image.Image | None:
    img = await _download_image(url)
    if img:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    fill: tuple,
    radius: int = 24,
):
    draw.rounded_rectangle(xy, fill=fill, radius=radius)


def _create_blurred_bg(avatar: Image.Image, card_w: int, card_h: int) -> Image.Image:
    aspect = avatar.width / avatar.height
    bg_h = max(card_h, int(card_w / aspect))
    bg = avatar.resize((card_w, bg_h), Image.LANCZOS)
    if bg_h > card_h:
        top = (bg_h - card_h) // 2
        bg = bg.crop((0, top, card_w, top + card_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=_s(20)))
    overlay = Image.new("RGBA", bg.size, (*BG_COLOR, 180))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return bg


def _calc_text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> int:
    if not text:
        return 0
    line_h = font.size + _s(6)
    total_h = 0
    for para in text.split("\n"):
        if not para:
            total_h += line_h
            continue
        line_w = 0
        lines = 1
        for ch in para:
            cw = draw.textlength(ch, font=font)
            if line_w + cw > max_w:
                lines += 1
                line_w = 0
            line_w += cw
        total_h += lines * line_h
    return total_h


def _draw_wrapped_text(
    img: Image.Image,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_w: int,
) -> int:
    """Draw text with wrapping, using per-character width measurement. Returns final y."""
    x, y = pos
    draw = ImageDraw.Draw(img)
    line_h = font.size + _s(6)
    for para in text.split("\n"):
        if not para:
            y += line_h
            continue
        row = ""
        line_w = 0
        for ch in para:
            cw = draw.textlength(ch, font=font)
            if line_w + cw > max_w and row:
                draw.text((x, y), row, font=font, fill=fill)
                y += line_h
                row = ""
                line_w = 0
            row += ch
            line_w += cw
        if row:
            draw.text((x, y), row, font=font, fill=fill)
            y += line_h
    return y


def _draw_footer(img: Image.Image, y: int) -> int:
    draw = ImageDraw.Draw(img)
    footer_font = _font(14)
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=_s(1))
    y += _s(12)
    draw.text(
        (CARD_W // 2, y),
        "BBBUID · 崩坏3 WIKI",
        (80, 80, 95),
        footer_font,
        anchor="mt",
    )
    return y + _s(30)
