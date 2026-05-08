from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import Subscribe, gs_subscribe
from gsuid_core.utils.database.models import GsBind, GsUser
from gsuid_core.utils.error_reply import CK_HINT

from ..utils.hint import BIND_UID_HINT as UID_HINT

sv_bbb_config = SV("崩坏3配置")

PRIV_MAP = {
    "自动签到": None,
}


@sv_bbb_config.on_prefix(("开启", "关闭"))
async def open_switch_func(bot: Bot, ev: Event):
    user_id = ev.user_id
    config_name = ev.text

    if config_name not in PRIV_MAP:
        return await bot.send(
            f"🔨 [崩坏3服务]\n❌ 请输入正确的功能名称...\n🚩 例如: bbb开启自动签到"
        )

    logger.info(f"[崩坏3服务] [{user_id}] 尝试[{ev.command}] [{config_name}]")

    uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, "bbb")
    if uid is None:
        return await bot.send(UID_HINT)
    cookie = await GsUser.get_user_cookie_by_user_id(ev.user_id, ev.bot_id)
    if cookie is None:
        return await bot.send(CK_HINT)

    c_name = f"[崩坏3] {config_name}"

    if "开启" in ev.command:
        if PRIV_MAP[config_name] is None and await gs_subscribe.get_subscribe(c_name, uid=uid):
            await Subscribe.update_data_by_data(
                {"task_name": c_name, "uid": uid},
                {
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "group_id": ev.group_id,
                    "bot_self_id": ev.bot_self_id,
                    "user_type": ev.user_type,
                    "WS_BOT_ID": ev.WS_BOT_ID,
                },
            )
        else:
            await gs_subscribe.add_subscribe(
                "single",
                c_name,
                ev,
                extra_message=PRIV_MAP[config_name],
                uid=uid,
            )
        await bot.send(f"🔨 [崩坏3服务]\n✅ 已为[UID{uid}]开启{config_name}功能。")
    else:
        data = await gs_subscribe.get_subscribe(
            c_name,
            ev.user_id,
            ev.bot_id,
            ev.user_type,
        )
        if data:
            await gs_subscribe.delete_subscribe(
                "single",
                c_name,
                ev,
                uid=uid,
            )
            await bot.send(f"🔨 [崩坏3服务]\n✅ 已为[UID{uid}]关闭{config_name}功能。")
        else:
            await bot.send(
                f"🔨 [崩坏3服务]\n❌ 未找到[UID{uid}]的{config_name}配置, 该功能可能未开启。"
            )
