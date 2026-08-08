from __future__ import annotations

import dagster

from . import assets

all_assets = dagster.load_assets_from_modules([assets])

catalog_job = dagster.define_asset_job(
    "catalog_job", selection=["catalog", "pg_backup"]
)
downstream_job = dagster.define_asset_job(
    "downstream_job",
    selection=[
        "texts", "stripped", "measures", "dbt_build", "site", "corpus_backup"
    ],
)

nightly_schedule = dagster.ScheduleDefinition(
    name="nightly", job=catalog_job, cron_schedule="0 8 * * *"
)


@dagster.asset_sensor(
    asset_key=dagster.AssetKey("catalog"),
    job=downstream_job,
    default_status=dagster.DefaultSensorStatus.RUNNING,
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
)
