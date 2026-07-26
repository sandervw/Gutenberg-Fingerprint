-- One row per author holding measured works: corpus rollups.

select
    author_key,
    author,
    is_self,
    count(*)         as works,
    sum(word_count)  as total_words
from {{ ref('mart_work') }}
group by author_key, author, is_self
