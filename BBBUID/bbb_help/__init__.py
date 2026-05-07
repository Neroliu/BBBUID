from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

sv_bbb_help = SV("崩坏3帮助")

HELP_TEXT = """【崩坏3】帮助
━━━━━━━━━━━━━━━━━━
📌 基础命令
  bbb绑定uid <uid> - 绑定UID
  bbb删除uid <uid> - 解绑UID
  bbb切换uid - 切换UID
📌 签到命令
  bbb签到 - 手动签到
  bbb开启自动签到 - 开启每日自动签到
  bbb关闭自动签到 - 关闭每日自动签到
📌 管理命令（管理员）
  bbb全部重签 - 重新执行所有签到
📌 WIKI查询
  bbb角色图鉴 <名称> - 查询角色信息
  bbb武器图鉴 <名称> - 查询武器信息
  bbb圣痕图鉴 <名称> - 查询圣痕信息
  bbb人偶图鉴 <名称> - 查询人偶信息
  bbb协同者图鉴 <名称> - 查询协同者信息
  bbbwiki <关键词> - 搜索WIKI
━━━━━━━━━━━━━━━━━━"""


@sv_bbb_help.on_fullmatch("帮助")
async def send_help(bot: Bot, ev: Event):
    await bot.send(HELP_TEXT)
