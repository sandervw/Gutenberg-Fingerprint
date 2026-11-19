<script>
	// Searchable authors list.
	import DataTable from '$lib/DataTable.svelte';

	let { data } = $props();

	const columns = [
		{ id: 'name', title: 'Author' },
		{ id: 'works', title: 'Works', format: 'num0' },
		{ id: 'words', title: 'Words', format: 'num0' }
	];
</script>

<svelte:head><title>Authors</title></svelte:head>

<h1>Authors</h1>
<p>Authors with at least one measured work.</p>
<DataTable rows={data.authors} {columns} search={true} link={(row) => `/authors/${encodeURIComponent(row.name)}`} />
