# Sitemap: render page paths as sitemap XML.

from __future__ import annotations


def render_sitemap(base_url: str, paths: list[str]) -> str:
    """Sitemap document listing each path under the base url."""
    entries = "".join(f"  <url><loc>{base_url}{path}</loc></url>\n" for path in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}"
        "</urlset>\n"
    )
