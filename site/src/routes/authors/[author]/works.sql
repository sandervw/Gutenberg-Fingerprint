select
    author,
    work_id,
    title,
    prose_type,
    genre,
    cast(word_count as integer) as word_count
from gold.mart_work
order by author, word_count desc
