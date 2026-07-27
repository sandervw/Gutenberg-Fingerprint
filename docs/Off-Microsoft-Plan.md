# Off-Microsoft: Migration Plan

Replacing Fabric + Azure with a stack that costs roughly nothing and stays queryable without a resume/pause ritual. Expands `Project-Outline.md` §9. Verified July 2026; re-check prices before provisioning.

---

## 1. Target stack

| Job           | Now                             | Pick                                                      | Alternative                                             |
| ------------- | ------------------------------- | --------------------------------------------------------- | ------------------------------------------------------- |
| Orchestration | `pl_nightly` + Logic App        | GitHub Actions `nightly.yml`, cron + step gating          | Dagster assets executed in Actions; Prefect Cloud Hobby |
| Compute       | Fabric notebooks on an F2       | `ubuntu-latest` runner, `uv run python -m extract <step>` | Modal ($30/mo credits, `Cron` decorators, per-second)   |
| Files         | OneLake `Files/`                | Cloudflare R2, S3 API                                     | Backblaze B2 (cheaper storage, metered egress)          |
| Tables        | OneLake Delta + `wh_gold`       | Neon Postgres (`bronze` / `raw` / `main`)                 | BigQuery free tier; Supabase Pro                        |
| dbt runtime   | Fabric dbt job off `fabric-dbt` | `uv run dbt build` in the same workflow                   | dbt Cloud or SQLMesh, both adding a tool                |
| Serving       | deploy hook, capacity held open | Evidence's Postgres connector, `wrangler` from the runner | keep the Pages deploy hook; Workers Static Assets       |
| Infra as code | Bicep + `fabric-cicd`           | OpenTofu (`cloudflare` + `neon` providers)                | Pulumi                                                  |
| Secrets       | Entra service principal         | GitHub Actions secrets                                    | Doppler; Cloudflare Secrets Store                       |

**Under $1/month, with nothing to remember to switch off.** Two dbt targets stay: `duckdb` for dev, `postgres` for prod.

```
GitHub Actions (cron 03:00 UTC, workflow_dispatch)
  ├─ extract catalog   → Neon bronze.catalog, bronze.watermark
  ├─ extract filter    → Neon raw.raw_works      [step output: new_count]
  │     └── if new_count > 0:
  │           ├─ extract texts   → R2 bronze/texts/
  │           ├─ extract strip   → R2 silver/corpus/
  │           └─ extract measure → Neon raw.raw_measurements, raw.raw_vocab
  ├─ dbt build         → Neon main.*
  └─ npm run sources && build → wrangler deploy → gufime.com
```

Four places to check on a failed night become one. The `If Condition` gate becomes `if: steps.filter.outputs.new_count != '0'`. The bracket disappears with the capacity, and so does the $263/month landmine.

---

## 2. The database

**Neon Postgres, Launch plan.** No monthly minimum; $0.106/CU-hour, $0.35/GB-month. A ~30 min night at the 0.25 CU floor is ~3.8 CU-hours/month ≈ $0.40, plus ~0.3 GB ≈ $0.10. Invoices under $0.50 aren't collected. `dbt-postgres` is first-party, and Postgres is near enough to DuckDB that most `target.type == 'fabric'` branching deletes.

**The caveat:** Neon autosuspends after 5 minutes idle. Wake is sub-second and nothing bills while it sleeps, but it isn't literally always-on; that costs ~$19/month.

**Sizing:** 1,842 works, 116k fact rows, ~790k `raw_vocab` rows — roughly 150-250 MB with indexes. Neon counts history as storage, so set 1-day retention. The free tier's 0.5 GB would fit today with no headroom.

**Alternatives:** BigQuery's free tier (10 GB storage, 1 TiB scanned/month) is $0, always on, and the best dbt adapter going, at the price of a GCP project and service-account JSON. Supabase stays awake on a nightly write but caps free at 500 MB and charges $25/mo for guarantees. ClickHouse Cloud floors near $66/mo. MotherDuck repriced to a $250/mo second tier. DuckLake 1.0 on R2 is the fashionable answer but still needs a DuckDB client, so it fails the "query at will" test.

---

## 3. Object storage

One R2 bucket, prefixes instead of Lakehouse `Files/`:

```
bronze/texts/{gutenberg_id}.txt      silver/corpus/{gutenberg_id}.md
bronze/self/ (+ _manifest.csv)       bronze/catalog/pg_catalog_{date}.csv
```

Free to 10 GB, 1M writes and 10M reads a month, no egress charge ever; the corpus is ~2 GB. `boto3` with `endpoint_url=https://<account_id>.r2.cloudflarestorage.com` and `region_name="auto"`. Backblaze B2 is the equivalent if Cloudflare ever disappoints.

