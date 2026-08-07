# `gutenberg-fingerprint` — A Nightly CDC Stylometrics Pipeline

A nightly, change-data-capturing pipeline that watches the Project Gutenberg science-fiction, fantasy, and horror catalog, lands new and corrected books on a small VPS, extracts stylometrics, and rebuilds dbt → Evidence → Cloudflare Pages.

---

## 1. Architecture

Everything runs on one OVH VPS ("the box"): Postgres, the pipeline files, dbt, and the Evidence build. GitHub Actions orchestrates; every workflow step is `ssh box 'cd /code/gufime && ...'`.

```
GitHub Actions nightly.yml (cron 08:00 UTC, workflow_dispatch, concurrency guard)
  ├─ git reset --hard origin/main    (sync /code/gufime)
  ├─ catalog_ingest.py           → pg bronze.catalog, bronze.watermark, raw.raw_works, bronze.ingest_audit
  │                                [step output: new_count]
  ├─ if new_count != 0:
  │    ├─ text_ingest.py         → /files/gufime/bronze/texts/, watermark
  │    ├─ strip.py               → /files/gufime/silver/corpus/, bronze.strip_audit
  │    ├─ measure.py             → pg raw.raw_measurements, raw.raw_vocab
  │    ├─ dbt deps && dbt build  → pg gold.*
  │    ├─ npm run sources && npm run build
  │    │    └─ wrangler pages deploy → gufime.com
  │    └─ backup.py corpus       → R2 gufime-backup/corpus/ (tar parts + manifest)
  └─ backup.py pg                → R2 gufime-backup/pg/gufime.dump  (every night, backup postgres)
```

- **Orchestrator:** GitHub Actions holds the schedule, the CDC gate (`if: steps.catalog.outputs.new_count != '0'`), the SSH key, and the logs. On a quiet night the run stops after `catalog_ingest.py`.
- **Workflow steps** are plain Python modules in `python/workflow/`, tunables in `python/helpers/` (`lexicons.py`, `vocab.py`, `stylometrics.py`, `clean.py`), all storage behind `python/helpers/storage.py`. `GUFIME_TARGET` picks `duckdb` (local default) or `postgres`; `GUFIME_FILES_ROOT`, `GUFIME_PG_DSN`, `GUFIME_DUCKDB_PATH` override paths. Steps run from the repo root: `uv run python -m python.workflow.<step>`. The gate count surfaces via `storage.emit("new_count", n)`, which also writes `$GITHUB_OUTPUT`.
- **Storage:** files on the box's disk (`/files/gufime/bronze/texts/`, `bronze/catalog/`, `bronze/self/` + `_manifest.csv`, `silver/corpus/`); tables in Postgres database `gufime`, schemas `bronze` (catalog, watermark, ingest_audit, strip_audit), `raw` (raw_works, raw_measurements, raw_vocab), and `gold` (the dbt layer). Postgres listens on the unix socket only and authenticates by peer; no database password exists anywhere.
- **Warehouse + dbt:** `dbt build --target postgres` on the box materializes the star schema and marts in `gold`.
- **BI:** Evidence, built on the box against the same socket (§6).

(one-off side input: manually uploaded works in `/files/gufime/bronze/self/`; `measure.py` re-parses a manual work when its `_manifest.csv` `loaded_at` changes)

---

## 2. CDC Design

**Official catalog feed:** `pg_catalog.csv` (zipped), regenerated daily by PG.

**The mechanics:**

- A `bronze.watermark` table: `gutenberg_id`, `catalog_row_hash`, `text_hash`, `first_seen`, `last_changed`, `status`.
- **New book** = in-scope catalog row ID absent from the watermark. **Changed book** = catalog row hash differs from the watermark's. **Retry** = last attempt failed.
- Downloads: plain-text format only, rate-limited, capped per run, from PG's mirrors.
- Every run writes an **ingestion audit row**: run timestamp, books checked, new, changed, failed.

**Corpus filter** (applied at CDC time): English, `Type = Text`, science-fiction, fantasy, and horror via subject and bookshelf keyword match. `genre` is one exclusive column; works matching more than one land `Undetermined`. Flags (`is_translation`, `is_juvenile`, `is_play`, `is_poetry`) ride along as fields on `stg_works` and are filtered at query time in Evidence.

---

## 3. Dimensional Model

