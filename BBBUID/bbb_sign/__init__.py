from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe

from . import until
from ..utils.hint import BIND_UID_HINT
from ..bbb_config.bbb_config import BBB_CONFIG

sv_bbb_sign = SV("崩坏3签到")
sv_bbb_sign_config = SV("崩坏3签到配置", pm=1)

SIGN_TIME = BBB_CONFIG.get_config("SignTime").data
IS_REPORT = BBB_CONFIG.get_config("PrivateSignReport").data


@sv_bbb_sign.on_fullmatch("签到")
async def manual_sign(bot: Bot, ev: Event):
    logger.info(f"[崩坏3] [签到] 用户: {ev.user_id}")
    qid = str(ev.user_id)
    bot_id = str(ev.bot_id)
    result, flag = await until.sign(qid, bot_id)
    if result:
        await bot.send(result)
    else:
        await bot.send(BIND_UID_HINT)


@sv_bbb_sign_config.on_fullmatch("全部重签")
async def recheck(bot: Bot, ev: Event):
    logger.info("开始执行[崩坏3全部重签]")
    await bot.send("🚩 [崩坏3] [全部重签] 已开始执行!")
    await _do_sign(force=True)
    await bot.send("🚩 [崩坏3] [全部重签] 执行完成!")


@scheduler.scheduled_job("cron", hour=SIGN_TIME[0], minute=SIGN_TIME[1])
async def bbb_sign_at_night():
    try:
        await _do_sign()
    except Exception as e:
        logger.error(f"[崩坏3] [定时签到] 定时任务异常: {e}")


async def sign_in_task(uid: str):
    return await until.sign_by_uid(uid)


async def _do_sign(force: bool = False):
    if not BBB_CONFIG.get_config("SchedSignin").data and not force:
        logger.info("[崩坏3] [定时签到] 定时签到已关闭")
        return

    logger.info("[崩坏3] [定时签到] 开始执行")
    datas = await gs_subscribe.get_subscribe("[崩坏3] 自动签到")
    if not datas:
        logger.info("[崩坏3] [定时签到] 无订阅用户")
        return

    priv_result, group_result = await gs_subscribe.muti_task(datas, sign_in_task, "uid")

    if not IS_REPORT:
        priv_result = {}

    for _, data in priv_result.items():
        im = "\n".join(data["im"])
        event = data["event"]
        await event.send(im)

    for _, data in group_result.items():
        im = "✅ 崩坏3今日自动签到已完成！\n"
        im += f"📝 本群共签到成功{data['success']}人，共签到失败{data['fail']}人。"
        event = data["event"]
        await event.send(im)

    logger.info("[崩坏3] [定时签到] 群聊推送完成")
