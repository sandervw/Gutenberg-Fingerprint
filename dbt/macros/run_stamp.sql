-- Run-constant timestamp; avoids current_timestamp() adapter differences.
-- Guard: run_started_at is unset during parsing.
{% macro run_stamp() %}
    {%- if execute and run_started_at -%}
        cast('{{ run_started_at.strftime('%Y-%m-%d %H:%M:%S') }}' as {{ dbt.type_timestamp() }})
    {%- else -%}
        cast(null as {{ dbt.type_timestamp() }})
    {%- endif -%}
{% endmacro %}
