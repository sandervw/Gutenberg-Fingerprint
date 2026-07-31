# `gutenberg-fingerprint` — A Fabric CDC Stylometrics Pipeline

The outline this project was built against, updated to what actually got built. A nightly, change-data-capturing pipeline that watches the Project Gutenberg science-fiction and fantasy catalog, lands new and corrected books in a Fabric Lakehouse, extracts stylometrics, and rebuilds dbt → Evidence.

**Note:** any dbt change has to reach the `fabric-dbt` branch. Fabric's dbt job reads a branch root only, so `dbt/` is republished there by CI; monthly service updates have broken this path before, so check it after a Fabric release.

---

## 1. Architecture (Medallion + Orchestration)

```
        ┌──────────────── Logic App: nightly bracket ─────────────────┐
        │                                                             │
┌───────▼────────┐   ┌───────────────┐   ┌──────────┐   ┌──────────┐  │
│ RESUME F2      │ → │ pl_nightly    │ → │ CDC gate │ → │ ingest + │  │
│ capacity       │   │ (Data Factory)│   │ (If Cond)│   │ measure  │  │
└────────────────┘   └───────────────┘   └──────────┘   └────┬─────┘  │
                                                             │        │
   ┌──────────────┐     ┌──────────────┐     ┌───────────┐   │        │
   │ lh_bronze    │  →  │ lh_silver    │  →  │ wh_gold   │ ←─┘        │
   │ catalog,     │     │ corpus .md,  │     │ dbt star  │            │
   │ texts,       │     │ tidy metric  │     │ schema +  │            │
   │ watermark    │     │ rows         │     │ marts     │            │
   └──────────────┘     └──────────────┘     └─────┬─────┘            │
                                                   │                  │
                        ┌──────────────────────────▼───────────────┐  │
                        │ export_gold.py → parquet in OneLake      │  │
                        └──────────────────────┬───────────────────┘  │
                                               │                      │
   ┌──────────────┐     ┌─────────────────────▼────────────────┐   ┌──▼─────┐
   │ gufime.com   │  ←  │ Cloudflare Pages build               │ → │ PAUSE  │
   │ (static)     │     │ (deploy hook; Evidence + DuckDB)     │   │ F2     │
   └──────────────┘     └──────────────────────────────────────┘   └────────┘
```

- **Orchestrator:** a Fabric Data Factory pipeline, `pl_nightly`, sequencing catalog refresh → CDC gate → conditional extract → SQL endpoint refresh → dbt → parquet export. The gate is an If Condition on `filter.py`'s exit value; on a no-op night the extract branch is skipped and dbt still runs against unchanged silver.
- **Bracket:** a single Logic App (`la-gutenberg-nightly`, in `infra/pipeline-automation.bicep`) resumes the capacity, runs the pipeline, fires the Cloudflare deploy hook, polls the Pages build, then suspends. Suspend runs regardless of outcome, so a failure never leaves the meter running.
- **CDC notebooks (Python kernel, not Spark):** `catalog_ingest.py` writes the catalog photo; `filter.py` diffs the in-scope subset against the watermark and emits the gate count. Catalog-wide diffs are meaningless — the ~78k out-of-scope books never enter the watermark, so they read as new forever.
- **Stylometrics notebooks (Python kernel):** the extractor logic from the previous project, re-homed and split into tunables (`lexicons.py`, `vocab.py`, `stylometrics.py`, `clean.py`) plus workflow steps. Same tidy `(work, metric, value)` output into silver Delta tables. 15 metric concepts fan out to 63 measured series.
- **Warehouse + dbt:** dbt models materialize gold marts in a Fabric **Warehouse**, reading silver via the Lakehouse's SQL analytics endpoint (three-part naming — the endpoint is read-only, which is why models must land in a Warehouse). Fabric's native **dbt job** item runs them.
- **BI:** Evidence. See §6 for the complication.

### Run order (step → what it loads → what it needs first)

```
catalog_ingest.py ──> bronze: catalog, watermark, Files/catalog/
        │
        ▼
filter.py ──────────> silver: raw_works, bronze: ingest_audit    needs: catalog, watermark
                      exits with the CDC gate count
        │
        ▼  (If Condition: gate count > 0, else skip to the export)
text_ingest.py ─────> bronze: Files/texts/, watermark            needs: raw_works, watermark
        │
        ▼
strip.py ───────────> silver: Files/corpus/, bronze: strip_audit needs: raw_works, Files/texts, Files/self
        │
        ▼
measure.py ─────────> silver: raw_measurements, raw_vocab        needs: Files/corpus, watermark, Files/self manifest
        │
        ▼
refresh_silver ─────> forces the Lakehouse SQL endpoint to catch up
        │
        ▼
dbt build ──────────> wh_gold: stg_* → int_* → dim_*/fact_* → mart_*
        │
        ▼
export_gold.py ─────> lh_silver: Files/exports/*.parquet         needs: wh_gold base tables
        │
        ▼
deploy hook ────────> Cloudflare Pages build → gufime.com        needs: the parquet exports
```

