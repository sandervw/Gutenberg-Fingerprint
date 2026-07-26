-- One row per work: catalog works off stg_works, plus the self corpus off the
-- seed. author_key hashes the same name dim_author hashes, so every work points
-- at a real author row. word_count rides raw_measurements as its own series.

-- Incremental for retention: a rebuild would restamp ingested_at.
-- post_hook sweeps departed works; seed rows must survive.

{{ config(
    materialized='incremental',
    unique_key='work_key',
    on_schema_change='fail',
    post_hook="
        delete from {{ this }}
        where work_id not in (
            select cast(gutenberg_id as {{ dbt.type_string() }}) from {{ ref('stg_works') }}
            union all
            select work_id from {{ ref('seed_authors') }}
        )
    "
) }}

with works as (

    select
        cast(gutenberg_id as {{ dbt.type_string() }}) as work_id,
        title,
        author_name,
        genre,
        is_translation,
        is_juvenile,
        is_play,
        is_poetry
    from {{ ref('stg_works') }}

    union all

    select
        work_id,
        title,
        author as author_name,
        cast('Undetermined' as {{ dbt.type_string() }}),
        0,
        0,
        0,
        0
    from {{ ref('seed_authors') }}

),

word_counts as (

    select
        work_id,
        cast(max(value) as {{ dbt.type_bigint() }}) as word_count
    from {{ ref('stg_measurements') }}
    where metric_name = 'word_count'
    group by work_id

)

select
    {{ dbt_utils.generate_surrogate_key(['works.work_id']) }}     as work_key,
    {{ dbt_utils.generate_surrogate_key(['works.author_name']) }} as author_key,
    works.work_id,
    works.title,
    works.genre,
    works.is_translation,
    works.is_juvenile,
    works.is_play,
    works.is_poetry,
    word_counts.word_count,
    case
        when word_counts.word_count < 10000 then 'short-story'
        when word_counts.word_count < 40000 then 'novella'
        when word_counts.word_count is not null then 'novel'
    end as prose_type,
    -- Merge updates all columns; coalesce holds the original stamp.
    {%- if is_incremental() %}
    coalesce(prior.ingested_at, {{ run_stamp() }}) as ingested_at
    {%- else %}
    {{ run_stamp() }} as ingested_at
    {%- endif %}
from works
left join word_counts
    on word_counts.work_id = works.work_id
{%- if is_incremental() %}
left join {{ this }} as prior
    on prior.work_key = {{ dbt_utils.generate_surrogate_key(['works.work_id']) }}
{%- endif %}
