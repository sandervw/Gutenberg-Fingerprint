# Learning Notes

*Claude, never touch this file unless I say to.*

## Terms

**.tar File**
- "tape archive"
- bundles a directory tree into one file (no compression)
- Pair it with gzip and you get .tar.gz, which also compresses
- Used here in R2 backup

**DuckDB-WASM**
- An in-process sql db compiled to Web-Assembly
- Allows clients to run queries in their browser

**VPS - Virtual Private Server**
- Runs the storage and compute
- Includes an `API token` - allows `OpenTofu` to create/destroy server, firewall, DNS

**Keypair**
- A form of asymmetric crypto
- Public key (the padlock) and private key (the key)
- `OpenTofo` puts the padlock on the VPS; VPS challenges for private key at connection
- Stored in `$env:USERPROFILE\.ssh`

**OpenTofu**
- infra-as-code: a file is written for the infrastructure that should exist; opentofu uses API to implement it
- Replaces AZURE .bicep
  - **Main** - (`main.tf`) Runs the two below
  - **cloudflare** -(`cloudflare.tf`) Creates the R2 backup bucket (not on the VPS - seperate resource)
  - **OVHCloud VPS** - (`ovh.tf`) Creates the VPS
  - **VPS Resources** - (`provision.sh`) Hands the "user data" to the VM - what to create
    - (`provision.tf`) - ssh into the VPS, runs the above
- `winget install opentofu.tofu`

## VPS Box

Currently set up in **OVHCloud** (the provider)

The Evidence Build requires a `swapfile`
- swap is disk space the kernel uses when RAM fills up
- pages out memory that's sitting idle to disk
- frees up room for currently active work
- Out box has only 3.7GB ram
- 2GB of swap gives it overflow room (it degrades to "slower" rather than "killed")

## Commands

**Create/Login-to vps box commands**
```
set -a; source .env; set +a
cd infra/tofu &&
tofu init &&
tofu plan
tofu apply
ssh -i ~/.ssh/gufime_rsa ubuntu@15.204.82.199
# Add password for DBeaver login/auth
sudo -u postgres psql -c "ALTER ROLE gufime WITH PASSWORD '{.env.POSTGRES_PASSWORD}';"
```

*`uv` = basically, `npm` for python*

**Setup Commands:**
`uv init --bare` # writes a minimal pyproject.toml; pyproject.toml is the package.json equivalent
`uv python pin 3.12`      # writes .python-version; 3.12 = Fabric's dbt runtime
`uv add dbt-core dbt-duckdb dbt-postgres` # records/installs the dependencies in a virtual env and pins versions in `uv.lock` (like package-lock.json)
`uv run dbt --version`    # runs a command inside .venv without activating it

**DBT Commands:**
`cd dbt`
`uv run dbt deps`   # installs dbt_utils into dbt_packages/ (per packages.yml)
`uv run dbt debug`  # validates profiles.yml + connection
`uv run dbt build`  # run models + tests (needs the old warehouse.duckdb copied in as sample data)
`dbt docs generate` # compile metadata
`dbt docs serve`    # launch local web server to view data lineage

**DuckDB Commands**
`duckdb -ui gutenberg_fingerprint/warehouse.duckdb`      # browser UI (object tree + grid)
`duckdb gutenberg_fingerprint/warehouse.duckdb `         # SQL shell: .tables, SELECT ... LIMIT 10

## Python extracts

Land untouched plain text gutenberg files in `bronze`, cleaned markdown in `silver`

Steps:
1. Pull the `PG catalog` feed (pg_catalog.csv - nightly log of all books with ids, title, author, etc); put in bronze
2. Load `watermark table` (a ledger of what we hold; id, catalog row, text hash, etc)
   1. *Watermark: how high on the wall the water rose*
   2. Log of how far ingest got, so tomorrow's run starts at that line; each night:
   - ID in catalog, absent from watermark: new book, fetch it.
   - ID in both, row hash differs: PG shipped a correction to an old text (real and common), fetch again.
   - Hashes match: skip. Most nights near everything skips, and a no-op night costs minutes.

Keep reference tables for list-based metrics (archaic words, function words, punctuation) in lexicons.py

Python creates a few 'raw' schema tables
- raw_measurements (one row per work_id, metric, and value)
- raw_works (one row per work_id and wordcount)
- raw_vocab (one row per work per word)
  - Used to claculate vocab overlap between me and others authors (Jaccard)

## dbt

### Models

A dimension is just a model: one `.sql` file = one `SELECT`.
dbt runs the SELECT and wraps it in `CREATE TABLE AS ...`;

### Where each thing lives

| Concern                              | Where                       | How                                                                                           |
| ------------------------------------ | --------------------------- | --------------------------------------------------------------------------------------------- |
| Schema (columns)                     | `models/marts/dim_work.sql` | Defined implicitly by the SELECT's column list. The columns I select ARE the table's columns. |
| Schema (documented + typed + tested) | `models/marts/_marts.yml`   | Optional properties file: column descriptions, `data_tests` (unique/not_null/relationships).  |
| Transformations                      | same `dim_work.sql`         | The SELECT body: `dbt_utils.generate_surrogate_key` for keys.                                 |
| Where it loads from                  | inside the SELECT           | `{{ ref('seed_authors') }}`, `{{ ref('stg_works') }}`. `ref()` builds the DAG                 |
| Materialization                      | `dbt_project.yml`           | `marts: +materialized: table`. Override per-model with `{{ config(...) }}`.                   |

Key point: **schema and transformation are the SAME file** (the SELECT). The `.yml` only describes and tests what that SELECT produces

### Files for one model (e.g. dim_work)

