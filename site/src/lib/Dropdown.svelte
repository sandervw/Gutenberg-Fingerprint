<!-- @component Searchable single-choice dropdown. -->
<script>
	let { label, options, value = $bindable() } = $props();

	const optionLimit = 100;
	let open = $state(false);
	let search = $state('');

	const shown = $derived(
		options.filter((option) => option.toLowerCase().includes(search.toLowerCase())).slice(0, optionLimit)
	);

	/** Close the list when Escape is pressed anywhere. */
	function closeOnEscape(event) {
		if (event.key === 'Escape') {
			open = false;
			search = '';
		}
	}
</script>

<svelte:window onkeydown={closeOnEscape} />

<div class="dropdown">
	<button
		class="control"
		type="button"
		role="combobox"
		aria-label={label}
		aria-expanded={open}
		aria-haspopup="listbox"
		onclick={() => (open = !open)}
	>
		{label}: {value}
	</button>
	{#if open}
		<div class="popup" role="application">
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="control"
				type="text"
				role="combobox"
				aria-label="Search {label}"
				aria-expanded="true"
				placeholder="Search"
				autofocus
				bind:value={search}
			/>
			<ul role="listbox">
				{#each shown as option (option)}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<li role="option" aria-selected={option === value} onclick={() => (value = option)}>{option}</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<style>
	.dropdown {
		position: relative;
	}
	.popup {
		position: absolute;
		left: 0;
		z-index: var(--z-overlay);
		width: 18rem;
		max-width: 80vw;
		padding: var(--small);
		background-color: var(--color-bg-primary);
		border: var(--border-width) solid var(--color-gray);
	}
	ul {
		max-height: 16rem;
		overflow-y: auto;
		padding: 0;
		list-style: none;
	}
	li {
		padding: var(--xsmall) var(--small);
		cursor: pointer;
	}
	li:hover,
	li[aria-selected='true'] {
		color: var(--color-accent);
	}
</style>
