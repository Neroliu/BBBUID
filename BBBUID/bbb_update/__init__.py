from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..version import BBBUID_version
from ..bbb_config.bbb_config import BBB_CONFIG
from .draw_update_log import draw_update_log_img

sv_bbb_update_history = SV("bbb更新记录", pm=1)


@sv_bbb_update_history.on_fullmatch(("更新记录", "更新日志"))
async def send_bbb_update_log_msg(bot: Bot, ev: Event):
    if BBB_CONFIG.get_config("UseHtmlRender").data:
        try:
            from ..bbb_render.draw_update_html import draw_update_log_html
            im = await draw_update_log_html(BBBUID_version)
            return await bot.send(im)
        except Exception as e:
            logger.warning(f"[崩坏3] [更新记录] HTML 渲染失败，回退到 PIL: {e}")
    im = await draw_update_log_img(BBBUID_version)
    await bot.send(im)
