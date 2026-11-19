select
    author,
    cast(works as integer) as works,
    cast(total_words as integer) as total_words
from gold.mart_author
