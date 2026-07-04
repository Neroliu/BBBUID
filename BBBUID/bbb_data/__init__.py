from datetime import datetime, timezone, timedelta

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..bbb_api import bh3_api
from ..bbb_config.bbb_config import BBB_CONFIG
from ..utils.uid import get_uid, get_query_target, extract_at_user_id_from_text
from ..utils.hint import BIND_UID_HINT, bbb_error_reply
from ..utils.char_data_cache import load_char_data, save_char_data, clear_char_data

CST = timezone(timedelta(hours=8))


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.fromtimestamp(int(ts), tz=CST)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return ts


# --- 查询 (Index/Overview) ---

sv_bbb_query = SV("崩坏3查询")


@sv_bbb_query.on_regex(r"^(?:查询|我的女武神)(?:\s*@[\w\-]+)?$", block=True)
async def send_index_info(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    index_data = await bh3_api.get_bbb_index(uid)
    if isinstance(index_data, int):
        return await bot.send(bbb_error_reply(index_data))

    # Try load from cache first
    characters = load_char_data(uid)
    if characters is None:
        # No cache, fetch from API
        char_data = await bh3_api.get_bbb_characters(uid)
        if isinstance(char_data, int):
            return await bot.send(bbb_error_reply(char_data))
        characters = char_data.get("characters", [])
        save_char_data(uid, characters)

    if BBB_CONFIG.get_config("UseHtmlRender").data:
        try:
            from ..bbb_render.draw_query_html import draw_query_card_html
            img = await draw_query_card_html(ev, uid, index_data, characters)
        except Exception as e:
            logger.warning(f"[崩坏3] HTML 渲染失败，回退到 PIL: {e}")
            from .draw_query import draw_query_card
            img = await draw_query_card(ev, uid, index_data, characters)
    else:
        from .draw_query import draw_query_card
        img = await draw_query_card(ev, uid, index_data, characters)
    await bot.send(img)


@sv_bbb_query.on_regex(r"^(?:刷新面板|更新面板)(?:\s*@[\w\-]+)?$", block=True)
async def send_refresh_panel(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    # Clear cache and re-fetch
    clear_char_data(uid)

    index_data = await bh3_api.get_bbb_index(uid)
    if isinstance(index_data, int):
        return await bot.send(bbb_error_reply(index_data))

    char_data = await bh3_api.get_bbb_characters(uid)
    if isinstance(char_data, int):
        return await bot.send(bbb_error_reply(char_data))

    characters = char_data.get("characters", [])
    save_char_data(uid, characters)

    if BBB_CONFIG.get_config("UseHtmlRender").data:
        try:
            from ..bbb_render.draw_query_html import draw_query_card_html
            img = await draw_query_card_html(ev, uid, index_data, characters)
        except Exception as e:
            logger.warning(f"[崩坏3] HTML 渲染失败，回退到 PIL: {e}")
            from .draw_query import draw_query_card
            img = await draw_query_card(ev, uid, index_data, characters)
    else:
        from .draw_query import draw_query_card
        img = await draw_query_card(ev, uid, index_data, characters)
    await bot.send(img)


# --- 便笺 (Real-time Notes) ---

sv_bbb_note = SV("崩坏3便笺")


@sv_bbb_note.on_regex(r"^(?:便笺|便签|实时便笺|体力|每日|mr)(?:\s*@[\w\-]+)?$", block=True)
async def send_note_info(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    index_data = await bh3_api.get_bbb_index(uid)
    if isinstance(index_data, int):
        return await bot.send(bbb_error_reply(index_data))
    note_data = await bh3_api.get_bbb_note(uid)
    if isinstance(note_data, int):
        return await bot.send(bbb_error_reply(note_data))

    if BBB_CONFIG.get_config("UseHtmlRender").data:
        try:
            from ..bbb_render.draw_note_html import draw_note_img_html
            img = await draw_note_img_html(ev, uid, index_data, note_data)
        except Exception as e:
            logger.warning(f"[崩坏3] HTML 渲染失败，回退到 PIL: {e}")
            from .draw_note import draw_note_img
            img = await draw_note_img(ev, uid, index_data, note_data)
    else:
        from .draw_note import draw_note_img
        img = await draw_note_img(ev, uid, index_data, note_data)
    await bot.send(img)


# --- 深渊 (Abyss) ---

sv_bbb_abyss = SV("崩坏3深渊")


@sv_bbb_abyss.on_regex(r"^(?:深渊|超弦空间|深渊战报)(?:\s*@[\w\-]+)?$", block=True)
async def send_abyss_info(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    data = await bh3_api.get_bbb_new_abyss(uid)
    if isinstance(data, int):
        data = await bh3_api.get_bbb_old_abyss(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    reports = data.get("reports", [])
    if not reports:
        return await bot.send("[崩坏3] 暂无深渊战报数据")

    try:
        from .avatar_utils import get_cached_avatar
        from .draw_abyss import draw_abyss

        user_avatar = await get_cached_avatar(ev, ev.user_id)
        img = await draw_abyss(ev, uid, data, user_avatar)
        await bot.send(img)
    except Exception as e:
        logger.warning(f"[崩坏3] 深渊图片渲染失败，回退到文本: {e}")
        lines = ["[崩坏3] 深渊战报"]
        for i, report in enumerate(reports):
            score = report.get("score", "?")
            boss = report.get("boss", {})
            boss_name = boss.get("name", "未知")
            lineup = report.get("lineup", [])
            lineup_names = " ".join([c.get("name", "?") for c in lineup[:3]])
            updated = _fmt_ts(report.get("updated_time_second", "0"))
            lines.append(f"  #{i+1} {boss_name} | 分数:{score} | {lineup_names}")
            lines.append(f"       更新于{updated}")
        await bot.send("\n".join(lines))


# --- 战场 (Battlefield/Memorial Arena) ---

sv_bbb_battlefield = SV("崩坏3战场")


@sv_bbb_battlefield.on_regex(r"^(?:战场|战场战报|记忆战场)(?:\s*@[\w\-]+)?$", block=True)
async def send_battlefield_info(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    data = await bh3_api.get_bbb_battle_field(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    reports = data.get("reports", [])
    if not reports:
        return await bot.send("[崩坏3] 暂无战场战报数据")

    try:
        from .avatar_utils import get_cached_avatar
        from .draw_battle import draw_battle

        user_avatar = await get_cached_avatar(ev, ev.user_id)
        img = await draw_battle(ev, uid, data, user_avatar)
        await bot.send(img)
    except Exception as e:
        logger.warning(f"[崩坏3] 战场图片渲染失败，回退到文本: {e}")
        lines = ["[崩坏3] 战场战报"]
        for i, report in enumerate(reports):
            score = report.get("score", "?")
            rank = report.get("rank", "?")
            ranking_pct = report.get("ranking_percentage", "?")
            area = report.get("area", "?")
            lines.append(f"  #{i+1} 分数:{score} 段位:{rank} 区:{area} 排名:前{ranking_pct}%")

            for bi in report.get("battle_infos", []):
                elf = bi.get("elf", {})
                elf_name = elf.get("name", "")
                lineup = bi.get("lineup", [])
                names = " ".join([c.get("name", "?") for c in lineup[:3]])
                elf_part = f" 人偶:{elf_name}" if elf_name else ""
                lines.append(f"    {names}{elf_part}")

        await bot.send("\n".join(lines))


# --- 往世乐土 (Elysian Realm / God War) ---

sv_bbb_godwar = SV("崩坏3往世乐土")


@sv_bbb_godwar.on_regex(r"^(?:往世乐土|乐土)(?:\s*@[\w\-]+)?$", block=True)
async def send_godwar_info(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示

    data = await bh3_api.get_bbb_god_war(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    records = data.get("records", [])
    if not records:
        return await bot.send("[崩坏3] 暂无往世乐土数据")

    lines = ["[崩坏3] 往世乐土"]
    for i, record in enumerate(records):
        score = record.get("score", "?")
        punish = record.get("punish_level", "?")
        main = record.get("main_avatar", {})
        main_name = main.get("name", "未知")
        supports = record.get("support_avatars", [])
        support_names = " ".join([s.get("name", "?") for s in supports[:2]])
        settle = _fmt_ts(record.get("settle_time_second", "0"))
        lines.append(f"  #{i+1} {main_name} + {support_names}")
        lines.append(f"       分数:{score} 难度:{punish} 时间:{settle}")

    await bot.send("\n".join(lines))


# --- 手账 (Hand Account) ---

sv_bbb_handbook = SV("崩坏3手账")


@sv_bbb_handbook.on_regex(r"^(?:手账|手帐)(?:\s*@[\w\-]+)?$", block=True)
async def send_handbook(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示
    logger.info(f"[崩坏3] [手账] 查询: UID={uid}")

    import asyncio
    index_data, count_data, finance_data = await asyncio.gather(
        bh3_api.get_bbb_index(uid),
        bh3_api.get_bbb_handbook_count(uid),
        bh3_api.get_bbb_weekly_finance(uid),
    )

    if isinstance(index_data, int):
        return await bot.send(bbb_error_reply(index_data))

    if isinstance(count_data, dict) and isinstance(finance_data, dict):
        from .draw_handbook import draw_handbook_img
        img = await draw_handbook_img(ev, uid, index_data, count_data, finance_data)
        await bot.send(img)
    else:
        lines = [f"[崩坏3] UID{uid} 本月手账"]
        if isinstance(count_data, dict):
            lines.append(f"角色&装备补给卡: {count_data.get('count', 0)} 张")
        else:
            lines.append(f"角色&装备补给卡: 查询失败")
        if isinstance(finance_data, dict):
            lines.append(f"本月水晶: {finance_data.get('month_hcoin', 0)}  (今日 +{finance_data.get('day_hcoin', 0)})")
            lines.append(f"本月星石: {finance_data.get('month_star', 0)}  (今日 +{finance_data.get('day_star', 0)})")
        else:
            lines.append(f"水晶/星石: 查询失败")
        await bot.send("\n".join(lines))


@sv_bbb_handbook.on_regex(r"^(?:手账上个月|手帐上个月)(?:\s*@[\w\-]+)?$", block=True)
async def send_handbook_last_month(bot: Bot, ev: Event):
    uid, _, _ = await get_query_target(bot, ev)
    if not uid:
        return  # 已在 get_query_target 内提示
    logger.info(f"[崩坏3] [手账上个月] 查询: UID={uid}")

    import asyncio
    index_data, count_data, finance_data = await asyncio.gather(
        bh3_api.get_bbb_index(uid),
        bh3_api.get_bbb_handbook_last_month_count(uid),
        bh3_api.get_bbb_weekly_finance_last_month(uid),
    )

    if isinstance(index_data, int):
        return await bot.send(bbb_error_reply(index_data))

    if isinstance(count_data, dict) and isinstance(finance_data, dict):
        from .draw_handbook import draw_handbook_img
        img = await draw_handbook_img(ev, uid, index_data, count_data, finance_data)
        await bot.send(img)
    else:
        lines = [f"[崩坏3] UID{uid} 上月手账"]
        if isinstance(count_data, dict):
            lines.append(f"角色&装备补给卡: {count_data.get('count', 0)} 张")
        else:
            lines.append(f"角色&装备补给卡: 查询失败")
        if isinstance(finance_data, dict):
            lines.append(f"上月水晶: {finance_data.get('month_hcoin', 0)}")
            lines.append(f"上月星石: {finance_data.get('month_star', 0)}")
        else:
            lines.append(f"水晶/星石: 查询失败")
        await bot.send("\n".join(lines))
