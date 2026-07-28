# CLAUDE.md

Nightly CDC pipeline over the Project Gutenberg sci-fi/fantasy corpus: Fabric (Lakehouse + Warehouse + Data Factory) → dbt → Evidence, published to Cloudflare Pages at https://gufime.com/.

`README.md` is the architecture. `docs/Project-Outline.md` is the design and the roadmap. `docs/reference/` holds verified tech notes.

## Rules

- **Never add, stage, or commit to git.**
- **All comments, descriptions, and other forms of 'in-code documentation', must be 12 words or fewer. No exceptions.**
- Check `docs/reference/` first for tech specs; if it isn't covered there, fetch current docs (Context7 / Microsoft Learn MCP / official sources), then update the ref file.
- Treat Fabric and Azure as unreliable.
- **No verification nagging.** When something ran and passed, it's done. Name the next concrete step instead.
- For a significant or hard-to-reverse design choice, give the options and a recommendation before committing to it.

## Facts that bite

- dbt models must compile on **both** targets: `duckdb` (local dev) and `fabric` (T-SQL, prod). Cross-db `dbt_utils` macros, or dispatch per adapter.
- Fabric's dbt job builds a branch **from its root** with no folder-path option, so `dbt/` is subtree-split onto the `fabric-dbt` branch by `.github/workflows/sync-fabric-dbt.yml`. Fabric service updates have broken this path before.
- Everything in `fabric/` is source-controlled and deployed by `scripts/deploy_fabric.py` (fabric-cicd); `fabric/parameter.yml` maps baked-in GUIDs to variables.
- The capacity must be **running during the Cloudflare build**: `evidence/scripts/fetch-sources.js` pulls parquet from OneLake, and a paused capacity rejects OneLake calls. Suspend is the last step in the Logic App.
- Evidence reads parquet from `evidence/data/warehouse/`, not `sources/`. Run `npm run sources` (not just `build`) or the extract comes back cached. `Error in Data Table: Dataset is empty` in the build log is known noise.
- Reading OneLake Delta from the laptop: `az account get-access-token --resource https://storage.azure.com`, then `deltalake.DeltaTable(uri, storage_options={"bearer_token": tok, "use_fabric_endpoint": "true"})`, with `PYTHONIOENCODING=utf-8`. `az` may default to a tenant-level account showing no subscriptions; `az account list --refresh`, then `az account set`.
- Site styling mirrors wordleaves.com (`evidence/sparse.css` + `evidence/wordleaves.css`): cream/charcoal, copper accent, iA Writer Quattro.

## Environment

Windows 11, PowerShell, VS Code. Python via `uv` (`uv run ...`), Node 24 for Evidence (pinned in `evidence/.node-version`).
