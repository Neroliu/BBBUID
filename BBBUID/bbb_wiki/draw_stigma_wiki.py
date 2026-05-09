import re

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.image.convert import convert_img

from .resource_update import (
    get_local_material_icon,
    save_material_icon,
    get_local_stigma_equip_icons,
)
from .draw_utils import (
    S,
    CARD_W,
    PAD,
    BG_COLOR,
    TEXT_COLOR,
    SUB_COLOR,
    ACCENT_COLOR,
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

MATERIAL_ICON_SIZE = 48 * S
EQUIP_ICON_SIZE = 64 * S
RELATIVE_ICON_SIZE = 56 * S
ROLE_ICON_SIZE = 64 * S

STAR_COLOR = (255, 200, 60)


def _extract_content_id(url: str) -> int | None:
    m = re.search(r"/content/(\d+)/detail", url)
    if m:
        return int(m.group(1))
    return None


async def _get_material_icon(content_id: int) -> Image.Image | None:
    local = get_local_material_icon(content_id)
    if local:
        try:
            return Image.open(local).convert("RGBA").resize(
                (MATERIAL_ICON_SIZE, MATERIAL_ICON_SIZE), Image.LANCZOS
            )
        except Exception:
            pass
    from .wiki_api import get_content_detail
    detail = await get_content_detail(content_id)
    if detail:
        icon_url = detail.get("icon", "")
        if icon_url:
            saved = await save_material_icon(content_id, icon_url)
            if saved:
                try:
                    return Image.open(saved).convert("RGBA").resize(
                        (MATERIAL_ICON_SIZE, MATERIAL_ICON_SIZE), Image.LANCZOS
                    )
                except Exception:
                    pass
    return None


async def _get_stigma_equip_icon(idx: int, icon_url: str, content_id: int) -> Image.Image | None:
    # Try local cache first
    cached = get_local_stigma_equip_icons(content_id)
    if idx in cached:
        try:
            return Image.open(cached[idx]).convert("RGBA").resize(
                (EQUIP_ICON_SIZE, EQUIP_ICON_SIZE), Image.LANCZOS
            )
        except Exception:
            pass
    # Download on-demand
    if icon_url:
        icon = await _get_icon(icon_url, EQUIP_ICON_SIZE)
        return icon
    return None


def _draw_star_text(draw: ImageDraw.ImageDraw, x: int, y: int, count: int, font: ImageFont.FreeTypeFont):
    stars = "★" * count
    draw.text((x, y), stars, STAR_COLOR, font)


async def _draw_header(
    img: Image.Image,
    stigma_icon: Image.Image | None,
    title: str,
    info: dict,
) -> int:
    draw = ImageDraw.Draw(img)
    y = PAD

    icon_sz = _s(120)
    if stigma_icon:
        icon_resized = stigma_icon.resize((icon_sz, icon_sz), Image.LANCZOS)
        img.paste(icon_resized, (PAD, y), icon_resized)

    text_x = PAD + icon_sz + _s(20)
    name_font = _font(32)
    draw.text((text_x, y + _s(4)), title, TEXT_COLOR, name_font)

    # Sub fields: 位置, 所属套装, 套装tag
    info_font = _font(18)
    info_parts = []
    for sf in info.get("subFields", []):
        name = sf.get("name", "")
        value = sf.get("value", "")
        if name and value and name != "圣痕技能":
            info_parts.append(f"{name}: {value}")
    info_y = y + _s(44)
    if info_parts:
        info_text = " | ".join(info_parts)
        info_max_w = CARD_W - text_x - PAD
        info_y = _draw_wrapped_text(img, (text_x, info_y), info_text, info_font, SUB_COLOR, info_max_w)

    y = max(y + icon_sz, info_y) + _s(10)

    # Stigma skill description
    skill_text = ""
    for sf in info.get("subFields", []):
        if sf.get("name") == "圣痕技能":
            skill_text = sf.get("value", "")
            break
    if skill_text:
        skill_font = _font(16)
        max_w = CARD_W - PAD * 2
        draw.text((PAD, y), "圣痕技能", ACCENT_COLOR, _font(20))
        y += _s(30)
        y = _draw_wrapped_text(img, (PAD, y), skill_text, skill_font, SUB_COLOR, max_w)
        y += _s(8)

    # Relatives (set mates)
    relatives = info.get("relatives", [])
    if relatives and not (len(relatives) == 1 and relatives[0].get("name") == "无"):
        draw.text((PAD, y), "关联圣痕", ACCENT_COLOR, _font(20))
        y += _s(30)
        for rel in relatives:
            rel_name = rel.get("name", "")
            rel_icon_url = rel.get("icon", "")
            rel_cid = _extract_content_id(rel.get("url", ""))

            icon = None
            if rel_icon_url:
                icon = await _get_icon(rel_icon_url, RELATIVE_ICON_SIZE)
            elif rel_cid:
                from .resource_update import get_local_icon
                icon_path = get_local_icon("圣痕", rel_cid)
                if icon_path:
                    try:
                        icon = Image.open(icon_path).convert("RGBA").resize(
                            (RELATIVE_ICON_SIZE, RELATIVE_ICON_SIZE), Image.LANCZOS
                        )
                    except Exception:
                        pass

            if icon:
                img.paste(icon, (PAD + _s(8), y), icon)
            rel_font = _font(18)
            draw.text((PAD + RELATIVE_ICON_SIZE + _s(16), y + _s(16)), rel_name, TEXT_COLOR, rel_font)
            y += RELATIVE_ICON_SIZE + _s(8)

    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=_s(1))
    return y + _s(20)


