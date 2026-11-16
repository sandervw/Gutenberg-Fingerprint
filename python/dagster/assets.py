from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

import dagster
from python.workflow import catalog_ingest, measure, strip, text_ingest

REPO = Path(__file__).resolve().parents[2]

# Prebuilt manifest in prod; regenerated under `dagster dev`.
dbt_project = DbtProject(project_dir=REPO / "dbt")
dbt_project.prepare_if_dev()

# Two retries, about one then three minutes later, jittered.
NETWORK_RETRY = dagster.RetryPolicy(
    max_retries=2, delay=60, backoff=dagster.Backoff.EXPONENTIAL, jitter=dagster.Jitter.PLUS_MINUS
)


def _run_shell(command: str, cwd: Path) -> None:
    """Run a shell command with uv on PATH; fail on error."""
    environment = {**os.environ, "PATH": f"{Path.home() / '.local' / 'bin'}:{os.environ.get('PATH', '')}"}
    subprocess.run(command, cwd=cwd, shell=True, check=True, env=environment)


@dagster.asset(retry_policy=NETWORK_RETRY)
def catalog() -> dagster.MaterializeResult:
    """Catalog ingest: PG feed -> bronze catalog table + raw CSV snapshot."""
    new_count = catalog_ingest.main()
    return dagster.MaterializeResult(metadata={"new_count": new_count})


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


# Dagster rejects a string-form context annotation; leave it bare.
@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_models(context, dbt: DbtCliResource) -> Iterator[object]:  # noqa: ANN001
    """dbt: build gold marts; each node its own lineage asset."""
    yield from dbt.cli(["build"], context=context).stream()


@dagster.asset(deps=list(dbt_models.keys), retry_policy=NETWORK_RETRY)
def postgres_backup() -> None:
    """Postgres Backup: dump full gufime postgres DB to cloudflare R2 via wrangler."""
    _run_shell(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup postgres",
        REPO,
    )


@dagster.asset(deps=[postgres_backup], retry_policy=NETWORK_RETRY)
def corpus_backup() -> None:
    """Corpus Backup: dump full corpus (bronze+silver) to cloudflare R2 as .tar.gz."""
    _run_shell(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup corpus",
        REPO,
    )


@dagster.asset(deps=[corpus_backup], retry_policy=NETWORK_RETRY)
def site() -> None:
    """Gufime Site Deploy: build evidence site and deploy to cloudflare."""
    # Cap node heap so the build can't balloon and OOM the box.
    _run_shell("NODE_OPTIONS=--max-old-space-size=1536 npm run sources && npm run build", REPO / "evidence")
    _run_shell(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "wrangler pages deploy build "
        "--project-name=gutenberg-fingerprint --branch=main",
        REPO / "evidence",
    )
