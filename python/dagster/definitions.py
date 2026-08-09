from __future__ import annotations

import os

import dagster
from dagster_dbt import DbtCliResource

from . import assets

all_assets = dagster.load_assets_from_modules([assets])

catalog_job = dagster.define_asset_job(
    "catalog_job",
    selection=["catalog"],
    description="Poll Project Gutenberg catalog: gates the nightly downstream run.",
)
# Everything downstream of catalog; catalog itself is sensor-gated.
_catalog = dagster.AssetSelection.keys("catalog")
downstream_job = dagster.define_asset_job(
    "downstream_job",
    selection=_catalog.downstream() - _catalog,
    description="Run Pipeline: when new/changed works detected, reprocess, rebuild, deploy.",
)

nightly_schedule = dagster.ScheduleDefinition(
    name="nightly",
    job=catalog_job,
    cron_schedule="0 3 * * *",
    execution_timezone="America/Chicago",
    description="Nightly 03:00 Central catalog poll.",
)


@dagster.asset_sensor(
    asset_key=dagster.AssetKey("catalog"),
    job=downstream_job,
    default_status=dagster.DefaultSensorStatus.RUNNING,
    description="Fire downstream job only when catalog finds new works.",
)
def gate(
    context: dagster.SensorEvaluationContext, asset_event: dagster.EventLogEntry
) -> dagster.RunRequest | dagster.SkipReason:
    materialization = asset_event.asset_materialization
    new_count = materialization.metadata["new_count"].value
    if new_count > 0:
        return dagster.RunRequest()
    return dagster.SkipReason("no new works")


defs = dagster.Definitions(
    assets=all_assets,
    jobs=[catalog_job, downstream_job],
    schedules=[nightly_schedule],
    sensors=[gate],
    resources={
        "dbt": DbtCliResource(
            project_dir=assets.dbt_project,
            target=os.environ.get("GUFIME_TARGET", "duckdb"),
        )
    },
)
