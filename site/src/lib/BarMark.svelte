<svelte:options namespace="svg" />

<!-- @component A plain bar from the zero line to the bar's end. -->
<script>
	let { start, end, centre, thickness } = $props();
</script>

<rect class="mark" x={Math.min(start, end)} y={centre - thickness / 2} width={Math.abs(end - start)} height={thickness} />

<style>
	.mark {
		fill: var(--color-accent);
	}
</style>
