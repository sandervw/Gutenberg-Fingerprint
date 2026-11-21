<!-- @component Page title that flames in once per load. -->
<script>
	import { onMount } from 'svelte';
	import { burnTitle } from '$lib/fire.js';

	let { text, href = null } = $props();
	let heading;

	const characters = $derived([...text]);

	onMount(() => {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		document.fonts.ready.then(() => burnTitle(heading));
	});
</script>

{#snippet letters()}{#each characters as character, index (index)}{#if /\s/.test(character)}{' '}{:else}<span class="letter">{character}</span>{/if}{/each}{/snippet}

<h1 bind:this={heading}>
	{#if href}<a {href}>{@render letters()}</a>{:else}{@render letters()}{/if}
</h1>
