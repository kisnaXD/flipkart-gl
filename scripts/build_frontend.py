"""Build static frontend/ from Stitch templates for Vercel."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_TEMPLATES = ROOT / "app" / "templates" / "stitch"
SRC_STATIC = ROOT / "app" / "static"
OUT = ROOT / "frontend"

PAGES = {
    "command.html": "index.html",
    "map.html": "map.html",
    "scenarios.html": "scenarios.html",
    "hotspots.html": "hotspots.html",
    "analytics.html": "analytics.html",
    "learning.html": "learning.html",
}

CONFIG_SCRIPT = '<script src="/js/config.js"></script>'
NAV_SCRIPT = '<script src="/js/gridlock-nav.js"></script>'
SHELL_CSS = '<link rel="stylesheet" href="/css/gridlock-shell.css"/>'


def patch_html(html: str) -> str:
    html = html.replace("/static/js/", "/js/")
    html = html.replace("/static/css/", "/css/")
    if SHELL_CSS not in html:
        html = html.replace("</head>", f"{SHELL_CSS}\n</head>")
    if "gridlock-nav.js" not in html:
        html = html.replace(
            '<script src="/js/gridlock-app.js">',
            f"{CONFIG_SCRIPT}\n{NAV_SCRIPT}\n<script src=\"/js/gridlock-app.js\">",
        )
    elif CONFIG_SCRIPT not in html:
        html = html.replace(NAV_SCRIPT, f"{CONFIG_SCRIPT}\n{NAV_SCRIPT}")
    return html


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "css").mkdir()
    (OUT / "js").mkdir()

    for src_name, dst_name in PAGES.items():
        src = SRC_TEMPLATES / src_name
        if not src.exists():
            raise FileNotFoundError(src)
        content = patch_html(src.read_text(encoding="utf-8"))
        (OUT / dst_name).write_text(content, encoding="utf-8")

    for css in (SRC_STATIC / "css").glob("*.css"):
        shutil.copy2(css, OUT / "css" / css.name)
    for js in (SRC_STATIC / "js").glob("*.js"):
        shutil.copy2(js, OUT / "js" / js.name)

    (OUT / "js" / "config.js").write_text(
        '''/**
 * API base URL — EC2 backend via nip.io
 * On Vercel: empty string uses /api proxy (vercel.json → nip.io) to avoid mixed-content.
 */
window.GRIDLOCK_API =
  window.GRIDLOCK_API ??
  (location.hostname.endsWith(".vercel.app") ? "" : "http://65.2.35.241.nip.io");

function apiUrl(path) {
  const base = (window.GRIDLOCK_API || "").replace(/\\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

window.apiUrl = apiUrl;
''',
        encoding="utf-8",
    )

    (OUT / "vercel.json").write_text(
        (ROOT / "vercel.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    print(f"Built {OUT} ({len(PAGES)} pages)")


if __name__ == "__main__":
    main()
