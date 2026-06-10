from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict


class ElysianResource(TypedDict, total=False):
    image: str
    last_updated: str


class ElysianIndex(TypedDict, total=False):
    schema_version: int
    generated_at: str
    resources: dict[str, ElysianResource]
    keywords: dict[str, list[str]]


@dataclass(slots=True)
class ResourceEntry:
    image: str
    last_updated: str | None = None


@dataclass(slots=True)
class MatchCandidate:
    resource_id: str
    matched_keyword: str
    display_keyword: str
    image: str
    last_updated: str | None = None


@dataclass(slots=True)
class MatchResult:
    resource_id: str
    image_path: Path
    matched_keyword: str
    display_keyword: str
    last_updated: str | None


@dataclass(slots=True)
class QueryResult:
    match: MatchResult | None = None
    error: str | None = None
    candidates: list[str] = field(default_factory=list)
    used_stale_cache: bool = False


@dataclass(slots=True)
class RefreshSummary:
    success: bool
    error: str | None = None
    resource_count: int = 0
    keyword_count: int = 0
    generated_at: str | None = None
