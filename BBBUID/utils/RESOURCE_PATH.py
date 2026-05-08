from pathlib import Path

RESOURCE_PATH = Path(__file__).parent.parent.parent / "data"
WIKI_PATH = RESOURCE_PATH / "wiki"

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
