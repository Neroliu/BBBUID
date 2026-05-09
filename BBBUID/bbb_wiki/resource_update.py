import json
import re
from pathlib import Path

import httpx

from gsuid_core.logger import logger

from .wiki_api import get_channel_content_list, get_content_detail, parse_evaluation_from_detail, parse_weapon_data_from_detail, parse_stigma_data_from_detail, parse_enemy_data_from_detail, parse_enemy_data_from_detail
from ..utils.RESOURCE_PATH import CHANNEL_MAP, get_wiki_path
from ..bbb_alias.name_convert import build_char_meta_from_wiki

INDEX_FILE = "index.json"
ICON_SUFFIX = ".png"
EQUIP_ICONS_DIR = "equip_icons"
MATERIAL_ICONS_DIR = "material_icons"
STIGMA_EQUIP_ICONS_DIR = "stigma_equip_icons"
PORTRAIT_ICONS_DIR = "portrait_icons"
WALLPAPER_ICONS_DIR = "wallpaper_icons"


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


async def _download_icon(channel_name: str, content_id: int, url: str):
    if not url:
        return
    icon_path = get_wiki_path(channel_name) / f"{content_id}{ICON_SUFFIX}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                icon_path.write_bytes(resp.content)
                logger.debug(f"[崩坏3] [资源更新] 图标已保存: {icon_path.name}")
            else:
                logger.warning(f"[崩坏3] [资源更新] 下载图标失败 [{resp.status_code}]: {url}")
    except Exception as e:
        logger.warning(f"[崩坏3] [资源更新] 下载图标异常: {e}")


def _remove_icon(channel_name: str, content_id: int):
    icon_path = get_wiki_path(channel_name) / f"{content_id}{ICON_SUFFIX}"
    if icon_path.exists():
        icon_path.unlink()


def _get_equip_icons_dir(channel_name: str, content_id: int) -> Path:
    path = get_wiki_path(channel_name) / EQUIP_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_equipment_icons(channel_name: str, content_id: int, detail: dict):
    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    equipments = evaluation.get("equipments", [])
    if not equipments:
        return

    icons_dir = _get_equip_icons_dir(channel_name, content_id)
    async with httpx.AsyncClient() as client:
        idx = 0
        for eq_group in equipments:
            for eq in eq_group.get("equips", []):
                icon_url = eq.get("icon", "")
                if not icon_url:
                    idx += 1
                    continue
                icon_path = icons_dir / f"{idx}.png"
                idx += 1
                if icon_path.exists():
                    continue
                try:
                    resp = await client.get(icon_url, timeout=15)
                    if resp.status_code == 200:
                        icon_path.write_bytes(resp.content)
                    else:
                        logger.warning(f"[崩坏3] [资源更新] 装备图标下载失败 [{resp.status_code}]")
                except Exception as e:
                    logger.warning(f"[崩坏3] [资源更新] 装备图标下载异常: {e}")


def _remove_equipment_icons(channel_name: str, content_id: int):
    icons_dir = get_wiki_path(channel_name) / EQUIP_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()
        icons_dir.rmdir()


def _get_stigma_equip_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("圣痕") / STIGMA_EQUIP_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_stigma_equip_icons(content_id: int, detail: dict):
    stigma_data = detail.get("stigma_data") or parse_stigma_data_from_detail(detail)
    equipments = stigma_data.get("equipments", [])
    if not equipments:
        return

    icons_dir = _get_stigma_equip_icons_dir(content_id)
    async with httpx.AsyncClient() as client:
        idx = 0
        for eq_group in equipments:
            for eq in eq_group.get("equips", []):
                icon_url = eq.get("icon", "")
                if not icon_url:
                    idx += 1
                    continue
                icon_path = icons_dir / f"{idx}.png"
                idx += 1
                if icon_path.exists():
                    continue
                try:
                    resp = await client.get(icon_url, timeout=15)
                    if resp.status_code == 200:
                        icon_path.write_bytes(resp.content)
                    else:
                        logger.warning(f"[崩坏3] [资源更新] 圣痕配装图标下载失败 [{resp.status_code}]")
                except Exception as e:
                    logger.warning(f"[崩坏3] [资源更新] 圣痕配装图标下载异常: {e}")


def _remove_stigma_equip_icons(content_id: int):
    icons_dir = get_wiki_path("圣痕") / STIGMA_EQUIP_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()
        icons_dir.rmdir()


def _get_enemy_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("敌人") / EQUIP_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_enemy_icons(channel_name: str, content_id: int, detail: dict):
    enemy_data = detail.get("enemy_data") or parse_enemy_data_from_detail(detail)
    image_url = enemy_data.get("info", {}).get("image", "")
    if not image_url:
        return

    icons_dir = _get_enemy_icons_dir(content_id)
    icon_path = icons_dir / "monster.png"
    if icon_path.exists():
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url, timeout=15)
            if resp.status_code == 200:
                icon_path.write_bytes(resp.content)
                logger.debug(f"[崩坏3] [资源更新] 敌人怪物图已保存: {content_id}")
    except Exception as e:
        logger.warning(f"[崩坏3] [资源更新] 敌人怪物图下载异常: {e}")


