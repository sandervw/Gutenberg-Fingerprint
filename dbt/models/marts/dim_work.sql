-- One row per work: self corpus + catalog.
select
    {{ dbt_utils.generate_surrogate_key(['work_id']) }} as work_key,
    {{ dbt_utils.generate_surrogate_key(['author']) }}  as author_key,
    work_id,
    title,
    0 as is_translation,
    0 as is_juvenile,
    0 as is_play,
    0 as is_poetry,
    cast(null as {{ dbt.type_bigint() }}) as word_count,
    cast(null as {{ dbt.type_string() }}) as prose_type
from {{ ref('seed_authors') }}

union all

select
    {{ dbt_utils.generate_surrogate_key(['gutenberg_id']) }},
    cast(null as {{ dbt.type_string() }}),
    cast(gutenberg_id as {{ dbt.type_string() }}),
    title,
    is_translation,
    is_juvenile,
    is_play,
    is_poetry,
    cast(null as {{ dbt.type_bigint() }}),
    cast(null as {{ dbt.type_string() }})
from {{ ref('stg_works') }}
