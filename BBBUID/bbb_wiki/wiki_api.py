import json
import re
import urllib.parse
from typing import Dict, List, Optional

import httpx

WIKI_BASE = "https://api-takumi-static.mihoyo.com/common/blackboard/bh3_wiki"
APP_SN = "bh3_wiki"


async def _get(path: str, params: Optional[Dict] = None) -> Optional[Dict]:
    url = f"{WIKI_BASE}{path}"
    if params is None:
        params = {}
    params["app_sn"] = APP_SN
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("retcode") == 0:
            return data.get("data")
        return None


async def get_channel_content_list(channel_id: int) -> List[Dict]:
    data = await _get("/v1/home/content/list", {"channel_id": channel_id})
    if not data or not data.get("list"):
        return []
    items = data["list"][0].get("list", [])
    result = []
    for item in items:
        ext = json.loads(item.get("ext", "{}"))
        channel_key = f"c_{channel_id}"
        filters = []
        if channel_key in ext:
            filt_text = ext[channel_key].get("filter", {}).get("text", "[]")
            filters = json.loads(filt_text)
        result.append({
            "content_id": item["content_id"],
            "title": item["title"],
            "filters": filters,
        })
    return result


def _parse_html_data(html: str) -> List[Dict]:
    match = re.search(r'data-data="([^"]*)"', html)
    if not match:
        return []
    try:
        decoded = urllib.parse.unquote(match.group(1))
        return json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return []


def _strip_html(html: str) -> str:
    import html as html_mod
    text = re.sub(r"<[^>]+>", "", html).strip()
    return html_mod.unescape(text)


def _parse_role_evaluation(parsed_items: List[Dict]) -> Dict:
    result: Dict = {
        "avatar": "",
        "hexagon": [],
        "finalLevel": "",
        "subFields": [],
        "equipments": [],
        "advanceGeneral": [],
        "advanceData": [],
    }
    for item in parsed_items:
        data = item.get("data", {})
        part = item.get("partKey", "")
        if part == "basicIntroduction":
            result["avatar"] = data.get("avatar", "")
            result["hexagon"] = data.get("hexagon", [])
            result["finalLevel"] = data.get("finalLevel", "")
            for sf in data.get("subFields", []):
                result["subFields"].append({
                    "name": sf.get("name", ""),
                    "value": _strip_html(sf.get("value", "")),
                })
        elif part == "equipmentRecommendation":
            for eq_group in data.get("equipment", []):
                name_ = eq_group.get("name_", "")
                if "推荐" not in name_:
                    continue
                equips = []
                for eq in eq_group.get("equips", []):
                    equips.append({
                        "title": eq.get("title", ""),
                        "icon": eq.get("icon", ""),
                    })
                result["equipments"].append({
                    "label": name_,
                    "equips": equips,
                    "reason": _strip_html(eq_group.get("reason", "")),
                })
        elif part == "advanceGeneral":
            for ag in data.get("advanceGeneral", []):
                result["advanceGeneral"].append({
                    "icon": ag.get("icon", ""),
                    "desc": _strip_html(ag.get("desc", "")),
                    "cost": ag.get("cost", ""),
                })
        elif part == "advanceData":
            for ad in data.get("advanceData", []):
                result["advanceData"].append({
                    "icon": ad.get("icon", ""),
                    "life": ad.get("life", ""),
                    "energy": ad.get("energy", ""),
                    "attack": ad.get("attack", ""),
                    "defense": ad.get("defense", ""),
                    "understanding": ad.get("understanding", ""),
                })
    return result


async def get_content_detail(content_id: int) -> Optional[Dict]:
    data = await _get("/v1/content/info", {"content_id": content_id})
    if not data:
        return None
    content = data.get("content", {})
    result = {
        "id": content.get("id"),
        "title": content.get("title"),
        "icon": content.get("icon"),
        "summary": content.get("summary"),
        "contents": content.get("contents", []),
        "ext": content.get("ext", ""),
        "basic_info": {},
        "evaluation": {},
    }
    is_weapon = False
    for section in result["contents"]:
        parsed = _parse_html_data(section.get("text", ""))
        if not parsed:
            continue
        for item in parsed:
            if item.get("tmplKey") == "valkyrie" and item.get("partKey") == "basicIntroduction":
                fields = {}
                for f in item["data"].get("mainFields", []):
                    if f.get("nameL") and f.get("valueL"):
                        fields[f["nameL"]] = f["valueL"]
                    if f.get("nameR") and f.get("valueR"):
                        fields[f["nameR"]] = f["valueR"]
                result["basic_info"] = fields
            if item.get("tmplKey") == "weapon" and item.get("partKey") == "info":
                is_weapon = True
        if section.get("name") == "角色评价":
            result["evaluation"] = _parse_role_evaluation(parsed)
    if is_weapon:
        result["weapon_data"] = _parse_weapon_data(result["contents"])
    return result