def _remove_enemy_icons(content_id: int):
    icons_dir = get_wiki_path("敌人") / EQUIP_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()
        icons_dir.rmdir()


def get_local_stigma_equip_icons(content_id: int) -> dict[int, Path]:
    result: dict[int, Path] = {}
    icons_dir = get_wiki_path("圣痕") / STIGMA_EQUIP_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            if f.suffix == ".png":
                try:
                    idx = int(f.stem)
                    result[idx] = f
                except ValueError:
                    pass
    return result


def _extract_content_id_from_url(url: str) -> int | None:
    m = re.search(r"/content/(\d+)/detail", url)
    if m:
        return int(m.group(1))
    return None


def _get_material_icons_dir() -> Path:
    path = get_wiki_path("武器") / MATERIAL_ICONS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_material_icons(detail: dict):
    weapon_data = detail.get("weapon_data") or parse_weapon_data_from_detail(detail)
    icons_dir = _get_material_icons_dir()

    # Collect all content_ids that need icons
    content_ids: dict[int, str] = {}  # cid -> name (for logging)

    # From forging
    forging = weapon_data.get("forging", {})
    for item in forging.get("material", []):
        cid = _extract_content_id_from_url(item.get("url", ""))
        if cid:
            content_ids[cid] = item.get("name", "")
        icon_url = item.get("icon", "")
        if icon_url and cid:
            await _download_single_icon(icons_dir, cid, icon_url)

    for item in forging.get("otherMaterial", []):
        cid = _extract_content_id_from_url(item.get("url", ""))
        if cid:
            content_ids[cid] = item.get("name", "")

    # From evolution materials
    for level_data in weapon_data.get("materials", []):
        for mat in level_data.get("material", []):
            cid = _extract_content_id_from_url(mat.get("url", ""))
            if cid:
                content_ids[cid] = mat.get("name", "")

    # Download missing icons by fetching content detail for icon URL
    async with httpx.AsyncClient() as client:
        for cid, name in content_ids.items():
            icon_path = icons_dir / f"{cid}.png"
            if icon_path.exists():
                continue
            try:
                detail_data = await get_content_detail(cid)
                if not detail_data:
                    continue
                icon_url = detail_data.get("icon", "")
                if not icon_url:
                    continue
                resp = await client.get(icon_url, timeout=15)
                if resp.status_code == 200:
                    icon_path.write_bytes(resp.content)
                    logger.debug(f"[崩坏3] [资源更新] 材料图标已保存: {name} ({cid})")
            except Exception as e:
                logger.warning(f"[崩坏3] [资源更新] 材料图标下载异常 [{cid}]: {e}")


async def _download_single_icon(icons_dir: Path, cid: int, icon_url: str):
    icon_path = icons_dir / f"{cid}.png"
    if icon_path.exists():
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(icon_url, timeout=15)
            if resp.status_code == 200:
                icon_path.write_bytes(resp.content)
    except Exception as e:
        logger.warning(f"[崩坏3] [资源更新] 材料图标下载异常 [{cid}]: {e}")


def _remove_material_icons():
    icons_dir = get_wiki_path("武器") / MATERIAL_ICONS_DIR
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()
        icons_dir.rmdir()


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
                icon_url = detail.get("icon", "")
                if icon_url:
                    await _download_icon(channel_name, item["content_id"], icon_url)
                if channel_name == "角色":
                    await _download_equipment_icons(channel_name, item["content_id"], detail)
                elif channel_name == "武器":
                    await _download_material_icons(detail)
                elif channel_name == "圣痕":
                    await _download_stigma_equip_icons(item["content_id"], detail)
                    await _download_material_icons(detail)
                elif channel_name == "敌人":
                    await _download_enemy_icons(channel_name, item["content_id"], detail)
                elif channel_name == "立绘":
                    await _download_portrait_icons(item["content_id"], detail)
                elif channel_name == "壁纸":
                    await _download_wallpaper_icons(item["content_id"], detail)

    for cid in removed:
        json_path = get_wiki_path(channel_name) / f"{cid}.json"
        if json_path.exists():
            json_path.unlink()
        _remove_icon(channel_name, int(cid))
        _remove_equipment_icons(channel_name, int(cid))
        if channel_name == "圣痕":
            _remove_stigma_equip_icons(int(cid))
        elif channel_name == "敌人":
            _remove_enemy_icons(int(cid))
        elif channel_name == "立绘":
            _remove_portrait_icons(int(cid))
        elif channel_name == "壁纸":
            _remove_wallpaper_icons(int(cid))

    _save_index(channel_name, new_index)
    logger.info(f"[崩坏3] [资源更新] {channel_name} 更新完成")


async def update_all():
    for name, cid in CHANNEL_MAP.items():
        try:
            await update_channel(name, cid)
        except Exception as e:
            logger.error(f"[崩坏3] [资源更新] {name} 更新失败: {e}")

    # Rebuild alias index from wiki data
    try:
        build_char_meta_from_wiki()
    except Exception as e:
        logger.error(f"[崩坏3] [资源更新] 别名索引生成失败: {e}")


