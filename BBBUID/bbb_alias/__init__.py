from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .alias_service import run_char_alias_action, run_char_alias_list

COMMAND_NAME_PATTERN = r"[一-龥a-zA-Z0-9\-—·()（）]{1,20}"

sv_bbb_alias = SV("崩坏3角色别名")
sv_bbb_alias_list = SV("崩坏3角色别名列表")


@sv_bbb_alias.on_regex(
    rf"^(?P<action>添加|删除)(角色)?(?P<char_name>{COMMAND_NAME_PATTERN})别名(?P<new_alias>{COMMAND_NAME_PATTERN})$",
    block=True,
)
async def bbb_role_alias_action(bot: Bot, ev: Event):
    await run_char_alias_action(
        bot,
        ev,
        ev.regex_dict["action"],
        ev.regex_dict["char_name"],
        ev.regex_dict["new_alias"],
    )


@sv_bbb_alias_list.on_regex(
    rf"^(?P<char_name>{COMMAND_NAME_PATTERN})别名(列表)?$",
    block=True,
)
async def bbb_role_alias(bot: Bot, ev: Event):
    await run_char_alias_list(bot, ev, ev.regex_dict["char_name"])
