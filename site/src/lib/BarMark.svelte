<svelte:options namespace="svg" />

<!-- @component A plain bar from the zero line to the bar's end. -->
<script>
	let { start, end, centre } = $props();
</script>

<rect class="mark" x={Math.min(start, end)} y={centre - 8} width={Math.abs(end - start)} height="16" />

<style>
	.mark {
		fill: var(--color-accent);
	}
</style>
