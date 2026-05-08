import copy
import random
import asyncio
import re

from gsuid_core.utils.api.mys.tools import get_web_ds_token, mys_version
from gsuid_core.utils.database.models import GsUser
from gsuid_core.utils.api.mys_api import _MysApi

web_api = "https://api-takumi.mihoyo.com"
act_id = "e202306201626331"
checkin_rewards_url = f"{web_api}/event/luna/home?lang=zh-cn&act_id={act_id}"
is_sign_url = web_api + "/event/luna/info?lang=zh-cn&act_id={}&region={}&uid={}"
sign_url = web_api + "/event/luna/sign"
account_info_url = web_api + "/binding/api/getUserGameRolesByCookie?game_biz=bh3_cn"


class MysApi(_MysApi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


mys_api = MysApi()


async def get_account_list(cookie) -> list:
    HEADER = copy.deepcopy(mys_api._HEADER)
    HEADER["Cookie"] = cookie
    HEADER["DS"] = get_web_ds_token(True)
    data = await mys_api._mys_request(
        url=account_info_url,
        method="GET",
        header=HEADER,
    )
    return data


async def sign(uid: str) -> str:
    """签到入口，接收游戏UID，返回结果文本。适配 muti_task 调用。"""
    cookie = await GsUser.get_user_cookie_by_uid(uid, "bbb")
    if not cookie:
        return f"[{uid}] 你没有绑定过Cookies噢~"

    account_data = await get_account_list(cookie)
    if isinstance(account_data, int):
        return f"[{uid}] 获取账号列表失败！"

    account_list = []
    for i in account_data["data"]["list"]:
        account_list.append([i["nickname"], i["game_uid"], i["region"]])
    if not account_list:
        return f"[{uid}] 未获取到账号信息"

    checkin_rewards = await get_checkin_rewards()
    if isinstance(checkin_rewards, int):
        return f"[{uid}] 获取签到奖励列表失败"
    checkin_rewards = checkin_rewards["data"]["awards"]

    # 找到匹配uid的账号
    target = None
    for acc in account_list:
        if acc[1] == uid:
            target = acc
            break
    if target is None:
        # uid不在账号列表中，尝试签第一个
        target = account_list[0]

    nickname, game_uid, region = target
    return_data = ""

    is_data = await is_sign(region=region, uid=game_uid, cookie=cookie)
    if isinstance(is_data, int):
        return f"舰长:{nickname} 获取签到信息失败！"

    is_data = is_data["data"]
    if is_data["is_sign"]:
        getitem = checkin_rewards[int(is_data["total_sign_day"]) - 1]
        return f"舰长:{nickname} 今天已经签到过了~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}"

    # 执行签到
    Header = {}
    fp = await GsUser.get_user_attr_by_uid(uid, "fp", "bbb")
    if fp:
        Header["x-rpc-device_fp"] = fp
    device_id = await GsUser.get_user_attr_by_uid(uid, "device_id", "bbb")
    if device_id:
        Header["x-rpc-device_id"] = device_id

    for index in range(4):
        sign_data = await sign_req(
            uid=game_uid,
            server_id=region,
            cookie=cookie,
            Header=Header,
        )
        if isinstance(sign_data, int):
            if sign_data == -500001:
                delay = 60 + random.randint(1, 30)
                await asyncio.sleep(delay)
                continue
            else:
                return f"舰长:{nickname} 签到失败~错误码:{sign_data}"

        if sign_data and "data" in sign_data and sign_data["data"]:
            if "risk_code" in sign_data["data"]:
                if sign_data["data"]["risk_code"] == 5001:
                    gt = sign_data["data"]["gt"]
                    ch = sign_data["data"]["challenge"]
                    vl, ch = await mys_api._pass(gt, ch, Header)
                    if vl:
                        Header["x-rpc-challenge"] = ch
                        Header["x-rpc-validate"] = vl
                        Header["x-rpc-seccode"] = f"{vl}|jordan"
                        await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(300 + random.randint(1, 120))
                    continue
                else:
                    getitem = checkin_rewards[int(is_data["total_sign_day"]) - 1 + 1]
                    return f"舰长:{nickname} 签到成功~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}"
            else:
                return f"舰长:{nickname} 签到失败~出现验证码"
    return f"舰长:{nickname} 签到失败~"


async def get_checkin_rewards():
    data = await mys_api._mys_request(
        url=checkin_rewards_url,
        method="GET",
        header=mys_api._HEADER,
    )
    return data


async def is_sign(region: str, uid: str, cookie):
    url = is_sign_url.format(act_id, region, uid)
    HEADER = copy.deepcopy(mys_api._HEADER)
    HEADER["Cookie"] = cookie
    data = await mys_api._mys_request(
        url=url,
        method="GET",
        header=HEADER,
    )
    return data


async def sign_req(uid, server_id="pc01", cookie=None, Header=None):
    HEADER = copy.deepcopy(mys_api._HEADER)
    HEADER["Cookie"] = cookie
    HEADER["x-rpc-app_version"] = mys_version
    HEADER["x-rpc-client_type"] = "5"
    HEADER["X_Requested_With"] = "com.mihoyo.hyperion"
    HEADER["DS"] = get_web_ds_token(True)
    HEADER["Referer"] = "https://act.mihoyo.com/"
    if Header:
        HEADER.update(Header)
    data = await mys_api._mys_request(
        url=sign_url,
        method="POST",
        header=HEADER,
        data={
            "act_id": act_id,
            "uid": uid,
            "region": server_id,
        },
    )
    return data
