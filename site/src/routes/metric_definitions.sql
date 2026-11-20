select
    dim_metric.display_name,
    dim_metric.description
from gold.dim_metric
where dim_metric.is_multivalue = false
    and dim_metric.metric_name <> 'jaccard'
order by dim_metric.display_name
