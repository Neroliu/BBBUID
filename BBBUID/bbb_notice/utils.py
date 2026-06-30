"""崩坏3公告订阅工具函数 & 消息常量"""
from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.utils.database.models import Subscribe

TOPIC_NOTICE = "订阅崩坏3公告"


class Msg:
    SUBSCRIBED = "✅ 已成功订阅崩坏3公告推送！"
    ALREADY_SUBSCRIBED = "✅ 已经订阅过崩坏3公告推送了，已刷新订阅信息。"
    UNSUBSCRIBED = "✅ 已取消订阅崩坏3公告推送。"
    NOT_SUBSCRIBED = "❌ 当前群尚未订阅崩坏3公告。"
    PUSH_CLOSED = "❌ 崩坏3公告推送功能已关闭，请联系管理员开启。"
    SUBSCRIBE_GROUP_ONLY = "❌ 请在群聊中使用订阅命令。"


async def subscribe_session(ev: Event) -> bool:
    """群级别订阅，同一群只保留一条。返回此前是否已存在。"""
    existed = await unsubscribe_session(ev)
    await gs_subscribe.add_subscribe("session", TOPIC_NOTICE, ev)
    return bool(existed)


async def unsubscribe_session(ev: Event) -> int:
    """取消群级别订阅。返回删除行数。"""
    if ev.group_id:
        return await Subscribe.delete_row(task_name=TOPIC_NOTICE, group_id=ev.group_id)
    return await Subscribe.delete_row(task_name=TOPIC_NOTICE, user_id=ev.user_id, bot_id=ev.bot_id)


async def list_subscribers() -> list[Subscribe]:
    subs = await gs_subscribe.get_subscribe(TOPIC_NOTICE)
    return list(subs) if subs else []


async def send_notify(bot: Bot, ev: Event, msg: str) -> None:
    await bot.send(msg)
