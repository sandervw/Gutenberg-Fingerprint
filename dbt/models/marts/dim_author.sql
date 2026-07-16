-- One row per author: catalog primary authors off stg_works, plus the self row
-- off the seed (tradition/era/is_self only exist there). Both halves hash the
-- same name dim_work hashes, so work rows land on these keys.
select
    {{ dbt_utils.generate_surrogate_key(['author_name']) }} as author_key,
    author_name                                             as name,
    cast(null as {{ dbt.type_string() }})                   as tradition,
    cast(null as {{ dbt.type_string() }})                   as era,
    0                                                       as is_self
from (select distinct author_name from {{ ref('stg_works') }}) as catalog_authors

union all

select
    {{ dbt_utils.generate_surrogate_key(['author']) }},
    author,
    tradition,
    era,
    1
from {{ ref('seed_authors') }}
group by author, tradition, era
