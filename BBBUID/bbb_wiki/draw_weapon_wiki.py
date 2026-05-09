import re

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.image.convert import convert_img

from .resource_update import get_local_material_icon, save_material_icon
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
    # Download on-demand
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


def _draw_section_title(draw: ImageDraw.ImageDraw, y: int, title: str) -> int:
    _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + _s(30)), fill=SECTION_BG, radius=_s(8))
    draw.text((PAD + _s(16), y + _s(4)), f"★ {title}", ACCENT_COLOR, _font(24))
    return y + _s(40)


def _draw_sub_title(draw: ImageDraw.ImageDraw, y: int, title: str) -> int:
    draw.text((PAD + _s(8), y), title, ACCENT_COLOR, _font(18))
    return y + _s(30)


def _draw_star_text(draw: ImageDraw.ImageDraw, x: int, y: int, count: int, font: ImageFont.FreeTypeFont):
    stars = "★" * count
    draw.text((x, y), stars, STAR_COLOR, font)


def _draw_header(
    img: Image.Image,
    weapon_icon: Image.Image | None,
    title: str,
    info: dict,
) -> int:
    draw = ImageDraw.Draw(img)
    y = PAD

    icon_sz = _s(100)
    if weapon_icon:
        icon_resized = weapon_icon.resize((icon_sz, icon_sz), Image.LANCZOS)
        img.paste(icon_resized, (PAD, y), icon_resized)

    text_x = PAD + icon_sz + _s(20)
    name_font = _font(32)
    draw.text((text_x, y + _s(4)), title, TEXT_COLOR, name_font)

    star_value = info.get("starValue", 0)
    if star_value:
        _draw_star_text(draw, text_x, y + _s(42), star_value, _font(20))

    # Attributes
    attrs = info.get("attr", [])
    if attrs:
        attr_font = _font(20)
        attr_parts = []
        for a in attrs:
            key = a.get("key", "")
            val = a.get("value", "")
            if key and val:
                attr_parts.append(f"{key} {val}")
        if attr_parts:
            attr_text = "  |  ".join(attr_parts)
            draw.text((text_x, y + _s(70)), attr_text, SUB_COLOR, attr_font)

    y = max(y + icon_sz, y + _s(100)) + _s(10)
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=(60, 60, 75), width=_s(1))
    return y + _s(20)


def _draw_skills(img: Image.Image, y: int, skills: list[dict]) -> int:
    if not skills:
        return y
    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "武器技能")

    name_font = _font(18)
    desc_font = _font(16)
    max_w = CARD_W - PAD * 2 - _s(16)

    for idx, skill in enumerate(skills):
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


def _draw_gain_methods(img: Image.Image, y: int, gain_methods: list[dict]) -> int:
    if not gain_methods:
        return y
    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "获取方式")

    font = _font(16)
    max_w = CARD_W - PAD * 2 - _s(16)

    for gm in gain_methods:
        key = gm.get("key", "")
        value = gm.get("value", "")
        text = f"{key}: {value}" if key else value
        if not text:
            continue
        y = _draw_wrapped_text(img, (PAD + _s(8), y), text, font, SUB_COLOR, max_w)
        y += _s(4)

    return y + _s(10)


async def _draw_material_item(
    img: Image.Image,
    x: int,
    y: int,
    name: str,
    count: int,
    icon_url: str,
    cid: int | None,
) -> None:
    draw = ImageDraw.Draw(img)
    name_font = _font(16)
    count_font = _font(14)

    icon = None
    if icon_url:
        icon = await _get_icon(icon_url, MATERIAL_ICON_SIZE)
    if not icon and cid:
        icon = await _get_material_icon(cid)

    if icon:
        img.paste(icon, (x, y), icon)

    text_x = x + MATERIAL_ICON_SIZE + _s(12)
    draw.text((text_x, y + _s(4)), name, TEXT_COLOR, name_font)
    if count:
        draw.text((text_x, y + _s(28)), f"x{count}", SUB_COLOR, count_font)


async def _draw_forging(
    img: Image.Image,
    y: int,
    forging: dict,
) -> int:
    material = forging.get("material", [])
    other_material = forging.get("otherMaterial", [])
    if not material and not other_material:
        return y

    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "悬赏锻造")

    # 超限素材
    if material:
        y = _draw_sub_title(draw, y, "超限素材")
        for item in material:
            name = item.get("name", "")
            num = item.get("num", 0)
            icon_url = item.get("icon", "")
            cid = _extract_content_id(item.get("url", ""))
            await _draw_material_item(img, PAD + _s(8), y, name, num, icon_url, cid)
            y += MATERIAL_ICON_SIZE + _s(12)

    # 其他素材
    if other_material:
        y = _draw_sub_title(draw, y, "其他素材")
        for item in other_material:
            name = item.get("name", "")
            num = item.get("num", 0)
            icon_url = item.get("icon", "")
            cid = _extract_content_id(item.get("url", ""))
            await _draw_material_item(img, PAD + _s(8), y, name, num, icon_url, cid)
            y += MATERIAL_ICON_SIZE + _s(12)

    return y + _s(10)


