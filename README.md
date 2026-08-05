# Gutenberg Fingerprint

**Live site: [gufime.com](https://gufime.com/)**

A nightly change-data-capture pipeline that watches the Project Gutenberg catalog, downloads the English science-fiction and fantasy corpus, measures 15 stylometric properties of every book, and publishes the result as an SPA analytics site. Every published number is a **z-score**.

Runs on one ~$5/month OVH VPS ("the box"): Postgres, plain Python, dbt Core, and Evidence.dev, orchestrated by GitHub Actions, published to Cloudflare Pages.

---

## Architecture

```
GitHub Actions nightly.yml (cron 08:00 UTC, workflow_dispatch) — every step is `ssh box '...'`
  ├─ git reset --hard origin/main    (sync /code/gufime)
  ├─ catalog_ingest.py           → postgres bronze.catalog, bronze.watermark
  ├─ filter.py                   → postgres raw.raw_works, bronze.ingest_audit
  │                                [step output: new_count]
  └─ if new_count != 0 (the "CDC gate"):
       ├─ text_ingest.py         → /files/gufime/bronze/texts/, watermark
       ├─ strip.py               → /files/gufime/silver/corpus/, bronze.strip_audit
       ├─ measure.py             → postgres raw.raw_measurements, raw.raw_vocab
       ├─ dbt deps && dbt build  → postgres gold.*
       ├─ npm run sources && npm run build
       │    └─ wrangler pages deploy → gufime.com
       └─ backup.py corpus       → R2 gufime-backup/corpus/
  backup.py pg                   → R2 gufime-backup/pg/gufime.dump  (every night)
```

GitHub Actions holds the schedule, the CDC gate, the SSH key, and the logs; the box executes. Files live on the box's disk under `/files/gufime/`, tables in Postgres (schemas `bronze`, `raw`, `gold`), listening on the unix socket only with peer auth. When there are no new fiction/sci-fi works in the catalog, the run stops after `filter.py`.

**Change detection.** A `bronze.watermark` table keyed on `gutenberg_id` marks a book new when its ID is absent, changed when its catalog row hash differs, and retried when it last failed. The diff runs against the **in-scope subset only**; the ~78,000 out-of-scope books never enter the watermark.

## Measurement

Cleaning and measurement are plain Python modules in `python/workflow/`, with tunables in `python/helpers/`.

- `strip.py` cuts the PG boilerplate.
- `measure.py` parses with spaCy, chunking text to stay under spaCy's max length. Only new/changed works re-parse.
- `lexicons.py`, `vocab.py`, and `stylometrics.py` hold the tunable parts, one function per metric returning a dict of series.

**15 metric concepts → 63 measured series.** Three concepts fan out, function-word frequency alone tracking 40 words individually.

| Category    | Metrics                                                                               |
| ----------- | ------------------------------------------------------------------------------------- |
| Lexical     | mean word length, Yule's K, archaic-word rate, Honoré's R, function-word frequency    |
| Syntactic   | mean sentence length, sentence-length stdev, mean parse-tree depth, sentence-type mix |
| Mechanical  | punctuation frequency, contraction rate                                               |
| Structural  | dialogue:narration ratio, adjective density, adverb density                           |
| Distinctive | Jaccard vocabulary overlap (author-pair grain, computed dbt-side)                     |

## The dbt layer

```
sources (raw)  →  stg_*  →  int_*  →  dim_*/fact_*  →  mart_*
                  views     views     tables           tables
```

A fact constellation: `fact_style_measurement` at work × series grain, `fact_vocab_overlap` at author-pair grain, sharing conformed `dim_work`, `dim_author`, and `dim_metric`. The marts on top are split by the grain the charts read at: `mart_style_long` (work × series), `mart_work` (work-grain listings, the outlier ranking), `mart_author` (author-grain rollups). Every Evidence query selects from the table already at its own grain.

- **Portability.** Every model compiles against both DuckDB (local dev) and Postgres (prod) from one codebase.
- **Derived stamps.** `dim_work.ingested_at` is `min(loaded_at)` over the work's measurement rows. The dimension inner-joins measurements, keeping unmeasured catalog rows out.
- **Source freshness.** `raw_works` is the heartbeat at `error_after: 24 hours`; measurement tables are exempt.
- **Snapshots.** SCD2 on `dim_work`.
- **Audit hook.** `on-run-end` writes one row per node into `gold.dbt_run_log`.
- **Tests.** Keys, relationships, and accepted values, plus asserting every work carries 14 metric concepts.

## The site

Evidence extracts data at build time; the deployed SPA never queries a database. The build runs on the box, where `@evidence-dev/postgres` reads the `gold` marts over the unix socket with peer auth. `wrangler pages deploy` ships the static build to Cloudflare Pages.

Postbuild scripts work around Cloudflare Pages' file-size cap and 404 handling. Styling mirrors [wordleaves.com](https://wordleaves.com).

## Cost

| Item                                  | Estimate  |
| ------------------------------------- | --------- |
| OVH VPS-1 (2 vCore, 4 GB, 40 GB NVMe) | ~$5/mo    |
| GitHub Actions (public repo)          | free      |
| Cloudflare Pages builds               | free tier |

Two credentials run the night: an SSH private key in Actions secrets, and a Cloudflare API token on the box scoped to Pages.

## Repo layout

```
python/      pipeline: workflow steps + helpers, storage seam (storage.py)
dbt/         dbt Core project (models, macros, snapshots, tests)
evidence/    Evidence.dev site + build scripts
infra/tofu/  OpenTofu: OVH VPS + Cloudflare DNS, provision.sh
scripts/     local dev loader
docs/        project outline, analysis write-ups, reference notes
```

## Running it locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node 24.

```bash
uv sync
uv run python scripts/load_local_raw_tables.py  # seed dbt/warehouse.duckdb

cd dbt
uv run dbt deps
uv run dbt build          # duckdb target by default

cd ../evidence
npm install
npm run dev               # serves the extraction cached in evidence/data/
```

Pipeline steps also run locally against DuckDB: `uv run python -m python.workflow.<step>`, files under `data/files/`. `GUFIME_TARGET=postgres` switches a step to the box's stack. `npm run sources` needs the box's Postgres socket; fresh extractions run there.
