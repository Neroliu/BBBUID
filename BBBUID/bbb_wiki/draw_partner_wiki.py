import json
import re
from urllib.parse import unquote

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import draw_pic_with_ring

from .draw_utils import (
    S,
    CARD_W,
    PAD,
    BG_COLOR,
    TEXT_COLOR,
    SUB_COLOR,
    ACCENT_COLOR,
    BADGE_BG,
    SECTION_BG,
    TABLE_HEADER_BG,
    TABLE_ROW_BG1,
    TABLE_ROW_BG2,
    SCORE_BAR_BG,
    _s,
    _font,
    _download_image,
    _get_icon,
    _draw_rounded_rect,
    _create_blurred_bg,
    _draw_wrapped_text,
    _calc_text_height,
    _draw_footer,
)

EQUIP_ICON_SIZE = 64 * S

LEVEL_COLORS = {
    "SSS": (255, 80, 80),
    "SS": (255, 140, 60),
    "S": (255, 200, 60),
    "A": (120, 200, 120),
    "B": (100, 160, 220),
    "C": (160, 160, 170),
}


def _extract_main_fields(contents: list) -> dict:
    """Extract mainFields from partner basicIntroduction data."""
    for section in contents:
        text = section.get("text", "")
        match = re.search(r'data-data="([^"]*)"', text)
        if not match:
            continue
        try:
            items = json.loads(unquote(match.group(1)))
        except (json.JSONDecodeError, ValueError):
            continue
        for item in items:
            if item.get("partKey") == "basicIntroduction":
                result = {}
                for mf in item.get("data", {}).get("mainFields", []):
                    if mf.get("nameL") and mf.get("valueL"):
                        result[mf["nameL"]] = mf["valueL"]
                    if mf.get("nameR") and mf.get("valueR"):
                        result[mf["nameR"]] = mf["valueR"]
                return result
    return {}


