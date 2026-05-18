import traceback

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
        logger.error(f"[崩坏3] [定时签到] 定时任务异常: {e}\n{traceback.format_exc()}")


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

    logger.info(f"[崩坏3] [定时签到] 共 {len(datas)} 个订阅用户")
    for i, d in enumerate(datas):
        logger.debug(
            f"[崩坏3] [定时签到] 订阅[{i}] uid={d.uid} user_type={d.user_type} "
            f"user_id={d.user_id} group_id={d.group_id} WS_BOT_ID={d.WS_BOT_ID}"
        )

    priv_result, group_result = await gs_subscribe.muti_task(datas, sign_in_task, "uid")

    logger.info(
        f"[崩坏3] [定时签到] muti_task 完成: "
        f"priv_result={len(priv_result)} group_result={len(group_result)}"
    )

    if not IS_REPORT:
        logger.info("[崩坏3] [定时签到] PrivateSignReport 已关闭，跳过私聊推送")
        priv_result = {}

    for sid, data in priv_result.items():
        msgs = data.get("im", [])
        if not msgs:
            continue
        im = "\n".join(msgs)
        event = data["event"]
        try:
            ret = await event.send(im)
            if ret == -1:
                logger.error(f"[崩坏3] [定时签到] 私聊通知发送失败 sid={sid} user_id={event.user_id}")
            else:
                logger.info(f"[崩坏3] [定时签到] 私聊通知已发送 sid={sid} user_id={event.user_id}")
        except Exception as e:
            logger.error(f"[崩坏3] [定时签到] 私聊通知异常 sid={sid}: {e}")

    for sid, data in group_result.items():
        im = "✅ 崩坏3今日自动签到已完成！\n"
        im += f"📝 本群共签到成功{data['success']}人，共签到失败{data['fail']}人。"
        event = data["event"]
        try:
            ret = await event.send(im)
            if ret == -1:
                logger.error(
                    f"[崩坏3] [定时签到] 群聊通知发送失败 sid={sid} "
                    f"group_id={event.group_id} WS_BOT_ID={event.WS_BOT_ID}"
                )
            else:
                logger.info(
                    f"[崩坏3] [定时签到] 群聊通知已发送 sid={sid} "
                    f"group_id={event.group_id} success={data['success']} fail={data['fail']}"
                )
        except Exception as e:
            logger.error(f"[崩坏3] [定时签到] 群聊通知异常 sid={sid}: {e}")

    logger.info("[崩坏3] [定时签到] 群聊推送完成")
