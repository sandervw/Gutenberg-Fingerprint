---
title: Author Summary
---

# {params.author}

```sql summary
select
    works,
    total_words
from warehouse.mart_author
where author = '${params.author.replaceAll("'", "''")}'
```

<Grid cols=2>
    <BigValue data={summary} value=works title="Works in corpus" />
    <BigValue data={summary} value=total_words title="Total words" fmt=num0 />
</Grid>

## Signature Stylometrics*

```sql distinctive
select
    display_name,
    avg(zscore) as zscore
from warehouse.mart_style_long
where author = '${params.author.replaceAll("'", "''")}'
    and is_multivalue = false
group by display_name
order by abs(avg(zscore)) desc
```

<div role="img" aria-label="Signature Stylometrics chart">

<BarChart
    data={distinctive}
    x=display_name
    y=zscore
    swapXY=true
    yFmt=num2
    sort=false
/>

</div>

```sql metric_defs
select
    dm.display_name,
    dm.description
from warehouse.dim_metric dm
where dm.is_multivalue = false
    and dm.metric_name <> 'jaccard'
order by dm.display_name
```

<Accordion>
    <AccordionItem title="*Definitions">

<DataTable data={metric_defs} rows=11>
    <Column id=display_name title="Metric" />
    <Column id=description title="Definition" wrap=true />
</DataTable>

    </AccordionItem>
</Accordion>

## Sentence Breakdown

```sql sentence_types
select
    series_label as sentence_type,
    avg(value) as proportion
from warehouse.mart_style_long
where author = '${params.author.replaceAll("'", "''")}'
    and concept_name = 'sentence_type_mix'
group by series_label
order by proportion desc
```

<div role="img" aria-label="Sentence Breakdown chart">

<BarChart
    data={sentence_types}
    x=sentence_type
    y=proportion
    swapXY=true
    yFmt=pct1
    sort=false
/>

</div>

## Punctuation Preferences

```sql punctuation
select
    series_label as mark,
    avg(zscore) as zscore
from warehouse.mart_style_long
where author = '${params.author.replaceAll("'", "''")}'
    and concept_name = 'punctuation_frequency'
group by series_label
order by zscore desc
```

<div role="img" aria-label="Punctuation Preferences chart">

<BarChart
    data={punctuation}
    x=mark
    y=zscore
    swapXY=true
    yFmt=num2
    sort=false
/>

</div>

## Function-word Loves/Hates

```sql function_words
select word, zscore
from (
    select
        series_label as word,
        avg(zscore) as zscore
    from warehouse.mart_style_long
    where author = '${params.author.replaceAll("'", "''")}'
        and concept_name = 'function_word_frequency'
    group by series_label
    order by abs(avg(zscore)) desc
    limit 12
)
order by abs(zscore) desc
```

<div role="img" aria-label="Function-word Loves/Hates chart">

<BarChart
    data={function_words}
    x=word
    y=zscore
    swapXY=true
    yFmt=num2
    sort=false
/>

</div>

## Works

```sql works
select
    title,
    prose_type,
    genre,
    word_count,
    '/works/' || work_id as link
from warehouse.mart_work
where author = '${params.author.replaceAll("'", "''")}'
order by word_count desc
```

<DataTable data={works} link=link rows=all>
    <Column id=title title="Title" />
    <Column id=prose_type title="Type" />
    <Column id=genre title="Genre" />
    <Column id=word_count title="Words" fmt=num0 />
</DataTable>
