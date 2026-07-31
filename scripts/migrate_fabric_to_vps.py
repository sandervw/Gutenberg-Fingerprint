"""One-time migration: Fabric OneLake files/tables down, then up to the VPS."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import polars as pl
import requests
from deltalake import DeltaTable
from deltalake.exceptions import DeltaProtocolError
from deltalake.query import QueryBuilder

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = "gutenberg-fingerprint"
DFS = f"https://onelake.dfs.fabric.microsoft.com/{WORKSPACE}"
ABFSS = f"abfss://{WORKSPACE}@onelake.dfs.fabric.microsoft.com"

VPS = "gufime@15.204.82.199"
KEY = str(Path.home() / ".ssh" / "gufime_rsa")
SSH_OPTS = ["-i", KEY, "-o", "StrictHostKeyChecking=accept-new"]
REMOTE_FILES = "/files/gufime"

# OneLake folder -> path under /files/gufime
FILE_DIRS: dict[str, str] = {
    "lh_bronze.Lakehouse/Files/catalog": "bronze/catalog",
    "lh_bronze.Lakehouse/Files/self": "bronze/self",
    "lh_bronze.Lakehouse/Files/texts": "bronze/texts",
    "lh_silver.Lakehouse/Files/corpus": "silver/corpus",
}

# OneLake delta table -> postgres schema.table
TABLES: dict[str, str] = {
    "lh_bronze.Lakehouse/Tables/catalog": "bronze.catalog",
    "lh_bronze.Lakehouse/Tables/watermark": "bronze.watermark",
    "lh_bronze.Lakehouse/Tables/ingest_audit": "bronze.ingest_audit",
    "lh_bronze.Lakehouse/Tables/strip_audit": "bronze.strip_audit",
    "lh_silver.Lakehouse/Tables/dbo/raw_works": "raw.raw_works",
    "lh_silver.Lakehouse/Tables/dbo/raw_measurements": "raw.raw_measurements",
    "lh_silver.Lakehouse/Tables/dbo/raw_vocab": "raw.raw_vocab",
    "wh_gold.Warehouse/Tables/dbo/snap_dim_work": "main.snap_dim_work",
    "wh_gold.Warehouse/Tables/dbo/dbt_run_log": "main.dbt_run_log",
}

_thread = threading.local()


def get_token() -> str:
    return subprocess.run(
        ["az", "account", "get-access-token", "--resource",
         "https://storage.azure.com", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True,
    ).stdout.strip()


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def ssh(command: str, capture: bool = False) -> str:
    res = run(["ssh", *SSH_OPTS, VPS, command],
              capture_output=capture, text=capture)
    return res.stdout if capture else ""


def session() -> requests.Session:
    if not hasattr(_thread, "s"):
        _thread.s = requests.Session()
    return _thread.s


def list_files(token: str, directory: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    cont = None
    while True:
        params = {"resource": "filesystem", "directory": directory, "recursive": "true"}
        if cont:
            params["continuation"] = cont
        r = requests.get(DFS, headers={"Authorization": f"Bearer {token}"},
                         params=params, timeout=60)
        r.raise_for_status()
        out += [(p["name"], int(p.get("contentLength", 0)))
                for p in r.json().get("paths", []) if p.get("isDirectory") != "true"]
        cont = r.headers.get("x-ms-continuation")
        if not cont:
            return out


def download(token: str, name: str, dest: Path) -> None:
    r = session().get(f"{DFS}/{quote(name)}",
                      headers={"Authorization": f"Bearer {token}"},
                      stream=True, timeout=300)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)


def pull_files(staging: Path) -> None:
    token = get_token()
    for src, sub in FILE_DIRS.items():
        entries = list_files(token, src)
        root = staging / "files" / sub
        # Size match skips already-downloaded files, so reruns resume
        todo = [(name, root / name[len(src) + 1:]) for name, size in entries
                if not ((root / name[len(src) + 1:]).exists()
                        and (root / name[len(src) + 1:]).stat().st_size == size)]
        print(f"{sub}: {len(entries)} files, {len(todo)} to fetch", flush=True)
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(download, token, n, d) for n, d in todo]
            for i, f in enumerate(futures, 1):
                f.result()
                if i % 500 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)


def pull_tables(staging: Path) -> None:
    opts = {"bearer_token": get_token(), "use_fabric_endpoint": "true"}
    tdir = staging / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    for src, dest in TABLES.items():
        table = DeltaTable(f"{ABFSS}/{src}", storage_options=opts)
        try:
            arrow = table.to_pyarrow_table()
        except DeltaProtocolError:
            # Warehouse tables use columnMapping; kernel reader handles it
            arrow = QueryBuilder().register("t", table).execute("select * from t").read_all()
        df = pl.from_arrow(arrow)
        df.write_parquet(tdir / f"{dest}.parquet")
        print(f"{dest}: {df.height:,} rows", flush=True)


def push_files(staging: Path) -> None:
    tar_path = staging / "gufime_files.tar.gz"
    if not tar_path.exists():
        print("packing tarball...", flush=True)
        with tarfile.open(tar_path, "w:gz", compresslevel=6) as tar:
            tar.add(staging / "files", arcname=".")
    print(f"uploading {tar_path.stat().st_size / 1e6:.0f} MB...", flush=True)
    run(["scp", *SSH_OPTS, str(tar_path), f"{VPS}:/tmp/"])
    ssh(f"mkdir -p {REMOTE_FILES}"
        f" && tar -xzf /tmp/gufime_files.tar.gz -C {REMOTE_FILES}"
        f" && rm /tmp/gufime_files.tar.gz")
    print("extracted on VPS", flush=True)


def pg_type(dtype: pl.DataType) -> str:
    if isinstance(dtype, pl.Datetime):
        return "timestamptz" if dtype.time_zone else "timestamp"
    simple = {pl.Int64: "bigint", pl.Int32: "integer", pl.Int16: "smallint",
              pl.Float64: "double precision", pl.Float32: "real",
              pl.Boolean: "boolean", pl.Date: "date", pl.String: "text"}
    for k, v in simple.items():
        if dtype == k:
            return v
    raise TypeError(f"no postgres mapping for {dtype}")


def push_tables(staging: Path) -> None:
    tdir = staging / "tables"
    lines = [f"create schema if not exists {s};" for s in ("bronze", "raw", "main")]
    for dest in TABLES.values():
        df = pl.read_parquet(tdir / f"{dest}.parquet")
        df.write_csv(tdir / f"{dest}.csv")
        cols = ", ".join(f'"{c}" {pg_type(t)}' for c, t in df.schema.items())
        lines += [f"drop table if exists {dest};",
                  f"create table {dest} ({cols});",
                  f"\\copy {dest} from '{dest}.csv' with (format csv, header true, null '')"]
    (tdir / "load.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ssh("mkdir -p /tmp/gufime_tables")
    csvs = [str(tdir / f"{d}.csv") for d in TABLES.values()]
    run(["scp", *SSH_OPTS, *csvs, str(tdir / "load.sql"), f"{VPS}:/tmp/gufime_tables/"])
    ssh("cd /tmp/gufime_tables && psql -d gufime -v ON_ERROR_STOP=1 -f load.sql"
        " && cd / && rm -r /tmp/gufime_tables")
    print("tables loaded", flush=True)


def verify(staging: Path) -> None:
    finds = " ; ".join(f"find {REMOTE_FILES}/{sub} -type f | wc -l"
                       for sub in FILE_DIRS.values())
    remote = ssh(finds, capture=True).split()
    ok = True
    for sub, count in zip(FILE_DIRS.values(), remote):
        local = sum(1 for p in (staging / "files" / sub).rglob("*") if p.is_file())
        match = local == int(count)
        ok &= match
        print(f"files {sub}: local {local}  vps {count}  {'OK' if match else 'MISMATCH'}")
    query = " union all ".join(f"select '{d}', count(*) from {d}" for d in TABLES.values())
    rows = dict(line.split("|") for line in
                ssh(f'psql -d gufime -tAc "{query}"', capture=True).strip().splitlines())
    for dest in TABLES.values():
        local = pl.read_parquet(staging / "tables" / f"{dest}.parquet").height
        match = local == int(rows[dest])
        ok &= match
        print(f"table {dest}: local {local}  vps {rows[dest]}  {'OK' if match else 'MISMATCH'}")
    print("ALL VERIFIED" if ok else "MISMATCHES FOUND", flush=True)


STEPS = {"pull-files": pull_files, "pull-tables": pull_tables,
         "push-files": push_files, "push-tables": push_tables, "verify": verify}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", default="C:/gufime-migration")
    parser.add_argument("--only", choices=list(STEPS), nargs="*")
    args = parser.parse_args()
    staging = Path(args.staging)
    for name in args.only or list(STEPS):
        print(f"== {name} ==", flush=True)
        STEPS[name](staging)


if __name__ == "__main__":
    main()
