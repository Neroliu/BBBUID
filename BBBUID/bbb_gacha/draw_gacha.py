"""崩坏3抽卡记录 PIL 渲染模块。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from ..bbb_data.avatar_utils import get_cached_avatar, draw_decorated_avatar
from ..bbb_data.draw_title import EVAL_RATING_TO_ICON

# --- Resource Paths ---
RES_DIR = Path(__file__).parent / "res"
NOTE_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "note_res"
EVAL_ICON_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "eval_icon"
TITLE_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "title"
INFO_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "info"

# --- Canvas ---
W = 1400

# --- Colors ---
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (200, 200, 210)
TEXT_DIM = (160, 160, 175)
GOLD_YELLOW = (254, 231, 114)  # #FEE772
PITY_RED = (255, 80, 80)
ACCENT_BLUE = (100, 180, 255)
TEXT_BLACK = (30, 30, 30)

# --- Font Cache ---
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_italic_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

SKEW = 0.25  # italic slant factor

# --- Pool type hints ---
POOL_HINTS = {
    "char": "S角色",
    "weapon": "5星武器",
    "partner": "协同者",
}


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


def _load_res(name: str, res_dir: Path = NOTE_RES_DIR) -> Image.Image | None:
    path = res_dir / name
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


def _get_emotion_icon(avg_pulls: float) -> Path | None:
    """根据平均抽数获取对应的表情图标路径。"""
    emotion_dir = RES_DIR / "servantemoticon"
    if avg_pulls < 50:
        name = "Emotion1_Type7_4.png"
    elif avg_pulls < 60:
        name = "Emotion1_Type7_2.png"
    elif avg_pulls < 70:
        name = "Emotion1_Type7_7.png"
    elif avg_pulls < 80:
        name = "Emotion1_Type8_1.png"
    elif avg_pulls < 90:
        name = "Emotion1_Type7_1.png"
    else:
        name = "Emotion1_Type7_14.png"

    path = emotion_dir / name
    return path if path.exists() else None


def _load_background() -> Image.Image:
    """加载背景图，按宽度1400等比缩放，不拉伸。"""
    bg_path = RES_DIR / "bg.jpg"
    if bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA")
        iw, ih = bg.size
        if iw != W:
            scale = W / iw
            new_w = W
            new_h = round(ih * scale)
            bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
    else:
        bg = Image.new("RGBA", (W, 800), (30, 35, 50, 255))
    return bg


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
    """复用便笺(mr)指令的玩家信息条渲染。"""
    draw = ImageDraw.Draw(canvas)

    # 使用 player_info_bar_long.png 作为背景（等比放大到1360宽）
    info_bar = _load_res("player_info_bar_long.png")
    if info_bar:
        orig_w, orig_h = info_bar.size
        scale = 1360 / orig_w
        bar_w = 1360
        bar_h = round(orig_h * scale)
        info_bar = info_bar.resize((bar_w, bar_h), Image.Resampling.LANCZOS)
        bar_x = 20
        canvas.paste(info_bar, (bar_x, y), info_bar)
    else:
        bar_x = 20
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
    _draw_italic_text(canvas, (text_x, y + 36), nickname, _ifont(54), TEXT_WHITE)

    # UID
    draw.text((text_x, y + 36 + 54 + 10), f"UID {uid}", font=_font(28), fill=TEXT_DIM)

    # 等级徽章
    level_bg_path = TITLE_RES_DIR / "level_bg.png"
    if level_bg_path.exists():
        level_bg = Image.open(level_bg_path).convert("RGBA")
        orig_w, orig_h = level_bg.size
        scale = 110 / orig_w
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        level_bg = level_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(28))) + 16
        lv_y = y + 36 + 54 + 10
        canvas.alpha_composite(level_bg, (lv_x, lv_y))
        draw.text((lv_x + new_w // 2, lv_y + new_h // 2), f"Lv.{level}", font=_font(20), fill=TEXT_WHITE, anchor="mm")
    else:
        level_text = f"Lv.{level}"
        lw = int(draw.textlength(level_text, font=_font(20)))
        lv_x = text_x + int(draw.textlength(f"UID {uid}", font=_font(28))) + 16
        lv_y = y + 36 + 54 + 10
        draw.rounded_rectangle((lv_x, lv_y, lv_x + lw + 16, lv_y + 28), radius=4, fill=ACCENT_BLUE)
        draw.text((lv_x + 8 + lw // 2, lv_y + 14), level_text, font=_font(20), fill=TEXT_WHITE, anchor="mm")

    # 累计登舰
    info_bg_path = INFO_RES_DIR / "info_bg.png"
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
    draw.text((days_x + info_w // 2, days_value_y), str(active_days), font=_font(36), fill=TEXT_WHITE, anchor="mm")
    draw.text((days_x + info_w // 2, days_title_y), "累计登舰", font=_font(28), fill=TEXT_DIM, anchor="mm")

    # 评级图标
    icon_name = EVAL_RATING_TO_ICON.get(rating.upper(), "SealedDanIcon01.png")
    icon_path = EVAL_ICON_DIR / icon_name
    if icon_path.exists():
        eval_icon = Image.open(icon_path).convert("RGBA").resize((110, 110), Image.Resampling.LANCZOS)
        icon_x = bar_x + bar_w - 60 - 110 if info_bar else W - 170
        icon_y = y + (bar_h - 110) // 2
        canvas.alpha_composite(eval_icon, (icon_x, icon_y))


def _fmt_time(time_str: str) -> str:
    """将时间格式从 2026-05-28 改为 2026.05.28。"""
    return time_str.replace("-", ".")


async def _draw_pool_section(pool: Dict) -> Image.Image:
    """绘制单个卡池区域。"""
    pool_type = pool.get("type", "char")
    pool_name = pool.get("name", "未知卡池")
    items = pool.get("items", [])
    avg_pulls = pool.get("avg_pulls", 0)
    start_time = pool.get("start_time", "")
    end_time = pool.get("end_time", "")
    current_pity = pool.get("current_pity", 0)

    # Banner 背景实际高度
    banner_h = 190

    # 计算网格区域高度
    items_per_row = 7
    item_size = 100
    item_gap = 10
    num_rows = (len(items) + items_per_row - 1) // items_per_row if items else 1
    grid_h = num_rows * (item_size + item_gap) + item_gap

    # 总高度
    total_h = banner_h + 30 + grid_h + 30

    # 创建画布（宽度 = 画布全宽，banner 本身是 1400 宽）
    canvas = Image.new("RGBA", (W, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 绘制 banner 背景（不缩放，原始尺寸，从左侧开始）
    banner_path = RES_DIR / "banner.png"
    if banner_path.exists():
        banner_bg = Image.open(banner_path).convert("RGBA")
        canvas.alpha_composite(banner_bg, (0, 0))

    # --- Banner 区域：全部斜体 ---
    # 卡池名称 (46px, #FEE772)，竖向居中于 banner，距左边 120px
    name_font = _ifont(46)
    name_bbox = draw.textbbox((0, 0), pool_name, font=name_font)
    name_h = name_bbox[3] - name_bbox[1]
    name_y = (banner_h - name_h) // 2
    name_x = 120
    _draw_italic_text(canvas, (name_x, name_y), pool_name, name_font, GOLD_YELLOW)

    # "已x抽未出" — 与卡池名称底部对齐，贴着卡池名称右侧，间距 10px
    name_w = name_bbox[2] - name_bbox[0]
    bottom_y = name_y + name_h  # 卡池名称底部 y
    pity_x = name_x + name_w + 10
    _draw_italic_text(canvas, (pity_x, bottom_y), "已", _ifont(28), TEXT_WHITE, anchor="ld")
    pity_x += 30
    pity_text = str(current_pity)
    _draw_italic_text(canvas, (pity_x, bottom_y), pity_text, _ifont(34), PITY_RED, anchor="ld")
    pity_bbox = draw.textbbox((0, 0), pity_text, font=_ifont(34))
    pity_x += pity_bbox[2] - pity_bbox[0] + 8
    _draw_italic_text(canvas, (pity_x, bottom_y), "抽未出", _ifont(28), TEXT_WHITE, anchor="ld")

    # 抽卡时间范围（斜体 22px 暗灰），与卡池名称左对齐，在卡池名称下方，间距 10px
    time_text = f"{_fmt_time(start_time)} ~ {_fmt_time(end_time)}"
    time_y = name_y + name_h + 10
    _draw_italic_text(canvas, (name_x, time_y), time_text, _ifont(22), TEXT_DIM)

    # 表情图标（不缩放），竖向居中于 banner，右侧距 banner 右侧 120px
    emotion_path = _get_emotion_icon(avg_pulls)
    if emotion_path:
        emotion_img = Image.open(emotion_path).convert("RGBA")
        ew, eh = emotion_img.size
        emotion_x = W - 120 - ew
        emotion_y = (banner_h - eh) // 2
        canvas.alpha_composite(emotion_img, (emotion_x, emotion_y))

    # 角色/武器网格（banner 下方 30px 开始）
    grid_y = banner_h + 30
    grid_w = items_per_row * (item_size + item_gap) - item_gap
    grid_start_x = (W - grid_w) // 2

    # 加载边框
    frame_path = RES_DIR / "char_frame2.png"
    frame_img = None
    if frame_path.exists():
        frame_img = Image.open(frame_path).convert("RGBA")

    for i, item in enumerate(items):
        row = i // items_per_row
        col = i % items_per_row

        item_x = grid_start_x + col * (item_size + item_gap)
        item_y = grid_y + row * (item_size + item_gap)

        # 绘制边框背景
        if frame_img:
            framed = frame_img.resize((item_size, item_size + 25), Image.Resampling.LANCZOS)
            canvas.alpha_composite(framed, (item_x, item_y))

        # 绘制角色/武器图标
        icon_path = item.get("icon_path")
        if icon_path and isinstance(icon_path, Path) and icon_path.exists():
            try:
                icon = Image.open(icon_path).convert("RGBA")
                icon = icon.resize((item_size - 10, item_size - 10), Image.Resampling.LANCZOS)
                canvas.alpha_composite(icon, (item_x + 5, item_y + 5))
            except Exception:
                pass

        # 绘制抽数标注
        pulls = item.get("pulls", 0)
        pulls_text = f"{pulls}抽"
        draw.text(
            (item_x + item_size // 2, item_y + item_size + 5),
            pulls_text,
            font=_font(14),
            fill=TEXT_BLACK,
            anchor="mt",
        )

    return canvas


async def draw_gacha_img(data: Dict, ev=None) -> bytes:
    """绘制抽卡记录图片，返回 PNG 字节流。"""
    # 加载背景（等比缩放，不拉伸）
    bg = _load_background()
    bg_w, bg_h = bg.size

    uid = data.get("uid", "")
    nickname = data.get("nickname", "未知舰长")
    level = data.get("level", 0)
    login_days = data.get("login_days", 0)
    rating = data.get("rating", "C")

    # 头像
    avatar_img = None
    if ev:
        try:
            avatar = await get_cached_avatar(ev, ev.user_id)
            avatar_img = draw_decorated_avatar(avatar, 179)
        except Exception as e:
            logger.warning(f"[崩坏3] [抽卡渲染] 获取头像失败: {e}")

    # 玩家信息条高度（等比放大到1360宽）
    info_bar = _load_res("player_info_bar_long.png")
    if info_bar:
        player_h = round(info_bar.height * (1360 / info_bar.width)) + 20
    else:
        player_h = 210

    # 计算卡池区域
    pool_imgs = []
    for pool in data.get("pools", []):
        pool_img = await _draw_pool_section(pool)
        pool_imgs.append(pool_img)

    total_pool_h = sum(p.height for p in pool_imgs) + 20 * len(pool_imgs) + 40
    total_h = player_h + total_pool_h

    # 创建最终画布
    final_h = max(total_h, bg_h)
    canvas = Image.new("RGBA", (W, final_h), (30, 35, 50, 255))

    # 背景居中铺设（超出部分截断）
    bg_y = (final_h - bg_h) // 2
    canvas.alpha_composite(bg, (0, bg_y))

    # 绘制玩家信息条（复用便笺 mr 的渲染）
    _draw_player_info(
        canvas, 0, ev, nickname, uid,
        int(level) if str(level).isdigit() else 0,
        int(login_days) if str(login_days).isdigit() else 0,
        rating, avatar_img,
    )

    # 绘制每个卡池
    current_y = player_h
    for pool_img in pool_imgs:
        canvas.alpha_composite(pool_img, (0, current_y))
        current_y += pool_img.height + 20

    # 裁剪到实际内容高度
    canvas = canvas.crop((0, 0, W, current_y + 20))

    return await convert_img(canvas)
