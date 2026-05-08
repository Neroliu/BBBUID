import json
from pathlib import Path

from gsuid_core.logger import logger

from .wiki_api import get_channel_content_list, get_content_detail
from ..utils.RESOURCE_PATH import CHANNEL_MAP, get_wiki_path

INDEX_FILE = "index.json"


def _load_index(channel_name: str) -> dict:
    path = get_wiki_path(channel_name) / INDEX_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_index(channel_name: str, data: dict):
    path = get_wiki_path(channel_name) / INDEX_FILE
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_detail(channel_name: str, content_id: int) -> dict | None:
    path = get_wiki_path(channel_name) / f"{content_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_detail(channel_name: str, content_id: int, data: dict):
    path = get_wiki_path(channel_name) / f"{content_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def update_channel(channel_name: str, channel_id: int):
    logger.info(f"[崩坏3] [资源更新] 开始更新 {channel_name}...")
    items = await get_channel_content_list(channel_id)
    if not items:
        logger.warning(f"[崩坏3] [资源更新] {channel_name} 获取列表为空")
        return

    old_index = _load_index(channel_name)
    new_index = {str(i["content_id"]): i["title"] for i in items}

    added = [cid for cid in new_index if cid not in old_index]
    removed = [cid for cid in old_index if cid not in new_index]
    updated = []

    for item in items:
        cid = str(item["content_id"])
        old_item = old_index.get(cid)
        if old_item is None:
            updated.append(cid)
        elif old_item != item["title"]:
            updated.append(cid)

    total = len(added) + len(updated)
    if not total and not removed:
        logger.info(f"[崩坏3] [资源更新] {channel_name} 无更新 ({len(items)} 条)")
        return

    logger.info(f"[崩坏3] [资源更新] {channel_name}: 新增{len(added)} 更新{len(updated)} 删除{len(removed)}")

    for item in items:
        cid = str(item["content_id"])
        if cid in added or cid in updated:
            detail = await get_content_detail(item["content_id"])
            if detail:
                _save_detail(channel_name, item["content_id"], detail)

    for cid in removed:
        path = get_wiki_path(channel_name) / f"{cid}.json"
        if path.exists():
            path.unlink()

    _save_index(channel_name, new_index)
    logger.info(f"[崩坏3] [资源更新] {channel_name} 更新完成")


async def update_all():
    for name, cid in CHANNEL_MAP.items():
        try:
            await update_channel(name, cid)
        except Exception as e:
            logger.error(f"[崩坏3] [资源更新] {name} 更新失败: {e}")


def get_local_detail(channel_name: str, content_id: int) -> dict | None:
    return _load_detail(channel_name, content_id)


def get_local_index(channel_name: str) -> dict:
    return _load_index(channel_name)
