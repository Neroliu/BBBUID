from io import BytesIO

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
EQUIP_ICON_SIZE = 64

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
    if avatar:
        avatar_img = avatar.resize((120, 120), Image.LANCZOS)
        avatar_img = await draw_pic_with_ring(avatar_img, 120, bg_color=BG_COLOR, is_ring=True)
        img.paste(avatar_img, (avatar_x, y), avatar_img)

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

    # Sub fields - skip 往世乐土
    sub_font = _font(18)
    for sf in sub_fields:
        name = sf.get("name", "")
        value = sf.get("value", "")
        if not name or not value or "往世乐土" in name:
            continue
        short_val = value[:50] + ("..." if len(value) > 50 else "")
        draw.text((text_x, y_info), f"{name}: {short_val}", SUB_COLOR, sub_font)
        y_info += 26

    y = max(y + 140, y_info + 10)
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=1)
    return y + 20


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
    bar_h = 16

    # Section title
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 30), fill=SECTION_BG, radius=8)
    draw.text((PAD + 16, y + 4), "性能评分", ACCENT_COLOR, title_font)
    y += 42

    # Table header
    col_w = (CARD_W - PAD * 2) // 4
    headers = ["评分项", "等级", "分数", "评分条"]
    hx = PAD
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 32), fill=TABLE_HEADER_BG, radius=6)
    for i, h in enumerate(headers):
        if i < 3:
            draw.text((hx + 12, y + 6), h, SUB_COLOR, header_font)
        hx += col_w
    y += 34

    # Table rows
    for idx, h in enumerate(hexagon_data):
        key = h.get("key", "")
        value = min(h.get("value", 0), 100)
        level = h.get("level", "")

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 34), fill=row_bg, radius=4)

        # Name
        draw.text((PAD + 12, y + 7), key, TEXT_COLOR, cell_font)

        # Level with color
        level_color = LEVEL_COLORS.get(level, SUB_COLOR)
        draw.text((PAD + col_w + 12, y + 7), level, level_color, cell_font)

        # Score
        draw.text((PAD + col_w * 2 + 12, y + 7), str(value), TEXT_COLOR, cell_font)

        # Score bar
        bar_x = PAD + col_w * 3 + 12
        bar_w = col_w - 24
        bar_y = y + 10
        _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=SCORE_BAR_BG, radius=4)
        fill_w = int(bar_w * value / 100)
        if fill_w > 0:
            bar_color = LEVEL_COLORS.get(level, ACCENT_COLOR)
            _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=bar_color, radius=4)

        y += 36

    # Total score row
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 38), fill=TABLE_HEADER_BG, radius=4)
    draw.text((PAD + 12, y + 9), "总评", ACCENT_COLOR, cell_font)
    if final_level_img:
        icon_size = 32
        fl_resized = final_level_img.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(fl_resized, (PAD + col_w + 12, y + 3), fl_resized)
    y += 40

    return y + 10


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
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 30), fill=SECTION_BG, radius=8)
        draw.text((PAD + 16, y + 4), f"★ {label}", ACCENT_COLOR, title_font)
        y += 40

        # Equipment grid: 2 per row, each with icon + name
        col_w = (CARD_W - PAD * 2) // 2
        for i, eq in enumerate(equips):
            col = i % 2
            row = i // 2
            ex = PAD + col * col_w
            ey = y + row * (EQUIP_ICON_SIZE + 28)

            title = eq.get("title", "")
            icon = equip_icons.get(title)
            if icon:
                icon_resized = icon.resize((EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS)
                img.paste(icon_resized, (ex + 8, ey), icon_resized)
            else:
                _draw_rounded_rect(
                    draw,
                    (ex + 8, ey, ex + 8 + EQUIP_ICON_SIZE, ey + EQUIP_ICON_SIZE),
                    fill=BADGE_BG,
                    radius=8,
                )

            # Equipment name - allow more space
            max_name_w = col_w - EQUIP_ICON_SIZE - 28
            draw_text_by_line(
                img,
                (ex + EQUIP_ICON_SIZE + 16, ey + 8),
                title,
                name_font,
                TEXT_COLOR,
                max_name_w,
            )

        rows = (len(equips) + 1) // 2
        y += rows * (EQUIP_ICON_SIZE + 28) + 8

        # Reason text with proper spacing
        if reason:
            y = draw_text_by_line(
                img,
                (PAD + 8, y),
                reason,
                reason_font,
                SUB_COLOR,
                CARD_W - PAD * 2 - 16,
            )
            y += 10

        y += 8

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
    rank_icon_size = 28
    row_h = 36

    # Section title
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 30), fill=SECTION_BG, radius=8)
    draw.text((PAD + 16, y + 4), "进阶总览", ACCENT_COLOR, title_font)
    y += 40

    # Column widths: Rank | Description | HP | ATK | DEF | SP | CRT | Cost
    cols = [60, 260, 70, 70, 70, 70, 70, 70]
    headers = ["星级", "进阶效果", "生命", "攻击", "防御", "能量", "会心", "碎片"]

    # Header row
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + 30), fill=TABLE_HEADER_BG, radius=6)
    cx = PAD
    for i, h in enumerate(headers):
        draw.text((cx + 6, y + 6), h, SUB_COLOR, header_font)
        cx += cols[i]
    y += 32

    for idx in range(len(advance_general)):
        gen = advance_general[idx]
        adv = advance_data[idx] if idx < len(advance_data) else {}

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=4)

        cx = PAD
        # Rank icon
        icon = rank_icons.get(idx)
        if icon:
            icon_y = y + (row_h - rank_icon_size) // 2
            img.paste(icon, (cx + (cols[0] - rank_icon_size) // 2, icon_y), icon)
        cx += cols[0]

        # Description - use draw_text_by_line for proper wrapping
        desc = gen.get("desc", "")
        desc_max_w = cols[1] - 12
        draw_text_by_line(
            img,
            (cx + 6, y + 4),
            desc,
            cell_font,
            SUB_COLOR,
            desc_max_w,
        )
        cx += cols[1]

        # Stats
        for j, key in enumerate(["life", "attack", "defense", "energy", "understanding"]):
            val = str(adv.get(key, "-"))
            draw.text((cx + 6, y + 7), val, TEXT_COLOR, cell_font)
            cx += cols[2 + j]

        # Fragment cost
        cost = str(gen.get("cost", "-"))
        draw.text((cx + 6, y + 7), cost, ACCENT_COLOR, cell_font)

        y += row_h

    return y + 10


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
    advance_general = evaluation.get("advanceGeneral", [])
    advance_data = evaluation.get("advanceData", [])
    final_level_url = evaluation.get("finalLevel", "")

    # Pre-calculate height
    header_h = 160
    score_h = 42 + 34 + len(hexagon) * 36 + 40 + 20 if hexagon else 0  # +40 for total row
    equip_h = 0
    for eq_group in equipments:
        equips = eq_group.get("equips", [])
        rows = (len(equips) + 1) // 2
        equip_h += 48 + rows * (EQUIP_ICON_SIZE + 28) + 20
        if eq_group.get("reason"):
            equip_h += 80
    advance_h = 40 + 32 + len(advance_general) * 36 + 20 if advance_general else 0
    footer_h = 60
    total_h = PAD + header_h + score_h + equip_h + advance_h + footer_h + 60

    img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)

    # Header
    avatar = await _download_image(avatar_url)
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
        rank_icon_size = 28
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
