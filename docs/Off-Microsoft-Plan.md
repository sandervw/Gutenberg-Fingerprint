# Off-Microsoft: Migration Plan

Replacing Fabric + Azure with a stack that costs roughly nothing and stays queryable without a resume/pause ritual. Expands `Project-Outline.md`.

**IMPORTANT:** This is a *proposal* by claude. Nothing in this plan is decided - no service, no design. Every piece of technology in this proposal can and probably will change. When comparing similar technologies/products, list the pros/cons of each across the following criteria:
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

*1-5 are locked in.*

| Job           | Now                             | Pick                                                      | Alternative                                       |
| ------------- | ------------------------------- | --------------------------------------------------------- | ------------------------------------------------- |
| Orchestration | `pl_nightly` + Logic App        | GitHub Actions `nightly.yml`, cron + step gating          | *Later:* Dagster OSS on a VPS, as a separate move |
| Compute       | Fabric notebooks on an F2       | runner triggers the box over SSH; code in `/code/gufime/` | —                                                 |
| Files         | OneLake `Files/`                | the VPS's own disk, `/files/gufime/`                      | —                                                 |
| Tables        | OneLake Delta + `wh_gold`       | Postgres on that same VPS (`bronze`/`raw`/`main`)         | —                                                 |
| dbt runtime   | Fabric dbt job off `fabric-dbt` | `uv run dbt build` on the box, `dbt-core` 1.x             | —                                                 |
| Serving       | deploy hook, capacity held open | Evidence's Postgres connector, `wrangler` from the runner | keep the Pages deploy hook; Workers Static Assets |
| Infra as code | Bicep + `fabric-cicd`           | OpenTofu (`hcloud` + `cloudflare` providers)              | Pulumi                                            |
| Secrets       | Entra service principal         | GitHub Actions secrets                                    | Doppler; Cloudflare Secrets Store                 |

**About €5/month, with nothing to remember to switch off.** Two dbt targets stay: `duckdb` for dev, `postgres` for prod.

```
GitHub Actions (cron 03:00 UTC, workflow_dispatch) — every step is `ssh box '...'`
  ├─ extract catalog   → pg bronze.catalog, bronze.watermark
  ├─ extract filter    → pg raw.raw_works       [step output: new_count]
  │     └── if new_count > 0:
  │           ├─ extract texts   → /files/gufime/bronze/texts/
  │           ├─ extract strip   → /files/gufime/silver/corpus/
  │           └─ extract measure → pg raw.raw_measurements, raw.raw_vocab
  ├─ dbt build         → pg main.*
  └─ npm run sources && build → wrangler deploy → gufime.com
```

Four places to check on a failed night become one. The `If Condition` gate becomes `if: steps.filter.outputs.new_count != '0'`. The bracket disappears with the capacity, and so does the $263/month landmine.

---

## 2. The database

**Postgres on a rented Linux box.** One small Hetzner VPS (~€5/month, 4 GB, 40 GB disk) runs Postgres *and* holds the files, so tables and files stay in one place exactly as the Lakehouse has them today. Always on, no autosuspend, no wake latency, no vendor account to lose. `dbt-postgres` is first-party, and Postgres is near enough to DuckDB that most `target.type == 'fabric'` branching deletes.

**Sizing:** 1,842 works, 116k fact rows, ~790k `raw_vocab` rows — roughly 150-250 MB with indexes, against a 40 GB disk. Headroom is not a concern for years.

**The trade, stated plainly:** backups, patching and disk headroom are now yours. Nightly `pg_dump` and the corpus pushed offsite; R2's permanently-free 10 GB is the obvious target and keeps the bill unchanged.

---

## 3. Files

The box's own disk, paths instead of Lakehouse `Files/`:

```
/files/gufime/bronze/texts/{gutenberg_id}.txt   /files/gufime/silver/corpus/{gutenberg_id}.md
/files/gufime/bronze/self/ (+ _manifest.csv)    /files/gufime/bronze/catalog/pg_catalog_{date}.csv
```

~2 GB against 40 GB.

Tabular bronze (`catalog`, `watermark`, `ingest_audit`) goes to Postgres, which drops the `deltalake` dependency.

**Consequence, resolved:** a GitHub-hosted runner cannot see this disk, so the runner orchestrates and the box executes. Every workflow step is `ssh box 'cd /code/gufime && uv run ...'`. Actions keeps the schedule, the gate, the secrets and the logs; files and Postgres stay local to the work.

---

## 4. Notebooks → `extract/`