async def _draw_materials(img: Image.Image, y: int, materials: list[dict]) -> int:
    if not materials:
        return y
    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "进化材料")

    level_font = _font(18)
    name_font = _font(16)
    count_font = _font(14)

    # Table header
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

        # Calculate row height: icon + count text below + name + padding
        item_w = MATERIAL_ICON_SIZE + _s(120)
        items_per_row = max(1, col_mat_w // item_w)
        mat_rows = (len(mats) + items_per_row - 1) // items_per_row
        item_h = MATERIAL_ICON_SIZE + _s(28)  # icon + count text
        row_h = max(_s(36), mat_rows * item_h + _s(8))

        row_bg = TABLE_ROW_BG1 if idx % 2 == 0 else TABLE_ROW_BG2
        _draw_rounded_rect(draw, (PAD, y, CARD_W - PAD, y + row_h), fill=row_bg, radius=_s(4))

        # Level text - vertically centered
        level_text = f"Lv.{level}"
        level_text_y = y + (row_h - _s(22)) // 2
        draw.text((PAD + _s(12), level_text_y), level_text, ACCENT_COLOR, level_font)

        # Material icons in grid
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

            # Draw count below icon
            count_text = f"x{count}"
            draw.text(
                (mat_x + MATERIAL_ICON_SIZE // 2, mat_y + MATERIAL_ICON_SIZE + _s(2)),
                count_text,
                SUB_COLOR,
                count_font,
                anchor="mt",
            )

            # Draw material name next to icon
            name_x = mat_x + MATERIAL_ICON_SIZE + _s(4)
            max_name_w = _s(120)
            draw.text((name_x, mat_y + _s(4)), name, SUB_COLOR, _font(12))

            mat_x += MATERIAL_ICON_SIZE + _s(120)

        y += row_h

    return y + _s(10)


async def _draw_sync_materials(img: Image.Image, y: int, sync_mats: list[dict]) -> int:
    if not sync_mats:
        return y
    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "同调素材")

    font = _font(16)
    max_w = CARD_W - PAD * 2 - _s(16)

    for sm in sync_mats:
        key = sm.get("key", "")
        value = sm.get("value", "")
        text = f"{key}: {value}" if key else value
        if not text:
            continue
        y = _draw_wrapped_text(img, (PAD + _s(8), y), text, font, SUB_COLOR, max_w)
        y += _s(4)

    return y + _s(10)


async def _draw_roles(img: Image.Image, y: int, roles: list[dict]) -> int:
    if not roles:
        return y
    draw = ImageDraw.Draw(img)
    y = _draw_section_title(draw, y, "适用角色")

    name_font = _font(18)
    desc_font = _font(15)
    max_w = CARD_W - PAD * 2 - ROLE_ICON_SIZE - _s(32)

    for role in roles:
        key = role.get("key", "")
        value = role.get("value", "")
        star_value = role.get("starValue", 0)
        icon_url = role.get("icon", "")

        icon = await _get_icon(icon_url, ROLE_ICON_SIZE) if icon_url else None
        if icon:
            img.paste(icon, (PAD + _s(8), y), icon)

        text_x = PAD + ROLE_ICON_SIZE + _s(20)
        draw.text((text_x, y + _s(4)), key, TEXT_COLOR, name_font)
        if star_value:
            _draw_star_text(draw, text_x, y + _s(28), star_value, _font(14))

        if value:
            desc_y = y + _s(48) if star_value else y + _s(28)
            _draw_wrapped_text(img, (text_x, desc_y), value, desc_font, SUB_COLOR, max_w)

        y += ROLE_ICON_SIZE + _s(16)

    return y + _s(10)


def _estimate_height(weapon_data: dict) -> int:
    h = PAD + _s(140)

    gain_methods = weapon_data.get("gainMethods", [])
    if gain_methods:
        h += _s(50) + len(gain_methods) * _s(30)

    forging = weapon_data.get("forging", {})
    forging_count = len(forging.get("material", [])) + len(forging.get("otherMaterial", []))
    if forging_count:
        h += _s(100) + forging_count * (MATERIAL_ICON_SIZE + _s(40))

    materials = weapon_data.get("materials", [])
    if materials:
        h += _s(80) + len(materials) * (MATERIAL_ICON_SIZE + _s(60))

    sync_mats = weapon_data.get("syncMaterials", [])
    if sync_mats:
        h += _s(50) + len(sync_mats) * _s(30)

    roles = weapon_data.get("roles", [])
    if roles:
        h += _s(50) + len(roles) * (ROLE_ICON_SIZE + _s(20))

    h += _s(80)
    return h


async def draw_weapon_wiki(detail: dict) -> Image.Image:
    from .wiki_api import parse_weapon_data_from_detail

    weapon_data = detail.get("weapon_data") or parse_weapon_data_from_detail(detail)
    title = detail.get("title", "未知武器")
    info = weapon_data.get("info", {})

    total_h = int(_estimate_height(weapon_data) * 1.5)

    weapon_icon_url = info.get("icon", "") or detail.get("icon", "")
    weapon_icon = await _download_image(weapon_icon_url) if weapon_icon_url else None
    if weapon_icon:
        img = _create_blurred_bg(weapon_icon, CARD_W, total_h)
    else:
        img = Image.new("RGBA", (CARD_W, total_h), BG_COLOR)

    y = _draw_header(img, weapon_icon, title, info)

    gain_methods = weapon_data.get("gainMethods", [])
    if gain_methods:
        y = _draw_gain_methods(img, y, gain_methods)

    forging = weapon_data.get("forging", {})
    if forging.get("material") or forging.get("otherMaterial"):
        y = await _draw_forging(img, y, forging)

    materials = weapon_data.get("materials", [])
    if materials:
        y = await _draw_materials(img, y, materials)

    sync_mats = weapon_data.get("syncMaterials", [])
    if sync_mats:
        y = await _draw_sync_materials(img, y, sync_mats)

    roles = weapon_data.get("roles", [])
    if roles:
        y = await _draw_roles(img, y, roles)

    y = _draw_footer(img, y)

    img = img.crop((0, 0, CARD_W, y))

    return await convert_img(img)
