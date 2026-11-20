<!-- @component Paged table; linked rows end in a chevron link. -->
<script>
	import { formatValue } from '$lib/format.js';

	let { rows, columns, link = null, pageSize = 25 } = $props();

	let pageNumber = $state(0);

	const size = $derived(pageSize > 0 ? pageSize : Math.max(1, rows.length));
	const pageCount = $derived(Math.max(1, Math.ceil(rows.length / size)));
	const current = $derived(Math.min(pageNumber, pageCount - 1));
	const visible = $derived(rows.slice(current * size, (current + 1) * size));
	const isFirst = $derived(current === 0);
	const isLast = $derived(current >= pageCount - 1);

	/** Open a row's page when any of its cells is clicked. */
	function openRow(row) {
		if (link) window.location.href = link(row);
	}
</script>

<div class="table-box">
	<table>
		<thead>
			<tr>
				{#each columns as column (column.id)}
					<th scope="col" class:number={column.format !== undefined}>{column.title}</th>
				{/each}
				{#if link}
					<th scope="col"><span class="sr-only">Links</span></th>
				{/if}
			</tr>
		</thead>
		<tbody>
			{#each visible as row, index (index)}
				<tr class:clickable={link !== null} onclick={() => openRow(row)}>
					{#each columns as column (column.id)}
						<td class:number={column.format !== undefined}>{formatValue(row[column.id], column.format)}</td>
					{/each}
					{#if link}
						<td class="chevron">
							<a href={link(row)} aria-label="Open {row[columns[0].id]}">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
									<path d="m9 6 6 6-6 6" />
								</svg>
							</a>
						</td>
					{/if}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
{#if pageCount > 1}
	<div class="pager">
		<button type="button" aria-label="First page" disabled={isFirst} onclick={() => (pageNumber = 0)}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m11 7-5 5 5 5M17 7l-5 5 5 5" /></svg>
		</button>
		<button type="button" aria-label="Previous page" disabled={isFirst} onclick={() => (pageNumber = current - 1)}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6" /></svg>
		</button>
		<span>Page <span class="page-number">{current + 1}</span> / {formatValue(pageCount, 'wholeNumber')}</span>
		<button type="button" aria-label="Next page" disabled={isLast} onclick={() => (pageNumber = current + 1)}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
		</button>
		<button type="button" aria-label="Last page" disabled={isLast} onclick={() => (pageNumber = pageCount - 1)}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 5 5-5 5M13 7l5 5-5 5" /></svg>
		</button>
	</div>
{/if}

<style>
	.table-box {
		position: relative;
		margin: 0.5rem 0;
		overflow-x: auto;
		max-width: 100%;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.79rem;
		line-height: 1.1875rem;
	}
	thead tr {
		border-bottom: 1px solid color-mix(in srgb, var(--color-muted) 60%, transparent);
	}
	tbody tr {
		border-bottom: 1px solid color-mix(in srgb, var(--color-muted) 20%, transparent);
	}
	th {
		padding: 2px 1px 2px 6px;
		text-align: left;
		vertical-align: bottom;
		white-space: nowrap;
	}
	td {
		padding: 2px 13px 2px 6px;
		vertical-align: middle;
	}
	th:first-child,
	td:first-child {
		padding-left: 3px;
	}
	.number {
		text-align: right;
		white-space: nowrap;
	}
	.clickable {
		cursor: pointer;
	}
	.clickable:hover {
		background-color: var(--color-hover);
	}
	.chevron {
		width: 1rem;
	}
	.chevron a {
		display: flex;
	}
	svg {
		width: 1rem;
		height: 1rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.pager {
		display: flex;
		gap: 0.25rem;
		margin: 0.75rem 0 1rem;
		align-items: center;
		font-size: 0.75rem;
		color: var(--color-muted);
	}
	.pager button {
		display: flex;
		padding: 0.125rem;
		border: 0;
		background: none;
		color: var(--color-text);
		cursor: pointer;
	}
	.pager button:disabled {
		color: var(--color-border);
		cursor: default;
	}
	.page-number {
		padding: 0.125rem 0.375rem;
		background-color: var(--color-hover);
		color: var(--color-text);
	}
</style>
