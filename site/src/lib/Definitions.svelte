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

<button class="toggle" type="button" aria-expanded={open} onclick={() => (open = !open)}>
	<span>*Definitions</span>
	<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
</button>
{#if open}
	<DataTable {rows} {columns} pageSize={0} />
{/if}

