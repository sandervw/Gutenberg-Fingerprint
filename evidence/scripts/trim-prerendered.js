// Cloudflare Pages caps a deployment at 20,000 files. Evidence writes one .arrow
// per unique query result plus one all-queries.json per page instance, so the
// count scales with the corpus and blew the cap once dim_work passed ~1,800 works.
// These are only a first-paint cache: +layout.js drops a missing entry and the
// component re-runs the query in DuckDB-WASM against build/data/*.parquet, which
// the browser already loads for the works/authors filters.
import { readdirSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const apiDir = 'build/api';
const cacheDir = join(apiDir, 'prerendered_queries');

if (!existsSync(cacheDir)) {
	throw new Error(`${cacheDir} not found - did the build layout change?`);
}

const arrowCount = readdirSync(cacheDir).length;
rmSync(cacheDir, { recursive: true });

// Without the .arrow files an all-queries.json only buys a round trip of 404s,
// so drop those route/params dirs too. customFormattingSettings.json stays:
// +layout.js parses it unguarded and a 404 would throw.
let manifestCount = 0;
for (const entry of readdirSync(apiDir, { withFileTypes: true })) {
	if (!entry.isDirectory()) continue;
	const routeDir = join(apiDir, entry.name);
	const paramDirs = readdirSync(routeDir, { withFileTypes: true }).filter((d) => d.isDirectory());
	const withManifest = paramDirs.filter((d) =>
		existsSync(join(routeDir, d.name, 'all-queries.json'))
	);
	if (withManifest.length === 0) continue;

	for (const dir of withManifest) {
		rmSync(join(routeDir, dir.name), { recursive: true });
		manifestCount++;
	}
	if (readdirSync(routeDir).length === 0) rmSync(routeDir, { recursive: true });
}

console.log(
	`trim-prerendered: removed ${arrowCount} .arrow + ${manifestCount} all-queries.json (queries now run client-side)`
);
