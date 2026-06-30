"""崩坏3公告 API 请求 (米游社 BBS 帖子)"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

from gsuid_core.logger import logger
from gsuid_core.utils.api.mys.tools import get_web_ds_token

import httpx

BBS_BASE = "https://bbs-api.mihoyo.com"
FORUM_POST_LIST_URL = BBS_BASE + "/post/api/getForumPostList"
POST_DETAIL_URL = BBS_BASE + "/post/api/getPostFull"

# 崩坏3官方版块
BH3_FORUM_ID = "6"

_HEADER = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36 miHoYoBBS/2.102.1",
    "x-rpc-app_version": "2.102.1",
    "x-rpc-client_type": "5",
    "Referer": "https://webstatic.mihoyo.com/",
    "Origin": "https://webstatic.mihoyo.com",
}

MIYOUSHE_ARTICLE_URL = "https://www.miyoushe.com/bh3/article/{post_id}"


async def get_bbb_notice_list(page_size: int = 20) -> List[Dict]:
    """从崩坏3版块(forum_id=6)拉取最新帖子列表。

    返回 [{post_id, subject, created_at, ...}, ...]
    """
    header = deepcopy(_HEADER)
    header["DS"] = get_web_ds_token(web=True)
    params = {
        "forum_id": BH3_FORUM_ID,
        "is_good": "false",
        "is_hot": "false",
        "page_size": str(page_size),
        "sort_type": "1",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(FORUM_POST_LIST_URL, headers=header, params=params, timeout=15)
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取帖子列表失败: {e}")
        return []

    if data.get("retcode") != 0:
        logger.warning(f"[崩坏3公告] API返回错误: {data.get('retcode')} {data.get('message')}")
        return []

    posts = []
    for item in data.get("data", {}).get("list", []):
        post = item.get("post", {})
        post_id = post.get("post_id", "")
        subject = post.get("subject", "")
        created_at = post.get("created_at", 0)
        if post_id and subject:
            posts.append({
                "post_id": str(post_id),
                "subject": subject,
                "created_at": created_at,
            })
    return posts


async def get_bbb_notice_detail(post_id: str) -> Dict | None:
    """获取帖子详情。"""
    header = deepcopy(_HEADER)
    header["DS"] = get_web_ds_token(web=True)
    params = {"post_id": post_id}
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(POST_DETAIL_URL, headers=header, params=params, timeout=15)
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取帖子详情失败 post_id={post_id}: {e}")
        return None

    if data.get("retcode") != 0:
        logger.warning(f"[崩坏3公告] API返回错误: {data.get('retcode')} {data.get('message')}")
        return None

    return data.get("data")


def get_article_url(post_id: str) -> str:
    return MIYOUSHE_ARTICLE_URL.format(post_id=post_id)
