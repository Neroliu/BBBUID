"""WIKI 图鉴 HTML 渲染版本（角色/武器/圣痕/人偶/协同者 共用）。

入口函数：
  - draw_role_wiki_html(detail) -> bytes
  - draw_weapon_wiki_html(detail) -> bytes
  - draw_stigma_wiki_html(detail) -> bytes
  - draw_elf_wiki_html(detail) -> bytes
  - draw_partner_wiki_html(detail) -> bytes
"""
from __future__ import annotations

import base64
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List

from PIL import Image

from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img

from ..bbb_wiki.draw_utils import (
    S, CARD_W, PAD, BG_COLOR, _s,
    _download_image, _get_icon, _create_blurred_bg,
)
from ..bbb_wiki.resource_update import (
    get_local_equip_icons,
    get_local_stigma_equip_icons,
    get_local_material_icon,
    save_material_icon,
    get_local_icon,
)
from .runner import render_html_to_bytes
from .templates import file_uri, render_template

FOOTER_PATH = Path(__file__).parent.parent / "bbb_data" / "footer.png"


# ───────────────── helpers ─────────────────

def _img_to_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _extract_content_id(url: str) -> int | None:
    m = re.search(r"/content/(\d+)/detail", url)
    return int(m.group(1)) if m else None


async def _icon_uri(url: str, size: int | None = None) -> str | None:
    """Download an icon and return as data URI."""
    if not url:
        return None
    try:
        img = await _download_image(url)
        if not img:
            return None
        if size:
            img = img.resize((size, size), Image.LANCZOS)
        return _img_to_data_uri(img)
    except Exception:
        return None


async def _material_icon_uri(content_id: int | None) -> str | None:
    """Get material icon as data URI from local cache or download."""
    if not content_id:
        return None
    local = get_local_material_icon(content_id)
    if local:
        try:
            img = Image.open(local).convert("RGBA").resize((_s(48), _s(48)), Image.LANCZOS)
            return _img_to_data_uri(img)
        except Exception:
            pass
    from ..bbb_wiki.wiki_api import get_content_detail
    detail = await get_content_detail(content_id)
    if detail:
        icon_url = detail.get("icon", "")
        if icon_url:
            saved = await save_material_icon(content_id, icon_url)
            if saved:
                try:
                    img = Image.open(saved).convert("RGBA").resize((_s(48), _s(48)), Image.LANCZOS)
                    return _img_to_data_uri(img)
                except Exception:
                    pass
    return None


async def _blurred_bg_uri(avatar: Image.Image) -> str:
    """Resize avatar for CSS-blurred background, return as JPEG data URI.

    CSS handles the actual blur + darkening via filter:blur+brightness and
    an overlay, so we only need a reasonably-sized source image.
    """
    bg = avatar.resize((CARD_W, max(CARD_W, int(CARD_W * avatar.height / avatar.width))), Image.LANCZOS)
    buf = BytesIO()
    bg.save(buf, format="JPEG", quality=75)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _build_sub_fields(sub_fields: list[dict], skip_names: set[str] | None = None) -> list[dict]:
    skip = skip_names or set()
    result = []
    for sf in sub_fields:
        name = sf.get("name", "")
        value = sf.get("value", "")
        if not name or not value or name in skip:
            continue
        result.append({"name": name, "value": value})
    return result


# ───────────────── 角色图鉴 ─────────────────

