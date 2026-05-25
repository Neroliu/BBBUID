from __future__ import annotations

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

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
_italic_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

SKEW = 0.25  # italic slant factor


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


def _ifont(size: int) -> ImageFont.FreeTypeFont:
    if size not in _italic_font_cache:
        _italic_font_cache[size] = core_font(size)
    return _italic_font_cache[size]


def _draw_italic_text(
    canvas: Image.Image,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...],
    anchor: str | None = None,
) -> None:
    """Draw text with an italic slant by applying an affine skew transform."""
    if not text:
        return

    PAD = 16  # generous padding for anti-aliasing, skew overflow, and font metrics

    draw = ImageDraw.Draw(canvas)
    # Get glyph bounding box (relative to the drawing origin)
    glyph_bbox = draw.textbbox((0, 0), text, font=font)
    gx0, gy0, gx1, gy1 = glyph_bbox
    gw = gx1 - gx0
    gh = gy1 - gy0

    # Draw text into a padded tmp image; offset so ink starts at (PAD, PAD)
    tmp_w = gw + PAD + int(gh * SKEW) + PAD
    tmp_h = gh + PAD + PAD
    ink_x = PAD - gx0  # drawing origin x in tmp
    ink_y = PAD - gy0  # drawing origin y in tmp

    tmp = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    tmp_draw.text((ink_x, ink_y), text, font=font, fill=fill)

    # Shear: top shifts right, bottom stays → standard italic lean
    # Pivot at the bottom of the ink region so the baseline stays put
    pivot_y = PAD + gh
    skewed = tmp.transform(
        (tmp_w, tmp_h),
        Image.AFFINE,
        (1, SKEW, -SKEW * pivot_y, 0, 1, 0),
        Image.Resampling.BICUBIC,
    )

    # Paste: align the ink in tmp (top-left at PAD, PAD) with the target
    # position on the canvas given by textbbox with anchor
    bbox = draw.textbbox(xy, text, font=font, anchor=anchor)
    canvas.alpha_composite(skewed, (bbox[0] - PAD, bbox[1] - PAD))


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
        # API 可能返回毫秒或秒级时间戳
        if end_ts > 1e12:
            end_ts = end_ts // 1000
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


def _get_random_portrait() -> Image.Image | None:
    """从本地 wiki 立绘缓存中随机选一张角色立绘。"""
    portrait_path = WIKI_PATH / "立绘" / PORTRAIT_ICONS_DIR
    if not portrait_path.exists():
        return None
    all_files: list[Path] = []
    for cid_dir in portrait_path.iterdir():
        if not cid_dir.is_dir():
            continue
        for f in cid_dir.iterdir():
            if f.is_file() and f.suffix == ".png":
                all_files.append(f)
    if not all_files:
        return None
    try:
        return Image.open(random.choice(all_files)).convert("RGBA")
    except Exception:
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

    # 体力数值 (右侧) — 当前体力54, "/"和总体力32，底部(baseline)对齐
    baseline_y = y + 62

    # 区域右边界对齐 bar01.png 背景图右边缘 (背景宽790)
    region_right = x + 790
    text_right = region_right - 30

    cur_w = int(draw.textlength(str(cur), font=_ifont(54)))
    slash_w = int(draw.textlength(" / ", font=_ifont(32)))
    total_w = int(draw.textlength(str(max_val), font=_ifont(32)))
    total_left = text_right - total_w
    slash_left = total_left - slash_w
    cur_left = slash_left - cur_w

    # 进度条 — 紧贴体力文字 baseline，右对齐于区域右边
    bar_w = 650
    bar_h = 67
    bar_x = region_right - bar_w - 5
    bar_y = baseline_y - 15

    ratio = cur / max_val if max_val > 0 else 1.0
    ratio = max(0.0, min(1.0, ratio))

    bg_bar = _load_res("line_bar01.png")
    cur_bar = _load_res("line_bar02.png")

    if bg_bar and cur_bar:
        # 1. 绘制总体力底条（line_bar01）全长
        bg_resized = bg_bar.resize((bar_w, bar_h), Image.Resampling.LANCZOS)
        canvas.paste(bg_resized, (bar_x, bar_y), bg_resized)

        # 2. 绘制当前体力覆盖层（line_bar02）— 整图缩放到目标高度，再按比例裁剪宽度
        cur_resized = cur_bar.resize((bar_w, bar_h), Image.Resampling.LANCZOS)
        cur_display_w = int(bar_w * ratio)
        if cur_display_w > 0:
            cur_crop = cur_resized.crop((0, 0, cur_display_w, bar_h))
            canvas.paste(cur_crop, (bar_x, bar_y), cur_crop)

    # 体力文字 — 在进度条之后渲染
    _draw_italic_text(canvas, (cur_left, baseline_y), str(cur), _ifont(54), TEXT_WHITE, anchor="ls")
    _draw_italic_text(canvas, (slash_left, baseline_y), " / ", _ifont(32), TEXT_WHITE, anchor="ls")
    _draw_italic_text(canvas, (text_right, baseline_y), str(max_val), _ifont(32), TEXT_WHITE, anchor="rs")

    # 回复时间 — 与体力条左对齐+20
    if recover_seconds > 0:
        recover_text = f"剩余回复时间: {_fmt_recover(recover_seconds)}"
        _draw_italic_text(canvas, (bar_x + 20, bar_y + bar_h - 20), recover_text, _ifont(20), TEXT_WHITE)


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

    if remain_text:
        _draw_italic_text(canvas, (x + 288, y + 88), remain_text, _ifont(18), TEXT_DIM)

    # 分数 (右侧) — 在背景图(高140)内竖向居中
    _draw_italic_text(canvas, (x + 740, y + 70), score_text, _ifont(40), TEXT_WHITE, anchor="rm")


