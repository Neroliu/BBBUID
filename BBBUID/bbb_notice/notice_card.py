"""崩坏3公告图片渲染"""
from __future__ import annotations

from io import BytesIO
from typing import List, Tuple

import httpx
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageOps

from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img

CANVAS_W = 1080
BG_COLOR = (249, 246, 242)
TEXT_COLOR = (51, 51, 51)
ACCENT_COLOR = (9, 109, 217)
PADDING = 40

_font_26 = core_font(26)
_font_30 = core_font(30)


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
    """将文本按宽度分行，返回 [(line, height), ...]"""
    lines = []
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


def _get_content_elements(content_html: str) -> List[tuple]:
    """解析HTML内容，返回元素列表 [(type, ...), ...]"""
    soup = BeautifulSoup(content_html, "lxml")

    # 找到实际内容容器 (body 或 html 的子元素)
    body = soup.find("body")
    root = body if body else soup

    elements = []

    def _process_tag(tag: Tag):
        if tag.name == "img":
            src = tag.get("src", "")
            if src:
                elements.append(("img", src))
        elif tag.name in ("p", "strong"):
            text = tag.get_text(strip=True)
            if not text:
                return
            is_bold = tag.name == "strong" or tag.find("strong")
            style = str(tag.get("style", ""))
            color = ACCENT_COLOR if "9, 109, 217" in style else TEXT_COLOR
            font = _font_30 if is_bold else _font_26
            elements.append(("text", text, font, color))
        elif tag.name == "div":
            # div 内可能有图片或嵌套内容
            imgs = tag.find_all("img")
            if imgs:
                for img_tag in imgs:
                    src = img_tag.get("src", "")
                    if src:
                        elements.append(("img", src))
            else:
                text = tag.get_text(strip=True)
                if text:
                    elements.append(("text", text, _font_26, TEXT_COLOR))

    for child in root.children:
        if isinstance(child, Tag):
            _process_tag(child)

    return elements


async def render_notice_card(title: str, content_html: str) -> bytes:
    """将公告HTML渲染为图片"""
    elements = _get_content_elements(content_html)

    # 下载所有图片
    images: dict[str, Image.Image] = {}
    for elem in elements:
        if elem[0] == "img":
            src = elem[1]
            if src not in images:
                img = await _download_img(src)
                if img:
                    if img.width > CANVAS_W:
                        ratio = CANVAS_W / img.width
                        img = img.resize(
                            (CANVAS_W, int(img.height * ratio)),
                            Image.Resampling.LANCZOS,
                        )
                    images[src] = img

    # 计算总高度
    total_h = PADDING  # top
    # title
    title_lines = _wrap_text(title, _font_30, CANVAS_W - PADDING * 2)
    for _, h in title_lines:
        total_h += h + 6
    total_h += 10

    for elem in elements:
        if elem[0] == "img":
            img = images.get(elem[1])
            total_h += (img.height + 20) if img else 0
        else:
            text, font, color = elem[1], elem[2], elem[3]
            wrapped = _wrap_text(text, font, CANVAS_W - PADDING * 2)
            for _, h in wrapped:
                total_h += h + 6
    total_h += PADDING  # bottom

    # 渲染
    canvas = Image.new("RGB", (CANVAS_W, max(total_h, 200)), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # 标题
    y = PADDING
    for line, h in title_lines:
        draw.text((PADDING, y), line, fill=ACCENT_COLOR, font=_font_30)
        y += h + 6
    y += 10

    # 内容
    for elem in elements:
        if elem[0] == "img":
            img = images.get(elem[1])
            if img:
                if img.mode == "RGBA":
                    canvas.paste(img, (0, y), img)
                else:
                    canvas.paste(img, (0, y))
                y += img.height + 20
        else:
            text, font, color = elem[1], elem[2], elem[3]
            wrapped = _wrap_text(text, font, CANVAS_W - PADDING * 2)
            for line, h in wrapped:
                draw.text((PADDING, y), line, fill=color, font=font)
                y += h + 6

    # 加 padding 边距
    pad = (PADDING, PADDING // 2, PADDING, PADDING // 2)
    canvas = ImageOps.expand(canvas, pad, BG_COLOR)

    return await convert_img(canvas)
