"""Storage seam: one pipeline codebase, duckdb locally, postgres on the VPS."""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = os.environ.get("GUFIME_TARGET", "duckdb")
DUCKDB_PATH = os.environ.get("GUFIME_DUCKDB_PATH", str(REPO_ROOT / "dbt" / "warehouse.duckdb"))
PG_DSN = os.environ.get("GUFIME_PG_DSN", "dbname=gufime")
FILES_ROOT = Path(
    os.environ.get("GUFIME_FILES_ROOT")
    or ("/files/gufime" if TARGET == "postgres" else REPO_ROOT / "data" / "files")
)

# Shared by the workflow scripts
TS_UTC: pl.Datetime = pl.Datetime("us", "UTC")
USER_AGENT: str = "gutenberg-fingerprint-pipeline/0.1 (contact: samvanwilligen@gmail.com)"
SELF_FOLDER: str = "Sander-VanWilligen"


class TableMissing(Exception):
    pass


def file_path(relative_path: str) -> Path:
    return FILES_ROOT / relative_path


def emit(key: str, value: object) -> None:
    # Step output for GitHub Actions gating
    line = f"{key}={value}"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output_file:
            output_file.write(line + "\n")
    print(line, flush=True)


def _sql_type(dtype: pl.DataType) -> str:
    if isinstance(dtype, pl.Datetime):
        return "timestamptz" if dtype.time_zone else "timestamp"
    simple = {pl.Int64: "bigint", pl.Int32: "integer", pl.Int16: "smallint",
              pl.Float64: "double precision", pl.Float32: "real",
              pl.Boolean: "boolean", pl.Date: "date", pl.String: "text"}
    if (sql_name := simple.get(dtype.base_type())) is None:
        raise TypeError(f"no sql mapping for {dtype}")
    return sql_name


def _ddl(schema: dict[str, pl.DataType] | pl.Schema) -> str:
    return ", ".join(
        f'"{column}" {_sql_type(dtype)}' for column, dtype in dict(schema).items()
    )


def read_table(name: str, columns: list[str] | None = None) -> pl.DataFrame:
    selected = ", ".join(f'"{column}"' for column in columns) if columns else "*"
    query = f"select {selected} from {name}"
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as connection:
            try:
                return pl.read_database(query, connection)
            except psycopg.errors.UndefinedTable as exc:
                raise TableMissing(name) from exc
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        try:
            return connection.sql(query).pl()
        except duckdb.CatalogException as exc:
            raise TableMissing(name) from exc


def write_table(name: str, df: pl.DataFrame, mode: str = "overwrite") -> None:
    schema_name = name.split(".")[0]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(f"create schema if not exists {schema_name}")
            if mode == "overwrite":
                cursor.execute(f"drop table if exists {name}")
            cursor.execute(f"create table if not exists {name} ({_ddl(df.schema)})")
            if df.height:
                columns = ", ".join(f'"{column}"' for column in df.columns)
                copy_sql = f"copy {name} ({columns}) from stdin (format csv, null '')"
                with cursor.copy(copy_sql) as copy_writer:
                    copy_writer.write(df.write_csv(include_header=False))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        connection.execute(f"create schema if not exists {schema_name}")
        connection.register("_df", df.to_arrow())
        if mode == "overwrite":
            connection.execute(f"create or replace table {name} as select * from _df")
        else:
            connection.execute(f"create table if not exists {name} ({_ddl(df.schema)})")
            connection.execute(f"insert into {name} by name select * from _df")


def ensure_table(name: str, schema: dict[str, pl.DataType]) -> None:
    schema_name = name.split(".")[0]
    statements = [f"create schema if not exists {schema_name}",
                  f"create table if not exists {name} ({_ddl(schema)})"]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as connection:
            for statement in statements:
                connection.execute(statement)
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        for statement in statements:
            connection.execute(statement)


def delete_where(name: str, column: str, values: list[str]) -> None:
    if not values:
        return
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(PG_DSN) as connection:
            connection.execute(f'delete from {name} where "{column}" = any(%s)', (values,))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        placeholders = ", ".join("?" for _ in values)
        connection.execute(f'delete from {name} where "{column}" in ({placeholders})', values)
