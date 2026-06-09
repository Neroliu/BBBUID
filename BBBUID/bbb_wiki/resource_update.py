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
ICONS_DIR = "icons"  # Subdirectory for cached icons
EQUIP_ICONS_DIR = "equip_icons"
MATERIAL_ICONS_DIR = "material_icons"
STIGMA_EQUIP_ICONS_DIR = "stigma_equip_icons"
PORTRAIT_ICONS_DIR = "portrait_icons"
WALLPAPER_ICONS_DIR = "wallpaper_icons"
WALLPAPER_LINKS_DIR = "wallpaper_links"
WALLPAPER_CACHE_DIR = "wallpaper_cache"
COMPRESSED_WALLPAPER_CACHE_DIR = "compressed_cache"


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
    icons_dir = get_wiki_path(channel_name) / ICONS_DIR
    icons_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icons_dir / f"{content_id}{ICON_SUFFIX}"
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
    icon_path = get_wiki_path(channel_name) / ICONS_DIR / f"{content_id}{ICON_SUFFIX}"
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


async def _check_missing_wallpaper_links(items: list):
    """Check and cache wallpaper links for items that don't have them yet."""
    for item in items:
        cid = item["content_id"]
        links_file = get_wiki_path("壁纸") / WALLPAPER_LINKS_DIR / f"{cid}.json"
        if links_file.exists():
            continue
        # Try loading local detail first, fall back to API
        detail = _load_detail("壁纸", cid)
        if not detail:
            detail = await get_content_detail(cid)
        if detail:
            await _cache_wallpaper_links(cid, detail)


def _cleanup_all_old_wallpaper_icons(items: list):
    """Remove old wallpaper_icons directories for all current items."""
    for item in items:
        _remove_wallpaper_icons(item["content_id"])


def _cleanup_wallpaper_residuals():
    """Remove all residual files in the wallpaper directory that are no longer used."""
    wp_path = get_wiki_path("壁纸")
    # Remove icons/ directory (unused by wallpaper channel)
    icons_dir = wp_path / "icons"
    if icons_dir.exists():
        _remove_dir(icons_dir)
    # Remove all <cid>.json detail files (keep index.json)
    for json_file in wp_path.glob("*.json"):
        if json_file.name == "index.json":
            continue
        json_file.unlink()
    # Remove all old wallpaper_icons/ directories
    wp_icons_dir = wp_path / WALLPAPER_ICONS_DIR
    if wp_icons_dir.exists():
        _remove_dir(wp_icons_dir)
    # Remove any leftover .png files in root (legacy files from old logic)
    for png_file in wp_path.glob("*.png"):
        png_file.unlink()


async def update_channel(channel_name: str, channel_id: int):
    logger.info(f"[崩坏3] [资源更新] 开始更新 {channel_name}...")

    # 立绘频道：从角色频道列表获取content_id，清理并下载立绘
    if channel_name == "立绘":
        await _update_portraits()
        return

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
        # Check for missing icons even if no data update needed
        await _check_missing_icons(channel_name, channel_id, items)
        # Wallpaper: always check links and clean old icons even if no data change
        if channel_name == "壁纸":
            await _check_missing_wallpaper_links(items)
            _cleanup_all_old_wallpaper_icons(items)
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
                elif channel_name == "壁纸":
                    await _cache_wallpaper_links(item["content_id"], detail)
                    _remove_wallpaper_icons(item["content_id"])
                    _remove_file(get_wiki_path("壁纸") / f'{item["content_id"]}.json')

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
        elif channel_name == "壁纸":
            _remove_wallpaper_links(int(cid))
            _remove_dir(get_wiki_path("壁纸") / WALLPAPER_CACHE_DIR / str(cid))
            _remove_dir(get_wiki_path("壁纸") / COMPRESSED_WALLPAPER_CACHE_DIR / str(cid))
            _remove_wallpaper_icons(int(cid))

    _save_index(channel_name, new_index)
    logger.info(f"[崩坏3] [资源更新] {channel_name} 更新完成")


