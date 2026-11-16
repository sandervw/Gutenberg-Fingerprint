# Dagster reference

Verified against dagster 1.13 and dagster-dbt 0.29.

- `@dbt_assets` functions take `(context, dbt: DbtCliResource)` and `yield from dbt.cli(["build"], context=context).stream()`.
- Leave `context` unannotated in modules that use `from __future__ import annotations`.
- An asset's docstring is its description in the UI. Asset keys come from function names plus `key_prefix`.
- `uv run dagster definitions validate` loads the code location the way the daemon does.
- `@dagster.asset(retry_policy=dagster.RetryPolicy(max_retries, delay, backoff, jitter))` retries the step inside the run. `Backoff.EXPONENTIAL` with `delay=60` waits 60 then 180 seconds.
- The instance has no run retries, so a step that exhausts its retries fails the run once and `run_failure_sensor` fires once.
