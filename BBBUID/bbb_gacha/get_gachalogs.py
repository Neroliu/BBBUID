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

from pathlib import Path

from ..bbb_api import bh3_api
from ..utils.RESOURCE_PATH import PLAYER_PATH, WIKI_PATH


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


def _record_key(record: Dict[str, str]) -> Tuple[str, str, int]:
    """生成单条记录的基础 key（不含出现序号，仅供内部排序后使用）。"""
    return (record.get("time", ""), record.get("content", ""), 0)


def _build_unique_keys(records: List[Dict[str, str]]) -> set[Tuple[str, str, int]]:
    """为一组记录生成带出现序号的唯一 key 集合。

    同一秒内相同内容的第 N 次出现，key 为 (time, content, N)。
    记录必须已按 time 排序，以保证序号稳定。
    """
    counters: Dict[Tuple[str, str], int] = {}
    keys: set[Tuple[str, str, int]] = set()
    for r in records:
        base = (r.get("time", ""), r.get("content", ""))
        count = counters.get(base, 0) + 1
        counters[base] = count
        keys.add((base[0], base[1], count))
    return keys


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

        logger.info(f"[崩坏3] [抽卡记录] type={gacha_type} page={page} API返回 {len(raw_list)} 条")

        skipped_parse = 0
        for raw_item in raw_list:
            record = _parse_record(raw_item.get("item", []))
            if not record.get("time") or not record.get("content"):
                skipped_parse += 1
                continue
            new_records.append(record)
        logger.info(f"[崩坏3] [抽卡记录] type={gacha_type} page={page} 处理完成: 新增 {len(new_records)} 条，解析跳过 {skipped_parse} 条")

        # API 返回不足一页，说明已到最后
        if len(raw_list) < 10:
            break

    return new_records


