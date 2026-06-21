"""崩坏3抽卡记录拉取逻辑。

两步查询流程：
1. GetMenus → 获取可用卡池列表（type + label）
2. GetUserGacha → 按每个卡池 type 分页拉取记录

去重方式：(补给时间, 补给内容) 二元组（API 无 id 字段）。
"""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import aiofiles

from gsuid_core.logger import logger

from ..bbb_api import bh3_api
from ..utils.RESOURCE_PATH import PLAYER_PATH


def _parse_record(item: list[Dict]) -> Dict[str, str]:
    """将 label/value 对数组转为 {time, content} dict。"""
    result: Dict[str, str] = {}
    for pair in item:
        label = pair.get("label", "")
        value = pair.get("value", "")
        if label == "补给时间":
            result["time"] = value
        elif label == "补给内容":
            result["content"] = value
    return result


def _record_key(record: Dict[str, str]) -> Tuple[str, str]:
    """生成去重用的 (time, content) 二元组。"""
    return (record.get("time", ""), record.get("content", ""))


async def _get_authkey(uid: str) -> str | None:
    """获取 authkey。需要通过 stoken 调用 genAuthKey API。"""
    server_id = await bh3_api.get_bbb_server(uid) or "prod_gf_cn"

    # get_authkey_by_cookie 内部 get_stoken 不传 game_name，
    # 会导致查找 uid 字段而非 bbb_uid，这里手动传 game_name="bbb"
    from gsuid_core.utils.database.models import GsUser
    stoken = await GsUser.get_user_stoken_by_uid(uid, "bbb")
    if not stoken:
        logger.warning(f"[崩坏3] [抽卡记录] 未找到 stoken (uid={uid})")
        return None

    import copy
    from gsuid_core.utils.api.mys.tools import get_web_ds_token, mys_version
    from gsuid_core.utils.api.mys.api import GET_AUTHKEY_URL
    import random as _random

    HEADER = copy.deepcopy(bh3_api._HEADER)
    HEADER["Cookie"] = stoken
    HEADER["DS"] = get_web_ds_token(True)
    HEADER["User-Agent"] = "okhttp/4.8.0"
    HEADER["x-rpc-app_version"] = mys_version
    HEADER["x-rpc-sys_version"] = "12"
    HEADER["x-rpc-client_type"] = "5"
    HEADER["x-rpc-channel"] = "mihoyo"
    HEADER["x-rpc-device_id"] = "".join(_random.choices("0123456789abcdef", k=32))
    HEADER["x-rpc-device_name"] = "Mi 10"
    HEADER["x-rpc-device_model"] = "Mi 10"
    HEADER["Referer"] = "https://app.mihoyo.com"
    HEADER["Host"] = "api-takumi.mihoyo.com"

    data = await bh3_api._mys_request(
        url=GET_AUTHKEY_URL,
        method="POST",
        header=HEADER,
        data={
            "auth_appid": "webview_gacha",
            "game_biz": "bh3_cn",
            "game_uid": uid,
            "region": server_id,
        },
    )
    if isinstance(data, dict) and "data" in data:
        return data["data"].get("authkey")
    logger.warning(f"[崩坏3] [抽卡记录] genAuthKey 失败: {data}")
    return None


async def _get_gacha_menus(uid: str, authkey: str) -> List[Dict]:
    """调用 GetMenus 获取卡池列表。"""
    data = await bh3_api.get_bh3_gacha_menus(uid, authkey)
    if isinstance(data, int):
        logger.warning(f"[崩坏3] [抽卡记录] GetMenus 失败: {data}")
        return []
    if isinstance(data, list):
        return data
    logger.warning(f"[崩坏3] [抽卡记录] GetMenus 返回非预期类型: {type(data)}")
    return []


async def _fetch_gacha_type(
    uid: str,
    authkey: str,
    gacha_type: str,
    existing_keys: set[Tuple[str, str]],
    is_force: bool,
) -> List[Dict[str, str]]:
    """拉取单个卡池类型的记录，返回新记录列表。"""
    new_records: list[Dict[str, str]] = []

    for page in range(1, 999):
        data = await bh3_api.get_bh3_gacha_log_by_authkey(
            uid, authkey, gacha_type, page=page,
        )
        await asyncio.sleep(0.9)

        if isinstance(data, int):
            logger.warning(f"[崩坏3] [抽卡记录] 拉取 type={gacha_type} page={page} 失败: {data}")
            break

        raw_list = data.get("list", [])
        if not raw_list:
            break

        for raw_item in raw_list:
            record = _parse_record(raw_item.get("item", []))
            if not record.get("time") or not record.get("content"):
                continue
            key = _record_key(record)
            if key in existing_keys and not is_force:
                # 增量模式：遇到已存在记录，收集完本页新增后停止
                return new_records
            new_records.append(record)

    return new_records


