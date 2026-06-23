from __future__ import annotations

import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from .avatar_utils import get_cached_avatar, draw_decorated_avatar
from .draw_title import EVAL_RATING_TO_ICON

CST = timezone(timedelta(hours=8))

# --- Canvas ---
W = 1300
H = 1300

# --- Resource Paths ---
HANDBOOK_RES_DIR = Path(__file__).parent / "handbook_res"
COMMON_RES_DIR = Path(__file__).parent / "note_res"

# --- Colors ---
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (200, 200, 210)
TEXT_DIM = (160, 160, 175)
ACCENT_BLUE = (100, 180, 255)
ACCENT_GREEN = (100, 220, 140)
ACCENT_ORANGE = (255, 180, 80)
ACCENT_YELLOW = (254, 231, 114)  # #FEE772

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

    PAD = 16

    draw = ImageDraw.Draw(canvas)
    glyph_bbox = draw.textbbox((0, 0), text, font=font)
    gx0, gy0, gx1, gy1 = glyph_bbox
    gw = gx1 - gx0
    gh = gy1 - gy0

    tmp_w = gw + PAD + int(gh * SKEW) + PAD
    tmp_h = gh + PAD + PAD
    ink_x = PAD - gx0
    ink_y = PAD - gy0

    tmp = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    tmp_draw.text((ink_x, ink_y), text, font=font, fill=fill)

    pivot_y = PAD + gh
    skewed = tmp.transform(
        (tmp_w, tmp_h),
        Image.AFFINE,
        (1, SKEW, -SKEW * pivot_y, 0, 1, 0),
        Image.Resampling.BICUBIC,
    )

    bbox = draw.textbbox(xy, text, font=font, anchor=anchor)
    canvas.alpha_composite(skewed, (bbox[0] - PAD, bbox[1] - PAD))


def _load_handbook_res(name: str) -> Image.Image | None:
    path = HANDBOOK_RES_DIR / name
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


def _load_common_res(name: str) -> Image.Image | None:
    path = COMMON_RES_DIR / name
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


