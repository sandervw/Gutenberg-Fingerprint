select author, word, zscore
from (
    select
        author,
        word,
        zscore,
        row_number() over (partition by author order by abs(zscore) desc) as position
    from (
        select
            author,
            series_label as word,
            avg(zscore) as zscore
        from gold.mart_style_long
        where concept_name = 'function_word_frequency'
        group by author, series_label
    ) averaged
) ranked
where position <= 12
order by author, abs(zscore) desc
