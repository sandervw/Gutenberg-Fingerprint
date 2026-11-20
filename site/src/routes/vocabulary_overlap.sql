select
    dim_author.name as author,
    fact_vocab_overlap.jaccard
from gold.fact_vocab_overlap
join gold.dim_author
    on fact_vocab_overlap.author_key_b = dim_author.author_key
order by fact_vocab_overlap.jaccard desc
limit 25
