select
    work_id,
    display_name,
    zscore
from gold.mart_style_long
where is_multivalue = false
order by work_id, abs(zscore) desc
