# Project: `gutenberg-fingerprint` — A Fabric-Native CDC Stylometrics Pipeline

The evolution of `prose-fingerprint`: a nightly, change-data-capturing pipeline that watches the Project Gutenberg fantasy catalog, lands new/updated books in a Fabric Lakehouse, extracts stylometrics, and rebuilds the same dbt → Evidence stack you already own. General fiction analysis at corpus scale — with your own prose kept in as the comparison anchor.

**Design constraint flip:** the original was built *locally, portable to Fabric*. This one is built *in Fabric, seeded from the original*. The dbt marts, seeds, macros, and tests carry over near-verbatim; what's new is orchestration, CDC, and FinOps. The dbt layer is now the part you *know* — the pipeline is the part you're here to learn.

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
                    │  or CI-run)   │   │ Evidence     │   └────────────┘
                    └───────────────┘   │ rebuild      │
                                        └──────────────┘
```

- **Orchestrator:** a Fabric Data Factory pipeline on a nightly schedule. It sequences: CDC check → conditional extract → dbt → BI rebuild → pause. If the CDC step finds nothing new (most nights), the pipeline short-circuits and pauses immediately — this "no-op fast path" is itself a talking point.
- **CDC notebook (Python kernel, not Spark):** diffs the PG catalog against a watermark table, downloads only new/changed texts, strips boilerplate, writes bronze Delta.
- **Stylometrics notebook (Python kernel):** your existing extractor logic, re-homed. Same tidy `(work, metric, value)` output contract — silver Delta tables.
- **Warehouse + dbt:** dbt models materialize gold marts in a Fabric **Warehouse**, reading silver via the Lakehouse's SQL analytics endpoint (three-part naming — the endpoint is read-only, which is why models must land in a Warehouse). Fabric now has a native **dbt job** item (preview) that runs dbt on a schedule inside the workspace; the fallback is dbt Core in a GitHub Action. Try the native job first — it's the newer resume line.
- **BI:** Evidence, unchanged in spirit. See §6 for the one real complication.

> **The Python-kernel rule is the new "keep messy work in Python."** Fabric notebooks default to a 2-vCore single-node Python kernel that burns 1 CU/second versus 8 CU/second for the default Spark configuration — roughly 8× cheaper. Your corpus is gigabytes of text, not terabytes; Spark buys you nothing here but cost and spin-up ceremony. DuckDB and Polars come pre-installed in Python notebooks, so your local extractor code ports almost directly.

---

## 2. CDC Design (the new core discipline)

**Catalog source — do not scrape gutenberg.org.** PG actively blocks crawlers. Two sanctioned options:

| Source                     | What                                                                                            | Fit                                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Official catalog feeds** | `pg_catalog.csv` (zipped) and the RDF/XML dump, both regenerated daily by PG                    | The diff source. One polite download per night, full catalog snapshot                               |
| **Gutendex API**           | Community JSON API over the same nightly RDF data; filters on `topic`, `languages` | Handy for metadata enrichment / backfill queries; best-effort service, so cache and don't hammer it |

**The CDC mechanics** (design these yourself — that's the exercise):

- A `watermark` Delta table: `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New book** = ID in catalog, not in watermark. **Changed book** = ID present but catalog row hash differs (PG issues corrections to old texts — this is your "updates" story, and it's real).
- Downloads: plain-text format only, rate-limited (think seconds between requests, not parallelism), from PG's file hosts. A handful of new fantasy titles per week is the norm — the fantasy shelf is small and mostly settled.
- Every run writes an **ingestion audit row**: run timestamp, books checked, new, changed, failed. This table is gold for both debugging and the dashboard's "pipeline health" page.

**Corpus filter** (apply at CDC time, not downstream): English, `Type = Text`, fantasy via subjects/bookshelves keyword match. Translations and juvenile fiction stay in scope, flagged (`is_translation`, `is_juvenile`), surfaced as fields on `stg_works`, filtered at query time in Evidence. Measured 2026-07-12: 689 works, ~290 authors. Log what you *exclude* too — duplicate editions will poison stylometrics if they leak in, and dedupe heuristics (same author + normalized title) are a genuine data-quality problem worth a README section.

---

## 3. What Changes in the Dimensional Model

The fact constellation survives intact. Additions, not rewrites:

| Table                        | Change                                                                                                                                                                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_author`                 | Now built from catalog data, not a seed. Keep `is_self = true` on your row — "me vs 500 dead fantasists" is the demo hook                                                                            |
| `dim_work`                   | Adds `gutenberg_id`, `download_count`, `subjects`, `ingested_at`                                                                                                                                     |
| `fact_style_measurement`     | **Becomes incremental** — new works append; unchanged works don't recompute. The materialization you deliberately skipped last time is now justified, and you know exactly why                       |
| `fact_vocab_overlap`         | Author-level only, top-N vocab, computed **incrementally**: new authors × existing authors, never full recompute. ~500 authors ≈ 125k pairs — fine. All-works pairwise is 8M rows of nothing — don't |
| `fact_ingestion_run` *(new)* | One row per nightly run, from the audit table. Grain: pipeline run                                                                                                                                   |
| `dim_date` *(new)*           | Now that time exists in the model, a date dimension earns its keep                                                                                                                                   |

---

## 4. dbt Concepts This Hits (the sequel checklist)

Last project's checklist was modeling fundamentals. This one is production operation:

- [ ] **Incremental models** — `is_incremental()`, `unique_key`, merge behavior on Fabric
- [ ] **Source freshness** — `dbt source freshness` against `ingested_at`; fail the run if the lakehouse is stale
- [ ] **Snapshots** — SCD2 on `dim_work` (PG corrections change word counts; capture history)
- [ ] **dbt job in Fabric** — the managed runtime, its adapter versions, its preview limitations (no build caching yet)
- [ ] **Environment split** — a `dev` target (your DuckDB local, still alive) and a `fabric` prod target; same repo, the portability promise made real
- [ ] **State-aware runs** — `dbt build --select state:modified+` in CI (needs artifacts; note the Fabric preview gap)
- [ ] **On-run-end hooks** — write dbt run metadata back to the audit table

---

## 5. FinOps (this section is load-bearing now)

The nightly job means the capacity *must* wake and sleep on its own. There is no built-in Fabric auto-pause schedule — you build the bracket yourself, and that bracket is a resume bullet:

1. **Resume:** Logic App / Azure Automation runbook POSTs to the capacity's `/resume` management endpoint on schedule (managed identity, Contributor scoped to the capacity resource only).
2. **Run:** the Data Factory pipeline does its work. A no-op night is minutes; an ingest night maybe 30–45.
3. **Pause:** the *pipeline's last step* triggers suspend (web activity → Logic App → `/suspend`), rather than a fixed clock — you pause when work finishes, not when you guessed it would.

**Cost math (F2 PAYG, US regions, ~$0.18/CU/hr):**

| Item                                          | Estimate               |
| --------------------------------------------- | ---------------------- |
| Backfill (one-time, bump to F4 for a weekend) | $2–5                   |
| Nightly runs (~30 min avg × 30 days on F2)    | $5–10/mo               |
| OneLake storage (~2 GB text + Delta)          | pennies ($0.023/GB/mo) |
| Cloudflare Pages nightly builds               | free tier covers it    |
| **Left running 24/7 by accident**             | **~$263/mo**           |

That last row is why an **Azure budget alert on the subscription is step zero**, before any pipeline exists. Do the initial build on the 60-day Fabric trial capacity; move to paid F2 only when the automation bracket is proven.

---

## 6. The Evidence Wrinkle (one real design decision)

Evidence extracts data at **build time** into a static site — the deployed Cloudflare Pages site never touches the Warehouse. Two consequences:

1. **Auth:** Fabric Warehouse refuses SQL auth; Entra ID only. Evidence's MSSQL connector (tedious driver) supports service-principal auth — configure `azure-active-directory-service-principal-secret` via env vars in the build environment. Budget an evening.
2. **Sequencing:** the Cloudflare build (triggered by a deploy-hook POST — each hook is a unique URL, no auth header, treat it as a secret) runs `npm run sources` against the Warehouse — so the capacity must still be awake *during* the CF build. Your pause step must wait for it. Options, in ascending elegance: fixed delay before suspend; poll the CF deployments API; or sidestep entirely by having dbt export gold marts to parquet in OneLake / the repo and pointing Evidence's DuckDB source at those files, decoupling BI builds from capacity state. Pick one deliberately and write down why — that reasoning is interview material.

---

## 7. Constraints & Gotchas (learn these before they teach you)

1. **PG politeness is non-negotiable.** Official feeds for the diff, rate-limited downloads, cache everything. Getting your IP blocked is the failure mode that kills the whole project.
2. **Boilerplate stripping is your biggest data-quality fight.** PG headers/footers/license blocks vary by era and would swamp every lexical metric. The `*** START/END OF THE PROJECT GUTENBERG EBOOK ***` markers are a starting point, not a solution. Test-drive against 20 books from different decades before trusting it. Extraction also needs to handle cleaning (take special care to use double quotes instead of single quotes in cleaned output texts).
3. **T-SQL surface:** same rules as before — `dbt_utils` cross-db macros, standard types, no engine-specific SQL. Fabric Warehouse has documented unsupported T-SQL commands and types; your existing models already respect this, keep it that way.
4. **F2 is small.** One notebook at a time, Python kernel, sequential pipeline steps. Smoothing spreads background CU over 24h, which helps — but the backfill deserves a temporary F4.
5. **Preview features move.** The Fabric dbt job is preview (no artifact caching yet); the Lakehouse dbt adapter story keeps shifting. Re-verify both when you start, and keep the GitHub Actions fallback in your pocket.

---

## 8. Phased Plan (evenings/weekends — this is a 6-week shape, not 3)

### Phase 1 — Foundation (wk 1)
Trial capacity, workspace, Lakehouse + Warehouse. Budget alert. Port the dbt repo, add the `fabric` target, `dbt debug` green against the Warehouse. **Done when:** existing marts build in Fabric from manually loaded sample data.

### Phase 2 — Backfill (wk 2–3)
Catalog ingestion notebook, corpus filter, boilerplate stripper, watermark table. Backfill the full fantasy corpus (rate-limited — let it take days). Stylometrics notebook over the corpus. **Done when:** bronze/silver populated, audit table records the backfill.

### Phase 3 — Incremental dbt (wk 3–4)
Convert facts to incremental, add snapshots, source freshness, the expanded tests. **Done when:** a second run with a hand-injected "new book" flows through end-to-end and *only* the delta recomputes.

### Phase 4 — Orchestration + FinOps (wk 4–5)
Data Factory pipeline, resume/pause bracket, nightly schedule, failure alerting. **Done when:** you watch it run three consecutive nights without touching it, and the Azure bill graph shows the sawtooth.

### Phase 5 — Serve + Polish (wk 5–6)
Evidence auth or the parquet decouple (§6), new dashboard pages (corpus explorer, "you vs the field," pipeline health from `fact_ingestion_run`), README with the architecture diagram, repo public. **Done when:** a hiring manager can read the repo and a stranger can browse the site.

**Deferred filter expansion (noted 2026-07-12):** after the nightly loop is proven, widen the filter to the full "Category: Science-Fiction & Fantasy" shelf (~3,550 more works). Flag columns plus Evidence-side filtering make it a config change, not a redesign.

---

## 9. Why This Version Is the Resume Piece

- **Operations, not artifacts:** scheduling, CDC, incremental processing, watermarks, audit trails, and cost-bracketed capacity — the verbs interviewers probe for after they've seen one static dbt repo.
- **The FinOps bracket is rare and legible:** "my pipeline resumes its own compute, runs, and pauses it" is a one-sentence story that lands with anyone who has seen a surprise Azure bill.
- **Direct company relevance:** Fabric Warehouse + Data Factory + dbt is the exact target of the Pharmacists Mutual migration; this is a working POC with your name on the commits.
- **The hook survives:** `is_self = true` still sits in `dim_author`. The dashboard's money page is unchanged in spirit and better in scale — your fingerprint plotted against the entire public-domain fantasy tradition, refreshed nightly by a system you run.
