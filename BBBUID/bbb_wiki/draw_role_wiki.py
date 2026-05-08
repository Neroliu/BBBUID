import math
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import (
    draw_pic_with_ring,
    draw_text_by_line,
)

from .resource_update import get_wiki_path, get_local_equip_icons

CARD_W = 900
PAD = 40
ICON_SIZE = 80
EQUIP_ICON_SIZE = 64

BG_COLOR = (28, 28, 38)
TEXT_COLOR = (230, 230, 235)
SUB_COLOR = (160, 160, 170)
ACCENT_COLOR = (80, 160, 255)
BADGE_BG = (50, 50, 65)
SECTION_BG = (36, 36, 48)

LEVEL_COLORS = {
    "SSS": (255, 80, 80),
    "SS": (255, 140, 60),
    "S": (255, 200, 60),
    "A": (120, 200, 120),
    "B": (100, 160, 220),
    "C": (160, 160, 170),
}

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
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


def _load_local_icon(channel_name: str, content_id: int) -> Image.Image | None:
    icon_path = get_wiki_path(channel_name) / f"{content_id}.png"
    if icon_path.exists():
        return Image.open(icon_path).convert("RGBA")
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
    radius: int = 12,
):
    draw.rounded_rectangle(xy, fill=fill, radius=radius)


def _draw_header(
    img: Image.Image,
    avatar: Image.Image | None,
    title: str,
    basic_info: dict,
    sub_fields: list[dict],
) -> int:
    draw = ImageDraw.Draw(img)
    y = PAD

    # Avatar
    avatar_x = PAD
    if avatar:
        avatar_img = avatar.resize((120, 120), Image.LANCZOS)
        avatar_img = draw_pic_with_ring(avatar_img, 120, bg_color=BG_COLOR, is_ring=True)
        img.paste(avatar_img, (avatar_x, y), avatar_img)

    # Name and basic info
    text_x = avatar_x + 140
    name_font = _font(36)
    draw.text((text_x, y + 8), title, TEXT_COLOR, name_font)
    y_info = y + 52

    info_font = _font(22)
    info_parts = []
    for key in ["角色属性", "武器类型", "角色定位"]:
        if key in basic_info:
            info_parts.append(basic_info[key])
    if info_parts:
        info_text = " | ".join(info_parts)
        draw.text((text_x, y_info), info_text, SUB_COLOR, info_font)
        y_info += 32

    # Sub fields (e.g. 星之环)
    sub_font = _font(18)
    for sf in sub_fields[:2]:
        name = sf.get("name", "")
        value = sf.get("value", "")
        if name and value:
            short_val = value[:50] + ("..." if len(value) > 50 else "")
            draw.text((text_x, y_info), f"{name}: {short_val}", SUB_COLOR, sub_font)
            y_info += 26

    y = max(y + 140, y_info + 10)

    # Divider
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=1)
    return y + 20


def _draw_hexagon(
    img: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    hexagon_data: list[dict],
):
    draw = ImageDraw.Draw(img)
    n = 6
    angles = [math.radians(90 + i * 360 / n) for i in range(n)]

    # Background hexagon grid (3 levels)
    for level in [0.33, 0.66, 1.0]:
        points = []
        for i in range(n):
            px = cx + radius * level * math.cos(angles[i])
            py = cy - radius * level * math.sin(angles[i])
            points.append((px, py))
        draw.polygon(points, outline=(50, 50, 65), width=1)

    # Axis lines
    for i in range(n):
        px = cx + radius * math.cos(angles[i])
        py = cy - radius * math.sin(angles[i])
        draw.line([(cx, cy), (px, py)], fill=(50, 50, 65), width=1)

    # Data polygon
    if hexagon_data:
        data_points = []
        for i, h in enumerate(hexagon_data[:n]):
            val = min(h.get("value", 0), 100) / 100.0
            px = cx + radius * val * math.cos(angles[i])
            py = cy - radius * val * math.sin(angles[i])
            data_points.append((px, py))
        draw.polygon(data_points, fill=(80, 160, 255, 60), outline=ACCENT_COLOR, width=2)

    # Labels
    label_font = _font(18)
    level_font = _font(16)
    label_r = radius + 30
    for i, h in enumerate(hexagon_data[:n]):
        angle = angles[i]
        lx = cx + label_r * math.cos(angle)
        ly = cy - label_r * math.sin(angle)
        key = h.get("key", "")
        level = h.get("level", "")
        tw, th = _text_size(draw, key, label_font)

        # Anchor based on position
        if i == 0:  # top
            anchor = "mb"
        elif i == 3:  # bottom
            anchor = "mt"
        elif i < 3:  # right side
            anchor = "lm"
        else:  # left side
            anchor = "rm"

        draw.text((lx, ly), key, TEXT_COLOR, label_font, anchor=anchor)

        # Level badge
        level_color = LEVEL_COLORS.get(level, SUB_COLOR)
        # Offset level label further out
        if i == 0:
            lly = ly - th - 4
            llx = lx
            lanchor = "mb"
        elif i == 3:
            lly = ly + th + 4
            llx = lx
            lanchor = "mt"
        elif i < 3:
            lly = ly
            llx = lx + tw + 6
            lanchor = "lm"
        else:
            lly = ly
            llx = lx - tw - 6
            lanchor = "rm"
        draw.text((llx, lly), level, level_color, level_font, anchor=lanchor)


