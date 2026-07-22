# Evidence.dev reference

Local cheat-sheet. Source: evidence-dev/evidence (via Context7). Evidence is "BI as code": reports are Markdown files with SQL inside, built into a static website. It's the dashboard layer that sits on top of our dbt marts.

---

## Mental model (coming from PowerBI / SQL Server)

| PowerBI | Evidence |
|---|---|
| `.pbix` canvas, drag visuals | `.md` files you type |
| DAX measures + data model | plain SQL queries |
| model relationships (`dim_id → fact_id`), auto cross-filter | **no relationships** — joins/filters written by hand in SQL |
| publish to Service | `npm run build` → static site |

There is **no semantic model**. Do the modeling upstream in dbt; Evidence just queries it.

---

## Project shape

```
sources/                 # one folder per data source
  warehouse/
    connection.yaml       # non-secret config (type, db file)
    connection.options.yaml  # secrets (gitignored) — not needed for local DuckDB
    some_query.sql        # optional source query
src/pages/               # the reports; folder structure = site URLs
  index.md
  authors/[author].md     # bracket = templated/dynamic page
```

Pages reference source data as `source_name.query_name` (or query a table directly).

---

## Scaffold + run

```bash
npx degit evidence-dev/template my-project   # download starter template
cd my-project
npm install
npm run sources    # build/cache data from sources
npm run dev        # dev server on localhost:3000
```

`npm run build` produces the static site. `npm run sources -- --changed` rebuilds only changed sources.

### Deploying to Cloudflare Pages

- Build command `npm run sources && npm run build`, output dir `build`, root dir `reports`.
- Prerender crawls every link; a `<Value/>` inside a markdown link URL becomes a literal href and 404s the build. Markdown also URL-encodes `[0]` in link destinations, so use a raw `<a href={query[0].col}>` for dynamic links.
- Pages (and Workers) cap files at 25 MiB; the bundled duckdb-wasm binaries (~33-38 MB) exceed it. `reports/scripts/cdn-wasm.js` (npm `postbuild`) rewrites their URLs to jsDelivr and deletes them from `build/`.
- `npm run dev` skips prerender; only `npm run build` reproduces deploy failures.

---

## Connecting to the parquet export (DuckDB source) — live since 2026-07-22

The site no longer talks to Fabric at build time. `nb_export_gold` writes the gold marts to `lh_silver/Files/exports/*.parquet`; `scripts/fetch-sources.js` downloads them to `evidence/data/warehouse/` (OneLake DFS REST + client-credentials token, `AZURE_TENANT_ID`/`AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET`), hooked as `prebuild`/`predev`/`presources`. The capacity must be running: paused capacities reject all OneLake transactions.

```yaml
name: warehouse
type: duckdb
options:
  filename: ':memory:'
```

- `filename` is **required** and relative to the source dir; `:memory:` opens READ_WRITE, so each query just `read_parquet`s the local file.
- Query paths inside the `.sql` files are relative to the **Evidence project root**, not the source dir: `read_parquet('data/warehouse/dim_work.parquet')`.
- **Keep the parquet out of `sources/`.** Evidence runs `${}` substitution over every file in a source directory; binary parquet in there produces a wall of `Missed substition for ${<garbage>}` warnings.
- **`evidence.config.yaml` has its own plugin registry** under `plugins.datasources` — swapping the connector means editing package.json *and* that list. Miss it and `evidence sources` dies with `Cannot find module '@evidence-dev/<old>'` while `evidence build` happily serves stale cache.
- `evidence build` reuses the cached extract in `.evidence/template/static/data/` and does **not** re-run sources. `npm run sources` forces it. A fresh CI clone has no cache, so CI always extracts.

---

## Connecting to Fabric Warehouse (MSSQL source) — retired 2026-07-22, kept for reference

Verified 2026-07-17 from connector source (`packages/datasources/mssql/index.cjs`); the docs page omits auth. Evidence's `type: mssql` source supports `authenticationType`:

| authenticationType | credentials needed | use |
|---|---|---|
| `default` | `user`, `password` (SQL auth) | n/a — Fabric refuses SQL auth |
| `azure-active-directory-default` | none — DefaultAzureCredential, picks up `az login` | **local dev** |
| `azure-active-directory-service-principal-secret` | `spclientid`, `spclientsecret`, `sptenantid` | **CI / Cloudflare build** |
| `azure-active-directory-password` | `pwuname`, `pwpword`, `pwclientid`, `pwtenantid` | avoid (raw password) |
| `azure-active-directory-access-token` | `attoken` | manual token, expires ~1h |

Common fields: `server` (Warehouse SQL endpoint), `database`, `port`, `encrypt: true` (required by Fabric), and — **snake_case, not camelCase** — `trust_server_certificate`, `connection_timeout`, `request_timeout` (defaults 15000 ms; camelCase keys are silently ignored).

Local↔CI switch without touching yaml: any option can be overridden by env var `EVIDENCE_SOURCE__<source>__<option>`, so connection.yaml holds the local `azure-active-directory-default` config and the CF build injects the service-principal fields.

