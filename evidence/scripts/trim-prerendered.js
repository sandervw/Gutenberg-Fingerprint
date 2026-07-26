// Cloudflare Pages caps a deployment at 20,000 files. Evidence writes one .arrow
// per unique query result plus one all-queries.json per page instance.
import { readdirSync, rmSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const apiDir = 'build/api';
const cacheDir = join(apiDir, 'prerendered_queries');

if (!existsSync(cacheDir)) {
  throw new Error(`${cacheDir} not found - did the build layout change?`);
}

const arrowCount = readdirSync(cacheDir).length;
rmSync(cacheDir, { recursive: true });

// An empty object is served by this deployment and lists no prerendered
// results, so every query falls through to DuckDB against the parquet.
let manifestCount = 0;
for (const entry of readdirSync(apiDir, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const routeDir = join(apiDir, entry.name);

  for (const dir of readdirSync(routeDir, { withFileTypes: true })) {
    if (!dir.isDirectory()) continue;
    const manifest = join(routeDir, dir.name, 'all-queries.json');
    if (!existsSync(manifest)) continue;

    writeFileSync(manifest, '{}');
    manifestCount++;
  }
}

console.log(
  `trim-prerendered: removed ${arrowCount} .arrow, emptied ${manifestCount} all-queries.json (queries now run client-side)`
);
