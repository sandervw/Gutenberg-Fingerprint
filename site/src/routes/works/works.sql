select
    work_id,
    title,
    author,
    genre,
    cast(word_count as integer) as word_count,
    cast(is_juvenile as integer) as is_juvenile,
    cast(is_play as integer) as is_play,
    cast(is_poetry as integer) as is_poetry,
    cast(is_translation as integer) as is_translation
from gold.mart_work
order by word_count desc nulls last, work_id
