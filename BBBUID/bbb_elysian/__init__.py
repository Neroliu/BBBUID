from PIL import Image

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV
from gsuid_core.utils.image.convert import convert_img

from .service import (
    format_refresh_summary,
    format_source,
    list_strategy_keywords,
    query_strategy,
    refresh_strategy_index,
    show_source,
    strategy_enabled,
)

sv_bbb_elysian = SV("崩坏3乐土攻略")
sv_bbb_elysian_admin = SV("崩坏3乐土攻略管理", pm=1)


async def _send_strategy(bot: Bot, keyword: str):
    keyword = keyword.strip()
    if not strategy_enabled():
        return await bot.send("[崩坏3] 乐土攻略查询已关闭。")
    if not keyword:
        return await bot.send("[崩坏3] 请输入攻略关键词，例如：bbb乐土攻略 人律")

    logger.info(f"[崩坏3] [乐土攻略] 查询: {keyword}")
    result = await query_strategy(keyword)
    if result.error:
        msg = result.error
        if result.candidates:
            msg += "\n可尝试：" + "、".join(result.candidates)
        return await bot.send(msg)
    if not result.match:
        return await bot.send("[崩坏3] 乐土攻略查询失败，请稍后再试。")

    if show_source():
        await bot.send(format_source(result.match))
    with Image.open(result.match.image_path) as image:
        await bot.send(await convert_img(image.copy()))


@sv_bbb_elysian.on_prefix(("乐土攻略", "攻略"), block=True)
async def send_elysian_strategy(bot: Bot, ev: Event):
    await _send_strategy(bot, ev.text)


@sv_bbb_elysian.on_regex(r"^(?!(?:更新|清理)?乐土攻略$)(?P<keyword>.+?)乐土攻略$", block=True)
async def send_elysian_strategy_shortcut(bot: Bot, ev: Event):
    await _send_strategy(bot, ev.regex_dict["keyword"])


@sv_bbb_elysian_admin.on_fullmatch("更新乐土攻略", block=True)
async def update_elysian_strategy(bot: Bot, ev: Event):
    if not strategy_enabled():
        return await bot.send("[崩坏3] 乐土攻略查询已关闭。")
    await _update_elysian_strategy(bot)


async def _update_elysian_strategy(bot: Bot):
    await bot.send("[崩坏3] 正在更新乐土攻略索引，请稍候...")
    await bot.send(format_refresh_summary(await refresh_strategy_index()))


@sv_bbb_elysian.on_prefix("乐土关键词列表", block=True)
async def list_elysian_keywords(bot: Bot, ev: Event):
    if not strategy_enabled():
        return await bot.send("[崩坏3] 乐土攻略查询已关闭。")
    _, msg = await list_strategy_keywords(ev.text.strip())
    await bot.send(msg)
