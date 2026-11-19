<!-- @component Horizontal bar chart drawn as SVG; `mark` draws each bar. -->
<script>
	import { scaleLinear } from 'd3-scale';
	import BarMark from '$lib/BarMark.svelte';
	import { formatValue } from '$lib/format.js';

	let { rows, label, value, title, format = 'twoDecimals', mark: Mark = BarMark } = $props();

	const width = 480;
	const rowHeight = 24;
	const labelWidth = 180;
	const valueWidth = 56;
	const labelLimit = 26;
	let hovered = $state(-1);

	/** A row's value; a missing column is an error, a null is zero. */
	function amountOf(row) {
		if (!(value in row)) throw new Error(`${title}: no column "${value}"`);
		return row[value] ?? 0;
	}

	const amounts = $derived(rows.map(amountOf));
	const scale = $derived(
		scaleLinear()
			.domain([Math.min(0, ...amounts), Math.max(0, ...amounts)])
			.range([labelWidth, width - valueWidth])
	);
	const height = $derived(rows.length * rowHeight + 8);

	/** Shorten long labels so they fit the label column. */
	function shortLabel(text) {
		return text.length > labelLimit ? `${text.slice(0, labelLimit - 1)}…` : text;
	}
</script>

<svg class="chart" role="img" aria-label="{title} chart" viewBox="0 0 {width} {height}">
	{#each rows as row, index (index)}
		{@const amount = amounts[index]}
		{@const centre = 4 + index * rowHeight + rowHeight / 2}
		<g
			class:active={hovered === index}
			onpointerenter={() => (hovered = index)}
			onpointerleave={() => (hovered = -1)}
		>
			<title>{row[label]}: {formatValue(amount, format)}</title>
			<rect class="hit" x="0" y={centre - rowHeight / 2} {width} height={rowHeight} />
			<text class="label" x={labelWidth - 8} y={centre}>{shortLabel(String(row[label]))}</text>
			<Mark start={scale(0)} end={scale(amount)} {centre} />
			<text class="amount" x={width - 2} y={centre}>{formatValue(amount, format)}</text>
		</g>
	{/each}
	<line class="zero" x1={scale(0)} x2={scale(0)} y1="2" y2={height - 2} />
</svg>

<style>
	.chart {
		display: block;
		width: 100%;
		max-width: 44rem;
		height: auto;
		margin-bottom: var(--large);
	}
	text {
		fill: var(--color-text-primary);
		font-size: 11px;
		dominant-baseline: middle;
	}
	.label,
	.amount {
		text-anchor: end;
	}
	.hit {
		fill: transparent;
	}
	.active .hit {
		fill: var(--color-gray);
		opacity: 0.2;
	}
	.active text {
		font-weight: var(--weight-bold);
	}
	.zero {
		stroke: var(--color-gray);
		stroke-width: 1;
	}
</style>
