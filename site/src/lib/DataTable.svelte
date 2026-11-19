<script>
	// Paged table; optional search box and row links.
	import { formatValue } from '$lib/format.js';

	let { rows, columns, link = null, pageSize = 25, search = false } = $props();

	let query = $state('');
	let pageNumber = $state(0);

	const matching = $derived(
		query === ''
			? rows
			: rows.filter((row) => String(row[columns[0].id]).toLowerCase().includes(query.toLowerCase()))
	);
	const size = $derived(pageSize > 0 ? pageSize : Math.max(1, matching.length));
	const pageCount = $derived(Math.max(1, Math.ceil(matching.length / size)));
	const current = $derived(Math.min(pageNumber, pageCount - 1));
	const visible = $derived(matching.slice(current * size, (current + 1) * size));

	/** Open a row's page when any of its cells is clicked. */
	function openRow(row) {
		if (link) window.location.href = link(row);
	}
</script>

{#if search}
	<input class="control" type="text" aria-label="Search" placeholder="Search" bind:value={query} />
{/if}
<div class="scrollbox">
	<table>
		<thead>
			<tr>
				{#each columns as column (column.id)}
					<th scope="col">{column.title}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each visible as row, index (index)}
				<tr class:clickable={link !== null} onclick={() => openRow(row)}>
					{#each columns as column, position (column.id)}
						<td class:number={column.format !== undefined}>
							{#if link && position === 0}
								<a href={link(row)}>{row[column.id]}</a>
							{:else}
								{formatValue(row[column.id], column.format)}
							{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
{#if pageCount > 1}
	<p class="pager">
		<button type="button" disabled={current === 0} onclick={() => (pageNumber = current - 1)}>Previous page</button>
		<span>Page {current + 1} of {formatValue(pageCount, 'num0')} ({formatValue(matching.length, 'num0')} rows)</span>
		<button type="button" disabled={current >= pageCount - 1} onclick={() => (pageNumber = current + 1)}>Next page</button>
	</p>
{/if}

<style>
	.scrollbox {
		overflow-x: auto;
		max-width: 100%;
	}
	.clickable {
		cursor: pointer;
	}
	.clickable:hover td,
	.clickable:hover a {
		color: var(--color-accent);
	}
	td a {
		display: block;
	}
	.number {
		text-align: right;
	}
	.pager {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--medium);
	}
</style>
