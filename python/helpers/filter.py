# Filter helper: catalog rows -> in-scope, deduped raw_works.

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

# %% Scope + genre - checks both subjects (LCSH) and bookshelves

SUBJECTS: pl.Expr = pl.col("subjects").fill_null("")
SHELVES: pl.Expr = pl.col("bookshelves").fill_null("")


def shelf_token(pattern: str) -> pl.Expr:
    """Whole-shelf match; the column is a '; '-joined list."""
    return SHELVES.str.contains(rf"(^|; ){pattern}($|;)")


SF_CORE: pl.Expr = SUBJECTS.str.contains("(?i)science fiction") | shelf_token(
    "(Science Fiction|Science Fiction by Women|Precursors of Science Fiction)"
)
FANTASY_CORE: pl.Expr = SUBJECTS.str.contains("(?i)fantas") | shelf_token("Fantasy")
SFF_SHELF: pl.Expr = shelf_token("Category: Science-Fiction & Fantasy")

SF_THEME: pl.Expr = SUBJECTS.str.contains(
    "(?i)interplanetary|space flight|time travel|robot|extraterrestrial|outer space"
    "|life on other planets|end of the world|utopia|dystopia"
)
FANTASY_THEME: pl.Expr = SUBJECTS.str.contains(
    "(?i)fairy tal|fairies|magic|mythology|folklore|dragons|witch|wizard"
    "|imaginary places|legends"
)

HORROR_CORE: pl.Expr = SUBJECTS.str.contains("(?i)horror tales|gothic fiction") | shelf_token(
    "(Horror|Gothic Fiction)"
)
# Ghosts/vampires etc need a fiction subdivision; the rest stand alone
HORROR_THEME: pl.Expr = SUBJECTS.str.contains(
    r"(?i)ghost stor|paranormal fiction|haunted house|haunted place|frankenstein.s monster"
    r"|(ghosts|supernatural|occultism|demonology|vampires|werewol\w*)\s*--\s*"
    r"(fiction|juvenile fiction|poetry|drama)"
)
HORROR: pl.Expr = HORROR_CORE | HORROR_THEME

ABOUT_SUBDIVISION: str = (
    r"(?i)--\s*(history and criticism|authorship|criticism|bibliograph"
    r"|study and teaching|biography|congresses|dictionaries|indexes)"
)
IS_ABOUT: pl.Expr = (
    SUBJECTS.str.split("; ")
    .list.eval(
        pl.element().str.contains(ABOUT_SUBDIVISION)
        & pl.element().str.contains(r"(?i)--\s*fiction").not_()
    )
    .list.any()
)

IN_SCOPE: pl.Expr = (SF_CORE | FANTASY_CORE | SFF_SHELF | HORROR) & IS_ABOUT.not_()

GENRE: pl.Expr = (
    pl.when((SF_CORE | SF_THEME) & (FANTASY_CORE | FANTASY_THEME).not_() & HORROR.not_())
    .then(pl.lit("Sci-Fi"))
    .when((FANTASY_CORE | FANTASY_THEME) & (SF_CORE | SF_THEME).not_() & HORROR.not_())
    .then(pl.lit("Fantasy"))
    .when(HORROR & (SF_CORE | SF_THEME).not_() & (FANTASY_CORE | FANTASY_THEME).not_())
    .then(pl.lit("Horror"))
    .otherwise(pl.lit("Undetermined"))
)

# %% Dedup - same title + primary author = one work, many PG ids

DEDUP_TITLE: pl.Expr = pl.col("title").fill_null("").str.strip_chars().str.to_lowercase()
DEDUP_AUTHOR: pl.Expr = (
    pl.col("authors").fill_null("").str.split(";").list.first().str.strip_chars().str.to_lowercase()
)

# %% Pure entry point


@dataclass(frozen=True)
class FilterResult:
    raw_works: pl.DataFrame
    deduped: int  # re-release rows dropped


def filter_catalog(catalog_df: pl.DataFrame) -> FilterResult:
    scoped = catalog_df.filter(
        (pl.col("type") == "Text") & (pl.col("language") == "en") & IN_SCOPE
    ).with_columns(GENRE.alias("genre"))
    raw_works = (
        scoped.with_columns(DEDUP_TITLE.alias("_k_title"), DEDUP_AUTHOR.alias("_k_author"))
        .sort("gutenberg_id")
        .unique(subset=["_k_title", "_k_author"], keep="first", maintain_order=True)
        .drop("_k_title", "_k_author")
    )
    return FilterResult(raw_works=raw_works, deduped=scoped.height - raw_works.height)
