import re
from typing import Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.utils.database.models import GsBind

GAME_NAME = "bbb"


async def get_uid(bot: Bot, ev: Event) -> Optional[str]:
    uid_data = re.findall(r"\d{6,10}", ev.text) if ev.text else []
    if uid_data:
        return uid_data[0]
    uid = await GsBind.get_uid_by_game(ev.user_id, ev.bot_id, GAME_NAME)
    return uid
