<script>
	// Shown for any address without a page.
	import FireTitle from '$lib/FireTitle.svelte';
</script>

<svelte:head><title>Page Not Found</title></svelte:head>

<FireTitle text="Page Not Found" />
<p>There's no page at this address. It may have moved, or it may never have existed.</p>
<p><a href="/">Return to the fingerprint &rarr;</a></p>
