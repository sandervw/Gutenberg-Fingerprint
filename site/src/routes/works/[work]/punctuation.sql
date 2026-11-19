select
    work_id,
    series_label as mark,
    zscore
from gold.mart_style_long
where concept_name = 'punctuation_frequency'
order by work_id, zscore desc
