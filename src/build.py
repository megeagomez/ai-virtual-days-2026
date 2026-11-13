#!/usr/bin/env python3
"""Empaqueta src/index.html en un único HTML autocontenido (CSS, JS, overlays e imágenes en línea).

Uso:  python src/build.py            → ../devops-conversacional-aivd.html
"""
import base64
import mimetypes
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent / "devops-conversacional-aivd.html"


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def inline_css(css: str, base: Path) -> str:
    return re.sub(r"url\((?!#|data:)([^)]+)\)",
                  lambda m: f"url({data_uri((base / m.group(1).strip('\"\'')).resolve())})", css)


html = (SRC / "index.html").read_text(encoding="utf-8")
html = re.sub(r'<link rel="stylesheet" href="([^"]+)">',
              lambda m: "<style>\n" + inline_css((SRC / m.group(1)).read_text(encoding="utf-8"),
                                                 (SRC / m.group(1)).parent) + "\n</style>", html)
html = re.sub(r"<!-- include: ([^ ]+) -->", lambda m: (SRC / m.group(1)).read_text(encoding="utf-8"), html)
html = re.sub(r'<script src="([^"]+)"></script>',
              lambda m: "<script>\n" + (SRC / m.group(1)).read_text(encoding="utf-8") + "\n</script>", html)
html = re.sub(r'src="(assets/[^"]+)"', lambda m: f'src="{data_uri(SRC / m.group(1))}"', html)

OUT.write_text(html, encoding="utf-8")
print(f"{OUT.name}: {OUT.stat().st_size / 1e6:.2f} MB · {html.count('<section class=\"slide')} diapositivas")
