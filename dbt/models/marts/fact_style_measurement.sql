-- fact_style_measurement
-- Central fact: one row per work x measured series, keyed (work_id, metric_name).
-- Raw value only; z-scores are corpus-relative and live in the marts.
-- Incremental: loaded_at watermark selects new rows; merge on measurement_key
-- upserts re-measured works.

{{ config(
    materialized='incremental',
    unique_key='measurement_key',
    on_schema_change='fail'
) }}

with measurements as (

    select
        work_id,
        metric_key,
        metric_name,
        value,
        loaded_at
    from {{ ref('int_measurements_normalized') }}

    {% if is_incremental() %}
    where loaded_at > (select max(loaded_at) from {{ this }})
    {% endif %}

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
    measurements.value,
    measurements.loaded_at     -- watermark for incremental runs
from measurements
inner join works on works.work_id = measurements.work_id
