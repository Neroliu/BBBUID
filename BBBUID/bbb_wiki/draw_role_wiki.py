from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import (
    draw_pic_with_ring,
    draw_text_by_line,
)

from .resource_update import get_wiki_path, get_local_equip_icons

# Resolution scale factor
S = 2

CARD_W = 900 * S
PAD = 40 * S
EQUIP_ICON_SIZE = 64 * S

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

LEVEL_COLORS = {
    "SSS": (255, 80, 80),
    "SS": (255, 140, 60),
    "S": (255, 200, 60),
    "A": (120, 200, 120),
    "B": (100, 160, 220),
    "C": (160, 160, 170),
}

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
    # Scale avatar to cover card width, crop to card height
    aspect = avatar.width / avatar.height
    bg_h = max(card_h, int(card_w / aspect))
    bg = avatar.resize((card_w, bg_h), Image.LANCZOS)
    # Center-crop to card height
    if bg_h > card_h:
        top = (bg_h - card_h) // 2
        bg = bg.crop((0, top, card_w, top + card_h))
    # Apply Gaussian blur
    bg = bg.filter(ImageFilter.GaussianBlur(radius=_s(20)))
    # Darken with overlay
    overlay = Image.new("RGBA", bg.size, (*BG_COLOR, 180))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return bg


async def _draw_header(
    img: Image.Image,
    avatar: Image.Image | None,
    title: str,
    basic_info: dict,
    sub_fields: list[dict],
) -> int:
    draw = ImageDraw.Draw(img)
    y = PAD

    avatar_x = PAD
    avatar_sz = _s(120)
    if avatar:
        avatar_img = avatar.resize((avatar_sz, avatar_sz), Image.LANCZOS)
        avatar_img = await draw_pic_with_ring(avatar_img, avatar_sz, bg_color=BG_COLOR, is_ring=True)
        img.paste(avatar_img, (avatar_x, y), avatar_img)

    text_x = avatar_x + _s(140)
    name_font = _font(36)
    draw.text((text_x, y + _s(8)), title, TEXT_COLOR, name_font)
    y_info = y + _s(52)

    info_font = _font(22)
    info_parts = []
    for key in ["角色属性", "武器类型", "角色定位"]:
        if key in basic_info:
            info_parts.append(basic_info[key])
    if info_parts:
        info_text = " | ".join(info_parts)
        draw.text((text_x, y_info), info_text, SUB_COLOR, info_font)
        y_info += _s(32)

    # Sub fields - skip 往世乐土
    sub_font = _font(18)
    for sf in sub_fields:
        name = sf.get("name", "")
        value = sf.get("value", "")
        if not name or not value or "往世乐土" in name:
            continue
        short_val = value[:50] + ("..." if len(value) > 50 else "")
        draw.text((text_x, y_info), f"{name}: {short_val}", SUB_COLOR, sub_font)
        y_info += _s(26)

    y = max(y + _s(140), y_info + _s(10))
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=_s(1))
    return y + _s(20)


def _draw_score_table(
    img: Image.Image,
    y: int,
    hexagon_data: list[dict],
    final_level_img: Image.Image | None = None,
) -> int:
    if not hexagon_data:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    header_font = _font(18)
    cell_font = _font(18)
    bar_h = _s(16)

    # Section title
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "性能评分", ACCENT_COLOR, title_font)
    y += _s(42)

    # Table header
    col_w = (CARD_W - PAD * 2) // 4
    headers = ["评分项", "等级", "分数", "评分条"]
    hx = PAD
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(32)), fill=TABLE_HEADER_BG, radius=_s(6))
    for i, h in enumerate(headers):
        if i < 3:
            draw.text((hx + _s(12), y + _s(6)), h, SUB_COLOR, header_font)
        hx += col_w
    y += _s(34)

    # Table rows
    for idx, h in enumerate(hexagon_data):
        key = h.get("key", "")
        value = min(h.get("value", 0), 100)
        level = h.get("level", "")

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(34)), fill=row_bg, radius=_s(4))

        # Name
        draw.text((PAD + _s(12), y + _s(7)), key, TEXT_COLOR, cell_font)

        # Level with color
        level_color = LEVEL_COLORS.get(level, SUB_COLOR)
        draw.text((PAD + col_w + _s(12), y + _s(7)), level, level_color, cell_font)

        # Score
        draw.text((PAD + col_w * 2 + _s(12), y + _s(7)), str(value), TEXT_COLOR, cell_font)

        # Score bar
        bar_x = PAD + col_w * 3 + _s(12)
        bar_w = col_w - _s(24)
        bar_y = y + _s(10)
        _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=SCORE_BAR_BG, radius=_s(4))
        fill_w = int(bar_w * value / 100)
        if fill_w > 0:
            bar_color = LEVEL_COLORS.get(level, ACCENT_COLOR)
            _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=bar_color, radius=_s(4))

        y += _s(36)

    # Total score row
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(38)), fill=TABLE_HEADER_BG, radius=_s(4))
    draw.text((PAD + _s(12), y + _s(9)), "总评", ACCENT_COLOR, cell_font)
    if final_level_img:
        icon_size = _s(32)
        fl_resized = final_level_img.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(fl_resized, (PAD + col_w + _s(12), y + _s(3)), fl_resized)
    y += _s(40)

    return y + _s(10)


