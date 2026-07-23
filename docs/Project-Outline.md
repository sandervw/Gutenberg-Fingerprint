# `gutenberg-fingerprint` — A Fabric CDC Stylometrics Pipeline

A nightly, change-data-capturing pipeline that watches the Project Gutenberg fantasy catalog, lands new/updated books in a Fabric Lakehouse, extracts stylometrics, and rebuilds dbt → Evidence.

**NOTE TO SELF:** any dbt changes need to be reflected in the fabric-dbt branch (because, of course, Microsoft can't make a simple working service - it ahs to be some overly-ornate piece of fragile fucking garbage, which they then proceed to update monthly, breaking it more.)

---

## 1. Architecture (Medallion + Orchestration)

```
        ┌──────────────────────── nightly schedule ────────────────────────┐
        │                                                                  │
┌───────▼────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│ RESUME capacity│→ │ Pipeline (DF) │→ │ CDC notebook  │→ │ Extract     │  │
│ (Logic App /   │  │ orchestrator  │  │ diff catalog  │  │ stylometrics│  │
│  Automation)   │  │               │  │ vs watermark  │  │ notebook    │  │
└────────────────┘  └───────────────┘  └───────┬───────┘  └──────┬──────┘  │
                                               │                 │         │
                    ┌───────────┐   ┌──────────▼──────┐  ┌───────▼──────┐  │
                    │ Warehouse │ ← │ Lakehouse       │  │ Lakehouse    │  │
                    │ (dbt gold)│   │ bronze: texts + │  │ silver: tidy │  │
                    │           │   │ catalog Delta   │  │ metric rows  │  │
                    └─────┬─────┘   └─────────────────┘  └──────────────┘  │
                          │                                                │
                    ┌─────▼─────────┐   ┌──────────────┐   ┌────────────┐  │
                    │ dbt job       │ → │ Deploy hook  │ → │ PAUSE      │──┘
                    │ (Fabric-native│   │ → Cloudflare │   │ capacity   │
                    │  or CI-run)   │   │ Evidence     │   └─────▲──────┘
                    └───────────────┘   │ rebuild      │         │
                                        └──────┬───────┘   wait for build
                                               └─────────────────┘
```

- **Orchestrator:** a Fabric Data Factory pipeline on a nightly schedule. It sequences: catalog refresh → filter (CDC gate) → conditional extract → SQL endpoint refresh → dbt → BI rebuild → pause. The gate is an If Condition on `nb_filter`'s exit value; on a no-op night the extract branch is skipped and dbt still runs against unchanged silver.
- **CDC notebooks (Python kernel, not Spark):** `nb_catalog_ingest` writes the catalog photo; `nb_filter` diffs the fantasy subset against the watermark and emits the gate count. Catalog-wide diffs are meaningless — the ~78k non-fantasy books never enter the watermark, so they read as new forever.
- **Stylometrics notebook (Python kernel):** existing extractor logic, re-homed. Same tidy `(work, metric, value)` output — silver Delta tables.
- **Warehouse + dbt:** dbt models materialize gold marts in a Fabric **Warehouse**, reading silver via the Lakehouse's SQL analytics endpoint (three-part naming — the endpoint is read-only, which is why models must land in a Warehouse). Fabric has a native **dbt job** item (preview).
- **BI:** Evidence. See §6 for one complication.

### Run order (script → what it loads → what it needs first)

```
nb_catalog_ingest ──> bronze: catalog, watermark, Files/catalog/
        │
        ▼
nb_filter ──────────> silver: raw_works, bronze: ingest_audit    needs: catalog, watermark
                      exits with the CDC gate count
        │
        ▼
nb_text_ingest ─────> bronze: Files/texts/, watermark            needs: raw_works, watermark
        │
        ▼
nb_strip ───────────> silver: Files/corpus/, bronze: strip_audit needs: raw_works, Files/texts, Files/self
        │
        ▼
nb_measure ─────────> silver: raw_measurements, raw_vocab        needs: Files/corpus, watermark, Files/self manifest
        │
        ▼
dbt build ──────────> wh_gold: stg_* → dim_*/fact_* → mart_*     needs: raw_works, raw_measurements, raw_vocab
```

(one-off side input: `scripts/upload_self_corpus.py` → bronze `Files/self/` + `_manifest.csv`, stamping `loaded_at` in the seed so nb_measure re-parses only re-uploaded manual works)

---

## 2. CDC Design

**Official catalog feeds:**

- `pg_catalog.csv` (zipped)
- The RDF/XML dump, both regenerated daily by PG

**The CDC mechanics**:

- A `watermark` Delta table: `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New book** = ID in catalog, not in watermark. **Changed book** = ID present but catalog row hash differs (PG issues corrections to old texts)
- Downloads: plain-text format only, rate-limited, from PG's file hosts
- Every run writes an **ingestion audit row**: run timestamp, books checked, new, changed, failed

**Corpus filter** (apply at CDC time, not downstream): English, `Type = Text`, fantasy via subjects/bookshelves keyword match. Flags (`is_translation`, `is_juvenile`, `is_play`, `is_poetry`), surfaced as fields on `stg_works`, filtered at query time in Evidence

---

## 3. Changes in the Dimensional Model

The fact constellation survives intact. Additions, not rewrites:

| Table                        | Change                                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `dim_author`                 | Now built from catalog data. Keep `is_self = true` on your row, and for select authors                           |
| `dim_work`                   | Adds `gutenberg_id`, `download_count`, `subjects`, `ingested_at`                                                 |
| `fact_style_measurement`     | **Becomes incremental** — new works append; unchanged works don't recompute                                      |
| `fact_vocab_overlap`         | Author-level only, top-N vocab, computed **incrementally**: new authors × existing authors, never full recompute |
| `fact_ingestion_run` *(new)* | One row per nightly run, from the audit table. Grain: pipeline run                                               |
| `dim_date` *(new)*           | Time now exists in the model                                                                                     |

---

## 4. dbt Concepts

Last project's checklist was modeling fundamentals. This one is production operation:

- [ ] **Incremental models** — `is_incremental()`, `unique_key`, merge behavior on Fabric
- [ ] **Source freshness** — `dbt source freshness` against `ingested_at`; fail the run if the lakehouse is stale
- [ ] **Snapshots** — SCD2 on `dim_work` (PG corrections change word counts; capture history)
- [ ] **dbt job in Fabric** — the managed runtime, its adapter versions, its preview limitations (no build caching yet)
- [ ] **Environment split** — a `dev` target (DuckDB local) and a `fabric` prod target
- [ ] **State-aware runs** — `dbt build --select state:modified+` in CI (needs artifacts; note the Fabric preview gap)
- [ ] **On-run-end hooks** — write dbt run metadata back to the audit table

---

## 5. FinOps

The nightly job means the capacity *must* wake and sleep on its own. There is no built-in Fabric auto-pause schedule.

1. **Resume:** Logic App / Azure Automation runbook POSTs to the capacity's `/resume` management endpoint on schedule (managed identity, Contributor scoped to the capacity resource only).
2. **Run:** the Data Factory pipeline does its work. A no-op night is minutes; an ingest night maybe 30–45.
3. **Pause:** the *pipeline's last step* triggers suspend (web activity → Logic App → `/suspend`).

**Cost math (F2 PAYG, US regions, ~$0.18/CU/hr):**

| Item                                       | Estimate               |
| ------------------------------------------ | ---------------------- |
| Backfill (one-time)                        | $2–5                   |
| Nightly runs (~30 min avg × 30 days on F2) | $5–10/mo               |
| OneLake storage (~2 GB text + Delta)       | pennies ($0.023/GB/mo) |
| Cloudflare Pages nightly builds            | free tier covers it    |
| **Left running 24/7 by accident**          | **~$263/mo**           |

Do the initial build on the 60-day Fabric trial capacity. The bracket cannot be built there: pause/resume are ARM operations on `Microsoft.Fabric/capacities`, and trial capacity is not an ARM resource. Provision paid F2 first, then build the bracket against it.

---

## 6. The Evidence Wrinkle

Evidence extracts data at **build time** into a static site — the deployed Cloudflare Pages site never touches the Warehouse. Two consequences:

1. **Auth:** Fabric Warehouse refuses SQL auth; Entra ID only. Evidence's MSSQL connector supports service-principal auth — configure `azure-active-directory-service-principal-secret` via env vars in the build environment.
2. **Sequencing:** the Cloudflare build (triggered by a deploy-hook POST — each hook is a unique URL, no auth header, treat it as a secret) would normally run `npm run sources` against the Warehouse. `nb_export_gold` writes the gold marts to parquet in OneLake instead, and Evidence's DuckDB source reads those. The pipeline must hold the pause until the Cloudflare build finishes.

---

## 7. Constraints & Gotchas

1. **PG politeness is non-negotiable.** Official feeds for the diff, rate-limited downloads, cache everything.
2. **Boilerplate stripping is biggest data-quality fight.** Test-drive against 20 books from different decades. Extraction also needs to handle cleaning (take special care to use double quotes instead of single quotes in cleaned output texts).
3. **T-SQL surface:** same rules as before — `dbt_utils` cross-db macros, standard types, no engine-specific SQL.
4. **F2 is small.** One notebook at a time, Python kernel, sequential pipeline steps.
5. **Preview features move.** The Fabric dbt job is preview (no artifact caching yet); the Lakehouse dbt adapter story keeps shifting.

---

## 8. Phased Plan

### (DONE) Phase 1 — Foundation (wk 1)
Trial capacity, workspace, Lakehouse + Warehouse. Budget alert. Port the dbt repo, add the `fabric` target, `dbt debug` green against the Warehouse. **Done when:** existing marts build in Fabric from manually loaded sample data.

### (DONE) Phase 2 — Backfill (wk 2–3)
Catalog ingestion notebook, corpus filter, boilerplate stripper, watermark table. Backfill the full fantasy corpus. Stylometrics notebook over the corpus. **Done when:** bronze/silver populated, audit table records the backfill.

### (DONE) Phase 3 — Incremental dbt (wk 3–4)
Convert facts to incremental, add snapshots, source freshness, the expanded tests. **Done when:** a second run with a hand-injected "new book" flows through end-to-end and *only* the delta recomputes.

### (DONE) Phase 4 — Orchestration + FinOps (wk 4–5)
Data Factory pipeline, resume/pause bracket, nightly schedule — Logic App `la-gutenberg-nightly` (`infra/pipeline-automation.bicep`) runs the full loop and suspends. Failure alerting deferred (Remaining #1).

### Phase 5 — Serve + Polish (wk 5–6)
Evidence auth or the parquet decouple (§6), new dashboard pages (pipeline health from `fact_ingestion_run`), README, repo public. **Done when:** a hiring manager can read the repo and a stranger can browse the site.

---

## Remaining

1. Failure alerting: pipeline and Cloudflare build.
2. Azure budget alert.
3. Expand to SF: after the nightly loop is proven, widen the filter to the full "Category: Science-Fiction & Fantasy" shelf (~3,550 more works). Need to add flag, both in the gutenberg extracts, and in the manual files (self) seed.
4. Make CLAUDE erase 75% of the bloated words in its references docs: no 'this, not that', no 'discovered on', no 'X confirmed that' - write down exactly the way a thing is working (without double-checking, again) and absolutely nothing else; if it sounds like a redditer wrote it, erase and rewrite
5. Pipeline-health page from `fact_ingestion_run`.
6.  README; scan git history for secrets; repo public.
