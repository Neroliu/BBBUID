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

from ..bbb_api import bh3_api
from ..bbb_sign.until import is_sign
from ..utils.RESOURCE_PATH import WIKI_PATH

from .avatar_utils import get_cached_avatar, draw_decorated_avatar

PORTRAIT_ICONS_DIR = "portrait_icons"
WALLPAPER_ICONS_DIR = "wallpaper_icons"

CST = timezone(timedelta(hours=8))

# --- Dimensions ---
W = 1786
H = 1200
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
    from .draw_title import draw_title, draw_info_section

    canvas = Image.new("RGBA", (W, H), BG_DARK)
    draw = ImageDraw.Draw(canvas)

    # --- Full background: blurred wallpaper ---
    wallpaper = await _get_random_wallpaper()
    if wallpaper:
        blurred = _fit_centered(wallpaper, (W, H))
        blurred = blurred.filter(ImageFilter.GaussianBlur(radius=10))
        dark_overlay = Image.new("RGBA", (W, H), (*BG_DARK, 200))
        blurred = Image.alpha_composite(blurred, dark_overlay)
        canvas.alpha_composite(blurred, (0, 0))

    # --- Title Section ---
    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    pref = index_data.get("preference", {})
    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    region = role.get("region", "")
    region_name = REGION_MAP.get(region, region)
    rating = pref.get("comprehensive_rating", "C")

    # Get character count
    char_data = await bh3_api.get_bbb_characters(uid)
    char_count = len(char_data.get("characters", [])) if not isinstance(char_data, int) else stats.get("armor_number", "?")

    # Draw title
    title_img = await draw_title(ev, uid, nickname, level, rating, region_name)
    # Center title
    title_x = (W - title_img.width) // 2
    title_y = PAD
    canvas.alpha_composite(title_img, (title_x, title_y))

    # --- Info Section ---
    info_img = await draw_info_section(index_data, char_count if isinstance(char_count, int) else 0)
    info_x = (W - info_img.width) // 2
    info_y = title_y + title_img.height + 20
    canvas.alpha_composite(info_img, (info_x, info_y))

    # --- Real-time Info Section ---
    section_y = info_y + info_img.height + 20
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

        # Right side: score + level
        right_x = act_x + act_w - 16
        challenge_score = endless_data.get("challenge_score")
        if challenge_score is not None:
            score_text = f"积分: {challenge_score}"
            draw.text((right_x, act_y + 14), score_text, font=_font(18), fill=ACCENT_ORANGE, anchor="ra")

        # Level: draw group_level as text badge (level_icon URL is dead on CDN)
        group_level = ultra.get("group_level") if ultra else None
        if group_level is not None:
            level_str = f"Lv.{group_level}"
            level_font = _font(16)
            lw = int(draw.textlength(level_str, font=level_font)) + 16
            lh = 24
            lx = right_x - lw
            ly = act_y + 42
            draw.rounded_rectangle(
                (lx, ly, lx + lw, ly + lh),
                fill=ACCENT_BLUE, radius=6,
            )
            draw.text((lx + 8, ly + 3), level_str, font=level_font, fill=TEXT_WHITE)

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
    footer_path = Path(__file__).parent / "footer.png"
    if footer_path.exists():
        footer_img = Image.open(footer_path).convert("RGBA")
        fw, fh = footer_img.size
        fx = (W - fw) // 2
        fy = H - fh - 6
        canvas.alpha_composite(footer_img, (fx, fy))

    return await convert_img(canvas)
