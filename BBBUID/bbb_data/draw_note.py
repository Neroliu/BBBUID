from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Union

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

# --- Scale & Dimensions ---
S = 2
W = 1786 * 1  # canvas width (match NTEUID)
H = 1000

LEFT_W = 800  # portrait area width
RIGHT_X = LEFT_W  # right panel start x
RIGHT_W = W - LEFT_W

# --- Colors ---
BG_DARK = (28, 28, 38)
BG_MID = (36, 36, 50)
BG_PANEL = (42, 42, 58)
TEXT_WHITE = (240, 240, 245)
TEXT_GRAY = (180, 180, 195)
TEXT_DIM = (130, 130, 148)
ACCENT_RED = (235, 80, 100)
ACCENT_BLUE = (80, 160, 255)
ACCENT_GREEN = (80, 200, 140)
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


def _s(v: int) -> int:
    return v * S


def _font(size: int) -> ImageFont.FreeTypeFont:
    size = _s(size)
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
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                from io import BytesIO
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 下载图片失败: {e}")
    return None


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    fill: tuple,
    radius: int = 16,
):
    draw.rounded_rectangle(xy, fill=fill, radius=radius)


def _draw_circle_avatar(avatar: Image.Image, size: int) -> Image.Image:
    avatar = avatar.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar, (0, 0), mask)
    return out


def _draw_ring_avatar(avatar: Image.Image, size: int) -> Image.Image:
    ring_w = _s(4)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    center = size // 2
    r = center - ring_w
    inner_avatar = _draw_circle_avatar(avatar, r * 2)
    canvas.paste(inner_avatar, (ring_w, ring_w), inner_avatar)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), outline=ACCENT_BLUE, width=ring_w)
    return canvas


