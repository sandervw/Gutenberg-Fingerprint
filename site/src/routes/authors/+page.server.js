// Authors list data: authors.sql beside this file.
import { rows } from '$lib/server/data.js';

/** Every author with at least one measured work. */
export function load() {
	return { authors: rows('authors/authors') };
}
