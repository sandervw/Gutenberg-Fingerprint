-- Birth/death years off the primary author's trailing date segment.

{% macro _first_author_dated(column) %}
  regexp_replace(regexp_replace({{ column }}, ';.*$', ''), '\[[^\]]*\]', '', 'g')
{% endmacro %}


{% macro author_birth_year(column) %}
  {{ return(adapter.dispatch('author_birth_year', 'gutenberg_fingerprint')(column)) }}
{% endmacro %}

{% macro default__author_birth_year(column) %}
  cast(substring({{ _first_author_dated(column) }} from ',\s*([0-9]{3,4})\??\s*-') as {{ dbt.type_int() }})
{% endmacro %}

{% macro duckdb__author_birth_year(column) %}
  cast(nullif(regexp_extract({{ _first_author_dated(column) }}, ',\s*([0-9]{3,4})\??\s*-', 1), '') as {{ dbt.type_int() }})
{% endmacro %}


{% macro author_death_year(column) %}
  {{ return(adapter.dispatch('author_death_year', 'gutenberg_fingerprint')(column)) }}
{% endmacro %}

{% macro default__author_death_year(column) %}
  cast(substring({{ _first_author_dated(column) }} from '-\s*([0-9]{3,4})\??\s*$') as {{ dbt.type_int() }})
{% endmacro %}

{% macro duckdb__author_death_year(column) %}
  cast(nullif(regexp_extract({{ _first_author_dated(column) }}, '-\s*([0-9]{3,4})\??\s*$', 1), '') as {{ dbt.type_int() }})
{% endmacro %}
