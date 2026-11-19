<script>
	// Horizontal bar chart drawn as SVG; bars may be serpents.
	import { scaleLinear } from 'd3-scale';
	import { area, curveCatmullRom } from 'd3-shape';
	import { formatValue } from '$lib/format.js';

	let { rows, label, value, title, format = 'num2', shape = 'bar' } = $props();

	const width = 480;
	const rowHeight = 24;
	const labelWidth = 180;
	const valueWidth = 56;
	const labelLimit = 26;
	let hovered = $state(-1);

	const amounts = $derived(rows.map((row) => row[value] ?? 0));
	const scale = $derived(
		scaleLinear()
			.domain([Math.min(0, ...amounts), Math.max(0, ...amounts)])
			.range([labelWidth, width - valueWidth])
	);
	const height = $derived(rows.length * rowHeight + 8);

	const serpentArea = area()
		.x((point) => point.x)
		.y0((point) => point.centre - point.half)
		.y1((point) => point.centre + point.half)
		.curve(curveCatmullRom)
		.digits(1);

	/** Half-thickness along the body: thin tail, swelling head, blunt snout. */
	function bodyHalf(position) {
		const tail = Math.min(1, position / 0.25) * 4;
		const head = position > 0.82 ? 3 * Math.sin(((position - 0.82) / 0.18) * Math.PI) : 0;
		return Math.max(0.6, tail + head);
	}

	/** A serpent path from the zero line to the bar's end. */
	function serpentPath(start, end, centre) {
		const length = Math.abs(end - start);
		const steps = Math.max(6, Math.round(length / 5));
		const points = Array.from({ length: steps + 1 }, (_, step) => {
			const position = step / steps;
			const wave = Math.sin((position * length) / 7) * 3 * (1 - position * 0.6);
			return { x: start + (end - start) * position, centre: centre + wave, half: bodyHalf(position) };
		});
		return serpentArea(points);
	}

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
			{#if shape === 'serpent'}
				<path class="mark" d={serpentPath(scale(0), scale(amount), centre)} />
				<circle class="eye" cx={scale(0) + (scale(amount) - scale(0)) * 0.92} cy={centre - 1.5} r="1" />
			{:else}
				<rect
					class="mark"
					x={Math.min(scale(0), scale(amount))}
					y={centre - 8}
					width={Math.abs(scale(amount) - scale(0))}
					height="16"
				/>
			{/if}
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
	.mark {
		fill: var(--color-accent);
	}
	.eye {
		fill: var(--color-bg-primary);
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
