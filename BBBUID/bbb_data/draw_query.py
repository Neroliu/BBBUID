"""Query card rendering module for BBBUID."""
from __future__ import annotations

from typing import Dict, List

from PIL import Image

from gsuid_core.utils.image.convert import convert_img

from .draw_title import draw_title
from .draw_character import draw_character_card

# Character card dimensions
CHAR_CARD_W = 182
CHAR_CARD_H = 276
CHAR_CARD_GAP = 10  # Gap between cards
CHARS_PER_ROW = 5

# Colors
BG_DARK = (28, 28, 38)


async def draw_query_card(
    ev,
    uid: str,
    index_data: Dict,
    characters: List[Dict],
) -> bytes:
    """Draw query card with title and character grid."""
    # Extract data
    role = index_data.get("role", {})
    stats = index_data.get("stats", {})
    pref = index_data.get("preference", {})

    nickname = role.get("nickname", "未知舰长")
    level = role.get("level", "?")
    rating = pref.get("comprehensive_rating", "C")

    # Region name mapping
    region_map = {
        "android01": "安卓1区",
        "ios01": "iOS1区",
        "pc01": "PC1区",
    }
    region = role.get("region", "")
    region_name = region_map.get(region, region)

    # Get stats for info cards
    char_count = len(characters)
    sss_count = stats.get("sss_armor_number", 0)
    five_star_stigma = stats.get("five_star_stigmata_number", 0)
    five_star_weapon = stats.get("five_star_weapon_number", 0)

    # Draw title section
    title_img = await draw_title(
        ev, uid, nickname, level, rating, region_name,
        index_data, char_count, sss_count, five_star_stigma, five_star_weapon,
    )

    # Calculate canvas size
    num_chars = len(characters)
    if num_chars == 0:
        # No characters, just return title
        return await convert_img(title_img)

    num_rows = (num_chars + CHARS_PER_ROW - 1) // CHARS_PER_ROW

    # Title section height
    title_h = title_img.height
    title_gap = 20  # Gap between title and character grid

    # Calculate grid dimensions
    grid_w = CHARS_PER_ROW * CHAR_CARD_W + (CHARS_PER_ROW - 1) * CHAR_CARD_GAP
    grid_h = num_rows * CHAR_CARD_H + (num_rows - 1) * CHAR_CARD_GAP

    # Total canvas size
    canvas_w = max(title_img.width, grid_w + 40)  # 40px padding on sides for grid
    canvas_h = title_h + title_gap + grid_h + 20  # 20px bottom padding

    # Create canvas
    canvas = Image.new("RGBA", (canvas_w, canvas_h), BG_DARK)

    # Draw title centered
    title_x = (canvas_w - title_img.width) // 2
    canvas.alpha_composite(title_img, (title_x, 0))

    # Draw character cards
    grid_start_y = title_h + title_gap
    grid_start_x = (canvas_w - grid_w) // 2  # Center the grid

    for i, char_item in enumerate(characters):
        char = char_item.get("character", {})
        avatar = char.get("avatar", {})

        name = avatar.get("name", "?")
        star = avatar.get("star", 0)
        level = avatar.get("level", 1)

        # Get content_id for cache key
        content_id = str(avatar.get("id", ""))
        # Use API icon_path for download if cache miss
        icon_url = avatar.get("icon_path")

        # Draw character card (icon from project cache, download if missing)
        char_card = await draw_character_card(name, star, level, content_id, icon_url)

        # Calculate position
        row = i // CHARS_PER_ROW
        col = i % CHARS_PER_ROW
        card_x = grid_start_x + col * (CHAR_CARD_W + CHAR_CARD_GAP)
        card_y = grid_start_y + row * (CHAR_CARD_H + CHAR_CARD_GAP)

        canvas.alpha_composite(char_card, (card_x, card_y))

    return await convert_img(canvas)
