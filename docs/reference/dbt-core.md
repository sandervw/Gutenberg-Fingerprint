# dbt Core reference

Version-gated and Fabric-specific behaviour only. Verify anything else against live dbt docs.

## Sources

`database:`/`schema:` on a source block accept Jinja; `target.name`/`target.type` available. properties.yml is a parse-time context: only `builtins.ref/source/config` and core context vars resolve, no custom macros.

```yaml
sources:
  - name: raw
    database: "{{ 'lh_silver' if target.name == 'fabric' else 'warehouse' }}"
    schema: "{{ 'dbo' if target.name == 'fabric' else 'raw' }}"
```

## Source freshness

Since 1.10, `freshness` and `loaded_at_field` sit under `config:` on the source; top-level is deprecated. Thresholds `warn_after`/`error_after`, each `{count: N, period: minute|hour|day}`. Source-level config inherits to all tables; override or disable per table with a table-level `config: freshness:`. Runs only via `dbt source freshness`; `dbt build` excludes it.

## Tests

Key is `data_tests:`; `tests:` still works. Built-ins: `unique`, `not_null`, `accepted_values`, `relationships`. Since v1.10.5, test arguments go under an `arguments:` wrapper; older versions put them top-level.

```yaml
- accepted_values:
    arguments:
      values: ['placed', 'shipped']
```

`severity`, `where` go under `config:`. Singular tests are `.sql` files in `tests/`; any returned row is a failure.

## Snapshots

Since 1.9, snapshots are pure YAML in `snapshots/`, no SQL block: `name`, `relation: ref(...)`, then `config:` with `unique_key`, `strategy: check|timestamp` (timestamp needs `updated_at`), `check_cols: all` or a list. `target_schema` optional since 1.9. dbt adds `dbt_valid_from`, `dbt_valid_to`, `dbt_scd_id`, `dbt_updated_at`; current rows have `dbt_valid_to = NULL`. Runs via `dbt snapshot` or `dbt build`.

## Hooks

`on-run-end` gains `results` (Result objects: `res.node.name`, `res.node.resource_type`, `res.status`, `res.execution_time`, `res.message`) and `schemas`. Global context vars: `invocation_id`, `run_started_at`. Hooks also fire on compile and docs generate; guard with `{% if execute and results | length > 0 and flags.WHICH in (...) %}`. Audit macros issue their own `run_query()` calls and return nothing.

Fabric: T-SQL has no `CREATE TABLE IF NOT EXISTS`; use `if object_id('...') is null create table ...`.

## CLI

`dbt build` = seed + run + test + snapshot in DAG order. Flags: `--select <model>`, `--select <model>+` (plus downstream), `--exclude`, `--full-refresh`, `--target <name>`.
