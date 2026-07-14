# Offline test harness for notebooks/nb_strip.py: pulls a ~20-book sample of the
# roster (spread across PG release dates, plus the three old-format stragglers),
# strips them, and writes preview markdown to data/corpus_preview/ for eyeballing.
# Usage: uv run python scripts/strip_sample.py

from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

import duckdb
import requests

REPO: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "notebooks"))

import nb_strip  # noqa: E402  (path shim above; run cell is __main__-guarded)

WAREHOUSE: Path = REPO / "dbt" / "warehouse.duckdb"
TEXTS_DIR: Path = REPO / "data" / "texts"
PREVIEW_DIR: Path = REPO / "data" / "corpus_preview"

MIRROR: str = "https://gutenberg.pglaf.org"
USER_AGENT: str = "gutenberg-fingerprint-pipeline/0.1 (contact: samvanwilligen@gmail.com)"
SLEEP_S: float = 2.0

SAMPLE_SIZE: int = 17
FORCED_IDS: tuple[int, ...] = (1062, 1152, 1311)  # old dirs-layout files, oldest boilerplate

Row = tuple[int, str, str, str]  # gutenberg_id, title, authors, issued


def pick_sample(con: duckdb.DuckDBPyConnection) -> list[Row]:
    """Evenly spaced picks over the issued-date range, plus the forced ids."""
    rows: list[Row] = con.execute(
        "SELECT gutenberg_id, title, authors, issued FROM raw.raw_works ORDER BY issued, gutenberg_id"
    ).fetchall()
    idxs = {round(i * (len(rows) - 1) / (SAMPLE_SIZE - 1)) for i in range(SAMPLE_SIZE)}
    sample = {rows[i][0]: rows[i] for i in idxs}
    by_id = {row[0]: row for row in rows}
    for gid in FORCED_IDS:
        if gid in by_id:
            sample[gid] = by_id[gid]
    return sorted(sample.values(), key=lambda row: (row[3], row[0]))


def text_urls(gid: int) -> list[str]:
    # Mirror of nb_text_ingest's fallback chain
    dirs = "/".join(str(gid)[:-1]) or "0"
    return [
        f"{MIRROR}/cache/epub/{gid}/pg{gid}.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}-0.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}-8.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}.txt",
    ]


def fetch(gid: int, session: requests.Session) -> bytes:
    for i, url in enumerate(text_urls(gid)):
        if i:
            time.sleep(SLEEP_S)
        resp = session.get(url, timeout=60)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.content
    raise FileNotFoundError(f"no text file for {gid}")


def ensure_texts(gids: list[int]) -> None:
    TEXTS_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    fetched = 0
    for gid in gids:
        path = TEXTS_DIR / f"{gid}.txt"
        if path.exists():
            continue
        if fetched:
            time.sleep(SLEEP_S)
        print(f"fetching {gid}...")
        path.write_bytes(fetch(gid, session))
        fetched += 1


def quote_stats(md: str) -> tuple[int, int]:
    """(double quotes in either form, likely single-quote dialogue openings)."""
    doubles = md.count('"') + md.count("“")
    singles = len(re.findall(r"(?:^|[\s(—-])['‘]\w", md))
    return doubles, singles


def main() -> None:
    if not WAREHOUSE.exists():
        sys.exit("dbt/warehouse.duckdb missing: run scripts/load_local_raw_tables.py first")
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        rows = pick_sample(con)
    ensure_texts([row[0] for row in rows])
    for _ in range(3):  # OneDrive briefly locks dirs mid-sync
        shutil.rmtree(PREVIEW_DIR, ignore_errors=True)
        if not PREVIEW_DIR.exists():
            break
        time.sleep(1.0)

    print(f"\n{'id':>7}  {'issued':<10}  {'words':>8}  {'##':>3}  quotes")
    for gid, title, authors, issued in rows:
        raw = (TEXTS_DIR / f"{gid}.txt").read_bytes()
        author = nb_strip.display_author(authors or "")
        try:
            md = nb_strip.to_markdown(raw, title or "", author)
        except ValueError as exc:
            print(f"{gid:>7}  {issued:<10}  FAILED: {exc}")
            continue
        dest = PREVIEW_DIR / nb_strip.author_folder(author) / f"{gid}-{nb_strip.title_slug(title or '')}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8", newline="\n")
        heads = md.count("\n## ")
        doubles, singles = quote_stats(md)
        flag = "  <- single-quote dialogue?" if doubles < 20 and singles > 40 else ""
        rel = dest.relative_to(PREVIEW_DIR)
        print(f"{gid:>7}  {issued:<10}  {len(md.split()):>8,}  {heads:>3}  \"x{doubles:<6,} 'x{singles:<5,}{flag}  {rel}")
    print(f"\npreview -> {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
