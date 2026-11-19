with author_avg as (
    select author_key, metric_key, avg(zscore) as author_z
    from gold.mart_style_long
    where is_multivalue = false
    group by author_key, metric_key
)
select
    msl.work_id,
    msl.display_name,
    msl.zscore - a.author_z as delta
from gold.mart_style_long msl
join author_avg a
    on a.author_key = msl.author_key
    and a.metric_key = msl.metric_key
where msl.is_multivalue = false
order by msl.work_id, abs(msl.zscore - a.author_z) desc
