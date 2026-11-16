# Catalog parse: normalize feed columns, key by id, hash rows.

from __future__ import annotations

import hashlib
import re
from datetime import datetime

import polars

from python.core.ledger import UTC_DATETIME_TYPE


def normalize_column(name: str) -> str:
    """'Text#' -> 'text', 'LoCC' -> 'locc', 'Bookshelves' -> 'bookshelves'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def row_hashes(frame: polars.DataFrame, id_column: str = "gutenberg_id") -> polars.Series:
    """sha256 per row over every non-id field, in column order."""
    payload_columns = [column for column in frame.columns if column != id_column]
    # \x1f (unit separator) between fields
    payload = frame.select(
        polars.concat_str(
            [polars.col(column).fill_null("") for column in payload_columns], separator="\x1f"
        ).alias("payload")
    )["payload"]
    return polars.Series(
        "catalog_row_hash",
        [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in payload],
    )


def parse_catalog(feed: polars.DataFrame, run_time: datetime) -> polars.DataFrame:
    """All-text feed to keyed, hashed, timestamped catalog rows."""
    catalog = feed.rename({column: normalize_column(column) for column in feed.columns})
    if "text" not in catalog.columns:
        raise KeyError(f"expected a 'Text#' column in the feed, got: {catalog.columns}")
    catalog = catalog.rename({"text": "gutenberg_id"}).with_columns(
        polars.col("gutenberg_id").cast(polars.Int64)  # strict cast: format drift fails loudly
    )
    return catalog.with_columns(
        row_hashes(catalog).alias("catalog_row_hash"),
        polars.lit(f"{run_time:%Y-%m-%d}").alias("snapshot_date"),
        polars.lit(run_time, dtype=UTC_DATETIME_TYPE).alias("loaded_at"),
    )