(one-off side input: `scripts/upload_self_corpus.py` → bronze `Files/self/` + `_manifest.csv`, stamping `loaded_at` in the seed so `measure.py` re-parses only re-uploaded manual works)

---

## 2. CDC Design

**Official catalog feed:** `pg_catalog.csv` (zipped), regenerated daily by PG.

**The mechanics:**

- A `watermark` Delta table: `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New book** = ID in catalog, not in watermark. **Changed book** = ID present but catalog row hash differs (PG issues corrections to old texts). **Retry** = last attempt failed.
- Downloads: plain-text format only, rate-limited, capped per run, from PG's mirrors.
- Every run writes an **ingestion audit row**: run timestamp, books checked, new, changed, failed.

**Corpus filter** (applied at CDC time, not downstream): English, `Type = Text`, science-fiction and fantasy via subject and bookshelf keyword match. Flags (`is_translation`, `is_juvenile`, `is_play`, `is_poetry`) ride along as fields on `stg_works` and are filtered at query time in Evidence.

---

## 3. Changes in the Dimensional Model

The fact constellation from the previous project survives intact. Additions, not rewrites:

| Table                    | Change                                                                                                                                                                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_author`             | Built from catalog data. `is_self = true` on my own row and on select authors                                                                                                                                                         |
| `dim_work`               | Adds `gutenberg_id`, `download_count`, `subjects`, `ingested_at` (`min(loaded_at)` over the work's measurement rows, so rebuilds reproduce it). Full rebuild; inner join to measurements keeps unmeasured catalog rows out |
| `fact_style_measurement` | Full rebuild, not incremental. Rebuilding on an F2 costs seconds, and works withdrawn from the catalog have to disappear from the fact rather than linger                                                                             |
| `fact_vocab_overlap`     | Author-pair grain, top-N vocab. Full rebuild, same reasoning                                                                                                                                                                          |
| `snap_dim_work` *(new)*  | SCD2 snapshot, check strategy on all columns — PG corrections change word counts, so history gets captured                                                                                                                            |
| `dbt_run_log` *(new)*    | One row per dbt node per run, written by an `on-run-end` hook                                                                                                                                                                         |

Two planned tables were dropped: `fact_ingestion_run` and `dim_date`. Audit rows stay in bronze `ingest_audit`, dbt's own run history lands in `dbt_run_log`, and the site surfaces freshness as `max(ingested_at)` on the index. A modeled pipeline-history page is worth revisiting only if the run log gets read often enough to justify the grain.

---

## 4. dbt Concepts

The previous project's checklist was modeling fundamentals. This one is production operation:

- [ ] **Incremental models** — none. Every dim/fact rebuilds in seconds on an F2, and `ingested_at` comes from the data rather than a run clock
- [x] **Source freshness** — `raw_works` is the heartbeat at `error_after: 24 hours`; the measurement tables are exempt, because a quiet night leaves them untouched
- [x] **Snapshots** — SCD2 on `dim_work`
- [x] **dbt job in Fabric** — the managed runtime, its adapter versions, its preview limitations
- [x] **Environment split** — a `duckdb` dev target and a `fabric` prod target from one codebase
- [ ] **State-aware runs** — `dbt build --select state:modified+` needs a prior manifest, and the Fabric dbt job has no artifact caching. Left undone deliberately
- [x] **On-run-end hooks** — `log_run_results` writes run metadata to `dbt_run_log`, with a T-SQL branch because Fabric has no `CREATE TABLE IF NOT EXISTS`

---

## 5. FinOps

The nightly job means the capacity must wake and sleep on its own. There is no built-in Fabric auto-pause schedule.

1. **Resume:** the Logic App POSTs to the capacity's `/resume` management endpoint on schedule, with a managed identity holding a custom role scoped to four capacity actions on that one resource.
2. **Run:** the Data Factory pipeline works. A no-op night is minutes; an ingest night 30–45.
3. **Pause:** the Logic App suspends after the Pages build reports back — not before (§6).

Failure alerting: a `RunsFailed` alert on the Logic App, plus `infra/budget.bicep` for spend alerts by email.

**Cost math (F2 PAYG, US regions, ~$0.18/CU/hr):**

| Item                                       | Estimate               |
| ------------------------------------------ | ---------------------- |
| Backfill (one-time)                        | $2–5                   |
| Nightly runs (~30 min avg × 30 days on F2) | $5–10/mo               |
| OneLake storage (~2 GB text + Delta)       | pennies ($0.023/GB/mo) |
| Cloudflare Pages nightly builds            | free tier covers it    |
| **Left running 24/7 by accident**          | **~$263/mo**           |

The initial build ran on the 60-day trial capacity. The bracket could not be built there: pause/resume are ARM operations on `Microsoft.Fabric/capacities`, and trial capacity is not an ARM resource. Paid F2 first, then the bracket against it.

---

## 6. The Evidence Wrinkle

Evidence extracts data at **build time** into a static site — the deployed Cloudflare Pages site never touches the Warehouse. Two consequences:

1. **Auth:** Fabric Warehouse refuses SQL auth; Entra ID only. So `export_gold.py` writes the gold marts to parquet in OneLake and `evidence/scripts/fetch-sources.js` pulls them over the OneLake DFS REST API with a service principal. DuckDB then runs `:memory:` against local parquet.
2. **Sequencing:** the deploy hook is a unique unauthenticated URL, so it's a secret. The Logic App holds the suspend until the Pages build reports success; pausing early kills the OneLake read mid-build.

Three postbuild scripts work around Cloudflare Pages limits on file size, deployment file count, and 404 handling.

---

## 7. Constraints & Gotchas

1. **PG politeness is non-negotiable.** Official feeds for the diff, rate-limited downloads, cache everything.
2. **Boilerplate stripping is the biggest data-quality fight.** Regenerated old files keep an ancient end-marker inside the modern `*** END OF ...` span, so the cut is taken at the earliest marker of either era. Cleaning also normalizes quotes to doubles.
3. **T-SQL surface:** `dbt_utils` cross-db macros, standard types, adapter dispatch where no portable SQL exists.
4. **F2 is small.** One notebook at a time, Python kernel, sequential pipeline steps, spaCy parsing in chunks because novels blow past its max length.
5. **Preview features move.** The Fabric dbt job is preview; the Lakehouse dbt adapter story keeps shifting.

---

## 8. Phased Plan

### (DONE) Phase 1 — Foundation (wk 1)
Trial capacity, workspace, Lakehouse + Warehouse. Budget alert. Port the dbt repo, add the `fabric` target, `dbt debug` green against the Warehouse. **Done when:** existing marts build in Fabric from manually loaded sample data.

### (DONE) Phase 2 — Backfill (wk 2–3)
Catalog ingestion notebook, corpus filter, boilerplate stripper, watermark table. Backfill the full corpus. Stylometrics notebook over it. **Done when:** bronze/silver populated, audit table records the backfill.

### (DONE) Phase 3 — Incremental dbt (wk 3–4)
`dim_work`, snapshots, source freshness, the expanded tests. **Done when:** a second run with a hand-injected "new book" flows through end-to-end.

### (DONE) Phase 4 — Orchestration + FinOps (wk 4–5)
Data Factory pipeline, resume/pause bracket, nightly schedule, failure alerting. Workspace items are source-controlled too: `fabric/` holds the item definitions and `scripts/deploy_fabric.py` publishes them with `fabric-cicd`.

### (DONE) Phase 5 — Serve + Polish (wk 5–6)
Site freshness surfaced from `ingested_at`, README, repo public. **Done when:** a hiring manager can read the repo and a stranger can browse the site.

---

## 9. Next Phase — Off Microsoft

The enterprise tooling costs more time in workarounds than it returns at this scale. Every Fabric/Azure piece has a smaller replacement that does the same job for roughly nothing.

**The Microsoft surface to remove:**
- 10 notebooks (re-convert back to simple python modules)
- `lh_bronze` + `lh_silver` + `wh_gold` (a simple cloud-storage solution, with folder-based file storage, and schema/database-based table storage?)
- `pl_nightly` - the fabric data factory pipeline
- the Logic App and `infra/*.bicep`
- `scripts/deploy_fabric.py`
- `.github/workflows/sync-fabric-dbt.yml`.

### Target stack

| Job              | Now                                           | Next                                                  |
| ---------------- | --------------------------------------------- | ----------------------------------------------------- |
| Orchestration    | Data Factory `pl_nightly` + Logic App bracket | GitHub Actions `nightly.yml`, each step `ssh` the box |
| Compute          | Fabric notebooks on an F2 capacity            | OVH VPS; plain Python modules in `python/`            |
| Bronze/silver    | OneLake Delta tables + Files                  | Box disk `/files/gufime/` + Postgres `bronze`/`raw`   |
| Gold warehouse   | `wh_gold` (Fabric Warehouse, T-SQL)           | Postgres `main` on the box                            |
| dbt runtime      | Fabric dbt job off `fabric-dbt`               | `uv run dbt build` on the box (`dbt-postgres`)        |
| Deploy + serving | Deploy hook, capacity held open               | Evidence Postgres source; `wrangler pages deploy`     |
| Infra as code    | Bicep + `fabric-cicd`                         | OpenTofu (`infra/tofu/`)                              |

**The goal is to maintain two targets, `duckdb` (dev) and `postgres` (prod)** - the project must continue to represent enterprise-grade architecture, but without the complexity introduced by fabric/azure's Lockin architecture.

**Status:** Phases 0-2 of `docs/Off-Microsoft-Plan.md` are done. The VPS is live, the notebooks are dual-target modules behind `python/helpers/storage.py`, and all Fabric state is migrated to the box and verified. The deployed Fabric items keep the nightly running until Phase 6; the repo module sources run as `uv run python -m python.workflow.<step>`.

**Done when:** a nightly run completes end to end with no Azure subscription attached to the project, and the site shows the same numbers.