async def save_gachalogs(uid: str, is_force: bool = False) -> str:
    """增量刷新抽卡记录，返回摘要文本。"""
    path = PLAYER_PATH / str(uid)
    path.mkdir(parents=True, exist_ok=True)
    gachalogs_path = path / "gacha_logs.json"

    # 读取已有数据
    if gachalogs_path.exists():
        async with aiofiles.open(gachalogs_path, "r", encoding="utf-8") as f:
            gacha_log = json.loads(await f.read())
        history: Dict[str, List[Dict]] = gacha_log.get("data", {})
    else:
        history = {}

    # 记录旧数量
    old_total = sum(len(v) for v in history.values())

    # 构建已有记录的去重集合
    existing_keys: Dict[str, set[Tuple[str, str]]] = {}
    for gacha_name, records in history.items():
        existing_keys[gacha_name] = {_record_key(r) for r in records}

    # 获取 authkey
    authkey = await _get_authkey(uid)
    if not authkey:
        return "[崩坏3] 获取 authkey 失败，请先绑定 stoken 后再使用抽卡记录功能。\n绑定方式：使用 bbb扫码登陆 或在 webconsole 中绑定 stoken。"

    # 获取卡池列表
    menus = await _get_gacha_menus(uid, authkey)
    if not menus:
        return "[崩坏3] 获取卡池列表失败，请稍后再试。"

    # 遍历卡池拉取
    total_add = 0
    deltas: Dict[str, int] = {}

    for menu in menus:
        gacha_type = str(menu.get("type", ""))
        gacha_name = menu.get("label", f"卡池{gacha_type}")
        if not gacha_type:
            continue

        if gacha_name not in history:
            history[gacha_name] = []
            existing_keys[gacha_name] = set()

        new_records = await _fetch_gacha_type(
            uid, authkey, gacha_type,
            existing_keys[gacha_name], is_force,
        )

        if new_records:
            # 去重后合并
            added = 0
            for r in new_records:
                key = _record_key(r)
                if key not in existing_keys[gacha_name]:
                    history[gacha_name].append(r)
                    existing_keys[gacha_name].add(key)
                    added += 1
            # 按时间降序排列
            history[gacha_name].sort(key=lambda x: x.get("time", ""), reverse=True)
            deltas[gacha_name] = added
            total_add += added

    # 构建结果
    result = {
        "uid": uid,
        "data_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": history,
    }

    # 写入文件
    async with aiofiles.open(gachalogs_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(result, indent=2, ensure_ascii=False))

    # 回复文字
    if total_add == 0:
        return f"🌱UID{uid} 没有新增抽卡数据！"
    parts = [f"✅UID{uid} 数据更新成功！本次更新 {total_add} 条"]
    for gacha_name, delta in deltas.items():
        if delta > 0:
            parts.append(f"  {gacha_name} 新增 {delta} 条记录")
    return "\n".join(parts)


# 全量刷新并发锁
_full_lock: list[str] = []


async def get_full_gachalogs(uid: str) -> str:
    """全量刷新：备份旧数据，裁剪 5 个月前记录，然后增量拉取。"""
    if uid in _full_lock:
        return "当前正在全量刷新抽卡记录中，请勿重试！请稍后再试..."

    _full_lock.append(uid)
    try:
        path = PLAYER_PATH / str(uid)
        gachalogs_path = path / "gacha_logs.json"

        if not gachalogs_path.exists():
            return "你还没有缓存的抽卡记录，请先使用「刷新抽卡记录」！"

        # 备份
        ts = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        backup_path = path / f"gacha_logs_{ts}.json"
        shutil.copy(gachalogs_path, backup_path)
        logger.info(f"[崩坏3] [抽卡记录] 已备份到 {backup_path}")

        # 读取并裁剪
        async with aiofiles.open(gachalogs_path, "r", encoding="utf-8") as f:
            gacha_log = json.loads(await f.read())

        threshold = datetime.now() - timedelta(days=150)
        history: Dict[str, List[Dict]] = gacha_log.get("data", {})
        for gacha_name in list(history.keys()):
            history[gacha_name] = [
                r for r in history[gacha_name]
                if r.get("time", "") > threshold.strftime("%Y-%m-%d %H:%M:%S")
            ]

        gacha_log["data"] = history
        async with aiofiles.open(gachalogs_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(gacha_log, ensure_ascii=False))

        return await save_gachalogs(uid)
    finally:
        if uid in _full_lock:
            _full_lock.remove(uid)
