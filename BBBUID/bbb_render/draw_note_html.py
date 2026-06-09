"""便笺卡 HTML 渲染版本（playwright + jinja2）。

入口：`draw_note_img_html(ev, uid, index_data, note_data) -> bytes`，
返回 PNG 字节流。当 `UseHtmlRender` 开启时由 `bbb_data/__init__.py` 调用。
"""
from __future__ import annotations

import base64
import json
import time
import random
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, List

from PIL import Image

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..bbb_data.avatar_utils import get_cached_avatar, draw_decorated_avatar
from ..bbb_data.draw_title import EVAL_RATING_TO_ICON
from ..utils.RESOURCE_PATH import WIKI_PATH
from .runner import render_html_to_bytes
from .templates import file_uri, render_template

# 与 PIL 版本一致
W = 1400
H = 1150

CST = timezone(timedelta(hours=8))

NOTE_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "note_res"
TITLE_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "title"
INFO_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "info"
EVAL_RES_DIR = Path(__file__).parent.parent / "bbb_data" / "res" / "eval_icon"
FOOTER_PATH = Path(__file__).parent.parent / "bbb_data" / "footer.png"


def _res_uri(name: str) -> str | None:
    p = NOTE_RES_DIR / name
    return file_uri(p) if p.exists() else None


def _img_to_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _fmt_recover(seconds: int) -> str:
    if seconds <= 0:
        return "已回满"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}时")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}分")
    return "".join(parts) if parts else "即将回满"


def _fmt_schedule_end(ts: str) -> str:
    try:
        end_ts = int(ts)
        if end_ts > 1e12:
            end_ts = end_ts // 1000
        now = datetime.now(tz=CST).timestamp()
        remain = int(end_ts - now)
        if remain <= 0:
            return "已结束"
        return _fmt_recover(remain)
    except Exception:
        return "未知"


