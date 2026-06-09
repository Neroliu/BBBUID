"""查询卡 HTML 渲染版本（playwright + jinja2）。

入口：`draw_query_card_html(ev, uid, index_data, characters) -> bytes`，
返回 PNG 字节流。当 `UseHtmlRender` 开启时由 `bbb_data/__init__.py` 调用。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..bbb_data.draw_title import EVAL_RATING_TO_ICON
from ..bbb_data.avatar_utils import get_cached_avatar, draw_decorated_avatar
from ..utils.RESOURCE_PATH import WIKI_PATH
from .runner import render_html_to_bytes
from .templates import file_uri, render_template

CHAR_CARD_W = 182
CHAR_CARD_H = 276
CHAR_GAP = 10
CHARS_PER_ROW = 5

TITLE_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "title"
INFO_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "info"
CHAR_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "char"
EVAL_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "eval_icon"
FOOTER_PATH = Path(__file__).parent.parent / "bbb_data" / "footer.png"
CHAR_ICON_CACHE_DIR = WIKI_PATH / "角色" / "icons"


async def draw_query_card_html(
    ev: Event,
    uid: str,
    index_data: Dict,
    characters: List[Dict],
) -> bytes:
    role = index_data.get("role", {}) or {}
    stats = index_data.get("stats", {}) or {}
    pref = index_data.get("preference", {}) or {}

    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    rating = pref.get("comprehensive_rating", "C")

    char_count = len(characters)
    sss_count = stats.get("sss_armor_number", 0)
    five_star_stigma = stats.get("five_star_stigmata_number", 0)
    five_star_weapon = stats.get("five_star_weapon_number", 0)
    active_days_raw = stats.get("active_day_number", "?")
    active_days = f"{active_days_raw}天"

    # Avatar
    avatar_uri: str | None = None
    try:
        avatar = await get_cached_avatar(ev, ev.user_id)
        decorated = draw_decorated_avatar(avatar, 179)
        from io import BytesIO
        import base64
        buf = BytesIO()
        decorated.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        avatar_uri = f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning(f"[崩坏3] [HTML渲染] 头像加载失败: {e}")

    # Title card width is fixed 1000px
    title_w = 1000

    # Grid layout
    num_chars = len(characters)
    if num_chars > 0:
        num_rows = (num_chars + CHARS_PER_ROW - 1) // CHARS_PER_ROW
        grid_w = CHARS_PER_ROW * CHAR_CARD_W + (CHARS_PER_ROW - 1) * CHAR_GAP
        grid_h = num_rows * CHAR_CARD_H + (num_rows - 1) * CHAR_GAP
    else:
        num_rows = 0
        grid_w = 0
        grid_h = 0

    # Canvas width
    canvas_w = max(title_w, grid_w + 40)

    # Footer
    footer_h = 0
    footer_uri: str | None = None
    footer_pad = 20
    if FOOTER_PATH.exists():
        from PIL import Image
        footer_img = Image.open(FOOTER_PATH)
        footer_h = footer_img.height
        footer_uri = file_uri(FOOTER_PATH)
    title_gap = 20

    # Total height
    content_h = 450 + title_gap + grid_h + footer_h + footer_pad
    canvas_h = content_h

    # Build info items
    info_items = [
        {"value": active_days, "label": "累计登舰"},
        {"value": str(char_count), "label": "装甲数"},
        {"value": str(sss_count), "label": "SSS女武神"},
        {"value": str(five_star_stigma), "label": "五星圣痕"},
        {"value": str(five_star_weapon), "label": "五星武器"},
    ]

    # Build character data
    char_data_list: List[Dict] = []
    for i, char_item in enumerate(characters):
        char = char_item.get("character", {})
        avatar_data = char.get("avatar", {})
        name = avatar_data.get("name", "?")
        star = avatar_data.get("star", 0)
        level = avatar_data.get("level", 1)

        # Character icon from wiki cache
        icon_uri: str | None = None
        cache_path = None
        from ..bbb_alias.name_convert import alias_to_char_name, char_name_to_content_id
        standard_name = alias_to_char_name(name) or name
        content_id = char_name_to_content_id(standard_name)
        if content_id:
            cache_path = CHAR_ICON_CACHE_DIR / f"{content_id}.png"
            if cache_path.exists():
                icon_uri = file_uri(cache_path)

        # Star icon
        star_icon_uri: str | None = None
        from ..bbb_data.draw_character import STAR_TO_ICON
        star_name = STAR_TO_ICON.get(star, "StarElf_B.png")
        star_path = CHAR_RES_DIR / "star_icon" / star_name
        if star_path.exists():
            star_icon_uri = file_uri(star_path)

        # Compute icon display height from actual image dimensions (same as PIL)
        icon_width = CHAR_CARD_W - 23  # 159
        icon_height = 222  # default estimate
        if cache_path and cache_path.exists():
            try:
                from PIL import Image as PILImage
                img = PILImage.open(cache_path)
                icon_height = img.height * icon_width // img.width + 4
            except Exception:
                pass

        # Positions matching PIL draw_character.py
        star_y = 17 + icon_height + 2
        level_y = 17 + icon_height + 20

        char_data_list.append({
            "name": name,
            "level": level,
            "star": star,
            "icon_uri": icon_uri,
            "star_icon_uri": star_icon_uri,
            "star_y": star_y,
            "level_y": level_y,
        })

    # URIs
    title_bg_uri = file_uri(TITLE_RES_DIR / "title_bg.png") if (TITLE_RES_DIR / "title_bg.png").exists() else None
    info_bg_uri = file_uri(INFO_RES_DIR / "info_bg.png") if (INFO_RES_DIR / "info_bg.png").exists() else None
    avatar_bg_uri = file_uri(CHAR_RES_DIR / "avatar_bg.png") if (CHAR_RES_DIR / "avatar_bg.png").exists() else None
    level_bg_uri = file_uri(TITLE_RES_DIR / "level_bg.png") if (TITLE_RES_DIR / "level_bg.png").exists() else None

    icon_name = EVAL_RATING_TO_ICON.get(str(rating).upper(), "SealedDanIcon01.png")
    eval_icon_path = EVAL_RES_DIR / icon_name
    eval_icon_uri = file_uri(eval_icon_path) if eval_icon_path.exists() else None

    ctx = {
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "title_bg_uri": title_bg_uri,
        "info_bg_uri": info_bg_uri,
        "avatar_bg_uri": avatar_bg_uri,
        "level_bg_uri": level_bg_uri,
        "eval_icon_uri": eval_icon_uri,
        "footer_uri": footer_uri,
        "avatar_uri": avatar_uri,
        "nickname": nickname,
        "uid": uid,
        "level": level,
        "info_items": info_items,
        "characters": char_data_list,
        "grid_w": max(grid_w, canvas_w - 40),
    }

    html = render_template("query.html", **ctx)
    png_bytes = await render_html_to_bytes(
        html,
        width=canvas_w,
        height=canvas_h,
        device_scale_factor=2,
    )
    return await convert_img(png_bytes)
