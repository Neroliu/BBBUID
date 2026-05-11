"""Character data cache for BBBUID."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any

from gsuid_core.logger import logger

from .RESOURCE_PATH import CHAR_DATA_CACHE_PATH

CHAR_DATA_CACHE_PATH.mkdir(parents=True, exist_ok=True)


def _get_cache_path(uid: str) -> Path:
    return CHAR_DATA_CACHE_PATH / f"{uid}.json"


def load_char_data(uid: str) -> List[Dict[str, Any]] | None:
    """Load cached character data for UID."""
    path = _get_cache_path(uid)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("characters", [])
    except Exception as e:
        logger.warning(f"[崩坏3] [角色缓存] 读取缓存失败 [{uid}]: {e}")
        return None


def save_char_data(uid: str, characters: List[Dict[str, Any]]) -> None:
    """Save character data to cache."""
    path = _get_cache_path(uid)
    try:
        path.write_text(
            json.dumps({"characters": characters}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"[崩坏3] [角色缓存] 已保存 [{uid}] {len(characters)} 个角色")
    except Exception as e:
        logger.warning(f"[崩坏3] [角色缓存] 保存失败 [{uid}]: {e}")


def clear_char_data(uid: str) -> bool:
    """Clear cached character data for UID."""
    path = _get_cache_path(uid)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            pass
    return False
