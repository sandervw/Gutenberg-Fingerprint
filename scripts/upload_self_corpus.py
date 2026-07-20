"""Upload manual corpus works to bronze Files/self/<work_id>.md.

Stamps loaded_at on the uploaded rows in the seed, then ships the refreshed
seed alongside the files as Files/self/_manifest.csv - nb_measure's watermark
for manual works.

Usage: python upload_self_corpus.py [work_id ...]   (no args = all works)
"""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FICTION_ROOT = Path("C:/Users/Sander/OneDrive/Documents/Github/Fiction-Fingerprint")
SEED = Path(__file__).parents[1] / "dbt" / "seeds" / "seed_authors.csv"
DEST = "gutenberg-fingerprint.Workspace/lh_bronze.Lakehouse/Files/self"

env = {**os.environ, "PYTHONUTF8": "1"}

with SEED.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

picked = set(sys.argv[1:]) or {row["work_id"] for row in rows}
unknown = picked - {row["work_id"] for row in rows}
if unknown:
    sys.exit(f"not in seed: {', '.join(sorted(unknown))}")

stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
for row in rows:
    if row["work_id"] in picked:
        row["loaded_at"] = stamp

with SEED.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

# fab copy keeps the source filename, so stage each file renamed to its work_id.
with tempfile.TemporaryDirectory() as staging:
    for row in rows:
        if row["work_id"] not in picked:
            continue
        staged = Path(staging) / f"{row['work_id']}.md"
        shutil.copyfile(FICTION_ROOT / row["path"], staged)
        subprocess.run(["fab", "copy", str(staged), DEST, "-f"], check=True, env=env)
        print(f"uploaded {staged.name}")
    manifest = Path(staging) / "_manifest.csv"
    shutil.copyfile(SEED, manifest)
    subprocess.run(["fab", "copy", str(manifest), DEST, "-f"], check=True, env=env)

print(f"{len(picked)} works + manifest -> {DEST}")
