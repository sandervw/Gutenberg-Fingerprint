# Learning Notes

*Claude, never touch this file unless I say to.*

## Setup

*`uv` = basically, `npm` for python*

`uv init --bare` # writes a minimal pyproject.toml; pyproject.toml is the package.json equivalent
`uv python pin 3.12`      # writes .python-version; 3.12 = Fabric's dbt runtime
`uv add dbt-core dbt-duckdb dbt-fabric` # records/installs the dependencies in a virtual env and pins versions in `uv.lock` (like package-lock.json)
`uv run dbt --version`    # runs a command inside .venv without activating it

Then:

`cd dbt`
`uv run dbt deps`         # installs dbt_utils into dbt_packages/ (per packages.yml)
`uv run dbt debug`        # validates profiles.yml + connection
`uv run dbt build`        # run models + tests (needs the old warehouse.duckdb copied in as sample data)

No dbt init — that scaffolds an empty project; we're porting a real one.

## Viewing the data

`duckdb -ui prose_fingerprint/warehouse.duckdb`      # browser UI (object tree + grid)
`duckdb prose_fingerprint/warehouse.duckdb `         # SQL shell: .tables, SELECT ... LIMIT 10

## Design Decisions

Raw data is extracted from /corpus via the /extracts python logic

Seven python files:
- `build_seed.py` - "the junior cook"; parses files to create authors csv
- `cleaning.py` - "the wash/strainer station"; cleans the raw file text
- `extracts.py` - "the cook"; knows text and NLP; cleans, parses with spaCy; runs metrics, assembles types rows; the 'E' of ELT
- `lexicons.py` - "the reference charts"; a list of spice rack spices; holds data, not logic
- `loaders.py` - "the waiter"; knows the database; holds table shapes and create/insert; the 'L' of ELT
- `stylometrics.py` - "the measuring gear"; scales, calipers; reads numbers off the dish
- `vocab.py` - "the specific sampler/bagging appliance"; does one specific job for one metric

The cleansing/quality part of transformation lives in the python extract (cleaning.py)
- strips out markdown (keeps source files intact while cleaning up text for downstream)
- Flattens multi-value stylometric measures into single work-metric-value rows

Keep reference tables for list-based metrics (archaic words, function words, punctuation) in lexicons.py

Python creates a few 'raw' schema tables in duckdb
- raw_measurements (one row per work_id, metric, and value)
- raw_works (one row per work_id and wordcount)
- raw_vocab (one row per work per word)
  - USed to claculate vocab overlap between me and others authors (Jaccard)

## Bicep

Basically "Infrastructure as code"
- See infra/ folder
- Basically, a .bicep file is a wanted end state; a tool takes all steps to get real state to match; git keeps your written record

## Lakehouse Design

We use two lakehouses in this design
- Lakehouse is seperate from a lake (OneLake)
- Lakehouse is a database-shaped folder on top of lake
- Bronze lakehouse holds raw text blobs, plus delta tables (catalog rows, CDC watermark)
- Silver holds tidy delta tables only
- Gold warehouse only holds cleaned marts
- Seperate layers (bronze/silver/gold) is standard design; creates seperation of trust

## dbt Run location

dbt currently sits on one machine; fabric/azure sits on another
- dbt builds the sql from templates (jinja) and mails them to the engine (fabric) to run the actual sql
- Needs an ODBC 18 driver (the light from the machine "remote" to the engine "TV")

## dbt Models

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

Key point: schema and transformation are the SAME file (the SELECT). The `.yml` only describes and tests what that SELECT produces

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

## Seeds

Seeds are small, static CSV files you keep inside your dbt project
- dbt loads into the warehouse as tables
- Version-controlled lookup tables, baked into the repo
- Use seeds for small reference datasets such as country codes, region mappings, or business-defined categories
- Ref() them downstream like any model

## Marts

Same concept from BI, just expressed as code
- Serve-ready, business-facing layer (dim_/fct_/agg_ tables)
- In a modular data modeling approach, data marts sit at the top of the transformation hierarchy
- Organize them by domain, exactly like your finance and marketing marts
- dbt recommends denormalizing heavily into wide tables
- Keep marts relatively simple and avoid too many joins, pushing complexity into the intermediate layer. 

## Macros

Like a User Defined Function in sql server, except they aren't artifacts created on a DB - they are translated into sql at compile time

## Tests

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