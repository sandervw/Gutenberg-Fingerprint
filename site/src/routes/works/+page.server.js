// Works list data: works.sql beside this file.
import { rows } from '$lib/server/data.js';

/** Every work, as column names plus value arrays to stay small. */
export function load() {
	const works = rows('works/works');
	return { columns: Object.keys(works[0]), values: works.map((work) => Object.values(work)) };
}