async def _pick_random_wallpaper_uri() -> str | None:
    """Pick a random wallpaper: check compressed cache, else original cache, else download."""
    from ..bbb_wiki.resource_update import (
        _cache_wallpaper_links,
        _get_compressed_cache_dir,
        _get_wallpaper_cache_dir,
        _enforce_wallpaper_cache_limits,
    )

    wp_path = WIKI_PATH / "壁纸"
    index_file = wp_path / "index.json"
    if not index_file.exists():
        return None
    try:
        t0 = time.time()
        index = json.loads(index_file.read_text(encoding="utf-8"))
        if not index:
            return None
        content_ids = list(index.keys())
        random.shuffle(content_ids)

        for cid in content_ids[:10]:
            cid = int(cid)
            comp_dir = _get_compressed_cache_dir(cid)

            # 1) Check compressed cache first
            comp_files = sorted(comp_dir.glob("*.jpg"), key=lambda f: f.stat().st_mtime)
            if comp_files:
                f = random.choice(comp_files)
                try:
                    with Image.open(f) as img:
                        if img.width >= 800:
                            logger.info(f"[崩坏3] [便笺渲染] 壁纸命中压缩缓存: {cid}/{f.name} ({time.time()-t0:.2f}s)")
                            return file_uri(f)
                except Exception:
                    continue

            # 2) No compressed cache - check original and generate compressed
            orig_dir = _get_wallpaper_cache_dir(cid)
            if orig_dir.exists():
                orig_files = sorted(orig_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
                if orig_files:
                    f = random.choice(orig_files)
                    try:
                        t1 = time.time()
                        with Image.open(f) as img:
                            if img.width >= 800:
                                rgb = img.convert("RGB")
                                buf = BytesIO()
                                rgb.save(buf, format="JPEG", quality=85)
                                comp_path = comp_dir / f"{f.stem}.jpg"
                                comp_dir.mkdir(parents=True, exist_ok=True)
                                comp_path.write_bytes(buf.getvalue())
                                logger.info(f"[崩坏3] [便笺渲染] 壁纸原图生成压缩缓存: {cid}/{f.name} (gen {time.time()-t1:.2f}s, total {time.time()-t0:.2f}s)")
                                return file_uri(comp_path)
                    except Exception:
                        continue

            # 3) No original cache - download from links
            links_file = wp_path / "wallpaper_links" / f"{cid}.json"
            if not links_file.exists():
                from ..bbb_wiki.wiki_api import get_content_detail
                detail = await get_content_detail(cid)
                if not detail:
                    continue
                await _cache_wallpaper_links(cid, detail)

            if not links_file.exists():
                continue

            urls = json.loads(links_file.read_text(encoding="utf-8"))
            if not urls:
                continue
            random.shuffle(urls)

            for idx, url in enumerate(urls):
                comp_path = comp_dir / f"{idx}.jpg"
                if comp_path.exists():
                    try:
                        with Image.open(comp_path) as img:
                            if img.width >= 800:
                                return file_uri(comp_path)
                    except Exception:
                        continue

                t2 = time.time()
                try:
                    import httpx
                    async with httpx.AsyncClient(follow_redirects=True) as client:
                        resp = await client.get(url, timeout=15)
                        if resp.status_code != 200:
                            continue
                        from io import BytesIO
                        from PIL import Image as PILImage
                        img = PILImage.open(BytesIO(resp.content)).convert("RGBA")
                        if img.width < 800:
                            continue
                        logger.info(f"[崩坏3] [便笺渲染] 壁纸下载: {cid}/{idx} ({time.time()-t2:.2f}s, total {time.time()-t0:.2f}s)")

                        # Save original to wallpaper cache
                        try:
                            cache_dir = _get_wallpaper_cache_dir(cid)
                            cache_path = cache_dir / f"{idx}.png"
                            img.save(str(cache_path), "PNG")
                        except Exception:
                            pass

                        # Save compressed
                        comp_dir.mkdir(parents=True, exist_ok=True)
                        rgb = img.convert("RGB")
                        buf = BytesIO()
                        rgb.save(buf, format="JPEG", quality=85)
                        comp_path.write_bytes(buf.getvalue())

                        await _enforce_wallpaper_cache_limits()
                        return file_uri(comp_path)
                except Exception:
                    continue

    except Exception as e:
        logger.warning(f"[崩坏3] [HTML渲染] 选择壁纸失败: {e}")
    return None


def _build_activities(note_data: Dict) -> List[Dict]:
    activities: List[Dict] = []
    act_y = 393
    act_gap = 20

    ultra = note_data.get("ultra_endless", {}) or {}
    greedy = note_data.get("greedy_endless", {}) or {}
    endless = ultra if ultra else greedy
    if endless:
        score = endless.get("challenge_score", "?")
        is_open = endless.get("is_open", False)
        remain_text = ""
        if is_open:
            r = _fmt_schedule_end(endless.get("schedule_end", "0"))
            remain_text = f"剩余时间 {r}" if r else "未开启"
        else:
            remain_text = "未开启"
        activities.append({"y": act_y, "score_text": str(score), "remain_text": remain_text, "bar_uri": _res_uri("bar02.png")})
        act_y += 140 + act_gap

    bf = note_data.get("battle_field", {}) or {}
    if bf:
        cur_r = bf.get("cur_reward", "?")
        max_r = bf.get("max_reward", "?")
        is_open = bf.get("is_open", False)
        if is_open:
            r = _fmt_schedule_end(bf.get("schedule_end", "0"))
            remain_text = f"剩余时间 {r}" if r else "未开启"
        else:
            remain_text = "未开启"
        activities.append({"y": act_y, "score_text": f"{cur_r} / {max_r}", "remain_text": remain_text, "bar_uri": _res_uri("bar03.png")})
        act_y += 140 + act_gap

    gw = note_data.get("god_war", {}) or {}
    if gw:
        cur_r = gw.get("cur_reward", "?")
        is_open = gw.get("is_open", False)
        r = _fmt_schedule_end(gw.get("schedule_end", "0"))
        remain_text = f"剩余时间 {r}" if r else ""
        activities.append({"y": act_y, "score_text": str(cur_r), "remain_text": remain_text, "bar_uri": _res_uri("bar04.png")})

    return activities


async def draw_note_img_html(
    ev: Event,
    uid: str,
    index_data: Dict,
    note_data: Dict,
) -> bytes:
    role = index_data.get("role", {}) or {}
    stats = index_data.get("stats", {}) or {}
    pref = index_data.get("preference", {}) or {}

    nickname = role.get("nickname", "未知舰长")
    level_raw = role.get("level", "?")
    level = int(level_raw) if str(level_raw).isdigit() else 0
    rating = pref.get("comprehensive_rating", "C")
    active_days_raw = stats.get("active_day_number", "?")
    active_days = int(active_days_raw) if str(active_days_raw).isdigit() else 0

    is_signed = bool(pref.get("community", 0))
    cur_train = note_data.get("current_train_score", 0)
    max_train = note_data.get("max_train_score", 1)
    train_achieved = cur_train >= max_train if max_train > 0 else True

    cur_stamina = note_data.get("current_stamina", 0)
    max_stamina = note_data.get("max_stamina", 1) or 1
    stamina_ratio = max(0.0, min(1.0, cur_stamina / max_stamina))
    recover = note_data.get("stamina_recover_time", 0)
    recover_text = f"剩余回复时间: {_fmt_recover(recover)}" if recover > 0 else ""

    avatar_uri: str | None = None
    try:
        avatar = await get_cached_avatar(ev, ev.user_id)
        decorated = draw_decorated_avatar(avatar, 179)
        avatar_uri = _img_to_data_uri(decorated)
    except Exception as e:
        logger.warning(f"[崩坏3] [HTML渲染] 头像加载失败: {e}")

    # 等级徽章 x 位置 = nickname 起点(309) + UID 文本宽度 + 间距16
    # 28px 字号下: "UID " ≈ 52px, 每位数字 ≈ 17px
    uid_text = f"UID {uid}"
    level_x = 309 + 52 + (len(uid_text) - 4) * 17 + 16

    icon_name = EVAL_RATING_TO_ICON.get(str(rating).upper(), "SealedDanIcon01.png")
    eval_icon_path = EVAL_RES_DIR / icon_name

    ctx = {
        "wallpaper_uri": await _pick_random_wallpaper_uri(),
        "fg1_uri": _res_uri("FG01.png"),
        "fg2_uri": _res_uri("FG02.png"),
        "title_uri": _res_uri("title.png"),
        "yes_tag_uri": _res_uri("yes_tag.png"),
        "no_tag_uri": _res_uri("no_tag.png"),
        "desc_tag_uri": _res_uri("desc_tag.png"),
        "bar01_uri": _res_uri("bar01.png"),
        "line_bar01_uri": _res_uri("line_bar01.png"),
        "line_bar02_uri": _res_uri("line_bar02.png"),
        "player_bar_uri": _res_uri("player_info_bar_long.png"),
        "level_bg_uri": file_uri(TITLE_RES_DIR / "level_bg.png") if (TITLE_RES_DIR / "level_bg.png").exists() else None,
        "info_bg_uri": file_uri(INFO_RES_DIR / "info_bg.png") if (INFO_RES_DIR / "info_bg.png").exists() else None,
        "eval_icon_uri": file_uri(eval_icon_path) if eval_icon_path.exists() else None,
        "footer_uri": file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None,
        "is_signed": is_signed,
        "train_achieved": train_achieved,
        "cur_stamina": cur_stamina,
        "max_stamina": max_stamina,
        "stamina_ratio": stamina_ratio,
        "recover_text": recover_text,
        "activities": _build_activities(note_data),
        "avatar_uri": avatar_uri,
        "nickname": nickname,
        "uid": uid,
        "level": level,
        "level_x": level_x,
        "active_days": active_days,
    }

    html = render_template("note.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=W, height=H, device_scale_factor=2)
    return await convert_img(png_bytes)
