import re

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.server import on_core_start
from gsuid_core.utils.image.convert import convert_img

from .resource_update import update_all, get_local_detail, get_local_index
from .draw_wiki import screenshot_wiki
from .draw_role_wiki import draw_role_wiki
from .draw_weapon_wiki import draw_weapon_wiki
from .draw_partner_wiki import draw_partner_wiki
from .draw_stigma_wiki import draw_stigma_wiki
from ..bbb_alias.name_convert import alias_to_content_id

sv_bbb_wiki = SV("崩坏3WIKI")

CHANNEL_NAME_MAP = {
    18: "角色",
    20: "武器",
    19: "圣痕",
    21: "人偶",
    218: "协同者",
}


@on_core_start
async def bbb_wiki_start():
    try:
        logger.info("[崩坏3] [WIKI] 开始更新本地资源...")
        await update_all()
        logger.info("[崩坏3] [WIKI] 本地资源更新完成")
    except Exception as e:
        logger.error(f"[崩坏3] [WIKI] 资源更新失败: {e}")


def _find_local(channel_name: str, name: str) -> dict | None:
    index = get_local_index(channel_name)
    for cid, title in index.items():
        if title == name:
            return get_local_detail(channel_name, int(cid))
    for cid, title in index.items():
        if name in title:
            return get_local_detail(channel_name, int(cid))
    # Alias resolution for 角色 channel
    if channel_name == "角色":
        content_id = alias_to_content_id(name)
        if content_id:
            return get_local_detail(channel_name, int(content_id))
    return None


async def _send_wiki(bot: Bot, name: str, channel_id: int, label: str):
    if not name:
        return await bot.send(f"[崩坏3] 请输入{label}名称，例如: bbb{label}图鉴琪亚娜")
    logger.info(f"[崩坏3] [{label}图鉴] 查询: {name}")

    channel_name = CHANNEL_NAME_MAP[channel_id]
    detail = _find_local(channel_name, name)
    if detail:
        img = await screenshot_wiki(detail["id"])
        img = await convert_img(img)
        logger.info(f"[崩坏3] [{label}图鉴] {name} 本地缓存命中")
        await bot.send(img)
    else:
        await bot.send(f"[崩坏3] 未找到{label}: {name}")


@sv_bbb_wiki.on_prefix("角色图鉴")
async def send_role_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·♪☆★♥]+", ev.text)).strip()
    if not name:
        return await bot.send("[崩坏3] 请输入角色名称，例如: bbb角色图鉴琪亚娜")
    logger.info(f"[崩坏3] [角色图鉴] 查询: {name}")
    detail = _find_local("角色", name)
    if detail:
        img = await draw_role_wiki(detail)
        logger.info(f"[崩坏3] [角色图鉴] {name} 渲染完成")
        await bot.send(img)
    else:
        await bot.send(f"[崩坏3] 未找到角色: {name}")


@sv_bbb_wiki.on_prefix("武器图鉴")
async def send_weapon_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·☆★]+", ev.text)).strip()
    if not name:
        return await bot.send("[崩坏3] 请输入武器名称，例如: bbb武器图鉴苍雷星梭·初号协议")
    logger.info(f"[崩坏3] [武器图鉴] 查询: {name}")
    detail = _find_local("武器", name)
    if detail:
        img = await draw_weapon_wiki(detail)
        logger.info(f"[崩坏3] [武器图鉴] {name} 渲染完成")
        await bot.send(img)
    else:
        await bot.send(f"[崩坏3] 未找到武器: {name}")


@sv_bbb_wiki.on_prefix("圣痕图鉴")
async def send_stigma_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·☆★()（）]+", ev.text)).strip()
    if not name:
        return await bot.send("[崩坏3] 请输入圣痕名称，例如: bbb圣痕图鉴真理(下)")
    logger.info(f"[崩坏3] [圣痕图鉴] 查询: {name}")
    detail = _find_local("圣痕", name)
    if detail:
        img = await draw_stigma_wiki(detail)
        logger.info(f"[崩坏3] [圣痕图鉴] {name} 渲染完成")
        await bot.send(img)
    else:
        await bot.send(f"[崩坏3] 未找到圣痕: {name}")


@sv_bbb_wiki.on_prefix("人偶图鉴")
async def send_elf_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    await _send_wiki(bot, name, 21, "人偶")


@sv_bbb_wiki.on_prefix("协同者图鉴")
async def send_partner_wiki(bot: Bot, ev: Event):
    name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    if not name:
        return await bot.send("[崩坏3] 请输入协同者名称，例如: bbb协同者图鉴寻梦者")
    logger.info(f"[崩坏3] [协同者图鉴] 查询: {name}")
    detail = _find_local("协同者", name)
    if detail:
        img = await draw_partner_wiki(detail)
        logger.info(f"[崩坏3] [协同者图鉴] {name} 渲染完成")
        await bot.send(img)
    else:
        await bot.send(f"[崩坏3] 未找到协同者: {name}")


@sv_bbb_wiki.on_prefix(("崩坏3wiki", "崩坏3WIKI", "bbbwiki", "bbbWIKI"))
async def search_wiki(bot: Bot, ev: Event):
    keyword = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    if not keyword:
        return await bot.send("[崩坏3] 请输入搜索关键词，例如: bbbwiki琪亚娜")
    logger.info(f"[崩坏3] [WIKI搜索] 关键词: {keyword}")

    all_results = []
    for channel_name in CHANNEL_NAME_MAP.values():
        index = get_local_index(channel_name)
        for cid, title in index.items():
            if keyword in title:
                all_results.append({"title": title, "channel": channel_name})

    if not all_results:
        return await bot.send(f"[崩坏3] 未找到与「{keyword}」相关的内容")
    msg = f"搜索「{keyword}」找到 {len(all_results)} 条结果:\n"
    for i, r in enumerate(all_results[:10], 1):
        msg += f"\n{i}. [{r['channel']}] {r['title']}"
    if len(all_results) > 10:
        msg += f"\n\n...还有 {len(all_results) - 10} 条结果"
    await bot.send(msg)
