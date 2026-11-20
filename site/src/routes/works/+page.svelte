<script>
	// Works list with author, genre, title, and flag filters.
	import DataTable from '$lib/DataTable.svelte';
	import Dropdown from '$lib/Dropdown.svelte';
	import { formatValue } from '$lib/format.js';

	let { data } = $props();

	const flagNames = ['Juvenile', 'Play', 'Poetry', 'Translation'];
	const choices = [
		{ name: 'No', wanted: 0 },
		{ name: 'Yes', wanted: 1 }
	];
	const columns = [
		{ id: 'title', title: 'Title' },
		{ id: 'author', title: 'Author' },
		{ id: 'word_count', title: 'Words', format: 'wholeNumber' },
		{ id: 'genre', title: 'Genre' },
		{ id: 'flags', title: 'Flags' }
	];

	/** The flag column of a work, such as "is_play". */
	function flagColumn(flag) {
		return `is_${flag.toLowerCase()}`;
	}

	const works = data.values.map((values) => {
		const work = Object.fromEntries(data.columns.map((column, position) => [column, values[position]]));
		work.flags = flagNames.filter((flag) => work[flagColumn(flag)] === 1).join(', ');
		return work;
	});
	const authors = ['All authors', ...new Set(works.map((work) => work.author).sort())];
	const genres = ['All genres', ...new Set(works.map((work) => work.genre).sort())];

	let author = $state('All authors');
	let genre = $state('All genres');
	let titleSearch = $state('');
	let wantedFlags = $state({});

	/** True when a work passes every chosen flag except the skipped one. */
	function passesFlags(work, skippedFlag) {
		return flagNames.every((flag) => {
			const isSkipped = flag === skippedFlag;
			const isUnset = wantedFlags[flag] === undefined;
			const matchesWanted = work[flagColumn(flag)] === wantedFlags[flag];
			return isSkipped || isUnset || matchesWanted;
		});
	}

	/** True when a work matches the chosen author, genre, and title text. */
	function passesFilters(work) {
		const authorMatches = author === 'All authors' || work.author === author;
		const genreMatches = genre === 'All genres' || work.genre === genre;
		const titleMatches = work.title.toLowerCase().includes(titleSearch.toLowerCase());
		return authorMatches && genreMatches && titleMatches;
	}

	const matching = $derived(works.filter(passesFilters));
	const shown = $derived(matching.filter((work) => passesFlags(work, null)));

	/** Works with a flag value, given the other filters. */
	function flagCount(flag, wanted) {
		return matching.filter((work) => passesFlags(work, flag) && work[flagColumn(flag)] === wanted).length;
	}

	/** Choose a flag value, or clear it when chosen again. */
	function toggleFlag(flag, wanted) {
		wantedFlags[flag] = wantedFlags[flag] === wanted ? undefined : wanted;
	}
</script>

<svelte:head><title>Works</title></svelte:head>

<h1>Works</h1>
<p>Click a work to see its details.</p>

<div class="filters">
	<Dropdown label="Author" options={authors} bind:value={author} />
	<Dropdown label="Genre" options={genres} bind:value={genre} />
	<div class="field">
		<span>Title contains</span>
		<input class="control" type="text" aria-label="Type to search" placeholder="Type to search" bind:value={titleSearch} />
	</div>
</div>
<div class="flag-filters">
	{#each flagNames as flag (flag)}
		<div class="flag-filter">
			<div class="flag-head"><span>{flag}</span><span>Works</span></div>
			{#each choices as choice (choice.name)}
				{@const count = flagCount(flag, choice.wanted)}
				<button
					type="button"
					aria-pressed={wantedFlags[flag] === choice.wanted}
					style:--share="{(100 * count) / Math.max(1, matching.length)}%"
					onclick={() => toggleFlag(flag, choice.wanted)}
				>
					<span>{choice.name}</span> <span>{formatValue(count, 'wholeNumber')}</span>
				</button>
			{/each}
		</div>
	{/each}
</div>

<DataTable rows={shown} {columns} link={(row) => `/works/${row.work_id}`} />

<style>
	.flag-filters {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(10.5rem, 1fr));
		gap: 0.5rem 0.25rem;
		margin-bottom: 1.5rem;
		font-size: 0.79rem;
		line-height: 1.1875rem;
	}
	.flag-head,
	.flag-filter button {
		display: flex;
		justify-content: space-between;
		padding: 1px 3px;
	}
	.flag-head {
		font-weight: 700;
		border-bottom: 1px solid color-mix(in srgb, var(--color-muted) 60%, transparent);
	}
	.flag-filter button {
		width: 100%;
		border: 0;
		background: linear-gradient(
				to right,
				color-mix(in srgb, var(--color-accent) 15%, transparent) var(--share),
				transparent var(--share)
			);
		cursor: pointer;
	}
	.flag-filter button:hover {
		background-color: var(--color-hover);
	}
	.flag-filter button[aria-pressed='true'] {
		color: var(--color-accent);
		font-weight: 700;
	}
</style>