async def _get_random_portrait() -> Image.Image | None:
    char_path = WIKI_PATH / "角色"
    if not char_path.exists():
        return None
    index_file = char_path / "index.json"
    if not index_file.exists():
        return None
    try:
        import json
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

    # --- Left: Portrait ---
    portrait = None
    head_bg_url = index_data.get("head_background", "")
    if head_bg_url:
        portrait = await _download_image(head_bg_url)

    if portrait is None:
        portrait = await _get_random_portrait()

    if portrait:
        fitted = _fit_centered(portrait, (LEFT_W + _s(40), H))
        canvas.alpha_composite(fitted, (-_s(40), 0))
        # Gradient overlay: left transparent, right opaque
        overlay = Image.new("RGBA", (LEFT_W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for x in range(LEFT_W):
            progress = x / LEFT_W
            alpha = int(40 + 215 * (progress ** 1.5))
            overlay_draw.line([(x, 0), (x, H)], fill=(*BG_DARK, alpha))
        canvas.alpha_composite(overlay, (0, 0))
    else:
        # Solid dark background as fallback
        _draw_rounded_rect(draw, (0, 0, LEFT_W, H), BG_DARK, 0)

    # Separator line
    sep_x = RIGHT_X + _s(20)
    draw.line([(sep_x, _s(60)), (sep_x, H - _s(60))], fill=(60, 60, 80), width=_s(2))

    # --- Right: User Info ---
    role = index_data.get("role", {})
    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    region = role.get("region", "")
    region_name = REGION_MAP.get(region, region)

    # Avatar
    user_avatar = await get_event_avatar(ev)
    avatar_size = _s(72)
    avatar_img = _draw_ring_avatar(user_avatar, avatar_size)
    ax = RIGHT_X + _s(36)
    ay = _s(40)
    canvas.alpha_composite(avatar_img, (ax, ay))

    # Nickname
    name_x = ax + avatar_size + _s(16)
    name_y = ay + _s(4)
    draw.text((name_x, name_y), nickname, font=_font(32), fill=TEXT_WHITE)

    # Server & UID
    server_text = f"{region_name}  UID: {uid}"
    draw.text((name_x, name_y + _s(40)), server_text, font=_font(18), fill=TEXT_GRAY)

    # Level badge
    level_text = f"Lv.{level}"
    level_font = _font(22)
    level_w = int(draw.textlength(level_text, font=level_font)) + _s(24)
    level_h = _s(32)
    level_x = W - _s(36) - level_w
    level_y = ay + _s(20)
    _draw_rounded_rect(draw, (level_x, level_y, level_x + level_w, level_y + level_h), ACCENT_BLUE, _s(8))
    draw.text((level_x + _s(12), level_y + _s(4)), level_text, font=level_font, fill=TEXT_WHITE)

    # Sign-in status
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

    sign_text = "今日已签到" if is_signed else "今日未签到"
    sign_bg = SIGN_YES_BG if is_signed else SIGN_NO_BG
    sign_font = _font(16)
    sign_w = int(draw.textlength(sign_text, font=sign_font)) + _s(20)
    sign_h = _s(26)
    sign_x = name_x
    sign_y = name_y + _s(80)
    _draw_rounded_rect(draw, (sign_x, sign_y, sign_x + sign_w, sign_y + sign_h), sign_bg, _s(6))
    draw.text((sign_x + _s(10), sign_y + _s(3)), sign_text, font=sign_font, fill=TEXT_WHITE)

    # --- Real-time Info Section ---
    section_y = _s(170)
    draw.text((RIGHT_X + _s(36), section_y), "实时信息", font=_font(28), fill=TEXT_WHITE)
    draw.text((RIGHT_X + _s(36) + _s(160), section_y + _s(6)), "REAL-TIME INFO", font=_font(12), fill=TEXT_DIM)

    # Stamina & Train Score
    cur_stamina = note_data.get("current_stamina", "?")
    max_stamina = note_data.get("max_stamina", "?")
    recover = note_data.get("stamina_recover_time", 0)
    cur_train = note_data.get("current_train_score", "?")
    max_train = note_data.get("max_train_score", "?")

    card_y = section_y + _s(50)
    card_h = _s(120)
    card_w = (RIGHT_W - _s(100)) // 2

    # Stamina card
    st_card_x = RIGHT_X + _s(36)
    _draw_rounded_rect(draw, (st_card_x, card_y, st_card_x + card_w, card_y + card_h), BG_PANEL, _s(12))
    draw.text((st_card_x + _s(20), card_y + _s(14)), "体力", font=_font(18), fill=TEXT_GRAY)
    stamina_val = f"{cur_stamina}/{max_stamina}"
    draw.text((st_card_x + _s(20), card_y + _s(46)), stamina_val, font=_font(40), fill=ACCENT_RED)
    if recover > 0:
        recover_text = f"回满: {_fmt_recover(recover)}"
        draw.text((st_card_x + _s(20), card_y + _s(94)), recover_text, font=_font(14), fill=TEXT_DIM)

    # Train score card
    tr_card_x = st_card_x + card_w + _s(16)
    _draw_rounded_rect(draw, (tr_card_x, card_y, tr_card_x + card_w, card_y + card_h), BG_PANEL, _s(12))
    draw.text((tr_card_x + _s(20), card_y + _s(14)), "每日历练", font=_font(18), fill=TEXT_GRAY)
    train_val = f"{cur_train}/{max_train}"
    draw.text((tr_card_x + _s(20), card_y + _s(46)), train_val, font=_font(40), fill=ACCENT_ORANGE)

    # --- Activity Sections (Abyss, Battlefield, Elysian Realm) ---
    act_y = card_y + card_h + _s(20)
    act_x = RIGHT_X + _s(36)
    act_w = RIGHT_W - _s(72)
    act_h = _s(160)
    act_gap = _s(12)

    # Ultra Endless (Abyss / Superstring Space)
    ultra = note_data.get("ultra_endless", {})
    greedy = note_data.get("greedy_endless", {})
    # Use ultra_endless for primary, greedy_endless as fallback
    endless_data = ultra if ultra else greedy
    if endless_data:
        _draw_rounded_rect(draw, (act_x, act_y, act_x + act_w, act_y + act_h), SECTION_BG, _s(12))

        # Title
        draw.text((act_x + _s(20), act_y + _s(16)), "超弦空间", font=_font(24), fill=TEXT_WHITE)

        # Status & remaining time
        is_open = endless_data.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + _s(20), act_y + _s(50)), status_text, font=_font(18), fill=status_color)

        schedule_end = endless_data.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + _s(20), act_y + _s(76)), remain_text, font=_font(14), fill=TEXT_DIM)

        # Score & level icon (right side)
        right_info_x = act_x + act_w - _s(20)
        challenge_score = endless_data.get("challenge_score", "?")
        if challenge_score != "?":
            score_text = f"积分: {challenge_score}"
            draw.text((right_info_x - _s(180), act_y + _s(20)), score_text, font=_font(22), fill=ACCENT_ORANGE, anchor="ra")

        # Level icon
        level_icon_url = endless_data.get("level_icon", "")
        if level_icon_url:
            icon_img = await _download_image(level_icon_url)
            if icon_img:
                icon_size = _s(48)
                icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                canvas.alpha_composite(icon_img, (right_info_x - icon_size, act_y + _s(56)))

        # Cup number from greedy (if available)
        if greedy:
            cur_reward = greedy.get("cur_reward", "?")
            max_reward = greedy.get("max_reward", "?")
            reward_text = f"奖励: {cur_reward}/{max_reward}"
            draw.text((right_info_x - _s(180), act_y + _s(110)), reward_text, font=_font(14), fill=TEXT_DIM, anchor="ra")

    act_y += act_h + act_gap

    # Battle Field
    bf = note_data.get("battle_field", {})
    if bf:
        _draw_rounded_rect(draw, (act_x, act_y, act_x + act_w, act_y + act_h), SECTION_BG, _s(12))

        draw.text((act_x + _s(20), act_y + _s(16)), "记忆战场", font=_font(24), fill=TEXT_WHITE)

        is_open = bf.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + _s(20), act_y + _s(50)), status_text, font=_font(18), fill=status_color)

        schedule_end = bf.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + _s(20), act_y + _s(76)), remain_text, font=_font(14), fill=TEXT_DIM)

        # Reward info (right side)
        right_info_x = act_x + act_w - _s(20)
        cur_reward = bf.get("cur_reward", "?")
        max_reward = bf.get("max_reward", "?")
        cur_sss = bf.get("cur_sss_reward", "?")
        max_sss = bf.get("max_sss_reward", "?")

        reward_text = f"挑战: {cur_reward}/{max_reward}"
        draw.text((right_info_x - _s(20), act_y + _s(20)), reward_text, font=_font(18), fill=ACCENT_ORANGE, anchor="ra")

        sss_text = f"SSS: {cur_sss}/{max_sss}"
        draw.text((right_info_x - _s(20), act_y + _s(52)), sss_text, font=_font(18), fill=ACCENT_RED, anchor="ra")

    act_y += act_h + act_gap

    # God War (Elysian Realm)
    gw = note_data.get("god_war", {})
    if gw:
        _draw_rounded_rect(draw, (act_x, act_y, act_x + act_w, act_y + act_h), SECTION_BG, _s(12))

        draw.text((act_x + _s(20), act_y + _s(16)), "往世乐土", font=_font(24), fill=TEXT_WHITE)

        is_open = gw.get("is_open", False)
        status_text = "开放中" if is_open else "未开放"
        status_color = ACCENT_GREEN if is_open else TEXT_DIM
        draw.text((act_x + _s(20), act_y + _s(50)), status_text, font=_font(18), fill=status_color)

        schedule_end = gw.get("schedule_end", "0")
        remain_text = f"剩余: {_fmt_schedule_end(schedule_end)}" if is_open else ""
        if remain_text:
            draw.text((act_x + _s(20), act_y + _s(76)), remain_text, font=_font(14), fill=TEXT_DIM)

        # Score info
        right_info_x = act_x + act_w - _s(20)
        cur_reward = gw.get("cur_reward", "?")
        max_reward = gw.get("max_reward", "?")
        score_text = f"积分: {cur_reward}/{max_reward}"
        draw.text((right_info_x - _s(20), act_y + _s(36)), score_text, font=_font(22), fill=ACCENT_ORANGE, anchor="ra")

    # --- Footer ---
    footer_y = H - _s(40)
    draw.line([(RIGHT_X + _s(36), footer_y), (W - _s(36), footer_y)], fill=(60, 60, 80), width=_s(1))
    footer_font = _font(12)
    draw.text((W // 2, footer_y + _s(14)), "BBBUID · 崩坏3", (80, 80, 100), footer_font, anchor="mt")

    return await convert_img(canvas)
