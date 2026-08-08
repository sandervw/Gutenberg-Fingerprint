# Evidence SPA + opt-in prerender: data flashes in on hard load

## Summary

In an Evidence project running in SPA mode (`VITE_EVIDENCE_SPA=true`), pages that opt into
prerendering with `export const prerender = true` build to static HTML, but their data is
not static. On a hard load or refresh, the shell paints immediately, then ~0.5s later every
chart and query-backed table re-renders as the in-browser DuckDB-WASM engine boots,
downloads the Parquet sources, and runs the SQL.

## Environment

- `@evidence-dev/evidence` 40.1.8, `@evidence-dev/core-components` 5.4.2
- SvelteKit + `@sveltejs/adapter-static`, `fallback: '200.html'`
- Build: `cross-env VITE_EVIDENCE_SPA=true evidence build`
- Deploy: Cloudflare Pages; sources ingested via the Postgres connector
- Pages: homepage (`Value` + `DataTable` + `BarChart`), `/works`, `/authors`

## Runtime data path

Connectors (Postgres, DuckDB-local) run at build/sources time and extract each query into
static Parquet files. At runtime the browser loads those Parquet files into an embedded
DuckDB-WASM engine and executes page SQL client-side. The deployed site is static assets
plus WASM, with no database connection. The client-side engine boot produces the flash.

## Symptom

The prerendered HTML contains page chrome and scalar `<Value>` output. Charts render a
`Loading` skeleton. Query tables re-query from cold DuckDB after mount. For ~0.5s the data
visual is absent or flickering.

## Root cause

Each ```sql block in a `.md` page compiles to a query store that reads its seed once, at
component init:

```js
let outliersInitialStates = { initialData: undefined, ... }
if (browser) {
  if (data.outliers_data) {
    outliersInitialStates.initialData = data.outliers_data
  }
}
// store created with initialData; when undefined, it re-queries via DuckDB-WASM
```

The `data` object comes from `getPrerenderedQueries()` in the root `src/pages/+layout.js`,
which fetches the build-time cache
(`/api/<routeHash>/<paramsHash>/all-queries.json` + `/api/prerendered_queries/*.arrow`):

```js
export const prerender = import.meta.env.VITE_EVIDENCE_SPA !== 'true';  // false in SPA
if (browser && isUserPage && prerender) {
  data = await getPrerenderedQueries(routeHash, paramsHash, fetch);
}
```

Two gates block this on a hard load:

1. In SPA mode the module-level `prerender` constant is `false`, so
   `browser && isUserPage && prerender` never passes. A prerendered page never rehydrates
   its cache.

2. The branch is gated on `browser`, and prerendered pages invoke `load` only at build time.
   Per SvelteKit docs: "load functions are invoked at runtime, unless the page is
   prerendered, in which case they are invoked at build time." At build time
   `browser === false`, so `getPrerenderedQueries()` is skipped and the serialized `data` is
   `{}`. SvelteKit reuses that build-time output on hydration and does not re-run the
   universal `load`. The fetch never fires. The component initializes with
   `initialData: undefined` and re-queries via DuckDB.

`getPrerenderedQueries()` runs only during client-side navigation, where `load` executes in
the browser. It does not run on a cold load.

## Observations (deployed, prerendered homepage)

- `all-queries.json` and every `.arrow` file serve HTTP 200 and hold the correct keys
  (`outliers_data`, `last_refreshed_data`, `kinship_data`).
- The page HTML contains zero occurrences of `outliers_data`; the cache is never serialized
  into the page.
- `<Value>` scalars render server-side. `<BarChart>` renders `Loading`; chart libraries do
  not server-render their data.
- Hard reload with the Network tab filtered to `arrow` shows zero requests. DuckDB-WASM and
  every `.parquet` load instead, followed by client-side XHR queries.

## Required fix

The prerendered query results must be present at component init on a hard load, which
requires them serialized into the page at build time. The layout `load` must populate `data`
during prerendering (`building`, `browser === false`), so SvelteKit serializes it and each
query store seeds `initialData` from it on a cold load.

## Related

evidence-dev/evidence #3084, "SPA mode fails when loading pages without data" (open).