def get_local_detail(channel_name: str, content_id: int) -> dict | None:
    return _load_detail(channel_name, content_id)


def get_local_index(channel_name: str) -> dict:
    return _load_index(channel_name)


def get_local_icon(channel_name: str, content_id: int) -> Path | None:
    icon_path = get_wiki_path(channel_name) / f"{content_id}{ICON_SUFFIX}"
    if icon_path.exists():
        return icon_path
    return None


def get_local_equip_icons(channel_name: str, content_id: int) -> dict[int, Path]:
    result: dict[int, Path] = {}
    icons_dir = get_wiki_path(channel_name) / EQUIP_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            if f.suffix == ".png":
                try:
                    idx = int(f.stem)
                    result[idx] = f
                except ValueError:
                    pass
    return result


def get_local_material_icon(content_id: int) -> Path | None:
    icon_path = get_wiki_path("武器") / MATERIAL_ICONS_DIR / f"{content_id}.png"
    if icon_path.exists():
        return icon_path
    return None


async def save_material_icon(content_id: int, icon_url: str) -> Path | None:
    icons_dir = get_wiki_path("武器") / MATERIAL_ICONS_DIR
    icons_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icons_dir / f"{content_id}.png"
    if icon_path.exists():
        return icon_path
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(icon_url, timeout=15)
            if resp.status_code == 200:
                icon_path.write_bytes(resp.content)
                return icon_path
    except Exception as e:
        logger.warning(f"[崩坏3] [资源更新] 材料图标下载异常 [{content_id}]: {e}")
    return None


def get_local_enemy_image(content_id: int) -> Path | None:
    icon_path = get_wiki_path("敌人") / EQUIP_ICONS_DIR / str(content_id) / "monster.png"
    if icon_path.exists():
        return icon_path
    return None


# --- Portrait (立绘) ---


def _get_portrait_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("立绘") / PORTRAIT_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_portrait_icons(content_id: int, detail: dict):
    icons_dir = _get_portrait_icons_dir(content_id)
    all_urls = set()
    for section in detail.get("contents", []):
        html = section.get("text", "")
        urls = re.findall(r'https?://[^\s"<>]+[.]png', html)
        all_urls.update(urls)

    async with httpx.AsyncClient() as client:
        idx = 0
        for url in sorted(all_urls):
            try:
                resp = await client.head(url, timeout=5, follow_redirects=True)
                cl = int(resp.headers.get("content-length", 0))
                if cl < 30000:
                    continue
            except Exception:
                continue

            icon_path = icons_dir / f"{idx}.png"
            idx += 1
            if icon_path.exists():
                continue
            try:
                resp = await client.get(url, timeout=15)
                if resp.status_code == 200:
                    icon_path.write_bytes(resp.content)
                    logger.debug(f"[崩坏3] [资源更新] 立绘图片已保存: {content_id}/{icon_path.name}")
            except Exception as e:
                logger.warning(f"[崩坏3] [资源更新] 立绘图片下载异常: {e}")


def _remove_portrait_icons(content_id: int):
    icons_dir = _get_portrait_icons_dir(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()


def get_local_portrait_icons(content_id: int) -> dict[int, Path]:
    result: dict[int, Path] = {}
    icons_dir = get_wiki_path("立绘") / PORTRAIT_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            if f.suffix == ".png":
                try:
                    idx = int(f.stem)
                    result[idx] = f
                except ValueError:
                    pass
    return result


# --- Wallpaper (壁纸) ---


def _get_wallpaper_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("壁纸") / WALLPAPER_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _download_wallpaper_icons(content_id: int, detail: dict):
    icons_dir = _get_wallpaper_icons_dir(content_id)
    all_urls = set()
    for section in detail.get("contents", []):
        html = section.get("text", "")
        urls = re.findall(r'https?://[^\s"<>]+[.]png', html)
        all_urls.update(urls)

    async with httpx.AsyncClient() as client:
        idx = 0
        for url in sorted(all_urls):
            try:
                resp = await client.head(url, timeout=5, follow_redirects=True)
                cl = int(resp.headers.get("content-length", 0))
                if cl < 50000:
                    continue
            except Exception:
                continue

            icon_path = icons_dir / f"{idx}.png"
            idx += 1
            if icon_path.exists():
                continue
            try:
                resp = await client.get(url, timeout=30)
                if resp.status_code == 200:
                    icon_path.write_bytes(resp.content)
                    logger.debug(f"[崩坏3] [资源更新] 壁纸已保存: {content_id}/{icon_path.name}")
            except Exception as e:
                logger.warning(f"[崩坏3] [资源更新] 壁纸下载异常: {e}")


def _remove_wallpaper_icons(content_id: int):
    icons_dir = _get_wallpaper_icons_dir(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()


def get_local_wallpaper_icons(content_id: int) -> dict[int, Path]:
    result: dict[int, Path] = {}
    icons_dir = get_wiki_path("壁纸") / WALLPAPER_ICONS_DIR / str(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            if f.suffix == ".png":
                try:
                    idx = int(f.stem)
                    result[idx] = f
                except ValueError:
                    pass
    return result
