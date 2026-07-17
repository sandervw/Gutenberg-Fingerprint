---
title: Prose Fingerprint
neverShowQueries: true
---

How [my prose](https://wordleaves.com) compares to the authors in the measured corpus, (measured as **z-scores**). Positive means a work does *more* of something than the typical work; negative, less.

## Largest Outliers

The 25 works furthest from the corpus average on the chosen metric.

```sql metric_options
select
    metric_name,
    display_name
from warehouse.dim_metric
where is_multivalue = false
    and metric_name <> 'jaccard'
order by display_name
```

```sql outliers
select
    case
        when length(msl.title) > 48 then left(msl.title, 45) || '…'
        else msl.title
    end as work_label,
    msl.zscore
from warehouse.mart_style_long msl
join warehouse.dim_work dw
    on dw.work_key = msl.work_key
where msl.is_multivalue = false
    and msl.metric_name = '${inputs.metric.value}'
    and case '${inputs.plays.value}'
        when 'only' then dw.is_play = 1
        when 'exclude' then dw.is_play = 0
        else true end
    and case '${inputs.juvenile.value}'
        when 'only' then dw.is_juvenile = 1
        when 'exclude' then dw.is_juvenile = 0
        else true end
    and case '${inputs.poetry.value}'
        when 'only' then dw.is_poetry = 1
        when 'exclude' then dw.is_poetry = 0
        else true end
order by abs(msl.zscore) desc
limit 25
```

<Dropdown data={metric_options} name=metric value=metric_name label=display_name title="Metric" defaultValue=mean_sentence_length />
<Dropdown name=plays title="Plays" defaultValue=all>
    <DropdownOption value=all valueLabel="Include" />
    <DropdownOption value=exclude valueLabel="Exclude" />
    <DropdownOption value=only valueLabel="Only" />
</Dropdown>
<Dropdown name=juvenile title="Juvenile" defaultValue=all>
    <DropdownOption value=all valueLabel="Include" />
    <DropdownOption value=exclude valueLabel="Exclude" />
    <DropdownOption value=only valueLabel="Only" />
</Dropdown>
<Dropdown name=poetry title="Poetry" defaultValue=all>
    <DropdownOption value=all valueLabel="Include" />
    <DropdownOption value=exclude valueLabel="Exclude" />
    <DropdownOption value=only valueLabel="Only" />
</Dropdown>

<BarChart
    data={outliers}
    x=work_label
    y=zscore
    swapXY=true
    sort=false
    yFmt=num2
/>

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

Jaccard overlap of vocabulary. Higher = more shared words. Top 25 of the corpus.

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
