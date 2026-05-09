from __future__ import annotations

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import get_event_avatar

from ..bbb_api import bh3_api
from ..bbb_sign.until import is_sign
from ..utils.RESOURCE_PATH import WIKI_PATH

PORTRAIT_ICONS_DIR = "portrait_icons"
WALLPAPER_ICONS_DIR = "wallpaper_icons"

CST = timezone(timedelta(hours=8))

# --- Dimensions ---
W = 1786
H = 1000
PAD = 40

# --- Colors ---
BG_DARK = (28, 28, 38)
BG_PANEL = (42, 42, 58)
TEXT_WHITE = (240, 240, 245)
TEXT_GRAY = (180, 180, 195)
TEXT_DIM = (130, 130, 148)
ACCENT_RED = (235, 80, 100)
ACCENT_BLUE = (80, 160, 255)
ACCENT_GREEN = (80, 200, 140)
ACCENT_LIGHT_GREEN = (140, 230, 180)
ACCENT_ORANGE = (255, 180, 60)
SIGN_YES_BG = (40, 140, 80)
SIGN_NO_BG = (160, 60, 60)
SECTION_BG = (48, 48, 66)

REGION_MAP = {
    "android01": "安卓1区",
    "ios01": "iOS1区",
    "pc01": "PC1区",
}

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


def _fmt_recover(seconds: int) -> str:
    if seconds <= 0:
        return "已回满"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}时")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}分")
    return "".join(parts) if parts else "即将回满"


def _fmt_schedule_end(ts: str) -> str:
    try:
        end_ts = int(ts)
        now = datetime.now(tz=CST).timestamp()
        remain = int(end_ts - now)
        if remain <= 0:
            return "已结束"
        return _fmt_recover(remain)
    except Exception:
        return "未知"


def _fit_centered(img: Image.Image, output_size: tuple[int, int]) -> Image.Image:
    """等比缩放填满 output_size，长边对齐，短边居中裁剪（cover crop）。"""
    iw, ih = img.size
    tw, th = output_size
    scale = max(tw / iw, th / ih)
    new_w = round(iw * scale)
    new_h = round(ih * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return resized.crop((left, top, left + tw, top + th))


async def _download_image(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        import httpx
        from io import BytesIO
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 下载图片失败: {e}")
    return None


def _draw_circle_avatar(avatar: Image.Image, size: int) -> Image.Image:
    avatar = avatar.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar, (0, 0), mask)
    return out


def _draw_ring_avatar(avatar: Image.Image, size: int) -> Image.Image:
    ring_w = 4
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    center = size // 2
    r = center - ring_w
    inner_avatar = _draw_circle_avatar(avatar, r * 2)
    canvas.paste(inner_avatar, (ring_w, ring_w), inner_avatar)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), outline=ACCENT_BLUE, width=ring_w)
    return canvas


def _get_stamina_icon() -> Image.Image | None:
    """Get stamina potion icon from cached 材料 data."""
    mat_path = WIKI_PATH / "材料"
    icon_path = mat_path / "1087.png"  # 体力药水 content_id=1087
    if icon_path.exists():
        try:
            return Image.open(icon_path).convert("RGBA")
        except Exception:
            pass
    return None


async def _get_random_wallpaper() -> Image.Image | None:
    """Get a random wallpaper from wiki cached 壁纸 data."""
    wp_path = WIKI_PATH / "壁纸"
    if not wp_path.exists():
        return None
    index_file = wp_path / "index.json"
    if not index_file.exists():
        return None
    try:
        index = json.loads(index_file.read_text(encoding="utf-8"))
        if not index:
            return None
        content_ids = list(index.keys())
        random.shuffle(content_ids)
        for cid in content_ids[:5]:
            icons_dir = wp_path / WALLPAPER_ICONS_DIR / str(cid)
            if not icons_dir.exists():
                continue
            files = [f for f in icons_dir.iterdir() if f.is_file() and f.suffix == ".png"]
            if not files:
                continue
            f = random.choice(files)
            try:
                img = Image.open(f).convert("RGBA")
                if img.width >= 800:
                    return img
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 获取壁纸失败: {e}")
    return None


