with author_averages as (
    select author_key, metric_key, avg(zscore) as author_average_zscore
    from gold.mart_style_long
    where is_multivalue = false
    group by author_key, metric_key
)
select
    mart_style_long.work_id,
    mart_style_long.display_name,
    mart_style_long.zscore - author_averages.author_average_zscore as delta
from gold.mart_style_long
join author_averages
    on author_averages.author_key = mart_style_long.author_key
    and author_averages.metric_key = mart_style_long.metric_key
where mart_style_long.is_multivalue = false
order by mart_style_long.work_id, abs(mart_style_long.zscore - author_averages.author_average_zscore) desc
