// The one seam to the gold schema: DuckDB locally, Postgres in production.
import process from 'node:process';

/** Open DuckDB read-only; return a query function and a closer. */
async function openDuckdb() {
	const path = process.env.GUFIME_DUCKDB_PATH;
	if (!path) throw new Error('GUFIME_DUCKDB_PATH is not set');
	const { DuckDBInstance } = await import('@duckdb/node-api');
	const instance = await DuckDBInstance.create(path, { access_mode: 'READ_ONLY' });
	const connection = await instance.connect();
	return {
		query: async (sql) => (await connection.runAndReadAll(sql)).getRowObjectsJson(),
		close: async () => connection.closeSync()
	};
}

/** Open Postgres; return a query function and a closer. */
async function openPostgres() {
	const url = process.env.GUFIME_POSTGRES_URL;
	if (!url) throw new Error('GUFIME_POSTGRES_URL is not set');
	const postgres = await import('pg');
	const client = new postgres.default.Client({ connectionString: url });
	await client.connect();
	return {
		query: async (sql) => (await client.query(sql)).rows,
		close: async () => client.end()
	};
}

/** Open the warehouse named by GUFIME_TARGET (duckdb or postgres). */
export async function openWarehouse() {
	const target = process.env.GUFIME_TARGET ?? 'duckdb';
	if (target === 'duckdb') return openDuckdb();
	if (target === 'postgres') return openPostgres();
	throw new Error(`Unknown GUFIME_TARGET: ${target}`);
}
