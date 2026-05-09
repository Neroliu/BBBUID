from datetime import datetime, timezone, timedelta

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..bbb_api import bh3_api
from ..utils.uid import get_uid
from ..utils.hint import BIND_UID_HINT, bbb_error_reply

CST = timezone(timedelta(hours=8))


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.fromtimestamp(int(ts), tz=CST)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return ts


# --- 查询 (Index/Overview) ---

sv_bbb_query = SV("崩坏3查询")


@sv_bbb_query.on_fullmatch(("查询", "我的女武神"), block=True)
async def send_index_info(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)

    data = await bh3_api.get_bbb_index(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    role = data.get("role", {})
    stats = data.get("stats", {})
    pref = data.get("preference", {})
    nickname = role.get("nickname", "未知")
    level = role.get("level", "?")

    lines = [
        f"舰长: {nickname} Lv.{level}",
        f"UID: {uid}",
        "",
    ]

    if stats:
        stat_map = {
            "active_day_number": "活跃天数",
            "armor_number": "女武神",
            "sss_armor_number": "SSS女武神",
            "stigmata_number": "圣痕",
            "five_star_stigmata_number": "五星圣痕",
            "weapon_number": "武器",
            "five_star_weapon_number": "五星武器",
        }
        for key, label in stat_map.items():
            if key in stats:
                lines.append(f"{label}: {stats[key]}")

        new_abyss = stats.get("new_abyss", {})
        if new_abyss:
            lines.append(f"超弦空间: 级别{new_abyss.get('level', '?')} 奖杯{new_abyss.get('cup_number', '?')}")
        if "abyss_score" in stats:
            lines.append(f"深渊分数: {stats['abyss_score']}")
        if "battle_field_score" in stats:
            lines.append(f"战场分数: {stats['battle_field_score']}")
        if "battle_field_ranking_percentage" in stats:
            lines.append(f"战场排名: 前{stats['battle_field_ranking_percentage']}%")
        if "god_war_max_challenge_score" in stats:
            lines.append(f"乐土最高分: {stats['god_war_max_challenge_score']}")

    if pref:
        lines.append("")
        comp = pref.get("comprehensive_rating", "?")
        comp_score = pref.get("comprehensive_score", "?")
        lines.append(f"综合评价: {comp}({comp_score}分)")

    await bot.send("\n".join(lines))


# --- 便笺 (Real-time Notes) ---

sv_bbb_note = SV("崩坏3便笺")


@sv_bbb_note.on_fullmatch(("便笺", "便签", "实时便笺", "体力"), block=True)
async def send_note_info(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)

    data = await bh3_api.get_bbb_note(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    cur = data.get("current_stamina", "?")
    mx = data.get("max_stamina", "?")
    recover = data.get("stamina_recover_time", 0)
    hours = recover // 3600
    minutes = (recover % 3600) // 60

    lines = [
        f"[崩坏3] 实时便笺",
        f"体力: {cur}/{mx}",
    ]
    if recover > 0:
        lines.append(f"体力回满: {hours}时{minutes}分后")

    # 深渊升降机
    ultra = data.get("ultra_endless", {})
    if ultra:
        is_open = "开放中" if ultra.get("is_open") else "未开放"
        end = _fmt_ts(ultra.get("schedule_end", "0"))
        lines.append(f"深渊升降机: {is_open} (结束{end})")

    # 战场升降机
    bf = data.get("battle_field", {})
    if bf:
        is_open = "开放中" if bf.get("is_open") else "未开放"
        end = _fmt_ts(bf.get("schedule_end", "0"))
        cur_r = bf.get("cur_reward", "?")
        max_r = bf.get("max_reward", "?")
        lines.append(f"战场升降机: {is_open} (结束{end}) 奖励{cur_r}/{max_r}")

    # 往世乐土
    gw = data.get("god_war", {})
    if gw:
        is_open = "开放中" if gw.get("is_open") else "未开放"
        end = _fmt_ts(gw.get("schedule_end", "0"))
        cur_r = gw.get("cur_reward", "?")
        max_r = gw.get("max_reward", "?")
        lines.append(f"往世乐土: {is_open} (结束{end}) 奖励{cur_r}/{max_r}")

    await bot.send("\n".join(lines))


# --- 深渊 (Abyss) ---

sv_bbb_abyss = SV("崩坏3深渊")


@sv_bbb_abyss.on_fullmatch(("深渊", "超弦空间", "深渊战报"), block=True)
async def send_abyss_info(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)

    data = await bh3_api.get_bbb_new_abyss(uid)
    if isinstance(data, int):
        data = await bh3_api.get_bbb_old_abyss(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    reports = data.get("reports", [])
    if not reports:
        return await bot.send("[崩坏3] 暂无深渊战报数据")

    lines = ["[崩坏3] 深渊战报"]
    for i, report in enumerate(reports[:3]):
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


@sv_bbb_battlefield.on_fullmatch(("战场", "战场战报", "记忆战场"), block=True)
async def send_battlefield_info(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)

    data = await bh3_api.get_bbb_battle_field(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    reports = data.get("reports", [])
    if not reports:
        return await bot.send("[崩坏3] 暂无战场战报数据")

    lines = ["[崩坏3] 战场战报"]
    for report in reports[:2]:
        score = report.get("score", "?")
        rank = report.get("rank", "?")
        ranking_pct = report.get("ranking_percentage", "?")
        area = report.get("area", "?")
        lines.append(f"  分数:{score} 段位:{rank} 区:{area} 排名:前{ranking_pct}%")

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


@sv_bbb_godwar.on_fullmatch(("往世乐土", "乐土"), block=True)
async def send_godwar_info(bot: Bot, ev: Event):
    uid = await get_uid(bot, ev)
    if not uid:
        return await bot.send(BIND_UID_HINT)

    data = await bh3_api.get_bbb_god_war(uid)
    if isinstance(data, int):
        return await bot.send(bbb_error_reply(data))

    records = data.get("records", [])
    if not records:
        return await bot.send("[崩坏3] 暂无往世乐土数据")

    lines = ["[崩坏3] 往世乐土"]
    for i, record in enumerate(records[:3]):
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
