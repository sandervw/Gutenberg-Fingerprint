-- on-run-end audit hook: one row per executed node into <target.schema>.dbt_run_log.
-- flags.WHICH guard keeps compile/docs-generate from logging phantom rows.
{% macro log_run_results(results) %}
    {% if execute and results | length > 0 and flags.WHICH in ('run', 'build', 'seed', 'snapshot', 'test') %}

        {% set audit_table = target.schema ~ '.dbt_run_log' %}

        {# Fabric's T-SQL has no CREATE TABLE IF NOT EXISTS #}
        {% if target.type == 'fabric' %}
            {% do run_query(
                "if object_id('" ~ audit_table ~ "') is null "
                ~ "create table " ~ audit_table ~ " ("
                ~ "invocation_id varchar(64), run_started_at datetime2(6), command varchar(20), "
                ~ "node varchar(300), resource_type varchar(20), status varchar(20), execution_time float)"
            ) %}
        {% else %}
            {% do run_query(
                "create table if not exists " ~ audit_table ~ " ("
                ~ "invocation_id varchar, run_started_at timestamp, command varchar, "
                ~ "node varchar, resource_type varchar, status varchar, execution_time double)"
            ) %}
        {% endif %}

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