Ten notebooks, all plain Python kernel (polars, no Spark): `%run` becomes `import`, `notebookutils.exit()` becomes a printed step output, `abfss://` becomes a local path, `write_deltalake` becomes a Postgres write. `_sources.yml` already credits `extract/ (Python + spaCy)` as the loader.

All of it becomes locally runnable, which none of it is today.

---

## 5. The site

Evidence supports PostgreSQL natively, credentials via `EVIDENCE_SOURCE__<source>__<variable>`. `fetch-sources.js` and `nb_export_gold` both delete; the published site stays static DuckDB-WASM over parquet, and the three postbuild scripts stay. Building on the runner and shipping with `wrangler pages deploy` retires the deploy-hook secret and the build-polling loop. Cloudflare now steers new projects to Workers Static Assets, but Pages is fully supported, so treat that move as separate.

---

## 6. Landmines

1. **Pin `dbt-core>=1.10,<2.0`.** dbt Labs say v1.x stays on PyPI, and 1.12 is in beta. A naive `pip install dbt-postgres` still resolves 2.0.0-alpha.1 and fails.
2. **The box is yours.** Unattended security upgrades, a firewall opening SSH only, Postgres bound to localhost, and a nightly `pg_dump` offsite.
3. **Scheduled workflows self-disable after 60 days without a commit**, and cron routinely fires 5-30 minutes late.
4. **The 6-hour job cap.** Nightly deltas are minutes; run any full backfill from the laptop against the same cloud targets.
5. **Carry `bronze.watermark`, `dim_work.ingested_at` and `snap_dim_work` across** or you lose the SCD2 history, the original stamps, and re-download the whole corpus.
6. **PG politeness** now lives in `extract/texts.py`. Keep the caps.

---

## 7. Phases

Fabric keeps running until Phase 6.

**0 — Provision.** Hetzner box, Postgres (three schemas, localhost-only), `/files/gufime/` and `/code/gufime/`, firewall (SSH only), SSH deploy key, `uv`, R2 backup bucket, GitHub secrets, OpenTofu module (`hcloud`) replacing `infra/*.bicep`. Confirm current CX-line specs and price at signup rather than trusting this doc.

**1 — `extract/`.** Convert the ten notebooks behind `storage.py`. *Done when* `catalog` and `filter` write real rows to Postgres from the laptop.

**2 — Migrate.** Copy `Files/texts/` and `Files/corpus/` to `/files/gufime/` (~2 GB, using the `az` token trick in `CLAUDE.md`); export the four stateful tables and load them. *Done when* a `filter` run reports zero new books.

**3 — dbt on Postgres.** Add the target, strip the T-SQL branches (`log_run_results`, the `dim_work` coalesce, the `_sources.yml` database switch). *Done when* both targets build and counts match Fabric.

**4 — Evidence.** Postgres source, delete `fetch-sources.js`. *Done when* the site builds with no Azure env vars.

**5 — `nightly.yml`.** Cron, gate, dbt, build, deploy, concurrency guard, `workflow_dispatch`, each step an `ssh` into the box with `git pull` first. Actions is free and unmetered on a public repo. *Done when* a dispatch and one unattended night both pass.

*Later, optional:* Dagster OSS (webserver + daemon + Postgres, ~2 GB VPS) taking over the schedule, with `dagster-dbt` reading `manifest.json` so extract → dbt → site is one asset graph. Not a prerequisite for anything below.

**6 — Teardown.** Delete `fabric/`, `infra/`, `deploy_fabric.py`, `sync-fabric-dbt.yml`, the `fabric-dbt` branch, the workspace, the F2, the subscription. Rewrite the README diagram and Outline §9.

**Done when:** a nightly run completes with no Azure subscription attached and the site shows the same numbers.

---

## 8. Open decisions

1. **Serving:** build Evidence on the box too (Node goes on the box, Postgres stays shut), or export gold to parquet, rsync it to the runner, and build there on free 16 GB compute? Changes §5. Forced by §3.
2. **Deploy:** build on the runner, or keep the Pages build and its hook?

---

## Sources

Hetzner [cloud pricing](https://www.hetzner.com/cloud/) · [`hcloud` provider](https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs) · [dbt Postgres setup](https://docs.getdbt.com/docs/local/connect-data-platform/postgres-setup) · Cloudflare [R2](https://developers.cloudflare.com/r2/pricing/) (backup target) · [Pages→Workers](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/) · GitHub [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage) · [workflow disabling](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows) · dbt [Fusion](https://docs.getdbt.com/docs/fusion/supported-features) · [adapter pin #1992](https://github.com/dbt-labs/dbt-adapters/issues/1992) · [Evidence CLI](https://docs.evidence.dev/reference/cli)
