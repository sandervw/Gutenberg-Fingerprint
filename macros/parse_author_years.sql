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


-- T-SQL: segment after the first author's last comma, e.g. "1490?-1553?".
{% macro _fabric_date_segment(column) %}
  {%- set el = "case when charindex(';', " ~ column ~ ") > 0 then left(" ~ column ~ ", charindex(';', " ~ column ~ ") - 1) else " ~ column ~ " end" -%}
  {%- set name = "trim(case when charindex('[', " ~ el ~ ") > 0 then left(" ~ el ~ ", charindex('[', " ~ el ~ ") - 1) else " ~ el ~ " end)" -%}
  replace(trim(case when charindex(',', {{ name }}) > 0 then right({{ name }}, charindex(',', reverse({{ name }})) - 1) end), '?', '')
{% endmacro %}

{% macro fabric__author_birth_year(column) %}
  {%- set seg = _fabric_date_segment(column) -%}
  case when charindex('-', {{ seg }}) > 1 then try_cast(nullif(trim(left({{ seg }}, charindex('-', {{ seg }}) - 1)), '') as int) end
{% endmacro %}

-- nullif: T-SQL try_cast('' as int) yields 0, not null.
{% macro fabric__author_death_year(column) %}
  {%- set seg = _fabric_date_segment(column) -%}
  case when charindex('-', {{ seg }}) > 0 then try_cast(nullif(trim(substring({{ seg }}, charindex('-', {{ seg }}) + 1, 10)), '') as int) end
{% endmacro %}


-- Jan 1 of a year; T-SQL spells make_date as datefromparts.
{% macro jan_first(year_col) %}
  {{ return(adapter.dispatch('jan_first', 'gutenberg_fingerprint')(year_col)) }}
{% endmacro %}

{% macro default__jan_first(year_col) %}make_date({{ year_col }}, 1, 1){% endmacro %}

{% macro fabric__jan_first(year_col) %}datefromparts({{ year_col }}, 1, 1){% endmacro %}