async def _build_role_sections(evaluation: dict, detail: dict) -> list[dict]:
    sections = []

    # Score table
    hexagon = evaluation.get("hexagon", [])
    if hexagon:
        final_level_url = evaluation.get("finalLevel", "")
        final_level_uri = await _icon_uri(final_level_url)
        rows = []
        for h in hexagon:
            val = min(h.get("value", 0), 100)
            rows.append({
                "key": h.get("key", ""),
                "level": h.get("level", ""),
                "value": val,
            })
        sections.append({
            "kind": "score_table",
            "title": "性能评分",
            "rows": rows,
            "final_level_uri": final_level_uri,
        })

    # Equipment
    equipments = evaluation.get("equipments", [])
    if equipments:
        content_id = detail.get("id")
        cached_icons = get_local_equip_icons("角色", content_id) if content_id else {}
        groups = []
        global_idx = 0
        for eq_group in equipments:
            equips = []
            for eq in eq_group.get("equips", []):
                icon_uri = None
                # Try local cache
                if global_idx in cached_icons:
                    try:
                        icon = Image.open(cached_icons[global_idx]).convert("RGBA").resize((_s(64), _s(64)), Image.LANCZOS)
                        icon_uri = _img_to_data_uri(icon)
                    except Exception:
                        pass
                if not icon_uri:
                    icon_uri = await _icon_uri(eq.get("icon", ""), _s(64))
                equips.append({"title": eq.get("title", ""), "icon_uri": icon_uri})
                global_idx += 1
            groups.append({
                "label": eq_group.get("label", ""),
                "equips": equips,
                "reason": eq_group.get("reason", ""),
            })
        sections.append({
            "kind": "equip_groups",
            "title": "装备推荐",
            "groups": groups,
        })

    # Advance table
    advance_general = evaluation.get("advanceGeneral", [])
    advance_data = evaluation.get("advanceData", [])
    if advance_general:
        headers = ["星级", "进阶效果", "生命", "攻击", "防御", "能量", "会心", "碎片"]
        rows = []
        for idx in range(len(advance_general)):
            gen = advance_general[idx]
            adv = advance_data[idx] if idx < len(advance_data) else {}
            rank_uri = None
            icon_url = gen.get("icon", "")
            if icon_url:
                rank_uri = await _icon_uri(icon_url, _s(28))
            rows.append({
                "rank_uri": rank_uri,
                "desc": gen.get("desc", ""),
                "stats": [str(adv.get(k, "-")) for k in ["life", "attack", "defense", "energy", "understanding"]],
                "cost": str(gen.get("cost", "-")),
            })
        sections.append({
            "kind": "advance_table",
            "title": "进阶总览",
            "headers": headers,
            "rows": rows,
        })

    return sections


