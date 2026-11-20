// Home page data: the .sql files beside this file.
import { rows } from '$lib/server/data.js';

/** Corpus summary, weirdest works, vocabulary overlap. */
export function load() {
	return {
		summary: rows('summary')[0],
		weirdest_works: rows('weirdest_works'),
		vocabulary_overlap: rows('vocabulary_overlap')
	};
}
