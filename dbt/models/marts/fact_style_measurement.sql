-- fact_style_measurement
-- Central fact: one row per work x measured series, keyed (work_id, metric_name).
-- Raw value only; z-scores are corpus-relative and live in the marts.

with measurements as (

    select
        work_id,
        metric_key,
        metric_name,
        value
    from {{ ref('int_measurements_normalized') }}

),

works as (  -- conformed work + author keys

    select
        work_id,
        work_key,
        author_key
    from {{ ref('dim_work') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['measurements.work_id', 'measurements.metric_name']) }} as measurement_key,
    works.work_key,
    works.author_key,
    measurements.metric_key,   -- FK -> dim_metric (concept grain)
    measurements.metric_name,  -- child series name (metric_key is concept-grain)
    measurements.value
from measurements
inner join works on works.work_id = measurements.work_id
