# Sitemap: write sitemap.xml for every public page into the site build.

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

from python import storage
from python.core.sitemap import render_sitemap

BASE_URL: str = "https://gufime.com"
HUB_PATHS: tuple[str, ...] = ("/", "/works/", "/authors/")


def main(output_path: Path) -> None:
    """Write the sitemap for the hubs and every work and author page."""
    work_ids = storage.read_table("gold.mart_work", columns=["work_id"])["work_id"].cast(str).to_list()
    authors = storage.read_table("gold.mart_author", columns=["author"])["author"].to_list()
    work_paths = [f"/works/{quote(work_id, safe='')}" for work_id in sorted(work_ids)]
    author_paths = [f"/authors/{quote(author, safe='')}" for author in sorted(authors)]
    paths = [*HUB_PATHS, *work_paths, *author_paths]
    output_path.write_text(render_sitemap(BASE_URL, paths), encoding="utf-8", newline="\n")
    storage.emit("sitemap_urls", len(paths))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
