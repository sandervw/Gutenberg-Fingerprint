select
    author,
    series_label as mark,
    avg(zscore) as zscore
from gold.mart_style_long
where concept_name = 'punctuation_frequency'
group by author, series_label
order by author, zscore desc
