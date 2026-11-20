<script>
	// One work: byline and style charts.
	import SerpentMark from '$lib/SerpentMark.svelte';
	import BarChart from '$lib/BarChart.svelte';
	import Definitions from '$lib/Definitions.svelte';
	import { formatValue } from '$lib/format.js';

	let { data } = $props();
	const work = $derived(data.work);
</script>

<svelte:head><title>{work.title}</title></svelte:head>

<h1><a class="link" href={work.work_link}>{work.title}</a></h1>
<!-- One line: the byline text must not contain line breaks. -->
<p>By <a class="value" href="/authors/{encodeURIComponent(work.author)}">{work.author}</a> - <span class="value">{work.genre}</span> <span class="value">{work.prose_type}</span>, <span class="value">{formatValue(work.word_count, 'wholeNumber')}</span> words.</p>

<h2>Departure from the Author's Norm*</h2>
<p>This work's z-score minus the author's average.</p>
<BarChart rows={data.deviation} label="display_name" value="delta" title="Departure from the Author's Norm" />

<h2>Work Signature</h2>
<p>The work's z-scores against all measured works.</p>
<BarChart rows={data.signature} label="display_name" value="zscore" title="Work Signature" mark={SerpentMark} />

<h2>Sentence Type Mix</h2>
<p>Share of simple, compound, and complex sentences.</p>
<BarChart rows={data.sentence_types} label="sentence_type" value="proportion" format="percentOneDecimal" title="Sentence Type Mix" />

<h2>Punctuation</h2>
<p>How this work's punctuation rates sit against the whole corpus (z-scores).</p>
<BarChart rows={data.punctuation} label="mark" value="zscore" title="Punctuation" />

<h2>Function-word Loves/Hates</h2>
<p>The work's 12 most unusual function-word rates vs the whole corpus.</p>
<BarChart rows={data.function_words} label="word" value="zscore" title="Function-word Loves/Hates" />

<Definitions rows={data.metric_definitions} />
