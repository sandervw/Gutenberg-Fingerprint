# Catalog ingest: PG feed -> bronze catalog table + raw CSV snapshot.

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import polars
import requests

from python import storage
from python.core import filter as scope_filter
from python.core.catalog import parse_catalog
from python.core.watermark import (
    WATERMARK_SCHEMA,
    IngestCounts,
    count_changes,
    ingest_audit_row,
    pick_downloads,
)

CATALOG_URL: str = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"

# %% Download - retries transient failures

RETRY_STATUS: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})


def _retriable(error: requests.RequestException) -> bool:
    """Connection and timeout errors, plus the transient statuses above."""
    if isinstance(error, requests.HTTPError):
        return error.response is not None and error.response.status_code in RETRY_STATUS
    return True


def _stream_to_file(url: str, destination: Path, timeout_seconds: float) -> int:
    """Stream one GET response to a file; return bytes written."""
    written = 0
    with requests.get(
        url,
        headers={"User-Agent": storage.USER_AGENT},
        stream=True,
        timeout=timeout_seconds,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1 << 20):
                written += output_file.write(chunk)
    return written


def download_catalog(
    url: str, destination: Path, timeout_seconds: float = 120.0, attempts: int = 4
) -> int:
    """Stream the catalog feed to destination; return bytes written."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            return _stream_to_file(url, destination, timeout_seconds)
        except requests.RequestException as error:
            if attempt == attempts or not _retriable(error):
                raise
            backoff: int = 30 * 2 ** (attempt - 1)
            print(f"catalog fetch failed ({error}); retrying in {backoff}s")
            time.sleep(backoff)
    raise RuntimeError("download_catalog exhausted its retries")


# %% Run


def main() -> int:
    """Refresh the catalog and raw_works; return New plus Changed count."""
    run_time: datetime = datetime.now(timezone.utc)
    raw_path: Path = storage.file_path(f"bronze/catalog/pg_catalog_{run_time:%Y-%m-%d}.csv")

    raw_bytes: int = download_catalog(CATALOG_URL, raw_path)
    print(f"raw feed -> {raw_path} ({raw_bytes:,} bytes)")

    # infer_schema_length=0 keeps every column as text
    catalog = parse_catalog(polars.read_csv(raw_path, infer_schema_length=0), run_time)
    print(f"parsed {catalog.height:,} rows, {catalog.width} columns")

    storage.write_table("bronze.catalog", catalog, mode=storage.WriteMode.OVERWRITE)
    storage.ensure_table("bronze.watermark", WATERMARK_SCHEMA)

    result = scope_filter.filter_catalog(catalog)
    raw_works = result.raw_works
    storage.write_table("raw.raw_works", raw_works, mode=storage.WriteMode.OVERWRITE)

    by_genre: dict[str, int] = dict(raw_works.group_by("genre").len().sort("genre").iter_rows())
    print(f"raw_works: kept {raw_works.height:,} of {catalog.height:,} catalog rows")
    print(f"deduped: dropped {result.deduped:,} re-release rows")
    print(f"genre split: {by_genre}")

    candidate_new, candidate_changed = count_changes(
        pick_downloads(raw_works, storage.read_table("bronze.watermark"))
    )
    counts = IngestCounts(catalog.height, candidate_new, candidate_changed)
    storage.write_table(
        "bronze.ingest_audit", ingest_audit_row("catalog_refresh", run_time, counts), mode=storage.WriteMode.APPEND
    )
    print(f"new in-scope works: {candidate_new:,} | changed: {candidate_changed:,}")
    storage.emit("new_count", candidate_new + candidate_changed)
    return candidate_new + candidate_changed


if __name__ == "__main__":
    main()
