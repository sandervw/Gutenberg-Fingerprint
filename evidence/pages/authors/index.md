---
title: Authors
---

Authors with at least one measured work.

```sql authors
select
    da.name,
    count(dw.work_key) as works,
    sum(dw.word_count) as words,
    '/authors/' || da.name as link
from warehouse.dim_author da
join warehouse.dim_work dw
    on dw.author_key = da.author_key
where dw.work_key in (
    select work_key from warehouse.mart_style_long
)
group by da.name
order by works desc, da.name
```

<DataTable data={authors} link=link rows=25 search=true>
    <Column id=name title="Author" />
    <Column id=works title="Works" />
    <Column id=words title="Words" fmt=num0 />
</DataTable>
