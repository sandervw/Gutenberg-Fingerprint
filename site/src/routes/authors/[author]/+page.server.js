// Author page data: the .sql files beside this file, keyed by author.
import { rows, rowsFor } from '$lib/server/data.js';

const queries = ['distinctive', 'sentence_types', 'punctuation', 'function_words', 'works'];

/** One page per author. */
export function entries() {
	return rows('authors/[author]/summary').map((summary) => ({ author: summary.author }));
}

/** This author's totals, chart rows, and works. */
export function load({ params }) {
	const parts = queries.map((query) => [query, rowsFor(`authors/[author]/${query}`, 'author', params.author)]);
	return {
		author: params.author,
		summary: rowsFor('authors/[author]/summary', 'author', params.author)[0],
		metric_definitions: rows('authors/[author]/metric_definitions'),
		...Object.fromEntries(parts)
	};
}
