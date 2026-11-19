// Build-time data: extracted query results, read once, grouped by key.
import { readFileSync } from 'node:fs';

const tables = new Map();
const groups = new Map();

/** All rows of one extracted query, such as "works/works". */
export function rows(name) {
	if (!tables.has(name)) tables.set(name, JSON.parse(readFileSync(`.data/${name}.json`, 'utf8')));
	return tables.get(name);
}

/** Group a query's rows by a key column, dropping that column. */
function groupRows(name, column) {
	const grouped = new Map();
	for (const { [column]: key, ...rest } of rows(name)) {
		if (!grouped.has(key)) grouped.set(key, []);
		grouped.get(key).push(rest);
	}
	return grouped;
}

/** Rows of a query whose key column equals the value. */
export function rowsFor(name, column, value) {
	if (!groups.has(name)) groups.set(name, groupRows(name, column));
	return groups.get(name).get(value) ?? [];
}
