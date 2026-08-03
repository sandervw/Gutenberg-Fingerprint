// Serves the SPA shell, not the homepage, for unmatched paths.
export async function onRequest(context) {
	const response = await context.env.ASSETS.fetch(context.request);
	if (response.status !== 404) return response;

	const shellUrl = new URL('/200.html', context.request.url);
	return context.env.ASSETS.fetch(shellUrl);
}
