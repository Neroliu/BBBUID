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


async def _do_sign(force: bool = False):
    if not BBB_CONFIG.get_config("SchedSignin").data and not force:
        logger.info("[崩坏3] [定时签到] 定时签到已关闭")
        return

    logger.info("[崩坏3] [定时签到] 开始执行")
    datas = await gs_subscribe.get_subscribe("[崩坏3] 自动签到")
    if not datas:
        logger.info("[崩坏3] [定时签到] 无订阅用户")
        return

    success_cnt = 0
    fail_cnt = 0
    for data in datas:
        qid = str(data.user_id or "")
        bot_id = str(data.bot_id or "onebot")
        if not qid:
            continue
        try:
            result, flag = await until.sign(qid, bot_id)
            if flag:
                success_cnt += 1
            else:
                fail_cnt += 1
            if result:
                await data.send(result)
        except Exception as e:
            logger.error(f"[崩坏3] [定时签到] {qid} 签到异常: {e}")
            fail_cnt += 1

    logger.info(f"[崩坏3] [定时签到] 完成: 成功{success_cnt} 失败{fail_cnt}")
