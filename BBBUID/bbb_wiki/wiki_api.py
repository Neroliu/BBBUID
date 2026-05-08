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
    return re.sub(r"<[^>]+>", "", html).strip()


def _parse_role_evaluation(parsed_items: List[Dict]) -> Dict:
    result: Dict = {
        "avatar": "",
        "hexagon": [],
        "subFields": [],
        "equipments": [],
    }
    for item in parsed_items:
        data = item.get("data", {})
        part = item.get("partKey", "")
        if part == "basicIntroduction":
            result["avatar"] = data.get("avatar", "")
            result["hexagon"] = data.get("hexagon", [])
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
                break
        if section.get("name") == "角色评价":
            result["evaluation"] = _parse_role_evaluation(parsed)
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
        if section.get("name") == "角色评价":
            parsed = _parse_html_data(section.get("text", ""))
            if parsed:
                return _parse_role_evaluation(parsed)
    return {"avatar": "", "hexagon": [], "subFields": [], "equipments": []}


async def find_content_by_name(name: str, channel_id: int) -> Optional[Dict]:
    items = await get_channel_content_list(channel_id)
    for item in items:
        if item["title"] == name:
            return item
    for item in items:
        if name in item["title"]:
            return item
    return None