async def draw_note_img(
    ev: Event,
    uid: str,
    index_data: Dict,
    note_data: Dict,
) -> bytes:
    canvas = Image.new("RGBA", (W, H), BG_DARK)
    draw = ImageDraw.Draw(canvas)

    # Debug: log note_data structure for level_icon investigation
    logger.debug(f"[崩坏3] [便笺渲染] note_data keys: {list(note_data.keys())}")
    logger.debug(f"[崩坏3] [便笺渲染] ultra_endless: {note_data.get('ultra_endless', {})}")
    logger.debug(f"[崩坏3] [便笺渲染] greedy_endless: {note_data.get('greedy_endless', {})}")

    # --- Full background: blurred wallpaper ---
    wallpaper = await _get_random_wallpaper()
    if wallpaper:
        blurred = _fit_centered(wallpaper, (W, H))
        blurred = blurred.filter(ImageFilter.GaussianBlur(radius=10))
        dark_overlay = Image.new("RGBA", (W, H), (*BG_DARK, 200))
        blurred = Image.alpha_composite(blurred, dark_overlay)
        canvas.alpha_composite(blurred, (0, 0))

    # --- User Info (full width) ---
    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    region = role.get("region", "")
    region_name = REGION_MAP.get(region, region)
    active_days = stats.get("active_day_number", "?")

    # Avatar
    user_avatar = await get_event_avatar(ev)
    avatar_size = 72
    avatar_img = _draw_ring_avatar(user_avatar, avatar_size)
    ax = PAD
    ay = PAD
    canvas.alpha_composite(avatar_img, (ax, ay))

    # Nickname
    name_x = ax + avatar_size + 16
    name_y = ay + 4
    draw.text((name_x, name_y), nickname, font=_font(32), fill=TEXT_WHITE)

    # Server & UID
    server_text = f"{region_name}  UID: {uid}"
    draw.text((name_x, name_y + 40), server_text, font=_font(18), fill=TEXT_GRAY)

    # Level badge (right-aligned)
    level_text = f"Lv.{level}"
    level_font = _font(22)
    level_w = int(draw.textlength(level_text, font=level_font)) + 24
    level_h = 32
    level_x = W - PAD - level_w
    level_y = ay + 20
    draw.rounded_rectangle(
        (level_x, level_y, level_x + level_w, level_y + level_h),
        fill=ACCENT_BLUE, radius=8,
    )
    draw.text((level_x + 12, level_y + 4), level_text, font=level_font, fill=TEXT_WHITE)

    # Sign-in status (left-aligned) + active days (right-aligned) on same row
    is_signed = False
    try:
        ck = await bh3_api.bbb_get_ck(uid)
        server = await bh3_api.get_bbb_server(uid)
        if ck and server:
            sign_data = await is_sign(region=server, uid=uid, cookie=ck)
            if not isinstance(sign_data, int) and sign_data.get("data"):
                is_signed = sign_data["data"].get("is_sign", False)
    except Exception:
        pass

    sign_y = name_y + 80
    sign_text = "今日已签到" if is_signed else "今日未签到"
    sign_bg = SIGN_YES_BG if is_signed else SIGN_NO_BG
    sign_font = _font(16)
    sign_w = int(draw.textlength(sign_text, font=sign_font)) + 20
    sign_h = 26
    draw.rounded_rectangle(
        (name_x, sign_y, name_x + sign_w, sign_y + sign_h),
        fill=sign_bg, radius=6,
    )
    draw.text((name_x + 10, sign_y + 3), sign_text, font=sign_font, fill=TEXT_WHITE)

    # Active days (right side of same row)
    days_text = f"累计登舰: {active_days}天"
    draw.text((W - PAD, sign_y + 3), days_text, font=_font(16), fill=TEXT_GRAY, anchor="ra")

    # --- Real-time Info Section ---
    section_y = 170
    draw.text((PAD, section_y), "实时信息", font=_font(24), fill=TEXT_WHITE)
    draw.text((PAD + 140, section_y + 5), "REAL-TIME INFO", font=_font(10), fill=TEXT_DIM)

    # Stamina & Train Score
    cur_stamina = note_data.get("current_stamina", "?")
    max_stamina = note_data.get("max_stamina", "?")
    recover = note_data.get("stamina_recover_time", 0)
    cur_train = note_data.get("current_train_score", "?")
    max_train = note_data.get("max_train_score", "?")

    card_y = section_y + 42
    card_h = 90
    card_w = (W - PAD * 2 - 16) // 2

    # Stamina card
    st_card_x = PAD
    draw.rounded_rectangle(
        (st_card_x, card_y, st_card_x + card_w, card_y + card_h),
        fill=BG_PANEL, radius=12,
    )

    # Stamina icon
    stamina_icon = _get_stamina_icon()
    icon_size = 36
    if stamina_icon:
        stamina_icon = stamina_icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        canvas.alpha_composite(stamina_icon, (st_card_x + 16, card_y + 10))

    # "体力" label next to icon
    draw.text((st_card_x + 16 + icon_size + 8, card_y + 16), "体力", font=_font(14), fill=TEXT_GRAY)

    # Stamina value (right-aligned)
    stamina_val = f"{cur_stamina}/{max_stamina}"
    draw.text((st_card_x + card_w - 16, card_y + 16), stamina_val, font=_font(34), fill=ACCENT_RED, anchor="ra")

    if recover > 0:
        recover_text = f"回满: {_fmt_recover(recover)}"
        draw.text((st_card_x + 16, card_y + 60), recover_text, font=_font(12), fill=TEXT_DIM)

    # Train score card
    tr_card_x = st_card_x + card_w + 16
    draw.rounded_rectangle(
        (tr_card_x, card_y, tr_card_x + card_w, card_y + card_h),
        fill=BG_PANEL, radius=12,
    )
    draw.text((tr_card_x + 16, card_y + 10), "每日历练", font=_font(14), fill=TEXT_GRAY)

    # If train score is maxed, show green "已达成"
    try:
        ct = int(cur_train)
        mt = int(max_train)
        train_maxed = ct >= mt > 0
    except (ValueError, TypeError):
        train_maxed = False

    if train_maxed:
        draw.text((tr_card_x + card_w - 16, card_y + 16), "已达成", font=_font(34), fill=ACCENT_LIGHT_GREEN, anchor="ra")
    else:
        train_val = f"{cur_train}/{max_train}"
        draw.text((tr_card_x + card_w - 16, card_y + 16), train_val, font=_font(34), fill=ACCENT_ORANGE, anchor="ra")

    # --- Activity Sections ---
    act_y = card_y + card_h + 14
    act_x = PAD
    act_w = W - PAD * 2
    act_h = 110
    act_gap = 10

    # Ultra Endless (Abyss / Superstring Space)
    ultra = note_data.get("ultra_endless", {})
    greedy = note_data.get("greedy_endless", {})
    endless_data = ultra if ultra else greedy
    if endless_data:
        draw.rounded_rectangle(
            (act_x, act_y, act_x + act_w, act_y + act_h),
            fill=SECTION_BG, radius=12,
        )
        draw.text((act_x + 16, act_y + 12), "超弦空间", font=_font(20), fill=TEXT_WHITE)

        is_open = endless_data.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + 16, act_y + 38), status_text, font=_font(14), fill=status_color)

        schedule_end = endless_data.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + 16, act_y + 58), remain_text, font=_font(12), fill=TEXT_DIM)

        # Right side: score + level icon
        right_x = act_x + act_w - 16
        challenge_score = endless_data.get("challenge_score")
        if challenge_score is not None:
            score_text = f"积分: {challenge_score}"
            draw.text((right_x, act_y + 14), score_text, font=_font(18), fill=ACCENT_ORANGE, anchor="ra")

        # Level icon: try ultra_endless first, then greedy_endless
        level_icon_url = ultra.get("level_icon", "") if ultra else ""
        if not level_icon_url and greedy:
            level_icon_url = greedy.get("level_icon", "")
        logger.debug(f"[崩坏3] [便笺渲染] level_icon_url: {level_icon_url or '(empty)'}")
        if level_icon_url:
            icon_img = await _download_image(level_icon_url)
            if icon_img:
                icon_size = 40
                icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                canvas.alpha_composite(icon_img, (right_x - icon_size, act_y + 40))

    act_y += act_h + act_gap

    # Battle Field
    bf = note_data.get("battle_field", {})
    if bf:
        draw.rounded_rectangle(
            (act_x, act_y, act_x + act_w, act_y + act_h),
            fill=SECTION_BG, radius=12,
        )
        draw.text((act_x + 16, act_y + 12), "记忆战场", font=_font(20), fill=TEXT_WHITE)

        is_open = bf.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + 16, act_y + 38), status_text, font=_font(14), fill=status_color)

        schedule_end = bf.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + 16, act_y + 58), remain_text, font=_font(12), fill=TEXT_DIM)

        right_x = act_x + act_w - 16
        cur_reward = bf.get("cur_reward", "?")
        max_reward = bf.get("max_reward", "?")
        cur_sss = bf.get("cur_sss_reward", "?")
        max_sss = bf.get("max_sss_reward", "?")

        reward_text = f"挑战: {cur_reward}/{max_reward}"
        draw.text((right_x, act_y + 14), reward_text, font=_font(14), fill=ACCENT_ORANGE, anchor="ra")

        sss_text = f"SSS: {cur_sss}/{max_sss}"
        draw.text((right_x, act_y + 38), sss_text, font=_font(14), fill=ACCENT_RED, anchor="ra")

    act_y += act_h + act_gap

    # God War (Elysian Realm)
    gw = note_data.get("god_war", {})
    if gw:
        draw.rounded_rectangle(
            (act_x, act_y, act_x + act_w, act_y + act_h),
            fill=SECTION_BG, radius=12,
        )
        draw.text((act_x + 16, act_y + 12), "往世乐土", font=_font(20), fill=TEXT_WHITE)

        is_open = gw.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + 16, act_y + 38), status_text, font=_font(14), fill=status_color)

        schedule_end = gw.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + 16, act_y + 58), remain_text, font=_font(12), fill=TEXT_DIM)

        right_x = act_x + act_w - 16
        cur_reward = gw.get("cur_reward", "?")
        max_reward = gw.get("max_reward", "?")
        score_text = f"积分: {cur_reward}/{max_reward}"
        draw.text((right_x, act_y + 26), score_text, font=_font(18), fill=ACCENT_ORANGE, anchor="ra")

    # --- Footer ---
    footer_y = H - 30
    draw.line([(PAD, footer_y), (W - PAD, footer_y)], fill=(60, 60, 80), width=1)
    draw.text((W // 2, footer_y + 12), "BBBUID · 崩坏3", (80, 80, 100), _font(10), anchor="mt")

    return await convert_img(canvas)
