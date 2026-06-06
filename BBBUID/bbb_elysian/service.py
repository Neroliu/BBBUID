import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from gsuid_core.logger import logger

from .models import MatchResult, QueryResult, RefreshSummary
from .store import STORE, display_timestamp, write_json_atomic
from ..bbb_config.bbb_config import BBB_CONFIG
from ..utils.RESOURCE_PATH import ELYSIAN_IMAGE_CACHE_PATH, ELYSIAN_INDEX_PATH, ELYSIAN_META_PATH

DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/MskTmi/ElysianRealm-Data/master/dist/elysian-realm-index.json"
DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/MskTmi/ElysianRealm-Data/master"

_update_lock = asyncio.Lock()
_image_locks: dict[str, asyncio.Lock] = {}


def _get_config(name: str, default: Any) -> Any:
    try:
        return BBB_CONFIG.get_config(name).data
    except Exception:
        return default


def strategy_enabled() -> bool:
    return bool(_get_config("ElysianStrategyEnabled", True))


def show_source() -> bool:
    return bool(_get_config("ElysianStrategyShowSource", True))


def _with_proxy(url: str) -> str:
    prefix = str(_get_config("ElysianStrategyProxyPrefix", "")).strip()
    if not prefix:
        return url
    return f"{prefix.rstrip('/')}/{url}"


def _load_meta() -> dict[str, Any]:
    if not ELYSIAN_META_PATH.exists():
        return {}
    try:
        data = json.loads(ELYSIAN_META_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"[崩坏3] [乐土攻略] 读取缓存元信息失败: {e}")
        return {}


def _save_meta(meta: dict[str, Any]):
    write_json_atomic(ELYSIAN_META_PATH, meta)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _index_expired() -> bool:
    try:
        raw_cache_hours = _get_config("ElysianStrategyCacheHours", 6)
        cache_hours = 6 if raw_cache_hours is None else max(0, int(raw_cache_hours))
    except (TypeError, ValueError):
        cache_hours = 6
    fetched_at = _parse_dt(_load_meta().get("fetched_at"))
    if not fetched_at:
        return True
    return datetime.now(timezone.utc) - fetched_at > timedelta(hours=cache_hours)


async def refresh_strategy_index() -> RefreshSummary:
    if _update_lock.locked():
        return RefreshSummary(success=False, error="已有乐土攻略索引更新任务进行中。")

    async with _update_lock:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(_with_proxy(DEFAULT_INDEX_URL), timeout=30)
            if resp.status_code != 200:
                return RefreshSummary(success=False, error=f"索引下载失败 [{resp.status_code}]")
            data = resp.json()
            if data.get("schema_version") != 1:
                return RefreshSummary(success=False, error="索引版本不受支持。")
            resources = data.get("resources", {})
            keywords = data.get("keywords", {})
            if not isinstance(resources, dict) or not isinstance(keywords, dict):
                return RefreshSummary(success=False, error="索引结构无效。")

            write_json_atomic(ELYSIAN_INDEX_PATH, data)
            meta = _load_meta()
            meta.update(
                {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "generated_at": data.get("generated_at"),
                    "resource_count": len(resources),
                    "keyword_count": len(keywords),
                }
            )
            _save_meta(meta)
            STORE.load()
            return RefreshSummary(
                success=True,
                resource_count=len(resources),
                keyword_count=len(keywords),
                generated_at=data.get("generated_at"),
            )
        except Exception as e:
            logger.warning(f"[崩坏3] [乐土攻略] 索引更新失败: {e}")
            return RefreshSummary(success=False, error=str(e))


async def ensure_strategy_index() -> tuple[bool, bool]:
    STORE.load()
    if STORE.has_index and not _index_expired():
        return True, False
    if STORE.has_index:
        if not _update_lock.locked():
            asyncio.create_task(refresh_strategy_index())
        return True, True

    summary = await refresh_strategy_index()
    return summary.success and STORE.has_index, False


def _image_cache_path(resource_id: str, image: str) -> Path:
    suffix = Path(image).suffix or ".jpg"
    safe_id = resource_id.replace("/", "_").replace("\\", "_")
    return ELYSIAN_IMAGE_CACHE_PATH / f"{safe_id}{suffix}"


