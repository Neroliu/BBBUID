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

from ..utils.RESOURCE_PATH import WIKI_PATH
from .avatar_utils import get_cached_avatar, draw_decorated_avatar
from .draw_title import EVAL_RATING_TO_ICON

PORTRAIT_ICONS_DIR = "portrait_icons"
WALLPAPER_ICONS_DIR = "wallpaper_icons"

CST = timezone(timedelta(hours=8))

# --- Canvas ---
W = 1400
H = 1150

# --- Resource Paths ---
RES_DIR = Path(__file__).parent / "note_res"

# --- Colors ---
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (200, 200, 210)
TEXT_DIM = (160, 160, 175)
ACCENT_BLUE = (100, 180, 255)
ACCENT_GREEN = (100, 220, 140)
ACCENT_ORANGE = (255, 180, 80)

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


async def _get_random_wallpaper() -> Image.Image | None:
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


def _load_res(name: str) -> Image.Image | None:
    path = RES_DIR / name
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


def _draw_stamina_bar(
    canvas: Image.Image,
    x: int,
    y: int,
    cur: int,
    max_val: int,
    recover_seconds: int,
) -> None:
    draw = ImageDraw.Draw(canvas)

    # 体力数值 (右侧)
    val_text = f"{cur} / {max_val}"
    draw.text((x + 740, y + 30), val_text, font=_font(48), fill=TEXT_WHITE, anchor="ra")

    # 进度条
    bar_x = x + 140
    bar_y = y + 85
    bar_w = 580
    bar_h = 30

    ratio = cur / max_val if max_val > 0 else 1.0
    ratio = max(0.0, min(1.0, ratio))

    blue_bar = _load_res("line_bar01.png")
    red_bar = _load_res("line_bar02.png")

    if blue_bar and red_bar:
        bw, bh = blue_bar.size
        scale = bar_h / bh

        # 蓝色部分（已充满）
        blue_w = int(bar_w * ratio)
        if blue_w > 0:
            src_w = int(bw * ratio)
            if src_w < 1:
                src_w = 1
            blue_crop = blue_bar.crop((0, 0, src_w, bh))
            blue_resized = blue_crop.resize((blue_w, bar_h), Image.Resampling.LANCZOS)
            canvas.paste(blue_resized, (bar_x, bar_y), blue_resized)

        # 红色部分（未满）
        red_w = bar_w - blue_w
        if red_w > 0:
            src_w = int(bw * (1 - ratio))
            if src_w < 1:
                src_w = 1
            red_crop = red_bar.crop((0, 0, src_w, bh))
            red_resized = red_crop.resize((red_w, bar_h), Image.Resampling.LANCZOS)
            canvas.paste(red_resized, (bar_x + blue_w, bar_y), red_resized)

    # 回复时间
    if recover_seconds > 0:
        recover_text = f"剩余回复时间: {_fmt_recover(recover_seconds)}"
        draw.text((bar_x, bar_y + 38), recover_text, font=_font(18), fill=TEXT_DIM)


def _draw_activity_bar(
    canvas: Image.Image,
    x: int,
    y: int,
    name: str,
    score_text: str,
    remain_text: str,
    is_open: bool,
) -> None:
    draw = ImageDraw.Draw(canvas)

    # 活动名称 (中间偏左)
    draw.text((x + 200, y + 35), name, font=_font(32), fill=TEXT_WHITE)

    # 状态 + 剩余时间
    status = "开放中" if is_open else "未开放"
    status_color = ACCENT_GREEN if is_open else TEXT_DIM
    draw.text((x + 200, y + 78), status, font=_font(18), fill=status_color)

    if remain_text and is_open:
        draw.text((x + 280, y + 78), remain_text, font=_font(18), fill=TEXT_DIM)

    # 分数 (右侧)
    draw.text((x + 740, y + 50), score_text, font=_font(40), fill=TEXT_WHITE, anchor="ra")


