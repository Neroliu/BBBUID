"""崩坏3公告订阅模块"""
import random
import asyncio

from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..bbb_config.bbb_config import BBB_CONFIG
from .utils import Msg, TOPIC_NOTICE, subscribe_session, unsubscribe_session, list_subscribers, send_notify
from .notice_api import get_bbb_notice_list, get_bbb_notice_detail, get_article_url
from .notice_card import render_notice_card

sv_bbb_notice = SV("崩坏3公告")
sv_bbb_notice_sub = SV("订阅崩坏3公告", pm=3)

ANN_CHECK_MIN: int = min(BBB_CONFIG.get_config("BBBAnnCheckMinutes").data, 60)


@sv_bbb_notice.on_command("公告", block=True)
async def send_bbb_notice(bot: Bot, ev: Event):
    """查询最新崩坏3公告"""
    notices = await get_bbb_notice_list(page_size=8)
    if not notices:
        return await bot.send("[崩坏3] 暂无公告数据")

    lines = ["[崩坏3] 最新公告"]
    for n in notices:
        lines.append(f"• {n['subject']}")
    lines.append(f"\n{get_article_url(notices[0]['post_id'])}")
    await bot.send("\n".join(lines))


@sv_bbb_notice_sub.on_fullmatch("订阅公告")
async def sub_bbb_notice(bot: Bot, ev: Event):
    if not ev.group_id:
        return await send_notify(bot, ev, Msg.SUBSCRIBE_GROUP_ONLY)
    if not BBB_CONFIG.get_config("BBBAnnOpen").data:
        return await send_notify(bot, ev, Msg.PUSH_CLOSED)

    existed = await subscribe_session(ev)
    await send_notify(bot, ev, Msg.ALREADY_SUBSCRIBED if existed else Msg.SUBSCRIBED)


@sv_bbb_notice_sub.on_fullmatch(("取消订阅公告", "退订公告"))
async def unsub_bbb_notice(bot: Bot, ev: Event):
    if not ev.group_id:
        return await send_notify(bot, ev, Msg.SUBSCRIBE_GROUP_ONLY)

    if await unsubscribe_session(ev):
        return await send_notify(bot, ev, Msg.UNSUBSCRIBED)
    return await send_notify(bot, ev, Msg.NOT_SUBSCRIBED)


@scheduler.scheduled_job("interval", minutes=ANN_CHECK_MIN)
async def check_bbb_notice():
    if not BBB_CONFIG.get_config("BBBAnnOpen").data:
        return
    await _check_and_push()


async def _check_and_push():
    logger.info("[崩坏3公告] 定时任务: 检查公告..")
    subs = await list_subscribers()
    if not subs:
        logger.info("[崩坏3公告] 暂无群订阅")
        return

    notices = await get_bbb_notice_list(page_size=20)
    if not notices:
        return

    known_ids: list[str] = BBB_CONFIG.get_config("BBBAnnIds").data
    fresh_ids = [n["post_id"] for n in notices]

    if not known_ids:
        BBB_CONFIG.set_config("BBBAnnIds", fresh_ids)
        logger.info("[崩坏3公告] 初始记录完成, 将在下次轮询中检测新公告.")
        return

    pending = [n for n in notices if n["post_id"] not in known_ids]
    if not pending:
        logger.info("[崩坏3公告] 没有新公告")
        return

    merged = sorted(set(known_ids) | set(fresh_ids), reverse=True)[:50]
    BBB_CONFIG.set_config("BBBAnnIds", merged)

    for n in reversed(pending):
        try:
            detail = await get_bbb_notice_detail(n["post_id"])
            if detail:
                post_data = detail.get("post", {}).get("post", {})
                title = post_data.get("subject", n["subject"])
                content_html = post_data.get("content", "")
                img = await render_notice_card(title, content_html)
            else:
                img = f"[崩坏3] 新公告\n{n['subject']}\n{get_article_url(n['post_id'])}"
        except Exception as e:
            logger.warning(f"[崩坏3公告] 渲染失败 post_id={n['post_id']}: {e}")
            img = f"[崩坏3] 新公告\n{n['subject']}\n{get_article_url(n['post_id'])}"

        for sub in subs:
            try:
                await sub.send(img)
            except Exception as e:
                logger.warning(f"[崩坏3公告] 推送失败 post_id={n['post_id']} group={sub.group_id}: {e!r}")
            await asyncio.sleep(random.uniform(1, 3))

    logger.info(f"[崩坏3公告] 推送完毕, 共 {len(pending)} 条新公告")
