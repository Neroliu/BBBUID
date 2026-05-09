import copy
from typing import Dict, Optional, Union, cast

from gsuid_core.utils.api.mys_api import _MysApi
from gsuid_core.utils.api.mys.tools import get_ds_token, get_web_ds_token
from gsuid_core.utils.database.models import GsUser
from gsuid_core.logger import logger

from .api import (
    BH3_API,
    BH3_BIND_API,
    BH3_INDEX_API,
    BH3_NOTE_API,
    BH3_CHARACTERS_API,
    BH3_NEW_ABYSS_API,
    BH3_OLD_ABYSS_API,
    BH3_BATTLE_FIELD_API,
    BH3_GODWAR_API,
)
from .models import (
    BH3IndexData,
    BH3NoteData,
    BH3CharactersData,
    BH3NewAbyssData,
    BH3OldAbyssData,
    BH3BattleFieldData,
    BH3GodWarData,
)


class BH3Api(_MysApi):
    async def bbb_get_ck(self, uid: str) -> Optional[str]:
        return await self.get_ck(uid, "RANDOM", "bbb")

    async def get_bbb_server(self, uid: str) -> Optional[str]:
        region = await GsUser.get_user_attr_by_uid(uid, "bbb_region", "bbb")
        if region:
            return region

        ck = await self.bbb_get_ck(uid)
        if not ck:
            return None

        HEADER = copy.deepcopy(self._HEADER)
        HEADER["Cookie"] = ck
        HEADER["DS"] = get_web_ds_token(True)

        data = await self._mys_request(
            url=f"{BH3_BIND_API}?game_biz=bh3_cn",
            method="GET",
            header=HEADER,
        )

        if isinstance(data, Dict) and "data" in data:
            for account in data["data"]["list"]:
                if account["game_uid"] == uid:
                    server = account["region"]
                    await GsUser.update_data_by_uid_without_bot_id(
                        uid, "bbb", bbb_region=server
                    )
                    return server
        return None

    async def simple_bh3_req(
        self,
        URL: str,
        uid: str,
        params: Optional[Dict] = None,
        header: Dict = {},
        cookie: Optional[str] = None,
    ) -> Union[Dict, int]:
        server = await self.get_bbb_server(uid)
        if not server:
            return -51

        if params is None:
            params = {}
        params.update({"role_id": uid, "server": server})

        HEADER = copy.deepcopy(self._HEADER)
        HEADER.update(header)

        ex_params = "&".join(
            [f"{k}={v}" for k, v in sorted(params.items())]
        )
        HEADER["DS"] = get_ds_token(ex_params)

        if cookie is not None:
            HEADER["Cookie"] = cookie
        elif "Cookie" not in HEADER:
            ck = await self.bbb_get_ck(uid)
            if ck is None:
                return -51
            HEADER["Cookie"] = ck

        data = await self._mys_request(
            url=URL,
            method="GET",
            header=HEADER,
            params=params,
            base_url=BH3_API,
            game_name="bbb",
        )
        return data

    async def get_bbb_index(self, uid: str) -> Union[int, BH3IndexData]:
        data = await self.simple_bh3_req(BH3_INDEX_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3IndexData, data["data"])
        return data

    async def get_bbb_note(self, uid: str) -> Union[int, BH3NoteData]:
        data = await self.simple_bh3_req(BH3_NOTE_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3NoteData, data["data"])
        return data

    async def get_bbb_characters(self, uid: str) -> Union[int, BH3CharactersData]:
        data = await self.simple_bh3_req(BH3_CHARACTERS_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3CharactersData, data["data"])
        return data

    async def get_bbb_new_abyss(self, uid: str) -> Union[int, BH3NewAbyssData]:
        data = await self.simple_bh3_req(BH3_NEW_ABYSS_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3NewAbyssData, data["data"])
        return data

    async def get_bbb_old_abyss(self, uid: str) -> Union[int, BH3OldAbyssData]:
        data = await self.simple_bh3_req(BH3_OLD_ABYSS_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3OldAbyssData, data["data"])
        return data

    async def get_bbb_battle_field(self, uid: str) -> Union[int, BH3BattleFieldData]:
        data = await self.simple_bh3_req(BH3_BATTLE_FIELD_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3BattleFieldData, data["data"])
        return data

    async def get_bbb_god_war(self, uid: str) -> Union[int, BH3GodWarData]:
        data = await self.simple_bh3_req(BH3_GODWAR_API, uid)
        if isinstance(data, Dict):
            data = cast(BH3GodWarData, data["data"])
        return data
