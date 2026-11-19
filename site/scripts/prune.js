// Deletes SvelteKit's per-page __data.json so each page is one file.
import { globSync, readdirSync, rmdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import process from 'node:process';

const output = process.env.GUFIME_OUT ?? 'build';
for (const file of globSync('**/__data.json', { cwd: output })) {
	const folder = dirname(join(output, file));
	rmSync(join(output, file));
	if (readdirSync(folder).length === 0) rmdirSync(folder);
}
