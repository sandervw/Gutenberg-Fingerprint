# Microsoft Fabric reference

Local cheat-sheet. Source: Microsoft Learn (via MCP), fetched 2026-07-06. Covers the Fabric pieces this project touches: capacities, Lakehouse/Warehouse, notebooks, dbt-fabric, dbt job, pause/resume.

---

## Core concepts

- **Capacity** = the compute meter. F SKUs sized in Capacity Units (CU): F2 = 2 CU, F4 = 4, F64 = 64. Trial capacity (per Learn, 2026-07): starts at **4 CU**, resizable to 64 via Admin portal → Capacity settings → Trial → Change size; 60 days; **doesn't support pause/resume** (paid F SKU only). At trial end: items go inactive, content kept in OneLake 7 days, revive by assigning workspace to a paid F capacity.
- **Trial sign-in gotcha**: Fabric blocks personal-MSA sign-ins (gmail etc.). Path per Learn `free-trial-account-personal-email`: create a native Entra user in the tenant (Azure portal → Entra ID → Users → New user), sign in at app.fabric.microsoft.com with its UPN, Account manager (profile pic, top-right) → Start/Free trial → pick region → Activate. Region is sticky — moving Fabric items cross-region later means deleting them first; match the region you'd buy paid F2 in.
- **IaC status**: paid F capacities are ARM resources (`Microsoft.Fabric/capacities`, Bicep-able). Trial capacity is portal-only. Workspaces/items sit on Fabric's own control plane — Fabric REST API / Terraform Fabric provider, not ARM/Bicep.
- **Workspace** = container for items (Lakehouse, Warehouse, notebooks, pipelines, dbt jobs), assigned to a capacity.
- Everything stores to **OneLake** as Delta/Parquet; engines share the same files. OneLake is *the* lake (one per tenant); a Lakehouse item is a database-shaped container over it — multiple Lakehouses copy no data.
- **Medallion deployment (Learn, 2026-07)**: recommended = one lakehouse per layer (enterprises: one *workspace* per layer for isolation). Alternative = one schema-enabled lakehouse with bronze/silver/gold schemas (used in MS tutorials). Schema-enabled limitations: no workspace-level sharing, no external ADLS table metadata, and **no conversion path** plain↔schema-enabled after creation. Bronze guidance: keep source format (Files/ ok); silver/gold: Delta tables.
- F2 PAYG ≈ $0.18/CU/hr US regions → ~$263/mo if left running. Pause = step zero of FinOps (see project doc §5).

## Lakehouse vs Warehouse

| | Lakehouse | Warehouse |
|---|---|---|
| Write path | Spark / Python notebooks, pipelines | T-SQL (full DML/DDL), dbt |
| Delta | read + write | read + write |
| T-SQL | via **SQL analytics endpoint — read-only** (views/TVFs ok, no DML) | full |

- Every Lakehouse auto-provisions a **SQL analytics endpoint**: read-only T-SQL over its Delta tables, same engine as Warehouse. This is why dbt models must materialize in a Warehouse and read silver via **three-part naming**: `MyLakehouse.dbo.table`.
- Cross-database queries work within a workspace: `SELECT ... FROM Lakehouse.dbo.t JOIN Warehouse.dbo.u`.
- Endpoint metadata syncs from Delta logs in the background — new/changed Lakehouse tables can lag briefly before appearing in SQL.
- Only Delta tables surface in the endpoint (not raw CSV/Parquet in `Files/`).

## Notebooks (Python kernel vs Spark)

- **Python kernel**: single node, default 2 vCores/16 GB = **1 CU**, ~5s start. DuckDB, Polars, delta-rs preinstalled. Our choice — corpus is GBs, not TBs.
- **Spark starter pool**: ~5s start but 8 CU after scale-up. Use only if data outgrows a single node (~10 GB+ compressed).
- **Delta-write gotchas on the Python kernel** (matters for bronze/silver):
  - No Python engine writes **deletion vectors**; writing to a table with them enabled errors. Create tables without DVs if Python writes them.
  - **DuckDB INSERT never writes checkpoints** → transaction log grows unbounded. Prefer **delta-rs** (`deltalake` lib) as the writer; DuckDB/Polars for compute.
  - delta-rs default checkpoint interval is 100 commits (Spark: 10) — set lower; run periodic `optimize`/`vacuum lite` via delta-rs.
- `notebookutils` data connector lets Python notebooks run T-SQL against Warehouse/endpoints.

## dbt-fabric adapter (local dbt Core → Warehouse)

Prereqs: Python ≥3.7, **Microsoft ODBC Driver 18 for SQL Server**, `pip install dbt-fabric`.

```yaml
gutenberg_fingerprint:
  target: fabric
  outputs:
    fabric:
      type: fabric
      driver: ODBC Driver 18 for SQL Server
      host: <workspace SQL endpoint, from Warehouse settings>
      database: <warehouse name>
      schema: dbo
      authentication: CLI     # az login; use service principal for automation
      threads: 4
```

- **No SQL auth** — Entra ID only. Interactive: `authentication: CLI` after `az login`. Automation: service principal (env-var creds).
- T-SQL surface limits apply: no engine-specific SQL, check unsupported commands/types. Adapter emulates `ALTER TABLE ADD COLUMN`, `MERGE`, `TRUNCATE`, `sp_rename` via CTAS/DROP/CREATE.
- Docs: learn.microsoft.com/fabric/data-warehouse/tutorial-setup-dbt

## dbt job item (preview, in-Fabric runtime)

- Workspace item that runs dbt Core **inside Fabric**: managed runtime V1.0 = dbt Core 1.9, dbt-fabric 1.9.0, Python 3.12.
- Enable per-tenant: admin portal → tenant settings → **dbt jobs (preview)**.
- Project source: authored in-UI or **connected to a GitHub repo** (classic PAT, pick branch — pulls fresh each run).
- Supports `build/run/seed/test/compile/snapshot` + selectors; orchestratable as a **pipeline activity** (operation, select/exclude, full refresh, threads).
- Full logs land in OneLake (`dbt-output-<run_id>.json` → `detailed_monitoring_output_path`).
- **Limitations**: no build caching — every run compiles fresh, no artifacts from prior runs → **no `state:modified` in-Fabric** (do state-aware runs in CI instead).

## Capacity pause/resume (the FinOps bracket)

- Azure portal: capacity → Pause/Resume. Programmatic: Fabric capacities REST API `.../suspend` and `.../resume` (Azure management plane, ARM resource).
- Required RBAC on the capacity resource: `Microsoft.Fabric/capacities/{read,write}`, `.../suspend/action`, `.../resume/action`. Best practice: **custom role** scoped to just these, assigned to the automation's managed identity.
- Azure Automation runbook gallery has prebuilt Fabric pause/resume runbooks (search "Fabric") — schedulable.
- **Pausing bills the smoothed backlog**: accumulated/carryforward usage is settled as a one-time charge at pause (shows as a spike in the Capacity Metrics app). Also instantly clears throttling.
- Pausing kills availability of everything on the capacity mid-run — sequence pause *after* all work (incl. the Evidence build) finishes.
- OneLake storage billing continues while paused (~$0.023/GB/mo).

## Pipeline (Data Factory) notes

- Fabric pipelines ≈ ADF: activities, schedules, conditionals. Relevant limits: **Web activity doesn't support service-principal auth** (matters for the suspend call — route via Logic App or use managed identity options), no tumbling-window triggers.
