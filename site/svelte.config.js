// SvelteKit config: every page prerendered to one static HTML file.
import process from 'node:process';
import adapter from '@sveltejs/adapter-static';

const concurrency = Number(process.env.GUFIME_PRERENDER_CONCURRENCY ?? 16);
const crawl = process.env.GUFIME_PRERENDER_CRAWL === '1';

/** Static adapter, explicit entries, no link crawl. */
export default {
	kit: {
		adapter: adapter({ pages: process.env.GUFIME_OUT ?? 'build', fallback: '404.html' }),
		prerender: { concurrency, crawl, entries: ['*', '/sitemap.xml'] },
		// A fixed version keeps unchanged pages byte-identical between builds.
		version: { name: process.env.GUFIME_SITE_VERSION ?? '1' }
	}
};
