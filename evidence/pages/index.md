---
title: Gutenberg Fiction Metrics
neverShowQueries: true
---

A metric-based comparison of fantasy and science fiction in [Project Gutenberg](https://www.gutenberg.org/). Measured as **z-scores**. Positive means a work does *more* of something than the typical work; negative, less.

```sql last_refreshed
select max(ingested_at) as refreshed,
  count(work_id) as work_count
from warehouse.mart_work
```

*<Value data={last_refreshed} column=work_count/> works in corpus - Last refreshed <Value data={last_refreshed} column=refreshed fmt=longdate/>.*

## Weirdest Works

The most statistically distinctive fiction, ranked by an **excess** index: for each work, the sum of every metric's z-score beyond ±2. Excludes plays, translations, juvenile fiction, poetry, and works under 10,000 words.

```sql outliers
select
    title,
    author,
    genre,
    word_count,
    excess,
    '/works/' || work_id as link
from warehouse.mart_work
where is_play = 0
    and is_translation = 0
    and is_juvenile = 0
    and is_poetry = 0
    and word_count >= 10000
order by excess desc
limit 25
```

<DataTable data={outliers} link=link rows=25>
    <Column id=title title="Work" wrap=true />
    <Column id=author title="Author" wrap=true />
    <Column id=genre title="Genre" />
    <Column id=word_count title="Words" fmt=num0 />
    <Column id=excess title="Excess" fmt=num1 />
</DataTable>

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
