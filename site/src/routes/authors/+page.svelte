<script>
	// Searchable authors list.
	import FireTitle from '$lib/FireTitle.svelte';
	import DataTable from '$lib/DataTable.svelte';

	let { data } = $props();
	let query = $state('');

	const matching = $derived(
		data.authors.filter((author) => author.name.toLowerCase().includes(query.toLowerCase()))
	);

	const columns = [
		{ id: 'name', title: 'Author' },
		{ id: 'works', title: 'Works', format: 'wholeNumber' },
		{ id: 'words', title: 'Words', format: 'wholeNumber' }
	];
</script>

<svelte:head><title>Authors</title></svelte:head>

<FireTitle text="Authors" />
<p>Authors with at least one measured work.</p>
<input class="control" type="text" aria-label="Search" placeholder="Search" bind:value={query} />
<DataTable rows={matching} {columns} link={(row) => `/authors/${encodeURIComponent(row.name)}`} />