def _crop_center(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Center-crop image to target size."""
    iw, ih = img.size
    left = (iw - tw) // 2
    top = (ih - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _draw_section_title(canvas: Image.Image, x: int, y: int, text: str) -> None:
    """Render section title with italic style."""
    _draw_italic_text(canvas, (x, y), text, _ifont(44), TEXT_WHITE)


def _draw_multi_color_title(
    canvas: Image.Image,
    x: int,
    y: int,
    segments: list[tuple[str, tuple[int, ...]]],
) -> None:
    """Render title with multiple colored segments."""
    draw = ImageDraw.Draw(canvas)
    font = _ifont(44)
    current_x = x
    for text, color in segments:
        _draw_italic_text(canvas, (current_x, y), text, font, color)
        current_x += int(draw.textlength(text, font=font))


def _draw_bar_number(
    canvas: Image.Image,
    x: int,
    y: int,
    bar_w: int,
    bar_h: int,
    number: str,
    color: tuple[int, ...] = ACCENT_YELLOW,
) -> None:
    """Draw number on the right side of a bar, vertically centered."""
    _draw_italic_text(
        canvas,
        (x + bar_w - 30, y + bar_h // 2),
        number,
        _ifont(40),
        color,
        anchor="rm",
    )


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

    info_bar = _load_common_res("player_info_bar_long.png")
    if info_bar:
        bar_w, bar_h = info_bar.size
        bar_x = (W - bar_w) // 2
        canvas.paste(info_bar, (bar_x, y), info_bar)
    else:
        bar_x = 50
        bar_h = 192

    avatar_x = bar_x + 90
    if avatar_img is not None:
        try:
            aw, ah = avatar_img.size
            avatar_y = y + (bar_h - ah) // 2
            canvas.alpha_composite(avatar_img, (avatar_x, avatar_y))
        except Exception:
            pass

    if avatar_img is not None:
        text_x = avatar_x + avatar_img.size[0] + 40
    else:
        text_x = avatar_x + 152 + 40

    _draw_italic_text(canvas, (text_x, y + 36), nickname, _ifont(54), TEXT_WHITE)

    draw.text((text_x, y + 36 + 54 + 10), f"UID {uid}", font=_font(28), fill=TEXT_DIM)

    level_bg_path = Path(__file__).parent / "res" / "title" / "level_bg.png"
    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        orig_w, orig_h = level_bg.size
        scale = 110 / orig_w
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        level_bg = level_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(28))) + 16
        lv_y = y + 36 + 54 + 10
        canvas.alpha_composite(level_bg, (lv_x, lv_y))
        draw.text(
            (lv_x + new_w // 2, lv_y + new_h // 2),
            f"Lv.{level}",
            font=_font(20),
            fill=TEXT_WHITE,
            anchor="mm",
        )
    else:
        level_text = f"Lv.{level}"
        lw = int(draw.textlength(level_text, font=_font(20)))
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(28))) + 16
        lv_y = y + 36 + 54 + 10
        draw.rounded_rectangle(
            (lv_x, lv_y, lv_x + lw + 16, lv_y + 28),
            radius=4,
            fill=ACCENT_BLUE,
        )
        draw.text(
            (lv_x + 8 + lw // 2, lv_y + 14),
            level_text,
            font=_font(20),
            fill=TEXT_WHITE,
            anchor="mm",
        )

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
    days_value_bottom = days_value_y + 18
    days_title_y = days_value_bottom + 8 + 14
    draw.text(
        (days_x + info_w // 2, days_value_y),
        str(active_days),
        font=_font(36),
        fill=TEXT_WHITE,
        anchor="mm",
    )
    draw.text(
        (days_x + info_w // 2, days_title_y),
        "累计登舰",
        font=_font(28),
        fill=TEXT_DIM,
        anchor="mm",
    )

    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = Path(__file__).parent / "res" / "eval_icon" / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA").resize(
            (110, 110), Image.Resampling.LANCZOS
        )
        icon_x = bar_x + bar_w - 60 - 110 if info_bar else W - 170
        icon_y = y + (bar_h - 110) // 2
        canvas.alpha_composite(eval_icon, (icon_x, icon_y))


async def draw_handbook_img(
    ev: Event,
    uid: str,
    index_data: dict,
    count_data: dict,
    finance_data: dict,
) -> bytes:
    t_start = time.time()
    canvas = Image.new("RGBA", (W, H), (20, 20, 30, 255))

    # --- Background ---
    bg_img = _load_handbook_res("bg1.jpg")
    if bg_img:
        bg_cropped = _crop_center(bg_img, W, H)
        canvas.paste(bg_cropped, (0, 0))
    logger.info(f"[崩坏3] [手账渲染] 背景完成 ({time.time()-t_start:.2f}s)")

    # --- Player Info Bar ---
    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    pref = index_data.get("preference", {})
    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    rating = pref.get("comprehensive_rating", "C")
    active_days = stats.get("active_day_number", "?")

    avatar_img = None
    try:
        avatar = await get_cached_avatar(ev, ev.user_id)
        avatar_img = draw_decorated_avatar(avatar, 179)
    except Exception:
        pass

    _draw_player_info(
        canvas, 120, ev, nickname, uid,
        int(level) if str(level).isdigit() else 0,
        int(active_days) if str(active_days).isdigit() else 0,
        rating, avatar_img,
    )
    logger.info(f"[崩坏3] [手账渲染] 玩家信息完成 ({time.time()-t_start:.2f}s)")

    # --- Monthly Section ---
    month_str = finance_data.get("month", "")
    day_hcoin = finance_data.get("day_hcoin")
    day_star = finance_data.get("day_star")
    is_current_month = day_hcoin is not None or day_star is not None

    # Player info bar bottom: 120 + 192 = 312
    # Monthly section: 60px gap from player info
    monthly_title_y = 312 + 60  # 372

    if is_current_month:
        # Current month: use local time
        now = datetime.now(tz=CST)
        month_num = f"{now.month:02d}"
        day_num = f"{now.day:02d}"
        title_segments = [
            ("截止 ", TEXT_WHITE),
            (month_num, ACCENT_YELLOW),
            (" 月 ", TEXT_WHITE),
            (day_num, ACCENT_YELLOW),
            (" 日，舰长本月已收到...", TEXT_WHITE),
        ]
    else:
        # Last month: use month from data
        if month_str:
            try:
                dt = datetime.strptime(month_str, "%Y-%m")
                month_num = str(dt.month)
            except Exception:
                month_num = "X"
        else:
            month_num = "X"
        title_segments = [
            ("舰长", TEXT_WHITE),
            (month_num, ACCENT_YELLOW),
            ("月已收到...", TEXT_WHITE),
        ]

    _draw_multi_color_title(canvas, 40, monthly_title_y, title_segments)

    # Monthly bars
    bar_w, bar_h = 600, 140
    bar_gap = 20  # gap between crystal and star bars (horizontal)

    # Bar positions: 40px gap after italic title (title 44px high)
    monthly_title_gap = 40
    monthly_bar_y = monthly_title_y + 44 + monthly_title_gap  # 456

    # Bar 1: Monthly crystals (left)
    bar1_img = _load_handbook_res("bar1.png")
    if bar1_img:
        canvas.paste(bar1_img, (40, monthly_bar_y), bar1_img)
    _draw_bar_number(canvas, 40, monthly_bar_y, bar_w, bar_h, str(finance_data.get("month_hcoin", 0)))

    # Bar 2: Monthly stars (right, 20px gap from crystals)
    bar2_img = _load_handbook_res("bar2.png")
    star_x = 40 + bar_w + bar_gap  # 660
    if bar2_img:
        canvas.paste(bar2_img, (star_x, monthly_bar_y), bar2_img)
    _draw_bar_number(canvas, star_x, monthly_bar_y, bar_w, bar_h, str(finance_data.get("month_star", 0)))

    # Bar 3: Monthly supply cards (below crystals, 40px gap)
    supply_gap = 40
    bar3_img = _load_handbook_res("bar3.png")
    supply_y = monthly_bar_y + bar_h + supply_gap  # 636
    if bar3_img:
        canvas.paste(bar3_img, (40, supply_y), bar3_img)
    _draw_bar_number(canvas, 40, supply_y, bar_w, bar_h, str(count_data.get("count", 0)))

    logger.info(f"[崩坏3] [手账渲染] 月度数据完成 ({time.time()-t_start:.2f}s)")

    # --- Today Section (only if day data exists) ---
    if is_current_month:
        # Monthly section bottom: supply_y + bar_h
        # Daily section: 130px gap from monthly
        monthly_bottom = supply_y + bar_h  # 776
        daily_title_y = monthly_bottom + 130  # 906
        daily_title_segments = [
            ("今日", ACCENT_YELLOW),
            ("，舰长已收到...", TEXT_WHITE),
        ]
        _draw_multi_color_title(canvas, 40, daily_title_y, daily_title_segments)

        # Daily bar positions: 30px gap after italic title
        daily_title_gap = 30
        daily_bar_y = daily_title_y + 44 + daily_title_gap  # 980

        # Today bars
        # Bar 1: Today crystals
        if bar1_img:
            canvas.paste(bar1_img, (40, daily_bar_y), bar1_img)
        _draw_bar_number(canvas, 40, daily_bar_y, bar_w, bar_h, str(finance_data.get("day_hcoin", 0)))

        # Bar 2: Today stars (20px gap from crystals)
        if bar2_img:
            canvas.paste(bar2_img, (star_x, daily_bar_y), bar2_img)
        _draw_bar_number(canvas, star_x, daily_bar_y, bar_w, bar_h, str(finance_data.get("day_star", 0)))

        logger.info(f"[崩坏3] [手账渲染] 今日数据完成 ({time.time()-t_start:.2f}s)")

    # --- FG Overlay ---
    fg_img = _load_handbook_res("fg.png")
    if fg_img:
        canvas.alpha_composite(fg_img, (0, 0))

    # --- Footer ---
    footer_path = Path(__file__).parent / "footer.png"
    if footer_path.exists():
        footer_img = Image.open(footer_path).convert("RGBA")
        fw, fh = footer_img.size
        fx = (W - fw) // 2
        fy = H - fh - 20
        canvas.alpha_composite(footer_img, (fx, fy))

    logger.info(f"[崩坏3] [手账渲染] 渲染完成 ({time.time()-t_start:.2f}s)")
    result = await convert_img(canvas)
    return result
