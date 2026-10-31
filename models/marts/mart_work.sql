-- One row per measured work: dim_work attributes plus author name.
-- Excess ranks distinctiveness: summed z-score mass beyond +/-2.

with excess as (

    select
        work_key,
        sum(case when abs(zscore) > 2.0 then abs(zscore) - 2.0 else 0 end) as excess,
        count(*) as series_measured
    from {{ ref('mart_style_long') }}
    group by work_key

)

select
    -- work
    w.work_key,
    w.work_id,
    w.title,
    w.genre,
    w.prose_type,
    w.word_count,
    w.is_translation,
    w.is_juvenile,
    w.is_play,
    w.is_poetry,
    w.issue_date,
    w.ingested_at,

    -- author
    w.author_key,
    a.name as author,
    a.is_self,

    -- rollups over the work's series
    e.excess,
    e.series_measured

from {{ ref('dim_work') }} w
inner join {{ ref('dim_author') }} a on a.author_key = w.author_key
inner join excess e on e.work_key = w.work_key  -- measured works only
