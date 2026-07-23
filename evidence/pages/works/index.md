---
title: Works
neverShowQueries: true
---

Click a work to see its details.

```sql author_list
select name from (
    select 'All authors' as name, 0 as ord
    union all
    select distinct author, 1
    from warehouse.mart_style_long
)
order by ord, name
```

<Dropdown data={author_list} name=author value=name title="Author" defaultValue="All authors" />
<TextInput name=title_search title="Title contains" />

```sql works
select
    dw.title,
    da.name as author,
    dw.word_count,
    case when dw.is_juvenile = 1 then '✓' else '' end as juvenile,
    case when dw.is_play = 1 then '✓' else '' end as play,
    case when dw.is_poetry = 1 then '✓' else '' end as poetry,
    case when dw.is_translation = 1 then '✓' else '' end as translation,
    '/works/' || dw.work_id as link
from warehouse.dim_work dw
join warehouse.dim_author da
    on dw.author_key = da.author_key
where dw.work_key in (
    select work_key from warehouse.mart_style_long
)
    and ('${inputs.author.value.replaceAll("'", "''")}' = 'All authors'
        or da.name = '${inputs.author.value.replaceAll("'", "''")}')
    and dw.title ilike '%${String(inputs.title_search).replaceAll("'", "''")}%'
order by dw.word_count desc nulls last
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
