---
title: Gutenberg Fiction Metrics
neverShowQueries: true
---

A metric-based comparison of fantasy and science fiction in [Project Gutenberg](https://www.gutenberg.org/). Measured as **z-scores**. Positive means a work does *more* of something than the typical work; negative, less.

```sql last_refreshed
select max(ingested_at) as refreshed
from warehouse.mart_style_long
```

*Last refreshed <Value data={last_refreshed} column=refreshed fmt=longdate/>*

## Weirdest Works

The most statistically distinctive fiction, ranked by an **excess** index: for each work, the sum of every metric's z-score beyond ±2. Works under 20,000 words are excluded.

Use the grid to filter by category (unselected = include all, **Yes** = only, **No** = exclude).

```sql work_flags
select
    case when is_poetry = 1 then 'Yes' else 'No' end as poetry,
    case when is_juvenile = 1 then 'Yes' else 'No' end as juvenile,
    case when is_play = 1 then 'Yes' else 'No' end as play,
    case when is_translation = 1 then 'Yes' else 'No' end as translation
from warehouse.mart_style_long
where word_count >= 20000
group by work_key, is_poetry, is_juvenile, is_play, is_translation
```

```sql outliers
with ranked as (
    select
        title,
        author,
        case when max(is_poetry) = 1 then '✓' else '' end as poetry_flag,
        case when max(is_juvenile) = 1 then '✓' else '' end as juvenile_flag,
        case when max(is_play) = 1 then '✓' else '' end as play_flag,
        case when max(is_translation) = 1 then '✓' else '' end as translation_flag,
        sum(greatest(abs(zscore) - 2.0, 0)) as excess,
        '/works/' || work_id as link,
        case when max(is_poetry) = 1 then 'Yes' else 'No' end as poetry,
        case when max(is_juvenile) = 1 then 'Yes' else 'No' end as juvenile,
        case when max(is_play) = 1 then 'Yes' else 'No' end as play,
        case when max(is_translation) = 1 then 'Yes' else 'No' end as translation
    from warehouse.mart_style_long
    where word_count >= 20000
    group by work_key, work_id, title, author
)
select *
from ranked
where ${inputs.filters}
order by excess desc
limit 25
```

<DimensionGrid data={work_flags} name=filters metric="count(*)" metricLabel="Count" fmt=num0 limit=2 />

<DataTable data={outliers} link=link rows=25>
    <Column id=title title="Title" wrap=true />
    <Column id=author title="Author" wrap=true />
    <Column id=poetry_flag title="Poetry" align=center />
    <Column id=juvenile_flag title="Juvenile" align=center />
    <Column id=play_flag title="Play" align=center />
    <Column id=translation_flag title="Translation" align=center />
    <Column id=excess title="Excess" fmt=num1 />
</DataTable>

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
    <AccordionItem title="Metric definitions">

<DataTable data={metric_defs} rows=11>
    <Column id=display_name title="Metric" />
    <Column id=description title="Definition" wrap=true />
</DataTable>

    </AccordionItem>
</Accordion>

## Vocabulary Overlap

Jaccard overlap of vocabulary. How [my fiction](https://wordleaves.com) compares to other authors. Higher = more shared words.

```sql kinship
select
    da.name as author,
    fvo.jaccard
from warehouse.fact_vocab_overlap fvo
join warehouse.dim_author da
    on fvo.author_key_b = da.author_key
order by fvo.jaccard desc
limit 25
```

<BarChart
    data={kinship}
    x=author
    y=jaccard
    swapXY=true
    yFmt=pct2
/>

---

Built with dbt, Microsoft Fabric, and Evidence — [source on GitHub](https://github.com/sandervw/Gutenberg-Fingerprint).