def _draw_player_info(
    canvas: Image.Image,
    y: int,
    ev: Event,
    nickname: str,
    uid: str,
    level: int,
    active_days: int,
    rating: str,
) -> None:
    draw = ImageDraw.Draw(canvas)

    # 使用 player_info_bar_long.png 作为背景
    info_bar = _load_res("player_info_bar_long.png")
    if info_bar:
        bar_w, bar_h = info_bar.size
        bar_x = (W - bar_w) // 2
        canvas.paste(info_bar, (bar_x, y), info_bar)
    else:
        bar_x = 50
        bar_h = 192

    # 头像 (左侧，参考 draw_title 的 179 大小)
    avatar_size = 120
    try:
        avatar = get_cached_avatar(ev, ev.user_id)
        avatar_img = draw_decorated_avatar(avatar, avatar_size)
        canvas.alpha_composite(avatar_img, (bar_x + 30, y + (bar_h - avatar_size) // 2))
    except Exception:
        pass

    text_x = bar_x + 30 + avatar_size + 24

    # 昵称
    draw.text((text_x, y + 36), nickname, font=_font(34), fill=TEXT_WHITE)

    # UID
    draw.text((text_x, y + 88), f"UID {uid}", font=_font(20), fill=TEXT_DIM)

    # 等级徽章（参考 draw_title.py 使用 level_bg.png）
    level_bg_path = Path(__file__).parent / "res" / "title" / "level_bg.png"
    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        orig_w, orig_h = level_bg.size
        scale = 110 / orig_w
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        level_bg = level_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(20))) + 16
        lv_y = y + 80
        canvas.alpha_composite(level_bg, (lv_x, lv_y))
        draw.text((lv_x + new_w // 2, lv_y + new_h // 2), f"Lv.{level}", font=_font(20), fill=TEXT_WHITE, anchor="mm")
    else:
        # fallback
        level_text = f"Lv.{level}"
        lw = int(draw.textlength(level_text, font=_font(20)))
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(20))) + 16
        lv_y = y + 82
        draw.rounded_rectangle((lv_x, lv_y, lv_x + lw + 16, lv_y + 28), radius=4, fill=ACCENT_BLUE)
        draw.text((lv_x + 8 + lw // 2, lv_y + 14), level_text, font=_font(20), fill=TEXT_WHITE, anchor="mm")

    # 累计登舰 (右侧偏左)
    days_x = bar_x + bar_w - 280 if info_bar else W - 280
    draw.text((days_x, y + 42), str(active_days), font=_font(42), fill=TEXT_WHITE, anchor="mm")
    draw.text((days_x, y + 96), "累计登舰", font=_font(18), fill=TEXT_DIM, anchor="mm")

    # 评级图标 (最右侧，参考 draw_title.py)
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = Path(__file__).parent / "res" / "eval_icon" / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA").resize((110, 110), Image.Resampling.LANCZOS)
        icon_x = bar_x + bar_w - 160 if info_bar else W - 210
        canvas.alpha_composite(eval_icon, (icon_x, y + 40))


async def draw_note_img(
    ev: Event,
    uid: str,
    index_data: Dict,
    note_data: Dict,
) -> bytes:
    canvas = Image.new("RGBA", (W, H), (20, 20, 30, 255))
    draw = ImageDraw.Draw(canvas)

    # --- Background: blurred wallpaper ---
    wallpaper = await _get_random_wallpaper()
    if wallpaper:
        # 模糊背景
        bg = _fit_centered(wallpaper, (W, H))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=15))
        dark_overlay = Image.new("RGBA", (W, H), (15, 15, 25, 200))
        bg = Image.alpha_composite(bg, dark_overlay)
        canvas.alpha_composite(bg, (0, 0))

        # 左侧角色立绘（原图，不模糊，占左半部分）
        char_img = _fit_centered(wallpaper, (600, H))
        char_img = char_img.resize((600, H), Image.Resampling.LANCZOS)
        canvas.alpha_composite(char_img, (-50, 0))

    # --- FG Overlays ---
    fg1 = _load_res("FG01.png")
    if fg1:
        canvas.alpha_composite(fg1, (0, 0))
    fg2 = _load_res("FG02.png")
    if fg2:
        canvas.alpha_composite(fg2, (0, 0))

    # --- Title Section ---
    title_img = _load_res("title.png")
    if title_img:
        canvas.paste(title_img, (580, 20), title_img)

    # 状态标记
    yes_tag = _load_res("yes_tag.png")
    no_tag = _load_res("no_tag.png")
    if yes_tag:
        canvas.paste(yes_tag, (580, 120), yes_tag)
    draw.text((620, 128), "社区已签到", font=_font(18), fill=ACCENT_GREEN)

    if no_tag:
        canvas.paste(no_tag, (740, 120), no_tag)
    draw.text((780, 128), "历练值未达成", font=_font(18), fill=(255, 100, 120))

    # 查看详情按钮
    desc_tag = _load_res("desc_tag.png")
    if desc_tag:
        canvas.paste(desc_tag, (1170, 30), desc_tag)

    # --- Stamina Bar ---
    bar01 = _load_res("bar01.png")
    bar_x = 560
    bar_y = 200
    if bar01:
        canvas.paste(bar01, (bar_x, bar_y), bar01)

    cur_stamina = note_data.get("current_stamina", 0)
    max_stamina = note_data.get("max_stamina", 1)
    recover = note_data.get("stamina_recover_time", 0)
    _draw_stamina_bar(canvas, bar_x, bar_y, cur_stamina, max_stamina, recover)

    # --- Activity Bars ---
    activities = []

    # 往世乐土
    gw = note_data.get("god_war", {})
    if gw:
        cur_r = gw.get("cur_reward", "?")
        max_r = gw.get("max_reward", "?")
        is_open = gw.get("is_open", False)
        remain = _fmt_schedule_end(gw.get("schedule_end", "0")) if is_open else ""
        activities.append(("往事乐土", f"{cur_r} / {max_r}", f"剩余时间 {remain}" if remain else "", is_open, "bar04.png"))

    act_y = 360
    act_gap = 20
    for name, score, remain, is_open, bar_name in activities:
        bar_img = _load_res(bar_name)
        if bar_img:
            canvas.paste(bar_img, (bar_x, act_y), bar_img)
        _draw_activity_bar(canvas, bar_x, act_y, name, score, remain, is_open)
        act_y += 140 + act_gap

    # --- Footer sizing (loaded first to position player info bar above it) ---
    footer_path = Path(__file__).parent / "footer.png"
    fh = 0
    footer_img = None
    if footer_path.exists():
        footer_img = Image.open(footer_path).convert("RGBA")
        _, fh = footer_img.size

    # --- Player Info Bar ---
    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    pref = index_data.get("preference", {})
    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    rating = pref.get("comprehensive_rating", "C")
    active_days = stats.get("active_day_number", "?")

    info_bar = _load_res("player_info_bar_long.png")
    bar_h = info_bar.height if info_bar else 192
    info_y = H - fh - 15 - bar_h
    _draw_player_info(canvas, info_y, ev, nickname, uid, int(level) if str(level).isdigit() else 0, int(active_days) if str(active_days).isdigit() else 0, rating)

    # --- Footer ---
    if footer_img:
        fw, fh = footer_img.size
        fx = (W - fw) // 2
        fy = H - fh
        canvas.alpha_composite(footer_img, (fx, fy))

    return await convert_img(canvas)
