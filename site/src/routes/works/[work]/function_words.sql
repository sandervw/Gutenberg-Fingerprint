select work_id, word, zscore
from (
    select
        work_id,
        series_label as word,
        zscore,
        row_number() over (partition by work_id order by abs(zscore) desc) as position
    from gold.mart_style_long
    where concept_name = 'function_word_frequency'
) ranked
where position <= 12
order by work_id, abs(zscore) desc
