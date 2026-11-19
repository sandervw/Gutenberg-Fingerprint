// Home page data: the .sql files beside this file.
import { rows } from '$lib/server/data.js';

/** Corpus summary, weirdest works, vocabulary overlap. */
export function load() {
	return { summary: rows('summary')[0], outliers: rows('outliers'), kinship: rows('kinship') };
}
