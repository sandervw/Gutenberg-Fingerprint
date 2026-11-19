<script>
	// One author: totals, style charts, and their works.
	import BarChart from '$lib/BarChart.svelte';
	import DataTable from '$lib/DataTable.svelte';
	import Definitions from '$lib/Definitions.svelte';
	import { formatValue } from '$lib/format.js';

	let { data } = $props();

	const workColumns = [
		{ id: 'title', title: 'Title' },
		{ id: 'prose_type', title: 'Type' },
		{ id: 'genre', title: 'Genre' },
		{ id: 'word_count', title: 'Words', format: 'num0' }
	];
</script>

<svelte:head><title>{data.author}</title></svelte:head>

<h1>{data.author}</h1>
<div class="big-values">
	<div>
		<div class="meta">Works in corpus</div>
		<div class="big-value">{formatValue(data.summary.works, 'num0')}</div>
	</div>
	<div>
		<div class="meta">Total words</div>
		<div class="big-value">{formatValue(data.summary.total_words, 'num0')}</div>
	</div>
</div>

<h2>Signature Stylometrics*</h2>
<BarChart rows={data.distinctive} label="display_name" value="zscore" title="Signature Stylometrics" />
<Definitions rows={data.metric_defs} />

<h2>Sentence Breakdown</h2>
<BarChart rows={data.sentence_types} label="sentence_type" value="proportion" format="pct1" title="Sentence Breakdown" />

<h2>Punctuation Preferences</h2>
<BarChart rows={data.punctuation} label="mark" value="zscore" title="Punctuation Preferences" />

<h2>Function-word Loves/Hates</h2>
<BarChart rows={data.function_words} label="word" value="zscore" title="Function-word Loves/Hates" />

<h2>Works</h2>
<DataTable rows={data.works} columns={workColumns} pageSize={0} link={(row) => `/works/${row.work_id}`} />
