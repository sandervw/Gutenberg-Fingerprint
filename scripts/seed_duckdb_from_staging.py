"""One-time: seed local duckdb from the migration staging parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", default="C:/gufime-migration")
    parser.add_argument("--db", default=str(REPO / "dbt" / "warehouse.duckdb"))
    args = parser.parse_args()

    con = duckdb.connect(args.db)
    for parquet in sorted(Path(args.staging, "tables").glob("*.parquet")):
        name = parquet.stem
        schema = name.split(".")[0]
        con.execute(f"create schema if not exists {schema}")
        con.execute(f"create or replace table {name} as select * from read_parquet(?)",
                    [str(parquet)])
        rows = con.execute(f"select count(*) from {name}").fetchone()[0]
        print(f"{name}: {rows:,} rows")
    con.close()


if __name__ == "__main__":
    main()
