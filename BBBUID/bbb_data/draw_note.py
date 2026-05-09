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

CST = timezone(timedelta(hours=8))

# --- Dimensions ---
W = 1786
H = 1000

LEFT_W = 800
RIGHT_X = LEFT_W
RIGHT_W = W - LEFT_W

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
    iw, ih = img.size
    tw, th = output_size
    if iw > ih:
        scale = tw / iw
        new_size = (tw, round(ih * scale))
    else:
        scale = th / ih
        new_size = (round(iw * scale), th)
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", output_size, (0, 0, 0, 0))
    out.paste(resized, ((tw - new_size[0]) // 2, (th - new_size[1]) // 2), resized)
    return out


async def _download_image(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        import httpx
        from io import BytesIO
        async with httpx.AsyncClient() as client:
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


async def _get_random_char_portrait(uid: str) -> Image.Image | None:
    """Get a random character portrait from the user's characters (background_path)."""
    try:
        chars_data = await bh3_api.get_bbb_characters(uid)
        if isinstance(chars_data, int):
            return None
        characters = chars_data.get("characters", [])
        if not characters:
            return None
        random.shuffle(characters)
        for char_item in characters[:5]:
            avatar = char_item.get("character", {}).get("avatar", {})
            bg_path = avatar.get("background_path", "")
            if bg_path:
                img = await _download_image(bg_path)
                if img:
                    return img
            img_path = avatar.get("image_path", "")
            if img_path:
                img = await _download_image(img_path)
                if img:
                    return img
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 获取角色立绘失败: {e}")
    return None


async def _get_random_wiki_portrait() -> Image.Image | None:
    """Fallback: get a random portrait from wiki cached data."""
    char_path = WIKI_PATH / "角色"
    if not char_path.exists():
        return None
    index_file = char_path / "index.json"
    if not index_file.exists():
        return None
    try:
        index = json.loads(index_file.read_text(encoding="utf-8"))
        if not index:
            return None
        content_ids = list(index.keys())
        random.shuffle(content_ids)
        for cid in content_ids[:5]:
            detail_file = char_path / f"{cid}.json"
            if not detail_file.exists():
                continue
            detail = json.loads(detail_file.read_text(encoding="utf-8"))
            evaluation = detail.get("evaluation", {})
            avatar_url = evaluation.get("avatar", "")
            if avatar_url:
                img = await _download_image(avatar_url)
                if img and img.width > 100:
                    return img
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 获取随机立绘失败: {e}")
    return None


async def draw_note_img(
    ev: Event,
    uid: str,
    index_data: Dict,
    note_data: Dict,
) -> bytes:
    canvas = Image.new("RGBA", (W, H), BG_DARK)
    draw = ImageDraw.Draw(canvas)

    # --- Bottom: blurred bridge background ---
    head_bg_url = index_data.get("head_background", "")
    head_bg = await _download_image(head_bg_url) if head_bg_url else None
    if head_bg:
        blurred = _fit_centered(head_bg, (W, H))
        blurred = blurred.filter(ImageFilter.GaussianBlur(radius=20))
        dark_overlay = Image.new("RGBA", (W, H), (*BG_DARK, 200))
        blurred = Image.alpha_composite(blurred, dark_overlay)
        canvas.alpha_composite(blurred, (0, 0))

    # --- Left: Random character portrait ---
    portrait = await _get_random_char_portrait(uid)
    if portrait is None:
        portrait = await _get_random_wiki_portrait()

    if portrait:
        fitted = _fit_centered(portrait, (LEFT_W + 40, H))
        canvas.alpha_composite(fitted, (-40, 0))
        # Gradient overlay: left transparent, right opaque
        overlay = Image.new("RGBA", (LEFT_W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for x in range(LEFT_W):
            progress = x / LEFT_W
            alpha = int(40 + 215 * (progress ** 1.5))
            overlay_draw.line([(x, 0), (x, H)], fill=(*BG_DARK, alpha))
        canvas.alpha_composite(overlay, (0, 0))

    # --- Right: User Info ---
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
    ax = RIGHT_X + 36
    ay = 40
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
    level_x = W - 36 - level_w
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
    days_font = _font(16)
    draw.text((W - 36, sign_y + 3), days_text, font=days_font, fill=TEXT_GRAY, anchor="ra")

    # --- Real-time Info Section ---
    section_y = 170
    draw.text((RIGHT_X + 36, section_y), "实时信息", font=_font(24), fill=TEXT_WHITE)
    draw.text((RIGHT_X + 36 + 140, section_y + 5), "REAL-TIME INFO", font=_font(10), fill=TEXT_DIM)

    # Stamina & Train Score
    cur_stamina = note_data.get("current_stamina", "?")
    max_stamina = note_data.get("max_stamina", "?")
    recover = note_data.get("stamina_recover_time", 0)
    cur_train = note_data.get("current_train_score", "?")
    max_train = note_data.get("max_train_score", "?")

    card_y = section_y + 42
    card_h = 90
    card_w = (RIGHT_W - 88) // 2

    # Stamina card
    st_card_x = RIGHT_X + 36
    draw.rounded_rectangle(
        (st_card_x, card_y, st_card_x + card_w, card_y + card_h),
        fill=BG_PANEL, radius=12,
    )
    draw.text((st_card_x + 16, card_y + 10), "体力", font=_font(14), fill=TEXT_GRAY)
    stamina_val = f"{cur_stamina}/{max_stamina}"
    draw.text((st_card_x + 16, card_y + 34), stamina_val, font=_font(34), fill=ACCENT_RED)
    if recover > 0:
        recover_text = f"回满: {_fmt_recover(recover)}"
        draw.text((st_card_x + 16, card_y + 70), recover_text, font=_font(12), fill=TEXT_DIM)

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
        draw.text((tr_card_x + 16, card_y + 34), "已达成", font=_font(34), fill=ACCENT_LIGHT_GREEN)
    else:
        train_val = f"{cur_train}/{max_train}"
        draw.text((tr_card_x + 16, card_y + 34), train_val, font=_font(34), fill=ACCENT_ORANGE)

    # --- Activity Sections ---
    act_y = card_y + card_h + 14
    act_x = RIGHT_X + 36
    act_w = RIGHT_W - 72
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

        # Score (right-aligned)
        right_x = act_x + act_w - 16
        challenge_score = endless_data.get("challenge_score", "?")
        if challenge_score != "?":
            score_text = f"积分: {challenge_score}"
            draw.text((right_x, act_y + 14), score_text, font=_font(18), fill=ACCENT_ORANGE, anchor="ra")

        # Level icon
        level_icon_url = endless_data.get("level_icon", "")
        if level_icon_url:
            icon_img = await _download_image(level_icon_url)
            if icon_img:
                icon_size = 40
                icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                canvas.alpha_composite(icon_img, (right_x - icon_size, act_y + 40))

        # Reward from greedy
        if greedy:
            cur_reward = greedy.get("cur_reward", "?")
            max_reward = greedy.get("max_reward", "?")
            reward_text = f"奖励: {cur_reward}/{max_reward}"
            draw.text((right_x, act_y + 84), reward_text, font=_font(12), fill=TEXT_DIM, anchor="ra")

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
    draw.line([(RIGHT_X + 36, footer_y), (W - 36, footer_y)], fill=(60, 60, 80), width=1)
    draw.text((W // 2, footer_y + 12), "BBBUID · 崩坏3", (80, 80, 100), _font(10), anchor="mt")

    return await convert_img(canvas)
