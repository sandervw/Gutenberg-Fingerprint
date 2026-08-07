-- Calendar dimension for loaded_date FKs. Daily grain, 1970-2035.

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
