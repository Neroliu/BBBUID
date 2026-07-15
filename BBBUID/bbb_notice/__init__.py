"""崩坏3公告模块 (分类公告 + 订阅推送 + 6h 过期过滤)"""
import time
import random
import asyncio

from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..bbb_config.bbb_config import BBB_CONFIG
from .utils import Msg, TOPIC_NOTICE, subscribe_session, unsubscribe_session, list_subscribers, send_notify
from .notice_api import (
    BBBNoticeType,
    NOTICE_TYPES,
    get_news_list,
    get_all_news_list,
    get_post_detail,
    get_article_url,
)
from .notice_card import render_notice_list_card, render_notice_detail

sv_bbb_notice = SV("崩坏3公告")
sv_bbb_notice_sub = SV("订阅崩坏3公告", pm=3)

ANN_CHECK_MIN: int = min(BBB_CONFIG.get_config("BBBAnnCheckMinutes").data, 60)

# 旧公告过滤窗口 (毫秒), 与 NTEUID 对齐
_MAX_AGE_MS = 6 * 60 * 60 * 1000

# 分类 type → 配置 key 映射
_TYPE_CONFIG_MAP = {
    BBBNoticeType.ANNOUNCE: "BBBAnnIdsAnnounce",
    BBBNoticeType.ACTIVITY: "BBBAnnIdsActivity",
    BBBNoticeType.INFO: "BBBAnnIdsInfo",
}


# ════════════════════════════════════════════
#  命令: 公告 (支持 公告 / 活动公告 / 资讯公告 / 公告+ID)
# ════════════════════════════════════════════


@sv_bbb_notice.on_command("公告", block=True)
async def send_bbb_notice(bot: Bot, ev: Event):
    """查询崩坏3公告。支持: 公告 / 活动公告 / 资讯公告 / 公告+ID"""
    text = (ev.text or "").strip().replace("#", "")

    # 分类列表
    type_map = {
        "活动": BBBNoticeType.ACTIVITY,
        "资讯": BBBNoticeType.INFO,
    }
    ntype = type_map.get(text)

    if ntype:
        posts = await get_news_list(ntype, page_size=8)
        if not posts:
            return await bot.send(f"[崩坏3] 暂无{ntype.label}数据")
        columns = {ntype: posts}
        img = await render_notice_list_card(columns)
        return await bot.send(img)

    # 按 ID 查详情
    if text.isdigit():
        post_id = int(text)
        detail = await get_post_detail(post_id)
        if not detail:
            return await bot.send(f"[崩坏3] 未找到公告 ID: {post_id}")
        img = await render_notice_detail(detail)
        return await bot.send(img)

    # 默认: 全分类列表
    columns = await get_all_news_list(page_size=8)
    if not any(columns.values()):
        return await bot.send("[崩坏3] 暂无公告数据")
    img = await render_notice_list_card(columns)
    await bot.send(img)

# ════════════════════════════════════════════
#  订阅 / 取消订阅
# ════════════════════════════════════════════


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


# ════════════════════════════════════════════
#  配置读写辅助
# ════════════════════════════════════════════


def _get_type_ids(ntype: BBBNoticeType) -> list[int]:
    cfg_key = _TYPE_CONFIG_MAP[ntype]
    raw = BBB_CONFIG.get_config(cfg_key).data
    return list(raw) if raw else []


def _set_type_ids(ntype: BBBNoticeType, ids: list[int]) -> None:
    cfg_key = _TYPE_CONFIG_MAP[ntype]
    BBB_CONFIG.set_config(cfg_key, ids)


def _get_known_ids() -> list[str]:
    """读取旧的扁平 ID 列表 (用于迁移)。"""
    raw = BBB_CONFIG.get_config("BBBAnnIds").data
    return list(raw) if raw else []


# ════════════════════════════════════════════
#  定时任务
# ════════════════════════════════════════════


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

    columns = await get_all_news_list(page_size=20)
    flat = [post for posts in columns.values() for post in posts]
    if not flat:
        return

    # 首次运行 / 旧配置迁移
    any_has_ids = any(_get_type_ids(t) for t in NOTICE_TYPES)
    if not any_has_ids:
        old_ids = _get_known_ids()
        if old_ids:
            _set_type_ids(BBBNoticeType.ANNOUNCE, [int(i) for i in old_ids])
            logger.info("[崩坏3公告] 已从旧配置迁移公告ID到分类存储")
        else:
            for ntype in NOTICE_TYPES:
                posts = columns.get(ntype, [])
                _set_type_ids(ntype, [p.post_id for p in posts])
            logger.info("[崩坏3公告] 初始记录完成, 将在下次轮询中检测新公告.")
            return

    # 增量检测 (按分类)
    now_ms = int(time.time() * 1000)
    min_send_time = now_ms - _MAX_AGE_MS
    pending_all = []

    for ntype in NOTICE_TYPES:
        known = set(_get_type_ids(ntype))
        posts = columns.get(ntype, [])

        fresh_ids = [p.post_id for p in posts]
        pending = [
            p for p in posts
            if p.post_id not in known and p.created_at * 1000 >= min_send_time
        ]
        pending_all.extend((ntype, p) for p in pending)

        merged = sorted(set(known) | set(fresh_ids), reverse=True)[:50]
        _set_type_ids(ntype, merged)

    if not pending_all:
        logger.info("[崩坏3公告] 没有新公告")
        return

    # 按时间排序后推送 (从旧到新)
    pending_all.sort(key=lambda x: x[1].created_at)

    for ntype, post in pending_all:
        try:
            detail = await get_post_detail(post.post_id)
            if detail:
                img = await render_notice_detail(detail)
            else:
                img = f"[崩坏3] 新{ntype.label}\n{post.subject}\n{get_article_url(post.post_id)}"
        except Exception as e:
            logger.warning(f"[崩坏3公告] 渲染失败 post_id={post.post_id}: {e}")
            img = f"[崩坏3] 新{ntype.label}\n{post.subject}\n{get_article_url(post.post_id)}"

        for sub in subs:
            try:
                await sub.send(img)
            except Exception as e:
                logger.warning(
                    f"[崩坏3公告] 推送失败 post_id={post.post_id} "
                    f"group={sub.group_id}: {e!r}"
                )
            await asyncio.sleep(random.uniform(1, 3))

    logger.info(f"[崩坏3公告] 推送完毕, 共 {len(pending_all)} 条新公告")
