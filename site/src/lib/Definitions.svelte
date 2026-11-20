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
	<svg class:open viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
</button>
{#if open}
	<DataTable {rows} {columns} pageSize={0} />
{/if}

<style>
	.toggle {
		display: flex;
		width: 100%;
		margin: 1rem 0 0.5rem;
		padding: 0.5rem 0;
		align-items: center;
		justify-content: space-between;
		border: 0;
		background: none;
		font-size: 0.875rem;
		cursor: pointer;
	}
	svg {
		width: 1rem;
		height: 1rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		transition: transform 0.15s ease;
	}
	.open {
		transform: rotate(180deg);
	}
</style>
