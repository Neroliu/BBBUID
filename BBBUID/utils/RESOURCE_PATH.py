from pathlib import Path

from gsuid_core.data_store import get_res_path

MAIN_PATH = get_res_path() / "BBBUID"

CONFIG_PATH = MAIN_PATH / "config.json"

WIKI_PATH = MAIN_PATH / "wiki"
ALIAS_PATH = MAIN_PATH / "alias"
USER_CHAR_ALIAS_PATH = ALIAS_PATH / "char_alias.json"
CHAR_META_PATH = MAIN_PATH / "char_meta.json"

CHANNEL_MAP = {
    "角色": 18,
    "武器": 20,
    "圣痕": 19,
    "人偶": 21,
    "协同者": 218,
    "敌人": 47,
    "立绘": 36,
    "壁纸": 37,
}


def get_wiki_path(channel_name: str) -> Path:
    path = WIKI_PATH / channel_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_dir():
    for name in CHANNEL_MAP:
        get_wiki_path(name)
    ALIAS_PATH.mkdir(parents=True, exist_ok=True)


init_dir()
