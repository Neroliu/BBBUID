import json
import re
import urllib.parse
from typing import Dict, List, Optional

import httpx

WIKI_BASE = "https://api-takumi-static.mihoyo.com/common/blackboard/bh3_wiki"
APP_SN = "bh3_wiki"

CHANNEL_MAP = {
    "女武神": 18,
    "角色": 18,
    "武器": 20,
    "圣痕": 19,
    "人偶": 21,
    "协同者": 218,
}


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
    }
    for section in result["contents"]:
        parsed = _parse_html_data(section.get("text", ""))
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


async def find_content_by_name(name: str, channel_id: int) -> Optional[Dict]:
    items = await get_channel_content_list(channel_id)
    for item in items:
        if item["title"] == name:
            return item
    for item in items:
        if name in item["title"]:
            return item
    return None
