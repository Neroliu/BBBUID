from PIL import Image

from gsuid_core.sv import SV, get_plugin_available_prefix
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.help.utils import register_help

from .get_help import PLUGIN_ICON, get_help

sv_bbb_help = SV("崩坏3帮助")


@sv_bbb_help.on_fullmatch("帮助")
async def send_help_img(bot: Bot, ev: Event):
    logger.info("[崩坏3] [帮助] 开始生成帮助图片")
    await bot.send(await get_help())


register_help(
    "BBBUID",
    f"{get_plugin_available_prefix('BBBUID')}帮助",
    Image.open(PLUGIN_ICON) if PLUGIN_ICON.exists() else Image.new("RGB", (256, 256), "#4A90D9"),
)
