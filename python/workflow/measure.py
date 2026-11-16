# Measure: corpus markdown -> raw_measurements + raw_vocab, incremental by watermark.

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars
import spacy

from python import storage
from python.core.clean import clean_markdown
from python.core.ledger import UTC_DATETIME_TYPE
from python.core.measure import (
    METRIC_FUNCTIONS,
    Watermarks,
    build_work_document,
    collect_vocab,
    measure_metrics,
    plan_measures,
)


def source_work_id(source: Path) -> str:
    """Gutenberg filename prefix, or the full stem for self works."""
    if source.parent.name == storage.SELF_FOLDER:
        return source.stem
    return source.name.split("-", 1)[0]


def read_watermarks(manifest_path: Path) -> Watermarks:
    """Last measured, catalog-changed, and manual-upload times per work."""
    try:
        measured_at: dict[str, datetime] = dict(
            storage.read_table("raw.raw_measurements", columns=["work_id", "loaded_at"])
            .group_by("work_id")
            .agg(polars.col("loaded_at").max())
            .iter_rows()
        )
    except storage.TableMissing:
        measured_at = {}
    catalog_changed_at: dict[str, datetime] = {
        str(gutenberg_id): last_changed
        for gutenberg_id, last_changed in storage.read_table(
            "bronze.watermark", columns=["gutenberg_id", "last_changed"]
        ).iter_rows()
    }
    # Manual works' watermark: the seed manifest's loaded_at stamps
    self_changed_at: dict[str, datetime] = dict(
        polars.read_csv(manifest_path, schema_overrides={"loaded_at": polars.String})
        .select(
            "work_id",
            polars.col("loaded_at").str.to_datetime("%Y-%m-%d %H:%M:%S").dt.replace_time_zone("UTC"),
        )
        .iter_rows()
    )
    return Watermarks(measured_at, catalog_changed_at, self_changed_at)


def sync_table(name: str, frame: polars.DataFrame, replaced_ids: list[str], *, first_fill: bool) -> None:
    """Swap re-measured works' rows in place, drop stale, keep the rest."""
    if first_fill:
        storage.write_table(name, frame, mode="overwrite")
        return
    storage.delete_where(name, "work_id", replaced_ids)
    if frame.height:
        storage.write_table(name, frame, mode="append")


def main() -> None:
    """Measure new and changed works; sync raw_measurements and raw_vocab."""
    corpus_root = storage.file_path("silver/corpus")
    sources = {source_work_id(path): path for path in sorted(corpus_root.rglob("*.md"))}
    self_ids = frozenset(
        work_id for work_id, path in sources.items() if path.parent.name == storage.SELF_FOLDER
    )
    watermarks = read_watermarks(storage.file_path("bronze/self/_manifest.csv"))
    plan = plan_measures(sources, self_ids, watermarks)
    print(f"corpus {len(sources)}: {len(plan.todo)} to measure, {len(plan.stale_ids)} stale to drop")

    # NER disabled: no metric uses it, skipping speeds parsing
    language_model = spacy.load("en_core_web_sm", disable=["ner"])

    measurement_rows: list[tuple[str, str, float]] = []
    vocab_rows: list[tuple[str, str, int]] = []
    for done, (work_id, source) in enumerate(plan.todo.items(), start=1):
        document = build_work_document(language_model, clean_markdown(source.read_text(encoding="utf-8")))
        measurement_rows.extend(measure_metrics(work_id, document))
        vocab_rows.extend(collect_vocab(work_id, document))
        if done % 50 == 0 or done == len(plan.todo):
            print(f"{done}/{len(plan.todo)} works parsed")

    # One batch timestamp shared by both tables
    loaded_at = datetime.now(timezone.utc)

    measurements = polars.DataFrame(
        measurement_rows,
        schema={"work_id": polars.String, "metric": polars.String, "value": polars.Float64},
        orient="row",
    ).with_columns(loaded_at=polars.lit(loaded_at, dtype=UTC_DATETIME_TYPE))
    vocab = polars.DataFrame(
        vocab_rows,
        schema={"work_id": polars.String, "term": polars.String, "term_count": polars.Int64},
        orient="row",
    ).with_columns(loaded_at=polars.lit(loaded_at, dtype=UTC_DATETIME_TYPE))

    replaced_ids = sorted(set(plan.todo) | set(plan.stale_ids))
    first_fill = not watermarks.measured_at
    sync_table("raw.raw_measurements", measurements, replaced_ids, first_fill=first_fill)
    sync_table("raw.raw_vocab", vocab, replaced_ids, first_fill=first_fill)
    print(
        f"Measured {len(plan.todo)} of {len(sources)} works ({len(plan.stale_ids)} stale dropped); "
        f"{measurements.height:,} rows into raw_measurements "
        f"({len(METRIC_FUNCTIONS)} metrics); {vocab.height:,} rows into raw_vocab."
    )


if __name__ == "__main__":
    main()
