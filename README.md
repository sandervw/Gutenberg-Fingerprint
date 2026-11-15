# Gutenberg Fingerprint

**Live site: [gufime.com](https://gufime.com/)**

A nightly change-data-capture pipeline that watches the Project Gutenberg catalog, downloads the English science-fiction, fantasy, and horror corpus, measures 15 stylometric metrics of every work, and publishes the result as an SPA analytics site. Every published number is a **z-score**.

Runs on one ~$5/month OVH VPS ("the box"): Postgres, plain Python, dbt Core, and Evidence.dev, orchestrated by **Dagster OSS**, published to Cloudflare.

---

## Architecture

```
Dagster on the box — nightly schedule 03:00 America/Chicago
  catalog                          → postgres bronze.*, raw.raw_works   (prints new_count)
   └─ gate sensor (new_count > 0) launches one linear chain:
        texts          → /files/gufime/bronze/texts/
        stripped       → /files/gufime/silver/corpus/
        measures       → postgres raw.raw_measurements, raw.raw_vocab
        dbt_models     → postgres gold.*   (each dbt node a lineage asset)
        postgres_backup → R2 gufime-backup/postgres/gufime.dump
        corpus_backup  → R2 gufime-backup/corpus/
        site           → npm build + wrangler pages deploy → gufime.com
```

Dagster OSS on the box holds the schedule, the CDC gate, and the run logs (Postgres `dagster` schema). The `nightly` schedule materializes `catalog`; a `gate` asset sensor reads its `new_count` and launches the downstream chain only when New or Changed works exist. Push to `main` triggers a GitHub Actions deploy hook (`deploy.yml`) that syncs the box's checkout and restarts Dagster. The Dagster UI is served at [dagster.gufime.com](https://dagster.gufime.com) behind a Cloudflare Tunnel + Access. Files live under `/files/gufime/`, tables in Postgres (schemas `bronze`, `raw`, `gold`) over the unix socket with peer auth.

**Change detection.** A `bronze.watermark` table keyed on `gutenberg_id` marks a work New when its ID is absent, changed when its catalog row hash differs, and retried when it last failed. `text_ingest` sniffs each fetched text for PG's copyrighted-donation header and stamps those with a terminal `copyrighted` status that is never retried. The diff runs against the **in-scope subset only**.

## Measurement

Cleaning and measurement are plain Python modules in `python/workflow/`, with tunables in `python/helpers/`.

- `strip.py` cuts the PG boilerplate.
- `measure.py` parses with spaCy in chunks under its max length. Only new/changed works re-parse.
- `lexicons.py`, `vocab.py`, and `stylometrics.py` hold the tunable parts, one function per metric returning a dict of series.

**15 metric concepts → 63 measured series.** Three concepts fan out; function-word frequency tracks 40 words.

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

A fact constellation: `fact_style_measurement` at work × series grain, `fact_vocab_overlap` at author-pair grain, sharing conformed `dim_work`, `dim_author`, `dim_metric`, and `dim_date` (a calendar dimension for load-date FKs). The marts split by chart grain: `mart_style_long` (work × series), `mart_work` (work-grain listings, the Excess ranking), `mart_author` (author-grain rollups). Each Evidence query selects from the mart at its grain.

- **Portability.** Every model compiles against both DuckDB (local dev) and Postgres (prod) from one codebase.
- **Derived stamps.** `dim_work.ingested_at` is `min(loaded_at)` over the work's measurement rows. The dimension inner-joins measurements.
- **Source freshness.** `raw_works` uses `error_after: 24 hours`; measurement tables are exempt.
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
| GitHub Actions deploy hook            | free      |
| Cloudflare Pages + Tunnel + Access    | free tier |

Credentials: an SSH key in Actions secrets (the deploy hook), a Cloudflare API token on the box (Pages + R2), and a Cloudflare Tunnel token `cloudflared` uses for the UI.

## Repo layout

```
python/      pipeline: workflow steps + helpers, storage seam (storage.py)
dbt/         dbt Core project (models, macros, snapshots, tests)
evidence/    Evidence.dev site + build scripts
infra/tofu/  OpenTofu: OVH VPS + Cloudflare, provision.sh + Dagster/tunnel services
docs/        vision, architecture, deploys, glossary, use cases, reference notes
.claude/     agents, hooks, and skills for the agent workflow
```

## Running it locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node 24.

```bash
uv sync
uv run python -m python.workflow.catalog_ingest  # seed bronze.catalog + raw.raw_works

cd dbt
uv run dbt deps
uv run dbt build          # duckdb target by default

cd ../evidence
npm install
npm run dev               # serves the extraction cached in evidence/data/
```

Pipeline steps also run locally against DuckDB: `uv run python -m python.workflow.<step>`, files under `data/files/`. `GUFIME_TARGET=postgres` switches a step to the box's stack. `npm run sources` needs the box's Postgres socket; fresh extractions run there.

## How it's built

Agent-built through pull requests. A CTO agent (Claude Code) plans, builds, reviews, and merges; `CLAUDE.md` is its manual and the `handoff` skill its running notes. Every code PR passes simplicity and architecture reviewers, plus a security reviewer for sensitive paths, and a hook blocks merging until they pass on the latest commit. CI runs the simple-code checks, `dbt parse` on both targets, and a Dagster definitions check.