def _draw_player_info(
    canvas: Image.Image,
    y: int,
    ev: Event,
    nickname: str,
    uid: str,
    level: int,
    active_days: int,
    rating: str,
    avatar_img: Image.Image | None = None,
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

    # 头像 — 在背景图区域内居中
    avatar_x = bar_x + 90
    if avatar_img is not None:
        try:
            aw, ah = avatar_img.size
            avatar_y = y + (bar_h - ah) // 2
            canvas.alpha_composite(avatar_img, (avatar_x, avatar_y))
        except Exception:
            pass

    # 昵称/UID/等级 — 整体以头像为锚点，距头像右边40px
    if avatar_img is not None:
        text_x = avatar_x + avatar_img.size[0] + 40
    else:
        text_x = avatar_x + 152 + 40

    # 昵称
    _draw_italic_text(canvas, (text_x, y + 36), nickname, _ifont(34), TEXT_WHITE)

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

    # 累计登舰 — 使用 info_bg.png 背景，竖向居中于信息条
    info_bg_path = Path(__file__).parent / "res" / "info" / "info_bg.png"
    info_bg_img = None
    info_w, info_h = 174, 100
    if info_bg_path.exists():
        info_bg_img = Image.open(info_bg_path).convert("RGBA")
        info_w, info_h = info_bg_img.size

    days_x = bar_x + bar_w - 340 if info_bar else W - 340
    days_card_y = y + (bar_h - info_h) // 2
    if info_bg_img:
        canvas.alpha_composite(info_bg_img, (days_x, days_card_y))

    days_value_y = days_card_y + 35
    days_title_y = days_card_y + info_h - 20
    draw.text((days_x + info_w // 2, days_value_y), str(active_days), font=_font(36), fill=TEXT_WHITE, anchor="mm")
    draw.text((days_x + info_w // 2, days_title_y), "累计登舰", font=_font(18), fill=TEXT_DIM, anchor="mm")

    # 评级图标 — 竖向居中，右边距60px
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = Path(__file__).parent / "res" / "eval_icon" / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA").resize((110, 110), Image.Resampling.LANCZOS)
        icon_x = bar_x + bar_w - 60 - 110 if info_bar else W - 170
        icon_y = y + (bar_h - 110) // 2
        canvas.alpha_composite(eval_icon, (icon_x, icon_y))


async def draw_note_img(
    ev: Event,
    uid: str,
    index_data: Dict,
    note_data: Dict,
) -> bytes:
    canvas = Image.new("RGBA", (W, H), (20, 20, 30, 255))
    draw = ImageDraw.Draw(canvas)

    # --- Background ---
    wallpaper = await _get_random_wallpaper()
    if wallpaper:
        # 壁纸铺满全画布（原图，不模糊）
        bg = _fit_centered(wallpaper, (W, H))
        canvas.alpha_composite(bg, (0, 0))

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
        canvas.paste(title_img, (487, 38), title_img)

    # 状态标记
    yes_tag = _load_res("yes_tag.png")
    no_tag = _load_res("no_tag.png")

    # 社区签到
    is_signed = bool(index_data.get("preference", {}).get("community", 0))
    if is_signed:
        if yes_tag:
            canvas.paste(yes_tag, (510, 145), yes_tag)
        _draw_italic_text(canvas, (550, 153), "社区已签到", _ifont(18), ACCENT_GREEN)
    else:
        if no_tag:
            canvas.paste(no_tag, (510, 145), no_tag)
        _draw_italic_text(canvas, (550, 153), "社区未签到", _ifont(18), (255, 100, 120))

    # 历练值
    cur_train = note_data.get("current_train_score", 0)
    max_train = note_data.get("max_train_score", 1)
    train_achieved = cur_train >= max_train if max_train > 0 else True
    if train_achieved:
        if yes_tag:
            canvas.paste(yes_tag, (670, 145), yes_tag)
        _draw_italic_text(canvas, (710, 153), "历练值已达成", _ifont(18), ACCENT_GREEN)
    else:
        if no_tag:
            canvas.paste(no_tag, (670, 145), no_tag)
        _draw_italic_text(canvas, (710, 153), "历练值未达成", _ifont(18), (255, 100, 120))

    # 查看详情按钮
    desc_tag = _load_res("desc_tag.png")
    if desc_tag:
        canvas.paste(desc_tag, (1017, 116), desc_tag)

    # --- Stamina Bar ---
    bar_x = 510
    bar_y = 233

    bar01 = _load_res("bar01.png")
    if bar01:
        canvas.paste(bar01, (bar_x, bar_y), bar01)

    cur_stamina = note_data.get("current_stamina", 0)
    max_stamina = note_data.get("max_stamina", 1)
    recover = note_data.get("stamina_recover_time", 0)
    _draw_stamina_bar(canvas, bar_x, bar_y, cur_stamina, max_stamina, recover)

    # --- Activity Bars ---
    activities = []

    # 超弦空间
    ultra = note_data.get("ultra_endless", {})
    greedy = note_data.get("greedy_endless", {})
    endless = ultra if ultra else greedy
    if endless:
        score = endless.get("challenge_score", "?")
        is_open = endless.get("is_open", False)
        if is_open:
            remain = _fmt_schedule_end(endless.get("schedule_end", "0"))
            remain_text = f"剩余时间 {remain}" if remain else "未开启"
        else:
            remain_text = "未开启"
        activities.append(("超弦空间", str(score), remain_text, is_open, "bar02.png"))

    # 记忆战场
    bf = note_data.get("battle_field", {})
    if bf:
        cur_r = bf.get("cur_reward", "?")
        max_r = bf.get("max_reward", "?")
        is_open = bf.get("is_open", False)
        if is_open:
            remain = _fmt_schedule_end(bf.get("schedule_end", "0"))
            remain_text = f"剩余时间 {remain}" if remain else "未开启"
        else:
            remain_text = "未开启"
        activities.append(("记忆战场", f"{cur_r} / {max_r}", remain_text, is_open, "bar03.png"))

    # 往世乐土
    gw = note_data.get("god_war", {})
    if gw:
        cur_r = gw.get("cur_reward", "?")
        is_open = gw.get("is_open", False)
        remain = _fmt_schedule_end(gw.get("schedule_end", "0"))
        activities.append(("往事乐土", str(cur_r), f"剩余时间 {remain}" if remain else "", is_open, "bar04.png"))

    act_y = 393
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

    # 头像（参考 bbb查询 在 async 中 await 获取）
    avatar_img = None
    try:
        avatar = await get_cached_avatar(ev, ev.user_id)
        avatar_img = draw_decorated_avatar(avatar, 179)
    except Exception:
        pass

    info_bar = _load_res("player_info_bar_long.png")
    bar_h = info_bar.height if info_bar else 192
    info_y = H - fh - 25 - bar_h
    _draw_player_info(
        canvas, info_y, ev, nickname, uid,
        int(level) if str(level).isdigit() else 0,
        int(active_days) if str(active_days).isdigit() else 0,
        rating, avatar_img,
    )

    # --- Footer ---
    if footer_img:
        fw, fh = footer_img.size
        fx = (W - fw) // 2
        fy = H - fh
        canvas.alpha_composite(footer_img, (fx, fy))

    return await convert_img(canvas)
