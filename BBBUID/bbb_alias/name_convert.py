import json
from pathlib import Path

from pydantic import BaseModel, RootModel, ConfigDict, ValidationError

from gsuid_core.logger import logger

from ..utils.RESOURCE_PATH import (
    CHAR_META_PATH,
    USER_CHAR_ALIAS_PATH,
    WIKI_PATH,
)


class CharMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    aliases: list[str] = []


class CharMetaFile(RootModel[dict[str, CharMeta]]):
    pass


class UserCharAliasFile(RootModel[dict[str, list[str]]]):
    pass


char_alias_data: dict[str, list[str]] = {}
char_id_to_name_data: dict[str, str] = {}


def _load_char_meta_file() -> CharMetaFile:
    return CharMetaFile.model_validate_json(CHAR_META_PATH.read_text(encoding="utf-8"))


def load_user_char_aliases() -> UserCharAliasFile:
    if not USER_CHAR_ALIAS_PATH.exists():
        return UserCharAliasFile(root={})
    try:
        return UserCharAliasFile.model_validate_json(
            USER_CHAR_ALIAS_PATH.read_text(encoding="utf-8")
        )
    except ValidationError as e:
        logger.warning(f"[BBBUID] {USER_CHAR_ALIAS_PATH} 解析失败: {e}")
        return UserCharAliasFile(root={})


def save_user_char_aliases(model: UserCharAliasFile) -> None:
    USER_CHAR_ALIAS_PATH.write_text(
        model.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def save_char_meta(model: CharMetaFile) -> None:
    CHAR_META_PATH.write_text(
        model.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def load_char_meta() -> None:
    global char_alias_data, char_id_to_name_data

    char_alias_data = {}
    char_id_to_name_data = {}

    if not CHAR_META_PATH.exists():
        return

    user_aliases = load_user_char_aliases().root

    for content_id, meta in _load_char_meta_file().root.items():
        if not meta.name:
            continue

        char_id_to_name_data[content_id] = meta.name

        aliases: list[str] = []
        for alias in [*meta.aliases, *user_aliases.get(content_id, []), meta.name]:
            if not alias or alias in aliases:
                continue
            aliases.append(alias)
        if meta.name not in char_alias_data:
            char_alias_data[meta.name] = aliases


def build_char_meta_from_wiki() -> None:
    role_path = WIKI_PATH / "角色"
    if not role_path.exists():
        return

    meta_dict: dict[str, CharMeta] = {}

    for f in role_path.glob("*.json"):
        if f.name == "index.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        content_id = str(data.get("id", ""))
        title = data.get("title", "")
        if not content_id or not title:
            continue

        basic_info = data.get("basic_info", {})
        alias_str = basic_info.get("别名", "")
        alias_list = [a.strip() for a in alias_str.split("、") if a.strip()]

        # Deduplicate: alias list + name, preserve order
        all_aliases = list(dict.fromkeys([*alias_list, title]))
        meta_dict[content_id] = CharMeta(name=title, aliases=all_aliases)

    model = CharMetaFile(root=meta_dict)
    save_char_meta(model)
    load_char_meta()
    logger.info(f"[BBBUID] [别名] 从wiki缓存生成 char_meta.json，共 {len(meta_dict)} 个角色")


load_char_meta()


def alias_to_char_name(char_name: str | None) -> str | None:
    if not char_name:
        return None
    for name, aliases in char_alias_data.items():
        if char_name in name or char_name in aliases:
            return name
    return None


def alias_to_char_name_list(char_name: str) -> list[str]:
    for name, aliases in char_alias_data.items():
        if char_name in name or char_name in aliases:
            return aliases
    return []


def char_name_to_content_id(char_name: str | None) -> str | None:
    char_name = alias_to_char_name(char_name)
    if not char_name:
        return None
    for content_id, name in char_id_to_name_data.items():
        if name == char_name:
            return content_id
    return None


def alias_to_content_id(char_name: str | None) -> str | None:
    return char_name_to_content_id(char_name)
