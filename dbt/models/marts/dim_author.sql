-- One row per author: catalog primary authors off stg_works, plus manually
-- loaded authors off the seed (is_self rides the seed: 1 marks you, 0 other
-- manual authors). Both halves hash the same name dim_work hashes, so work
-- rows land on these keys.
select
    {{ dbt_utils.generate_surrogate_key(['author_name']) }} as author_key,
    author_name                                             as name,
    0                                                       as is_self
from (select distinct author_name from {{ ref('stg_works') }}) as catalog_authors

union all

select
    {{ dbt_utils.generate_surrogate_key(['author']) }},
    author,
    is_self
from (select distinct author, is_self from {{ ref('seed_authors') }}) as seed_authors
