from typing import Union

from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.utils.database.models import GsBind

from . import until
from ..utils.hint import BIND_UID_HINT

sv_bbb_sign = SV("崩坏3米游社签到")
sv_bbb_sign_config = SV("崩坏3米游社签到配置", pm=1)


@sv_bbb_sign.on_fullmatch("签到")
async def manual_sign(bot: Bot, ev: Event):
    logger.info(f"[崩坏3] [签到] 用户: {ev.user_id}")
    uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, "bbb")
    if uid is None:
        return await bot.send(BIND_UID_HINT)
    logger.info(f"[崩坏3] [签到] UID: {uid}")
    await bot.send(await until.sign(uid))


@sv_bbb_sign_config.on_fullmatch("全部重签")
async def recheck(bot: Bot, ev: Event):
    logger.info("开始执行[崩坏3全部重签]")
    await bot.send("🚩 [崩坏3] [全部重签] 已开始执行!")
    await bbb_sign_at_night(True)
    await bot.send("🚩 [崩坏3] [全部重签] 执行完成!")


async def sign_in_task(uid: Union[str, int]) -> str:
    return await until.sign(str(uid))


@scheduler.scheduled_job("cron", hour="2", minute="00")
async def bbb_sign_at_night(force: bool = False):
    logger.info("[崩坏3] [定时签到] 开始执行")
    datas = await gs_subscribe.get_subscribe("[崩坏3] 自动签到")
    if not datas:
        logger.info("[崩坏3] [定时签到] 无订阅用户")
        return

    priv_result, group_result = await gs_subscribe.muti_task(datas, sign_in_task, "uid")

    for _, data in priv_result.items():
        im = "\n".join(data["im"])
        event = data["event"]
        await event.send(im)

    for _, data in group_result.items():
        im = "✅ 崩坏3今日自动签到已完成！\n"
        im += f"📝 本群共签到成功{data['success']}人，共签到失败{data['fail']}人。"
        event = data["event"]
        await event.send(im)

    logger.info("[崩坏3] [每日全部签到] 推送完成")
