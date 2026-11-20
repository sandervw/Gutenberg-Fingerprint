<!-- @component Horizontal bar chart in the Evidence look; `mark` draws bars. -->
<script>
	import { scaleLinear } from 'd3-scale';
	import BarMark from '$lib/BarMark.svelte';
	import { formatValue } from '$lib/format.js';

	let { rows, label, value, title, format = 'twoDecimals', mark: Mark = BarMark } = $props();

	const axisHeight = 22;
	const minimumPlotHeight = 150;
	const rowHeight = 21.6;
	const characterWidth = 6.2;
	const labelGap = 8;
	const rightPadding = 24;
	let width = $state(736);
	let hovered = $state(-1);
	let pointer = $state({ x: 0, y: 0 });

	/** A row's value; a missing column is an error, a null is zero. */
	function amountOf(row) {
		if (!(value in row)) throw new Error(`${title}: no column "${value}"`);
		return row[value] ?? 0;
	}

	const amounts = $derived(rows.map(amountOf));
	const longestLabel = $derived(Math.max(0, ...rows.map((row) => String(row[label]).length)));
	const labelWidth = $derived(Math.min(longestLabel * characterWidth, width * 0.45) + labelGap);
	const plotHeight = $derived(Math.max(minimumPlotHeight, rows.length * rowHeight));
	const band = $derived(plotHeight / Math.max(1, rows.length));
	const height = $derived(axisHeight + plotHeight);
	const scale = $derived(
		scaleLinear()
			.domain([Math.min(0, ...amounts), Math.max(0, ...amounts)])
			.range([labelWidth, width - rightPadding])
			.nice(5)
	);
	const ticks = $derived(scale.ticks(5));
	const valueName = $derived(value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' '));
	const maximumLabel = $derived(Math.floor((labelWidth - labelGap) / characterWidth));

	/** Shorten long labels so they fit the label column. */
	function shortLabel(text) {
		return text.length > maximumLabel ? `${text.slice(0, maximumLabel - 1)}…` : text;
	}

	/** Track the hovered row and pointer for the tooltip. */
	function trackPointer(event, index) {
		const box = event.currentTarget.ownerSVGElement.getBoundingClientRect();
		hovered = index;
		pointer = { x: event.clientX - box.left, y: event.clientY - box.top };
	}
</script>

<div class="chart-box" bind:clientWidth={width}>
	<svg class="chart" role="img" aria-label="{title} chart" {width} {height} viewBox="0 0 {width} {height}">
		{#each ticks as tick (tick)}
			<line class="grid" x1={scale(tick)} x2={scale(tick)} y1={axisHeight} y2={height} />
			<text class="tick" x={scale(tick)} y={axisHeight - 8}>{formatValue(tick, format)}</text>
		{/each}
		{#each rows as row, index (index)}
			{@const top = axisHeight + index * band}
			<g
				class:active={hovered === index}
				onpointermove={(event) => trackPointer(event, index)}
				onpointerleave={() => (hovered = -1)}
			>
				<rect class="hit" x={labelWidth} y={top} width={width - rightPadding - labelWidth} height={band} />
				<text class="label" x={labelWidth - labelGap} y={top + band / 2}>{shortLabel(String(row[label]))}</text>
				<Mark start={scale(0)} end={scale(amounts[index])} centre={top + band / 2} thickness={band * 0.7} />
			</g>
		{/each}
		<line class="axis" x1={scale(0)} x2={scale(0)} y1={axisHeight} y2={height} />
	</svg>
	{#if hovered >= 0}
		<div class="tooltip" style:left="{Math.min(pointer.x + 14, width - 190)}px" style:top="{pointer.y + 14}px">
			<strong>{rows[hovered][label]}</strong>
			<span class="tooltip-row">{valueName}: <span>{formatValue(amounts[hovered], format)}</span></span>
		</div>
	{/if}
</div>

<style>
	.chart-box {
		position: relative;
		margin: 1.25rem 0 1.75rem;
	}
	.chart {
		display: block;
		overflow: visible;
	}
	text {
		font-family: var(--font-inter);
		font-size: 11px;
		fill: var(--color-muted);
		dominant-baseline: middle;
	}
	.tick {
		text-anchor: middle;
	}
	.label {
		text-anchor: end;
	}
	.grid {
		stroke: var(--color-border);
		stroke-width: 1;
	}
	.axis {
		stroke: var(--color-muted);
		stroke-width: 1;
	}
	.hit {
		fill: transparent;
	}
	.active .hit {
		fill: var(--color-hover);
	}
	.active :global(.mark) {
		opacity: 0.8;
	}
	.tooltip {
		position: absolute;
		z-index: 1;
		display: flex;
		flex-direction: column;
		min-width: 9rem;
		padding: 6px;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		background-color: var(--color-bg);
		font-size: 12px;
		line-height: 18px;
		white-space: nowrap;
		pointer-events: none;
	}
	.tooltip-row {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
</style>
