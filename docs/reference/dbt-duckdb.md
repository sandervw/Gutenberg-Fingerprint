# dbt-duckdb

## profiles.yml

Keys: `type: duckdb`, `path`, `threads`, `schema`, `plugins`.

Relative `path` resolves against CWD, not project dir; running dbt elsewhere silently creates a second DB. Use absolute. `:memory:` = ephemeral.

Fabric swap: add `fabric:` output beside `dev`, change `target`.

## Config keys

- Sources: `meta.external_location` / `config.external_location`; `{name}` = table name; accepts read functions.
- `materialized='external'`: `location`, `format`, `delimiter`. Default Parquet.
- Python models: `models/*.py`, `model(dbt, session)`; `dbt.ref()` -> DuckDB relation, `.df()` -> pandas.

## Fabric

Python models and DuckDB file reads do not port. SQL models: joins, aggregations, window functions. See dbt-Project.md §7.
