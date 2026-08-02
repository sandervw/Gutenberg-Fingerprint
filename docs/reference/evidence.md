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
- **`_redirects` outranks static assets**, so a blanket `/works/*` shadows the prerendered `/works/index.html`. Pin hubs first; first match wins.
- `npm run dev` skips prerender; only `npm run build` reproduces deploy failures.

## Rendering modes

- SPA mode is on: `VITE_EVIDENCE_SPA=true` (via `cross-env`) flips prerender off globally. `evidence/svelte.config.js` deep-merges in `fallback: '200.html'`; not `index.html`, which collides with the prerendered homepage.
- Opt back in via `export const prerender = true` in a `+page.js`. On: `/`, `/works`, `/authors`, `/404`. Un-prerender `/404` and `copy-404.js` breaks.
- Detail routes need `_redirects`. `/works/:work/` won't match the bare `/works/` hub; a splat would.
- `npm run preview` uses `serve -s`, which rewrites every path to `index.html`. Use `npx serve build` for true behaviour.
- `<Value/>` in a markdown link URL becomes a literal href and 404s the build; markdown also URL-encodes `[0]`. Use raw `<a href={query[0].col}>`.
- Escape `'` inside interpolation: `'${params.author.replaceAll("'", "''")}'`.
- "Error in Data Table: Dataset is empty" from input-dependent components on non-template pages is build-log noise; they hydrate.

## Theming

- `pages/+layout.svelte` overrides the default layout: copy `.evidence/template/src/pages/+layout.svelte`, keep the `'../app.css'` import, wrap in `<EvidenceDefaultLayout {data}>`. CSS imported there bundles after `app.css`. Ours: `pages/wordleaves-theme.css`.
- ECharts canvas text ignores page CSS fonts.
