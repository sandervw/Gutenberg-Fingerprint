// Preloads upright fonts with JS and CSS; italics load on use.

/** True for the files each page should preload. */
function shouldPreload({ type, path }) {
	if (type === 'font') return !path.includes('Italic');
	return type === 'js' || type === 'css';
}

/** @type {import('@sveltejs/kit').Handle} */
export function handle({ event, resolve }) {
	return resolve(event, { preload: shouldPreload });
}
