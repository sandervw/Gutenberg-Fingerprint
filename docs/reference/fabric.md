# Microsoft Fabric reference

## Capacity

- Pause/resume: capacity blade, or REST `.../suspend`, `.../resume` (RBAC `suspend/action`, `resume/action`).
- Pausing settles the smoothed usage backlog as a one-time charge; clears throttling.
- Pause kills availability mid-run; sequence after all work. OneLake storage bills while paused.

## SQL analytics endpoint

- Read-only T-SQL; only Delta tables surface, not `Files/`. dbt materializes into `wh_gold`, reads silver as `<Lakehouse>.dbo.<table>`.
- Metadata syncs from Delta logs in background; lag hits overwrites too. A full `raw_measurements` overwrite served stale data 6+ min after the write, fresh ~25 min later. Interactive notebook runs report `InProgress` until the session closes.
- Force a sync: `fab api -X post "workspaces/<ws>/sqlEndpoints/<id>/refreshMetadata?preview=true" -i "{}"`; returns per-table status.
- Unsupported Delta column types are silently omitted, no error. `TIMESTAMP_NTZ` is unsupported (Lakehouse explorer still shows it). Chain: DuckDB `TIMESTAMP` -> Parquet `isAdjustedToUTC=false` -> Delta `timestamp_ntz` -> dbt "Invalid column name". Fix: export `TIMESTAMPTZ` (`timezone('UTC', col)`) -> `datetime2(6)`.

## Notebooks, Python kernel

- Python 3.12 (Learn says 3.10/3.11). DuckDB, Polars, delta-rs preinstalled.
- delta-rs cannot write Delta through `/lakehouse/default/`: `DeltaError: Failed to parse parquet: External: Generic LocalFileSystem error: Upload aborted`. Raw CSV over the mount works. Use abfss on every `write_deltalake` / `DeltaTable(...)` / `DeltaTable.create(...)`:

```
abfss://<ws>@onelake.dfs.fabric.microsoft.com/<lh>.Lakehouse/Tables/<schema>/<table>
storage_options={"bearer_token": notebookutils.credentials.getToken("storage"), "use_fabric_endpoint": "true"}
```

Token lives ~1 h. Same root for `notebookutils.fs.mount`.

- Schema-enabled lakehouse (`lh_silver`): schema folder is part of the path, `Tables/dbo/works`. Root-level `Tables/<table>` lands in "Unidentified", invisible to the endpoint.
- Writing to a deletion-vector table errors.
- DuckDB INSERT never checkpoints; use delta-rs as the writer.
- Warehouse Delta logs enable `columnMapping`: `deltalake.DeltaTable(<wh abfss>)` -> `DeltaProtocolError: reader features {'columnMapping'} ... not yet supported by the deltalake reader`. Read Warehouse over T-SQL, `notebookutils.data.connect_to_artifact("wh_gold")` -> `conn.query(...)` -> pandas; list tables via `INFORMATION_SCHEMA.TABLES`, `TABLE_TYPE='BASE TABLE'`.
- `%run <Notebook>` shares the caller's session; alone in its cell, else `MagicUsageError: %run cannot run with other code or magic commands`.

## Shipping code

- `fab import -i` takes an item-shaped directory (`x.Notebook/` holding `artifact.content.ipynb`); a bare file posts `"parts": []` -> 400 `InvalidInput`, "Parts: Must be a non-empty collection". Detail needs `debug_enabled true`; log at `%LOCALAPPDATA%\fabric-cli\Logs\`. `--format .py` means Fabric git-source markers, Spark-only; ship `.ipynb`.
- `.ipynb` without kernel metadata lands on Spark (`ModuleNotFoundError: polars`); `language_info` is insufficient. Required top-level and per cell: `kernel_info: {"name": "jupyter", "jupyter_kernel_name": "python3.12"}`, `kernelspec: {"name": "jupyter"}`, `microsoft: {language: python, language_group: jupyter_python}`, plus `dependencies.lakehouse` GUID or `/lakehouse/default/` never mounts.
- `fab` silently omits unknown item types: 1.6.1 drops `DataBuildToolJob` from `ls` and `export -a`. `fab api workspaces/<ws>/items` returns it; definition via raw `POST .../items/<id>/getDefinition`.
- fab console glyphs crash cp1252 consoles (`[UnexpectedError] charmap`) after the API call ran; `fab ls` tells the true outcome. Use PowerShell for `fab` writes.

## dbt

- In-Fabric dbt job item: dbt Core 1.9, adapter dbt-fabric 1.10.0 in practice, Python 3.12, auto-runs `dbt deps`. No `source freshness`, no build caching, no `state:modified`.
- Profile is UI-configured; repo `profiles.yml` ignored, target name uncontrollable. Branch on `target.type == 'fabric'`, never `target.name`.
- `dbt_project.yml` must sit at repo root (error 20418). Ship via `git subtree split --prefix=dbt -b fabric-dbt` + push, point the job at `fabric-dbt`, refresh after dbt changes.
- Wrapper bug: an exposure's `no-op` status reports the run Failed (20402, "No errors", red X, `results: null`) though dbt logs `Completed successfully`. Exclude `exposure:<name>` in Run settings, no `+` prefix. Same for `severity: warn`: one warn fails the job at `ERROR=0`, message shows only `[Warn]` lines. `run_results.json` shows the truth; `severity: warn` is unusable in-Fabric.
- Logs: `az account get-access-token --resource https://storage.azure.com`, GET `https://onelake.dfs.fabric.microsoft.com/<workspaceId>/<itemId>/Output/<runGuid>/logs/dbt.log`. Root `dbt.log` is 0 bytes.

## Pipelines

- Web activity does not support service-principal auth. No tumbling-window triggers.
- `notebookutils.notebook.exit("<string>")` sets the activity's `exitValue`; always a string, `int()` before numeric compare. Never inside try/except; own cell only.
- Refresh SQL Endpoint activity fixes endpoint lag. Output `Success` / `NotRun` / `Failure`; `NotRun` is normal, does not fail the activity. Fails intermittently under concurrent lakehouse writes: run all ingest/transform, then one refresh at the end.
- Deleting a notebook referenced by a pipeline activity 400s: `fab rm` and REST deletes (`items/<id>`, `notebooks/<id>`) return `UnknownError` 400, `isRetriable: false`. Portal right-click Delete works.
