from __future__ import annotations

import os
import subprocess
from pathlib import Path

import dagster

from python.workflow import catalog_ingest, text_ingest, strip, measure

REPO = Path(__file__).resolve().parents[2]


def _sh(cmd: str, cwd: Path) -> None:
    env = {**os.environ, "PATH": f"{Path.home() / '.local' / 'bin'}:{os.environ.get('PATH', '')}"}
    subprocess.run(cmd, cwd=cwd, shell=True, check=True, env=env)


@dagster.asset
def catalog() -> dagster.MaterializeResult:
    """Catalog ingest: PG feed -> bronze catalog table + raw CSV snapshot."""
    n = catalog_ingest.main()
    return dagster.MaterializeResult(metadata={"new_count": n})


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


@dagster.asset(deps=[measures])
def dbt_build() -> None:
    """dbt: build gold layer marts from raw bronze source tables."""
    _sh("uv run dbt deps && uv run dbt build --target postgres", REPO / "dbt")


@dagster.asset(deps=[dbt_build])
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
    _sh("npm run sources && npm run build", REPO / "evidence")
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "wrangler pages deploy build "
        "--project-name=gutenberg-fingerprint --branch=main",
        REPO / "evidence",
    )
