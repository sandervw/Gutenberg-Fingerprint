select
    cast(cast(max(ingested_at) as date) as varchar) as refreshed,
    cast(count(work_id) as integer) as work_count
from gold.mart_work
