from __future__ import annotations

import os
import subprocess
from pathlib import Path

import dagster
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from python.workflow import catalog_ingest, text_ingest, strip, measure

REPO = Path(__file__).resolve().parents[2]

# Prebuilt manifest in prod; regenerated under `dagster dev`.
dbt_project = DbtProject(project_dir=REPO / "dbt")
dbt_project.prepare_if_dev()


def _sh(cmd: str, cwd: Path) -> None:
    env = {**os.environ, "PATH": f"{Path.home() / '.local' / 'bin'}:{os.environ.get('PATH', '')}"}
    subprocess.run(cmd, cwd=cwd, shell=True, check=True, env=env)


@dagster.asset
def catalog() -> dagster.MaterializeResult:
    """Catalog ingest: PG feed -> bronze catalog table + raw CSV snapshot."""
    n = catalog_ingest.main()
    return dagster.MaterializeResult(metadata={"new_count": n})


@dagster.asset(deps=[catalog], key_prefix="raw")
def raw_works() -> None:
    """Table node: raw_works, written by catalog."""


@dagster.asset(deps=[catalog])
def texts() -> None:
    """Text ingest: download new/changed/failed works from PG's mirror into bronze."""
    text_ingest.main()


@dagster.asset(deps=[texts])
def stripped() -> None:
    """Strip: bronze texts -> silver corpus markdown, minus PG boilerplate."""
    strip.main()


@dagster.asset(deps=[stripped])
def measures() -> None:
    """Measure: corpus markdown -> raw_measurements + raw_vocab, incremental by watermark."""
    measure.main()


@dagster.asset(deps=[measures], key_prefix="raw")
def raw_measurements() -> None:
    """Table node: raw_measurements, written by measures."""


@dagster.asset(deps=[measures], key_prefix="raw")
def raw_vocab() -> None:
    """Table node: raw_vocab, written by measures."""


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_models(context, dbt: DbtCliResource):
    """dbt: build gold marts; each node its own lineage asset."""
    yield from dbt.cli(["build"], context=context).stream()


@dagster.asset(deps=list(dbt_models.keys))
def postgres_backup() -> None:
    """Postgres Backup: dump full gufime postgres DB to cloudflare R2 via wrangler."""
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup postgres",
        REPO,
    )


@dagster.asset(deps=[postgres_backup])
def corpus_backup() -> None:
    """Corpus Backup: dump full corpus (bronze+silver) to cloudflare R2 as .tar.gz."""
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup corpus",
        REPO,
    )


@dagster.asset(deps=[corpus_backup])
def site() -> None:
    """Gufime Site Deploy: build evidence site and deploy to cloudflare."""
    # Cap node heap so the build can't balloon and OOM the box.
    _sh("NODE_OPTIONS=--max-old-space-size=1536 npm run sources && npm run build", REPO / "evidence")
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "wrangler pages deploy build "
        "--project-name=gutenberg-fingerprint --branch=main",
        REPO / "evidence",
    )
