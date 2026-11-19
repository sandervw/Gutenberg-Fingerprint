<script>
	// Home: corpus summary, Weirdest Works, Vocabulary Overlap.
	import BarChart from '$lib/BarChart.svelte';
	import DataTable from '$lib/DataTable.svelte';
	import { formatValue, longDate } from '$lib/format.js';

	let { data } = $props();

	const weirdestColumns = [
		{ id: 'title', title: 'Work' },
		{ id: 'author', title: 'Author' },
		{ id: 'genre', title: 'Genre' },
		{ id: 'word_count', title: 'Words', format: 'wholeNumber' },
		{ id: 'excess', title: 'Excess', format: 'oneDecimal' }
	];
</script>

<svelte:head><title>Gutenberg Fiction Metrics</title></svelte:head>

<h1>Gutenberg Fiction Metrics</h1>
<p>
	A metric-based comparison of science fiction, fantasy, and horror in
	<a href="https://www.gutenberg.org/">Project Gutenberg</a>. Measured as <strong>z-scores</strong>. Positive means a
	work does <em>more</em> of something than the typical work; negative, less.
</p>
<p>
	<em>
		There are currently {formatValue(data.summary.work_count, 'wholeNumber')} works in this corpus. The lastest Gutenberg work
		of speculative fiction arrived on {longDate(data.summary.refreshed)}.
	</em>
</p>

<h2>Weirdest Works</h2>
<p>
	The most statistically distinctive fiction, ranked by <strong>excess</strong>: for each work, the sum of every
	metric's z-score beyond ±2. Shorter works are excluded.
</p>
<DataTable rows={data.weirdest_works} columns={weirdestColumns} link={(row) => `/works/${row.work_id}`} />

<h2>Vocabulary Overlap</h2>
<p>
	Jaccard overlap of vocabulary. How <a href="https://wordleaves.com">my fiction</a> compares to other authors. Higher
	= more shared words.
</p>
<BarChart rows={data.vocabulary_overlap} label="author" value="jaccard" format="percentTwoDecimals" title="Vocabulary Overlap" />

<hr />
<p>
	Built with dbt, Postgres, Dagster, and SvelteKit —
	<a href="https://github.com/sandervw/Gutenberg-Fingerprint">source on GitHub</a>.
</p>
