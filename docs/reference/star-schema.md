# Star schema reference

## dbt layers

| Layer | Naming | Materialization | Contents |
|---|---|---|---|
| staging | `stg_*` | view | 1:1 with sources; cast, rename |
| intermediate | `int_*` | ephemeral | joins prepping marts |
| marts | `dim_*`, `fct_*`/`fact_*` | table | the star; surrogate keys, tests |

## Keys

- Join fact to dimension on surrogate key, never natural key.
- Surrogate keys built with `dbt_utils.generate_surrogate_key([...])` over the natural-key columns.
- Natural key (`work_id`) stays in the dimension as an attribute.
- Test surrogate keys `unique` + `not_null`; fact FKs get `relationships`.
- Degenerate dimensions stay in the fact as a bare key.

## Grain

- Declare grain before dimensions and facts. Every dim key and measure must fit it.
- One grain per fact table, atomic where possible.
- Each dimension gets its own FK in the fact.
- Dimensions flat and denormalized.

## Additivity

| Class | Summable across | Examples |
|---|---|---|
| Additive | all dimensions | counts, amounts |
| Semi-additive | all but time | balances, headcount |
| Non-additive | nothing | ratios, percentages, averages, z-scores, Jaccard/similarity |

- Non-additive measures are never summed. Store additive numerator and denominator; compute ratio at query time.
- Semi-additive across time: period-ending value or average.
- Flag non-additive columns in docs.

## SCD

- Type 2 dimensions carry surrogate key plus `valid_from`, `valid_to`, `is_current`.
- Type 1 overwrites, no history.
- Rapidly-changing attributes belong in a fact.

## Red flags

- [ ] Undeclared or mixed grain.
- [ ] Dimension reachable only through another dimension; snowflaking.
- [ ] Fact joining on raw natural keys; dimension without surrogate key.
- [ ] Non-additive measure unflagged, or ratio stored instead of numerator/denominator.
- [ ] Semi-additive balance summed across time.
- [ ] Descriptive text or high-cardinality attributes in a fact.
- [ ] Table acting as both fact and dimension.
- [ ] Many-to-many fanned out in a fact instead of a bridge or factless fact.
- [ ] Conformed dimension duplicated with diverging keys across facts.
- [ ] Missing `unique`/`not_null` on surrogate keys, or `relationships` on fact FKs.
