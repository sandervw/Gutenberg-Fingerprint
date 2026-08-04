-- Z-score: how many stddevs a value sits from its metric's average.
{% macro zscore(value_col, partition_col) %}
  ({{ value_col }} - avg({{ value_col }}) over (partition by {{ partition_col }}))
  / nullif({{ stddev_pop_expr(value_col) }} over (partition by {{ partition_col }}), 0)
{% endmacro %}


-- Population stddev via adapter dispatch (DuckDB: stddev_pop).
{% macro stddev_pop_expr(col) %}
  {{ return(adapter.dispatch('stddev_pop_expr', 'gutenberg_fingerprint')(col)) }}
{% endmacro %}

{% macro default__stddev_pop_expr(col) %}stddev_pop({{ col }}){% endmacro %}