def _draw_basic_attr(
    img: Image.Image,
    y: int,
    basic_attr: dict,
) -> int:
    if not basic_attr:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    header_font = _font(18)
    cell_font = _font(18)
    bar_h = _s(16)

    # Section title
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 圣痕技能", ACCENT_COLOR, title_font)
    y += _s(42)

    attrs = basic_attr.get("attr", [])
    if attrs:
        # Table header
        col_w = (CARD_W - PAD * 2) // 4
        headers = ["属性", "数值", "评分", "评分条"]
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=TABLE_HEADER_BG, radius=_s(6))
        hx = PAD
        for i, h in enumerate(headers):
            draw.text((hx + _s(12), y + _s(6)), h, SUB_COLOR, header_font)
            hx += col_w
        y += _s(32)

        # Attribute rows
        for idx, attr in enumerate(attrs):
            key = attr.get("key", "")
            value = attr.get("value", 0)
            score = min(attr.get("score", 0), 100)

            row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
            _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(34)), fill=row_bg, radius=_s(4))

            draw.text((PAD + _s(12), y + _s(7)), key, TEXT_COLOR, cell_font)
            draw.text((PAD + col_w + _s(12), y + _s(7)), str(value), TEXT_COLOR, cell_font)
            draw.text((PAD + col_w * 2 + _s(12), y + _s(7)), str(score), SUB_COLOR, cell_font)

            bar_x = PAD + col_w * 3 + _s(12)
            bar_w = col_w - _s(24)
            bar_y = y + _s(10)
            _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=SCORE_BAR_BG, radius=_s(4))
            fill_w = int(bar_w * score / 100)
            if fill_w > 0:
                _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=ACCENT_COLOR, radius=_s(4))

            y += _s(36)

    # Comment
    comment = basic_attr.get("comment", "")
    if comment:
        comment_font = _font(16)
        max_w = CARD_W - PAD * 2
        y += _s(4)
        draw.text((PAD, y), "玩家评价", ACCENT_COLOR, _font(18))
        y += _s(26)
        y = _draw_wrapped_text(img, (PAD, y), comment, comment_font, SUB_COLOR, max_w)

    return y + _s(10)


def _draw_set_skills(
    img: Image.Image,
    y: int,
    set_skills: list[dict],
) -> int:
    if not set_skills:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    name_font = _font(18)
    desc_font = _font(16)
    max_w = CARD_W - PAD * 2 - _s(16)

    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 套装技能", ACCENT_COLOR, title_font)
    y += _s(40)

    for idx, skill in enumerate(set_skills):
        key = skill.get("key", "")
        value = skill.get("value", "")
        if not key:
            continue

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        name_h = _s(28)
        desc_h = _calc_text_height(draw, value, desc_font, max_w) if value else 0
        row_h = name_h + desc_h + _s(12)

        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=_s(6))
        draw.text((PAD + _s(16), y + _s(6)), key, ACCENT_COLOR, name_font)
        if value:
            _draw_wrapped_text(img, (PAD + _s(16), y + name_h), value, desc_font, SUB_COLOR, max_w)
        y += row_h

    return y + _s(10)


async def _draw_roles(
    img: Image.Image,
    y: int,
    roles: list[dict],
) -> int:
    if not roles:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    name_font = _font(18)
    desc_font = _font(15)
    max_w = CARD_W - PAD * 2 - ROLE_ICON_SIZE - _s(32)

    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 适用角色", ACCENT_COLOR, title_font)
    y += _s(40)

    for role in roles:
        key = role.get("key", "")
        value = role.get("value", "")
        icon_url = role.get("icon", "")

        icon = await _get_icon(icon_url, ROLE_ICON_SIZE) if icon_url else None
        if icon:
            img.paste(icon, (PAD + _s(8), y), icon)

        text_x = PAD + ROLE_ICON_SIZE + _s(20)
        draw.text((text_x, y + _s(4)), key, TEXT_COLOR, name_font)

        if value:
            desc_y = y + _s(28)
            _draw_wrapped_text(img, (text_x, desc_y), value, desc_font, SUB_COLOR, max_w)

        y += ROLE_ICON_SIZE + _s(16)

    return y + _s(10)


