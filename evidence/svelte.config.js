import adapter from '@sveltejs/adapter-static';

// SPA mode serves unprerendered routes from this fallback shell.
export default {
	kit: {
		adapter: adapter({
			pages: process.env.EVIDENCE_BUILD_DIR ?? './build',
			fallback: '200.html',
			strict: false
		})
	}
};
