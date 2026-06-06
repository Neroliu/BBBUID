import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gsuid_core.logger import logger

from .models import ElysianIndex, MatchCandidate, ResourceEntry
from ..utils.RESOURCE_PATH import ELYSIAN_INDEX_PATH, ELYSIAN_LOCAL_INDEX_PATH


def normalize_keyword(keyword: str) -> str:
    return re.sub(r"\s+", "", keyword.strip())


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def display_timestamp(value: str | None) -> str:
    if not value:
        return "未知"
    try:
        return parse_timestamp(value).strftime("%Y-%m-%d")
    except ValueError:
        return value


def _backup_broken(path: Path):
    if not path.exists():
        return
    broken = path.with_suffix(path.suffix + ".broken")
    try:
        path.replace(broken)
        logger.warning(f"[崩坏3] [乐土攻略] 已备份损坏索引: {broken.name}")
    except Exception as e:
        logger.warning(f"[崩坏3] [乐土攻略] 损坏索引备份失败: {e}")


def _read_index(path: Path) -> ElysianIndex | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("index root must be object")
        if data.get("schema_version") != 1:
            raise ValueError(f"unsupported schema_version: {data.get('schema_version')}")
        if not isinstance(data.get("resources", {}), dict):
            raise ValueError("resources must be object")
        if not isinstance(data.get("keywords", {}), dict):
            raise ValueError("keywords must be object")
        return data
    except Exception as e:
        logger.warning(f"[崩坏3] [乐土攻略] 读取索引失败 {path.name}: {e}")
        _backup_broken(path)
        return None


class StrategyStore:
    """Loads official and local Elysian Realm indexes, then matches user keywords."""

    def __init__(self):
        self.generated_at: str | None = None
        self.resources: dict[str, ResourceEntry] = {}
        self.keywords: dict[str, list[str]] = {}
        self._keyword_lookup: dict[str, tuple[str, list[str]]] = {}

    @property
    def has_index(self) -> bool:
        return bool(self.resources and self.keywords)

    def load(self):
        official = _read_index(ELYSIAN_INDEX_PATH)
        local = _read_index(ELYSIAN_LOCAL_INDEX_PATH)

        resources: dict[str, ResourceEntry] = {}
        keywords: dict[str, list[str]] = {}
        generated_at: str | None = None

        for index in (official, local):
            if not index:
                continue
            generated_at = generated_at or index.get("generated_at")
            for resource_id, item in index.get("resources", {}).items():
                if not isinstance(item, dict) or not item.get("image"):
                    continue
                resources[resource_id] = ResourceEntry(
                    image=str(item["image"]),
                    last_updated=item.get("last_updated"),
                )
            for keyword, ids in index.get("keywords", {}).items():
                if not isinstance(ids, list):
                    continue
                valid_ids = [str(resource_id) for resource_id in ids if str(resource_id) in resources]
                if valid_ids:
                    keywords[str(keyword)] = valid_ids

        self.generated_at = generated_at
        self.resources = resources
        self.keywords = keywords
        self._keyword_lookup = {
            normalize_keyword(keyword): (keyword, ids)
            for keyword, ids in self.keywords.items()
            if normalize_keyword(keyword)
        }

    def _to_candidates(self, display_keyword: str, ids: list[str], matched_keyword: str) -> list[MatchCandidate]:
        candidates: list[MatchCandidate] = []
        for resource_id in ids:
            item = self.resources.get(resource_id)
            if not item:
                continue
            candidates.append(
                MatchCandidate(
                    resource_id=resource_id,
                    matched_keyword=matched_keyword,
                    display_keyword=display_keyword,
                    image=item.image,
                    last_updated=item.last_updated,
                )
            )
        return candidates

    def _pick_latest(self, candidates: list[MatchCandidate]) -> MatchCandidate | None:
        if not candidates:
            return None
        return max(candidates, key=lambda item: parse_timestamp(item.last_updated))

    def find(self, keyword: str) -> tuple[MatchCandidate | None, list[str]]:
        normalized = normalize_keyword(keyword)
        if not normalized:
            return None, []

        attempts = [normalized]
        if "乐土" not in normalized:
            attempts.append(f"{normalized}乐土")

        for attempt in attempts:
            found = self._keyword_lookup.get(attempt)
            if not found:
                continue
            display_keyword, ids = found
            return self._pick_latest(self._to_candidates(display_keyword, ids, attempt)), []

        if len(normalized) < 2:
            return None, []

        candidates: list[MatchCandidate] = []
        seen: set[tuple[str, str]] = set()
        for norm_keyword, (display_keyword, ids) in self._keyword_lookup.items():
            if normalized not in norm_keyword and norm_keyword not in normalized:
                continue
            for candidate in self._to_candidates(display_keyword, ids, normalized):
                key = (candidate.resource_id, candidate.display_keyword)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)

        if len({item.resource_id for item in candidates}) > 8:
            hints = sorted({item.display_keyword for item in candidates})[:12]
            return None, hints
        return self._pick_latest(candidates), []

    def list_keywords(self, query: str = "", limit: int = 80) -> list[tuple[str, list[str]]]:
        normalized = normalize_keyword(query)
        items = sorted(self.keywords.items(), key=lambda item: item[0])
        if normalized:
            items = [
                item for item in items
                if normalized in normalize_keyword(item[0])
                or any(normalized in resource_id.lower() for resource_id in item[1])
            ]
        return items[:limit]


STORE = StrategyStore()


def write_json_atomic(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
