---
title: Works
neverShowQueries: true
---

Click a work to see its details.

```sql author_list
select name from (
    select 'All authors' as name, 0 as ord
    union all
    select author, 1
    from warehouse.mart_author
)
order by ord, name
```

<Dropdown data={author_list} name=author value=name title="Author" defaultValue="All authors" />
<TextInput name=title_search title="Title contains" />

```sql works
select
    title,
    author,
    word_count,
    case when is_juvenile = 1 then '✓' else '' end as juvenile,
    case when is_play = 1 then '✓' else '' end as play,
    case when is_poetry = 1 then '✓' else '' end as poetry,
    case when is_translation = 1 then '✓' else '' end as translation,
    '/works/' || work_id as link
from warehouse.mart_work
where ('${inputs.author.value.replaceAll("'", "''")}' = 'All authors'
        or author = '${inputs.author.value.replaceAll("'", "''")}')
    and title ilike '%${String(inputs.title_search).replaceAll("'", "''")}%'
order by word_count desc nulls last
```

<DataTable data={works} link=link rows=25>
    <Column id=title title="Title" wrap=true />
    <Column id=author title="Author" wrap=true />
    <Column id=word_count title="Words" fmt=num0 />
    <Column id=juvenile title="Juvenile" align=center />
    <Column id=play title="Play" align=center />
    <Column id=poetry title="Poetry" align=center />
    <Column id=translation title="Translation" align=center />
</DataTable>
