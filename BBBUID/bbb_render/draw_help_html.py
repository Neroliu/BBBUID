"""帮助 HTML 渲染版本。

入口：`draw_help_html() -> bytes`。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.utils.image.convert import convert_img

from .runner import render_html_to_bytes
from .templates import file_uri, render_template

HELP_DATA = Path(__file__).parent.parent / "bbb_help" / "help.json"
PLUGIN_ICON = Path(__file__).parent.parent.parent / "ICON.png"
ICON_PACK_PATH = Path(__file__).parent.parent / "bbb_data" / "icons"

BANNER_BG = Path(__file__).parent.parent / "bbb_data" / "banner_bg.jpg"
HELP_BG = Path(__file__).parent.parent / "bbb_data" / "bg.jpg"
FOOTER_PATH = Path(__file__).parent.parent / "bbb_data" / "footer.png"

PREFIX = get_plugin_available_prefix("BBBUID")


def _data_uri(path: Path) -> str | None:
    """Convert a local image file to a data URI (base64)."""
    if not path.exists():
        return None
    import base64

    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "image/png")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def draw_help_html() -> bytes:
    import aiofiles

    async with aiofiles.open(HELP_DATA, "rb") as f:
        raw: dict = json.loads(f.read())

    # Assign icons to commands that don't have one
    all_icons = list(ICON_PACK_PATH.glob("*.png")) if ICON_PACK_PATH.exists() else []
    random.shuffle(all_icons)
    icon_idx = 0

    groups = []
    for cag_name, cag_data in raw.items():
        commands = []
        for cmd in cag_data["data"]:
            highlight = cmd.get("highlight", 6)

            # Resolve icon
            if "icon" in cmd:
                icon_path = Path(cmd["icon"])
                icon_uri = _data_uri(icon_path) if icon_path.exists() else file_uri(icon_path)
            elif all_icons:
                icon_path = all_icons[icon_idx % len(all_icons)]
                icon_idx += 1
                icon_uri = file_uri(icon_path)
            else:
                icon_uri = None

            eg = cmd["eg"]
            # commands in "插件帮助一览" group don't need prefix
            if cag_name != "插件帮助一览":
                eg = PREFIX + eg

            commands.append({
                "name": cmd["name"],
                "eg": eg,
                "highlight": highlight,
                "icon_uri": icon_uri,
            })

        groups.append({
            "name": cag_name,
            "desc": cag_data["desc"],
            "commands": commands,
        })

    icon_uri = _data_uri(PLUGIN_ICON) if PLUGIN_ICON.exists() else None
    banner_bg_uri = file_uri(BANNER_BG) if BANNER_BG.exists() else None
    bg_uri = file_uri(HELP_BG) if HELP_BG.exists() else None
    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    from ..version import BBBUID_version
    badges = [f"v{BBBUID_version}"]

    ctx = {
        "plugin_name": "BBBUID",
        "badges": badges,
        "banner_sub_text": "崩坏3插件为你服务！",
        "icon_uri": icon_uri,
        "banner_bg_uri": banner_bg_uri,
        "bg_uri": bg_uri,
        "footer_uri": footer_uri,
        "groups": groups,
    }

    # Height estimate: banner 320 + (each group: 70 bar + 14 margin top + 30 margin bottom)
    #                  + rows of 156 + 14 gap per row
    #                  + footer ~120 + bottom padding 80
    column = 3
    total_h = 320
    for g in groups:
        total_h += 30 + 70 + 14  # margin-top + bar + margin-bottom
        rows = (len(g["commands"]) + column - 1) // column
        total_h += rows * 156 + max(0, rows - 1) * 14
    total_h += 40 + 80 + 80  # footer margin + footer + bottom padding
    total_h = max(total_h, 800)

    html = render_template("help.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=1545, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)