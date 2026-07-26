-- Report-serving OBT at work x child series grain.
-- Work and author attributes live in mart_work and mart_author.

with fact as (
    select * from {{ ref('fact_style_measurement') }}
)

select
    -- keys the pages filter on
    f.work_key,
    w.work_id,
    f.author_key,
    a.name as author,

    -- metric
    f.metric_key,
    f.metric_name,                       -- child series, e.g. funcword_the
    dm.metric_name as concept_name,      -- parent concept
    dm.display_name,
    dm.category,
    dm.is_multivalue,
    case dm.metric_name                  -- child label, family prefix stripped
        when 'function_word_frequency' then replace(f.metric_name, 'funcword_', '')
        when 'sentence_type_mix'       then replace(f.metric_name, 'senttype_', '')
        when 'punctuation_frequency'   then replace(f.metric_name, 'punct_', '')
        else f.metric_name
    end as series_label,

    -- measures (non-additive: never SUM)
    f.value,
    {{ zscore('f.value', 'f.metric_name') }} as zscore

from fact f
inner join {{ ref('dim_work') }}   w  on w.work_key   = f.work_key
inner join {{ ref('dim_author') }} a  on a.author_key = f.author_key
inner join {{ ref('dim_metric') }} dm on dm.metric_key = f.metric_key
