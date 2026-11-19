select
    author as name,
    cast(works as integer) as works,
    cast(total_words as integer) as words
from gold.mart_author
order by works desc, author
