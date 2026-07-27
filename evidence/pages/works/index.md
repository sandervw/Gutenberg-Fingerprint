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

```sql genre_list
select name from (
    select 'All genres' as name, 0 as ord
    union all
    select distinct genre, 1
    from warehouse.mart_work
)
order by ord, name
```

<Dropdown data={author_list} name=author value=name title="Author" defaultValue="All authors" />
<Dropdown data={genre_list} name=genre value=name title="Genre" defaultValue="All genres" />
<TextInput name=title_search title="Title contains" />

```sql flag_options
select
    case when is_juvenile = 1 then 'Yes' else 'No' end as juvenile,
    case when is_play = 1 then 'Yes' else 'No' end as play,
    case when is_poetry = 1 then 'Yes' else 'No' end as poetry,
    case when is_translation = 1 then 'Yes' else 'No' end as translation
from warehouse.mart_work
where ('${inputs.author.value.replaceAll("'", "''")}' = 'All authors'
        or author = '${inputs.author.value.replaceAll("'", "''")}')
    and ('${inputs.genre.value.replaceAll("'", "''")}' = 'All genres'
        or genre = '${inputs.genre.value.replaceAll("'", "''")}')
    and title ilike '%${String(inputs.title_search).replaceAll("'", "''")}%'
```

<DimensionGrid data={flag_options} name=work_flags metricLabel="Works" limit=2 />

```sql works
select * from (
    select
        title,
        author,
        genre,
        word_count,
        case when is_juvenile = 1 then 'Yes' else 'No' end as juvenile,
        case when is_play = 1 then 'Yes' else 'No' end as play,
        case when is_poetry = 1 then 'Yes' else 'No' end as poetry,
        case when is_translation = 1 then 'Yes' else 'No' end as translation,
        concat_ws(', ',
            case when is_juvenile = 1 then 'Juvenile' end,
            case when is_play = 1 then 'Play' end,
            case when is_poetry = 1 then 'Poetry' end,
            case when is_translation = 1 then 'Translation' end
        ) as flags,
        '/works/' || work_id as link
    from warehouse.mart_work
    where ('${inputs.author.value.replaceAll("'", "''")}' = 'All authors'
            or author = '${inputs.author.value.replaceAll("'", "''")}')
        and ('${inputs.genre.value.replaceAll("'", "''")}' = 'All genres'
            or genre = '${inputs.genre.value.replaceAll("'", "''")}')
        and title ilike '%${String(inputs.title_search).replaceAll("'", "''")}%'
)
where ${inputs.work_flags}
order by word_count desc nulls last
```

<DataTable data={works} link=link rows=25>
    <Column id=title title="Title" wrap=true />
    <Column id=author title="Author" wrap=true />
    <Column id=word_count title="Words" fmt=num0 />
    <Column id=genre title="Genre" />
    <Column id=flags title="Flags" wrap=true />
</DataTable>
