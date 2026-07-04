import re
from typing import Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.utils.database.models import GsBind

from ..bbb_config.bbb_config import BBB_CONFIG
from .hint import BIND_UID_HINT, OTHER_BIND_UID_HINT, AT_QUERY_DISABLED

GAME_NAME = "bbb"


async def get_uid(bot: Bot, ev: Event) -> Optional[str]:
    """获取发送者自身已绑定UID（兼容命令内直接写入UID）。

    - 支持命令内显式写入UID（正则提取）
    - 默认查询发送者自身已绑定UID
    - @他人查询请使用 `get_query_target`
    """
    explicit_uid = _extract_explicit_uid(ev.text)
    if explicit_uid:
        return explicit_uid

    uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, GAME_NAME)
    if uid:
        return uid

    await bot.send(BIND_UID_HINT, at_sender=bool(ev.group_id))
    return None


async def get_query_target(bot: Bot, ev: Event) -> tuple[Optional[str], str, bool]:
    """获取查询目标并返回 (uid, target_user_id, is_other)。

    - 当 uid 缺失时，会自动发送对应提示（他人未绑定 / 未开启@查询 / 自己未绑定）
    - 适用于需要区分是否查他人、或需要对“被@用户”做额外提示的场景
    """
    uid, target_user_id, is_other = await _resolve_query_uid(bot, ev)
    if uid:
        return uid, target_user_id, is_other

    if is_other:
        await bot.send(OTHER_BIND_UID_HINT, at_sender=False)
    else:
        await bot.send(BIND_UID_HINT, at_sender=bool(ev.group_id))
    return None, target_user_id, is_other


def _extract_explicit_uid(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\d{6,10}", text)
    return match.group(0) if match else None


def extract_at_user_id_from_text(text: Optional[str]) -> Optional[str]:
    """从文本中提取 @目标QQ（仅数字ID形式，如 @123456）。
    如果是 @全体 或 @昵称 等非数字形式，返回 None。
    """
    if not text:
        return None
    match = re.search(r"@(\d{5,20})", text)
    return match.group(1) if match else None


def _is_mention_self(ev: Event) -> bool:
    at = getattr(ev, "at", None)
    if not at:
        return True
    if at in {ev.user_id, getattr(ev, "bot_id", None), getattr(ev, "real_bot_id", None)}:
        return True
    return False


async def _resolve_query_uid(bot: Bot, ev: Event) -> tuple[Optional[str], str, bool]:
    explicit_uid = _extract_explicit_uid(ev.text)
    if explicit_uid:
        return explicit_uid, ev.user_id, False

    at = getattr(ev, "at", None)
    text_at = extract_at_user_id_from_text(getattr(ev, "text", None) or getattr(ev, "raw_text", None))

    if at and at not in {ev.user_id, getattr(ev, "bot_id", None), getattr(ev, "real_bot_id", None)}:
        target_user_id = str(at)
    elif text_at and text_at not in {ev.user_id, getattr(ev, "bot_id", None), getattr(ev, "real_bot_id", None)}:
        target_user_id = text_at
    else:
        uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, GAME_NAME)
        return uid, ev.user_id, False

    if not BBB_CONFIG.get_config("BBBAllowAtQuery").data:
        await bot.send(AT_QUERY_DISABLED, at_sender=bool(ev.group_id))
        return None, ev.user_id, False

    uid = await GsBind.get_uid_by_game(target_user_id, ev.bot_id, GAME_NAME)
    return uid, target_user_id, True
