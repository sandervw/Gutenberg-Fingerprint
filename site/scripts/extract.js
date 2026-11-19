// Runs every page's .sql file once, in bulk, into .data/*.json.
import { globSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { openWarehouse } from './warehouse.js';

const routes = 'src/routes';
const output = '.data';

/** Round fractions to four places to keep pages small. */
function roundValue(value) {
	const isFraction = typeof value === 'number' && !Number.isInteger(value);
	return isFraction ? Math.round(value * 10000) / 10000 : value;
}

/** Round every fractional number in a row. */
function roundRow(row) {
	return Object.fromEntries(Object.entries(row).map(([key, value]) => [key, roundValue(value)]));
}

const started = performance.now();
const warehouse = await openWarehouse();
rmSync(output, { recursive: true, force: true });
for (const file of globSync('**/*.sql', { cwd: routes })) {
	const rows = await warehouse.query(readFileSync(join(routes, file), 'utf8'));
	const target = join(output, file.replace(/\.sql$/, '.json'));
	mkdirSync(dirname(target), { recursive: true });
	writeFileSync(target, JSON.stringify(rows.map(roundRow)));
	console.log(`${file}: ${rows.length} rows`);
}
await warehouse.close();
console.log(`EXTRACT_SECONDS ${((performance.now() - started) / 1000).toFixed(2)}`);
