select
    work_id,
    title,
    author,
    genre,
    cast(word_count as integer) as word_count,
    excess
from gold.mart_work
where is_play = 0
    and is_translation = 0
    and is_juvenile = 0
    and is_poetry = 0
    and prose_type <> 'short-story'
order by excess desc
limit 25
