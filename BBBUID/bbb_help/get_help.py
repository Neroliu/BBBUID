import json
from pathlib import Path

import aiofiles
from PIL import Image

from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.help.model import PluginHelp
from gsuid_core.help.draw_new_plugin_help import get_new_help, TEXT_PATH, ICON_PATH

from ..version import BBBUID_version

HELP_DATA = Path(__file__).parent / "help.json"
PLUGIN_ICON = Path(__file__).parent.parent.parent / "ICON.png"


async def get_help_data():
    async with aiofiles.open(HELP_DATA, "rb") as file:
        return json.loads(await file.read())


async def get_help():
    return await get_new_help(
        plugin_name="BBBUID",
        plugin_info={f"v{BBBUID_version}": ""},
        plugin_icon=Image.open(PLUGIN_ICON) if PLUGIN_ICON.exists() else Image.new("RGB", (256, 256), "#4A90D9"),
        plugin_help=await get_help_data(),
        plugin_prefix=get_plugin_available_prefix("BBBUID"),
        help_mode="dark",
        banner_bg=Image.open(TEXT_PATH / "banner_bg_dark.jpg"),
        banner_sub_text="崩坏3插件为你服务！",
        help_bg=Image.open(TEXT_PATH / "bg_dark.jpg"),
        cag_bg=Image.open(TEXT_PATH / "cag_bg_dark.png"),
        item_bg=Image.open(TEXT_PATH / "item_bg_dark.png"),
        icon_path=ICON_PATH,
        footer=Image.open(TEXT_PATH / "footer_dark.png"),
        enable_cache=True,
    )
