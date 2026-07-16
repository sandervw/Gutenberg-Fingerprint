-- One row per work: catalog works off stg_works, plus the self corpus off the
-- seed (those texts aren't in the lakehouse yet). author_key hashes the same
-- name dim_author hashes, so every work points at a real author row.
select
    {{ dbt_utils.generate_surrogate_key(['gutenberg_id']) }} as work_key,
    {{ dbt_utils.generate_surrogate_key(['author_name']) }}  as author_key,
    cast(gutenberg_id as {{ dbt.type_string() }})            as work_id,
    title,
    is_translation,
    is_juvenile,
    is_play,
    is_poetry,
    cast(null as {{ dbt.type_bigint() }})                    as word_count,
    cast(null as {{ dbt.type_string() }})                    as prose_type
from {{ ref('stg_works') }}

union all

select
    {{ dbt_utils.generate_surrogate_key(['work_id']) }},
    {{ dbt_utils.generate_surrogate_key(['author']) }},
    work_id,
    title,
    0,
    0,
    0,
    0,
    cast(null as {{ dbt.type_bigint() }}),
    cast(null as {{ dbt.type_string() }})
from {{ ref('seed_authors') }}
