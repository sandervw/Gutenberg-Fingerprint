# `gutenberg-fingerprint` — A Nightly CDC Stylometrics Pipeline

A nightly, change-data-capturing pipeline that watches the Project Gutenberg science-fiction, fantasy, and horror catalog, lands new and corrected books on a small VPS, extracts stylometrics, and rebuilds dbt → Evidence → Cloudflare Pages.

---

## 1. Architecture

Everything runs on one OVH VPS ("the box"): Postgres, the pipeline files, dbt, the Evidence build, and **Dagster OSS**, which orchestrates the graph. A GitHub Actions deploy hook syncs the checkout and restarts Dagster on push to `main`.

```
Dagster OSS on the box (nightly schedule 08:00 UTC, Postgres-backed run storage)
  catalog                          → postgres bronze.catalog, bronze.watermark, raw.raw_works, bronze.ingest_audit
   │                                 [prints new_count; published as asset metadata]
   └─ gate sensor (new_count > 0) launches downstream_job, one linear chain:
        texts         → /files/gufime/bronze/texts/, watermark
        stripped      → /files/gufime/silver/corpus/, bronze.strip_audit
        measures      → postgres raw.raw_measurements, raw.raw_vocab
        dbt_models    → dbt build → postgres gold.*  (each dbt node a lineage asset)
        postgres_backup → R2 gufime-backup/postgres/gufime.dump
        corpus_backup → R2 gufime-backup/corpus/ (tar parts + manifest)
        site          → npm run sources && build → wrangler pages deploy → gufime.com
```

- **Orchestrator:** Dagster OSS on the box holds the schedule, the CDC gate, and the run logs (Postgres `dagster` schema). The `nightly` schedule materializes `catalog`; the `gate` asset sensor reads its `new_count` and launches `downstream_job` only when `new_count > 0`. On a quiet night nothing past `catalog` runs; **manual rebuild** is *Materialize all* in the UI. A `failure_alert` run-status sensor emails via Cloudflare on any run failure. Two systemd units serve it: `dagster-webserver` (`127.0.0.1:3000`) and `dagster-daemon`. The UI lives at `dagster.gufime.com` behind a Cloudflare Tunnel + Access.
- **Assets** (`python/dagster/assets.py`, `definitions.py`) wrap the Python modules in `python/workflow/`; Python steps import and call `main()`, while dbt, Evidence, and backup shell out. Tunables in `python/helpers/` (`lexicons.py`, `vocab.py`, `stylometrics.py`, `clean.py`), all storage behind `python/helpers/storage.py`. `GUFIME_TARGET` picks `duckdb` (local default) or `postgres`; `GUFIME_FILES_ROOT`, `GUFIME_PG_DSN`, `GUFIME_DUCKDB_PATH` override paths. `catalog.main()` returns the new-count int, published as `MaterializeResult` metadata the sensor reads.
- **Storage:** files on the box's disk (`/files/gufime/bronze/texts/`, `bronze/catalog/`, `bronze/self/` + `_manifest.csv`, `silver/corpus/`); tables in Postgres database `gufime`, schemas `bronze` (catalog, watermark, ingest_audit, strip_audit), `raw` (raw_works, raw_measurements, raw_vocab), `gold` (the dbt layer), and `dagster` (run metadata). Postgres listens on the unix socket only and authenticates by peer; no database password exists anywhere.
- **Warehouse + dbt:** `dbt build --target postgres` on the box materializes the star schema and marts in `gold`.
- **BI:** Evidence, built on the box against the same socket (§6).

(one-off side input: manually uploaded works in `/files/gufime/bronze/self/`; `measure.py` re-parses a manual work when its `_manifest.csv` `loaded_at` changes)

---

## 2. CDC Design

**Official catalog feed:** `pg_catalog.csv` (zipped), regenerated daily by PG.

**The mechanics:**

- A `bronze.watermark` table: `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New book** = in-scope catalog row ID absent from the watermark. **Changed book** = catalog row hash differs from the watermark's. **Retry** = last attempt failed.
- **Status vocabulary:** `ingested`, `failed`, `copyrighted`. `text_ingest` sniffs each fetched text and skips copyrighted donations, stamping a terminal `copyrighted` status that is never retried.
- Downloads: plain-text format only, rate-limited, capped per run, from PG's mirrors.
- Every run writes an **ingestion audit row**: run timestamp, books checked, new, changed, failed.

**Corpus filter** (applied at CDC time): English, `Type = Text`, science-fiction, fantasy, and horror via subject and bookshelf keyword match. `genre` is one exclusive column; works matching more than one land `Undetermined`. Flags (`is_translation`, `is_juvenile`, `is_play`, `is_poetry`) ride along as fields on `stg_works` and are filtered at query time in Evidence.

---

## 3. Dimensional Model

| Table                    | Notes                                                                                                                                              |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_author`             | Built from catalog data. `is_self = true` on my own row and on select authors; carries `birth_date`/`death_date` (Jan 1 of catalog year, nullable) |
| `dim_work`               | Carries `gutenberg_id`, `subjects`, `ingested_at`, `issue_date` (PG posting date). inner join to measurements keeps unmeasured catalog rows out    |
| `dim_metric`             | One row per metric concept, from the `seed_metrics` seed; carries display/unit metadata and additivity class                                       |
| `dim_date`               | Calendar dimension, daily grain 1970-2035; both facts' `loaded_date_key` FKs point here                                                            |
| `fact_style_measurement` | Work × series grain; `loaded_date_key` FK to `dim_date`                                                                                            |
| `fact_vocab_overlap`     | Author-pair grain, top-N vocab; `loaded_date_key` FK to `dim_date`                                                                                 |
| `snap_dim_work`          | SCD2 snapshot, check strategy on all columns                                                                                                       |
| `dbt_run_log`            | One row per dbt node per run, written by an `on-run-end` hook                                                                                      |

