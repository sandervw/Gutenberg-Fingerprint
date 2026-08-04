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
