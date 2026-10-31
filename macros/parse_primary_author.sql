-- Primary author from the raw catalog authors string.
{% macro parse_primary_author(column) %}
  {{ return(adapter.dispatch('parse_primary_author', 'gutenberg_fingerprint')(column)) }}
{% endmacro %}


-- Strips role tags and the trailing date segment from the first author.
{% macro default__parse_primary_author(column) %}
  trim(
    regexp_replace(
      regexp_replace(
        regexp_replace({{ column }}, ';.*$', ''),
        '\[[^\]]*\]', '', 'g'),
      ',[^,]*[0-9][^,]*$', '')
  )
{% endmacro %}


-- T-SQL has no regex: cut at the last comma before a digit.
{% macro fabric__parse_primary_author(column) %}
  {%- set el = "case when charindex(';', " ~ column ~ ") > 0 then left(" ~ column ~ ", charindex(';', " ~ column ~ ") - 1) else " ~ column ~ " end" -%}
  {%- set name = "case when charindex('[', " ~ el ~ ") > 0 then left(" ~ el ~ ", charindex('[', " ~ el ~ ") - 1) else " ~ el ~ " end" -%}
  trim(
    case
      when patindex('%[0-9]%', {{ name }}) = 0
        then {{ name }}
      when charindex(',', reverse(left({{ name }}, patindex('%[0-9]%', {{ name }}) - 1))) = 0
        then {{ name }}
      else left(
        {{ name }},
        patindex('%[0-9]%', {{ name }})
          - charindex(',', reverse(left({{ name }}, patindex('%[0-9]%', {{ name }}) - 1)))
          - 1
      )
    end
  )
{% endmacro %}
