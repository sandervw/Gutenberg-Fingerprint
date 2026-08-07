# Plan: Make filter a helper, catalog_ingest the orchestrator

Make `filter.py` a pure helper: `catalog_df -> FilterResult`, no `storage` import, no `__main__`. `catalog_ingest.py` owns the reads, the table writes, the CDC diff, the audit row, and the `new_count` gate.

## `python/helpers/filter.py` (moved from `python/workflow/`)

1. Move the file into `helpers/`. Import becomes `from python.helpers import filter`.
2. Delete the `__main__` block, `from python.helpers import storage`, and `from datetime import datetime, timezone`.
3. Keep every expression (`SUBJECTS` ... `GENRE`, `DEDUP_TITLE`, `DEDUP_AUTHOR`) exactly as-is.
4. Add the dataclass and the pure entry point:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FilterResult:
    raw_works: pl.DataFrame
    deduped: int  # re-release rows dropped

def filter_catalog(catalog_df: pl.DataFrame) -> FilterResult:
    scoped = catalog_df.filter(
        (pl.col("type") == "Text") & (pl.col("language") == "en") & IN_SCOPE
    ).with_columns(GENRE.alias("genre"))
    raw_works = (
        scoped.with_columns(DEDUP_TITLE.alias("_k_title"), DEDUP_AUTHOR.alias("_k_author"))
        .sort("gutenberg_id")
        .unique(subset=["_k_title", "_k_author"], keep="first", maintain_order=True)
        .drop("_k_title", "_k_author")
    )
    return FilterResult(raw_works=raw_works, deduped=scoped.height - raw_works.height)
```

## `python/workflow/catalog_ingest.py`

1. Add `from python.helpers import filter` to the imports.
2. In `__main__`, after `write_table("bronze.catalog", ...)` and `ensure_table("bronze.watermark", ...)` (keep `ensure_table` before the watermark read below), append the filter body, wired to the in-memory `catalog_df` and the existing `run_ts`:

```python
    result: filter.FilterResult = filter.filter_catalog(catalog_df)
    raw_works_df: pl.DataFrame = result.raw_works
    storage.write_table("raw.raw_works", raw_works_df, mode="overwrite")

    by_genre: dict[str, int] = dict(
        raw_works_df.group_by("genre").len().sort("genre").iter_rows()
    )
    print(f"raw_works: kept {raw_works_df.height:,} of {catalog_df.height:,} catalog rows")
    print(f"deduped: dropped {result.deduped:,} re-release rows")
    print(f"genre split: {by_genre}")

    # CDC diff - in-scope set vs watermark
    joined: pl.DataFrame = raw_works_df.select("gutenberg_id", "catalog_row_hash").join(
        storage.read_table("bronze.watermark").select(
            "gutenberg_id", pl.col("catalog_row_hash").alias("seen_hash")
        ),
        on="gutenberg_id",
        how="left",
    )
    candidate_new: int = joined.filter(pl.col("seen_hash").is_null()).height
    candidate_changed: int = joined.filter(
        pl.col("seen_hash").is_not_null()
        & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
    ).height
    audit_row: pl.DataFrame = pl.DataFrame(
        {
            "run_ts": [run_ts],  # reuse the run's timestamp
            "run_type": ["catalog_refresh"],
            "books_in_catalog": [catalog_df.height],
            "candidate_new": [candidate_new],
            "candidate_changed": [candidate_changed],
            "downloaded": [0],
            "failed": [0],
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
    storage.write_table("bronze.ingest_audit", audit_row, mode="append")
    print(f"new in-scope works: {candidate_new:,} | changed: {candidate_changed:,}")
    storage.emit("new_count", candidate_new + candidate_changed)
```

Drop the `catalog photo written` print.

## `.github/workflows/nightly.yml`

1. Give the **Catalog ingest** step `id: catalog` and the `new_count` output capture:

```yaml
      - name: Catalog ingest (CDC gate)
        id: catalog
        run: |
          output=$(ssh $SSH_OPTS $BOX "cd /code/gufime && GUFIME_TARGET=postgres ~/.local/bin/uv run python -m python.workflow.catalog_ingest")
          echo "$output"
          echo "$output" | grep '^new_count=' >> "$GITHUB_OUTPUT"
```

2. Delete the entire **Filter (CDC gate)** step.
3. Flip all **8** downstream gates from `steps.filter.outputs.new_count` to `steps.catalog.outputs.new_count`: Text ingest, Strip, Measure, dbt deps, dbt build, Evidence build, Deploy to Cloudflare Pages, Backup corpus to R2. (Backup Postgres stays ungated.)

## Docs

- `README.md`: architecture diagram (lines ~16-18) collapses `filter.py` into the `catalog_ingest.py` line; local-run block (lines ~100-101) drops the separate `python -m python.workflow.filter` seed, since `catalog_ingest` now seeds both `bronze.catalog` and `raw.raw_works`.
- `docs/Project-Outline.md`: diagram (lines ~14-16) and line ~28 (`if: steps.catalog.outputs.new_count`; "run stops after `catalog_ingest.py`").

## Validation

```bash
# duckdb, local
uv run python -m python.workflow.catalog_ingest
```

- Confirm the printout still shows `raw_works: kept ...`, `deduped: ...`, `genre split: {...}` with all four genres, and a final `new_count=` line.
- Confirm `raw.raw_works` and `bronze.ingest_audit` land with the same schema and row counts as before (one `catalog_refresh` row appended per run).
- `cd dbt && uv run dbt build` stays green.
- Grep the repo for stray `python.workflow.filter` / `steps.filter` references.

## Out of scope

- Renaming `catalog_ingest.py`; keep the name.
- Any change to `raw.raw_works` / `bronze.ingest_audit` schema or contents.
- `text_ingest`, `strip`, `measure`, dbt, or Evidence logic.
- The CDC diff computation itself.
