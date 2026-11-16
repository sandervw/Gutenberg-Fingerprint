# Text ingest: download new/changed/failed works from PG's mirror into bronze.

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import polars
import requests

from python import storage
from python.core.filter import is_copyrighted
from python.core.ledger import (
    IngestCounts,
    count_changes,
    ingest_audit_row,
    pick_downloads,
    update_watermark,
)

TEXTS_ROOT: Path = storage.file_path("bronze/texts")
MIRROR: str = "https://gutenberg.pglaf.org"

POLITENESS_SECONDS: float = 2.0  # PG's stated politeness gap
MAX_CONSECUTIVE_FAILURES: int = 5  # a streak means blocked or mirror down
MAX_DOWNLOADS_PER_RUN: int = 200  # caps a run to a predictable length

# %% Download - raw bytes, one file per work, rate-limited


def text_urls(gutenberg_id: int) -> list[str]:
    """Mirror URLs to try for one work, best first."""
    digit_path = "/".join(str(gutenberg_id)[:-1]) or "0"
    return [
        f"{MIRROR}/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}-8.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}.txt",
    ]


def fetch_text(gutenberg_id: int, session: requests.Session) -> bytes:
    """Fetch the first mirror URL that exists for one work."""
    for index, url in enumerate(text_urls(gutenberg_id)):
        if index:
            time.sleep(POLITENESS_SECONDS)
        response = session.get(url, timeout=60)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        return response.content
    raise FileNotFoundError(f"no text file for {gutenberg_id}")


def download_texts(todo: polars.DataFrame) -> polars.DataFrame:
    """Download each work; return its id, hash, text hash, and status."""
    TEXTS_ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = storage.USER_AGENT

    rows: list[tuple[int, str, str | None, str]] = []
    consecutive_failures = 0
    for index, row in enumerate(todo.iter_rows(named=True)):
        if index:
            time.sleep(POLITENESS_SECONDS)
        if index % 50 == 0:
            print(f"{index:,}/{todo.height:,}...")
        gutenberg_id = row["gutenberg_id"]
        try:
            raw_bytes = fetch_text(gutenberg_id, session)
            if is_copyrighted(raw_bytes):
                (TEXTS_ROOT / f"{gutenberg_id}.txt").unlink(missing_ok=True)
                rows.append((gutenberg_id, row["catalog_row_hash"], None, "copyrighted"))
                consecutive_failures = 0
                continue
            (TEXTS_ROOT / f"{gutenberg_id}.txt").write_bytes(raw_bytes)
            text_hash = hashlib.sha256(raw_bytes).hexdigest()
            rows.append((gutenberg_id, row["catalog_row_hash"], text_hash, "ingested"))
            consecutive_failures = 0
        # OSError covers the all-mirrors-404 FileNotFoundError
        except (requests.RequestException, OSError) as error:
            print(f"{gutenberg_id}: {error}")
            rows.append((gutenberg_id, row["catalog_row_hash"], None, "failed"))
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"{consecutive_failures} failures in a row, stopping early")
                break
    return polars.DataFrame(
        rows,
        schema={
            "gutenberg_id": polars.Int64,
            "catalog_row_hash": polars.String,
            "text_hash": polars.String,
            "status": polars.String,
        },
        orient="row",
    )


# %% Prune - bronze mirrors roster; drop files for departed works


def prune_orphans(roster: polars.DataFrame, texts_root: Path) -> int:
    """Delete bronze texts whose work left the roster."""
    if not texts_root.exists():
        return 0
    keep = set(roster["gutenberg_id"].to_list())
    removed = 0
    for path in texts_root.glob("*.txt"):
        if path.stem.isdigit() and int(path.stem) not in keep:
            path.unlink()
            removed += 1
    return removed


# %% Run


def main() -> None:
    """Download the backlog, then update the watermark and audit."""
    run_time: datetime = datetime.now(timezone.utc)
    roster: polars.DataFrame = storage.read_table("raw.raw_works")
    watermark: polars.DataFrame = storage.read_table("bronze.watermark")
    pruned: int = prune_orphans(roster, TEXTS_ROOT)
    if pruned:
        print(f"pruned {pruned:,} orphan bronze texts")
    backlog: polars.DataFrame = pick_downloads(roster, watermark)
    candidate_new, candidate_changed = count_changes(backlog)

    # Sorted slice is deterministic; next run resumes there
    todo: polars.DataFrame = backlog.head(MAX_DOWNLOADS_PER_RUN)
    deferred: int = backlog.height - todo.height
    print(
        f"roster {roster.height:,} | backlog {backlog.height:,} "
        f"(new {candidate_new:,}, changed {candidate_changed:,}, "
        f"retry {backlog.height - candidate_new - candidate_changed:,}) "
        f"| this run {todo.height:,}, deferred {deferred:,}"
    )

    processed: polars.DataFrame = download_texts(todo)
    downloaded: int = processed.filter(polars.col("status") == "ingested").height
    failed: int = processed.filter(polars.col("status") == "failed").height
    copyrighted: int = processed.filter(polars.col("status") == "copyrighted").height

    storage.write_table(
        "bronze.watermark", update_watermark(watermark, processed, run_time), mode="overwrite"
    )
    counts = IngestCounts(roster.height, candidate_new, candidate_changed, downloaded, failed)
    storage.write_table(
        "bronze.ingest_audit", ingest_audit_row("text_ingest", run_time, counts), mode="append"
    )

    print(
        f"texts: {downloaded:,} downloaded, {failed:,} failed, {copyrighted:,} copyrighted"
        f" -> {TEXTS_ROOT} | {deferred:,} left for the next run"
    )


if __name__ == "__main__":
    main()
