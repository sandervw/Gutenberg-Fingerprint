# Off-Microsoft: Migration Plan

*Phases 0-4 are executed and verified; Phases 5-6 remain proposals.*

**IMPORTANT:** When comparing technologies/products, list the pros/cons of each across the following criteria:
- Is it simple?
- Is it low cost?
- Is data, or the interface, accessible without a manual resume/pause step?
- Is it long-standing, with a solid reputation (this is the microsoft strength)?
- Is it 'enterprisey? Used by established companies, not startups?
- Does it intergrate with other technologies easily?
- Is it standalone?
- It it a true seperate target versus DuckDB/Fabric?

---

## 1. Target stack

| Job           | Now                             | Pick                                                      | *Later:*                                 |
| ------------- | ------------------------------- | --------------------------------------------------------- | ---------------------------------------- |
| Orchestration | `pl_nightly` + Logic App        | GitHub Actions `nightly.yml`, cron + step gating          | Dagster OSS on a VPS, as a separate move |
| Compute       | Fabric notebooks on an F2       | runner triggers the box over SSH; code in `/code/gufime/` | —                                        |
| Files         | OneLake `Files/`                | the box's own disk, `/files/gufime/`                      | —                                        |
| Tables        | OneLake Delta + `wh_gold`       | Postgres on the same box (`bronze`/`raw`/`main`)          | —                                        |
| dbt runtime   | Fabric dbt job off `fabric-dbt` | `uv run dbt build` on the box, `dbt-core` 1.x             | —                                        |
| Serving       | deploy hook, capacity held open | Postgres connector; build on box, `wrangler pages deploy` | Workers Static Assets                    |
| Infra as code | Bicep + `fabric-cicd`           | OpenTofu; custom provision bash builds on the box         | —                                        |
| Secrets       | Entra service principal         | one SSH key in Actions, one Cloudflare token on the box   | —                                        |

**About $5/month, with nothing to remember to switch off.** Two dbt targets stay: `duckdb` for dev, `postgres` for prod.

The nightly run touches **two credentials**: an SSH private key in Actions, and a Cloudflare API token in a file on the box, scoped to `Pages: Edit` plus write on the one R2 bucket. The OVH and Cloudflare tokens OpenTofu needs stay on the laptop.

```
GitHub Actions (cron 03:00 UTC, workflow_dispatch) — every step is `ssh box '...'`
  ├─ catalog_ingest.py → pg bronze.catalog, bronze.watermark
  ├─ filter.py         → pg raw.raw_works       [step output: new_count]
  │     └── if new_count > 0:
  │           ├─ text_ingest.py → /files/gufime/bronze/texts/
  │           ├─ strip.py       → /files/gufime/silver/corpus/
  │           └─ measure.py     → pg raw.raw_measurements, raw.raw_vocab
  ├─ dbt build         → pg main.*
  └─ npm run sources && build → wrangler pages deploy → gufime.com
```

Four places to check on a failed night become one. The `If Condition` gate becomes `if: steps.filter.outputs.new_count != '0'`.

---

## 2. The database

**Postgres on an OVHcloud VPS-1** ($4.54/month listed, 2 vCore, 4 GB, 40 GB NVMe) runs Postgres *and* holds the files, so tables and files stay in one place exactly as the Lakehouse has them today. Always on, no autosuspend, no wake latency, no vendor account to lose. `dbt-postgres` is first-party, and Postgres is near enough to DuckDB that most `target.type == 'fabric'` branching deletes.

**Sizing:** 4,408 in-scope works, 204k `raw_measurements` rows, 7.3M `raw_vocab` rows, against a 40 GB disk. Headroom is not a concern for years.

Postgres listens on the unix socket only and authenticates by peer, so the Linux user *is* the credential and no database password exists anywhere.

**The trade, stated plainly:** backups, patching and disk headroom are now yours. Nightly `pg_dump` and the corpus go offsite with `wrangler r2 object put` on the same Cloudflare token, so there are no S3 keys; it caps at 315 MB per object, so the corpus tars in parts. R2's permanently-free 10 GB is the obvious target and keeps the bill unchanged.

---

## 3. Files

The box's own disk, paths instead of Lakehouse `Files/`:

```
/files/gufime/bronze/texts/{gutenberg_id}.txt   /files/gufime/silver/corpus/{gutenberg_id}.md
/files/gufime/bronze/self/ (+ _manifest.csv)    /files/gufime/bronze/catalog/pg_catalog_{date}.csv
```

~2 GB against 40 GB.

Tabular bronze (`catalog`, `watermark`, `ingest_audit`, `strip_audit`) lives in Postgres `bronze`; the raw tables in `raw`; `snap_dim_work` and `dbt_run_log` in `main`.

A GitHub-hosted runner cannot see this disk, so the runner orchestrates and the box executes. Every workflow step is `ssh box 'cd /code/gufime && uv run ...'`. Actions keeps the schedule, the gate, the secrets and the logs; files and Postgres stay local to the work.

---

## 4. Notebooks → plain modules *(done)*

