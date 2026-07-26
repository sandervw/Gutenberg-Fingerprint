---
title: Authors
---

Authors with at least one measured work.

```sql authors
select
    author as name,
    works,
    total_words as words,
    '/authors/' || author as link
from warehouse.mart_author
order by works desc, author
```

<DataTable data={authors} link=link rows=25 search=true>
    <Column id=name title="Author" />
    <Column id=works title="Works" />
    <Column id=words title="Words" fmt=num0 />
</DataTable>
