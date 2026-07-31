# Gutenberg Fingerprint

**Live site: [gufime.com](https://gufime.com/)**

A nightly change-data-capture pipeline that watches the Project Gutenberg catalog, downloads the English science-fiction and fantasy corpus, measures 15 stylometric properties of every book, and publishes the result as a static analytics site.

Every number is a **z-score**, so unrelated metrics sit on one scale and a book like *The Night Land* can be ranked the strangest text in the corpus, then explained series by series.

Built on Microsoft Fabric (Lakehouse + Warehouse + Data Factory), dbt Core, and Evidence.dev, wrapped in a resume/pause bracket so the capacity is billed only while it works.

---

## Architecture

```
        ┌───────────────────── Logic App: nightly bracket ─────────────────────┐
        │                                                                      │
┌───────▼────────┐   ┌─────────────────┐   ┌──────────────┐   ┌─────────────┐  │
│ RESUME F2      │ → │ pl_nightly      │ → │ CDC gate     │ → │ ingest +    │  │
│ capacity       │   │ (Data Factory)  │   │ (If Cond.)   │   │ measure     │  │
└────────────────┘   └─────────────────┘   └──────────────┘   └──────┬──────┘  │
                                                                     │         │
   ┌──────────────┐      ┌──────────────┐      ┌───────────────┐     │         │
   │ lh_bronze    │      │ lh_silver    │      │ wh_gold       │ ←───┘         │
   │ catalog,     │  →   │ corpus .md,  │  →   │ dbt star      │               │
   │ texts,       │      │ tidy metric  │      │ schema +      │               │
   │ watermark    │      │ rows         │      │ marts         │               │
   └──────────────┘      └──────────────┘      └───────┬───────┘               │
                                                       │                       │
                              ┌────────────────────────▼────────────┐          │
                              │ export_gold.py → parquet in OneLake │          │
                              └────────────────────┬────────────────┘          │
                                                   │                           │
   ┌───────────────┐      ┌────────────────────────▼────────────┐   ┌────────┐ │
   │ gufime.com    │  ←   │ Cloudflare Pages build              │ → │ PAUSE  │─┘
   │ (static)      │      │ (deploy hook; Evidence + DuckDB)    │   │ F2     │
   └───────────────┘      └─────────────────────────────────────┘   └────────┘
```

A single Logic App (`infra/pipeline-automation.bicep`) owns the loop: resume the capacity, run the pipeline, fire the Cloudflare deploy hook, poll the Pages build, then suspend. Suspend runs regardless of outcome, so a failure never leaves the meter running.

## The nightly run

`pl_nightly` sequences ten steps. The CDC gate means a quiet night costs minutes, not an hour.

| Step | Notebook / activity    | Reads                      | Writes                                                |
| ---- | ---------------------- | -------------------------- | ----------------------------------------------------- |
| 1    | `catalog_ingest.py`    | PG's `pg_catalog.csv` feed | bronze `catalog`, `watermark`                         |
| 2    | `filter.py`            | `catalog`, `watermark`     | silver `raw_works`; **exits with the CDC gate count** |
| 3    | *If Condition*         | `filter.py` exit value > 0 | skips steps 4-10 on a no-op night                     |
| 4    | `text_ingest.py`       | `raw_works`                | bronze `Files/texts/`, rate-limited from PG's mirror  |
| 5    | `strip.py`             | `Files/texts/`             | silver `Files/corpus/`                                |
| 6    | `measure.py`           | `Files/corpus/`            | silver `raw_measurements`, `raw_vocab`                |
| 7    | `refresh_silver`       | -                          | forces the Lakehouse SQL endpoint to catch up         |
| 8    | `dbt` (Fabric dbt job) | silver                     | `wh_gold` star schema + marts                         |
| 9    | `export_gold.py`       | `wh_gold`                  | `lh_silver/Files/exports/*.parquet`                   |
| 10   | deploy hook → Pages    | those parquet files        | the published site                                    |

**Change detection.** A `watermark` Delta table keyed on `gutenberg_id` marks a book new when its ID is absent, changed when its catalog row hash differs, and retried when it last failed. The diff runs against the **in-scope subset only**: the ~78,000 out-of-scope books never enter the watermark, so a catalog-wide diff would read as "everything is new" forever.

## Measurement

Cleaning and measurement run in Python notebooks on a plain Python kernel, since an F2 has no Spark headroom.

- `strip.py` cuts the PG boilerplate. Regenerated old files keep an ancient end-marker inside the modern `*** END OF ...` span, so the cut is taken at the earliest marker of either era.
- `measure.py` parses with spaCy `en_core_web_sm` in chunks, because novels blow past spaCy's max length. Only new works, and works whose source changed, re-parse.
- `lexicons.py`, `vocab.py`, and `stylometrics.py` hold the tunable parts, one function per metric returning a dict so a single metric can emit many series.

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
sources (silver)  →  stg_*  →  int_*  →  dim_*/fact_*  →  mart_*
                     views     views     tables           tables
```

A fact constellation: `fact_style_measurement` at work × series grain, `fact_vocab_overlap` at author-pair grain, sharing conformed `dim_work`, `dim_author`, and `dim_metric`. The marts on top are split by the grain the charts read at: `mart_style_long` is the measurement OBT kept long at work × series, `mart_work` serves work-grain listings and the outlier ranking, `mart_author` serves author-grain rollups. Every Evidence query selects from the table already at its own grain, rather than deduplicating the OBT down to one.

- **Portability.** Every model compiles against both DuckDB (local dev) and Fabric T-SQL (prod) from one codebase, with macros dispatching per adapter where no portable SQL exists.
- **Derived stamps.** `dim_work.ingested_at` is `min(loaded_at)` over the work's measurement rows, so a full rebuild reproduces it. The dimension inner-joins measurements, so unmeasured catalog rows stay out.
- **Source freshness.** `raw_works` is the heartbeat at `error_after: 24 hours`. Measurement tables are exempt, because a quiet night leaves them untouched.
- **Snapshots.** SCD2 on `dim_work`, since PG corrections change word counts.
- **Audit hook.** `on-run-end` writes one row per node into `dbt_run_log`, with a T-SQL branch because Fabric has no `CREATE TABLE IF NOT EXISTS`.
- **Tests.** Keys, relationships, and accepted values, plus a singular test asserting every work carries all 14 per-work metric concepts.

## The site

Evidence extracts data at **build time**, which creates two problems.

1. **Auth.** Fabric Warehouse refuses SQL auth; Entra ID only. So `export_gold.py` writes the gold marts to parquet in OneLake, and `evidence/scripts/fetch-sources.js` pulls them over the OneLake DFS REST API. DuckDB runs `:memory:` against local parquet, so **the published site never touches the Warehouse**.
2. **Sequencing.** The Logic App holds the pause until the Pages build reports success. Pausing early would kill the OneLake read mid-build.

Three postbuild scripts work around Cloudflare Pages limits on file size, deployment file count, and 404 handling. Styling mirrors [wordleaves.com](https://wordleaves.com).

## Cost

An F2 capacity left running costs roughly **$263/month**. The bracket is the entire point.

| Item                                     | Estimate  |
| ---------------------------------------- | --------- |
| Backfill (one-time)                      | $2-5      |
| Nightly runs (~30 min avg × 30 days, F2) | $5-10/mo  |
| OneLake storage (~2 GB)                  | pennies   |
| Cloudflare Pages builds                  | free tier |

`infra/budget.bicep` deploys a budget with email alerts. `infra/pipeline-automation.bicep` adds an RBAC role scoped to the four capacity actions the bracket needs, plus a `RunsFailed` alert.

## Repo layout

```
dbt/         dbt Core project (models, macros, snapshots, tests)
evidence/    Evidence.dev site + build scripts
fabric/      Fabric item definitions: notebooks, pl_nightly, lakehouses,
             the dbt job item, and parameter.yml GUID parameterization
infra/       Bicep: capacity bracket, alerting, budget
scripts/     deploy_fabric.py, local dev loaders, corpus upload
docs/        project outline, analysis write-ups, reference notes
```

**Everything in `fabric/` deploys from source.** `scripts/deploy_fabric.py` publishes it with `fabric-cicd`, and `parameter.yml` maps every baked-in GUID to a variable, so the workspace can be retargeted without hand-editing definitions.

Fabric's dbt job builds a GitHub branch **from its root** with no folder-path option, so `.github/workflows/sync-fabric-dbt.yml` subtree-splits `dbt/` onto a `fabric-dbt` branch on every push to `main`.

## Running it locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node 24.

```bash
uv sync
uv run python scripts/load_local_raw_tables.py  # seed a local DuckDB

cd dbt
uv run dbt deps
uv run dbt build          # duckdb by default; --target fabric needs az login

cd ../evidence
npm install
npm run dev               # falls back to cached parquet without credentials
```
