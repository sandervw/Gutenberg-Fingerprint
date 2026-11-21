// SvelteKit config: every page prerendered to one static HTML file.
import process from 'node:process';
import adapter from '@sveltejs/adapter-static';

/** Where the static site is written. */
export const outputFolder = 'build';

const concurrency = Number(process.env.GUFIME_PRERENDER_CONCURRENCY ?? 16);
const crawl = process.env.GUFIME_PRERENDER_CRAWL === '1';

/** Static adapter, explicit entries, no link crawl. */
export default {
	kit: {
		adapter: adapter({ pages: outputFolder, fallback: '404.html' }),
		// Inline the stylesheets so first paint needs no extra request.
		inlineStyleThreshold: 16384,
		prerender: { concurrency, crawl, entries: ['*', '/sitemap.xml'] },
		// A fixed version keeps unchanged pages byte-identical between builds.
		version: { name: process.env.GUFIME_SITE_VERSION ?? '1' }
	}
};
