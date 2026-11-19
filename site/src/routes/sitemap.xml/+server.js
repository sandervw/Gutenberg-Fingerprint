// sitemap.xml: hubs plus every work and author page.
import { rows } from '$lib/server/data.js';

const origin = 'https://gufime.com';

/** Prerendered once per build. */
export const prerender = true;

/** The sitemap as XML. */
export function GET() {
	const works = rows('works/[work]/work').map((work) => `/works/${work.work_id}`);
	const authors = rows('authors/[author]/summary').map((summary) => `/authors/${encodeURIComponent(summary.author)}`);
	const locations = ['/', '/works/', '/authors/', ...works, ...authors];
	const urls = locations.map((path) => `<url><loc>${origin}${path}</loc></url>`).join('\n');
	const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
	return new Response(body, { headers: { 'content-type': 'application/xml' } });
}
