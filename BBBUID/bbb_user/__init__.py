from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.utils.database.models import GsBind

from ..bbb_api import bh3_api

GAME_NAME = "bbb"

REGION_MAP = {
    "android01": "安卓1区",
    "ios01": "iOS1区",
    "pc01": "PC1区",
}

sv_bbb_user = SV("崩坏3用户信息")


@sv_bbb_user.on_fullmatch(("查看", "查看uid", "uid列表"), block=True)
async def view_bindings(bot: Bot, ev: Event):
    uid_list = await GsBind.get_uid_list_by_game(ev.user_id, ev.bot_id, GAME_NAME)
    if not uid_list:
        return await bot.send("[崩坏3] 你还没有绑定任何UID！")

    current_uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, GAME_NAME)
    lines = [f"[崩坏3] 已绑定 {len(uid_list)} 个UID"]
    for i, uid in enumerate(uid_list, 1):
        tag = "（当前）" if uid == current_uid else ""
        server = await bh3_api.get_bbb_server(uid)
        region_name = REGION_MAP.get(server, server or "未知区服")
        lines.append(f"  {i}. {uid} {region_name}{tag}")
    await bot.send("\n".join(lines))


@sv_bbb_user.on_command(
    ("绑定uid", "绑定UID", "绑定"),
    block=True,
)
async def bind_uid(bot: Bot, ev: Event):
    qid = ev.user_id
    uid = (ev.text or "").strip()
    if not uid:
        return await bot.send("[崩坏3] 你需要在命令后面加入你的UID！")
    data = await GsBind.insert_uid(qid, ev.bot_id, uid, ev.group_id, game_name=GAME_NAME)
    if data == 0:
        await bot.send(f"✅[崩坏3]绑定uid[{uid}]成功!")
    elif data == -1:
        await bot.send(f"❎[崩坏3]uid[{uid}]的位数不正确!")
    elif data == -2:
        await bot.send(f"❎[崩坏3]uid[{uid}]已经绑定过了!")
    elif data == -3:
        await bot.send("❎[崩坏3]你输入了错误的格式!")


@sv_bbb_user.on_command(
    ("切换uid", "切换UID", "切换"),
    block=True,
)
async def switch_uid(bot: Bot, ev: Event):
    qid = ev.user_id
    uid = (ev.text or "").strip()
    if uid and not uid.isdigit():
        return await bot.send("[崩坏3] 你需要在切换命令后面加入UID或者直接输入切换命令！")
    data = await GsBind.switch_uid_by_game(qid, ev.bot_id, uid, GAME_NAME)
    if data == 0:
        await bot.send(f"✅[崩坏3]切换uid成功!")
    elif data == -1:
        await bot.send("❎[崩坏3]不存在绑定记录!")
    else:
        await bot.send("❎[崩坏3]请绑定两个以上UID再进行切换!")


@sv_bbb_user.on_command(
    ("删除uid", "解绑uid", "删除UID", "解绑", "删除"),
    block=True,
)
async def delete_uid(bot: Bot, ev: Event):
    qid = ev.user_id
    uid = (ev.text or "").strip()
    if not uid:
        return await bot.send("[崩坏3] 你需要在解绑命令后面加入你的UID！")
    data = await GsBind.delete_uid(qid, ev.bot_id, uid, GAME_NAME)
    if data == 0:
        await bot.send(f"✅[崩坏3]删除uid[{uid}]成功!")
    else:
        await bot.send(f"❎[崩坏3]该uid[{uid}]不在已绑定列表中!")