async def save_gachalogs(uid: str, is_force: bool = False, skip_dedup: bool = False) -> str:
    """增量/全量刷新抽卡记录，返回摘要文本。
    skip_dedup=True 时直接追加 API 数据，不做去重（全量刷新用）。"""
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

        new_records = await _fetch_gacha_type(
            uid, authkey, gacha_type,
            set(), is_force,
        )

        if new_records:
            old_count = len(history[gacha_name])
            if skip_dedup:
                # 全量刷新：用 API 数据替换该卡池，同时对 API 数据内部去重
                api_sorted = sorted(new_records, key=lambda x: x.get("time", ""))
                seen_api: set[Tuple[str, str]] = set()
                deduped_api: list[Dict[str, str]] = []
                for r in api_sorted:
                    base = (r.get("time", ""), r.get("content", ""))
                    if base not in seen_api:
                        seen_api.add(base)
                        deduped_api.append(r)
                history[gacha_name] = deduped_api
                added = len(deduped_api)
                if len(deduped_api) < len(new_records):
                    logger.info(f"[崩坏3] [抽卡记录] {gacha_name}: API 数据去重 {len(new_records)} → {len(deduped_api)}")
                logger.info(f"[崩坏3] [抽卡记录] {gacha_name}: 替换为 API 数据 {added} 条")
            else:
                # 增量刷新：合并本地与 API 数据，按 (time, content) 去重
                merged = history[gacha_name] + new_records
                merged.sort(key=lambda x: x.get("time", ""))
                seen: set[Tuple[str, str]] = set()
                deduped: list[Dict[str, str]] = []
                for r in merged:
                    base = (r.get("time", ""), r.get("content", ""))
                    if base not in seen:
                        seen.add(base)
                        deduped.append(r)
                history[gacha_name] = deduped
                added = len(history[gacha_name]) - old_count
            # 按时间降序排列
            history[gacha_name].sort(key=lambda x: x.get("time", ""), reverse=True)
            deltas[gacha_name] = added
            total_add += added

    # 全量刷新时，对所有卡池（含 API 未覆盖的旧池子）做去重
    if skip_dedup:
        from collections import Counter as _Counter
        for gacha_name, records in history.items():
            key_counts = _Counter(
                (r.get("time", ""), r.get("content", "")) for r in records
            )
            if not key_counts:
                continue
            freq = _Counter(key_counts.values())
            multiplier = freq.most_common(1)[0][0]
            if multiplier > 1:
                # 检测到累积倍数，按倍数恢复
                target: Dict[Tuple[str, str], int] = {}
                sorted_recs = sorted(records, key=lambda x: x.get("time", ""))
                recovered: list[Dict[str, str]] = []
                for r in sorted_recs:
                    base = (r.get("time", ""), r.get("content", ""))
                    count = target.get(base, 0) + 1
                    target[base] = count
                    if count <= max(1, key_counts[base] // multiplier):
                        recovered.append(r)
                history[gacha_name] = recovered
                logger.info(
                    f"[崩坏3] [抽卡记录] {gacha_name}: "
                    f"检测到 {multiplier}x 累积, 恢复 {len(records)} → {len(recovered)} 条"
                )
            else:
                # 无倍数累积，仍做 (time,content) 去重
                seen_set: set[Tuple[str, str]] = set()
                deduped: list[Dict[str, str]] = []
                for r in sorted(records, key=lambda x: x.get("time", "")):
                    base = (r.get("time", ""), r.get("content", ""))
                    if base not in seen_set:
                        seen_set.add(base)
                        deduped.append(r)
                if len(deduped) < len(records):
                    history[gacha_name] = deduped
                    logger.info(
                        f"[崩坏3] [抽卡记录] {gacha_name}: "
                        f"去重 {len(records)} → {len(deduped)} 条"
                    )

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
    """全量刷新：备份旧数据，用 API 数据覆盖相同时间范围，更早的本地数据保留。"""
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

        # 拉取 API 数据（不做去重，直接追加）
        result_msg = await save_gachalogs(uid, is_force=True, skip_dedup=True)

        # 读取拉取后的数据（包含旧数据 + 新追加的 API 数据）
        async with aiofiles.open(gachalogs_path, "r", encoding="utf-8") as f:
            merged_log = json.loads(await f.read())
        merged_history: Dict[str, List[Dict]] = merged_log.get("data", {})

        # 读取备份的旧数据
        async with aiofiles.open(backup_path, "r", encoding="utf-8") as f:
            old_log = json.loads(await f.read())
        old_history: Dict[str, List[Dict]] = old_log.get("data", {})

        # 合并：API 数据（已在 save_gachalogs 中去重）+ 备份中更早的旧数据
        # save_gachalogs 已对所有卡池做了去重/恢复，这里只需合并时间范围
        for gacha_name, old_records in old_history.items():
            api_records = merged_history.get(gacha_name, [])
            if not api_records:
                # API 没拉到该卡池，save_gachalogs 已去重，直接使用
                continue

            # 构建 API 的 (time,content) 集合
            api_keys: set[Tuple[str, str]] = {
                (r.get("time", ""), r.get("content", "")) for r in api_records
            }

            # 保留 API 时间范围之外的旧数据（更早的记录）
            extra: list[Dict[str, str]] = []
            extra_seen: set[Tuple[str, str]] = set()
            for r in sorted(old_records, key=lambda x: x.get("time", "")):
                base = (r.get("time", ""), r.get("content", ""))
                if base not in api_keys and base not in extra_seen:
                    extra_seen.add(base)
                    extra.append(r)

            merged_history[gacha_name] = api_records + extra
            merged_history[gacha_name].sort(key=lambda x: x.get("time", ""), reverse=True)
            if extra:
                logger.info(
                    f"[崩坏3] [抽卡记录] {gacha_name}: "
                    f"API {len(api_records)} 条 + 保留更早旧数据 {len(extra)} 条"
                )

        merged_log["data"] = merged_history
        async with aiofiles.open(gachalogs_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(merged_log, ensure_ascii=False))

        return result_msg
    finally:
        if uid in _full_lock:
            _full_lock.remove(uid)


def _extract_character_name(content: str) -> str | None:
    """从补给内容中提取角色名称。格式: [角色]XXX角色卡"""
    if not content.startswith("[角色]"):
        return None
    name = content.replace("[角色]", "").replace("角色卡", "").strip()
    return name if name else None


def _extract_weapon_name(content: str) -> str | None:
    """从补给内容中提取武器名称。格式: [武器]XXX"""
    if not content.startswith("[武器]"):
        return None
    name = content.replace("[武器]", "").strip()
    return name if name else None


async def _get_character_star_map() -> Dict[str, int]:
    """从本地 wiki 数据获取角色星级映射。返回 {角色名: starValue}"""
    star_map: Dict[str, int] = {}
    try:
        from ..bbb_wiki.resource_update import get_local_index, get_local_detail
        from ..bbb_wiki.wiki_api import parse_evaluation_from_detail
        index = get_local_index("角色")
        if not index:
            logger.info("[崩坏3] [抽卡记录] 角色索引为空，跳过星级查询")
            return star_map
        for cid_str, title in index.items():
            detail = get_local_detail("角色", int(cid_str))
            if not detail:
                continue
            star_value = 0
            # 优先从 ext 字段的 filter 文本中提取初始阶级
            ext = detail.get("ext", "")
            if isinstance(ext, str):
                try:
                    import json as _json
                    ext_data = _json.loads(ext)
                    for v in ext_data.values():
                        filter_text = v.get("filter", {}).get("text", "")
                        if "初始阶级/S" in filter_text:
                            star_value = 4
                            break
                        elif "初始阶级/A" in filter_text:
                            star_value = 3
                            break
                        elif "初始阶级/B" in filter_text:
                            star_value = 2
                            break
                except Exception:
                    pass
            # 回退到 evaluation
            if not star_value:
                evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
                if evaluation:
                    advance = evaluation.get("advanceGeneral", [])
                    if advance:
                        star_value = advance[0].get("starValue", 0)
            if not star_value:
                basic_info = detail.get("basic_info", {})
                rank = basic_info.get("角色评级", "")
                if "S" in rank:
                    star_value = 4
                elif "A" in rank:
                    star_value = 3
                elif "B" in rank:
                    star_value = 2
            if star_value:
                star_map[title] = star_value
        logger.info(f"[崩坏3] [抽卡记录] 角色星级: {len(star_map)}/{len(index)} 条")
    except Exception as e:
        logger.warning(f"[崩坏3] [抽卡记录] 获取角色星级失败: {e}")
    return star_map


async def _get_weapon_star_map() -> Dict[str, int]:
    """从本地 wiki 数据获取武器星级映射。返回 {武器名: starValue}"""
    star_map: Dict[str, int] = {}
    try:
        from ..bbb_wiki.resource_update import get_local_index, get_local_detail
        from ..bbb_wiki.wiki_api import parse_weapon_data_from_detail
        index = get_local_index("武器")
        if not index:
            logger.info("[崩坏3] [抽卡记录] 武器索引为空，跳过星级查询")
            return star_map
        logger.info(f"[崩坏3] [抽卡记录] 武器索引: {len(index)} 条")
        for cid_str, title in index.items():
            detail = get_local_detail("武器", int(cid_str))
            if not detail:
                continue
            weapon_data = detail.get("weapon_data") or parse_weapon_data_from_detail(detail)
            info = weapon_data.get("info", {})
            star_value = info.get("starValue", 0)
            if star_value:
                star_map[title] = star_value
    except Exception as e:
        logger.warning(f"[崩坏3] [抽卡记录] 获取武器星级失败: {e}")
    return star_map


def _get_pool_type(gacha_name: str) -> str:
    """根据卡池名称判断类型：char / weapon / partner"""
    if "武器" in gacha_name or "装备" in gacha_name:
        return "weapon"
    if "协同者" in gacha_name:
        return "partner"
    # 角色补给、家园补给等都是出角色的
    return "char"


def _is_special_item(content: str, pool_type: str, char_star_map: Dict[str, int], weapon_star_map: Dict[str, int]) -> bool:
    """根据卡池类型判断是否为需要高亮的物品。"""
    if pool_type == "char":
        char_name = _extract_character_name(content)
        if char_name and char_name in char_star_map:
            return char_star_map[char_name] >= 4  # S 初始阶级
    elif pool_type == "weapon":
        weapon_name = _extract_weapon_name(content)
        if weapon_name and weapon_name in weapon_star_map:
            return weapon_star_map[weapon_name] >= 5  # 5 星
    elif pool_type == "partner":
        return content.startswith("[协同者]")
    return False


async def get_gacha_summary(uid: str) -> str:
    """生成抽卡记录文本摘要：只显示 S 角色 / 5星武器 / 协同者，带抽数统计。"""
    path = PLAYER_PATH / str(uid)
    gachalogs_path = path / "gacha_logs.json"

    if not gachalogs_path.exists():
        return f"🌱UID{uid} 还没有抽卡记录，请先使用「刷新抽卡记录」。"

    async with aiofiles.open(gachalogs_path, "r", encoding="utf-8") as f:
        gacha_log = json.loads(await f.read())

    data: Dict[str, List[Dict]] = gacha_log.get("data", {})
    if not data:
        return f"🌱UID{uid} 还没有抽卡记录，请先使用「刷新抽卡记录」。"

    data_time = gacha_log.get("data_time", "未知")
    total = sum(len(records) for records in data.values())

    # 获取角色和武器星级映射
    char_star_map = await _get_character_star_map()
    weapon_star_map = await _get_weapon_star_map()

    # 各卡池类型的提示词
    pool_hints = {
        "char": "S 角色",
        "weapon": "5星武器",
        "partner": "协同者",
    }

    parts = [f"📊 UID{uid} 抽卡记录（共 {total} 条）"]
    parts.append(f"数据更新时间：{data_time}")
    parts.append("")

    for gacha_name, records in data.items():
        count = len(records)
        if count == 0:
            parts.append(f"【{gacha_name}】暂无记录")
            continue

        pool_type = _get_pool_type(gacha_name)
        hint = pool_hints.get(pool_type, "特殊物品")

        # 按时间正序排列（从旧到新）
        sorted_records = sorted(records, key=lambda r: r.get("time", ""))

        # 统计特殊物品之间的抽数
        highlights: List[Tuple[str, int, str]] = []  # (内容, 距上次抽数, 时间)
        pull_since_last = 0

        for r in sorted_records:
            content = r.get("content", "未知")
            pull_since_last += 1
            if _is_special_item(content, pool_type, char_star_map, weapon_star_map):
                highlights.append((content, pull_since_last, r.get("time", "")))
                pull_since_last = 0

        # 按时间倒序显示（最新在前）
        highlights.reverse()

        parts.append(f"【{gacha_name}】共 {count} 抽")

        if not highlights:
            parts.append(f"  未抽到{hint}")
            if pull_since_last > 0:
                parts.append(f"  已连续 {pull_since_last} 抽未出")
        else:
            for content, pulls, time_str in highlights:
                parts.append(f"  {content}  ({pulls}抽)  {time_str}")
            if pull_since_last > 0:
                parts.append(f"  ---- 已连续 {pull_since_last} 抽未出 ----")

        parts.append("")

    return "\n".join(parts).strip()


# --- 角色/武器图标缓存路径 ---
CHAR_ICON_CACHE_DIR = WIKI_PATH / "角色" / "icons"
WEAPON_ICON_CACHE_DIR = WIKI_PATH / "武器" / "icons"


def _get_char_icon_path(char_name: str) -> Path | None:
    """根据角色名称获取图标路径（支持别名查找）。"""
    try:
        from ..bbb_alias.name_convert import alias_to_char_name, char_name_to_content_id
        standard_name = alias_to_char_name(char_name) or char_name
        content_id = char_name_to_content_id(standard_name)
        if content_id:
            icon_path = CHAR_ICON_CACHE_DIR / f"{content_id}.png"
            if icon_path.exists():
                return icon_path
    except Exception:
        pass
    return None


def _get_weapon_icon_path(weapon_name: str) -> Path | None:
    """根据武器名称获取图标路径。"""
    try:
        # 尝试从武器索引中查找
        from ..bbb_wiki.resource_update import get_local_index
        index = get_local_index("武器")
        if index:
            for cid_str, title in index.items():
                if title == weapon_name:
                    icon_path = WEAPON_ICON_CACHE_DIR / f"{cid_str}.png"
                    if icon_path.exists():
                        return icon_path
    except Exception:
        pass
    return None


async def get_gacha_summary_data(uid: str, ev=None) -> Dict | str:
    """生成抽卡记录结构化数据，供图片渲染使用。"""
    path = PLAYER_PATH / str(uid)
    gachalogs_path = path / "gacha_logs.json"

    if not gachalogs_path.exists():
        return f"UID{uid} 还没有抽卡记录，请先使用「刷新抽卡记录」。"

    async with aiofiles.open(gachalogs_path, "r", encoding="utf-8") as f:
        gacha_log = json.loads(await f.read())

    data: Dict[str, List[Dict]] = gacha_log.get("data", {})
    if not data:
        return f"UID{uid} 还没有抽卡记录，请先使用「刷新抽卡记录」。"

    # 获取玩家信息
    nickname = "未知舰长"
    level = 0
    login_days = 0
    rating = "C"

    try:
        index_data = await bh3_api.get_bbb_index(uid)
        if isinstance(index_data, Dict):
            role = index_data.get("role", {})
            stats = index_data.get("stats", {})
            pref = index_data.get("preference", {})
            nickname = role.get("nickname", nickname)
            level = role.get("level", level)
            login_days = stats.get("active_day_number", login_days)
            rating = pref.get("comprehensive_rating", rating)
    except Exception as e:
        logger.warning(f"[崩坏3] [抽卡记录] 获取玩家信息失败: {e}")

    # 获取角色和武器星级映射
    char_star_map = await _get_character_star_map()
    weapon_star_map = await _get_weapon_star_map()

    # 构建卡池数据
    pools = []
    for gacha_name, records in data.items():
        count = len(records)
        if count == 0:
            continue

        pool_type = _get_pool_type(gacha_name)

        # 按时间正序排列（从旧到新）
        sorted_records = sorted(records, key=lambda r: r.get("time", ""))

        # 统计特殊物品之间的抽数
        items = []
        pull_since_last = 0
        gold_count = 0
        pull_counts = []  # 记录每次出金的抽数

        for r in sorted_records:
            content = r.get("content", "未知")
            pull_since_last += 1
            if _is_special_item(content, pool_type, char_star_map, weapon_star_map):
                # 提取名称
                item_name = content
                icon_path = None
                if pool_type == "char":
                    char_name = _extract_character_name(content)
                    if char_name:
                        item_name = char_name
                        icon_path = _get_char_icon_path(char_name)
                elif pool_type == "weapon":
                    weapon_name = _extract_weapon_name(content)
                    if weapon_name:
                        item_name = weapon_name
                        icon_path = _get_weapon_icon_path(weapon_name)

                items.append({
                    "name": item_name,
                    "content": content,
                    "icon_path": icon_path,
                    "pulls": pull_since_last,
                    "time": r.get("time", ""),
                })
                pull_counts.append(pull_since_last)
                gold_count += 1
                pull_since_last = 0

        # 计算统计数据
        avg_pulls = sum(pull_counts) / len(pull_counts) if pull_counts else 0
        max_pulls = max(pull_counts) if pull_counts else 0
        avg_rate = f"{(gold_count / count * 100):.1f}%" if count > 0 else "0%"

        # 时间范围
        start_time = sorted_records[0].get("time", "") if sorted_records else ""
        end_time = sorted_records[-1].get("time", "") if sorted_records else ""

        # 按时间倒序显示（最新在前）
        items.reverse()

        pools.append({
            "name": gacha_name,
            "type": pool_type,
            "total_pulls": count,
            "gold_count": gold_count,
            "start_time": start_time,
            "end_time": end_time,
            "avg_pulls": round(avg_pulls, 1),
            "max_pulls": max_pulls,
            "avg_rate": avg_rate,
            "items": items,
            "current_pity": pull_since_last,  # 当前距离上次出金的抽数
        })

    return {
        "uid": uid,
        "nickname": nickname,
        "level": level,
        "login_days": login_days,
        "rating": rating,
        "index_data": index_data if isinstance(index_data, Dict) else {},
        "pools": pools,
    }