async def _ensure_image(resource_id: str, image: str, last_updated: str | None) -> Path | None:
    cache_path = _image_cache_path(resource_id, image)
    meta = _load_meta()
    image_meta = meta.setdefault("images", {})
    if not isinstance(image_meta, dict):
        image_meta = {}
        meta["images"] = image_meta
    cached = image_meta.get(resource_id, {}) if isinstance(image_meta, dict) else {}
    if cache_path.exists() and cached.get("last_updated") == last_updated:
        return cache_path

    lock = _image_locks.setdefault(resource_id, asyncio.Lock())
    async with lock:
        meta = _load_meta()
        image_meta = meta.setdefault("images", {})
        if not isinstance(image_meta, dict):
            image_meta = {}
            meta["images"] = image_meta
        cached = image_meta.get(resource_id, {}) if isinstance(image_meta, dict) else {}
        if cache_path.exists() and cached.get("last_updated") == last_updated:
            return cache_path

        url = f"{DEFAULT_RAW_BASE}/{image.lstrip('/')}"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(_with_proxy(url), timeout=45)
            if resp.status_code != 200:
                logger.warning(f"[崩坏3] [乐土攻略] 图片下载失败 [{resp.status_code}]: {url}")
                return cache_path if cache_path.exists() else None
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
            tmp_path.write_bytes(resp.content)
            tmp_path.replace(cache_path)
            image_meta[resource_id] = {
                "last_updated": last_updated,
                "path": cache_path.name,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_meta(meta)
            return cache_path
        except Exception as e:
            logger.warning(f"[崩坏3] [乐土攻略] 图片下载异常: {e}")
            return cache_path if cache_path.exists() else None


async def query_strategy(keyword: str) -> QueryResult:
    ok, stale = await ensure_strategy_index()
    if not ok:
        return QueryResult(error="[崩坏3] 乐土攻略索引获取失败，请稍后再试。")

    candidate, candidates = STORE.find(keyword)
    if candidates:
        return QueryResult(
            error=f"[崩坏3] 「{keyword}」命中多个乐土攻略，请输入更精确关键词。",
            candidates=candidates,
            used_stale_cache=stale,
        )
    if not candidate:
        return QueryResult(
            error=f"[崩坏3] 未找到「{keyword}」相关乐土攻略，可尝试输入角色简称 + 乐土。",
            used_stale_cache=stale,
        )

    image_path = await _ensure_image(candidate.resource_id, candidate.image, candidate.last_updated)
    if not image_path:
        return QueryResult(
            error="[崩坏3] 已匹配到攻略，但图片下载失败。请稍后重试，或使用 bbb更新乐土攻略 刷新索引。",
            used_stale_cache=stale,
        )

    return QueryResult(
        match=MatchResult(
            resource_id=candidate.resource_id,
            image_path=image_path,
            matched_keyword=candidate.matched_keyword,
            display_keyword=candidate.display_keyword,
            last_updated=candidate.last_updated,
        ),
        used_stale_cache=stale,
    )


def format_source(match: MatchResult) -> str:
    return (
        f"[崩坏3] 已找到「{match.display_keyword}」攻略：{match.resource_id}\n"
        f"更新时间：{display_timestamp(match.last_updated)}\n"
        "来源：MskTmi/ElysianRealm-Data"
    )


def format_refresh_summary(summary: RefreshSummary) -> str:
    if not summary.success:
        return f"[崩坏3] 乐土攻略索引更新失败：{summary.error or '未知错误'}"
    return (
        "[崩坏3] 乐土攻略索引更新完成\n"
        f"资源数量：{summary.resource_count}\n"
        f"关键词数量：{summary.keyword_count}\n"
        f"索引时间：{summary.generated_at or '未知'}"
    )


async def list_strategy_keywords(query: str = "") -> tuple[bool, str]:
    ok, stale = await ensure_strategy_index()
    if not ok:
        return False, "[崩坏3] 乐土攻略索引获取失败，请稍后再试。"

    items = STORE.list_keywords(query)
    if not items:
        return True, f"[崩坏3] 未找到「{query}」相关乐土关键词。" if query else "[崩坏3] 暂无乐土关键词缓存。"

    total = len(STORE.keywords)
    title = f"[崩坏3] 乐土关键词列表（显示{len(items)}条 / 共{total}条，最多80条）"
    if query:
        title = f"[崩坏3] 「{query}」相关乐土关键词（显示{len(items)}条，最多80条）"
    if stale:
        title += "\n当前使用本地缓存，后台正在尝试更新索引。"
    lines = [title]
    for keyword, ids in items:
        lines.append(f"- {keyword}: {', '.join(ids[:3])}")
    return True, "\n".join(lines)
