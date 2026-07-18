-- int_measurements_normalized
-- Grain: one row per work x measured series (# works x 63 = 8,505)

with measurements as (

    select
        work_id,
        metric_name,
        value,
        loaded_at
    from {{ ref('stg_measurements') }}
    -- word_count is a dim_work attribute, not a style series; keep it out of z-scores.
    where metric_name <> 'word_count'

),

-- Map each measured (child) name onto its metric concept name by prefix.
bridged as (

    select
        work_id,
        metric_name,
        value,
        case
            when metric_name like 'funcword_%' then 'function_word_frequency'
            when metric_name like 'punct_%'    then 'punctuation_frequency'
            when metric_name like 'senttype_%' then 'sentence_type_mix'
            else metric_name
        end as concept_name,
        loaded_at
    from measurements

),

-- Attach the concept's surrogate key
joined as (

    select
        bridged.work_id,
        bridged.metric_name,
        dim_metric.metric_key,
        bridged.value,
        bridged.loaded_at
    from bridged
    left join {{ ref('dim_metric') }} as dim_metric
        on bridged.concept_name = dim_metric.metric_name

)

select
    work_id,
    metric_key,
    metric_name,
    value,
    loaded_at
from joined
