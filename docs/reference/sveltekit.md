# SvelteKit static site

## Build

- `uv run python -m python.workflow.site_extract` runs every `.sql` under `site/src/routes/` through the storage seam and writes `<name>.json` beside it. `GUFIME_TARGET` picks DuckDB or Postgres.
- `npm run build` in `site/`: `vite build` prerenders, then `scripts/prune.js` deletes each `__data.json`.
- Per-page SQL selects every row with a key column (`work_id`, `author`); `src/lib/server/data.js` groups by key in memory.
- `outputFolder` in `svelte.config.js` names the output folder (`build`).

## Prerender

- `export const prerender = true` in `src/routes/+layout.js`. `adapter-static` writes `works/<id>.html`; Pages serves it at `/works/<id>`.
- `entries()` in each `[param]/+page.server.js` lists the pages; `prerender.crawl` is off.
- `kit.version.name` is fixed (`GUFIME_SITE_VERSION`, default `1`).
- `fallback: '404.html'`: unknown paths return 404.
- `<body data-sveltekit-reload>` makes every link a full page load.

## Load speed

- Fonts and textures live in `src/assets/`; `site.css` refers to them by relative `url()`. Vite fingerprints them into `_app/immutable/assets/`.
- `static/_headers` gives `/_app/immutable/*` a one-year `immutable` cache.
- `src/hooks.server.js` passes `resolve(event, { preload })` to add font preloads, except italics, to the default JS and CSS ones. It runs during prerender.
- `kit.inlineStyleThreshold` inlines stylesheets under the limit into each page's `<style>` and rewrites asset URLs relative to the page.
- `static/fix-tprotocol-service-worker.js` unregisters the service worker registered at that path.

## Cloudflare Pages

- 20,000 files per deployment on the Free plan; 25 MiB per file.
- `wrangler pages deploy build --project-name=gutenberg-fingerprint --branch=<name>`; branch `main` is production, any other branch is a preview at `<branch>.gutenberg-fingerprint.pages.dev`.

## Lockfile

- Regenerate `site/package-lock.json` on Linux (the box).
