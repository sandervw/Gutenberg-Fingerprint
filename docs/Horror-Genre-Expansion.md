# Plan: Add Horror as a third genre

Add `Horror` as a third `genre` value alongside `Sci-Fi`/`Fantasy`, as a single exclusive column (extend the `when/otherwise` chain in `filter.py`). Do not implement multi-label boolean tags.

Re-derive all counts/regex below against the current `bronze.catalog` snapshot before shipping.

## `python/workflow/filter.py`

1. Remove `ghost stories` and `supernatural` from `FANTASY_THEME` (line ~32-35).

2. Add:

```python
HORROR_CORE: pl.Expr = SUBJECTS.str.contains("(?i)horror tales|gothic fiction") | shelf_token(
    "(Horror|Gothic Fiction)"
)
HORROR_THEME: pl.Expr = SUBJECTS.str.contains(
    r"(?i)ghost stor|paranormal fiction|haunted house|haunted place|frankenstein.s monster"
    r"|(ghosts|supernatural|occultism|demonology|vampires|werewol\w*)\s*--\s*"
    r"(fiction|juvenile fiction|poetry|drama)"
)
HORROR: pl.Expr = HORROR_CORE | HORROR_THEME
```

`HORROR_THEME` requires the `-- fiction|juvenile fiction|poetry|drama` subdivision on `ghosts`, `supernatural`, `occultism`, `demonology`, `vampires`, `werewolves`. `ghost stor`, `haunted house`, `haunted place`, `monsters --`, `frankenstein's monster`, `paranormal fiction` stay unqualified.

3. `IN_SCOPE` (line 50):

```python
IN_SCOPE: pl.Expr = (SF_CORE | FANTASY_CORE | SFF_SHELF | HORROR) & IS_ABOUT.not_()
```

4. `GENRE` (line 52-58):

```python
GENRE: pl.Expr = (
    pl.when((SF_CORE | SF_THEME) & (FANTASY_CORE | FANTASY_THEME).not_() & HORROR.not_())
    .then(pl.lit("Sci-Fi"))
    .when((FANTASY_CORE | FANTASY_THEME) & (SF_CORE | SF_THEME).not_() & HORROR.not_())
    .then(pl.lit("Fantasy"))
    .when(HORROR & (SF_CORE | SF_THEME).not_() & (FANTASY_CORE | FANTASY_THEME).not_())
    .then(pl.lit("Horror"))
    .otherwise(pl.lit("Undetermined"))
)
```

## `dbt/models/marts/_marts.yml`

`dim_work.genre` (~line 52-58): add `"Horror"` to the `accepted_values` test's `values` list. Update the `description` string.

## `dbt/models/staging/_staging.yml`

`stg_works.genre` (~line 19-22): regenerate the `description` string's counts from a live pipeline run.

## `dbt/seeds/seed_authors.csv`

Confirm `subjects = "speculative fiction"` does not match `HORROR_CORE`/`HORROR_THEME`.

## No edits required

`stg_works.sql`, `dim_work.sql`, `mart_work.sql`, `evidence/pages/works/index.md`, `evidence/pages/works/[work].md`, `evidence/pages/index.md`, `evidence/pages/authors/[author].md`.

## Validation

```python
import polars as pl

df = pl.read_csv("data/files/bronze/catalog/<latest>.csv", infer_schema_length=0)
df = df.rename({c: c.lower().replace("#", "").replace(" ", "_") for c in df.columns})
df = df.filter((pl.col("type") == "Text") & (pl.col("language") == "en"))

# ...paste SF_CORE / FANTASY_CORE / SFF_SHELF / SF_THEME / FANTASY_THEME / HORROR_CORE / HORROR_THEME here...

IN_SCOPE_OLD = SF_CORE | FANTASY_CORE | SFF_SHELF
NEW_TO_SCOPE = HORROR & IN_SCOPE_OLD.not_()

print("new works added:", df.filter(NEW_TO_SCOPE).height)

bad = ["Extraordinary Popular Delusions", "Light of Egypt"]
good = ["Legend of Sleepy Hollow", "Owl Creek Bridge", "Northanger Abbey"]
for title in bad:
    assert df.filter(pl.col("title").str.contains(title) & NEW_TO_SCOPE).height == 0
for title in good:
    assert df.filter(pl.col("title").str.contains(title) & NEW_TO_SCOPE).height == 1

leaks = df.filter(NEW_TO_SCOPE)["subjects"].str.contains("(?i)criticism|early works to")
assert leaks.sum() == 0
```

Run a full pipeline pass and check `filter.py`'s `by_genre` printout shows all four values.

## Out of scope

- Multi-label genre tags.
- Sub-genres finer than Horror.
- Backfilling already-ingested works: `raw.raw_works` overwrites from `bronze.catalog` every run.
