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
		<span>{label}</span>
		<span class="divider"></span>
		<span>{value}</span>
		<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 9 4-4 4 4M16 15l-4 4-4-4" /></svg>
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
	.divider {
		align-self: stretch;
		margin: 0.5rem 0;
		border-left: 1px solid var(--rule);
	}
	svg {
		width: 0.75rem;
		height: 0.75rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
	}
	.popup {
		position: absolute;
		left: 0;
		z-index: 30;
		width: 18rem;
		max-width: 80vw;
		padding: 0.5rem;
		background-color: var(--sheet-base);
		border: 1px solid var(--rule);
		border-radius: 0.375rem;
		font-size: 0.875rem;
	}
	.popup input {
		width: 100%;
	}
	ul {
		max-height: 16rem;
		overflow-y: auto;
		margin: 0.5rem 0 0;
		padding: 0;
		list-style: none;
	}
	li {
		padding: 0.25rem 0.5rem;
		border-radius: 0.125rem;
		cursor: pointer;
	}
	li:hover {
		background-color: var(--hover);
	}
	li[aria-selected='true'] {
		color: var(--link);
	}
</style>
