"""Upload the self corpus to bronze Files/self/<work_id>.md, seed CSV as manifest."""

import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

FICTION_ROOT = Path("C:/Users/Sander/OneDrive/Documents/Github/Fiction-Fingerprint")
SEED = Path(__file__).parents[1] / "dbt" / "seeds" / "seed_authors.csv"
DEST = "gutenberg-fingerprint.Workspace/lh_bronze.Lakehouse/Files/self"

env = {**os.environ, "PYTHONUTF8": "1"}

with SEED.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

# fab copy keeps the source filename, so stage each file renamed to its work_id.
with tempfile.TemporaryDirectory() as staging:
    for row in rows:
        staged = Path(staging) / f"{row['work_id']}.md"
        shutil.copyfile(FICTION_ROOT / row["path"], staged)
        subprocess.run(["fab", "copy", str(staged), DEST, "-f"], check=True, env=env)
        print(f"uploaded {staged.name}")

print(f"{len(rows)} works -> {DEST}")
