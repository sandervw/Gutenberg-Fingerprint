<!-- @component Collapsible table of metric definitions. -->
<script>
	import DataTable from '$lib/DataTable.svelte';

	let { rows } = $props();
	let open = $state(false);

	const columns = [
		{ id: 'display_name', title: 'Metric' },
		{ id: 'description', title: 'Definition' }
	];
</script>

<p>
	<button class="control" type="button" aria-expanded={open} onclick={() => (open = !open)}>*Definitions</button>
</p>
{#if open}
	<DataTable {rows} {columns} pageSize={0} />
{/if}
