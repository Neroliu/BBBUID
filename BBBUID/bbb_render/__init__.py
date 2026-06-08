"""HTML rendering pipeline (playwright + jinja2).

启用方式：在 webconsole 中开启 `UseHtmlRender` 配置；首次使用需手动执行
`playwright install chromium`。
"""
from .runner import render_html_to_bytes
from .templates import render_template

__all__ = ["render_html_to_bytes", "render_template"]