async def _check_missing_icons(channel_name: str, channel_id: int, items: list):
    """Check and download missing icons for existing data."""
    missing_count = 0
    icons_dir = get_wiki_path(channel_name) / ICONS_DIR
    icons_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        cid = item["content_id"]
        icon_path = icons_dir / f"{cid}{ICON_SUFFIX}"
        if icon_path.exists():
            continue

        # Load detail to get icon URL
        detail = _load_detail(channel_name, cid)
        if not detail:
            continue

        icon_url = detail.get("icon", "")
        if not icon_url:
            continue

        missing_count += 1
        await _download_icon(channel_name, cid, icon_url)

    if missing_count > 0:
        logger.info(f"[崩坏3] [资源更新] {channel_name} 补充下载 {missing_count} 个缺失图标")


async def _update_portraits():
    """立绘频道更新：从角色频道列表获取content_id，清理并下载660x660立绘。"""
    logger.info("[崩坏3] [资源更新] 开始更新立绘...")
    # 获取角色频道列表
    char_items = await get_channel_content_list(CHANNEL_MAP["角色"])
    if not char_items:
        logger.warning("[崩坏3] [资源更新] 立绘更新失败: 角色列表为空")
        return

    valid_cids = {str(item["content_id"]) for item in char_items}
    _cleanup_portrait_cache(valid_cids)
    await _check_missing_portraits(char_items)
    logger.info(f"[崩坏3] [资源更新] 立绘更新完成 ({len(char_items)} 个角色)")


async def update_all():
    for name, cid in CHANNEL_MAP.items():
        try:
            await update_channel(name, cid)
        except Exception as e:
            logger.error(f"[崩坏3] [资源更新] {name} 更新失败: {e}")

    # Pre-download 3 random wallpaper originals
    try:
        await _prefetch_wallpaper_originals()
    except Exception as e:
        logger.error(f"[崩坏3] [资源更新] 壁纸预下载失败: {e}")

    # Clean up residual wallpaper files (icons dir, old detail JSONs, etc.)
    try:
        _cleanup_wallpaper_residuals()
    except Exception as e:
        logger.error(f"[崩坏3] [资源更新] 壁纸残留清理失败: {e}")

    # Enforce wallpaper cache limits
    try:
        await _enforce_wallpaper_cache_limits()
    except Exception as e:
        logger.error(f"[崩坏3] [资源更新] 壁纸缓存清理失败: {e}")

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
    icon_path = get_wiki_path(channel_name) / ICONS_DIR / f"{content_id}{ICON_SUFFIX}"
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


def _cleanup_portrait_cache(valid_cids: set[str]):
    """清理立绘缓存：淘汰不在valid_cids中的目录，清理非portrait.png文件。"""
    import shutil

    portrait_base = get_wiki_path("立绘") / PORTRAIT_ICONS_DIR
    if not portrait_base.exists():
        return
    evicted = 0
    cleaned = 0
    for cid_dir in list(portrait_base.iterdir()):
        if not cid_dir.is_dir() or cid_dir.name.startswith("@"):
            continue
        # 淘汰不在当前角色列表中的缓存目录
        if cid_dir.name not in valid_cids:
            shutil.rmtree(cid_dir, ignore_errors=True)
            evicted += 1
            continue
        # 清理非portrait.png的文件和非预期目录
        for f in list(cid_dir.iterdir()):
            if f.is_dir():
                shutil.rmtree(f, ignore_errors=True)
                cleaned += 1
            elif f.name != "portrait.png":
                f.unlink()
                cleaned += 1
    if evicted > 0 or cleaned > 0:
        logger.info(f"[崩坏3] [资源更新] 立绘缓存清理: 淘汰 {evicted} 个过期, 清理 {cleaned} 个多余文件")


def _get_portrait_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("立绘") / PORTRAIT_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _check_missing_portraits(items: list):
    """检查并补充缺失的角色立绘缓存。"""
    missing_count = 0
    for item in items:
        cid = item["content_id"]
        portrait_path = _get_portrait_icons_dir(cid) / "portrait.png"
        if portrait_path.exists():
            continue
        # 优先从本地缓存读取detail，不存在则从API获取
        detail = _load_detail("角色", cid)
        if not detail:
            detail = await get_content_detail(cid)
        if not detail:
            continue
        missing_count += 1
        await _download_portrait(cid, detail)
    if missing_count > 0:
        logger.info(f"[崩坏3] [资源更新] 补充下载 {missing_count} 个缺失立绘")


