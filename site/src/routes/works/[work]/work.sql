select
    work_id,
    title,
    author,
    genre,
    prose_type,
    cast(word_count as integer) as word_count,
    case when is_self = 1 then 'https://wordleaves.com/'
         else 'https://www.gutenberg.org/ebooks/' || work_id end as work_link
from gold.mart_work
