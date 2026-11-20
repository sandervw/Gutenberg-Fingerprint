select
    work_id,
    series_label as sentence_type,
    value as proportion
from gold.mart_style_long
where concept_name = 'sentence_type_mix'
order by work_id, proportion desc
