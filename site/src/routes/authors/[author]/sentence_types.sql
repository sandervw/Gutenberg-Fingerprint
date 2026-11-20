select
    author,
    series_label as sentence_type,
    avg(value) as proportion
from gold.mart_style_long
where concept_name = 'sentence_type_mix'
group by author, series_label
order by author, proportion desc
