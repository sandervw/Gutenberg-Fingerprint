-- One row per author: catalog primary authors off stg_works, plus manually
-- loaded authors off the seed (is_self rides the seed: 1 marks you, 0 other
-- manual authors). Both halves hash the same name dim_work hashes, so work
-- rows land on these keys.
-- Years are fabricated to Jan 1; source carries year only.
select
    {{ dbt_utils.generate_surrogate_key(['author_name']) }} as author_key,
    author_name                                             as name,
    case when birth_year is not null then make_date(birth_year, 1, 1) end as birth_date,
    case when death_year is not null then make_date(death_year, 1, 1) end as death_date,
    0                                                       as is_self
from (
    select
        author_name,
        max(birth_year) as birth_year,
        max(death_year) as death_year
    from {{ ref('stg_works') }}
    group by author_name
) as catalog_authors

union all

select
    {{ dbt_utils.generate_surrogate_key(['author']) }},
    author,
    cast(null as date),
    cast(null as date),
    is_self
from (select distinct author, is_self from {{ ref('seed_authors') }}) as seed_authors
