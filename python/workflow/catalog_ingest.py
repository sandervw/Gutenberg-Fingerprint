# Catalog ingest: PG feed -> bronze catalog table + raw CSV snapshot.

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import requests

from python.helpers import storage

CATALOG_URL: str = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"

WATERMARK_SCHEMA: dict[str, pl.DataType] = {
    "gutenberg_id": pl.Int64,
    "catalog_row_hash": pl.String,
    "text_hash": pl.String,
    "first_seen": storage.TS_UTC,
    "last_changed": storage.TS_UTC,
    "status": pl.String,
}

# %% Download - retries transient failures

RETRY_STATUS: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})


def _retriable(exc: requests.RequestException) -> bool:
    """Connection and timeout errors, plus the transient statuses above."""
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in RETRY_STATUS
    return True


def download_catalog(
    url: str, dest: Path, timeout_s: float = 120.0, attempts: int = 4
) -> int:
    """Stream the catalog feed to dest; return bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            written = 0
            with requests.get(
                url,
                headers={"User-Agent": storage.USER_AGENT},
                stream=True,
                timeout=timeout_s,
            ) as response:
                response.raise_for_status()
                with dest.open("wb") as output_file:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        written += output_file.write(chunk)
            return written
        except requests.RequestException as exc:
            if attempt == attempts or not _retriable(exc):
                raise
            backoff: int = 30 * 2 ** (attempt - 1)
            print(f"catalog fetch failed ({exc}); retrying in {backoff}s")
            time.sleep(backoff)
    raise RuntimeError("download_catalog exhausted its retries")


# %% Parse - normalize columns, hash rows


def normalize_column(name: str) -> str:
    """'Text#' -> 'text', 'LoCC' -> 'locc', 'Bookshelves' -> 'bookshelves'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def row_hashes(df: pl.DataFrame, id_column: str = "gutenberg_id") -> pl.Series:
    """sha256 per row over every non-id field, in column order."""
    payload_columns = [column for column in df.columns if column != id_column]
    # \x1f (unit separator) between fields
    payload = df.select(
        pl.concat_str(
            [pl.col(column).fill_null("") for column in payload_columns], separator="\x1f"
        ).alias("payload")
    )["payload"]
    return pl.Series(
        "catalog_row_hash",
        [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in payload],
    )


def load_catalog(csv_path: Path, run_ts: datetime) -> pl.DataFrame:
    # infer_schema_length=0 keeps every column as text
    df = pl.read_csv(csv_path, infer_schema_length=0)
    df = df.rename({column: normalize_column(column) for column in df.columns})
    if "text" not in df.columns:
        raise KeyError(f"expected a 'Text#' column in the feed, got: {df.columns}")
    df = df.rename({"text": "gutenberg_id"}).with_columns(
        pl.col("gutenberg_id").cast(pl.Int64)  # strict cast: format drift fails loudly
    )
    return df.with_columns(
        row_hashes(df).alias("catalog_row_hash"),
        pl.lit(f"{run_ts:%Y-%m-%d}").alias("snapshot_date"),
        pl.lit(run_ts, dtype=storage.TS_UTC).alias("loaded_at"),
    )


# %% Run

if __name__ == "__main__":
    run_ts: datetime = datetime.now(timezone.utc)
    raw_path: Path = storage.file_path(f"bronze/catalog/pg_catalog_{run_ts:%Y-%m-%d}.csv")

    raw_bytes: int = download_catalog(CATALOG_URL, raw_path)
    print(f"raw feed -> {raw_path} ({raw_bytes:,} bytes)")

    catalog_df: pl.DataFrame = load_catalog(raw_path, run_ts)
    print(f"parsed {catalog_df.height:,} rows, {catalog_df.width} columns")

    storage.write_table("bronze.catalog", catalog_df, mode="overwrite")
    storage.ensure_table("bronze.watermark", WATERMARK_SCHEMA)
    print(f"catalog photo written: {catalog_df.height:,} books")
