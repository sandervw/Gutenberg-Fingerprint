-- On-run-end hook: logs each executed node to dbt_run_log.
{% macro log_run_results(results) %}
    {% if execute and results | length > 0 and flags.WHICH in ('run', 'build', 'seed', 'snapshot', 'test') %}

        {% set audit_table = target.schema ~ '.dbt_run_log' %}

        {% do run_query(
            "create table if not exists " ~ audit_table ~ " ("
            ~ "invocation_id varchar, run_started_at timestamp, command varchar, "
            ~ "node varchar, resource_type varchar, status varchar, execution_time double precision)"
        ) %}

        {% set rows = [] %}
        {% for res in results %}
            {% do rows.append(
                "('" ~ invocation_id ~ "', '"
                ~ run_started_at.strftime('%Y-%m-%d %H:%M:%S') ~ "', '"
                ~ flags.WHICH ~ "', '"
                ~ res.node.name ~ "', '"
                ~ res.node.resource_type ~ "', '"
                ~ res.status ~ "', "
                ~ (res.execution_time or 0) | round(3) ~ ")"
            ) %}
        {% endfor %}
        {% do run_query("insert into " ~ audit_table ~ " values " ~ rows | join(', ')) %}

    {% endif %}
{% endmacro %}
