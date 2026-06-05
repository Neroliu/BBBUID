import json
import random
from pathlib import Path

import aiofiles
from PIL import Image

from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.help.model import PluginHelp

from .draw_help import get_new_help, TEXT_PATH, ICON_PATH

from ..version import BBBUID_version

HELP_DATA = Path(__file__).parent / "help.json"
PLUGIN_ICON = Path(__file__).parent.parent.parent / "ICON.png"
# 图标资源包路径（/app/napcat/config/icons.zip 解压到项目 bbb_data/icons/）
# 新增命令时从此目录随机取图标，确保不重复即可
ICON_PACK_PATH = Path(__file__).parent.parent / "bbb_data" / "icons"


async def get_help_data():
    async with aiofiles.open(HELP_DATA, "rb") as file:
        return json.loads(await file.read())


def _assign_icons(plugin_help: dict) -> dict:
    """为没有 icon 字段的命令从图标资源包中随机分配不重复的图标。"""
    if ICON_PACK_PATH.exists():
        all_icons = list(ICON_PACK_PATH.glob("*.png"))
    else:
        all_icons = []

    random.shuffle(all_icons)
    icon_idx = 0

    for cag in plugin_help:
        for cmd in plugin_help[cag]["data"]:
            if "icon" not in cmd and all_icons:
                cmd["icon"] = str(all_icons[icon_idx % len(all_icons)])
                icon_idx += 1

    return plugin_help


async def get_help():
    plugin_help = await get_help_data()
    _assign_icons(plugin_help)
    return await get_new_help(
        plugin_name="BBBUID",
        plugin_info={f"v{BBBUID_version}": ""},
        plugin_icon=Image.open(PLUGIN_ICON) if PLUGIN_ICON.exists() else Image.new("RGB", (256, 256), "#4A90D9"),
        plugin_help=plugin_help,
        plugin_prefix=get_plugin_available_prefix("BBBUID"),
        help_mode="dark",
        banner_bg=Image.open(Path(__file__).parent.parent / "bbb_data" / "banner_bg.jpg"),
        banner_sub_text="崩坏3插件为你服务！",
        help_bg=Image.open(Path(__file__).parent.parent / "bbb_data" / "bg.jpg"),
        cag_bg=Image.open(Path(__file__).parent.parent / "bbb_data" / "cag_bg.png"),
        item_bg=Image.open(Path(__file__).parent.parent / "bbb_data" / "item.png"),
        icon_path=Path(__file__).parent.parent / "bbb_data" / "icons",
        footer=Image.open(Path(__file__).parent.parent / "bbb_data" / "footer.png"),
        enable_cache=True,
    )