Tabular bronze (`catalog`, `watermark`, `ingest_audit`) goes to Postgres rather than Delta-on-R2, which drops the `deltalake` dependency.

---

## 4. Notebooks → `extract/`

Ten notebooks, all plain Python kernel (polars, no Spark): `%run` becomes `import`, `notebookutils.exit()` becomes a printed step output, `abfss://` becomes an R2 key, `write_deltalake` becomes a Postgres write. `_sources.yml` already credits `extract/ (Python + spaCy)` as the loader.

```
extract/
  __main__.py   config.py   storage.py
  catalog.py  filter.py  texts.py  strip.py  clean.py  measure.py
  lexicons.py  vocab.py  stylometrics.py
```

All of it becomes locally runnable, which none of it is today.

---

## 5. The site

Evidence supports PostgreSQL natively, credentials via `EVIDENCE_SOURCE__<source>__<variable>`. `fetch-sources.js` and `nb_export_gold` both delete; the published site stays static DuckDB-WASM over parquet, and the three postbuild scripts stay. Building on the runner and shipping with `wrangler pages deploy` retires the deploy-hook secret and the build-polling loop. Cloudflare now steers new projects to Workers Static Assets, but Pages is fully supported, so treat that move as separate.

---

## 6. Landmines

1. **Pin `dbt-core>=1.10,<2.0`.** A naive `pip install dbt-postgres` resolves 2.0.0-alpha.1 and fails: Fusion supports only Snowflake, BigQuery, Databricks and Redshift.
2. **Use Neon's direct connection string for dbt**, not the pooled one; PgBouncer drops session `SET`s.
3. **Scheduled workflows self-disable after 60 days without a commit**, and cron routinely fires 5-30 minutes late.
4. **The 6-hour job cap.** Nightly deltas are minutes; run any full backfill from the laptop against the same cloud targets.
5. **Carry `bronze.watermark`, `dim_work.ingested_at` and `snap_dim_work` across** or you lose the SCD2 history, the original stamps, and re-download the whole corpus.
6. **PG politeness** now lives in `extract/texts.py`. Keep the caps.

---

## 7. Phases

Fabric keeps running until Phase 6.

**0 — Provision.** Neon project (1-day retention, three schemas), R2 bucket, API tokens, GitHub secrets, OpenTofu module replacing `infra/*.bicep`.

**1 — `extract/`.** Convert the ten notebooks behind `storage.py`. *Done when* `catalog` and `filter` write real rows to Neon from the laptop.

**2 — Migrate.** Copy `Files/texts/` and `Files/corpus/` to R2 (~2 GB, using the `az` token trick in `CLAUDE.md`); export the four stateful tables to parquet and load them. *Done when* a `filter` run reports zero new books.

**3 — dbt on Postgres.** Add the target, strip the T-SQL branches (`log_run_results`, the `dim_work` coalesce, the `_sources.yml` database switch). *Done when* both targets build and counts match Fabric.

**4 — Evidence.** Postgres source, delete `fetch-sources.js`. *Done when* the site builds with no Azure env vars.

**5 — `nightly.yml`.** Cron, gate, dbt, build, deploy, concurrency guard, `workflow_dispatch`. *Done when* a dispatch and one unattended night both pass.

**6 — Teardown.** Delete `fabric/`, `infra/`, `deploy_fabric.py`, `sync-fabric-dbt.yml`, the `fabric-dbt` branch, the workspace, the F2, the subscription. Rewrite the README diagram and Outline §9.

**Done when:** a nightly run completes with no Azure subscription attached and the site shows the same numbers.

---

## 8. Open decisions

1. **Tables:** Neon, or BigQuery's free tier for the stronger adapter at the cost of a GCP project?
2. **Orchestration:** plain Actions, or Dagster assets executed in Actions for the lineage vocabulary?
3. **Deploy:** build on the runner, or keep the Pages build and its hook?

---

## Sources

Neon [pricing](https://neon.com/pricing) · [pooling](https://neon.com/docs/connect/connection-pooling) · [Terraform](https://neon.com/docs/reference/terraform) · Cloudflare [R2](https://developers.cloudflare.com/r2/pricing/) · [Pages→Workers](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/) · GitHub [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage) · [workflow disabling](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows) · dbt [Fusion](https://docs.getdbt.com/docs/fusion/supported-features) · [adapter pin #1992](https://github.com/dbt-labs/dbt-adapters/issues/1992) · [Evidence CLI](https://docs.evidence.dev/reference/cli) · [DuckLake 1.0](https://ducklake.select/2026/04/13/ducklake-10/) · [Modal](https://modal.com/pricing) · [BigQuery](https://cloud.google.com/bigquery/pricing)
