# dbt-duckdb reference

Local cheat-sheet. Source: github.com/duckdb/dbt-duckdb (via Context7). This is the adapter that lets dbt target DuckDB. Installing it (`pip install dbt-duckdb`) pulls in `duckdb` itself.

---

## profiles.yml (the connection)

Minimal local target:

```yaml
prose_fingerprint:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /abs/path/to/warehouse.duckdb  # ABSOLUTE; see CWD warning below
      threads: 4
      # schema: main             # optional default schema
```

`path` is the DuckDB file. **A relative `path` is resolved against the current working directory, NOT the project dir.** Running dbt from a different folder with a relative path silently creates a SECOND DB there. Fix: use an absolute path (our `profiles.yml` does). `:memory:` for an ephemeral DB. This is where the dual-target swap happens later: add a `fabric:` output alongside `dev`, change `target`, no model changes.

Optional `plugins:` load Python integrations (gsheet, excel, sqlalchemy) at connection time, how dbt-duckdb reaches outside data.

---

## External sources (point dbt at files without loading first)

Declare files as sources via `meta.external_location` / `config.external_location`. dbt rewrites `source(...)` to a DuckDB file-read function:

```yaml
sources:
  - name: external_source
    meta:
      external_location: "s3://my-bucket/{name}.parquet"   # {name} = table name
    tables:
      - name: source1
      - name: source2
        config:
          external_location: "read_parquet(['a.parquet', 'b.parquet'])"

  - name: flights_source
    tables:
      - name: flights
        config:
          external_location: "read_csv('flights.csv', types={'FlightDate': 'DATE'})"
```

Use external sources when landing Parquet/CSV instead of real tables.

---

## external materialization (write models out to files)

`materialized='external'` writes a model's output to a file (default Parquet) instead of a table. Useful for handing data to BI tools.

```sql
{{ config(materialized='external', location='output/data.parquet') }}
select id, name, created_at from {{ ref('upstream_model') }}
```

CSV with options:

```sql
{{ config(materialized='external', location='output/data.csv',
          format='csv', delimiter='|') }}
select * from {{ ref('source_model') }}
```

Standard `view` / `table` / `incremental` materializations also work as normal.

---

## Python models (.py in models/)

dbt-duckdb supports Python models. A `model(dbt, session)` function returns a DataFrame / Arrow table that dbt materializes.

```python
# models/example_python.py
import pandas as pd

def model(dbt, session):
    dbt.config(materialized='table')
    upstream = dbt.ref("my_sql_model")     # a DuckDB relation
    df = upstream.df()                     # -> pandas
    df['new_column'] = df['value'] * 2
    return df
```

PyArrow streaming variant exists for large data (`record_batch`, `RecordBatchReader`).

> Portability note: Python models and DuckDB-specific file reads do NOT port to Fabric. Keep messy Python work in the standalone extractor; keep dbt SQL models to plain joins/aggregations/window functions. See dbt-Project.md §7.
