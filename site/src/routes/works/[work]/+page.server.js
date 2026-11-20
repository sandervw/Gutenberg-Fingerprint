// Work page data: the .sql files beside this file, keyed by work_id.
import { rows, rowsFor } from '$lib/server/data.js';

const queries = ['deviation', 'signature', 'sentence_types', 'punctuation', 'function_words'];

/** One page per work. */
export function entries() {
	return rows('works/[work]/work').map((work) => ({ work: work.work_id }));
}

/** This work's row and its chart rows. */
export function load({ params }) {
	const charts = queries.map((query) => [query, rowsFor(`works/[work]/${query}`, 'work_id', params.work)]);
	return {
		work: rowsFor('works/[work]/work', 'work_id', params.work)[0],
		metric_definitions: rows('metric_definitions'),
		...Object.fromEntries(charts)
	};
}
