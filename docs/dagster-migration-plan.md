# Dagster migration plan (POC)

Hand this to a fresh Claude instance. It contains every repo fact needed; **do not go exploring**.

## Goal

Run the pipeline on **Dagster OSS** on the OVH box, reusing the existing Postgres for Dagster metadata. Wrap the existing `python.workflow.*` logic as Dagster assets. A sensor gates the downstream pipeline on the CDC count.

## Repo facts

- Repo root has `python/` (importable package; modules run as `python -m python.workflow.<name>`), `dbt/`, `evidence/`, `infra/tofu/`, `pyproject.toml`, `uv.lock`.
- Python runs via **uv** (`uv run ...`). dbt has a `postgres` target. Evidence is Node.
- Postgres access uses `GUFIME_TARGET=postgres` and peer auth over the unix socket.
- The four ingestion modules hold their logic in `if __name__ == "__main__":` blocks (`catalog_ingest.py:108`, `text_ingest.py:179`, `strip.py`, `measure.py:107`). `backup.py` takes a CLI arg (`corpus`/`pg`).
- Python rules live in `docs/reference/python-rules.md`; obey them in all new/edited files.

## Pipeline steps

Eight steps become assets. `catalog` and `pg_backup` run every night. A sensor launches the middle six when `new_count > 0`.

1. `python -m python.workflow.catalog_ingest` prints `new_count=<N>`.
2. `python -m python.workflow.text_ingest`
3. `python -m python.workflow.strip`
4. `python -m python.workflow.measure`
5. `dbt deps && dbt build --target postgres` (cwd `dbt/`)
6. `npm run sources && npm run build`, then `wrangler pages deploy build --project-name=gutenberg-fingerprint --branch=main` (cwd `evidence/`, needs `CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token)`)
7. `python -m python.workflow.backup corpus`
8. `python -m python.workflow.backup pg` (runs every night)

## Scope

**In:** the 8 steps as assets, a nightly schedule, one gate sensor, Postgres-backed Dagster storage, two systemd services, a validation pass, Cloudflare-tunnel instructions for the user.

**Out:** `dagster-dbt` model-level assets, partitions, retries, alerts, IO-manager customization, backfills, tests beyond validation, `strip.py`'s line-count rule.

## Step 1 — Install

```bash
uv add dagster dagster-webserver dagster-postgres
```

## Step 2 — Refactor the 4 ingestion modules

For `catalog_ingest.py`, `text_ingest.py`, `strip.py`, `measure.py`: move the `if __name__ == "__main__":` body into a top-level `def main() -> None:`, then restore the guard:

```python
def main() -> None:
    ...
if __name__ == "__main__":
    main()
```

`catalog_ingest.main` returns the new-count int and keeps printing `new_count=`:

```python
def main() -> int:
    ...
    print(f"new_count={new_count}")
    return new_count
```

Leave `backup.py` unchanged.

## Step 3 — Dagster package `python/dagster/`

**`__init__.py`** — empty.

**`assets.py`** — Python steps import and call `main()`; dbt, Evidence, and backup shell out. `catalog` publishes `new_count` as metadata. Assets are pure `deps` chains.

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import dagster as dg

from python.workflow import catalog_ingest, text_ingest, strip, measure

REPO = Path(__file__).resolve().parents[2]

def _sh(cmd: str, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, shell=True, check=True)

@dg.asset
def catalog() -> dg.MaterializeResult:
    n = catalog_ingest.main()
    return dg.MaterializeResult(metadata={"new_count": n})

@dg.asset(deps=[catalog])
def texts() -> None:
    text_ingest.main()

@dg.asset(deps=[texts])
def stripped() -> None:
    strip.main()

@dg.asset(deps=[stripped])
def measures() -> None:
    measure.main()

@dg.asset(deps=[measures])
def dbt_build() -> None:
    _sh("uv run dbt deps && uv run dbt build --target postgres", REPO / "dbt")

@dg.asset(deps=[dbt_build])
def site() -> None:
    _sh("npm run sources && npm run build", REPO / "evidence")
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "wrangler pages deploy build "
        "--project-name=gutenberg-fingerprint --branch=main",
        REPO / "evidence",
    )

@dg.asset(deps=[site])
def corpus_backup() -> None:
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup corpus",
        REPO,
    )