async def _draw_equipments(
    img: Image.Image,
    y: int,
    equipments: list[dict],
) -> int:
    if not equipments:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    label_font = _font(18)
    name_font = _font(16)
    reason_font = _font(15)

    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 配装推荐", ACCENT_COLOR, title_font)
    y += _s(40)

    # Collect all equip icons with their content_ids for batch caching
    global_idx = 0
    for eq_group in equipments:
        label = eq_group.get("label", "")
        evaluation = eq_group.get("evaluation", 0)
        equips = eq_group.get("equips", [])
        reason = eq_group.get("reason", "")

        # Label + evaluation
        label_text = f"{label}"
        if evaluation:
            label_text += f"  {evaluation}分"
        draw.text((PAD + _s(8), y), label_text, ACCENT_COLOR, label_font)
        y += _s(30)

        # Equip icons: 3 per row
        col_w = (CARD_W - PAD * 2) // 3
        for i, eq in enumerate(equips):
            col = i % 3
            row = i // 3
            ex = PAD + col * col_w
            ey = y + row * (EQUIP_ICON_SIZE + _s(28))

            title = eq.get("title", "")
            icon_url = eq.get("icon", "")
            eq_cid = eq.get("content_id", 0)

            icon = await _get_stigma_equip_icon(global_idx, icon_url, eq_cid) if icon_url else None
            if icon:
                img.paste(icon, (ex + _s(8), ey), icon)
            else:
                _draw_rounded_rect(
                    draw,
                    (ex + _s(8), ey, ex + _s(8) + EQUIP_ICON_SIZE, ey + EQUIP_ICON_SIZE),
                    fill=(50, 50, 65),
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
            global_idx += 1

        rows = (len(equips) + 2) // 3
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


async def _draw_gain_methods(
    img: Image.Image,
    y: int,
    gain_methods: list[dict],
    forging_materials: list[dict] | None = None,
) -> int:
    if not gain_methods:
        return y

    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    font = _font(16)
    count_font = _font(14)
    max_w = CARD_W - PAD * 2 - _s(16)

    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 获取途径", ACCENT_COLOR, title_font)
    y += _s(40)

    for gm in gain_methods:
        key = gm.get("key", "")
        value = gm.get("value", "")
        if not value:
            continue
        if key == "装备锻造" and forging_materials:
            draw.text((PAD + _s(8), y), f"{key}:", ACCENT_COLOR, _font(18))
            y += _s(28)
            for mat in forging_materials:
                mat_name = mat.get("name", "")
                mat_count = mat.get("count", 0)
                mat_cid = mat.get("content_id", 0)

                icon = await _get_material_icon(mat_cid) if mat_cid else None
                if icon:
                    img.paste(icon, (PAD + _s(8), y), icon)

                text_x = PAD + MATERIAL_ICON_SIZE + _s(12)
                draw.text((text_x, y + _s(4)), mat_name, TEXT_COLOR, font)
                if mat_count:
                    draw.text((text_x, y + _s(28)), f"x{mat_count}", SUB_COLOR, count_font)
                y += MATERIAL_ICON_SIZE + _s(8)
        else:
            text = f"{key}: {value}" if key else value
            y = _draw_wrapped_text(img, (PAD + _s(8), y), text, font, SUB_COLOR, max_w)
            y += _s(4)

    return y + _s(10)


async def _draw_materials(img: Image.Image, y: int, materials: list[dict]) -> int:
    if not materials:
        return y
    draw = ImageDraw.Draw(img)
    title_font = _font(24)
    level_font = _font(18)
    count_font = _font(14)

    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), "★ 进化材料", ACCENT_COLOR, title_font)
    y += _s(40)

    col_level_w = _s(120)
    col_mat_w = CARD_W - PAD * 2 - col_level_w
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=TABLE_HEADER_BG, radius=_s(4))
    draw.text((PAD + _s(12), y + _s(6)), "突破等级", SUB_COLOR, level_font)
    draw.text((PAD + col_level_w + _s(12), y + _s(6)), "所需材料", SUB_COLOR, level_font)
    y += _s(32)

    for idx, level_data in enumerate(materials):
        level = level_data.get("level", "")
        mats = level_data.get("material", [])
        if not mats:
            continue

        item_w = MATERIAL_ICON_SIZE + _s(120)
        items_per_row = max(1, col_mat_w // item_w)
        mat_rows = (len(mats) + items_per_row - 1) // items_per_row
        item_h = MATERIAL_ICON_SIZE + _s(28)
        row_h = max(_s(36), mat_rows * item_h + _s(8))

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=_s(4))

        level_text = f"Lv.{level}"
        level_text_y = y + (row_h - _s(22)) // 2
        draw.text((PAD + _s(12), level_text_y), level_text, ACCENT_COLOR, level_font)

        mat_x = PAD + col_level_w + _s(8)
        mat_y = y + _s(4)
        for i, mat in enumerate(mats):
            col = i % items_per_row
            if col == 0 and i > 0:
                mat_x = PAD + col_level_w + _s(8)
                mat_y += item_h

            name = mat.get("name", "")
            count = mat.get("count", 0)
            cid = _extract_content_id(mat.get("url", ""))

            icon = await _get_material_icon(cid) if cid else None
            if icon:
                img.paste(icon, (mat_x, mat_y), icon)

            count_text = f"x{count}"
            draw.text(
                (mat_x + MATERIAL_ICON_SIZE // 2, mat_y + MATERIAL_ICON_SIZE + _s(2)),
                count_text,
                SUB_COLOR,
                count_font,
                anchor="mt",
            )

            name_x = mat_x + MATERIAL_ICON_SIZE + _s(4)
            draw.text((name_x, mat_y + _s(4)), name, SUB_COLOR, _font(12))

            mat_x += MATERIAL_ICON_SIZE + _s(120)

        y += row_h

    return y + _s(10)


def _estimate_height(stigma_data: dict) -> int:
    h = PAD + _s(200)

    basic_attr = stigma_data.get("basicAttr", {})
    if basic_attr.get("attr"):
        h += _s(50) + len(basic_attr["attr"]) * _s(36)
    if basic_attr.get("comment"):
        h += _s(200)

    set_skills = stigma_data.get("setSkills", [])
    if set_skills:
        h += _s(50) + len(set_skills) * _s(80)

    roles = stigma_data.get("roles", [])
    if roles:
        h += _s(50) + len(roles) * (ROLE_ICON_SIZE + _s(20))

    equipments = stigma_data.get("equipments", [])
    for eq_group in equipments:
        equips = eq_group.get("equips", [])
        rows = (len(equips) + 2) // 3
        h += _s(48) + rows * (EQUIP_ICON_SIZE + _s(28)) + _s(20)
        if eq_group.get("reason"):
            h += _s(80)

    gain_methods = stigma_data.get("gainMethods", [])
    if gain_methods:
        h += _s(50) + len(gain_methods) * _s(30)
    forging_materials = stigma_data.get("forgingMaterials", [])
    if forging_materials:
        h += len(forging_materials) * (MATERIAL_ICON_SIZE + _s(12))

    materials = stigma_data.get("materials", [])
    if materials:
        h += _s(80) + len(materials) * (MATERIAL_ICON_SIZE + _s(60))

    h += _s(80)
    return h


async def draw_stigma_wiki(detail: dict) -> Image.Image:
    from .wiki_api import parse_stigma_data_from_detail

    stigma_data = detail.get("stigma_data") or parse_stigma_data_from_detail(detail)
    title = detail.get("title", "未知圣痕")
    info = stigma_data.get("info", {})

    total_h = int(_estimate_height(stigma_data) * 1.5)

    avatar_url = info.get("avatar", "") or detail.get("icon", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    if avatar:
        img = _create_blurred_bg(avatar, CARD_W, total_h)
    else:
        img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)

    # Header
    y = await _draw_header(img, avatar, title, info)

    # Basic attributes
    basic_attr = stigma_data.get("basicAttr", {})
    if basic_attr:
        y = _draw_basic_attr(img, y, basic_attr)

    # Set skills
    set_skills = stigma_data.get("setSkills", [])
    if set_skills:
        y = _draw_set_skills(img, y, set_skills)

    # Applicable roles
    roles = stigma_data.get("roles", [])
    if roles:
        y = await _draw_roles(img, y, roles)

    # Equipment recommendations
    equipments = stigma_data.get("equipments", [])
    if equipments:
        y = await _draw_equipments(img, y, equipments)

    # Gain methods
    gain_methods = stigma_data.get("gainMethods", [])
    if gain_methods:
        forging_materials = stigma_data.get("forgingMaterials", [])
        y = await _draw_gain_methods(img, y, gain_methods, forging_materials)

    # Evolution materials
    materials = stigma_data.get("materials", [])
    if materials:
        y = await _draw_materials(img, y, materials)

    # Footer
    y = _draw_footer(img, y)

    img = img.crop((0, 0, CARD_W, y))

    return await convert_img(img)