Audit rows live in bronze `ingest_audit`, dbt's run history in `dbt_run_log`, and the site surfaces freshness as `max(ingested_at)` on the main page.

---

## 4. dbt Concepts

- **Incremental models** — none; every dim/fact full-rebuilds (overkill for this scale)
- **Source freshness** — `raw_works` is the heartbeat at `error_after: 24 hours`; the measurement tables are exempt
- **Snapshots** — SCD2 on `dim_work`
- **Environment split** — a `duckdb` dev target and a `postgres` prod target from one codebase
- **On-run-end hook** — `log_run_results` writes run metadata to `gold.dbt_run_log` with plain `create table if not exists`

Prod dbt is `uv run dbt build --target postgres` on the box: peer auth over the unix socket, schema `gold`, no password. Local dev builds against `dbt/warehouse.duckdb`.

---

## 5. Cost & Operations

**About $5/month, always on.** An OVH VPS-1 (2 vCore, 4 GB, 40 GB NVMe); ~2 GB of corpus against 40 GB. GitHub Actions is free and unmetered on a public repo; Cloudflare Pages builds sit inside the free tier.

**Credentials:** an SSH private key in Actions secrets (the deploy hook), a Cloudflare API token in `~/.config/gufime/cf_token` on the box (Pages, R2 write, plus Send Email), and a Cloudflare **Tunnel token** `cloudflared` uses to expose the Dagster UI. The OVH and Cloudflare tokens OpenTofu needs stay on the laptop.

**Backups:** `python/workflow/backup.py` wraps `wrangler r2 object put` and ships to the R2 bucket `gufime-backup` (free-tier 10 GB, declared in `infra/tofu/cloudflare.tf`), latest-only keys overwritten in place. On changed nights `postgres_backup` writes `pg_dump -Fc` to `postgres/gufime.dump`, then `corpus_backup` tars the corpus into 250 MB parts under `corpus/`, plus a sha256 `corpus.manifest` uploaded last. Restore fetches the parts the manifest lists: `cat corpus.tar.gz.* | tar -xz`, and `pg_restore -d gufime`. Backup steps run only after every prior step succeeds.

**Infra as code:** `infra/tofu/` (OpenTofu, OVH + Cloudflare providers) orders the box; `provision.sh` sets up Postgres (four schemas — `bronze`, `raw`, `gold`, `dagster` — peer auth on the socket), `uv`, Node 24, `wrangler`, `cloudflared`, unattended-upgrades, 6 GB swap, `/files/gufime/`, `/code/gufime/`. `provision.tf` installs the Dagster systemd units and registers the `cloudflared` tunnel service.

**Box hygiene:** unattended security upgrades, a firewall opening SSH only, Postgres bound to the local socket.

---

## 6. The Site

Evidence extracts data at **build time**; the deployed SPA never touches Postgres. Node and Evidence run on the box beside Postgres: `@evidence-dev/postgres` reads the `gold` marts over the unix socket with peer auth. Each Evidence query selects from the mart already at its own grain.

The `site` asset runs `npm run sources && npm run build` (SPA mode), then `wrangler pages deploy build/` ships the static site to gufime.com. Postbuild scripts (`cdn-wasm.js`, `copy-404.js`) work around Cloudflare Pages' file-size cap and 404 handling.

---

## 7. Constraints & Gotchas

1. **PG politeness is non-negotiable.** Official feeds for the diff, rate-limited downloads, cache everything.
2. **Boilerplate stripping.** Regenerated old files keep an ancient end-marker inside the modern `*** END OF ...` span; the cut is taken at the earliest marker of either era. Cleaning normalizes quotes to doubles.
3. **Pin `dbt-core` below 2.0** (`>=1.11,<2.0` in `pyproject.toml`).
4. **`measure.py` chunks each text** to stay under spaCy's max document length.
5. **Backfills run from the laptop** against the same targets; nightly deltas are minutes.

---

## 8. Future Enhancements

**Dagster Enhancements**
1. **Retry policies.** Auto-retry network-bound assets (catalog, texts, deploy) with backoff.

**Custom analytics frontend.** An Astro static site over the `gold` marts, replacing Evidence. A build-time renderer runs each page's SQL against Postgres (DuckDB locally) and emits plain HTML with inline SVG; the deployed site ships no client-side query engine or WASM. A markdown-plus-SQL authoring layer binds fenced ` ```sql ` blocks to chart and table components, reproducing Evidence's authoring model. Templated `[work]` and `[author]` pages render at build.