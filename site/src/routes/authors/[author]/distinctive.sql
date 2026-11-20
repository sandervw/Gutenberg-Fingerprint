select
    author,
    display_name,
    avg(zscore) as zscore
from gold.mart_style_long
where is_multivalue = false
group by author, display_name
order by author, abs(avg(zscore)) desc