async def _download_portrait(content_id: int, detail: dict):
    """从角色详情页HTML中提取660x660立绘图并下载。"""
    from PIL import Image as PILImage
    from io import BytesIO

    all_urls = set()
    for section in detail.get("contents", []):
        html = section.get("text", "")
        urls = re.findall(r'https?://[^\s"<>]+[.]png', html)
        all_urls.update(urls)

    icons_dir = _get_portrait_icons_dir(content_id)
    portrait_path = icons_dir / "portrait.png"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in sorted(all_urls):
            # 只检查 uploadstatic.mihoyo.com 的大图
            if "uploadstatic.mihoyo.com" not in url:
                continue
            try:
                resp = await client.head(url, timeout=5)
                cl = int(resp.headers.get("content-length", 0))
                if cl < 50000:
                    continue
            except Exception:
                continue

            try:
                resp = await client.get(url, timeout=15)
                if resp.status_code != 200:
                    continue
                img = PILImage.open(BytesIO(resp.content))
                if img.size == (660, 660):
                    portrait_path.write_bytes(resp.content)
                    logger.debug(f"[崩坏3] [资源更新] 立绘已保存: {content_id}/portrait.png")
                    return
            except Exception:
                continue

    logger.warning(f"[崩坏3] [资源更新] 未找到660x660立绘: {content_id}")


def _remove_portrait_icons(content_id: int):
    import shutil
    icons_dir = _get_portrait_icons_dir(content_id)
    if icons_dir.exists():
        shutil.rmtree(icons_dir, ignore_errors=True)


def get_local_portrait(content_id: int) -> Path | None:
    portrait_path = get_wiki_path("立绘") / PORTRAIT_ICONS_DIR / str(content_id) / "portrait.png"
    if portrait_path.exists():
        return portrait_path
    return None


# --- Wallpaper (壁纸) ---


def _remove_dir(path: Path):
    """Remove a directory and all its contents (handles @eaDir etc)."""
    import shutil
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _remove_file(path: Path):
    """Remove a single file."""
    if path.exists():
        path.unlink()


