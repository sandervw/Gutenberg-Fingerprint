-- One row per author: catalog primary authors off stg_works, plus the self row
-- off the seed. Both halves hash the same name dim_work hashes, so work rows
-- land on these keys.
select
    {{ dbt_utils.generate_surrogate_key(['author_name']) }} as author_key,
    author_name                                             as name,
    0                                                       as is_self
from (select distinct author_name from {{ ref('stg_works') }}) as catalog_authors

union all

select
    {{ dbt_utils.generate_surrogate_key(['author']) }},
    author,
    1
from (select distinct author from {{ ref('seed_authors') }}) as self_authors
