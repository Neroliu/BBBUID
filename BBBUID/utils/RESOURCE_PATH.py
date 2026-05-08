from pathlib import Path

from gsuid_core.data_store import get_res_path

MAIN_PATH = get_res_path() / "BBBUID"

WIKI_PATH = MAIN_PATH / "wiki"

CHANNEL_MAP = {
    "角色": 18,
    "武器": 20,
    "圣痕": 19,
    "人偶": 21,
    "协同者": 218,
}


def get_wiki_path(channel_name: str) -> Path:
    path = WIKI_PATH / channel_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_dir():
    for name in CHANNEL_MAP:
        get_wiki_path(name)


init_dir()
