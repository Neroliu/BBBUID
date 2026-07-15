"""崩坏3公告 API (米游社 painter/getNewsList + getPostFull)"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from enum import IntEnum
from typing import Dict, List, Optional

import httpx
from gsuid_core.logger import logger
from gsuid_core.utils.api.mys.tools import get_web_ds_token

NEWS_LIST_URL = "https://bbs-api-static.miyoushe.com/painter/api/getNewsList"
POST_DETAIL_URL = "https://bbs-api.mihoyo.com/post/api/getPostFull"
MIYOUSHE_ARTICLE_URL = "https://www.miyoushe.com/bh3/article/{post_id}"

_HEADER = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36 "
        "miHoYoBBS/2.102.1"
    ),
    "x-rpc-app_version": "2.102.1",
    "x-rpc-client_type": "5",
    "Referer": "https://webstatic.mihoyo.com/",
    "Origin": "https://webstatic.mihoyo.com",
}


class BBBNoticeType(IntEnum):
    """公告分类 (对应 getNewsList type 参数)"""

    ANNOUNCE = 1  # 公告
    ACTIVITY = 2  # 活动
    INFO = 3  # 资讯

    @property
    def label(self) -> str:
        return {
            BBBNoticeType.ANNOUNCE: "公告",
            BBBNoticeType.ACTIVITY: "活动",
            BBBNoticeType.INFO: "资讯",
        }[self]


NOTICE_TYPES = (BBBNoticeType.ANNOUNCE, BBBNoticeType.ACTIVITY, BBBNoticeType.INFO)


class BBBNoticePost:
    """公告帖子轻量结构 (列表用)"""

    __slots__ = ("post_id", "subject", "created_at", "cover_url")

    def __init__(self, post_id: int, subject: str, created_at: int, cover_url: str):
        self.post_id = post_id
        self.subject = subject
        self.created_at = created_at
        self.cover_url = cover_url


class BBBNoticeDetail:
    """公告详情 (含结构化内容)"""

    __slots__ = ("post_id", "subject", "created_at", "content_blocks")

    def __init__(
        self,
        post_id: int,
        subject: str,
        created_at: int,
        content_blocks: List[tuple],
    ):
        self.post_id = post_id
        self.subject = subject
        self.created_at = created_at
        self.content_blocks = content_blocks  # [("text", str, attrs), ("image", url), ...]


def _ds_header() -> Dict[str, str]:
    header = deepcopy(_HEADER)
    header["DS"] = get_web_ds_token(web=True)
    return header


async def get_news_list(
    notice_type: BBBNoticeType,
    page_size: int = 20,
) -> List[BBBNoticePost]:
    """从 getNewsList 拉取指定分类的公告列表。"""
    params = {
        "client_type": "2",
        "gids": "1",
        "is_official_tab": "true",
        "last_id": "",
        "page_size": str(page_size),
        "type": str(int(notice_type)),
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                NEWS_LIST_URL, headers=_ds_header(), params=params, timeout=15,
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取列表失败 type={notice_type}: {e}")
        return []

    if data.get("retcode") != 0:
        logger.warning(
            f"[崩坏3公告] API错误 type={notice_type}: "
            f"{data.get('retcode')} {data.get('message')}"
        )
        return []

    posts: List[BBBNoticePost] = []
    for item in data.get("data", {}).get("list", []):
        post = item.get("post", {})
        post_id_raw = post.get("post_id")
        subject = post.get("subject", "")
        created_at = post.get("created_at", 0)
        if not post_id_raw or not subject:
            continue
        posts.append(
            BBBNoticePost(
                post_id=int(post_id_raw),
                subject=subject,
                created_at=int(created_at),
                cover_url=_pick_cover(item, post),
            )
        )
    return posts


async def get_all_news_list(
    page_size: int = 20,
) -> Dict[BBBNoticeType, List[BBBNoticePost]]:
    """并发拉取全部三种分类的公告列表。"""
    tasks = [get_news_list(t, page_size) for t in NOTICE_TYPES]
    results = await asyncio.gather(*tasks)
    return dict(zip(NOTICE_TYPES, results))


async def get_post_detail(post_id: int) -> Optional[BBBNoticeDetail]:
    """获取帖子详情, 解析 structured_content (Quill Delta JSON)。"""
    params = {"post_id": str(post_id)}
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                POST_DETAIL_URL, headers=_ds_header(), params=params, timeout=15,
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取详情失败 post_id={post_id}: {e}")
        return None

    if data.get("retcode") != 0:
        logger.warning(
            f"[崩坏3公告] 详情API错误 post_id={post_id}: "
            f"{data.get('retcode')} {data.get('message')}"
        )
        return None

    post_data = data.get("data", {}).get("post", {}).get("post", {})
    if not post_data:
        return None

    subject = post_data.get("subject", "")
    created_at = int(post_data.get("created_at", 0))
    structured_content = post_data.get("structured_content", "")

    blocks = _parse_structured_content(structured_content)

    # 如果 structured_content 解析不到图片, 回退到 post.images
    has_image = any(b[0] == "image" for b in blocks)
    if not has_image:
        for img_url in post_data.get("images", []):
            if img_url:
                blocks.append(("image", img_url))

    return BBBNoticeDetail(
        post_id=post_id,
        subject=subject,
        created_at=created_at,
        content_blocks=blocks,
    )


def _parse_structured_content(raw: str) -> List[tuple]:
    """解析 Quill Delta JSON → [(type, ...)] 列表。

    - ("text", text_str, {"bold": bool, "color": str|None, "align": str|None})
    - ("image", url_str)
    """
    import json

    blocks: List[tuple] = []
    if not raw:
        return blocks

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return blocks

    if not isinstance(payload, list):
        return blocks

    text_buf: List[str] = []

    def _flush_text():
        if text_buf:
            merged = "".join(text_buf)
            # 按 \n 拆成段落
            for para in merged.split("\n"):
                stripped = para.strip()
                if stripped:
                    blocks.append(("text", stripped, {}))
            text_buf.clear()

    for item in payload:
        if not isinstance(item, dict):
            continue

        insert = item.get("insert")
        attrs = item.get("attributes", {}) or {}

        # 图片
        if isinstance(insert, dict) and "image" in insert:
            _flush_text()
            blocks.append(("image", insert["image"]))
            continue

        # 文本
        if isinstance(insert, str):
            text_buf.append(insert)
            continue

    _flush_text()
    return blocks


def get_article_url(post_id: int) -> str:
    return MIYOUSHE_ARTICLE_URL.format(post_id=post_id)


def _pick_cover(item: Dict, post: Dict) -> str:
    """从 item 中选取封面图 URL (cover > image_list > post.images)。"""
    cover = item.get("cover")
    if isinstance(cover, dict) and cover.get("url"):
        return cover["url"]
    image_list = item.get("image_list") or []
    if image_list and isinstance(image_list[0], dict) and image_list[0].get("url"):
        return image_list[0]["url"]
    images = post.get("images") or []
    if images:
        return images[0] if isinstance(images[0], str) else ""
    return ""
