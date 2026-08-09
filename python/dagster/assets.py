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
    n = catalog_ingest.main()
    return dagster.MaterializeResult(metadata={"new_count": n})


@dagster.asset(deps=[catalog])
def texts() -> None:
    text_ingest.main()


@dagster.asset(deps=[texts])
def stripped() -> None:
    strip.main()


@dagster.asset(deps=[stripped])
def measures() -> None:
    measure.main()


@dagster.asset(deps=[measures])
def dbt_build() -> None:
    _sh("uv run dbt deps && uv run dbt build --target postgres", REPO / "dbt")


@dagster.asset(deps=[dbt_build])
def pg_backup() -> None:
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup pg",
        REPO,
    )


@dagster.asset(deps=[pg_backup])
def corpus_backup() -> None:
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "uv run python -m python.workflow.backup corpus",
        REPO,
    )


@dagster.asset(deps=[corpus_backup])
def site() -> None:
    _sh("npm run sources && npm run build", REPO / "evidence")
    _sh(
        "CLOUDFLARE_API_TOKEN=$(cat ~/.config/gufime/cf_token) "
        "wrangler pages deploy build "
        "--project-name=gutenberg-fingerprint --branch=main",
        REPO / "evidence",
    )
