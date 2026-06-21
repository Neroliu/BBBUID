"""崩坏3抽卡记录命令入口。"""
from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..utils.uid import get_uid
from ..utils.hint import BIND_UID_HINT
from .get_gachalogs import save_gachalogs, get_full_gachalogs, get_gacha_summary

sv_bbb_gacha = SV("崩坏3抽卡记录")


@sv_bbb_gacha.on_fullmatch(("抽卡记录", "抽卡统计"), block=True)
async def send_gacha_log(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)
    logger.info(f"[崩坏3] [抽卡记录] 查看记录: UID={uid}")
    result = await get_gacha_summary(uid)
    await bot.send(result)


@sv_bbb_gacha.on_fullmatch(("刷新抽卡记录", "更新抽卡记录"), block=True)
async def send_refresh_gacha(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)
    logger.info(f"[崩坏3] [抽卡记录] 增量刷新: UID={uid}")
    result = await save_gachalogs(uid)
    await bot.send(result)


@sv_bbb_gacha.on_fullmatch(("全量刷新抽卡记录", "全量更新抽卡记录"), block=True)
async def send_full_refresh_gacha(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)
    logger.info(f"[崩坏3] [抽卡记录] 全量刷新: UID={uid}")
    result = await get_full_gachalogs(uid)
    await bot.send(result)
