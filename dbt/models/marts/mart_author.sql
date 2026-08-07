-- One row per author holding measured works: corpus rollups.

select
    mw.author_key,
    mw.author,
    mw.is_self,
    da.birth_date,
    da.death_date,
    count(*)              as works,
    sum(mw.word_count)    as total_words
from {{ ref('mart_work') }} mw
inner join {{ ref('dim_author') }} da on da.author_key = mw.author_key
group by mw.author_key, mw.author, mw.is_self, da.birth_date, da.death_date
