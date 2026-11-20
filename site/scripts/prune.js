// Deletes SvelteKit's per-page __data.json so each page is one file.
import { globSync, readdirSync, rmdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { outputFolder } from '../svelte.config.js';

for (const file of globSync('**/__data.json', { cwd: outputFolder })) {
	const folder = dirname(join(outputFolder, file));
	rmSync(join(outputFolder, file));
	if (readdirSync(folder).length === 0) rmdirSync(folder);
}