| Table                    | Notes                                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `dim_author`             | Built from catalog data. `is_self = true` on my own row and on select authors                                   |
| `dim_work`               | Carries `gutenberg_id`, `subjects`, `ingested_at`. inner join to measurements keeps unmeasured catalog rows out |
| `dim_metric`             | One row per metric concept, from the `seed_metrics` seed; carries display/unit metadata and additivity class    |
| `fact_style_measurement` | Work × series grain                                                                                             |
| `fact_vocab_overlap`     | Author-pair grain, top-N vocab                                                                                  |
| `snap_dim_work`          | SCD2 snapshot, check strategy on all columns                                                                    |
| `dbt_run_log`            | One row per dbt node per run, written by an `on-run-end` hook                                                   |

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

The nightly run touches **two credentials**: an SSH private key in Actions secrets, and a Cloudflare API token in `~/.config/gufime/cf_token` on the box, scoped to Pages plus R2 write on the backup bucket. The OVH and Cloudflare tokens OpenTofu needs stay on the laptop.

**Backups:** `python/workflow/backup.py` wraps `wrangler r2 object put` and ships to the R2 bucket `gufime-backup` (free-tier 10 GB, declared in `infra/tofu/cloudflare.tf`), latest-only keys overwritten in place. `pg_dump -Fc` every night to `pg/gufime.dump`; on changed nights the corpus tars into 250 MB parts under `corpus/`, plus a sha256 `corpus.manifest` uploaded last. Restore fetches the parts the manifest lists: `cat corpus.tar.gz.* | tar -xz`, and `pg_restore -d gufime`. Backup steps run only after every prior step succeeds.

**Infra as code:** `infra/tofu/` (OpenTofu, OVH + Cloudflare providers) orders the box; `infra/tofu/scripts/provision.sh` runs over SSH and sets up Postgres (three schemas, peer auth on the socket), `uv`, Node 24, `wrangler`, unattended-upgrades, 2 GB swap, `/files/gufime/`, `/code/gufime/`.

**Box hygiene:** unattended security upgrades, a firewall opening SSH only, Postgres bound to the local socket.

---

## 6. The Site

Evidence extracts data at **build time**; the deployed SPA never touches Postgres. Node and Evidence run on the box beside Postgres: `@evidence-dev/postgres` reads the `gold` marts over the unix socket with peer auth. Each Evidence query selects from the mart already at its own grain.

The workflow runs `npm run sources && npm run build` (SPA mode), then `wrangler pages deploy build/` ships the static site to gufime.com. Postbuild scripts (`cdn-wasm.js`, `copy-404.js`) work around Cloudflare Pages' file-size cap and 404 handling.

---

## 7. Constraints & Gotchas

1. **PG politeness is non-negotiable.** Official feeds for the diff, rate-limited downloads, cache everything.
2. **Boilerplate stripping.** Regenerated old files keep an ancient end-marker inside the modern `*** END OF ...` span; the cut is taken at the earliest marker of either era. Cleaning normalizes quotes to doubles.
3. **Pin `dbt-core` below 2.0** (`>=1.11,<2.0` in `pyproject.toml`).
4. **`measure.py` chunks each text** to stay under spaCy's max document length.
5. **Scheduled workflows self-disable after 60 days without a commit**, and cron routinely fires 5-30 minutes late.
6. **The 6-hour Actions job cap.** Nightly deltas are minutes; full backfills run from the laptop against the same targets.

---

## 8. Future Enhancements

1. **Filtering/Cleansing Improvements.** Come up with scheme to remove "new" Works (Concordance)
   1. PG takes public-domain works plus copyrighted ones donated with permission
   2. `pg_catalog.csv` has no rights column. Downloaded text has `*** This is a COPYRIGHTED Project Gutenberg eBook`: ~50 bronze texts.
2. **Add dim_date** (how to load date table?)
3. **Dagster orchestration.** Dagster OSS (webserver + daemon + Postgres, ~2 GB VPS) takes over the schedule from Actions, with `dagster-dbt` reading `manifest.json`; extract → dbt → site becomes one asset graph.

---

## 9. Catalog Facts

**Dates.** `issued` is the PG posting date, 79,071/79,071 populated, 1971-12-01 to 2026-08-02. No date-written exists anywhere. `authors` carries birth/death years for 4,169 of 4,708.