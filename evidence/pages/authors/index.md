---
title: Authors
---

Authors with at least one measured work.

```sql authors
with measured_works as (
    select distinct author, work_key, word_count
    from warehouse.mart_style_long
)
select
    author as name,
    count(*) as works,
    sum(word_count) as words,
    '/authors/' || author as link
from measured_works
group by author
order by works desc, author
```

<DataTable data={authors} link=link rows=25 search=true>
    <Column id=name title="Author" />
    <Column id=works title="Works" />
    <Column id=words title="Words" fmt=num0 />
</DataTable>
