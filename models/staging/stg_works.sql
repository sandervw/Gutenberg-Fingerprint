-- One row per work off silver raw_works.
-- lower() everything (Fabric collation is case-sensitive); no [ in LIKE (T-SQL);
-- locc is a '; '-joined list, '; '-prefixed so each element matches as '%; <code>%'.
{% set locc_list = dbt.concat(["'; '", "coalesce(locc, '')"]) %}
{% set foreign_lit = ['PA', 'PG', 'PH', 'PJ', 'PK', 'PL', 'PQ', 'PT'] %}

select
    cast(gutenberg_id as {{ dbt.type_bigint() }})   as gutenberg_id,
    cast(title as {{ dbt.type_string() }})          as title,
    cast(authors as {{ dbt.type_string() }})        as authors,
    -- primary author; parse rule lives in macros/parse_primary_author.sql.
    -- Blank -> 'Unknown' member so author_key never goes null downstream.
    coalesce(nullif({{ parse_primary_author('authors') }}, ''), 'Unknown')
                                                    as author_name,
    cast(nullif(issued, '') as date)                as issued,
    cast(subjects as {{ dbt.type_string() }})       as subjects,
    cast(bookshelves as {{ dbt.type_string() }})    as bookshelves,
    case
        when lower(authors) like '%translator%'                 then 1
        when lower(subjects) like '%translations into english%' then 1
        {%- for code in foreign_lit %}
        when {{ locc_list }} like '%; {{ code }}%' then 1
        {%- endfor %}
        else 0
    end                                             as is_translation,
    case
        when {{ locc_list }} like '%; PZ%'     then 1
        when lower(subjects) like '%juvenile%' then 1
        else 0
    end                                             as is_juvenile,
    case
        when lower(subjects) like '%drama%'                    then 1
        when lower(subjects) like '%plays%'                    then 1
        when lower(bookshelves) like '%plays/films/dramas%'    then 1
        else 0
    end                                             as is_play,
    case
        when lower(subjects) like '%poetry%' then 1
        else 0
    end                                             as is_poetry,
    cast(loaded_at as {{ dbt.type_timestamp() }})   as loaded_at
from {{ source('raw', 'raw_works') }}
