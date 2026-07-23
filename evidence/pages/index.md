---
title: Gutenberg Fiction Metrics
neverShowQueries: true
---

A metric-based comparison of authors and works of fantasy and science fiction in [Project Gutenberg](https://www.gutenberg.org/). Measured as **z-scores**. Positive means a work does *more* of something than the typical work; negative, less.

## Biggest Outliers

The most statistically distinctive works, ranked by an **excess** index: for each work, the sum of every metric's z-score beyond ±2. This rewards both *how many* extreme scores a work has and *how* extreme they are. Works under 20,000 words are excluded.

Use the grid to filter by category (unselected = include all, **Yes** = only, **No** = exclude).

```sql work_flags
select
    case when dw.is_poetry = 1 then 'Yes' else 'No' end as poetry,
    case when dw.is_juvenile = 1 then 'Yes' else 'No' end as juvenile,
    case when dw.is_play = 1 then 'Yes' else 'No' end as play,
    case when dw.is_translation = 1 then 'Yes' else 'No' end as translation
from warehouse.dim_work dw
where dw.work_key in (select work_key from warehouse.mart_style_long)
    and dw.word_count >= 20000
```

```sql outliers
with work_excess as (
    select
        work_key,
        sum(greatest(abs(zscore) - 2.0, 0)) as excess
    from warehouse.mart_style_long
    group by work_key
),
ranked as (
    select
        dw.title,
        da.name as author,
        case when dw.is_poetry = 1 then '✓' else '' end as poetry_flag,
        case when dw.is_juvenile = 1 then '✓' else '' end as juvenile_flag,
        case when dw.is_play = 1 then '✓' else '' end as play_flag,
        case when dw.is_translation = 1 then '✓' else '' end as translation_flag,
        we.excess,
        '/works/' || dw.work_id as link,
        case when dw.is_poetry = 1 then 'Yes' else 'No' end as poetry,
        case when dw.is_juvenile = 1 then 'Yes' else 'No' end as juvenile,
        case when dw.is_play = 1 then 'Yes' else 'No' end as play,
        case when dw.is_translation = 1 then 'Yes' else 'No' end as translation
    from work_excess we
    join warehouse.dim_work dw
        on dw.work_key = we.work_key
    join warehouse.dim_author da
        on da.author_key = dw.author_key
    where dw.word_count >= 20000
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

Jaccard overlap of vocabulary. How [my fiction](https://wordleaves.com) compares to other authors in the corpus. Higher = more shared words.

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
