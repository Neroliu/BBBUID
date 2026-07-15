"""崩坏3公告图片渲染 (分类列表 + 详情)"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

import httpx
from PIL import Image, ImageDraw, ImageOps

from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

from .notice_api import BBBNoticePost, BBBNoticeDetail, BBBNoticeType

# ── 常量 ──
CANVAS_W = 1080
BG_COLOR = (249, 246, 242)
TEXT_COLOR = (51, 51, 51)
MUTED_COLOR = (140, 140, 140)
ACCENT_COLOR = (9, 109, 217)
DIVIDER_COLOR = (220, 220, 220)
PADDING = 40

SECTION_COLORS = {
    BBBNoticeType.ANNOUNCE: (220, 50, 50),
    BBBNoticeType.ACTIVITY: (9, 109, 217),
    BBBNoticeType.INFO: (50, 170, 130),
}

_font_22 = core_font(22)
_font_24 = core_font(24)
_font_26 = core_font(26)
_font_30 = core_font(30)
_font_36 = core_font(36)

THUMB_W = 180
THUMB_H = 100


# ════════════════════════════════════════════
#  工具函数
# ════════════════════════════════════════════


async def _download_img(url: str) -> Image.Image | None:
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def _wrap_text(text: str, font, max_w: int) -> List[Tuple[str, int]]:
    lines: List[Tuple[str, int]] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append(("", 0))
            continue
        current = ""
        for ch in paragraph:
            test = current + ch
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] > max_w:
                lines.append((current, bbox[3] - bbox[1]))
                current = ch
            else:
                current = test
        if current:
            bbox = font.getbbox(current)
            lines.append((current, bbox[3] - bbox[1]))
    return lines


def _format_time(created_at: int) -> str:
    if created_at <= 0:
        return ""
    return datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")


# ════════════════════════════════════════════
#  分类列表渲染
# ════════════════════════════════════════════


async def render_notice_list_card(
    columns: Dict[BBBNoticeType, List[BBBNoticePost]],
) -> bytes:
    """渲染分类公告列表图。"""
    # 预下载缩略图
    thumbs: Dict[int, Image.Image] = {}
    for posts in columns.values():
        for p in posts:
            if p.cover_url and p.post_id not in thumbs:
                img = await _download_img(p.cover_url)
                if img:
                    thumbs[p.post_id] = ImageOps.fit(
                        img.convert("RGB"),
                        (THUMB_W, THUMB_H),
                        method=Image.Resampling.LANCZOS,
                    )

    # 计算总高度
    title_h = 70
    total_h = PADDING + title_h + 20
    for ntype in BBBNoticeType:
        posts = columns.get(ntype, [])
        if posts:
            total_h += 40 + len(posts) * (THUMB_H + 20)
    total_h += PADDING

    canvas = Image.new("RGB", (CANVAS_W, total_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    y = PADDING
    draw.text((PADDING, y), "崩坏3 最新公告", fill=ACCENT_COLOR, font=_font_36)
    y += title_h

    for ntype in BBBNoticeType:
        posts = columns.get(ntype, [])
        if not posts:
            continue
        color = SECTION_COLORS[ntype]

        # 分类标题 + 分割线
        draw.rectangle((PADDING, y, PADDING + 4, y + 24), fill=color)
        draw.text((PADDING + 14, y - 2), ntype.label, fill=color, font=_font_26)
        y += 34
        draw.line((PADDING, y, CANVAS_W - PADDING, y), fill=DIVIDER_COLOR, width=1)
        y += 6

        for post in posts:
            item_top = y

            # 缩略图
            thumb = thumbs.get(post.post_id)
            if thumb:
                canvas.paste(thumb, (PADDING, item_top))
            else:
                draw.rectangle(
                    (PADDING, item_top, PADDING + THUMB_W, item_top + THUMB_H),
                    fill=(230, 230, 230),
                )
                draw.text(
                    (PADDING + 60, item_top + 38),
                    "无图", fill=MUTED_COLOR, font=_font_22,
                )

            # 标题
            text_left = PADDING + THUMB_W + 20
            text_right = CANVAS_W - PADDING
            text_w = text_right - text_left

            subject_lines = _wrap_text(post.subject, _font_24, text_w)
            text_y = item_top + 4
            for line, lh in subject_lines[:2]:
                draw.text((text_left, text_y), line, fill=TEXT_COLOR, font=_font_24)
                text_y += lh + 4

            # 时间
            time_str = _format_time(post.created_at)
            if time_str:
                draw.text(
                    (text_left, item_top + THUMB_H - 24),
                    time_str, fill=MUTED_COLOR, font=_font_22,
                )

            # ID 标签
            id_str = str(post.post_id)
            id_bbox = _font_22.getbbox(id_str)
            id_w = id_bbox[2] - id_bbox[0] + 16
            id_x = text_right - id_w
            draw.rounded_rectangle(
                (id_x, item_top + THUMB_H - 28, text_right, item_top + THUMB_H),
                radius=4, fill=(235, 235, 235),
            )
            draw.text(
                (id_x + 8, item_top + THUMB_H - 26),
                id_str, fill=MUTED_COLOR, font=_font_22,
            )

            y += THUMB_H + 20

    return await convert_img(canvas)


# ════════════════════════════════════════════
#  详情渲染 (基于 structured_content / Quill Delta)
# ════════════════════════════════════════════


async def render_notice_detail(detail: BBBNoticeDetail) -> bytes:
    """将公告详情渲染为图片。

    content_blocks 格式:
    - ("text", str, attrs_dict)
    - ("image", url_str)
    """
    blocks = detail.content_blocks

    # 下载所有图片
    images: Dict[str, Image.Image] = {}
    for block in blocks:
        if block[0] == "image":
            url = block[1]
            if url not in images:
                img = await _download_img(url)
                if img:
                    if img.width > CANVAS_W:
                        ratio = CANVAS_W / img.width
                        img = img.resize(
                            (CANVAS_W, int(img.height * ratio)),
                            Image.Resampling.LANCZOS,
                        )
                    images[url] = img

    # 计算总高度
    total_h = PADDING

    # 标题
    title_lines = _wrap_text(detail.subject, _font_30, CANVAS_W - PADDING * 2)
    for _, h in title_lines:
        total_h += h + 6
    total_h += 10

    # 内容块
    for block in blocks:
        if block[0] == "image":
            img = images.get(block[1])
            total_h += (img.height + 20) if img else 0
        else:
            text = block[1]
            font = _font_26
            wrapped = _wrap_text(text, font, CANVAS_W - PADDING * 2)
            for _, h in wrapped:
                total_h += h + 6
    total_h += PADDING

    # 渲染
    canvas = Image.new("RGB", (CANVAS_W, max(total_h, 200)), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # 标题
    y = PADDING
    for line, h in title_lines:
        draw.text((PADDING, y), line, fill=ACCENT_COLOR, font=_font_30)
        y += h + 6
    y += 10

    # 内容块
    for block in blocks:
        if block[0] == "image":
            img = images.get(block[1])
            if img:
                x_offset = (CANVAS_W - img.width) // 2
                if img.mode == "RGBA":
                    canvas.paste(img, (x_offset, y), img)
                else:
                    canvas.paste(img, (x_offset, y))
                y += img.height + 20
        else:
            text, attrs = block[1], block[2] if len(block) > 2 else {}
            font = _font_26

            # 颜色: 支持 structured_content 中的 color 属性
            color = TEXT_COLOR
            raw_color = attrs.get("color", "")
            if raw_color:
                try:
                    # 解析 "#096dd9" 或 "rgb(9,109,217)" 格式
                    if raw_color.startswith("#"):
                        color = tuple(int(raw_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                    elif "109" in raw_color:
                        color = ACCENT_COLOR
                except (ValueError, IndexError):
                    pass

            # 加粗 → 用大一号字体
            if attrs.get("bold"):
                font = _font_30

            wrapped = _wrap_text(text, font, CANVAS_W - PADDING * 2)
            for line, h in wrapped:
                draw.text((PADDING, y), line, fill=color, font=font)
                y += h + 6

    canvas = ImageOps.expand(
        canvas, (PADDING, PADDING // 2, PADDING, PADDING // 2), BG_COLOR,
    )
    return await convert_img(canvas)