def _get_wallpaper_links_dir() -> Path:
    path = get_wiki_path("壁纸") / WALLPAPER_LINKS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_wallpaper_cache_dir(content_id: int) -> Path:
    path = get_wiki_path("壁纸") / WALLPAPER_CACHE_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_compressed_cache_dir(content_id: int) -> Path:
    path = get_wiki_path("壁纸") / COMPRESSED_WALLPAPER_CACHE_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _cache_wallpaper_links(content_id: int, detail: dict):
    """Extract wallpaper URLs from detail, validate them, and cache valid ones."""
    links_dir = _get_wallpaper_links_dir()
    all_urls = set()
    for section in detail.get("contents", []):
        urls = re.findall(r"https?://[^\s\"<>]+[.]png", section.get("text", ""))
        all_urls.update(urls)

    # Filter: only large images (>= 500KB), then validate
    valid_urls = set()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in sorted(all_urls):
            try:
                resp = await client.head(url, timeout=5)
                if resp.status_code != 200:
                    continue
                cl = int(resp.headers.get("content-length", 0))
                if cl < 50000:
                    continue
                valid_urls.add(url)
            except Exception:
                logger.debug(f"[崩坏3] [资源更新] 壁纸链接不可达: {url}")

    link_file = links_dir / f"{content_id}.json"
    link_file.write_text(
        json.dumps(sorted(valid_urls), ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug(f"[崩坏3] [资源更新] 壁纸链接已缓存: {content_id} ({len(valid_urls)} valid urls)")

def _remove_wallpaper_links(content_id: int):
    link_file = get_wiki_path("壁纸") / WALLPAPER_LINKS_DIR / f"{content_id}.json"
    if link_file.exists():
        link_file.unlink()


def _get_wallpaper_icons_dir(content_id: int) -> Path:
    path = get_wiki_path("壁纸") / WALLPAPER_ICONS_DIR / str(content_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_wallpaper_icons(content_id: int):
    icons_dir = _get_wallpaper_icons_dir(content_id)
    if icons_dir.exists():
        for f in icons_dir.iterdir():
            f.unlink()


async def _cleanup_broken_wallpaper_links():
    """Validate cached wallpaper links and remove broken ones."""
    links_dir = get_wiki_path("壁纸") / WALLPAPER_LINKS_DIR
    if not links_dir.exists():
        return
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for link_file in links_dir.glob("*.json"):
            try:
                urls = json.loads(link_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            valid = []
            for url in urls:
                try:
                    resp = await client.head(url, timeout=5)
                    if resp.status_code == 200:
                        valid.append(url)
                except Exception:
                    pass
            if not valid:
                link_file.unlink()
                logger.debug(f"[崩坏3] [资源更新] 壁纸链接全部失效，已清理: {link_file.name}")
            elif len(valid) < len(urls):
                link_file.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
                logger.debug(f"[崩坏3] [资源更新] 壁纸链接部分失效: {link_file.name} ({len(valid)}/{len(urls)} valid)")


async def _prefetch_wallpaper_originals():
    import random as _random
    wp_base = get_wiki_path("壁纸")
    links_dir = wp_base / WALLPAPER_LINKS_DIR
    if not links_dir.exists(): return
    candidates = []
    for lf in links_dir.glob("*.json"):
        try: cid = int(lf.stem)
        except: continue
        cd = _get_wallpaper_cache_dir(cid)
        if cd.exists() and any(cd.glob("*.png")): continue
        try: urls = json.loads(lf.read_text(encoding="utf-8"))
        except: continue
        for ui, u in enumerate(urls): candidates.append((cid, ui, u))
    if not candidates: return
    _random.shuffle(candidates)
    dl = 0
    for cid, ui, u in candidates[:3]:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as cl:
                r = await cl.get(u, timeout=15)
                if r.status_code != 200: continue
                from io import BytesIO; from PIL import Image as PI
                img = PI.open(BytesIO(r.content)).convert("RGBA")
                if img.width < 800: continue
                cd = _get_wallpaper_cache_dir(cid); cd.mkdir(parents=True, exist_ok=True)
                cp = cd / f"{ui}.png"; img.save(str(cp), "PNG")
                dl += 1
        except: pass
    if dl > 0:
        logger.info(f"[崩坏3] [资源更新] 预下载了 {dl} 张壁纸原图")
        from ..bbb_config.bbb_config import BBB_CONFIG
        mc = int(BBB_CONFIG.get_config("WallpaperCacheCount").data)
        ms = int(BBB_CONFIG.get_config("WallpaperCacheSizeMB").data) * 1024 * 1024
        _enforce_dir_limits(wp_base / WALLPAPER_CACHE_DIR, mc, ms)

async def _enforce_wallpaper_cache_limits():
    """Enforce wallpaper cache count and size limits, and clean up broken links."""
    from ..bbb_config.bbb_config import BBB_CONFIG
    wp_base = get_wiki_path("壁纸")

    # --- Clean up broken wallpaper links ---
    await _cleanup_broken_wallpaper_links()

    # --- Compressed wallpaper cache limits ---
    comp_dir = wp_base / COMPRESSED_WALLPAPER_CACHE_DIR
    if comp_dir.exists():
        max_comp_count = int(BBB_CONFIG.get_config("CompressedWallpaperCacheCount").data)
        max_comp_size = int(BBB_CONFIG.get_config("CompressedWallpaperCacheSizeMB").data) * 1024 * 1024
        _enforce_dir_limits(comp_dir, max_comp_count, max_comp_size)

    # --- Original wallpaper cache limits ---
    cache_dir = wp_base / WALLPAPER_CACHE_DIR
    if cache_dir.exists():
        max_cache_count = int(BBB_CONFIG.get_config("WallpaperCacheCount").data)
        max_cache_size = int(BBB_CONFIG.get_config("WallpaperCacheSizeMB").data) * 1024 * 1024
        _enforce_dir_limits(cache_dir, max_cache_count, max_cache_size)


def _enforce_dir_limits(base_dir: Path, max_count: int, max_size: int):
    """Enforce count and size limits on files under base_dir (recursive).
    Removes oldest files first when limits are exceeded."""
    files = sorted(base_dir.rglob("*.*"), key=lambda f: f.stat().st_mtime)
    files = [f for f in files if f.suffix in (".png", ".jpg", ".jpeg")]
    total_size = sum(f.stat().st_size for f in files)

    # Remove by count
    while len(files) > max_count:
        f = files.pop(0)
        f.unlink()
        total_size -= f.stat().st_size if f.exists() else 0

    # Remove by size
    while total_size > max_size and files:
        f = files.pop(0)
        sz = f.stat().st_size if f.exists() else 0
        f.unlink()
        total_size -= sz

    # Cleanup empty dirs
    for d in sorted(base_dir.iterdir(), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


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