async def _draw_header(
    img: Image.Image,
    avatar: Image.Image | None,
    title: str,
    evaluation: dict,
    main_fields: dict,
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

    # Final level badge
    final_level_url = evaluation.get("finalLevel", "")
    if final_level_url:
        badge = await _download_image(final_level_url)
        if badge:
            badge_sz = _s(40)
            badge = badge.resize((badge_sz, badge_sz), Image.LANCZOS)
            name_w = draw.textlength(title, font=name_font)
            img.paste(badge, (text_x + int(name_w) + _s(12), y + _s(10)), badge)

    # Main fields: 所属, CV, 特征
    info_font = _font(20)
    info_parts = []
    for key in ["所属", "CV", "特征"]:
        if key in main_fields:
            info_parts.append(f"{key}: {main_fields[key]}")
    if info_parts:
        info_text = " | ".join(info_parts)
        draw.text((text_x, y + _s(50)), info_text, SUB_COLOR, info_font)

    # Sub fields - show 数据信息 and 基本介绍
    sub_font = _font(16)
    y_text = y + _s(80)
    max_w = CARD_W - text_x - PAD
    for sf in evaluation.get("subFields", []):
        name = sf.get("name", "")
        value = sf.get("value", "")
        if not name or not value:
            continue
        draw.text((text_x, y_text), f"【{name}】", ACCENT_COLOR, sub_font)
        y_text += _s(24)
        y_text = _draw_wrapped_text(img, (text_x, y_text), value, sub_font, SUB_COLOR, max_w)
        y_text += _s(8)

    y = max(y + avatar_sz + _s(10), y_text + _s(10))
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

        draw.text((PAD + _s(12), y + _s(7)), key, TEXT_COLOR, cell_font)

        level_color = LEVEL_COLORS.get(level, SUB_COLOR)
        draw.text((PAD + col_w + _s(12), y + _s(7)), level, level_color, cell_font)

        draw.text((PAD + col_w * 2 + _s(12), y + _s(7)), str(value), TEXT_COLOR, cell_font)

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


async def _draw_pairings(
    img: Image.Image,
    y: int,
    equipments: list[dict],
) -> int:
    if not equipments:
        return y

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

        # Valkyrie icons: 2 per row
        col_w = (CARD_W - PAD * 2) // 2
        for i, eq in enumerate(equips):
            col = i % 2
            row = i // 2
            ex = PAD + col * col_w
            ey = y + row * (EQUIP_ICON_SIZE + _s(28))

            title = eq.get("title", "")
            icon_url = eq.get("icon", "")
            icon = await _get_icon(icon_url, EQUIP_ICON_SIZE) if icon_url else None
            if icon:
                img.paste(icon, (ex + _s(8), ey), icon)
            else:
                _draw_rounded_rect(
                    draw,
                    (ex + _s(8), ey, ex + _s(8) + EQUIP_ICON_SIZE, ey + EQUIP_ICON_SIZE),
                    fill=BADGE_BG,
                    radius=_s(8),
                )

            max_name_w = col_w - EQUIP_ICON_SIZE - _s(28)
            _draw_wrapped_text(
                img,
                (ex + EQUIP_ICON_SIZE + _s(16), ey + _s(8)),
                title,
                name_font,
                TEXT_COLOR,
                max_name_w,
            )

        rows = (len(equips) + 1) // 2
        y += rows * (EQUIP_ICON_SIZE + _s(28)) + _s(8)

        if reason:
            y = _draw_wrapped_text(
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


def _draw_advance_table(
    img: Image.Image,
    y: int,
    advance_general: list[dict],
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

    # Column widths: Rank | Description | Cost
    cols = [_s(60), _s(600), _s(100)]
    headers = ["星级", "进阶效果", "碎片"]
    desc_max_w = cols[1] - _s(12)

    # Header row
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=TABLE_HEADER_BG, radius=_s(6))
    cx = PAD
    for i, h in enumerate(headers):
        draw.text((cx + _s(6), y + _s(6)), h, SUB_COLOR, header_font)
        cx += cols[i]
    y += _s(32)

    for idx, ag in enumerate(advance_general):
        desc = ag.get("desc", "")
        cost = str(ag.get("cost", "-"))

        desc_h = _calc_text_height(draw, desc, cell_font, desc_max_w)
        row_h = max(min_row_h, desc_h + _s(12))

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=_s(4))

        cx = PAD
        icon = rank_icons.get(idx)
        if icon:
            icon_y = y + (row_h - rank_icon_size) // 2
            img.paste(icon, (cx + (cols[0] - rank_icon_size) // 2, icon_y), icon)
        cx += cols[0]

        desc_y = y + (row_h - desc_h) // 2
        _draw_wrapped_text(img, (cx + _s(6), desc_y), desc, cell_font, SUB_COLOR, desc_max_w)
        cx += cols[1]

        cost_y = y + (row_h - _s(18)) // 2
        draw.text((cx + _s(6), cost_y), cost, ACCENT_COLOR, cell_font)

        y += row_h

    return y + _s(10)


def _estimate_height(evaluation: dict) -> int:
    h = PAD + _s(240)

    hexagon = evaluation.get("hexagon", [])
    if hexagon:
        h += _s(42 + 34 + 40 + 20) + len(hexagon) * _s(36)

    sub_fields = evaluation.get("subFields", [])
    h += len(sub_fields) * _s(200)

    equipments = evaluation.get("equipments", [])
    for eq_group in equipments:
        equips = eq_group.get("equips", [])
        rows = (len(equips) + 1) // 2
        h += _s(48) + rows * (EQUIP_ICON_SIZE + _s(28)) + _s(20)
        if eq_group.get("reason"):
            h += _s(80)

    advance_general = evaluation.get("advanceGeneral", [])
    h += _s(50) + len(advance_general) * _s(60)

    h += _s(80)
    return h


async def draw_partner_wiki(detail: dict) -> Image.Image:
    from .wiki_api import parse_evaluation_from_detail

    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    title = detail.get("title", "未知协同者")
    main_fields = _extract_main_fields(detail.get("contents", []))

    total_h = int(_estimate_height(evaluation) * 1.5)

    avatar_url = evaluation.get("avatar", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    if avatar:
        img = _create_blurred_bg(avatar, CARD_W, total_h)
    else:
        img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)

    # Header with basic info
    y = await _draw_header(img, avatar, title, evaluation, main_fields)

    # Score table
    hexagon = evaluation.get("hexagon", [])
    if hexagon:
        final_level_url = evaluation.get("finalLevel", "")
        final_level_img = await _download_image(final_level_url) if final_level_url else None
        y = _draw_score_table(img, y, hexagon, final_level_img)

    # Common pairings
    equipments = evaluation.get("equipments", [])
    if equipments:
        y = await _draw_pairings(img, y, equipments)

    # Advance overview
    advance_general = evaluation.get("advanceGeneral", [])
    if advance_general:
        rank_icon_size = _s(28)
        rank_icons: dict[int, Image.Image] = {}
        for idx, ag in enumerate(advance_general):
            icon_url = ag.get("icon", "")
            if icon_url:
                icon = await _get_icon(icon_url, rank_icon_size)
                if icon:
                    rank_icons[idx] = icon
        y = _draw_advance_table(img, y, advance_general, rank_icons)

    # Footer
    y = _draw_footer(img, y)

    img = img.crop((0, 0, CARD_W, y))

    return await convert_img(img)
