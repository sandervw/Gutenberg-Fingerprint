# DuckDB reference

## Python API

- `duckdb.connect("warehouse.duckdb")`; no arg = in-memory.
- `.sql()` returns lazy relation; materialize via `.show()` / `.df()` / `.fetchall()`.
- `.execute("... WHERE id = ?", [id])` for params.
- pandas DataFrames in local scope are queryable by variable name: `CREATE TABLE raw.m AS SELECT * FROM df`. `con.register('name', df)` registers a virtual table.

## Types vs Fabric

- Portable: `INTEGER`, `BIGINT`, `DECIMAL(p,s)`, `VARCHAR`, `BOOLEAN`, `DATE`.
- Floats diverge: bare `DOUBLE` is invalid T-SQL; Fabric `float` and DuckDB `FLOAT` differ in width. Use `{{ dbt.type_float() }}` with the `duckdb__type_float` -> `double` override, or `DECIMAL(p,s)`.

## DuckDB-only, extractor only

`LIST`/`STRUCT`/`MAP`, `VARCHAR[]`, `regexp_matches`, `regexp_extract`, `string_split`, `len`, `string_agg`, `list()`, `FROM tbl SELECT col`, `SELECT * FROM 'f.parquet'`, `read_csv(f, types={'d':'DATE'})`.
