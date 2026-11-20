<svelte:options namespace="svg" />

<!-- @component A bar drawn as a serpent from zero to its value. -->
<script>
	import { area, curveCatmullRom } from 'd3-shape';

	let { start, end, centre } = $props();

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

	const length = $derived(Math.abs(end - start));
	const steps = $derived(Math.max(6, Math.round(length / 5)));
	const points = $derived(
		Array.from({ length: steps + 1 }, (_, step) => {
			const position = step / steps;
			const wave = Math.sin((position * length) / 7) * 3 * (1 - position * 0.6);
			return { x: start + (end - start) * position, centre: centre + wave, half: bodyHalf(position) };
		})
	);
</script>

<path class="mark" d={serpentArea(points)} />
<circle class="eye" cx={start + (end - start) * 0.92} cy={centre - 1.5} r="1" />

<style>
	.mark {
		fill: var(--color-accent);
	}
	.eye {
		fill: var(--color-bg-primary);
	}
</style>
