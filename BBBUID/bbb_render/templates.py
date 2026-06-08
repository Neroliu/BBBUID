"""Jinja2 模板加载与渲染。

约定：所有模板放在 `bbb_render/templates/`；模板中通过 `file_uri(path)`
全局函数把绝对路径转成 `file://` URL，让 Playwright 能直接读本地资源
（壁纸 / 立绘 / 图标 / 字体）。
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def file_uri(path: str | Path) -> str:
    """绝对路径 → file:// URL，处理空格与中文。"""
    p = Path(path).resolve()
    return "file://" + quote(str(p))


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)
_env.globals["file_uri"] = file_uri
_env.globals["static_dir"] = STATIC_DIR
_env.globals["templates_dir"] = TEMPLATES_DIR


def render_template(name: str, **ctx) -> str:
    template = _env.get_template(name)
    return template.render(**ctx)
