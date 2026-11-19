select
    da.name as author,
    fvo.jaccard
from gold.fact_vocab_overlap fvo
join gold.dim_author da
    on fvo.author_key_b = da.author_key
order by fvo.jaccard desc
limit 25