@dg.asset
def pg_backup() -> None:
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup pg",
        REPO,
    )
```

**`definitions.py`** — two jobs, a nightly schedule on `catalog_job`, and the gate sensor.

```python
from __future__ import annotations

import dagster as dg

from . import assets

all_assets = dg.load_assets_from_modules([assets])

catalog_job = dg.define_asset_job(
    "catalog_job", selection=["catalog", "pg_backup"]
)
downstream_job = dg.define_asset_job(
    "downstream_job",
    selection=[
        "texts", "stripped", "measures", "dbt_build", "site", "corpus_backup"
    ],
)

nightly_schedule = dg.ScheduleDefinition(
    name="nightly", job=catalog_job, cron_schedule="0 8 * * *"
)

@dg.asset_sensor(
    asset_key=dg.AssetKey("catalog"),
    job=downstream_job,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def gate(
    context: dg.SensorEvaluationContext, asset_event: dg.EventLogEntry
) -> dg.RunRequest | dg.SkipReason:
    materialization = asset_event.asset_materialization
    new_count = materialization.metadata["new_count"].value
    if new_count > 0:
        return dg.RunRequest()
    return dg.SkipReason("no new works")

defs = dg.Definitions(
    assets=all_assets,
    jobs=[catalog_job, downstream_job],
    schedules=[nightly_schedule],
    sensors=[gate],
)
```

## Step 4 — Instance config

**`pyproject.toml`** — add:

```toml
[tool.dagster]
module_name = "python.dagster.definitions"
code_location_name = "gufime"
```

**`infra/dagster/dagster.yaml`**:

```yaml
storage:
  postgres:
    postgres_url:
      env: DAGSTER_PG_URL
```

Box `DAGSTER_PG_URL`: `postgresql://gufime@/gufime?host=/var/run/postgresql`.

## Step 5 — Python rules (`docs/reference/python-rules.md`)

Every new/edited file: `from __future__ import annotations` first; full type annotations; imports grouped stdlib / third-party / local; f-strings only; explicit exception types; context managers for resources; ≤300 lines (new files only); in-code comments ≤12 words.

## Step 6 — Infra (`infra/tofu/provision.tf`)

Two services under `/code/gufime`, both with `DAGSTER_HOME=/files/gufime/dagster` (holds `dagster.yaml`), `GUFIME_TARGET=postgres`, and `DAGSTER_PG_URL` in the environment. Webserver binds to `127.0.0.1`.

- `dagster-webserver.service`: `ExecStart=/home/gufime/.local/bin/uv run dagster-webserver -h 127.0.0.1 -p 3000`
- `dagster-daemon.service`: `ExecStart=/home/gufime/.local/bin/uv run dagster-daemon run`

Provision with a `terraform_data` block whose `remote-exec` provisioner writes the units, runs `systemctl daemon-reload`, and `systemctl enable --now` on both. Then delete `nightly.yml` and `reprocess.yml`.

## Step 7 — Validation

Local:

```bash
uv run python -c "from python.dagster.definitions import defs; print('ok')"
uv run dagster definitions validate
```

On the box: open the UI, confirm the 8-asset graph, the `nightly` schedule, and the running `gate` sensor appear. Materialize `catalog_job`; when `new_count > 0`, confirm the sensor launches `downstream_job` to a green run.

## Step 8 — USER STEP: Cloudflare Tunnel + Access

Gate the UI behind a Cloudflare Tunnel with Access. Do not expose port 3000.

1. On the box: install `cloudflared`, then `cloudflared tunnel login` (interactive browser).
2. `cloudflared tunnel create gufime-dagster`.
3. Map `dagster.gufime.com` → `http://localhost:3000` in the tunnel `ingress:` config, then `cloudflared tunnel route dns gufime-dagster dagster.gufime.com`.
4. `cloudflared service install`.
5. Dashboard: **Zero Trust → Access → Applications**, add a self-hosted app for `dagster.gufime.com` with an email one-time-PIN policy.

## Operating notes

- Nightly: the schedule fires `catalog_job` (`catalog` + `pg_backup`).
- The `gate` sensor reads `catalog`'s `new_count` and launches `downstream_job` when it is `> 0`.
- Manual full rebuild: **Materialize all** in the UI.
- Selective rebuild: materialize any asset directly.