def _draw_equipment_section(
    img: Image.Image,
    y: int,
    equipments: list[dict],
    equip_icons: dict[str, Image.Image],
) -> int:
    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    name_font = _font(16)
    reason_font = _font(15)

    for eq_group in equipments:
        label = eq_group.get("label", "")
        equips = eq_group.get("equips", [])
        reason = eq_group.get("reason", "")

        # Section label
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
        draw.text((PAD + _s(16), y + _s(4)), f"★ {label}", ACCENT_COLOR, title_font)
        y += _s(40)

        # Equipment grid: 2 per row, each with icon + name
        col_w = (CARD_W - PAD * 2) // 2
        for i, eq in enumerate(equips):
            col = i % 2
            row = i // 2
            ex = PAD + col * col_w
            ey = y + row * (EQUIP_ICON_SIZE + _s(28))

            title = eq.get("title", "")
            icon = equip_icons.get(title)
            if icon:
                icon_resized = icon.resize((EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS)
                img.paste(icon_resized, (ex + _s(8), ey), icon_resized)
            else:
                _draw_rounded_rect(
                    draw,
                    (ex + _s(8), ey, ex + _s(8) + EQUIP_ICON_SIZE, ey + EQUIP_ICON_SIZE),
                    fill=BADGE_BG,
                    radius=_s(8),
                )

            # Equipment name - allow more space
            max_name_w = col_w - EQUIP_ICON_SIZE - _s(28)
            draw_text_by_line(
                img,
                (ex + EQUIP_ICON_SIZE + _s(16), ey + _s(8)),
                title,
                name_font,
                TEXT_COLOR,
                max_name_w,
            )

        rows = (len(equips) + 1) // 2
        y += rows * (EQUIP_ICON_SIZE + _s(28)) + _s(8)

        # Reason text with proper spacing
        if reason:
            y = draw_text_by_line(
                img,
                (PAD + _s(8), y),
                reason,
                reason_font,
                SUB_COLOR,
                CARD_W - PAD * 2 - _s(16),
            )
            y += _s(10)

        y += _s(8)

    return y


def _calc_text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> int:
    if not text:
        return 0
    line_h = font.size + _s(6)
    line_w = 0
    lines = 1
    for ch in text:
        cw = draw.textlength(ch, font=font)
        if line_w + cw > max_w:
            lines += 1
            line_w = 0
        line_w += cw
    return lines * line_h


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
    row = ""
    line_w = 0
    for ch in text:
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


def _draw_advance_table(
    img: Image.Image,
    y: int,
    advance_general: list[dict],
    advance_data: list[dict],
    rank_icons: dict[int, Image.Image],
) -> int:
    if not advance_general:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    header_font = _font(16)
    cell_font = _font(15)
    rank_icon_size = _s(28)
    min_row_h = _s(36)

    # Section title
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "进阶总览", ACCENT_COLOR, title_font)
    y += _s(40)

    # Column widths: Rank | Description | HP | ATK | DEF | SP | CRT | Cost
    # Total = CARD_W - PAD*2
    cols = [_s(60), _s(340), _s(70), _s(70), _s(70), _s(70), _s(70), _s(70)]
    headers = ["星级", "进阶效果", "生命", "攻击", "防御", "能量", "会心", "碎片"]
    desc_max_w = cols[1] - _s(12)

    # Header row
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=TABLE_HEADER_BG, radius=_s(6))
    cx = PAD
    for i, h in enumerate(headers):
        draw.text((cx + _s(6), y + _s(6)), h, SUB_COLOR, header_font)
        cx += cols[i]
    y += _s(32)

    for idx in range(len(advance_general)):
        gen = advance_general[idx]
        adv = advance_data[idx] if idx < len(advance_data) else {}

        # Pre-calculate row height based on desc text
        desc = gen.get("desc", "")
        desc_h = _calc_text_height(draw, desc, cell_font, desc_max_w)
        row_h = max(min_row_h, desc_h + _s(12))

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=_s(4))

        cx = PAD
        # Rank icon - vertically centered
        icon = rank_icons.get(idx)
        if icon:
            icon_y = y + (row_h - rank_icon_size) // 2
            img.paste(icon, (cx + (cols[0] - rank_icon_size) // 2, icon_y), icon)
        cx += cols[0]

        # Description - draw directly, left-aligned, vertically centered
        desc_x = cx + _s(6)
        desc_y = y + (row_h - desc_h) // 2
        _draw_wrapped_text(img, (desc_x, desc_y), desc, cell_font, SUB_COLOR, desc_max_w)
        cx += cols[1]

        # Stats - vertically centered
        stat_y = y + (row_h - _s(18)) // 2
        for j, key in enumerate(["life", "attack", "defense", "energy", "understanding"]):
            val = str(adv.get(key, "-"))
            draw.text((cx + _s(6), stat_y), val, TEXT_COLOR, cell_font)
            cx += cols[2 + j]

        # Fragment cost
        cost = str(gen.get("cost", "-"))
        draw.text((cx + _s(6), stat_y), cost, ACCENT_COLOR, cell_font)

        y += row_h

    return y + _s(10)


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


async def draw_role_wiki(detail: dict) -> Image.Image:
    from .wiki_api import parse_evaluation_from_detail

    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    basic_info = detail.get("basic_info", {})
    title = detail.get("title", "未知角色")

    avatar_url = evaluation.get("avatar", "")
    hexagon = evaluation.get("hexagon", [])
    sub_fields = evaluation.get("subFields", [])
    equipments = evaluation.get("equipments", [])
    advance_general = evaluation.get("advanceGeneral", [])
    advance_data = evaluation.get("advanceData", [])
    final_level_url = evaluation.get("finalLevel", "")

    # Pre-calculate height
    header_h = _s(160)
    score_h = _s(42 + 34 + 40 + 20) + len(hexagon) * _s(36) if hexagon else 0
    equip_h = 0
    for eq_group in equipments:
        equips = eq_group.get("equips", [])
        rows = (len(equips) + 1) // 2
        equip_h += _s(48) + rows * (EQUIP_ICON_SIZE + _s(28)) + _s(20)
        if eq_group.get("reason"):
            equip_h += _s(80)
    advance_h = _s(40 + 32 + 20) + len(advance_general) * _s(60) if advance_general else 0
    footer_h = _s(60)
    total_h = PAD + header_h + score_h + equip_h + advance_h + footer_h + _s(60)

    # Download avatar and create blurred background
    avatar = await _download_image(avatar_url)
    if avatar:
        img = _create_blurred_bg(avatar, CARD_W, total_h)
    else:
        img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)
    y = await _draw_header(img, avatar, title, basic_info, sub_fields)

    # Score table (replaces hexagon radar)
    if hexagon:
        final_level_img = await _download_image(final_level_url) if final_level_url else None
        y = _draw_score_table(img, y, hexagon, final_level_img)

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
                if global_idx in cached_icons:
                    try:
                        icon = Image.open(cached_icons[global_idx]).convert("RGBA")
                        icon = icon.resize((EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS)
                        equip_icons[t] = icon
                    except Exception:
                        pass
                if t not in equip_icons and url:
                    icon = await _get_icon(url, EQUIP_ICON_SIZE)
                    if icon:
                        equip_icons[t] = icon
            global_idx += 1

    # Equipment section
    if equipments:
        y = _draw_equipment_section(img, y, equipments, equip_icons)

    # Advance overview table
    if advance_general:
        rank_icon_size = _s(28)
        rank_icons: dict[int, Image.Image] = {}
        for idx, ag in enumerate(advance_general):
            icon_url = ag.get("icon", "")
            if icon_url:
                icon = await _get_icon(icon_url, rank_icon_size)
                if icon:
                    rank_icons[idx] = icon
        y = _draw_advance_table(img, y, advance_general, advance_data, rank_icons)

    # Footer
    y = _draw_footer(img, y)

    # Crop to actual height
    img = img.crop((0, 0, CARD_W, y))

    return await convert_img(img)
