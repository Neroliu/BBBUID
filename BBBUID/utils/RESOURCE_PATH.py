from pathlib import Path

from gsuid_core.data_store import get_res_path

MAIN_PATH = get_res_path() / "BBBUID"

CONFIG_PATH = MAIN_PATH / "config.json"

WIKI_PATH = MAIN_PATH / "wiki"
ALIAS_PATH = MAIN_PATH / "alias"
AVATAR_CACHE_PATH = MAIN_PATH / "avatar_cache"
USER_CHAR_ALIAS_PATH = ALIAS_PATH / "char_alias.json"
CHAR_META_PATH = MAIN_PATH / "char_meta.json"

# Character icon cache (separate from wiki cache)
CHAR_ICON_CACHE_PATH = MAIN_PATH / "char_icons"

CHANNEL_MAP = {
    "角色": 18,
    "武器": 20,
    "圣痕": 19,
    "人偶": 21,
    "协同者": 218,
    "敌人": 47,
    "立绘": 36,
    "壁纸": 37,
    "材料": 38,
}


def get_wiki_path(channel_name: str) -> Path:
    path = WIKI_PATH / channel_name
    path.mkdir(parents=True, exist_ok=True)
    # Ensure icons subdirectory exists
    icons_path = path / "icons"
    icons_path.mkdir(parents=True, exist_ok=True)
    return path


def init_dir():
    for name in CHANNEL_MAP:
        get_wiki_path(name)
    ALIAS_PATH.mkdir(parents=True, exist_ok=True)


init_dir()
