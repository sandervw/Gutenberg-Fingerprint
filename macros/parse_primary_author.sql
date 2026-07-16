-- Primary author name off the raw catalog authors string, e.g.
--   "Rabelais, François, 1490?-1553?; Doré, Gustave, 1832-1883 [Illustrator]"
-- Rule: first '; ' element, minus any [Role] tag, cut at the last comma before
-- the first digit — drops "1892-1973", "-1471", "1925-", "active 12th century"
-- alike, and leaves date-less names ("Erckmann-Chatrian", "Various") whole.
-- Dispatched per engine: no portable find-first-digit exists (DuckDB regex,
-- T-SQL PATINDEX).
{% macro parse_primary_author(column) %}
  {{ return(adapter.dispatch('parse_primary_author', 'gutenberg_fingerprint')(column)) }}
{% endmacro %}


{% macro default__parse_primary_author(column) %}
  trim(
    regexp_replace(
      regexp_replace(
        regexp_replace({{ column }}, ';.*$', ''),  -- first author element
        '\[[^\]]*\]', '', 'g'),                    -- drop [Role] tags
      ',[^,]*[0-9][^,]*$', '')                     -- drop the trailing date segment
  )
{% endmacro %}


{% macro fabric__parse_primary_author(column) %}
  {#- el: first author element; name: el minus any [Role] tag -#}
  {%- set el = "case when charindex(';', " ~ column ~ ") > 0 then left(" ~ column ~ ", charindex(';', " ~ column ~ ") - 1) else " ~ column ~ " end" -%}
  {%- set name = "case when charindex('[', " ~ el ~ ") > 0 then left(" ~ el ~ ", charindex('[', " ~ el ~ ") - 1) else " ~ el ~ " end" -%}
  trim(
    case
      when patindex('%[0-9]%', {{ name }}) = 0
        then {{ name }}  -- no date to strip
      when charindex(',', reverse(left({{ name }}, patindex('%[0-9]%', {{ name }}) - 1))) = 0
        then {{ name }}  -- digit but no comma before it: leave whole
      else left(
        {{ name }},
        patindex('%[0-9]%', {{ name }})
          - charindex(',', reverse(left({{ name }}, patindex('%[0-9]%', {{ name }}) - 1)))
          - 1
      )
    end
  )
{% endmacro %}
