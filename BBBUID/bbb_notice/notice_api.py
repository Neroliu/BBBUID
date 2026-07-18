"""崩坏3公告 API (getNewsList + home/new + getPostFull)"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from enum import IntEnum
from typing import Dict, List, Optional

import httpx
from gsuid_core.logger import logger
from gsuid_core.utils.api.mys.tools import get_web_ds_token

NEWS_LIST_URL = "https://bbs-api-static.miyoushe.com/painter/api/getNewsList"
HOME_NEW_URL = "https://bbs-api.miyoushe.com/apihub/api/home/new"
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
    ANNOUNCE = 1  # 公告
    ACTIVITY = 2  # 活动
    INFO = 3  # 资讯

    @property
    def label(self) -> str:
        return {1: "公告", 2: "活动", 3: "资讯"}[int(self)]


NOTICE_TYPES = (BBBNoticeType.ANNOUNCE, BBBNoticeType.ACTIVITY, BBBNoticeType.INFO)


class BBBNoticePost:
    __slots__ = ("post_id", "subject", "created_at", "cover_url")

    def __init__(self, post_id: int, subject: str, created_at: int, cover_url: str):
        self.post_id = post_id
        self.subject = subject
        self.created_at = created_at
        self.cover_url = cover_url


class BBBNoticeDetail:
    __slots__ = ("post_id", "subject", "created_at", "content_blocks")

    def __init__(self, post_id: int, subject: str, created_at: int, content_blocks: List[tuple]):
        self.post_id = post_id
        self.subject = subject
        self.created_at = created_at
        self.content_blocks = content_blocks


def _ds_header() -> Dict[str, str]:
    header = deepcopy(_HEADER)
    header["DS"] = get_web_ds_token(web=True)
    return header


# ════════════════════════════════════════════
#  标题前缀 → 分类推断
# ════════════════════════════════════════════

_PREFIX_MAP = [
    ("【公告】", BBBNoticeType.ANNOUNCE),
    ("【补给】", BBBNoticeType.ANNOUNCE),
    ("【活动】", BBBNoticeType.ACTIVITY),
    ("【有奖活动】", BBBNoticeType.ACTIVITY),
    ("【生日活动】", BBBNoticeType.ACTIVITY),
    ("【资讯】", BBBNoticeType.INFO),
    ("【商品资讯】", BBBNoticeType.INFO),
    ("【活动资讯】", BBBNoticeType.INFO),
]


def _infer_type(subject: str) -> BBBNoticeType:
    for prefix, ntype in _PREFIX_MAP:
        if subject.startswith(prefix):
            return ntype
    return BBBNoticeType.ANNOUNCE


def _merge_posts(primary: List[BBBNoticePost], extra: List[BBBNoticePost]) -> List[BBBNoticePost]:
    """合并两个帖子列表, 去重, 按时间降序。"""
    existing = {p.post_id for p in primary}
    merged = list(primary)
    for p in extra:
        if p.post_id not in existing:
            merged.append(p)
            existing.add(p.post_id)
    merged.sort(key=lambda p: p.created_at, reverse=True)
    return merged


# ════════════════════════════════════════════
#  getNewsList
# ════════════════════════════════════════════


async def _fetch_news_list(notice_type: BBBNoticeType, page_size: int) -> List[BBBNoticePost]:
    """纯 getNewsList 拉取 (不含 home/new 合并)。"""
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
            resp = await client.get(NEWS_LIST_URL, headers=_ds_header(), params=params, timeout=15)
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取 NewsList 失败 type={notice_type}: {e}")
        return []

    if data.get("retcode") != 0:
        logger.warning(f"[崩坏3公告] NewsList 错误 type={notice_type}: {data.get('retcode')}")
        return []

    posts: List[BBBNoticePost] = []
    for item in data.get("data", {}).get("list", []):
        post = item.get("post", {})
        pid = post.get("post_id")
        subj = post.get("subject", "")
        cat = post.get("created_at", 0)
        if not pid or not subj:
            continue
        posts.append(BBBNoticePost(int(pid), subj, int(cat), _pick_cover(item, post)))
    return posts


# ════════════════════════════════════════════
#  home/new
# ════════════════════════════════════════════


async def get_home_official_posts() -> List[BBBNoticePost]:
    """从 home/new 接口拉取首页 official 公告。"""
    params = {
        "gids": "1",
        "parts": "4",
        "device": "Vivo V2185A",
        "cpu": "placeholder",
        "version": "3",
        "is_triggered_by_resource": "false",
        "exposed_resource_tickets": "",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(HOME_NEW_URL, headers=_ds_header(), params=params, timeout=15)
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取 home/new 失败: {e}")
        return []

    if data.get("retcode") != 0:
        logger.warning(f"[崩坏3公告] home/new 错误: {data.get('retcode')}")
        return []

    official = data.get("data", {}).get("official", {})
    items = official.get("data", []) if isinstance(official, dict) else []

    posts: List[BBBNoticePost] = []
    for item in items:
        pid = item.get("post_id")
        title = item.get("title", "")
        date_str = item.get("date", "0")
        image_url = item.get("image_url", "")
        image_obj = item.get("image")
        if isinstance(image_obj, dict) and image_obj.get("url"):
            image_url = image_obj["url"]
        if not pid or not title:
            continue
        posts.append(BBBNoticePost(int(pid), title, int(date_str), image_url))
    return posts


# ════════════════════════════════════════════
#  对外接口: 带 home/new 合并
# ════════════════════════════════════════════


async def get_news_list(notice_type: BBBNoticeType, page_size: int = 20) -> List[BBBNoticePost]:
    """拉取指定分类, 并合并 home/new 中同分类的补充帖子。"""
    posts = await _fetch_news_list(notice_type, page_size)
    home_posts = await get_home_official_posts()
    home_filtered = [p for p in home_posts if _infer_type(p.subject) == notice_type]
    return _merge_posts(posts, home_filtered)


async def get_all_news_list(page_size: int = 20) -> Dict[BBBNoticeType, List[BBBNoticePost]]:
    """并发拉取全部分类, 并合并 home/new 补充数据 (home/new 只请求一次)。"""
    tasks = [_fetch_news_list(t, page_size) for t in NOTICE_TYPES]
    tasks.append(get_home_official_posts())
    *type_results, home_posts = await asyncio.gather(*tasks)

    columns: Dict[BBBNoticeType, List[BBBNoticePost]] = dict(zip(NOTICE_TYPES, type_results))

    for post in home_posts:
        target = _infer_type(post.subject)
        if target in columns:
            columns[target] = _merge_posts(columns[target], [post])

    return columns


# ════════════════════════════════════════════
#  帖子详情
# ════════════════════════════════════════════


async def get_post_detail(post_id: int) -> Optional[BBBNoticeDetail]:
    params = {"post_id": str(post_id)}
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(POST_DETAIL_URL, headers=_ds_header(), params=params, timeout=15)
            data = resp.json()
    except Exception as e:
        logger.warning(f"[崩坏3公告] 拉取详情失败 post_id={post_id}: {e}")
        return None

    if data.get("retcode") != 0:
        logger.warning(f"[崩坏3公告] 详情错误 post_id={post_id}: {data.get('retcode')}")
        return None

    post_data = data.get("data", {}).get("post", {}).get("post", {})
    if not post_data:
        return None

    blocks = _parse_structured_content(post_data.get("structured_content", ""))
    if not any(b[0] == "image" for b in blocks):
        for img_url in post_data.get("images", []):
            if img_url:
                blocks.append(("image", img_url))

    return BBBNoticeDetail(
        post_id=post_id,
        subject=post_data.get("subject", ""),
        created_at=int(post_data.get("created_at", 0)),
        content_blocks=blocks,
    )


# ════════════════════════════════════════════
#  工具函数
# ════════════════════════════════════════════


def _parse_structured_content(raw: str) -> List[tuple]:
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

    def _flush():
        if text_buf:
            merged = "".join(text_buf)
            for para in merged.split("\n"):
                s = para.strip()
                if s:
                    blocks.append(("text", s, {}))
            text_buf.clear()

    for item in payload:
        if not isinstance(item, dict):
            continue
        insert = item.get("insert")
        if isinstance(insert, dict) and "image" in insert:
            _flush()
            blocks.append(("image", insert["image"]))
            continue
        if isinstance(insert, dict) and "vod" in insert:
            vod = insert["vod"]
            if isinstance(vod, dict):
                cover = vod.get("cover", "")
                if cover:
                    _flush()
                    blocks.append(("image", cover))
            continue
        if isinstance(insert, str):
            text_buf.append(insert)
            continue

    _flush()
    return blocks


def get_article_url(post_id: int) -> str:
    return MIYOUSHE_ARTICLE_URL.format(post_id=post_id)


def _pick_cover(item: Dict, post: Dict) -> str:
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
