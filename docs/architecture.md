# Architecture

Terms follow [the glossary](glossary.md). Sections 1, 4, and 5 are binding; change them in the same PR as the code that needs it.

## 1. Parts and boundaries

| Part | Folder | Does | May import |
|---|---|---|---|
| Steps | `python/workflow/` | One module per pipeline step | `python/helpers/` |
| Logic and seam | `python/helpers/` | Metric, filter, and cleaning functions; `storage.py` is the only storage access | standard library, spaCy, polars; `storage.py` also psycopg and duckdb |
| Orchestration | `python/dagster/` | Assets, schedule, gate sensor, failure alert | `python/workflow/` |
| Warehouse | `dbt/` | Staging, star schema, marts | sources in `raw` |
| Site | `evidence/` | Pages over the marts | `gold` dimensions, facts, and marts |
| Infra | `infra/` | The box, Cloudflare, systemd units | none |

Metric, filter, and cleaning functions do no I/O and read no clock. `GUFIME_TARGET` picks `duckdb` (local default) or `postgres`; `GUFIME_FILES_ROOT`, `GUFIME_PG_DSN`, and `GUFIME_DUCKDB_PATH` override paths.

## 2. Data flow

```
Dagster on the box, nightly schedule 03:00 America/Chicago
  catalog          → bronze.catalog, bronze.watermark, raw.raw_works, bronze.ingest_audit
   └─ gate sensor (new_count > 0) launches downstream_job:
        texts           → /files/gufime/bronze/texts/, watermark
        stripped        → /files/gufime/silver/corpus/, bronze.strip_audit
        measures        → raw.raw_measurements, raw.raw_vocab
        dbt_models      → gold.*  (each dbt node a lineage asset)
        postgres_backup → R2 gufime-backup/postgres/gufime.dump
        corpus_backup   → R2 gufime-backup/corpus/
        site            → npm run sources, build, wrangler pages deploy → gufime.com
```

`catalog.main()` returns `new_count`, New plus Changed Works, as asset metadata; the gate reads it. A quiet night runs nothing past `catalog`. *Materialize all* in the UI is the manual rebuild. The `failure_alert` sensor emails through Cloudflare Email Sending on any run failure. Python assets import and call `main()`; dbt, Evidence, and backups shell out. Manually uploaded works live in `/files/gufime/bronze/self/` with a `_manifest.csv`; a changed `loaded_at` re-measures one.

## 3. Change detection

- `bronze.watermark` holds `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New:** an in-scope ID absent from the watermark. **Changed:** its catalog row hash differs. **Retry:** its last attempt failed.
- **Status:** `ingested`, `failed`, or `copyrighted`. `copyrighted` is terminal and set when a text carries PG's copyrighted-donation header.
- The diff runs over the in-scope subset only. Every run writes an `ingest_audit` row.
- **In scope:** English, `Type = Text`, and science fiction, fantasy, or horror by subject and bookshelf keywords. `genre` is exclusive; a work matching several is `Undetermined`. `is_translation`, `is_juvenile`, `is_play`, and `is_poetry` ride along on `stg_works`.

## 4. Dimensional model

```
sources (raw) → stg_* (views) → int_* (views) → dim_* / fact_* (tables) → mart_* (tables)
```

`int_` models may also read dimensions; marts may read other marts.

| Table | Grain and notes |
|---|---|
| `dim_author` | One author; `is_self` marks the CEO's row and chosen comparisons; birth and death dates |
| `dim_work` | One measured work; `ingested_at` is `min(loaded_at)` of its measurements; inner-joins measurements |
| `dim_metric` | One metric concept, from `seed_metrics`; display, unit, and additivity |
| `dim_date` | One day, 1970 to 2035 |
| `fact_style_measurement` | Work × series |
| `fact_vocab_overlap` | Author pair, top-N vocabulary Jaccard |
| `mart_style_long` | Work × series, for charts |
| `mart_work` | Work, for listings and the Excess ranking |
| `mart_author` | Author, for rollups |
| `snap_dim_work` | SCD2 snapshot of `dim_work` |
| `dbt_run_log` | One row per node per run, from `on-run-end` |

Every model compiles on DuckDB and Postgres. Every model full-rebuilds. `raw_works` freshness errors after 24 hours; measurement tables are exempt. Tests cover keys, relationships, accepted values, and 14 metric concepts per work.

## 5. Measurement

`strip.py` cuts PG boilerplate at the earliest end marker of either era and normalizes quotes. `measure.py` parses with spaCy in chunks under its maximum length. `lexicons.py`, `vocab.py`, and `stylometrics.py` hold one function per metric, each returning a dict of series. **15 metric concepts → 63 series.**

| Category | Metrics |
|---|---|
| Lexical | mean word length, Yule's K, archaic-word rate, Honoré's R, function-word frequency (40 words) |
| Syntactic | mean sentence length, sentence-length stdev, mean parse-tree depth, sentence-type mix |
| Mechanical | punctuation frequency, contraction rate |
| Structural | dialogue:narration ratio, adjective density, adverb density |
| Distinctive | Jaccard vocabulary overlap, computed in dbt |

## 6. Storage

Files under `/files/gufime/` (`bronze/texts/`, `bronze/catalog/`, `bronze/self/`, `silver/corpus/`). Postgres database `gufime` with schemas `bronze`, `raw`, `gold`, and `dagster`, on the unix socket with peer auth. Local development uses `dbt/warehouse.duckdb` and `data/files/`.

## 7. Site

Evidence extracts data at build time; the deployed SPA never queries a database. Each query selects from the mart at its own grain. Postbuild scripts `cdn-wasm.js` and `copy-404.js` handle the Pages file-size cap and 404s.

## 8. Security

No database password exists. Postgres listens on the local socket only; the Dagster UI sits behind a Cloudflare Tunnel and Access. Credentials and their homes are in [deploy.md](deploy.md).
