"""崩坏3深渊战报图片渲染模块"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from ..utils.RESOURCE_PATH import WIKI_PATH
from .avatar_utils import get_cached_avatar, draw_decorated_avatar
from .draw_character import draw_character_card, _get_cached_star_icon, _add_rounded_corners, CHAR_RES_DIR
from .draw_note import W, _draw_player_info
from ..utils.char_data_cache import load_char_data

# --- 常量定义 ---

ABYSS_RES_DIR = Path(__file__).parent / "abyss_res"

# 大段位映射 (用于折线图Y轴 - 5档)
ABYSS_LEVEL_MAP = {
    1: "禁忌",
    2: "原罪",
    3: "苦痛",
    4: "红莲",
    5: "寂灭"
}

# 完整段位映射 (用于卡片显示)
ABYSS_LEVEL_FULL_MAP = {
    1: "禁忌",
    2: "原罪Ⅰ", 3: "原罪Ⅱ", 4: "原罪Ⅲ",
    5: "苦痛Ⅰ", 6: "苦痛Ⅱ", 7: "苦痛Ⅲ",
    8: "红莲", 9: "寂灭"
}

# API返回的level -> 折线图Y轴位置 (1-5对应5档)
LEVEL_TO_CHART_Y = {
    1: 1, 2: 1,      # 禁忌、原罪 -> 五档(最下)
    3: 2, 4: 2,      # 原罪Ⅱ/Ⅲ -> 四档
    5: 3, 6: 3, 7: 3, # 苦痛 -> 三档
    8: 4,             # 红莲 -> 二档
    9: 5              # 寂灭 -> 一档(最上)
}

# 折线图区域参数
LINE_BG_W = 1400
LINE_BG_H = 480

# 横纹Y坐标 (基于第一个点 y=428 为五档/禁忌，间距81px)
CHART_Y_POSITIONS = {
    5: 428,  # 五档(禁忌) - 最下面
    4: 347,  # 四档(原罪)
    3: 266,  # 三档(苦痛)
    2: 185,  # 二档(红莲)
    1: 104   # 一档(寂灭) - 最上面
}

# X轴: 8个点，第一个点 x=225，间隔151px
CHART_X_START = 225
CHART_X_SPACING = 151

# 颜色定义
TEXT_WHITE = (255, 255, 255, 255)
TEXT_DIM = (180, 180, 180, 255)
ACCENT_BLUE = (100, 150, 255, 255)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_italic_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

SKEW = 0.25  # italic slant factor


def _load_res(filename: str) -> Optional[Image.Image]:
    """加载资源文件"""
    path = ABYSS_RES_DIR / filename
    if path.exists():
        return Image.open(path).convert("RGBA")
    return None


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


async def _draw_elf_card(
    canvas: Image.Image,
    x: int,
    y: int,
    elf: Dict,
    scale: float = 0.65,
) -> None:
    """绘制协同者卡片 (65%角色卡片大小，同样式)"""
    from io import BytesIO
    import httpx

    card_w = int(182 * scale)
    card_h = int(276 * scale)

    # 卡片背景
    bg_path = CHAR_RES_DIR / "avatar_bg.png"
    if bg_path.exists():
        card = Image.open(bg_path).convert("RGBA")
        card = card.resize((card_w, card_h), Image.Resampling.LANCZOS)
    else:
        card = Image.new("RGBA", (card_w, card_h), (28, 28, 38, 255))
    draw = ImageDraw.Draw(card)

    # 获取协同者头像 (URL → 本地缓存)
    avatar_url = elf.get("avatar", "")
    elf_icon = None
    if avatar_url:
        cache_dir = WIKI_PATH / "ELF" / "icons"
        cache_dir.mkdir(parents=True, exist_ok=True)
        elf_id = elf.get("id", "")
        cache_path = cache_dir / f"{elf_id}.png" if elf_id else None

        if cache_path and cache_path.exists():
            try:
                elf_icon = Image.open(cache_path).convert("RGBA")
            except Exception:
                pass

        if elf_icon is None:
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    resp = await client.get(avatar_url, timeout=15)
                    if resp.status_code == 200:
                        elf_icon = Image.open(BytesIO(resp.content)).convert("RGBA")
                        if cache_path:
                            elf_icon.save(str(cache_path), "PNG")
            except Exception:
                pass

    if elf_icon is None:
        elf_icon = Image.new("RGBA", (100, 100), (100, 100, 100, 255))

    # 缩放头像
    icon_width = card_w - int(23 * scale)
    icon_height = elf_icon.height * icon_width // elf_icon.width + int(4 * scale)
    elf_icon = elf_icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)
    elf_icon = _add_rounded_corners(elf_icon, 1)
    icon_x = (card_w - icon_width) // 2 + 1
    icon_y = int(17 * scale)
    card.alpha_composite(elf_icon, (icon_x, icon_y))

    # 星级图标居中
    star = elf.get("star", 0)
    star_icon = await _get_cached_star_icon(star)
    star_render_h = int(32 * scale)
    if star_icon:
        orig_w, orig_h = star_icon.size
        s = star_render_h / orig_h
        star_icon = star_icon.resize((int(orig_w * s), star_render_h), Image.Resampling.LANCZOS)
        star_x = (card_w - star_icon.width) // 2
        card.alpha_composite(star_icon, (star_x, icon_y + icon_height + 2))

    canvas.alpha_composite(card, (x, y))


def _draw_line_chart(
    canvas: Image.Image,
    reports: List[Dict],
    y_offset: int,
) -> int:
    """绘制折线图"""
    # 1. 贴折线图背景 (已包含横纹)
    line_bg = _load_res("line_bg.png")
    if line_bg:
        canvas.paste(line_bg, (0, y_offset), line_bg)

    # 2. 获取8个数据点的坐标
    points = []
    dates = []
    for i, report in enumerate(reports):
        x = CHART_X_START + i * CHART_X_SPACING
        level = LEVEL_TO_CHART_Y.get(report.get("settled_level", 7), 3)
        y = y_offset + CHART_Y_POSITIONS[level]
        points.append((x, y))

        # 日期格式 mm.dd
        ts = int(report.get("updated_time_second", 0))
        dt = datetime.fromtimestamp(ts)
        dates.append(f"{dt.month:02d}.{dt.day:02d}")

    # 3. 绘制连线 (白色线条)
    draw = ImageDraw.Draw(canvas)
    if len(points) > 1:
        draw.line(points, fill="white", width=3)

    # 4. 贴数据点 (dot.png 14x14)
    dot = _load_res("dot.png")
    if dot:
        for x, y in points:
            canvas.paste(dot, (x - 7, y - 7), dot)

    # 5. 绘制日期文字 (点下方居中)
    font = _font(20)
    x_positions = [CHART_X_START + i * CHART_X_SPACING for i in range(8)]
    for x, date in zip(x_positions, dates):
        text_bbox = draw.textbbox((0, 0), date, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_x = x - text_w // 2
        text_y = y_offset + CHART_Y_POSITIONS[5] + 7 + 12
        draw.text((text_x, text_y), date, fill="white", font=font)

    return LINE_BG_H


async def _draw_abyss_record(
    canvas: Image.Image,
    report: Dict,
    y_offset: int,
    char_levels: Dict[str, int] | None = None,
) -> int:
    """绘制单个挑战记录卡片"""
    # 1. 贴卡片背景
    bgb = _load_res("bgb.png")
    if bgb:
        canvas.paste(bgb, (0, y_offset), bgb)

    # 2. 叠加蒙版
    monster_mask = _load_res("monster_mask.png")
    if monster_mask:
        canvas.paste(monster_mask, (0, y_offset), monster_mask)

    draw = ImageDraw.Draw(canvas)

    # 3. 获取数据
    score = report.get("score", 0)
    level = report.get("settled_level", 7)
    level_name = ABYSS_LEVEL_FULL_MAP.get(level, f"未知({level})")
    rank = report.get("rank", 0)
    cup_number = report.get("cup_number", 0)
    settled_cup = report.get("settled_cup_number", 0)
    lineup = report.get("lineup", [])

    # 4. 绘制段位名称 (左上角)
    _draw_italic_text(canvas, (30, y_offset + 40), level_name, _ifont(40), TEXT_WHITE)

    # 5. 绘制积分 (右上角)
    score_text = f"积分: {score}"
    score_bbox = draw.textbbox((0, 0), score_text, font=_font(36))
    score_w = score_bbox[2] - score_bbox[0]
    _draw_italic_text(canvas, (1400 - 200 - score_w, y_offset + 40), score_text, _font(36), TEXT_WHITE)

    # 6. 绘制角色卡片 — 直接复用bbb查询的渲染代码，去掉名称
    if char_levels is None:
        char_levels = {}
    char_x = 30
    char_y = y_offset + 100
    char_gap = 10
    card_w = 182  # draw_character_card default width
    for char in lineup[:4]:
        char_name = char.get("name", "")
        if char_name:
            star = char.get("star", 0)
            level = char_levels.get(char_name, 1)
            card = await draw_character_card(char_name, star, level, show_name=False)
            canvas.alpha_composite(card, (char_x, char_y))
            char_x += card.width + char_gap

    # 6b. 绘制协同者 (ELF) — 角色右侧，间距扩大一倍，底部对齐，65%大小
    elf = report.get("elf")
    if elf:
        elf_card_w = int(182 * 0.65)
        elf_x = char_x + (card_w + char_gap)  # 间距扩大一倍
        elf_card_h = int(276 * 0.65)
        elf_y = y_offset + 100 + (276 - elf_card_h)  # 底部对齐
        await _draw_elf_card(canvas, elf_x, elf_y, elf)

    # 7. 绘制右侧信息 (排名、段位、杯数、结算时间)
    info_x = 1400 - 200
    info_y = y_offset + 100

    _draw_italic_text(canvas, (info_x, info_y), f"排名: {rank}", _font(28), TEXT_WHITE)
    info_y += 45

    _draw_italic_text(canvas, (info_x, info_y), f"段位: {level_name}", _font(28), TEXT_WHITE)
    info_y += 45

    cup_text = f"杯数: {cup_number}"
    if settled_cup != 0:
        cup_change = f"({settled_cup:+d})"
        cup_text += cup_change
    _draw_italic_text(canvas, (info_x, info_y), cup_text, _font(28), TEXT_WHITE)
    info_y += 45

    ts = int(report.get("updated_time_second", 0))
    dt = datetime.fromtimestamp(ts)
    time_text = f"结算时间: {dt.year}.{dt.month:02d}.{dt.day:02d}"
    _draw_italic_text(canvas, (info_x, info_y), time_text, _font(28), TEXT_WHITE)

    return 480  # bgb.png高度


async def draw_abyss(
    ev,
    uid: str,
    data: Dict,
    user_avatar: Image.Image | None = None,
) -> Image.Image:
    """绘制深渊战报图片"""

    reports = data.get("reports", [])
    if not reports:
        raise ValueError("无深渊战报数据")

    # 按时间降序排列，取最近4个 (显示用)
    display_reports = sorted(
        reports, key=lambda x: int(x.get("updated_time_second", 0)), reverse=True
    )[:4]

    # 折线图使用全部8个数据点 (按时间升序)
    all_reports = sorted(
        reports, key=lambda x: int(x.get("updated_time_second", 0))
    )

    # 获取玩家信息 (从index接口获取)
    from ..bbb_api import bh3_api
    index_data = await bh3_api.get_bbb_index(uid)
    if isinstance(index_data, int):
        index_data = {}

    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    preference = index_data.get("preference", {})

    nickname = role.get("nickname", "未知")
    level = role.get("level", 0)
    active_days = stats.get("active_day_number", 0)
    rating = preference.get("comprehensive_rating", "C")

    # 从角色缓存查等级 (bbb查询路径)
    char_levels: Dict[str, int] = {}
    char_data = load_char_data(uid)
    if char_data:
        for item in char_data:
            avatar = item.get("character", {}).get("avatar", {})
            name = avatar.get("name")
            if name:
                char_levels[name] = avatar.get("level", 1)

    # 计算画布高度 — 基于实际内容，不额外加底部padding
    # y=40 info(192) + gap(18) + chart(480) + gap(20) + cards(4*500) + gap(20) + footer(62)
    canvas_h = 40 + 192 + 18 + 480 + 20 + (480 + 20) * 4 + 20 + 62  # 2792

    canvas = Image.new("RGBA", (W, canvas_h), (0, 0, 0, 255))

    # 1. 贴画布背景
    bg = _load_res("bg.jpg")
    if bg:
        canvas.paste(bg, (0, 0))

    # 2. 绘制玩家信息条 — 直接复用draw_note的代码
    y_pos = 40
    avatar_img = None
    if user_avatar is not None:
        try:
            avatar_img = draw_decorated_avatar(user_avatar, 179)
        except Exception:
            pass
    _draw_player_info(
        canvas, y_pos, None, nickname, uid, level, active_days, rating, avatar_img
    )
    y_pos += 192 + 18  # info bar height + gap to chart

    # 3. 绘制折线图
    chart_h = _draw_line_chart(canvas, all_reports, y_pos)
    y_pos += chart_h + 20

    # 4. 绘制挑战记录卡片
    for report in display_reports:
        record_h = await _draw_abyss_record(canvas, report, y_pos, char_levels)
        y_pos += record_h + 20

    # 5. 绘制footer
    y_pos += 20
    footer = Image.open(Path(__file__).parent / "footer.png").convert("RGBA")
    footer_x = (W - footer.width) // 2
    canvas.paste(footer, (footer_x, y_pos), footer)

    # 6. 裁剪到footer底部 — 不加额外padding，避免黑边
    final_h = y_pos + footer.height
    canvas = canvas.crop((0, 0, W, final_h))

    return await convert_img(canvas)
