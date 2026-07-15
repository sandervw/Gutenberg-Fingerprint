# Fabric notebook: nb_text_ingest
# Silver raw_works roster -> bronze text files; pulls only new/changed/failed vs watermark.
# www.gutenberg.org blocks automated clients, so we use PG's own mirror.

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import notebookutils
import polars as pl
import requests
from deltalake import DeltaTable, write_deltalake

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
RAW_WORKS_TABLE: str = f"{ONELAKE}/lh_silver.Lakehouse/Tables/dbo/raw_works"
WATERMARK_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/watermark"
AUDIT_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/ingest_audit"

TEXTS_ROOT: Path = Path("/lakehouse/default/Files/texts")
MIRROR: str = "https://gutenberg.pglaf.org"
USER_AGENT: str = "gutenberg-fingerprint-pipeline/0.1 (contact: samvanwilligen@gmail.com)"

SLEEP_S: float = 2.0  # PG's stated politeness gap
MAX_CONSECUTIVE_FAILURES: int = 5  # a streak means blocked or mirror down

TS_UTC: pl.Datetime = pl.Datetime("us", "UTC")


def storage_options() -> dict[str, str]:
    # Fetched per call: token lives ~1 h, a backfill outlasts it
    return {
        "bearer_token": notebookutils.credentials.getToken("storage"),
        "use_fabric_endpoint": "true",
    }


# %% Diff - roster vs watermark ledger


def read_table(table_uri: str) -> pl.DataFrame:
    return pl.from_arrow(
        DeltaTable(table_uri, storage_options=storage_options()).to_pyarrow_table()
    )


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


def text_urls(gid: int) -> list[str]:
    dirs = "/".join(str(gid)[:-1]) or "0"
    return [
        f"{MIRROR}/cache/epub/{gid}/pg{gid}.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}-0.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}-8.txt",
        f"{MIRROR}/{dirs}/{gid}/{gid}.txt",
    ]


def fetch_text(gid: int, session: requests.Session) -> bytes:
    for i, url in enumerate(text_urls(gid)):
        if i:
            time.sleep(SLEEP_S)
        resp = session.get(url, timeout=60)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.content
    raise FileNotFoundError(f"no text file for {gid}")


def download_texts(todo: pl.DataFrame) -> pl.DataFrame:
    TEXTS_ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    rows: list[tuple[int, str, str | None, str]] = []
    consecutive_failures = 0
    for i, row in enumerate(todo.iter_rows(named=True)):
        if i:
            time.sleep(SLEEP_S)
        if i % 50 == 0:
            print(f"{i:,}/{todo.height:,}...")
        gid = row["gutenberg_id"]
        try:
            raw = fetch_text(gid, session)
            (TEXTS_ROOT / f"{gid}.txt").write_bytes(raw)
            text_hash = hashlib.sha256(raw).hexdigest()
            rows.append((gid, row["catalog_row_hash"], text_hash, "ingested"))
            consecutive_failures = 0
        except Exception as exc:
            print(f"{gid}: {exc}")
            rows.append((gid, row["catalog_row_hash"], None, "failed"))
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
            pl.col("first_seen").fill_null(pl.lit(run_ts, dtype=TS_UTC)),
            pl.lit(run_ts, dtype=TS_UTC).alias("last_changed"),
        )
        .select(watermark.columns)
    )
    return pl.concat([carried, updated])


def write_watermark(watermark: pl.DataFrame) -> None:
    # Strict schema on purpose: drift should fail loudly
    write_deltalake(
        WATERMARK_TABLE, watermark.to_arrow(), mode="overwrite", storage_options=storage_options()
    )
    DeltaTable(WATERMARK_TABLE, storage_options=storage_options()).create_checkpoint()


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
            "run_ts": TS_UTC,
            "run_type": pl.Utf8,
            "books_in_catalog": pl.Int64,
            "candidate_new": pl.Int64,
            "candidate_changed": pl.Int64,
            "downloaded": pl.Int64,
            "failed": pl.Int64,
        },
    )
    write_deltalake(AUDIT_TABLE, row.to_arrow(), mode="append", storage_options=storage_options())


# %% Run

run_ts: datetime = datetime.now(timezone.utc)
roster: pl.DataFrame = read_table(RAW_WORKS_TABLE)
watermark: pl.DataFrame = read_table(WATERMARK_TABLE)
todo: pl.DataFrame = pick_downloads(roster, watermark)

candidate_new: int = todo.filter(pl.col("seen_hash").is_null()).height
candidate_changed: int = todo.filter(
    pl.col("seen_hash").is_not_null() & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
).height
print(
    f"roster {roster.height:,} | to pull {todo.height:,} "
    f"(new {candidate_new:,}, changed {candidate_changed:,}, "
    f"retry {todo.height - candidate_new - candidate_changed:,})"
)

processed: pl.DataFrame = download_texts(todo)
downloaded: int = processed.filter(pl.col("status") == "ingested").height
failed: int = processed.height - downloaded

write_watermark(update_watermark(watermark, processed, run_ts))
write_audit(roster.height, candidate_new, candidate_changed, downloaded, failed, run_ts)

print(f"texts: {downloaded:,} downloaded, {failed:,} failed -> Files/texts/")
