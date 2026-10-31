-- Calendar dimension for loaded_date FKs. Daily grain, 1970-2035.

{% if target.type == 'fabric' %}

-- T-SQL forbids date_spine's nested CTEs; digits cross join instead.
with digits as (
    select n from (values (0), (1), (2), (3), (4), (5), (6), (7), (8), (9)) as d (n)
),

spine as (
    select dateadd(day, a.n + b.n * 10 + c.n * 100 + d.n * 1000 + e.n * 10000, cast('1970-01-01' as date)) as date_day
    from digits a cross join digits b cross join digits c cross join digits d cross join digits e
    where a.n + b.n * 10 + c.n * 100 + d.n * 1000 + e.n * 10000
        < datediff(day, cast('1970-01-01' as date), cast('2036-01-01' as date))
)

select
    {{ dbt_utils.generate_surrogate_key(['cast(date_day as date)']) }} as date_key,
    cast(date_day as date)                         as date_day,
    datepart(year, date_day)                       as year,
    datepart(quarter, date_day)                    as quarter,
    datepart(month, date_day)                      as month,
    datepart(day, date_day)                        as day_of_month,
    -- 1970-01-04 was a Sunday: Sunday = 0, DATEFIRST-proof.
    datediff(day, cast('1970-01-04' as date), date_day) % 7 as day_of_week,
    case when datediff(day, cast('1970-01-04' as date), date_day) % 7 in (0, 6) then 1 else 0 end as is_weekend
from spine

{% else %}

with spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1970-01-01' as date)",
        end_date="cast('2036-01-01' as date)"
    ) }}

)

select
    {{ dbt_utils.generate_surrogate_key(['cast(date_day as date)']) }} as date_key,
    cast(date_day as date)                                         as date_day,
    cast(extract(year    from date_day) as {{ dbt.type_int() }})   as year,
    cast(extract(quarter from date_day) as {{ dbt.type_int() }})   as quarter,
    cast(extract(month   from date_day) as {{ dbt.type_int() }})   as month,
    cast(extract(day     from date_day) as {{ dbt.type_int() }})   as day_of_month,
    cast(extract(dow     from date_day) as {{ dbt.type_int() }})   as day_of_week,
    case when extract(dow from date_day) in (0, 6) then 1 else 0 end as is_weekend
from spine

{% endif %}
