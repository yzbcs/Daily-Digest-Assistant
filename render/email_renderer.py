"""
email_renderer.py

使用 Jinja2 将论文和文章数据渲染成 HTML 邮件正文。
"""

from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import os


WEEKDAY_MAP = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def render_email(
    papers: list[dict],
    keywords: list[str],
    template_dir: str = None,
) -> str:
    """
    渲染 HTML 邮件正文。

    Args:
        papers: 筛选后的论文列表（含 summary_zh / detail_zh）
        keywords: 关键词列表（展示在 header）
        template_dir: 模板目录路径，默认为本文件同级的 ../templates

    Returns:
        渲染后的 HTML 字符串
    """
    if template_dir is None:
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")

    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("email.html")

    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    weekday_str = WEEKDAY_MAP[now.weekday()]

    html = template.render(
        date=date_str,
        weekday=weekday_str,
        papers=papers,
        keywords=keywords,
    )
    return html
