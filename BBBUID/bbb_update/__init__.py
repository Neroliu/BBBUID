from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..version import BBBUID_version
from .draw_update_log import draw_update_log_img

sv_bbb_update_history = SV("bbb更新记录", pm=1)


@sv_bbb_update_history.on_fullmatch(("更新记录", "更新日志"))
async def send_bbb_update_log_msg(bot: Bot, ev: Event):
    im = await draw_update_log_img(BBBUID_version)
    await bot.send(im)
