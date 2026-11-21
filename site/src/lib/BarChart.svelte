<!-- @component Horizontal bar chart in the Rulebook module-chart style. -->
<script>
	import { scaleLinear } from 'd3-scale';
	import { formatValue } from '$lib/format.js';
	import { pastel } from '$lib/pastels.js';

	let { rows, label, value, title, labelTitle, measure, format = 'twoDecimals' } = $props();

	const titleRow = 20;
	const bandHeight = 20;
	const headHeight = titleRow + bandHeight + 2;
	const rowHeight = 25;
	const legendHeight = 20;
	const legendWidth = 170;
	const characterWidth = 7;
	const titleCharacterWidth = 6.8;
	const gap = 12;
	const textInset = 6;
	const narrowWidth = 520;
	let width = $state(736);
	let hovered = $state(-1);
	let pointer = $state({ x: 0, y: 0 });

	/** A row's value; missing columns throw, nulls count as zero. */
	function amountOf(row) {
		if (!(value in row)) throw new Error(`${title}: no column "${value}"`);
		return row[value] ?? 0;
	}

	/** A value as printed: formatted, with a true minus sign. */
	function printed(amount) {
		return formatValue(amount, format).replace('-', '−');
	}

	/** An axis tick as a plain number or whole percent. */
	function tickText(tick) {
		const text = format.startsWith('percent') ? formatValue(tick, 'wholePercent') : String(tick);
		return text.replace('-', '−');
	}

	const amounts = $derived(rows.map(amountOf));
	const isNarrow = $derived(width < narrowWidth);
	const longestLabel = $derived(Math.max(labelTitle.length, ...rows.map((row) => String(row[label]).length)));
	const labelShare = $derived(isNarrow ? 0.4 : 0.32);
	const labelWidth = $derived(Math.min(longestLabel * characterWidth, width * labelShare) + gap);
	const valueRoom = $derived(Math.max(...amounts.map((amount) => printed(amount).length)) * characterWidth + gap);
	const scale = $derived(
		scaleLinear()
			.domain([Math.min(0, ...amounts), Math.max(0, ...amounts)])
			.range([labelWidth, width - valueRoom])
			.nice(5)
	);
	const ticks = $derived(scale.ticks(5));
	const tickLabels = $derived(ticks.map(tickText));
	const tickLabelWidth = $derived(Math.max(...tickLabels.map((text) => text.length)) * characterWidth + gap);
	const tickSpacing = $derived(Math.abs(scale(ticks[1] ?? 0) - scale(ticks[0] ?? 0)) || tickLabelWidth);
	const labelStride = $derived(Math.ceil(tickLabelWidth / tickSpacing));
	const zeroPosition = $derived(Math.max(0, ticks.indexOf(0)));
	const firstTickShown = $derived(scale(ticks[zeroPosition % labelStride]) - tickLabelWidth / 2 > labelTitle.length * characterWidth + textInset);
	const zero = $derived(scale(0));
	const plotMiddle = $derived((labelWidth + width - valueRoom) / 2);
	const titleWidth = $derived(measure.length * titleCharacterWidth);
	const titleCentre = $derived(Math.min(Math.max(plotMiddle, titleWidth / 2), width - titleWidth / 2));
	const hasNegative = $derived(amounts.some((amount) => amount < 0));
	const legendFitsTop = $derived(titleCentre + titleWidth / 2 + gap < width - legendWidth);
	const rowsBottom = $derived(headHeight + rows.length * rowHeight);
	const legendTop = $derived(legendFitsTop ? 2 : rowsBottom + 6);
	const legendBelow = $derived(hasNegative && !legendFitsTop);
	const height = $derived(rowsBottom + 8 + (legendBelow ? legendHeight : 0));
	const maximumLabel = $derived(Math.floor((labelWidth - gap) / characterWidth));

	/** True when a tick's label is drawn; strides out from zero. */
	function isTickShown(position) {
		const onStride = (position - zeroPosition) % labelStride === 0;
		const isFirstShown = position === zeroPosition % labelStride;
		return onStride && (firstTickShown || !isFirstShown);
	}

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
		<text class="title" x={titleCentre} y={titleRow / 2 - 1}>{measure}</text>
		<rect class="band" x="0" y={titleRow} {width} height={bandHeight} />
		<text class="head" x={textInset} y={titleRow + bandHeight / 2}>{labelTitle}</text>
		{#each ticks as tick, position (tick)}
			{#if isTickShown(position)}
				<text class="tick" x={scale(tick)} y={titleRow + bandHeight / 2}>{tickLabels[position]}</text>
			{/if}
		{/each}
		{#each rows as row, index (index)}
			{@const top = headHeight + index * rowHeight}
			{@const amount = amounts[index]}
			{@const barLeft = Math.min(zero, scale(amount))}
			{@const barWidth = Math.max(1.5, Math.abs(scale(amount) - zero))}
			<g
				class="row"
				class:active={hovered === index}
				onpointermove={(event) => trackPointer(event, index)}
				onpointerleave={() => (hovered = -1)}
			>
				<rect class="hit" x="0" y={top} {width} height={rowHeight} />
				{#if index < rows.length - 1}
					<line class="rule" x1="0" x2={width} y1={top + rowHeight} y2={top + rowHeight} />
				{/if}
				<text class="label" x={textInset} y={top + rowHeight / 2}>{shortLabel(String(row[label]))}</text>
				<g class="mark">
					<rect x={barLeft} y={top + 3} width={barWidth} height={rowHeight - 6} style:fill={pastel(index)} />
					{#if amount < 0}
						<rect x={barLeft} y={top + 3} width={barWidth} height={rowHeight - 6} fill="url(#dither)" />
					{/if}
				</g>
				<text class="value" x={Math.max(zero, scale(amount)) + textInset} y={top + rowHeight / 2}>{printed(amount)}</text>
			</g>
		{/each}
		<line class="zero" x1={zero} x2={zero} y1={headHeight - 2} y2={rowsBottom} />
		{#if hasNegative}
			<g class="legend">
				<rect x={width - legendWidth} y={legendTop} width="14" height="12" style:fill="var(--m7)" />
				<rect x={width - legendWidth} y={legendTop} width="14" height="12" fill="url(#dither)" />
				<text x={width - legendWidth + 20} y={legendTop + 6}>Denotes below average</text>
			</g>
		{/if}
	</svg>
	{#if hovered >= 0}
		<div class="tooltip" style:left="{Math.min(pointer.x + 14, width - 190)}px" style:top="{pointer.y + 14}px">
			<strong>{rows[hovered][label]}</strong>
			<span class="tooltip-row">{measure}: <span>{printed(amounts[hovered])}</span></span>
		</div>
	{/if}
</div>

<style>
	.chart-box {
		position: relative;
		min-width: 0;
		margin: 0.6rem 0 1.4rem;
	}
	.chart {
		display: block;
		overflow: visible;
	}
	text {
		font: 400 12.5px var(--font-data);
		fill: var(--ink);
		dominant-baseline: middle;
	}
	.title {
		font: 400 15px var(--font-head);
		fill: var(--gold);
		text-anchor: middle;
	}
	.band {
		fill: var(--oxblood);
	}
	.head,
	.tick {
		font: italic 700 12px var(--font-data);
		fill: var(--oxblood-ink);
	}
	.tick {
		text-anchor: middle;
	}
	.label {
		font: italic 700 12.5px var(--font-data);
	}
	.legend text {
		font: 700 12px var(--font-data);
	}
	.mark {
		filter: url(#chisel);
	}
	.rule {
		stroke: var(--rule);
		stroke-dasharray: 1 3;
	}
	.zero {
		stroke: var(--gold);
		stroke-width: 2.5;
	}
	.hit {
		fill: transparent;
	}
	.active .hit {
		fill: var(--hover);
	}
	.tooltip {
		position: absolute;
		z-index: 3;
		display: flex;
		flex-direction: column;
		min-width: 9rem;
		padding: 6px 8px;
		border: 1px solid var(--gold);
		background-color: var(--sheet-base);
		font: 12px/18px var(--font-data);
		white-space: nowrap;
		pointer-events: none;
	}
	.tooltip-row {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
</style>
