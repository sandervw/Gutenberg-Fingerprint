# Change detection: watermark diff, watermark upsert, and ingest audit rows.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import polars

UTC_DATETIME_TYPE: polars.Datetime = polars.Datetime("us", "UTC")

WATERMARK_SCHEMA: dict[str, polars.DataType] = {
    "gutenberg_id": polars.Int64,
    "catalog_row_hash": polars.String,
    "text_hash": polars.String,
    "first_seen": UTC_DATETIME_TYPE,
    "last_changed": UTC_DATETIME_TYPE,
    "status": polars.String,
}

AUDIT_SCHEMA: dict[str, polars.DataType] = {
    "run_ts": UTC_DATETIME_TYPE,
    "run_type": polars.String,
    "books_in_catalog": polars.Int64,
    "candidate_new": polars.Int64,
    "candidate_changed": polars.Int64,
    "downloaded": polars.Int64,
    "failed": polars.Int64,
}


@dataclass(frozen=True)
class IngestCounts:
    """One run's catalog size, change counts, and download outcomes."""

    books_in_catalog: int
    candidate_new: int
    candidate_changed: int
    downloaded: int = 0
    failed: int = 0


def ingest_audit_row(run_type: str, run_time: datetime, counts: IngestCounts) -> polars.DataFrame:
    """One bronze.ingest_audit row for this run."""
    return polars.DataFrame(
        {
            "run_ts": [run_time],
            "run_type": [run_type],
            "books_in_catalog": [counts.books_in_catalog],
            "candidate_new": [counts.candidate_new],
            "candidate_changed": [counts.candidate_changed],
            "downloaded": [counts.downloaded],
            "failed": [counts.failed],
        },
        schema=AUDIT_SCHEMA,
    )


def pick_downloads(roster: polars.DataFrame, watermark: polars.DataFrame) -> polars.DataFrame:
    """New, changed, or previously failed works."""
    seen = watermark.select(
        "gutenberg_id",
        polars.col("catalog_row_hash").alias("seen_hash"),
        "status",
    )
    return (
        roster.select("gutenberg_id", "catalog_row_hash")
        .join(seen, on="gutenberg_id", how="left")
        .filter(
            polars.col("seen_hash").is_null()
            | (polars.col("seen_hash") != polars.col("catalog_row_hash"))
            | (polars.col("status") == "failed")
        )
        .sort("gutenberg_id")
    )


def count_changes(backlog: polars.DataFrame) -> tuple[int, int]:
    """New and Changed counts from a roster joined to seen hashes."""
    new = backlog.filter(polars.col("seen_hash").is_null()).height
    changed = backlog.filter(
        polars.col("seen_hash").is_not_null()
        & (polars.col("seen_hash") != polars.col("catalog_row_hash"))
    ).height
    return new, changed


def update_watermark(
    watermark: polars.DataFrame, processed: polars.DataFrame, run_time: datetime
) -> polars.DataFrame:
    """Carry untouched rows; upsert processed ones with this run's time."""
    carried = watermark.filter(
        ~polars.col("gutenberg_id").is_in(processed["gutenberg_id"].implode())
    )
    updated = (
        processed.join(
            watermark.select("gutenberg_id", "first_seen"), on="gutenberg_id", how="left"
        )
        .with_columns(
            polars.col("first_seen").fill_null(polars.lit(run_time, dtype=UTC_DATETIME_TYPE)),
            polars.lit(run_time, dtype=UTC_DATETIME_TYPE).alias("last_changed"),
        )
        .select(watermark.columns)
    )
    return polars.concat([carried, updated])