Capacity must be **running during `npm run sources`** (that's when extraction happens); `npm run dev`/`build` afterward read the cached parquet.

### Two required workarounds (found 2026-07-17; both removed with the connector on 2026-07-22)

1. **tedious < 19.2.1 cannot connect to Fabric at all** ("Connection lost - socket hang up" during the TDS handshake; tediousjs/tedious#1563, fixed by PR #1718 merged 2026-02-09). The connector's mssql@11 pins tedious@18, so package.json overrides `"mssql": "^12.7.0"` (brings tedious 20).
2. **@evidence-dev/mssql@1.1.4 (latest) never passes `authentication.type` to mssql** for any AAD auth type — AAD default silently falls back to SQL auth, service-principal nukes the encrypt options. Patched via `patch-package` (`patches/@evidence-dev+mssql+1.1.4.patch`, applied by the `postinstall` script — runs on CF builds too). Re-check on any connector upgrade.

## Prerender gotchas (bit us in the port)

- Template pages (`[param].md`) are only prerendered if a **non-parameterized page SSRs a link to them** — the crawler reads server-rendered HTML. Input-filtered tables SSR empty, so their links are invisible to the crawl: the old site silently built only 27 of its work pages. Fix: every `[param]` family needs a full, unfiltered link table somewhere static (`authors/index.md`, `works/index.md` catalog). Paginated DataTables are fine — all rows' links reach the crawler.
- `'${params.x}'` / `'${inputs.x.value}'` interpolation breaks on values containing `'` (O'Grady). `${}` evaluates JS, so escape inline: `'${params.author.replaceAll("'", "''")}'`.
- Input-dependent components on non-template pages SSR as "Dataset is empty" errors in the build log and hydrate correctly in the browser — noise, not failures.

---

## Pages = Markdown + components

A page is prose + fenced SQL blocks + component tags, all in one `.md`. Components are **Svelte** (same idea as MDX = Markdown + React); `<BarChart/>` is a component, not HTML.

````markdown
```sql author_lengths
select author, mean_word_length from mart_work_fingerprint
```

<BarChart data={author_lengths} x=author y=mean_word_length />
````

Named SQL block (`author_lengths`) → its result is the `data={...}` for any component below it.

---

## Filtering (the PowerBI cross-filter replacement)

No auto-propagation. Three mechanisms:

**1. Pre-joined marts.** Query a wide flat table (e.g. `mart_work_fingerprint`); joins already done in dbt.

**2. Inputs → WHERE clause.** An input captures a selection into `${inputs.<name>.value}`, interpolated into SQL:

````markdown
```sql authors
select distinct author from mart_work_fingerprint
```

<Dropdown data={authors} name=picked value=author />

```sql filtered
select * from mart_work_fingerprint
where author = '${inputs.picked.value}'
```
````

Multi-value: `where author in ${inputs.picked.value}` (no quotes).

**3. Query chaining.** Reference one query inside another with `${query_name}` to build reusable base queries, then filter downstream:

```sql
select * from ${author_lengths} where mean_word_length > 4
```

---

## Theming & custom styling

- `evidence.config.yaml` → `appearance:` sets `default: light|dark|system` and `switcher: true` (built-in light/dark toggle, lives in the header kebab menu).
- `theme.colors` tokens: `primary`, `accent`, `base`, `info`, `positive`, `warning`, `negative` — each with `light:`/`dark:` hex. `base` drives the whole surface: Evidence generates `base-100/200/300` + `base-content` shades from it (header, sidebar, borders, text).
- `theme.colorPalettes.default` (categorical chart series) and `theme.colorScales.default` (sequential 2-endpoint ramp), each per mode.
- **Custom layout:** any `pages/+layout.svelte` overrides the default. Copy from `.evidence/template/src/pages/+layout.svelte`, keep the `'../app.css'` import, wrap content in `<EvidenceDefaultLayout {data} ...props>`. Useful props: `title` (text wordmark replacing the Evidence logo), `logo`, `hideSidebar`, `fullWidth`, `maxWidth`, `builtWithEvidence`.
- **Custom CSS:** import a plain `.css` from the custom layout (e.g. `import './wordleaves-theme.css'`); it bundles after `app.css` so equal-specificity rules win. Static assets (fonts) go in `reports/static/`, referenced by absolute path (`/fonts/x.woff`).
- Dark mode = `dark` class on `<html>`; scope CSS overrides with `html.dark`.
- Limitation: chart text (ECharts canvas) doesn't inherit page CSS fonts.
- Ours: `pages/wordleaves-theme.css` + copper/cream/charcoal tokens in config, mirroring wordleaves.com (`reports/sparse.css`, `reports/wordleaves.css`).

---

## Exposures (dbt link)

Once a dashboard exists, declare it as a dbt `exposure` so lineage knows the marts feed it.

> Portability note: Evidence reads straight from the DuckDB file and is independent of the dbt engine — swapping dbt to Fabric later doesn't touch the Evidence layer, only the `connection.yaml`.
