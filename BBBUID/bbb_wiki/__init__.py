import re

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from .wiki_api import (
    CHANNEL_MAP,
    find_content_by_name,
    get_channel_content_list,
    get_content_detail,
    search_content,
)

sv_bbb_wiki = SV("崩坏3WIKI")


def _format_detail(detail: dict) -> str:
    title = detail["title"]
    summary = detail.get("summary", "")
    basic = detail.get("basic_info", {})
    sections = detail.get("contents", [])

    msg = f"【{title}】"
    if summary:
        msg += f"\n{summary}"
    if basic:
        msg += "\n\n── 基本信息 ──"
        for k, v in basic.items():
            msg += f"\n  {k}: {v}"
    if sections:
        msg += f"\n\n── 内容板块 ({len(sections)}) ──"
        for s in sections:
            msg += f"\n  · {s['name']}"
    return msg


@sv_bbb_wiki.on_prefix("角色图鉴")
async def send_role_wiki(bot: Bot, ev: Event):
    char_name = " ".join(re.findall("[a-zA-Z_一-龥·♪☆★♥]+", ev.text)).strip()
    if not char_name:
        return await bot.send("[崩坏3] 请输入角色名称，例如: bbb角色图鉴琪亚娜")
    logger.info(f"[崩坏3] [角色图鉴] 查询: {char_name}")
    item = await find_content_by_name(char_name, 18)
    if not item:
        return await bot.send(f"[崩坏3] 未找到角色: {char_name}")
    detail = await get_content_detail(item["content_id"])
    if not detail:
        return await bot.send(f"[崩坏3] 获取角色详情失败: {char_name}")
    await bot.send(_format_detail(detail))


@sv_bbb_wiki.on_prefix("武器图鉴")
async def send_weapon_wiki(bot: Bot, ev: Event):
    weapon_name = " ".join(re.findall("[a-zA-Z_一-龥·☆★]+", ev.text)).strip()
    if not weapon_name:
        return await bot.send("[崩坏3] 请输入武器名称，例如: bbb武器图鉴苍雷星梭")
    logger.info(f"[崩坏3] [武器图鉴] 查询: {weapon_name}")
    item = await find_content_by_name(weapon_name, 20)
    if not item:
        return await bot.send(f"[崩坏3] 未找到武器: {weapon_name}")
    detail = await get_content_detail(item["content_id"])
    if not detail:
        return await bot.send(f"[崩坏3] 获取武器详情失败: {weapon_name}")
    await bot.send(_format_detail(detail))


@sv_bbb_wiki.on_prefix("圣痕图鉴")
async def send_stigma_wiki(bot: Bot, ev: Event):
    stigma_name = " ".join(re.findall("[a-zA-Z_一-龥·☆★()（）]+", ev.text)).strip()
    if not stigma_name:
        return await bot.send("[崩坏3] 请输入圣痕名称，例如: bbb圣痕图鉴琪亚娜·霓裳")
    logger.info(f"[崩坏3] [圣痕图鉴] 查询: {stigma_name}")
    item = await find_content_by_name(stigma_name, 19)
    if not item:
        return await bot.send(f"[崩坏3] 未找到圣痕: {stigma_name}")
    detail = await get_content_detail(item["content_id"])
    if not detail:
        return await bot.send(f"[崩坏3] 获取圣痕详情失败: {stigma_name}")
    await bot.send(_format_detail(detail))


@sv_bbb_wiki.on_prefix("人偶图鉴")
async def send_elf_wiki(bot: Bot, ev: Event):
    elf_name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    if not elf_name:
        return await bot.send("[崩坏3] 请输入人偶名称，例如: bbb人偶图鉴重装小兔")
    logger.info(f"[崩坏3] [人偶图鉴] 查询: {elf_name}")
    item = await find_content_by_name(elf_name, 21)
    if not item:
        return await bot.send(f"[崩坏3] 未找到人偶: {elf_name}")
    detail = await get_content_detail(item["content_id"])
    if not detail:
        return await bot.send(f"[崩坏3] 获取人偶详情失败: {elf_name}")
    await bot.send(_format_detail(detail))


@sv_bbb_wiki.on_prefix("协同者图鉴")
async def send_partner_wiki(bot: Bot, ev: Event):
    partner_name = " ".join(re.findall("[a-zA-Z_一-龥·]+", ev.text)).strip()
    if not partner_name:
        return await bot.send("[崩坏3] 请输入协同者名称，例如: bbb协同者图鉴松雀")
    logger.info(f"[崩坏3] [协同者图鉴] 查询: {partner_name}")
    item = await find_content_by_name(partner_name, 218)
    if not item:
        return await bot.send(f"[崩坏3] 未找到协同者: {partner_name}")
    detail = await get_content_detail(item["content_id"])
    if not detail:
        return await bot.send(f"[崩坏3] 获取协同者详情失败: {partner_name}")
    await bot.send(_format_detail(detail))


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