async def search_content(keyword: str, channel_id: Optional[int] = None) -> List[Dict]:
    params = {"keyword": keyword, "page": 1}
    if channel_id:
        params["channel_id"] = channel_id
    data = await _get("/v1/search/content", params)
    if not data:
        return []
    results = []
    for item in data.get("list", []):
        channels = item.get("channels", [])
        channel_name = channels[0]["name"] if channels else ""
        results.append({
            "id": item["id"],
            "title": item["title"],
            "summary": item.get("summary", ""),
            "icon": item.get("icon", ""),
            "channel_name": channel_name,
            "bbs_url": item.get("bbs_url", ""),
        })
    return results


def parse_evaluation_from_detail(detail: Dict) -> Dict:
    for section in detail.get("contents", []):
        if section.get("name") in ("角色评价", "协同者评价"):
            parsed = _parse_html_data(section.get("text", ""))
            if parsed:
                return _parse_role_evaluation(parsed)
    return {"avatar": "", "hexagon": [], "finalLevel": "", "subFields": [], "equipments": [], "advanceGeneral": [], "advanceData": []}


async def find_content_by_name(name: str, channel_id: int) -> Optional[Dict]:
    items = await get_channel_content_list(channel_id)
    for item in items:
        if item["title"] == name:
            return item
    for item in items:
        if name in item["title"]:
            return item
    return None


def _parse_weapon_data(contents: list) -> Dict:
    result: Dict = {
        "info": {},
        "skills": [],
        "forging": {},
        "materials": [],
        "gainMethods": [],
        "syncMaterials": [],
        "roles": [],
    }
    for section in contents:
        parsed = _parse_html_data(section.get("text", ""))
        if not parsed:
            continue
        for item in parsed:
            tk = f"{item.get('tmplKey', '')}:{item.get('partKey', '')}"
            data = item.get("data", {})
            if tk == "weapon:info":
                result["info"] = {
                    "starValue": data.get("starValue", 0),
                    "attr": data.get("attr", []),
                    "icon": data.get("icon", ""),
                }
            elif tk == "weapon:skill":
                for a in data.get("attr", []):
                    result["skills"].append({
                        "key": a.get("key", ""),
                        "value": _strip_html(a.get("value", "")),
                    })
            elif tk == "weapon:forging":
                result["forging"] = {
                    "material": data.get("material", []),
                    "otherMaterial": data.get("otherMaterial", []),
                }
            elif tk in ("stigmata:material", "general:material"):
                result["materials"] = data.get("list", [])
            elif tk == "general:gainMethod":
                title = data.get("title", "")
                methods = []
                for gm in data.get("gainMethod", []):
                    methods.append({
                        "key": gm.get("key", ""),
                        "value": _strip_html(gm.get("value", "")),
                    })
                if "同调" in title:
                    # Extract linked items with content IDs for icon lookup
                    items = []
                    for gm in data.get("gainMethod", []):
                        raw_val = gm.get("value", "")
                        links = re.findall(
                            r'href="(/bh3/wiki/content/(\d+)/detail)[^"]*"[^>]*>([^<]+)',
                            raw_val,
                        )
                        if links:
                            for url, cid, name in links:
                                items.append({
                                    "name": name.strip(),
                                    "content_id": int(cid),
                                    "url": url,
                                })
                        else:
                            items.append({
                                "name": _strip_html(raw_val),
                                "content_id": 0,
                                "url": "",
                            })
                    result["syncMaterials"].extend(items)
                else:
                    result["gainMethods"].extend(methods)
            elif tk == "weapon:role":
                for a in data.get("attr", []):
                    result["roles"].append({
                        "icon": a.get("icon", ""),
                        "key": a.get("key", ""),
                        "value": _strip_html(a.get("value", "")),
                        "starValue": a.get("starValue", 0),
                    })
    return result


def parse_weapon_data_from_detail(detail: Dict) -> Dict:
    return _parse_weapon_data(detail.get("contents", []))
