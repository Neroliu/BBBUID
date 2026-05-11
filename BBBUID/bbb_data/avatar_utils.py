"""Avatar rendering utilities for BBBUID cards."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.image_tools import get_event_avatar

from ..utils.RESOURCE_PATH import AVATAR_CACHE_PATH

CST = timezone(timedelta(hours=8))

# Avatar decoration resources
AVATAR_RES_DIR = Path(__file__).parent / "avatar"

# Colors
ACCENT_BLUE = (80, 160, 255)


def _draw_circle_avatar(avatar: Image.Image, size: int) -> Image.Image:
    avatar = avatar.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar, (0, 0), mask)
    return out


def _draw_ring_avatar(avatar: Image.Image, size: int) -> Image.Image:
    ring_w = 4
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    center = size // 2
    r = center - ring_w
    inner_avatar = _draw_circle_avatar(avatar, r * 2)
    canvas.paste(inner_avatar, (ring_w, ring_w), inner_avatar)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), outline=ACCENT_BLUE, width=ring_w)
    return canvas


async def get_cached_avatar(ev: Event, user_id: str) -> Image.Image:
    """Get avatar with 24h cache. Refresh if cache is stale."""
    AVATAR_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    cache_file = AVATAR_CACHE_PATH / f"{user_id}.png"
    meta_file = AVATAR_CACHE_PATH / "avatar_meta.json"

    # Load metadata
    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    now = datetime.now(tz=CST)
    cached_time = meta.get(user_id)
    should_refresh = True

    if cache_file.exists() and cached_time:
        try:
            last_update = datetime.fromisoformat(cached_time)
            if (now - last_update) < timedelta(hours=24):
                should_refresh = False
        except Exception:
            pass

    # Return cached avatar if fresh
    if not should_refresh and cache_file.exists():
        try:
            return Image.open(cache_file).convert("RGBA")
        except Exception:
            pass

    # Fetch fresh avatar from event
    avatar = await get_event_avatar(ev)

    # Save to cache
    try:
        avatar.save(cache_file, "PNG")
        meta[user_id] = now.isoformat()
        meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[崩坏3] [便笺渲染] 保存头像缓存失败: {e}")

    return avatar


def draw_decorated_avatar(avatar: Image.Image, size: int) -> Image.Image:
    """Draw avatar with mask and foreground decoration."""
    mask_path = AVATAR_RES_DIR / "avatar_mask.png"
    fg_path = AVATAR_RES_DIR / "avatar_fg.png"

    # Load resources
    mask_img = None
    fg_img = None
    if mask_path.exists():
        mask_img = Image.open(mask_path).convert("RGBA")
    if fg_path.exists():
        fg_img = Image.open(fg_path).convert("RGBA")

    # If no decoration resources, fallback to ring avatar
    if not mask_img or not fg_img:
        return _draw_ring_avatar(avatar, size)

    # Create canvas with decoration size
    mw, mh = mask_img.size
    canvas = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))

    # Resize avatar to fit mask (ellipse area, slightly smaller than mask)
    avatar_size = min(mw, mh) - 10
    avatar_resized = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
    avatar_x = (mw - avatar_size) // 2
    avatar_y = (mh - avatar_size) // 2

    # Draw avatar
    canvas.alpha_composite(avatar_resized, (avatar_x, avatar_y))

    # Apply mask (use mask's alpha channel)
    mask_alpha = mask_img.getchannel("A")
    result = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
    result.paste(canvas, (0, 0), mask_alpha)

    # Draw foreground decoration on top
    result.alpha_composite(fg_img, (0, 0))

    # Scale to requested size
    if size != mw:
        result = result.resize((size, int(size * mh / mw)), Image.Resampling.LANCZOS)

    return result