async def draw_role_wiki_html(detail: dict) -> bytes:
    from ..bbb_wiki.wiki_api import parse_evaluation_from_detail
    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    title = detail.get("title", "未知角色")
    basic_info = detail.get("basic_info", {})
    sub_fields = _build_sub_fields(evaluation.get("subFields", []), {"往世乐土"})

    info_parts = []
    for key in ["角色属性", "武器类型", "角色定位"]:
        if key in basic_info:
            info_parts.append(basic_info[key])
    basic_info_text = " | ".join(info_parts)

    avatar_url = evaluation.get("avatar", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    blur_bg_uri = await _blurred_bg_uri(avatar) if avatar else None
    avatar_uri = _img_to_data_uri(avatar.resize((240, 240), Image.LANCZOS)) if avatar else None

    final_level_url = evaluation.get("finalLevel", "")
    final_level_uri = await _icon_uri(final_level_url) if final_level_url else None

    sections = await _build_role_sections(evaluation, detail)
    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "blur_bg_uri": blur_bg_uri,
        "avatar_uri": avatar_uri,
        "title": title,
        "final_level_uri": final_level_uri,
        "basic_info_text": basic_info_text,
        "sub_fields": sub_fields,
        "sections": sections,
        "footer_uri": footer_uri,
    }
    html = render_template("wiki.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)


# ───────────────── 武器图鉴 ─────────────────

async def _build_weapon_sections(weapon_data: dict) -> list[dict]:
    sections = []
    info = weapon_data.get("info", {})

    # Skills
    skills = weapon_data.get("skills", [])
    if skills:
        blocks = []
        for s in skills:
            blocks.append({"title": s.get("key", ""), "desc": s.get("value", "")})
        sections.append({"kind": "text_blocks", "title": "武器技能", "blocks": blocks})

    # Gain methods
    gain_methods = weapon_data.get("gainMethods", [])
    if gain_methods:
        blocks = []
        for gm in gain_methods:
            key = gm.get("key", "")
            value = gm.get("value", "")
            if key == "装备锻造" and weapon_data.get("forgingMaterials"):
                forging = weapon_data.get("forging", {})
                mat_lines = []
                for mat in forging.get("material", []):
                    mat_lines.append(f"{mat.get('name', '')} x{mat.get('num', 0)}")
                for mat in forging.get("otherMaterial", []):
                    mat_lines.append(f"{mat.get('name', '')} x{mat.get('num', 0)}")
                value = f"{value}\n超限素材: {' '.join(mat_lines)}"
            blocks.append({"title": key, "desc": value} if key else {"desc": value})
        sections.append({"kind": "text_blocks", "title": "获取方式", "blocks": blocks})

    # Materials (evolution)
    materials = weapon_data.get("materials", [])
    if materials:
        levels = []
        for level_data in materials:
            mats = []
            for m in level_data.get("material", []):
                cid = _extract_content_id(m.get("url", ""))
                icon_uri = await _material_icon_uri(cid)
                mats.append({
                    "name": m.get("name", ""),
                    "count": m.get("count", 0),
                    "icon_uri": icon_uri,
                })
            levels.append({
                "level": level_data.get("level", ""),
                "materials": mats,
            })
        sections.append({"kind": "materials", "title": "进化材料", "levels": levels})

    # Sync materials
    sync_mats = weapon_data.get("syncMaterials", [])
    if sync_mats:
        levels = []
        cur_mats = []
        for sm in sync_mats:
            cid = sm.get("content_id", 0)
            icon_uri = await _material_icon_uri(cid)
            cur_mats.append({
                "name": sm.get("name", ""),
                "count": 0,
                "icon_uri": icon_uri,
            })
        if cur_mats:
            levels.append({"level": "", "materials": cur_mats})
            sections.append({"kind": "materials", "title": "同调素材", "levels": levels})

    # Roles
    roles = weapon_data.get("roles", [])
    if roles:
        role_list = []
        for r in roles:
            icon_uri = await _icon_uri(r.get("icon", ""), _s(64))
            role_list.append({
                "name": r.get("key", ""),
                "desc": r.get("value", ""),
                "star_value": r.get("starValue", 0),
                "icon_uri": icon_uri,
            })
        sections.append({"kind": "roles", "title": "适用角色", "roles": role_list})

    return sections


async def draw_weapon_wiki_html(detail: dict) -> bytes:
    from ..bbb_wiki.wiki_api import parse_weapon_data_from_detail
    weapon_data = detail.get("weapon_data") or parse_weapon_data_from_detail(detail)
    title = detail.get("title", "未知武器")
    info = weapon_data.get("info", {})

    weapon_icon_url = info.get("icon", "") or detail.get("icon", "")
    icon = await _download_image(weapon_icon_url) if weapon_icon_url else None
    blur_bg_uri = await _blurred_bg_uri(icon) if icon else None
    icon_uri = _img_to_data_uri(icon.resize((200, 200), Image.LANCZOS)) if icon else None

    sub_fields = _build_sub_fields(info.get("subFields", []))
    star_value = info.get("starValue", 0)
    attrs = info.get("attr", [])
    attr_parts = [f"{a.get('key', '')} {a.get('value', '')}" for a in attrs if a.get("key") and a.get("value")]
    basic_info_text = " | ".join(attr_parts)

    sections = await _build_weapon_sections(weapon_data)
    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "blur_bg_uri": blur_bg_uri,
        "avatar_uri": icon_uri,
        "title": title,
        "final_level_uri": None,
        "star_value": star_value,
        "basic_info_text": basic_info_text,
        "sub_fields": sub_fields,
        "sections": sections,
        "footer_uri": footer_uri,
    }
    html = render_template("wiki.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)


# ───────────────── 圣痕图鉴 ─────────────────

async def _build_stigma_sections(stigma_data: dict, detail: dict) -> list[dict]:
    sections = []
    info = stigma_data.get("info", {})

    # Stigma skill
    stigma_skill = stigma_data.get("stigmaSkill", {})
    if stigma_skill.get("value"):
        sections.append({
            "kind": "text_blocks",
            "title": "圣痕技能",
            "blocks": [{"title": stigma_skill.get("key", ""), "desc": stigma_skill.get("value", "")}],
        })

    # Set skills
    set_skills = stigma_data.get("setSkills", [])
    if set_skills:
        blocks = []
        for s in set_skills:
            blocks.append({"title": s.get("key", ""), "desc": s.get("value", "")})
        sections.append({"kind": "text_blocks", "title": "套装技能", "blocks": blocks})

    # Roles
    roles = stigma_data.get("roles", [])
    if roles:
        role_list = []
        for r in roles:
            icon_uri = await _icon_uri(r.get("icon", ""), _s(64))
            role_list.append({
                "name": r.get("key", ""),
                "desc": r.get("value", ""),
                "icon_uri": icon_uri,
            })
        sections.append({"kind": "roles", "title": "适用角色", "roles": role_list})

    # Equipment recommendations
    equipments = stigma_data.get("equipments", [])
    if equipments:
        content_id = detail.get("id")
        cached_icons = get_local_stigma_equip_icons(content_id) if content_id else {}
        groups = []
        global_idx = 0
        for eq_group in equipments:
            equips = []
            for eq in eq_group.get("equips", []):
                icon_uri = None
                if global_idx in cached_icons:
                    try:
                        icon = Image.open(cached_icons[global_idx]).convert("RGBA").resize((_s(64), _s(64)), Image.LANCZOS)
                        icon_uri = _img_to_data_uri(icon)
                    except Exception:
                        pass
                if not icon_uri:
                    icon_uri = await _icon_uri(eq.get("icon", ""), _s(64))
                equips.append({"title": eq.get("title", ""), "icon_uri": icon_uri})
                global_idx += 1
            groups.append({
                "label": eq_group.get("label", ""),
                "evaluation": eq_group.get("evaluation", 0),
                "equips": equips,
                "reason": eq_group.get("reason", ""),
            })
        sections.append({
            "kind": "equip_groups",
            "title": "配装推荐",
            "groups": groups,
        })

    # Gain methods + forging
    gain_methods = stigma_data.get("gainMethods", [])
    forging_materials = stigma_data.get("forgingMaterials", [])
    if gain_methods:
        blocks = []
        for gm in gain_methods:
            key = gm.get("key", "")
            value = gm.get("value", "")
            if key == "装备锻造" and forging_materials:
                mat_lines = [f"{m.get('name', '')} x{m.get('count', 0)}" for m in forging_materials]
                value = f"{value}\n素材: {' '.join(mat_lines)}"
            blocks.append({"title": key, "desc": value} if key else {"desc": value})
        sections.append({"kind": "text_blocks", "title": "获取途径", "blocks": blocks})

    # Evolution materials
    materials = stigma_data.get("materials", [])
    if materials:
        levels = []
        for level_data in materials:
            mats = []
            for m in level_data.get("material", []):
                cid = _extract_content_id(m.get("url", ""))
                icon_uri = await _material_icon_uri(cid)
                mats.append({
                    "name": m.get("name", ""),
                    "count": m.get("count", 0),
                    "icon_uri": icon_uri,
                })
            levels.append({
                "level": level_data.get("level", ""),
                "materials": mats,
            })
        sections.append({"kind": "materials", "title": "进化材料", "levels": levels})

    return sections


async def draw_stigma_wiki_html(detail: dict) -> bytes:
    from ..bbb_wiki.wiki_api import parse_stigma_data_from_detail
    stigma_data = detail.get("stigma_data") or parse_stigma_data_from_detail(detail)
    title = detail.get("title", "未知圣痕")
    info = stigma_data.get("info", {})

    avatar_url = info.get("avatar", "") or detail.get("icon", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    blur_bg_uri = await _blurred_bg_uri(avatar) if avatar else None
    icon_uri = _img_to_data_uri(avatar.resize((240, 240), Image.LANCZOS)) if avatar else None

    # Sub fields (skip 圣痕技能)
    sub_fields = _build_sub_fields(info.get("subFields", []), {"圣痕技能"})

    # Relatives
    relatives = info.get("relatives", [])
    if relatives and not (len(relatives) == 1 and relatives[0].get("name") == "无"):
        for rel in relatives:
            rel_name = rel.get("name", "")
            sub_fields.append({"name": "关联圣痕", "value": rel_name})

    sections = await _build_stigma_sections(stigma_data, detail)
    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "blur_bg_uri": blur_bg_uri,
        "avatar_uri": icon_uri,
        "title": title,
        "final_level_uri": None,
        "basic_info_text": "",
        "sub_fields": sub_fields,
        "sections": sections,
        "footer_uri": footer_uri,
    }
    html = render_template("wiki.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)


# ───────────────── 人偶图鉴 ─────────────────

async def draw_elf_wiki_html(detail: dict) -> bytes:
    from ..bbb_wiki.wiki_api import parse_evaluation_from_detail
    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    title = detail.get("title", "未知人偶")
    basic_info = detail.get("basic_info", {})

    info_parts = []
    for key in ["CV", "特征"]:
        if key in basic_info:
            info_parts.append(f"{key}: {basic_info[key]}")
    basic_info_text = " | ".join(info_parts)

    sub_fields = _build_sub_fields(evaluation.get("subFields", []))

    avatar_url = evaluation.get("avatar", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    blur_bg_uri = await _blurred_bg_uri(avatar) if avatar else None
    avatar_uri = _img_to_data_uri(avatar.resize((240, 240), Image.LANCZOS)) if avatar else None

    final_level_url = evaluation.get("finalLevel", "")
    final_level_uri = await _icon_uri(final_level_url) if final_level_url else None

    sections: list[dict] = []

    # Score table
    hexagon = evaluation.get("hexagon", [])
    if hexagon:
        rows = [{"key": h.get("key", ""), "level": h.get("level", ""), "value": min(h.get("value", 0), 100)} for h in hexagon]
        sections.append({
            "kind": "score_table",
            "title": "★ 性能评分",
            "rows": rows,
            "final_level_uri": final_level_uri,
        })

    # Pairings
    equipments = evaluation.get("equipments", [])
    if equipments:
        groups = []
        for eq_group in equipments:
            equips = []
            for eq in eq_group.get("equips", []):
                icon_uri = await _icon_uri(eq.get("icon", ""), _s(64))
                equips.append({"title": eq.get("title", ""), "icon_uri": icon_uri})
            groups.append({
                "label": eq_group.get("label", ""),
                "equips": equips,
                "reason": eq_group.get("reason", ""),
            })
        sections.append({"kind": "equip_groups", "title": "配合搭配", "groups": groups})

    # Advance table
    advance_general = evaluation.get("advanceGeneral", [])
    if advance_general:
        rows = []
        for ag in advance_general:
            rank_uri = None
            icon_url = ag.get("icon", "")
            if icon_url:
                rank_uri = await _icon_uri(icon_url, _s(28))
            rows.append({
                "rank_uri": rank_uri,
                "stars": "★" * ag.get("starValue", 0) if ag.get("starValue") else None,
                "desc": ag.get("desc", ""),
                "stats": [],
                "cost": str(ag.get("cost", "-")),
            })
        sections.append({
            "kind": "advance_table",
            "title": "进阶总览",
            "headers": ["星级", "进阶效果", "碎片"],
            "rows": rows,
        })

    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "blur_bg_uri": blur_bg_uri,
        "avatar_uri": avatar_uri,
        "title": title,
        "final_level_uri": None,
        "basic_info_text": basic_info_text,
        "sub_fields": sub_fields,
        "sections": sections,
        "footer_uri": footer_uri,
    }
    html = render_template("wiki.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)


# ───────────────── 协同者图鉴 ─────────────────

async def draw_partner_wiki_html(detail: dict) -> bytes:
    from ..bbb_wiki.wiki_api import parse_evaluation_from_detail
    evaluation = detail.get("evaluation") or parse_evaluation_from_detail(detail)
    title = detail.get("title", "未知协同者")

    # Extract main fields from contents
    main_fields = {}
    for section in detail.get("contents", []):
        text = section.get("text", "")
        import json as _json
        from urllib.parse import unquote
        match = re.search(r'data-data="([^"]*)"', text)
        if not match:
            continue
        try:
            items = _json.loads(unquote(match.group(1)))
        except (_json.JSONDecodeError, ValueError):
            continue
        for item in items:
            if item.get("partKey") == "basicIntroduction":
                for mf in item.get("data", {}).get("mainFields", []):
                    if mf.get("nameL") and mf.get("valueL"):
                        main_fields[mf["nameL"]] = mf["valueL"]
                    if mf.get("nameR") and mf.get("valueR"):
                        main_fields[mf["nameR"]] = mf["valueR"]
                break

    info_parts = []
    for key in ["所属", "CV", "特征"]:
        if key in main_fields:
            info_parts.append(f"{key}: {main_fields[key]}")
    basic_info_text = " | ".join(info_parts)

    sub_fields = _build_sub_fields(evaluation.get("subFields", []))

    avatar_url = evaluation.get("avatar", "")
    avatar = await _download_image(avatar_url) if avatar_url else None
    blur_bg_uri = await _blurred_bg_uri(avatar) if avatar else None
    avatar_uri = _img_to_data_uri(avatar.resize((240, 240), Image.LANCZOS)) if avatar else None

    final_level_url = evaluation.get("finalLevel", "")
    final_level_uri = await _icon_uri(final_level_url) if final_level_url else None

    sections: list[dict] = []

    # Score table
    hexagon = evaluation.get("hexagon", [])
    if hexagon:
        rows = [{"key": h.get("key", ""), "level": h.get("level", ""), "value": min(h.get("value", 0), 100)} for h in hexagon]
        sections.append({
            "kind": "score_table",
            "title": "性能评分",
            "rows": rows,
            "final_level_uri": final_level_uri,
        })

    # Pairings
    equipments = evaluation.get("equipments", [])
    if equipments:
        groups = []
        for eq_group in equipments:
            equips = []
            for eq in eq_group.get("equips", []):
                icon_uri = await _icon_uri(eq.get("icon", ""), _s(64))
                equips.append({"title": eq.get("title", ""), "icon_uri": icon_uri})
            groups.append({
                "label": eq_group.get("label", ""),
                "equips": equips,
                "reason": eq_group.get("reason", ""),
            })
        sections.append({"kind": "equip_groups", "title": "配合搭配", "groups": groups})

    # Advance table
    advance_general = evaluation.get("advanceGeneral", [])
    if advance_general:
        rows = []
        for ag in advance_general:
            rank_uri = None
            icon_url = ag.get("icon", "")
            if icon_url:
                rank_uri = await _icon_uri(icon_url, _s(28))
            rows.append({
                "rank_uri": rank_uri,
                "desc": ag.get("desc", ""),
                "stats": [],
                "cost": str(ag.get("cost", "-")),
            })
        sections.append({
            "kind": "advance_table",
            "title": "进阶总览",
            "headers": ["星级", "进阶效果", "碎片"],
            "rows": rows,
        })

    footer_uri = file_uri(FOOTER_PATH) if FOOTER_PATH.exists() else None

    ctx = {
        "blur_bg_uri": blur_bg_uri,
        "avatar_uri": avatar_uri,
        "title": title,
        "final_level_uri": None,
        "basic_info_text": basic_info_text,
        "sub_fields": sub_fields,
        "sections": sections,
        "footer_uri": footer_uri,
    }
    html = render_template("wiki.html", **ctx)
    png_bytes = await render_html_to_bytes(html, width=CARD_W, height=600, device_scale_factor=2, full_page=True)
    return await convert_img(png_bytes)