import re

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from .wiki_api import (
    find_content_by_name,
    get_content_detail,
    search_content,
)
from .draw_wiki import screenshot_wiki

sv_bbb_wiki = SV("崩坏3WIKI")


async def _send_wiki_img(bot: Bot, name: str, channel_id: int, label: str):
    if not name:
        return await bot.send(f"[崩坏3] 请输入{label}名称，例如: bbb{label}图鉴琪亚娜")
    logger.info(f"[崩坏3] [{label}图鉴] 查询: {name}")
    item = await find_content_by_name(name, channel_id)
    if not item:
        return await bot.send(f"[崩坏3] 未找到{label}: {name}")
    img = await screenshot_wiki(item["content_id"])
    img = await convert_img(img)
    logger.info(f"[崩坏3] [{label}图鉴] {name} 截图成功")
    await bot.send(img)


@sv_bbb_wiki.on_prefix("角色图鉴")
async def send_role_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·♪☆★♥]+", ev.text)).strip()
    await _send_wiki_img(bot, name, 18, "角色")


@sv_bbb_wiki.on_prefix("武器图鉴")
async def send_weapon_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·☆★]+", ev.text)).strip()
    await _send_wiki_img(bot, name, 20, "武器")


@sv_bbb_wiki.on_prefix("圣痕图鉴")
async def send_stigma_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·☆★()（）]+", ev.text)).strip()
    await _send_wiki_img(bot, name, 19, "圣痕")


@sv_bbb_wiki.on_prefix("人偶图鉴")
async def send_elf_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    await _send_wiki_img(bot, name, 21, "人偶")


@sv_bbb_wiki.on_prefix("协同者图鉴")
async def send_partner_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    await _send_wiki_img(bot, name, 218, "协同者")


@sv_bbb_wiki.on_prefix("崩坏3wiki", "崩坏3WIKI", "bbbwiki", "bbbWIKI")
async def search_wiki(bot: Bot, ev: Event):
    keyword = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    if not keyword:
        return await bot.send("[崩坏3] 请输入搜索关键词，例如: bbbwiki琪亚娜")
    logger.info(f"[崩坏3] [WIKI搜索] 关键词: {keyword}")
    results = await search_content(keyword)
    if not results:
        return await bot.send(f"[崩坏3] 未找到与「{keyword}」相关的内容")
    msg = f"搜索「{keyword}」找到 {len(results)} 条结果:\n"
    for i, r in enumerate(results[:10], 1):
        msg += f"\n{i}. [{r['channel_name']}] {r['title']}"
        if r["summary"]:
            msg += f" - {r['summary'][:30]}"
    if len(results) > 10:
        msg += f"\n\n...还有 {len(results) - 10} 条结果"
    await bot.send(msg)
