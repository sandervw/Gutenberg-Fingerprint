# Backup: pg dump and corpus tar to R2 via wrangler.

from __future__ import annotations

import hashlib
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from python.helpers import storage

BUCKET = "gufime-backup"
PART_SIZE = 250 * 1024 * 1024  # under wrangler's 315 MB object cap
CHUNK = 8 * 1024 * 1024

# %% wrangler wrappers

def put_file(key: str, path: Path) -> None:
    subprocess.run(
        ["wrangler", "r2", "object", "put", f"{BUCKET}/{key}", f"--file={path}", "--remote"],
        check=True,
    )

def put_stream(key: str, payload: Iterable[bytes]) -> None:
    process = subprocess.Popen(
        ["wrangler", "r2", "object", "put", f"{BUCKET}/{key}", "--pipe", "--remote"],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    for chunk in payload:
        process.stdin.write(chunk)
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"wrangler put failed for {key}")

# %% Modes

def backup_pg(work: Path) -> None:
    dump = work / "gufime.dump"
    subprocess.run(
        ["pg_dump", "-Fc", "-f", str(dump), storage.POSTGRES_CONNECTION_STRING],
        check=True,
    )
    put_file("pg/gufime.dump", dump)
    print(f"pg backup: {dump.stat().st_size:,} bytes -> {BUCKET}/pg/gufime.dump")

def backup_corpus(work: Path) -> None:
    archive = work / "corpus.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=6) as tar:
        tar.add(storage.FILES_ROOT, arcname=".")
    manifest: list[str] = []
    with archive.open("rb") as handle:
        index = 0
        while head := handle.read(CHUNK):
            digest = hashlib.sha256()
            name = f"corpus.tar.gz.{index:02d}"

            def window() -> Iterator[bytes]:
                remaining, chunk = PART_SIZE, head
                while chunk:
                    digest.update(chunk)
                    remaining -= len(chunk)
                    yield chunk
                    if remaining == 0:
                        break
                    chunk = handle.read(min(CHUNK, remaining))

            put_stream(f"corpus/{name}", window())
            manifest.append(f"{digest.hexdigest()}  {name}")
            index += 1
    # Manifest lists live parts; restore ignores stale ones
    put_stream("corpus/corpus.manifest", ["\n".join(manifest).encode() + b"\n"])
    print(f"corpus backup: {index} parts -> {BUCKET}/corpus/")

# %% Run

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("pg", "corpus"):
        sys.exit("usage: python -m python.workflow.backup pg|corpus")
    with tempfile.TemporaryDirectory(prefix="gufime-backup.") as scratch:
        (backup_pg if mode == "pg" else backup_corpus)(Path(scratch))
