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
- Keep parquet out of `sources/`; Evidence runs `${}` substitution over every file there.
- `evidence.config.yaml` holds its own plugin registry under `plugins.datasources`. A connector swap edits package.json and that list.
- `evidence build` reuses the cached extract in `.evidence/template/static/data/` and skips sources; `npm run sources` forces it, `-- --changed` limits to changed. CI always extracts.

## Cloudflare Pages

- Build `npm run sources && npm run build`, output dir `build`, root dir `evidence`.
- 25 MiB per-file cap. `evidence/scripts/cdn-wasm.js` (`postbuild`) rewrites the duckdb-wasm binary URLs to jsDelivr and deletes the binaries from `build/`.
- 20-minute build cap (Free plan); 20,000 files per deployment.
- `npm run dev` skips prerender; only `npm run build` reproduces deploy failures.

## Rendering modes

- SPA mode is on: `VITE_EVIDENCE_SPA=true` (via `cross-env`) flips prerender off globally. `evidence/svelte.config.js` deep-merges in `adapter-static` with `fallback: '200.html'`.
- Opt back in via `export const prerender = true` in a `+page.js`. On: `/`, `/works`, `/authors`, `/404`.
- Detail links route client-side. Cold loads (refresh, pasted URL, inbound link) use the fallback below.
- **Fallback:** `postbuild` runs `scripts/copy-404.js`, copying `build/404/index.html` to `build/404.html`, which puts Pages in custom-404 mode (404 status for unmatched paths). `evidence/functions/[[path]].js` intercepts that 404 via the `env.ASSETS.fetch` binding and serves `200.html` (the client shell) at 200. Both files are required.
- Verify with `npx wrangler pages dev build`.
- Unknown URLs (no matching route at all) also return 200 with the shell; SvelteKit renders the error page client-side.
- Deleting a file from `pages/` or `static/` leaves it in `.evidence/template/`; wipe `.evidence`.
- Build link hrefs from query values with raw `<a href={query[0].col}>`.
- Escape `'` inside interpolation: `'${params.author.replaceAll("'", "''")}'`.
- "Error in Data Table: Dataset is empty" from input-dependent components on non-template pages is build-log noise; they hydrate.

## Theming

- `pages/+layout.svelte` overrides the default layout: copy `.evidence/template/src/pages/+layout.svelte`, keep the `'../app.css'` import, wrap in `<EvidenceDefaultLayout {data}>`. CSS imported there bundles after `app.css`. Ours: `pages/wordleaves-theme.css`.
- ECharts canvas text ignores page CSS fonts.
- DataTable row links are `sr-only` absolutes that escape the table's `.scrollbox` and widen phone pages; `pages/wordleaves-theme.css` sets `.scrollbox { position: relative; }`.
- Charts render without an accessible name; wrap each in `<div role="img" aria-label="... chart">`.
