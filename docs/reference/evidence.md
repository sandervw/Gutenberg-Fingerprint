# Evidence.dev reference

## Layout

```
sources/warehouse/connection.yaml   # type: duckdb, filename: ':memory:'
data/warehouse/*.parquet            # gold marts, downloaded
src/pages/                          # folders = URLs; [param].md = templated
```

## Parquet source

- `scripts/fetch-sources.js` (hooked `prebuild`/`predev`/`presources`) downloads `lh_silver/Files/exports/*.parquet` into `evidence/data/warehouse/` over OneLake DFS REST with a client-credentials token. Paused capacity rejects all OneLake transactions.
- `filename` required; `:memory:` opens READ_WRITE.
- Query paths are relative to the project root: `read_parquet('data/warehouse/dim_work.parquet')`.
- Keep parquet out of `sources/`: Evidence runs `${}` substitution over every file there, and binary parquet emits `Missed substition for ${...}` warnings.
- `evidence.config.yaml` holds its own plugin registry under `plugins.datasources`. A connector swap edits package.json and that list; otherwise `evidence sources` dies with `Cannot find module '@evidence-dev/<old>'` while `evidence build` serves stale cache.
- `evidence build` reuses the cached extract in `.evidence/template/static/data/` and skips sources; `npm run sources` forces it, `-- --changed` limits to changed. Fresh CI clone has no cache, so CI always extracts.

## Cloudflare Pages

- Build `npm run sources && npm run build`, output dir `build`, root dir `evidence`.
- 25 MiB per-file cap; bundled duckdb-wasm binaries run 33-38 MB. `evidence/scripts/cdn-wasm.js` (`postbuild`) rewrites their URLs to jsDelivr and deletes them from `build/`.
- 20-minute build cap (Free plan); 20,000 files per deployment.
- **Never ship a top-level `build/404.html`.** Its presence disables Pages' built-in SPA fallback, which serves `index.html` at 200 with the URL intact. That fallback is the only thing making cold loads of detail pages work.
- Don't use `_redirects` 200-rewrites here. Pages normalises the target (`/200.html` becomes `/200`, `/x/index.html` becomes `/x/`) and downgrades the rewrite to a 308; extensionless and directory targets just 404.
- `npm run dev` skips prerender; only `npm run build` reproduces deploy failures.

## Rendering modes

- SPA mode is on: `VITE_EVIDENCE_SPA=true` (via `cross-env`) flips prerender off globally. `evidence/svelte.config.js` deep-merges in `adapter-static`.
- Opt back in via `export const prerender = true` in a `+page.js`. On: `/`, `/works`, `/authors`, `/404`.
- Clicking a detail link never hits Cloudflare (client-side routing). Only cold loads (refresh, pasted URL, inbound link) exercise the fallback.
- Unknown URLs return 200 with the shell, not 404; SvelteKit renders the error page client-side.
- Deleting a file from `pages/` or `static/` does not remove it from `.evidence/template/`. Wipe `.evidence` or the stale copy ships.
- `npm run preview` uses `serve -s`, which rewrites every path to `index.html`. Use `npx serve build`, or `npx wrangler pages dev build` to emulate Pages routing faithfully.
- `<Value/>` in a markdown link URL becomes a literal href and 404s the build; markdown also URL-encodes `[0]`. Use raw `<a href={query[0].col}>`.
- Escape `'` inside interpolation: `'${params.author.replaceAll("'", "''")}'`.
- "Error in Data Table: Dataset is empty" from input-dependent components on non-template pages is build-log noise; they hydrate.

## Theming

- `pages/+layout.svelte` overrides the default layout: copy `.evidence/template/src/pages/+layout.svelte`, keep the `'../app.css'` import, wrap in `<EvidenceDefaultLayout {data}>`. CSS imported there bundles after `app.css`. Ours: `pages/wordleaves-theme.css`.
- ECharts canvas text ignores page CSS fonts.