def _draw_equipment_section(
    img: Image.Image,
    y: int,
    equipments: list[dict],
    equip_icons: dict[str, Image.Image],
) -> int:
    draw = ImageDraw.Draw(img)
    title_font = _font(26)
    label_font = _font(20)
    name_font = _font(18)
    reason_font = _font(16)

    for eq_group in equipments:
        label = eq_group.get("label", "")
        equips = eq_group.get("equips", [])
        reason = eq_group.get("reason", "")

        # Section background
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 30), fill=SECTION_BG, radius=8)
        draw.text((PAD + 16, y + 4), f"★ {label}", ACCENT_COLOR, title_font)
        y += 42

        # Equipment icons row
        icon_x = PAD + 10
        for eq in equips:
            title = eq.get("title", "")
            icon_url = eq.get("icon", "")
            icon = equip_icons.get(title)
            if icon:
                icon_resized = icon.resize((EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS)
                img.paste(icon_resized, (icon_x, y), icon_resized)
            else:
                _draw_rounded_rect(
                    draw,
                    (icon_x, y, icon_x + EQUIP_ICON_SIZE, y + EQUIP_ICON_SIZE),
                    fill=BADGE_BG,
                    radius=8,
                )
            # Equipment name below icon
            short_name = title[:8] + ("..." if len(title) > 8 else "")
            tw, _ = _text_size(draw, short_name, name_font)
            draw.text(
                (icon_x + EQUIP_ICON_SIZE // 2 - tw // 2, y + EQUIP_ICON_SIZE + 4),
                short_name,
                SUB_COLOR,
                name_font,
            )
            icon_x += EQUIP_ICON_SIZE + 24

        y += EQUIP_ICON_SIZE + 30

        # Reason text
        if reason:
            y = draw_text_by_line(
                img,
                (PAD + 10, y),
                reason,
                reason_font,
                SUB_COLOR,
                CARD_W - PAD * 2 - 20,
            )
            y += 8

        y += 12

    return y


def _draw_footer(img: Image.Image, y: int) -> int:
    draw = ImageDraw.Draw(img)
    footer_font = _font(14)
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=1)
    y += 12
    draw.text(
        (CARD_W // 2, y),
        "BBBUID · 崩坏3 WIKI",
        (80, 80, 95),
        footer_font,
        anchor="mt",
    )
    return y + 30


async def draw_role_wiki(detail: dict) -> Image.Image:
    from .wiki_api import parse_evaluation_from_detail

    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    basic_info = detail.get("basic_info", {})
    title = detail.get("title", "未知角色")

    avatar_url = evaluation.get("avatar", "")
    hexagon = evaluation.get("hexagon", [])
    sub_fields = evaluation.get("subFields", [])
    equipments = evaluation.get("equipments", [])

    # Pre-calculate height
    header_h = 160
    hexagon_h = 380 if hexagon else 0
    equip_h = 0
    for eq in equipments:
        equip_h += 52 + EQUIP_ICON_SIZE + 30
        if eq.get("reason"):
            equip_h += 80
    footer_h = 60
    total_h = PAD + header_h + hexagon_h + equip_h + footer_h + 40

    img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)

    # Header
    avatar = await _download_image(avatar_url)
    y = _draw_header(img, avatar, title, basic_info, sub_fields)

    # Hexagon radar chart
    if hexagon:
        hex_cx = CARD_W // 2
        hex_cy = y + 150
        hex_r = 130
        _draw_hexagon(img, hex_cx, hex_cy, hex_r, hexagon)
        y = hex_cy + hex_r + 50

    # Equipment icons - try local cache first, then download
    equip_icons: dict[str, Image.Image] = {}
    content_id = detail.get("id")
    cached_icons = get_local_equip_icons("角色", content_id) if content_id else {}
    global_idx = 0
    for eq_group in equipments:
        for eq in eq_group.get("equips", []):
            t = eq.get("title", "")
            url = eq.get("icon", "")
            if t and t not in equip_icons:
                # Try cached icon first
                if global_idx in cached_icons:
                    try:
                        icon = Image.open(cached_icons[global_idx]).convert("RGBA")
                        icon = icon.resize((EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS)
                        equip_icons[t] = icon
                    except Exception:
                        pass
                # Fall back to download
                if t not in equip_icons and url:
                    icon = await _get_icon(url, EQUIP_ICON_SIZE)
                    if icon:
                        equip_icons[t] = icon
            global_idx += 1

    # Equipment section
    if equipments:
        y = _draw_equipment_section(img, y, equipments, equip_icons)

    # Footer
    y = _draw_footer(img, y)

    # Crop to actual height
    img = img.crop((0, 0, CARD_W, y))

    return await convert_img(img)
