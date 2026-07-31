"""Storage seam: one pipeline codebase, duckdb locally, postgres on the VPS."""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[2]
TARGET = os.environ.get("GUFIME_TARGET", "duckdb")
DUCKDB_PATH = os.environ.get("GUFIME_DUCKDB_PATH", str(REPO / "dbt" / "warehouse.duckdb"))
PG_DSN = os.environ.get("GUFIME_PG_DSN", "dbname=gufime")
FILES_ROOT = Path(
    os.environ.get("GUFIME_FILES_ROOT")
    or ("/files/gufime" if TARGET == "postgres" else REPO / "data" / "files")
)


class TableMissing(Exception):
    pass


def file_path(rel: str) -> Path:
    return FILES_ROOT / rel


def emit(key: str, value: object) -> None:
    # Step output for GitHub Actions gating
    line = f"{key}={value}"
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    print(line, flush=True)


def _sql_type(dtype: pl.DataType) -> str:
    if isinstance(dtype, pl.Datetime):
        return "timestamptz" if dtype.time_zone else "timestamp"
    simple = {pl.Int64: "bigint", pl.Int32: "integer", pl.Int16: "smallint",
              pl.Float64: "double precision", pl.Float32: "real",
              pl.Boolean: "boolean", pl.Date: "date", pl.String: "text"}
    for k, v in simple.items():
        if dtype == k:
            return v
    raise TypeError(f"no sql mapping for {dtype}")


def _ddl(schema: dict[str, pl.DataType] | pl.Schema) -> str:
    return ", ".join(f'"{c}" {_sql_type(t)}' for c, t in dict(schema).items())


def read_table(name: str, columns: list[str] | None = None) -> pl.DataFrame:
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    query = f"select {cols} from {name}"
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as con:
            try:
                return pl.read_database(query, con)
            except psycopg.errors.UndefinedTable as exc:
                raise TableMissing(name) from exc
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as con:
        try:
            return con.sql(query).pl()
        except duckdb.CatalogException as exc:
            raise TableMissing(name) from exc


def write_table(name: str, df: pl.DataFrame, mode: str = "overwrite") -> None:
    schema_name = name.split(".")[0]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as con, con.cursor() as cur:
            cur.execute(f"create schema if not exists {schema_name}")
            if mode == "overwrite":
                cur.execute(f"drop table if exists {name}")
            cur.execute(f"create table if not exists {name} ({_ddl(df.schema)})")
            if df.height:
                cols = ", ".join(f'"{c}"' for c in df.columns)
                copy_sql = f"copy {name} ({cols}) from stdin (format csv, null '')"
                with cur.copy(copy_sql) as cp:
                    cp.write(df.write_csv(include_header=False))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as con:
        con.execute(f"create schema if not exists {schema_name}")
        con.register("_df", df.to_arrow())
        if mode == "overwrite":
            con.execute(f"create or replace table {name} as select * from _df")
        else:
            con.execute(f"create table if not exists {name} ({_ddl(df.schema)})")
            con.execute(f"insert into {name} by name select * from _df")


def ensure_table(name: str, schema: dict[str, pl.DataType]) -> None:
    schema_name = name.split(".")[0]
    statements = [f"create schema if not exists {schema_name}",
                  f"create table if not exists {name} ({_ddl(schema)})"]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as con:
            for statement in statements:
                con.execute(statement)
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as con:
        for statement in statements:
            con.execute(statement)


def delete_where(name: str, column: str, values: list[str]) -> None:
    if not values:
        return
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as con:
            con.execute(f'delete from {name} where "{column}" = any(%s)', (values,))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as con:
        marks = ", ".join("?" for _ in values)
        con.execute(f'delete from {name} where "{column}" in ({marks})', values)
