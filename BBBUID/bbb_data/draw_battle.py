"""崩坏3战场战报图片渲染模块"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from ..utils.RESOURCE_PATH import WIKI_PATH
from .avatar_utils import get_cached_avatar, draw_decorated_avatar
from .draw_character import draw_character_card, _add_rounded_corners, CHAR_RES_DIR, STAR_ICON_RES_DIR
from .draw_note import W, _draw_player_info
from ..utils.char_data_cache import load_char_data

# --- 常量定义 ---

BATTLE_RES_DIR = Path(__file__).parent / "battle_res"

CST = timezone(timedelta(hours=8))

# 段位映射 (area字段)
AREA_MAP = {
    4: "终极组",
}
DEFAULT_AREA_NAME = "终极组"

# 折线图区域参数
LINE_BG_W = 1400
LINE_BG_H = 480

# 7档Y坐标 (从下到上, 间隔54px, 基准y=428为七档)
CHART_Y_POSITIONS = {
    7: 428,  # 七档 - 最下面
    6: 374,  # 六档
    5: 320,  # 五档
    4: 266,  # 四档
    3: 212,  # 三档
    2: 158,  # 二档
    1: 104,  # 一档 - 最上面
}

# X轴: 8个点, 第一个点 x=225, 间隔151px
CHART_X_START = 225
CHART_X_SPACING = 151

# 颜色定义
TEXT_WHITE = (255, 255, 255, 255)
TEXT_DIM = (222, 222, 221, 255)
ACCENT_GOLD = (254, 231, 114, 255)

SKEW = 0.25  # italic slant factor

# 预计算avatar_bg可见内容底部
_CHAR_BG = Image.open(CHAR_RES_DIR / "avatar_bg.png").convert("RGBA")
_CHAR_VIS_BOTTOM = next(
    r for r in range(_CHAR_BG.height - 1, -1, -1)
    if any(_CHAR_BG.getpixel((c, r))[3] > 0 for c in range(0, _CHAR_BG.width, 10))
)
_ELF_BG = _CHAR_BG.resize((round(182 * 0.65), round(276 * 0.65)), Image.Resampling.LANCZOS)
_ELF_VIS_BOTTOM = next(
    r for r in range(_ELF_BG.height - 1, -1, -1)
    if any(_ELF_BG.getpixel((c, r))[3] > 0 for c in range(0, _ELF_BG.width, 10))
)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_italic_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

# 协同者星级图标映射
ELF_STAR_TO_ICON = {
    1: "StarElf_S.png",
    2: "StarElf_SS.png",
    3: "StarElf_SSS.png",
}


def _load_res(filename: str) -> Optional[Image.Image]:
    """加载battle_res资源文件"""
    path = BATTLE_RES_DIR / filename
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

    card_w = round(182 * scale)
    card_h = round(276 * scale)

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

    # 星级渲染
    star = elf.get("star", 0)
    is_collaborator = elf.get("is_collaborator", False)
    star_y = icon_y + icon_height + 12

    if is_collaborator:
        star_icon_name = ELF_STAR_TO_ICON.get(star, "StarElf_S.png")
        star_path = STAR_ICON_RES_DIR / star_icon_name
        star_render_h = int(40 * scale)
        if star_path.exists():
            try:
                star_icon = Image.open(star_path).convert("RGBA")
                orig_w, orig_h = star_icon.size
                s = star_render_h / orig_h
                star_icon = star_icon.resize((int(orig_w * s), star_render_h), Image.Resampling.LANCZOS)
                star_x = (card_w - star_icon.width) // 2
                card.alpha_composite(star_icon, (star_x, star_y))
            except Exception:
                pass
    else:
        if star <= 1:
            star_count = 1
        elif star <= 3:
            star_count = 2
        elif star <= 6:
            star_count = 3
        else:
            star_count = 4
        star_text = "★" * star_count
        star_font = _font(int(20 * scale))
        star_text_w = draw.textlength(star_text, font=star_font)
        star_x = (card_w - int(star_text_w)) // 2
        draw.text((star_x, star_y), star_text, fill=(255, 200, 60, 255), font=star_font)

    canvas.alpha_composite(card, (x, y))


def _draw_line_chart(
    canvas: Image.Image,
    reports: List[Dict],
    y_offset: int,
) -> int:
    """绘制折线图 (7档) — 与深渊折线图对齐"""
    # 1. 贴折线图背景
    line_bg = _load_res("bg.png")
    if line_bg:
        canvas.paste(line_bg, (0, y_offset), line_bg)

    # 2. 获取8个数据点的坐标 (整体上移34px, 与深渊对齐)
    points = []
    dates = []
    for i, report in enumerate(reports):
        x = CHART_X_START + i * CHART_X_SPACING
        rank = report.get("rank", 4)
        rank = max(1, min(7, rank))
        y = y_offset + CHART_Y_POSITIONS[rank] - 34
        points.append((x, y))

        ts = int(report.get("time_second", 0))
        dt = datetime.fromtimestamp(ts, tz=CST)
        dates.append(f"{dt.month:02d}.{dt.day:02d}")

    # 3. 绘制连线
    draw = ImageDraw.Draw(canvas)
    if len(points) > 1:
        draw.line(points, fill="#1AC5FF", width=4)

    # 4. 贴数据点 (dot.png 14x14)
    dot = _load_res("dot.png")
    if dot:
        for x, y in points:
            canvas.paste(dot, (x - 7, y - 7), dot)

    # 5. 绘制纵轴档位标签 (整体上移35px, 与深渊对齐)
    label_font = _font(30)
    tier_order = [(7, "七档"), (6, "六档"), (5, "五档"), (4, "四档"), (3, "三档"), (2, "二档"), (1, "一档")]
    for tier, label in tier_order:
        y_val = CHART_Y_POSITIONS[tier]
        bbox = draw.textbbox((0, 0), label, font=label_font)
        tw = bbox[2] - bbox[0]
        top, bottom = bbox[1], bbox[3]
        lx = 142 - tw
        ly = y_offset + y_val - 35 - (top + bottom) // 2
        draw.text((lx, ly), label, fill="white", font=label_font)

    # 6. 绘制日期文字 (与深渊对齐 y_offset+403)
    date_font = _font(30)
    x_positions = [CHART_X_START + i * CHART_X_SPACING for i in range(8)]
    for x, date in zip(x_positions, dates):
        text_bbox = draw.textbbox((0, 0), date, font=date_font)
        text_w = text_bbox[2] - text_bbox[0]
        text_x = x - text_w // 2
        draw.text((text_x, y_offset + 403), date, fill="white", font=date_font)

    return LINE_BG_H


async def _draw_battle_record(
    canvas: Image.Image,
    battle_info: Dict,
    y_offset: int,
    char_levels: Dict[str, int],
    is_first: bool = False,
    report_score: int = 0,
    report_rank: int = 0,
    area_name: str = "",
    ranking_pct: str = "0",
    time_second: str = "0",
) -> int:
    """绘制单个Boss挑战记录卡片 (与深渊 _draw_abyss_record 对齐)"""
    from io import BytesIO
    import httpx

    draw = ImageDraw.Draw(canvas)

    # Boss头像 (372%, 43%透明度)
    boss = battle_info.get("boss", {})
    boss_avatar_url = boss.get("avatar", "")
    boss_id = boss.get("id", "")
    boss_name = boss.get("name", "")
    if boss_avatar_url and boss_id:
        boss_cache_dir = WIKI_PATH / "Boss" / "icons"
        boss_cache_dir.mkdir(parents=True, exist_ok=True)
        boss_cache_path = boss_cache_dir / f"{boss_id}.png"
        boss_icon = None
        if boss_cache_path.exists():
            try:
                boss_icon = Image.open(boss_cache_path).convert("RGBA")
            except Exception:
                pass
        if boss_icon is None:
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    resp = await client.get(boss_avatar_url, timeout=15)
                    if resp.status_code == 200:
                        boss_icon = Image.open(BytesIO(resp.content)).convert("RGBA")
                        boss_icon.save(str(boss_cache_path), "PNG")
            except Exception:
                pass
        if boss_icon is not None:
            new_w = round(boss_icon.width * 3.72)
            new_h = round(boss_icon.height * 3.72)
            boss_icon = boss_icon.resize((new_w, new_h), Image.Resampling.LANCZOS)
            r, g, b, a = boss_icon.split()
            a = a.point(lambda x: int(x * 0.43))
            boss_icon.putalpha(a)
            canvas.paste(boss_icon, (390, y_offset + 43), boss_icon)

    # --- 标题区 (仅第一张卡片) ---
    if is_first and area_name:
        title_font = _ifont(55)
        title_bbox = draw.textbbox((0, 0), area_name, font=title_font)
        title_top, title_bottom = title_bbox[1], title_bbox[3]
        title_th = title_bottom - title_top
        title_draw_y = y_offset + 111 - title_th // 2
        _draw_italic_text(canvas, (134, title_draw_y), area_name, title_font, ACCENT_GOLD)

        # 总得分/档位 (段位右侧+15px, 底部对齐)
        score_text = f"总得分 {report_score} / {report_rank}档"
        score_font = _font(30)
        title_visual_bottom = title_draw_y + title_th
        title_right = 134 + (title_bbox[2] - title_bbox[0])
        score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
        score_h = score_bbox[3] - score_bbox[1]
        score_y = title_visual_bottom - score_h
        draw.text((title_right + 15, score_y), score_text, font=score_font, fill=TEXT_DIM)

    # --- 积分badge (每张卡片, x=1018) ---
    boss_score = battle_info.get("score", 0)
    score_badge = _load_res("score_badge.png")
    if score_badge:
        canvas.paste(score_badge, (1018, y_offset + 75), score_badge)
        badge_w, badge_h = score_badge.size
        score_text = str(boss_score)
        score_font = _font(48)
        score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
        score_top, score_bottom = score_bbox[1], score_bbox[3]
        score_y = y_offset + 75 + badge_h // 2 - (score_top + score_bottom) // 2
        draw.text((1018 + 95, score_y), score_text, font=score_font, fill=TEXT_WHITE)

    # --- 角色卡片 ---
    lineup = battle_info.get("lineup", [])
    char_x = 134
    char_y = y_offset + 165
    char_gap = 0
    for char in lineup[:3]:
        char_name = char.get("name", "")
        if char_name:
            star = char.get("star", 0)
            lvl = char_levels.get(char_name, 1)
            card = await draw_character_card(char_name, star, lvl, show_name=False, show_level=False)
            canvas.alpha_composite(card, (char_x, char_y))
            char_x += card.width + char_gap

    # ELF — 最后一个角色右侧15px
    elf = battle_info.get("elf")
    if elf:
        last_card_right = char_x - char_gap
        elf_x = last_card_right + 15
        elf_y = char_y + _CHAR_VIS_BOTTOM - _ELF_VIS_BOTTOM
        await _draw_elf_card(canvas, elf_x, elf_y, elf)

    # --- 右侧信息 (x=1018, 每张卡片都有, 与深渊对齐) ---
    info_x = 1018
    info_font = _font(30)
    rank_num_font = _ifont(36)
    time_font = _font(24)
    line_h = 30
    line_gap = 10
    total_h = line_h * 3 + line_gap * 2  # 3行: 排名百分比 + boss名 + 结算时间
    info_y = char_y + _CHAR_VIS_BOTTOM - total_h

    # 排名百分比 (与深渊"排名: 数字"同格式)
    rank_label = "排名: "
    draw.text((info_x, info_y), rank_label, font=info_font, fill=TEXT_WHITE)
    rank_label_w = draw.textlength(rank_label, font=info_font)
    pct_num = f"{ranking_pct}%"
    label_th = draw.textbbox((0, 0), rank_label, font=info_font)[3]
    num_th = draw.textbbox((0, 0), pct_num, font=rank_num_font)[3]
    num_y = info_y + label_th - num_th - int(num_th * SKEW) + int(label_th * SKEW)
    _draw_italic_text(canvas, (int(info_x + rank_label_w), num_y), pct_num, rank_num_font, ACCENT_GOLD)
    info_y += line_h + line_gap

    # Boss名称 (24px #DEDEDE, 与结算时间同字号)
    if boss_name:
        draw.text((info_x, info_y), boss_name, font=time_font, fill=TEXT_DIM)
    info_y += line_h + line_gap

    # 结算时间 (24px #DEDEDE)
    ts = int(time_second)
    dt = datetime.fromtimestamp(ts, tz=CST)
    time_text = f"结算时间: {dt.year}.{dt.month:02d}.{dt.day:02d}"
    draw.text((info_x, info_y), time_text, font=time_font, fill=TEXT_DIM)

    return 480  # 每张卡片高度


async def draw_battle(
    ev,
    uid: str,
    data: Dict,
    user_avatar: Image.Image | None = None,
) -> Image.Image:
    """绘制战场战报图片"""
    reports = data.get("reports", [])
    if not reports:
        raise ValueError("无战场战报数据")

    # 折线图使用全部8个数据点 (按时间升序)
    all_reports = sorted(
        reports, key=lambda x: int(x.get("time_second", 0))
    )

    # 取最新一条report用于挑战记录
    latest_report = sorted(
        reports, key=lambda x: int(x.get("time_second", 0)), reverse=True
    )[0]

    battle_infos = latest_report.get("battle_infos", [])
    if not battle_infos:
        raise ValueError("无战场挑战记录")

    report_score = latest_report.get("score", 0)
    report_rank = latest_report.get("rank", 0)
    ranking_pct = latest_report.get("ranking_percentage", "0")
    area = latest_report.get("area", 0)
    area_name = AREA_MAP.get(area, DEFAULT_AREA_NAME)
    time_second = latest_report.get("time_second", "0")

    # 获取玩家信息
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

    # 角色等级缓存
    char_levels: Dict[str, int] = {}
    char_data = load_char_data(uid)
    if char_data:
        for item in char_data:
            avatar = item.get("character", {}).get("avatar", {})
            name = avatar.get("name")
            if name:
                char_levels[name] = avatar.get("level", 1)

    # 画布高度: info(104+192+44) + chart(480) + cards(3*480) + footer(62) - 12
    canvas_h = 104 + 192 + 44 + 480 + 480 * 3 + 62 - 12

    canvas = Image.new("RGBA", (W, canvas_h), (0, 0, 0, 255))

    # 1. 平铺背景
    bg = Image.open(BATTLE_RES_DIR / "bg.jpg").convert("RGB")
    bg_w, bg_h = bg.size
    for ty in range(0, canvas_h, bg_h):
        canvas.paste(bg, (0, ty))

    # 2. 玩家信息条
    y_pos = 104
    avatar_img = None
    if user_avatar is not None:
        try:
            avatar_img = draw_decorated_avatar(user_avatar, 179)
        except Exception:
            pass
    _draw_player_info(
        canvas, y_pos, None, nickname, uid, level, active_days, rating, avatar_img
    )
    y_pos += 192 + 44

    # 3. 折线图
    chart_h = _draw_line_chart(canvas, all_reports, y_pos)
    y_pos += chart_h

    # 4. 贴bgc.png作为挑战记录区整体背景 (上移10px与折线图重叠)
    bgc = _load_res("bgc.png")
    if bgc:
        canvas.paste(bgc, (0, y_pos - 10), bgc)

    # 5. 绘制3个Boss挑战记录卡片 (与深渊对齐)
    for i, bi in enumerate(battle_infos[:3]):
        await _draw_battle_record(
            canvas, bi, y_pos, char_levels,
            is_first=(i == 0),
            report_score=report_score,
            report_rank=report_rank,
            area_name=area_name,
            ranking_pct=ranking_pct,
            time_second=time_second,
        )
        y_pos += 480

    # 6. Footer (上移12px, 与深渊对齐)
    footer = Image.open(Path(__file__).parent / "footer.png").convert("RGBA")
    footer_x = (W - footer.width) // 2
    canvas.paste(footer, (footer_x, y_pos - 12), footer)

    # 7. 裁剪到footer底部
    final_h = y_pos - 12 + footer.height
    canvas = canvas.crop((0, 0, W, final_h))

    return await convert_img(canvas)
