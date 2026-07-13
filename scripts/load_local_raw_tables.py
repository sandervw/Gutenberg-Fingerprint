"""Load local stand-ins for the silver raw tables into dbt/warehouse.duckdb.

Run: uv run python scripts/load_local_raw_tables.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl

CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
USER_AGENT = "gutenberg-fingerprint-pipeline/0.1 (contact: samvanwilligen@gmail.com)"

REPO = Path(__file__).resolve().parents[1]
CSV_CACHE = REPO / "data" / "pg_catalog.csv"
DUCKDB_PATH = REPO / "dbt" / "warehouse.duckdb"

TS_UTC = pl.Datetime("us", "UTC")


def download_catalog(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as fh:
        shutil.copyfileobj(resp, fh)


def normalize_column(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def row_hashes(df: pl.DataFrame, id_col: str = "gutenberg_id") -> pl.Series:
    """sha256 per row over every non-id field, in column order."""
    payload_cols = [c for c in df.columns if c != id_col]
    payload = df.select(
        pl.concat_str(
            [pl.col(c).fill_null("") for c in payload_cols], separator="\x1f"
        ).alias("payload")
    )["payload"]
    return pl.Series(
        "catalog_row_hash",
        [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in payload],
    )


def load_catalog(csv_path: Path, run_ts: datetime) -> pl.DataFrame:
    df = pl.read_csv(csv_path, infer_schema_length=0)
    df = df.rename({c: normalize_column(c) for c in df.columns})
    if "text" not in df.columns:
        raise KeyError(f"expected a 'Text#' column in the feed, got: {df.columns}")
    df = df.rename({"text": "gutenberg_id"}).with_columns(
        pl.col("gutenberg_id").cast(pl.Int64)
    )
    return df.with_columns(
        row_hashes(df).alias("catalog_row_hash"),
        pl.lit(f"{run_ts:%Y-%m-%d}").alias("snapshot_date"),
        pl.lit(run_ts, dtype=TS_UTC).alias("loaded_at"),
    )


def filter_works(catalog_df: pl.DataFrame) -> pl.DataFrame:
    is_fantasy = pl.col("subjects").fill_null("").str.contains("(?i)fantasy") | pl.col(
        "bookshelves"
    ).fill_null("").str.contains(r"(^|; )Fantasy($|;)")
    return catalog_df.filter(
        (pl.col("type") == "Text") & (pl.col("language") == "en") & is_fantasy
    )


if __name__ == "__main__":
    if CSV_CACHE.exists():
        print(f"using cached feed {CSV_CACHE}")
    else:
        download_catalog(CATALOG_URL, CSV_CACHE)
        print(f"downloaded feed -> {CSV_CACHE}")

    catalog_df = load_catalog(CSV_CACHE, datetime.now(timezone.utc))
    works_df = filter_works(catalog_df)

    con = duckdb.connect(str(DUCKDB_PATH))
    con.register("works_src", works_df.to_arrow())
    con.execute("create schema if not exists raw")
    con.execute("create or replace table raw.raw_works as select * from works_src")
    con.execute(
        "create table if not exists raw.raw_measurements ("
        "work_id varchar, metric varchar, value double, "
        "loaded_at timestamp with time zone)"
    )
    con.execute(
        "create table if not exists raw.raw_vocab ("
        "work_id varchar, term varchar, term_count bigint, "
        "loaded_at timestamp with time zone)"
    )
    con.close()
    print(
        f"raw_works: kept {works_df.height:,} of {catalog_df.height:,} catalog rows "
        f"-> {DUCKDB_PATH}"
    )