Workflow steps live in `python/workflow/`, tunables in `python/helpers/`, all storage behind `python/helpers/storage.py`. `GUFIME_TARGET` picks `duckdb` (default) or `postgres`; `GUFIME_FILES_ROOT`, `GUFIME_PG_DSN`, `GUFIME_DUCKDB_PATH` override paths. Steps run from the repo root: `uv run python -m python.workflow.<step>`. The gate count surfaces via `storage.emit("new_count", n)`, which also writes `$GITHUB_OUTPUT`. The deployed Fabric notebook items are frozen copies.

---

## 5. The site

**(DONE)** Evidence reads Postgres over the unix socket, peer auth, `@evidence-dev/postgres`. `fetch-sources.js` deleted. `export_gold.py` stays until Phase 6. The three postbuild scripts stay. Node and Evidence run on the box beside Postgres, bound to localhost; the runner `ssh`s in to build, then `wrangler pages deploy build/` ships it.

---

## 6. Landmines

1. **Pin `dbt-core>=1.10,<2.0`.** dbt Labs say v1.x stays on PyPI, and 1.12 is in beta. A naive `pip install dbt-postgres` still resolves 2.0.0-alpha.1 and fails.
2. **The box is yours.** Unattended security upgrades, a firewall opening SSH only, Postgres bound to localhost, and a nightly `pg_dump` offsite. **cloud-init runs once, at first boot**, so later changes to it only take effect on a rebuild.
3. **(DONE) 2 GB swap.** Set in `provision.sh` and live on the box.
4. **Scheduled workflows self-disable after 60 days without a commit**, and cron routinely fires 5-30 minutes late.
5. **The 6-hour job cap.** Nightly deltas are minutes; run any full backfill from the laptop against the same cloud targets.
6. **(DONE)** All nine stateful tables and both file trees are carried across; `scripts/migrate_fabric_to_vps.py` re-runs safely.
7. **PG politeness** now lives in `python/workflow/text_ingest.py`. Keep the caps.

---

## 7. Phases

Fabric keeps running until Phase 6.

**(DONE) 0 — Provision.** `infra/tofu/` orders the box and runs `scripts/provision.sh` over SSH: Postgres (three schemas, peer auth on the socket), `uv`, Node 24, `wrangler`, unattended-upgrades, `/files/gufime/`, `/code/gufime/`.

**(DONE) 1 — Plain modules.** The ten notebooks are modules behind `python/helpers/storage.py` (§4); both targets write real rows.

**(DONE) 2 — Migrate.** `scripts/migrate_fabric_to_vps.py` carried all files and nine tables; every count verified both sides. Warehouse tables read via `deltalake.query.QueryBuilder` (`columnMapping`). `scripts/seed_duckdb_from_staging.py` seeds the local duckdb from the staging copy at `C:\gufime-migration`, which stays until the first unattended VPS night passes. `filter.py` on the box matches Fabric's gate count; the backfill backlog drains at ~200 texts/night.

**(DONE) 3 — dbt on Postgres.** `postgres` target added (peer auth, unix socket, no password). `log_run_results` and `_sources.yml` needed a postgres branch; `parse_primary_author`/`stddev_pop_expr` already fell through to `default__` unchanged. Both targets build clean on `--full-refresh`; row counts match exactly (dim_work/mart_work 3187, fact_style_measurement/mart_style_long 200781, mart_author 1171, fact_vocab_overlap 1170).

**(DONE) 4 — Evidence.** `evidence.config.yaml` and `package.json` use `@evidence-dev/postgres`. Row counts match Phase 3's dbt output. Build verified on the box.

**5 — `nightly.yml`.** Cron, gate, dbt, build, deploy, concurrency guard, `workflow_dispatch`, each step an `ssh` into the box with `git pull` first. The first push replaces the tar snapshot in `/code/gufime/`. Actions is free and unmetered on a public repo. *Done when* a dispatch and one unattended night both pass. Pause the Logic App here.

*Later, optional:* Dagster OSS (webserver + daemon + Postgres, ~2 GB VPS) taking over the schedule, with `dagster-dbt` reading `manifest.json` so extract → dbt → site is one asset graph. Not a prerequisite for anything below.

**6 — Teardown.** Delete `fabric/`, `infra/`, `deploy_fabric.py`, `sync-fabric-dbt.yml`, the `fabric-dbt` branch, the workspace, the F2, the subscription. Rewrite the README diagram and Outline §9.

**Done when:** a nightly run completes with no Azure subscription attached and the site shows the same numbers.

---

## Sources

[OVH VPS](https://www.ovhcloud.com/en/vps/) · [OpenTofu](https://opentofu.org/docs/) · [cloud-init](https://cloudinit.readthedocs.io/en/latest/reference/examples.html) · [dbt Postgres setup](https://docs.getdbt.com/docs/local/connect-data-platform/postgres-setup) · Cloudflare [R2](https://developers.cloudflare.com/r2/pricing/) (backup target) · [Pages→Workers](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/) · GitHub [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage) · [workflow disabling](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows) · dbt [Fusion](https://docs.getdbt.com/docs/fusion/supported-features) · [adapter pin #1992](https://github.com/dbt-labs/dbt-adapters/issues/1992) · [Evidence CLI](https://docs.evidence.dev/reference/cli)
