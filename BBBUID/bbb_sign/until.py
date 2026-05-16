import copy
import random
import asyncio

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


async def sign_by_uid(uid: str) -> str:
    """通过uid签到，供muti_task调用，返回结果文本。"""
    cookie = await GsUser.get_user_cookie_by_uid(uid, "bbb")
    if not cookie:
        return "签到失败~未找到Cookie"

    account_data = await get_account_list(cookie)
    if isinstance(account_data, int):
        return "获取账号列表失败！"

    items = (account_data.get("data") or {}).get("list", [])
    if not items:
        return "签到失败~未获取到账号信息"
    account_list = []
    for i in items:
        account_list.append([i.get("nickname", "?"), i.get("game_uid", ""), i.get("region", "")])

    checkin_rewards = await get_checkin_rewards()
    if isinstance(checkin_rewards, int):
        return "签到失败~获取签到奖励列表失败"
    checkin_rewards = (checkin_rewards.get("data") or {}).get("awards", [])
    if not checkin_rewards:
        return "签到失败~签到奖励列表为空"

    return_data = ""
    for nickname, game_uid, region in account_list:
        if str(game_uid) != str(uid):
            continue
        is_data = await is_sign(region=region, uid=game_uid, cookie=cookie)
        if isinstance(is_data, int):
            return_data += f"舰长:{nickname} 获取签到信息失败！\n"
            continue

        is_data = is_data.get("data")
        if not is_data:
            return_data += f"舰长:{nickname} 获取签到信息失败~\n"
            continue
        if is_data.get("is_sign"):
            day_idx = int(is_data.get("total_sign_day", 0)) - 1
            if 0 <= day_idx < len(checkin_rewards):
                getitem = checkin_rewards[day_idx]
                return_data += f"舰长:{nickname} 今天已经签到过了~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}\n"
            else:
                return_data += f"舰长:{nickname} 今天已经签到过了~\n"
            continue

        Header = {}
        fp = await GsUser.get_user_attr_by_uid(uid, "fp", "bbb")
        if fp:
            Header["x-rpc-device_fp"] = fp
        device_id = await GsUser.get_user_attr_by_uid(uid, "device_id", "bbb")
        if device_id:
            Header["x-rpc-device_id"] = device_id

        signed = False
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
                    return_data += f"舰长:{nickname} 签到失败~错误码:{sign_data}\n"
                    break

            if sign_data and "data" in sign_data and sign_data["data"]:
                risk_code = sign_data["data"].get("risk_code", -1)
                if risk_code == 5001:
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
                elif risk_code == 0:
                    day_idx = int(is_data.get("total_sign_day", 0))
                    if 0 <= day_idx < len(checkin_rewards):
                        getitem = checkin_rewards[day_idx]
                        return_data += f"舰长:{nickname} 签到成功~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}\n"
                    else:
                        return_data += f"舰长:{nickname} 签到成功~\n"
                    signed = True
                    break
                else:
                    return_data += f"舰长:{nickname} 签到失败~risk_code:{risk_code}\n"
                    break
            else:
                return_data += f"舰长:{nickname} 签到失败~响应异常\n"
                break
        if not signed and f"舰长:{nickname}" not in return_data:
            return_data += f"舰长:{nickname} 签到失败~\n"

    return return_data if return_data else "签到失败~"


async def sign(qid: str, bot_id: str = "onebot") -> tuple[str, bool]:
    """签到入口，接收QQ用户ID和bot_id，返回(结果文本, 是否成功)。"""
    return_data = ""
    flag = False

    cookie = await GsUser.get_user_cookie_by_user_id(qid, bot_id)
    if not cookie:
        return return_data + "你没有绑定过Cookies噢~", flag

    account_data = await get_account_list(cookie)
    if isinstance(account_data, int):
        return return_data + "获取账号列表失败！", flag

    items = (account_data.get("data") or {}).get("list", [])
    if not items:
        return return_data + "签到失败~未获取到账号信息", flag
    account_list = []
    for i in items:
        account_list.append([i.get("nickname", "?"), i.get("game_uid", ""), i.get("region", "")])

    checkin_rewards = await get_checkin_rewards()
    if isinstance(checkin_rewards, int):
        return return_data + "签到失败~获取签到奖励列表失败", flag
    checkin_rewards = (checkin_rewards.get("data") or {}).get("awards", [])
    if not checkin_rewards:
        return return_data + "签到失败~签到奖励列表为空", flag

    for nickname, game_uid, region in account_list:
        is_data = await is_sign(region=region, uid=game_uid, cookie=cookie)
        if isinstance(is_data, int):
            return_data += f"舰长:{nickname} 获取签到信息失败！\n"
            continue

        is_data = is_data.get("data")
        if not is_data:
            return_data += f"舰长:{nickname} 获取签到信息失败~\n"
            continue
        if is_data.get("is_sign"):
            day_idx = int(is_data.get("total_sign_day", 0)) - 1
            if 0 <= day_idx < len(checkin_rewards):
                getitem = checkin_rewards[day_idx]
                return_data += f"舰长:{nickname} 今天已经签到过了~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}\n"
            else:
                return_data += f"舰长:{nickname} 今天已经签到过了~\n"
            flag = True
            continue

        # 执行签到
        Header = {}
        fp = await GsUser.get_user_attr(qid, bot_id, "fp")
        if fp:
            Header["x-rpc-device_fp"] = fp
        device_id = await GsUser.get_user_attr(qid, bot_id, "device_id")
        if device_id:
            Header["x-rpc-device_id"] = device_id

        signed = False
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
                    return_data += f"舰长:{nickname} 签到失败~错误码:{sign_data}\n"
                    break

            if sign_data and "data" in sign_data and sign_data["data"]:
                risk_code = sign_data["data"].get("risk_code", -1)
                if risk_code == 5001:
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
                elif risk_code == 0:
                    day_idx = int(is_data.get("total_sign_day", 0))
                    if 0 <= day_idx < len(checkin_rewards):
                        getitem = checkin_rewards[day_idx]
                        return_data += f"舰长:{nickname} 签到成功~\n今天获得的奖励是{getitem['name']}x{getitem['cnt']}\n"
                    else:
                        return_data += f"舰长:{nickname} 签到成功~\n"
                    flag = True
                    signed = True
                    break
                else:
                    return_data += f"舰长:{nickname} 签到失败~risk_code:{risk_code}\n"
                    break
            else:
                return_data += f"舰长:{nickname} 签到失败~响应异常\n"
                break
        if not signed and f"舰长:{nickname}" not in return_data:
            return_data += f"舰长:{nickname} 签到失败~\n"

    return return_data, flag


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
