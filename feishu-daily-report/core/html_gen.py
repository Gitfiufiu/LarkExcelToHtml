from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger


class HtmlGenError(Exception):
    pass


def generate_html(headers: List[str], rows: List[Dict[str, str]], output_path: Path) -> Path:
    try:
        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template("report.html.j2")
        html = template.render(headers=headers, rows=rows, now=datetime.now())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML 已生成: {output_path}")
        return output_path
    except Exception as e:
        raise HtmlGenError(f"生成 HTML 失败: {e}") from e
