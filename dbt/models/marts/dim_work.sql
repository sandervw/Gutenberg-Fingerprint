-- One row per measured work: catalog works off stg_works, plus the self corpus
-- off the seed. author_key hashes the same name dim_author hashes, so every work
-- points at a real author row. word_count rides raw_measurements as its own series.

with works as (

    select
        cast(gutenberg_id as {{ dbt.type_string() }}) as work_id,
        title,
        author_name,
        genre,
        is_translation,
        is_juvenile,
        is_play,
        is_poetry,
        issued as issue_date
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
        0,
        cast(null as date)
    from {{ ref('seed_authors') }}

),

measured as (

    select
        work_id,
        cast(max(value) as {{ dbt.type_bigint() }}) as word_count,
        min(loaded_at) as ingested_at
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
    measured.word_count,
    case
        when measured.word_count < 10000 then 'short-story'
        when measured.word_count < 40000 then 'novella'
        else 'novel'
    end as prose_type,
    works.issue_date,
    measured.ingested_at
from works
-- inner: unmeasured and departed catalog works stay out
inner join measured
    on measured.work_id = works.work_id
