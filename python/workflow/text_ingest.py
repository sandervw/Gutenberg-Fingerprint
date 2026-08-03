# Text ingest: download new/changed/failed works from PG's mirror into bronze.

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import requests

from python.helpers import storage

TEXTS_ROOT: Path = storage.file_path("bronze/texts")
MIRROR: str = "https://gutenberg.pglaf.org"

SLEEP_S: float = 2.0  # PG's stated politeness gap
MAX_CONSECUTIVE_FAILURES: int = 5  # a streak means blocked or mirror down
MAX_DOWNLOADS_PER_RUN: int = 200  # caps a run to a predictable length

# %% Diff - roster vs watermark ledger


def pick_downloads(roster: pl.DataFrame, watermark: pl.DataFrame) -> pl.DataFrame:
    """New, changed, or previously failed works."""
    seen = watermark.select(
        "gutenberg_id",
        pl.col("catalog_row_hash").alias("seen_hash"),
        "status",
    )
    return (
        roster.select("gutenberg_id", "catalog_row_hash")
        .join(seen, on="gutenberg_id", how="left")
        .filter(
            pl.col("seen_hash").is_null()
            | (pl.col("seen_hash") != pl.col("catalog_row_hash"))
            | (pl.col("status") == "failed")
        )
        .sort("gutenberg_id")
    )


# %% Download - raw bytes, one file per work, rate-limited


def text_urls(gutenberg_id: int) -> list[str]:
    digit_path = "/".join(str(gutenberg_id)[:-1]) or "0"
    return [
        f"{MIRROR}/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}-8.txt",
        f"{MIRROR}/{digit_path}/{gutenberg_id}/{gutenberg_id}.txt",
    ]


def fetch_text(gutenberg_id: int, session: requests.Session) -> bytes:
    for index, url in enumerate(text_urls(gutenberg_id)):
        if index:
            time.sleep(SLEEP_S)
        response = session.get(url, timeout=60)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        return response.content
    raise FileNotFoundError(f"no text file for {gutenberg_id}")


def download_texts(todo: pl.DataFrame) -> pl.DataFrame:
    TEXTS_ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = storage.USER_AGENT

    rows: list[tuple[int, str, str | None, str]] = []
    consecutive_failures = 0
    for index, row in enumerate(todo.iter_rows(named=True)):
        if index:
            time.sleep(SLEEP_S)
        if index % 50 == 0:
            print(f"{index:,}/{todo.height:,}...")
        gutenberg_id = row["gutenberg_id"]
        try:
            raw_bytes = fetch_text(gutenberg_id, session)
            (TEXTS_ROOT / f"{gutenberg_id}.txt").write_bytes(raw_bytes)
            text_hash = hashlib.sha256(raw_bytes).hexdigest()
            rows.append((gutenberg_id, row["catalog_row_hash"], text_hash, "ingested"))
            consecutive_failures = 0
        # OSError covers the all-mirrors-404 FileNotFoundError
        except (requests.RequestException, OSError) as exc:
            print(f"{gutenberg_id}: {exc}")
            rows.append((gutenberg_id, row["catalog_row_hash"], None, "failed"))
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"{consecutive_failures} failures in a row, stopping early")
                break
    return pl.DataFrame(
        rows,
        schema={
            "gutenberg_id": pl.Int64,
            "catalog_row_hash": pl.Utf8,
            "text_hash": pl.Utf8,
            "status": pl.Utf8,
        },
        orient="row",
    )


# %% Watermark - carry untouched rows, upsert processed ones


def update_watermark(
    watermark: pl.DataFrame, processed: pl.DataFrame, run_ts: datetime
) -> pl.DataFrame:
    carried = watermark.filter(
        ~pl.col("gutenberg_id").is_in(processed["gutenberg_id"].implode())
    )
    updated = (
        processed.join(
            watermark.select("gutenberg_id", "first_seen"), on="gutenberg_id", how="left"
        )
        .with_columns(
            pl.col("first_seen").fill_null(pl.lit(run_ts, dtype=storage.UTC_DATETIME_TYPE)),
            pl.lit(run_ts, dtype=storage.UTC_DATETIME_TYPE).alias("last_changed"),
        )
        .select(watermark.columns)
    )
    return pl.concat([carried, updated])


def write_audit(
    roster_size: int, new: int, changed: int, downloaded: int, failed: int, run_ts: datetime
) -> None:
    row = pl.DataFrame(
        {
            "run_ts": [run_ts],
            "run_type": ["text_ingest"],
            "books_in_catalog": [roster_size],
            "candidate_new": [new],
            "candidate_changed": [changed],
            "downloaded": [downloaded],
            "failed": [failed],
        },
        schema={
            "run_ts": storage.UTC_DATETIME_TYPE,
            "run_type": pl.Utf8,
            "books_in_catalog": pl.Int64,
            "candidate_new": pl.Int64,
            "candidate_changed": pl.Int64,
            "downloaded": pl.Int64,
            "failed": pl.Int64,
        },
    )
    storage.write_table("bronze.ingest_audit", row, mode="append")


# %% Run

if __name__ == "__main__":
    run_ts: datetime = datetime.now(timezone.utc)
    roster: pl.DataFrame = storage.read_table("raw.raw_works")
    watermark: pl.DataFrame = storage.read_table("bronze.watermark")
    backlog: pl.DataFrame = pick_downloads(roster, watermark)

    candidate_new: int = backlog.filter(pl.col("seen_hash").is_null()).height
    candidate_changed: int = backlog.filter(
        pl.col("seen_hash").is_not_null()
        & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
    ).height

    # Sorted slice is deterministic; next run resumes there
    todo: pl.DataFrame = backlog.head(MAX_DOWNLOADS_PER_RUN)
    deferred: int = backlog.height - todo.height
    print(
        f"roster {roster.height:,} | backlog {backlog.height:,} "
        f"(new {candidate_new:,}, changed {candidate_changed:,}, "
        f"retry {backlog.height - candidate_new - candidate_changed:,}) "
        f"| this run {todo.height:,}, deferred {deferred:,}"
    )

    processed: pl.DataFrame = download_texts(todo)
    downloaded: int = processed.filter(pl.col("status") == "ingested").height
    failed: int = processed.height - downloaded

    storage.write_table(
        "bronze.watermark", update_watermark(watermark, processed, run_ts), mode="overwrite"
    )
    write_audit(roster.height, candidate_new, candidate_changed, downloaded, failed, run_ts)

    print(
        f"texts: {downloaded:,} downloaded, {failed:,} failed -> {TEXTS_ROOT}"
        f" | {deferred:,} left for the next run"
    )
