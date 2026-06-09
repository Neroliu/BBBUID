"""更新日志 HTML 渲染版本。

入口：`draw_update_log_html(version) -> bytes`。
"""
from __future__ import annotations

from pathlib import Path

from gsuid_core.utils.image.convert import convert_img

from .runner import render_html_to_bytes
from .templates import file_uri, render_template

CARD_W = 950
FOOTER_PATH = Path(__file__).parent.parent / "bbb_data" / "footer.png"


async def draw_update_log_html(version: str) -> bytes:
    # Reuse the same git log extraction as the PIL version
    from ..bbb_update.draw_update_log import _CACHED_LOGS

    entries = []
    for i, raw in enumerate(_CACHED_LOGS):
        text = raw.replace("`", "")
        entries.append({"index": str(i + 1), "text": text})

    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "version": version,
        "entries": entries,
        "footer_uri": footer_uri,
    }

    total_entries = len(entries)
    # Header(220) + padding(30) + entries(len*~68) + footer(~100)
    content_h = 220 + 30 + total_entries * 76 + 100

    html = render_template("update_log.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=content_h, device_scale_factor=2)
    return await convert_img(png_bytes)