1. `models/marts/dim_work.sql` - the transformation + the schema (the SELECT).
2. `models/marts/_marts.yml` - docs + tests (optional but wanted).
3. `dbt_project.yml` - already says marts to table.
4. Upstream `ref()` targets: `seed_authors`, `stg_works` (already built).

### Materializations

A materialization answers: when I run this SELECT, what physical thing should exist in the warehouse? It's the build strategy (the DDL wrapper dbt generates).

| Type          | dbt builds                                       | Trade-off                                                      |
| ------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| `view`        | `CREATE VIEW`, recomputed on every read          | cheap to build, always fresh, slower to query. Our `staging/`. |
| `table`       | `CREATE TABLE AS`, rebuilt each `dbt run`        | costs build time + storage, fast to query. Our `marts/`.       |
| `incremental` | table built once, then only new rows appended    | for big append-only data; overkill for a static corpus.        |
| `ephemeral`   | nothing; inlined as a CTE into downstream models | reusable logic with no DB object.                              |

Purpose: it decouples WHAT the data is (the SELECT) from HOW/WHEN it is stored and refreshed.
Flip a view into a table by changing one config line; the SQL never changes.

**Incremental is a cache. A snapshot (SCD2) is a diary.**
- Incremental can be thrown away and rebuilt
- Snapshots only show what was written that day
- Incremental is just an optimization for when a full rebuild is slow/expensive (so worthless on a table like dim_works)
- Snapshots are for when a soruce overwrites itself, and you want to capture old values
- Snapshot manufactures information that exists nowhere else; Incremental only saves time
- *If you need incremental to preserve a value, that value belongs upstream in the data*

### Freshness Checks

Used to throw warning/errors in the event that source (raw) data is stale
- Can be configured at source or table level
- see `staging/_sources.yml`

### Audit Hooks

See `dbt_project.yml` and `macros/log_run_results.sql`
- Basically, adds a step at the end of the run to add a row to the audit log table
- could also configure "on-node-end" if needed

### Seeds

Seeds are small, static CSV files you keep inside your dbt project
- dbt loads into the warehouse as tables
- Version-controlled lookup tables, baked into the repo
- Use seeds for small reference datasets such as country codes, region mappings, or business-defined categories
- Ref() them downstream like any model

### Marts

Same concept from BI, just expressed as code
- Serve-ready, business-facing layer (dim_/fct_/agg_ tables)
- In a modular data modeling approach, data marts sit at the top of the transformation hierarchy
- Organize them by domain, exactly like your finance and marketing marts
- dbt recommends denormalizing heavily into wide tables
- Keep marts relatively simple and avoid too many joins, pushing complexity into the intermediate layer. 

### Macros

Like a User Defined Function in sql server, except they aren't artifacts created on a DB - they are translated into sql at compile time

### Tests

run using `dbt test`

Two kinds:
- Tests in _marts.yml are generic assertions on column/model (not_null, unique, etc)
- Singular tests in `tests/` - for mroe specific assertions; one sql file; if it returns rows, the test fails

## evidence.dev

Basically, PowerBI plus Astro

Everything is written in a markdown file, and all joins/queries are hardcoded in sql (no dynamic joins)
- dynamic filters are possible

PowerBI → Evidence translation
┌────────────────────┬───────────────────────────────────────┐
│   PowerBI world    │            Evidence world             │
├────────────────────┼───────────────────────────────────────┤
│ .pbix canvas, drag │ .md files you type in a text editor   │
│  visuals           │                                       │
├────────────────────┼───────────────────────────────────────┤
│ DAX measures, data │ Plain SQL queries against your        │
│  model             │ warehouse                             │
├────────────────────┼───────────────────────────────────────┤
│ Click a visual,    │ Write a SQL block, then drop a        │
│ bind fields        │ <BarChart> component below it         │
├────────────────────┼───────────────────────────────────────┤
│ Publish to PowerBI │ npm run build → static HTML site      │
│  Service           │ (host anywhere, or run locally)       │
├────────────────────┼───────────────────────────────────────┤
│ Model lives in the │ Logic lives in Git, diffable like     │
│  file              │ code                                  │
└────────────────────┴───────────────────────────────────────┘

Basic synax

```sql authors
select distinct author from mart_work_fingerprint
```

```sql author_lengths
select author, mean_word_length from mart_work_fingerprint
```

<BarChart data={author_lengths} x=author y=mean_word_length />

<Dropdown data={authors} name=picked value=author />

```sql filtered
select * from mart_work_fingerprint
where author = '${inputs.picked.value}'
```
- ${inputs.picked.value} is the manual equivalent of PowerBI's cross-filtering.
- one query can reference another's result with ${query_name}; build reusable base queries and filter them downstream

## Dagster

Overview:
- Open-source, python data orchestrator
- Orchestrates tables, files, models; knows how they depend
- First-class dbt integration
- Pipelines like software: local development, typed inputs/outputs
- One web UI showing whole graph and freshness
- Dagster (OSS) = the dbt Core equivalent; `pip install dagster`
- OSS has everything: assets, scheduling, the web UI, everything; Self-hosted on our OVH box
- Requires adding to privision.tf
- Dagster isn't a nightly job like your GitHub cron; It's a persistent service
- Two long-running processes:
  - webserver - serves the UI (default port 3000)
  - daemon - the background clock that fires your nightly schedule
  - The box runs both of the above continually
- Manual runs: click "Materialize" in the UI. No SSH
- Viewing the UI: two options
    - Quick SSH port-forward (ssh -L 3000:localhost:3000 box, one command, keeps it private)
    - Expose it via a Cloudflare Tunnel + Access on a subdomain, so it's a bookmarked URL with login, no SSH at all