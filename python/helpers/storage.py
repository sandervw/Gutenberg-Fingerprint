"""Storage seam: one pipeline codebase, duckdb locally, postgres on the VPS."""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TARGET = os.environ.get("GUFIME_TARGET", "duckdb")
DUCKDB_PATH = os.environ.get("GUFIME_DUCKDB_PATH", str(REPOSITORY_ROOT / "dbt" / "warehouse.duckdb"))
POSTGRES_CONNECTION_STRING = os.environ.get("GUFIME_PG_DSN", "dbname=gufime")
FILES_ROOT = Path(
    os.environ.get("GUFIME_FILES_ROOT")
    or ("/files/gufime" if TARGET == "postgres" else REPOSITORY_ROOT / "data" / "files")
)

# Shared by the workflow scripts
UTC_DATETIME_TYPE: pl.Datetime = pl.Datetime("us", "UTC")
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


def _sql_type(data_type: pl.DataType) -> str:
    if isinstance(data_type, pl.Datetime):
        return "timestamptz" if data_type.time_zone else "timestamp"
    simple = {pl.Int64: "bigint", pl.Int32: "integer", pl.Int16: "smallint",
              pl.Float64: "double precision", pl.Float32: "real",
              pl.Boolean: "boolean", pl.Date: "date", pl.String: "text"}
    if (sql_name := simple.get(data_type.base_type())) is None:
        raise TypeError(f"no sql mapping for {data_type}")
    return sql_name


def _column_definitions(schema: dict[str, pl.DataType] | pl.Schema) -> str:
    return ", ".join(
        f'"{column_name}" {_sql_type(data_type)}' for column_name, data_type in dict(schema).items()
    )


def _normalize_utc(dataframe: pl.DataFrame) -> pl.DataFrame:
    # Postgres timestamptz round-trips as Etc/UTC; align to literals' UTC label.
    casts = [
        pl.col(column_name).cast(pl.Datetime(data_type.time_unit, "UTC"))
        for column_name, data_type in dataframe.schema.items()
        if isinstance(data_type, pl.Datetime) and data_type.time_zone not in (None, "UTC")
    ]
    return dataframe.with_columns(casts) if casts else dataframe


def read_table(name: str, columns: list[str] | None = None) -> pl.DataFrame:
    selected = ", ".join(f'"{column_name}"' for column_name in columns) if columns else "*"
    query = f"select {selected} from {name}"
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(POSTGRES_CONNECTION_STRING) as connection:
            try:
                dataframe = pl.read_database(query, connection)
            except psycopg.errors.UndefinedTable as exception:
                raise TableMissing(name) from exception
        return _normalize_utc(dataframe)
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        try:
            return connection.sql(query).pl()
        except duckdb.CatalogException as exception:
            raise TableMissing(name) from exception


def write_table(name: str, dataframe: pl.DataFrame, mode: str = "overwrite") -> None:
    schema_name = name.split(".")[0]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(POSTGRES_CONNECTION_STRING) as connection, connection.cursor() as cursor:
            cursor.execute(f"create schema if not exists {schema_name}")
            if mode == "overwrite":
                cursor.execute(f"drop table if exists {name} cascade")
            cursor.execute(f"create table if not exists {name} ({_column_definitions(dataframe.schema)})")
            if dataframe.height:
                column_names = ", ".join(f'"{column_name}"' for column_name in dataframe.columns)
                copy_sql = f"copy {name} ({column_names}) from stdin (format csv, null '')"
                with cursor.copy(copy_sql) as copy_writer:
                    copy_writer.write(dataframe.write_csv(include_header=False))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        connection.execute(f"create schema if not exists {schema_name}")
        connection.register("_dataframe", dataframe.to_arrow())
        if mode == "overwrite":
            connection.execute(f"drop table if exists {name} cascade")
            connection.execute(f"create table {name} as select * from _dataframe")
        else:
            connection.execute(f"create table if not exists {name} ({_column_definitions(dataframe.schema)})")
            connection.execute(f"insert into {name} by name select * from _dataframe")


def ensure_table(name: str, schema: dict[str, pl.DataType]) -> None:
    schema_name = name.split(".")[0]
    statements = [f"create schema if not exists {schema_name}",
                  f"create table if not exists {name} ({_column_definitions(schema)})"]
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(POSTGRES_CONNECTION_STRING) as connection:
            for statement in statements:
                connection.execute(statement)
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        for statement in statements:
            connection.execute(statement)


def delete_where(name: str, column_name: str, values: list[str]) -> None:
    if not values:
        return
    if TARGET == "postgres":
        import psycopg

        with psycopg.connect(POSTGRES_CONNECTION_STRING) as connection:
            connection.execute(f'delete from {name} where "{column_name}" = any(%s)', (values,))
        return
    import duckdb

    with duckdb.connect(DUCKDB_PATH) as connection:
        placeholders = ", ".join("?" for _ in values)
        connection.execute(f'delete from {name} where "{column_name}" in ({placeholders})', values)
