from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .name_convert import (
    load_char_meta,
    alias_to_char_name,
    char_name_to_content_id,
    load_user_char_aliases,
    save_user_char_aliases,
    alias_to_char_name_list,
)


async def run_char_alias_action(
    bot: Bot,
    ev: Event,
    action: str,
    char_name: str,
    new_alias: str,
) -> None:
    if not char_name or not new_alias:
        return await bot.send("[崩坏3] 角色名或别名不能为空")

    std_char_name = alias_to_char_name(char_name)
    if not std_char_name:
        return await bot.send(f"[崩坏3] 未找到角色: {char_name}")
    content_id = char_name_to_content_id(std_char_name)
    if not content_id:
        return await bot.send(f"[崩坏3] 未找到角色: {char_name}")

    user_file = load_user_char_aliases()

    if action == "添加":
        check_new_alias = alias_to_char_name(new_alias)
        if check_new_alias:
            return await bot.send(
                f"[崩坏3] 别名「{new_alias}」已被角色【{check_new_alias}】占用"
            )

        user_file.root.setdefault(content_id, []).append(new_alias)
        save_user_char_aliases(user_file)
        load_char_meta()
        return await bot.send(
            f"[崩坏3] 已为角色【{std_char_name}】添加别名: {new_alias}"
        )

    if action == "删除":
        user_aliases = user_file.root.get(content_id, [])
        if new_alias not in user_aliases:
            return await bot.send(
                f"[崩坏3] 别名「{new_alias}」不存在或为预设别名，无法删除"
            )

        user_aliases.remove(new_alias)
        if not user_aliases:
            user_file.root.pop(content_id, None)
        save_user_char_aliases(user_file)
        load_char_meta()
        return await bot.send(
            f"[崩坏3] 已为角色【{std_char_name}】删除别名: {new_alias}"
        )

    await bot.send("[崩坏3] 未知操作，请使用「添加」或「删除」")


async def run_char_alias_list(bot: Bot, ev: Event, char_name: str) -> None:
    if not char_name:
        return await bot.send("[崩坏3] 请输入角色名称，例如: bbb次生银翼别名")

    std_char_name = alias_to_char_name(char_name)
    if not std_char_name:
        return await bot.send(f"[崩坏3] 未找到角色: {char_name}")

    alias_list = alias_to_char_name_list(char_name)
    if not alias_list:
        return await bot.send(f"[崩坏3] 未找到角色: {char_name}")

    await bot.send(
        f"[崩坏3] 角色【{std_char_name}】别名列表：\n" + "、".join(alias_list)
    )
