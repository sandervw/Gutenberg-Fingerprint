# SvelteKit static site

## Build

- `npm run build` in `site/`: `scripts/extract.js` runs every `.sql` under `src/routes/` once into `.data/<route>/<name>.json`, `vite build` prerenders, `scripts/prune.js` deletes each `__data.json`.
- `scripts/warehouse.js` is the one database seam. `GUFIME_TARGET=duckdb` (default) opens `GUFIME_DUCKDB_PATH` (default `../dbt/warehouse.duckdb`) read-only; `postgres` connects over `/var/run/postgresql` with peer auth (`PGHOST`, `PGDATABASE` override).
- Per-page SQL selects every row with a key column (`work_id`, `author`); `src/lib/server/data.js` groups by key in memory.
- `GUFIME_OUT` sets the output folder (default `build`).

## Prerender

- `export const prerender = true` in `src/routes/+layout.js`. `adapter-static` writes `works/<id>.html`; Pages serves it at `/works/<id>`.
- `entries()` in each `[param]/+page.server.js` lists the pages; `prerender.crawl` is off.
- `kit.version.name` is fixed (`GUFIME_SITE_VERSION`, default `1`).
- `fallback: '404.html'`: unknown paths return 404.
- `<body data-sveltekit-reload>` makes every link a full page load.

## Cloudflare Pages

- 20,000 files per deployment on the Free plan; 25 MiB per file.
- `wrangler pages deploy build --project-name=gutenberg-fingerprint --branch=<name>`; branch `main` is production, any other branch is a preview at `<branch>.gutenberg-fingerprint.pages.dev`.

## Lockfile

- Regenerate `site/package-lock.json` on Linux (the box).
