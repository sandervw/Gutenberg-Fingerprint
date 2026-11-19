<script>
	// Works list with author, genre, title, and flag filters.
	import DataTable from '$lib/DataTable.svelte';
	import Dropdown from '$lib/Dropdown.svelte';
	import { formatValue } from '$lib/format.js';

	let { data } = $props();

	const flagNames = ['Juvenile', 'Play', 'Poetry', 'Translation'];
	const choices = [
		{ name: 'Yes', wanted: 1 },
		{ name: 'No', wanted: 0 }
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
		return flagNames.every(
			(flag) => flag === skippedFlag || wantedFlags[flag] === undefined || work[flagColumn(flag)] === wantedFlags[flag]
		);
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
	<input class="control" type="text" aria-label="Type to search" placeholder="Title contains" bind:value={titleSearch} />
</div>
<div class="filters">
	{#each flagNames as flag (flag)}
		<div>
			<div class="meta">{flag}</div>
			{#each choices as choice (choice.name)}
				<button
					class="control"
					type="button"
					aria-pressed={wantedFlags[flag] === choice.wanted}
					onclick={() => toggleFlag(flag, choice.wanted)}
				>
					{choice.name} <span>{formatValue(flagCount(flag, choice.wanted), 'wholeNumber')}</span>
				</button>
			{/each}
		</div>
	{/each}
</div>

<DataTable rows={shown} {columns} link={(row) => `/works/${row.work_id}`} />
