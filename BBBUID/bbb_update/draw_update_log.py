import subprocess
import unicodedata
from pathlib import Path
from typing import List, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.fonts.fonts import core_font
from gsuid_core.utils.image.convert import convert_img


# --- Constants ---
CARD_W = 950
BG_COLOR = (28, 28, 38)
PANEL_BG = (42, 42, 58)
TEXT_WHITE = (240, 240, 245)
TEXT_GRAY = (180, 180, 195)
TEXT_DIM = (130, 130, 148)
ACCENT_BLUE = (80, 160, 255)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = core_font(size)
    return _font_cache[size]


def _get_git_logs() -> List[str]:
    try:
        repo_root = Path(__file__).parents[2]
        process = subprocess.Popen(
            ["git", "log", "--pretty=format:%s", "-40"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logger.warning(f"Git log failed: {stderr.decode('utf-8', errors='ignore')}")
            return []
        commits = stdout.decode("utf-8", errors="ignore").split("\n")

        # Prefer commits with emoji prefixes; fallback to all commits
        filtered_commits = []
        fallback_commits = []
        for commit in commits:
            if not commit:
                continue
            emojis, _ = _extract_leading_emojis(commit)
            if emojis:
                filtered_commits.append(commit)
                if len(filtered_commits) >= 18:
                    break
            else:
                fallback_commits.append(commit)

        if filtered_commits:
            return filtered_commits
        return fallback_commits[:18]
    except Exception as e:
        logger.warning(f"Get logs failed: {e}")
        return []


def _extract_leading_emojis(message: str) -> Tuple[List[str], str]:
    emojis = []
    i = 0
    while i < len(message):
        ch = message[i]
        if ch == "️":
            i += 1
            continue
        if unicodedata.category(ch) in ("So", "Sk"):
            emojis.append(ch)
            if i + 1 < len(message) and message[i + 1] == "️":
                i += 2
            else:
                i += 1
        else:
            break
    return emojis, message[i:].lstrip()


# Cache logs at module import time
_CACHED_LOGS = _get_git_logs()


def _draw_header(canvas: Image.Image, version: str) -> None:
    """Draw title banner with gradient-like navy header."""
    draw = ImageDraw.Draw(canvas)
    header_h = 220

    # Draw solid navy header
    draw.rectangle((0, 0, CARD_W, header_h), fill=(36, 48, 72))

    # Decorative accent line at bottom of header
    draw.rectangle((0, header_h - 4, CARD_W, header_h), fill=ACCENT_BLUE)

    # Title text
    title_font = _font(42)
    draw.text((CARD_W // 2, 90), "BBBUID 更新记录", font=title_font, fill=TEXT_WHITE, anchor="mm")

    # Version text
    version_font = _font(22)
    draw.text(
        (CARD_W // 2, 155),
        f"当前版本: v{version}",
        font=version_font,
        fill=TEXT_GRAY,
        anchor="mm",
    )

    # Decorative dot pattern
    dot_color = (60, 80, 120)
    for x in range(40, CARD_W - 40, 60):
        for y in range(40, header_h - 40, 50):
            if (x + y) % 120 == 0:
                draw.ellipse((x, y, x + 4, y + 4), fill=dot_color)


def _draw_log_entry(
    canvas: Image.Image,
    y: int,
    log_text: str,
    index: int,
) -> int:
    """Draw a single update log entry. Returns next y position."""
    draw = ImageDraw.Draw(canvas)

    emojis, text = _extract_leading_emojis(log_text)
    text = text.replace("`", "")

    # Entry background
    entry_h = 68
    entry_pad_x = 50
    entry_w = CARD_W - entry_pad_x * 2
    radius = 12

    # Alternating background colors
    bg_colors = [
        (48, 48, 66, 160),
        (42, 42, 58, 160),
    ]
    bg_fill = bg_colors[index % 2]

    # Draw rounded rectangle background
    draw.rounded_rectangle(
        (entry_pad_x, y, entry_pad_x + entry_w, y + entry_h),
        radius=radius,
        fill=bg_fill,
    )

    # Index number badge
    badge_size = 28
    badge_x = entry_pad_x + 20
    badge_y = y + (entry_h - badge_size) // 2
    draw.ellipse(
        (badge_x, badge_y, badge_x + badge_size, badge_y + badge_size),
        fill=ACCENT_BLUE,
    )
    badge_font = _font(14)
    draw.text(
        (badge_x + badge_size // 2, badge_y + badge_size // 2),
        str(index + 1),
        font=badge_font,
        fill=TEXT_WHITE,
        anchor="mm",
    )

    # Emoji + text
    text_x = badge_x + badge_size + 16
    text_font = _font(24)
    max_text_width = entry_pad_x + entry_w - 30 - text_x

    # Build display text
    display_text = text
    if emojis:
        display_text = "".join(emojis[:3]) + "  " + text

    # Truncate if too long
    if draw.textlength(display_text, font=text_font) > max_text_width:
        ellipsis = "…"
        ellipsis_w = draw.textlength(ellipsis, font=text_font)
        while display_text and draw.textlength(display_text, font=text_font) + ellipsis_w > max_text_width:
            display_text = display_text[:-1]
        display_text = display_text + ellipsis

    draw.text(
        (text_x, y + entry_h // 2),
        display_text,
        font=text_font,
        fill=TEXT_WHITE,
        anchor="lm",
    )

    return y + entry_h + 12


def _draw_footer(canvas: Image.Image, y: int) -> int:
    """Draw footer section."""
    draw = ImageDraw.Draw(canvas)

    # Try to use existing footer image
    footer_path = Path(__file__).parent.parent / "bbb_data" / "footer.png"
    if footer_path.exists():
        footer_img = Image.open(footer_path).convert("RGBA")
        fw, fh = footer_img.size
        scale = min(1.0, (CARD_W - 100) / fw)
        if scale < 1.0:
            fw = int(fw * scale)
            fh = int(fh * scale)
            footer_img = footer_img.resize((fw, fh), Image.Resampling.LANCZOS)
        fx = (CARD_W - fw) // 2
        fy = y + 20
        canvas.alpha_composite(footer_img, (fx, fy))
        return fy + fh + 20

    # Fallback text footer
    y += 30
    draw.line([(60, y), (CARD_W - 60, y)], fill=(60, 60, 75), width=2)
    y += 16
    footer_font = _font(16)
    draw.text(
        (CARD_W // 2, y),
        "BBBUID · 崩坏3插件",
        (80, 80, 95),
        footer_font,
        anchor="mt",
    )
    return y + 30


async def draw_update_log_img(version: str) -> Union[bytes, str]:
    if not _CACHED_LOGS:
        return "暂无更新记录"

    # Calculate canvas height
    header_h = 220
    entry_total_h = len(_CACHED_LOGS) * (68 + 12)
    footer_h = 100
    canvas_h = header_h + 40 + entry_total_h + footer_h

    canvas = Image.new("RGBA", (CARD_W, canvas_h), BG_COLOR)

    # Draw header
    _draw_header(canvas, version)

    # Draw log entries
    y = header_h + 30
    for i, raw_log in enumerate(_CACHED_LOGS):
        y = _draw_log_entry(canvas, y, raw_log, i)

    # Draw footer
    _draw_footer(canvas, y)

    return await convert_img(canvas)
