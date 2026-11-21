<script>
	// One author: totals, style charts, and their works.
	import FireTitle from '$lib/FireTitle.svelte';
	import BarChart from '$lib/BarChart.svelte';
	import DataTable from '$lib/DataTable.svelte';
	import Definitions from '$lib/Definitions.svelte';
	import { formatValue } from '$lib/format.js';

	let { data } = $props();

	const workColumns = [
		{ id: 'title', title: 'Title' },
		{ id: 'prose_type', title: 'Type' },
		{ id: 'genre', title: 'Genre' },
		{ id: 'word_count', title: 'Words', format: 'wholeNumber' }
	];
</script>

<svelte:head><title>{data.author}</title></svelte:head>

<FireTitle text={data.author} />
<div class="big-values">
	<div>
		<div class="big-label">Works in corpus</div>
		<div class="big-value">{formatValue(data.summary.works, 'wholeNumber')}</div>
	</div>
	<div>
		<div class="big-label">Total words</div>
		<div class="big-value">{formatValue(data.summary.total_words, 'wholeNumber')}</div>
	</div>
</div>

<h2>Signature Stylometrics*</h2>
<BarChart rows={data.distinctive} label="display_name" value="zscore" labelTitle="Metric" measure="z-score" title="Signature Stylometrics" />
<Definitions rows={data.metric_definitions} />

<h2>Sentence Breakdown</h2>
<BarChart rows={data.sentence_types} label="sentence_type" value="proportion" labelTitle="Sentence type" measure="Share" format="percentOneDecimal" title="Sentence Breakdown" />

<h2>Punctuation Preferences</h2>
<BarChart rows={data.punctuation} label="mark" value="zscore" labelTitle="Mark" measure="z-score" title="Punctuation Preferences" />

<h2>Function-word Loves/Hates</h2>
<BarChart rows={data.function_words} label="word" value="zscore" labelTitle="Word" measure="z-score" title="Function-word Loves/Hates" />

<h2>Works</h2>
<DataTable rows={data.works} columns={workColumns} pageSize={0} link={(row) => `/works/${row.work_id}`} />
