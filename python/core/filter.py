# Filter helper: catalog rows -> in-scope, deduped raw_works.

from __future__ import annotations

from dataclasses import dataclass

import polars

# %% Scope + genre - checks both subjects (LCSH) and bookshelves

SUBJECTS: polars.Expr = polars.col("subjects").fill_null("")
SHELVES: polars.Expr = polars.col("bookshelves").fill_null("")


def shelf_token(pattern: str) -> polars.Expr:
    """Whole-shelf match; the column is a '; '-joined list."""
    return SHELVES.str.contains(rf"(^|; ){pattern}($|;)")


SCIFI_CORE: polars.Expr = SUBJECTS.str.contains("(?i)science fiction") | shelf_token(
    "(Science Fiction|Science Fiction by Women|Precursors of Science Fiction)"
)
FANTASY_CORE: polars.Expr = SUBJECTS.str.contains("(?i)fantas") | shelf_token("Fantasy")
SCIFI_FANTASY_SHELF: polars.Expr = shelf_token("Category: Science-Fiction & Fantasy")

SCIFI_THEME: polars.Expr = SUBJECTS.str.contains(
    "(?i)interplanetary|space flight|time travel|robot|extraterrestrial|outer space"
    "|life on other planets|end of the world|utopia|dystopia"
)
FANTASY_THEME: polars.Expr = SUBJECTS.str.contains(
    "(?i)fairy tal|fairies|magic|mythology|folklore|dragons|witch|wizard"
    "|imaginary places|legends"
)

HORROR_CORE: polars.Expr = SUBJECTS.str.contains("(?i)horror tales|gothic fiction") | shelf_token(
    "(Horror|Gothic Fiction)"
)
# Ghosts/vampires etc need a fiction subdivision; the rest stand alone
HORROR_THEME: polars.Expr = SUBJECTS.str.contains(
    r"(?i)ghost stor|paranormal fiction|haunted house|haunted place|frankenstein.s monster"
    r"|(ghosts|supernatural|occultism|demonology|vampires|werewol\w*)\s*--\s*"
    r"(fiction|juvenile fiction|poetry|drama)"
)
HORROR: polars.Expr = HORROR_CORE | HORROR_THEME

ABOUT_SUBDIVISION: str = (
    r"(?i)--\s*(history and criticism|authorship|criticism|bibliograph"
    r"|study and teaching|biography|congresses|dictionaries|indexes)"
)
IS_ABOUT: polars.Expr = (
    SUBJECTS.str.split("; ")
    .list.eval(
        polars.element().str.contains(ABOUT_SUBDIVISION)
        & polars.element().str.contains(r"(?i)--\s*fiction").not_()
    )
    .list.any()
)

IN_SCOPE: polars.Expr = (SCIFI_CORE | FANTASY_CORE | SCIFI_FANTASY_SHELF | HORROR) & IS_ABOUT.not_()

GENRE: polars.Expr = (
    polars.when((SCIFI_CORE | SCIFI_THEME) & (FANTASY_CORE | FANTASY_THEME).not_() & HORROR.not_())
    .then(polars.lit("Sci-Fi"))
    .when((FANTASY_CORE | FANTASY_THEME) & (SCIFI_CORE | SCIFI_THEME).not_() & HORROR.not_())
    .then(polars.lit("Fantasy"))
    .when(HORROR & (SCIFI_CORE | SCIFI_THEME).not_() & (FANTASY_CORE | FANTASY_THEME).not_())
    .then(polars.lit("Horror"))
    .otherwise(polars.lit("Undetermined"))
)

# %% Dedup - same title and primary author is one work

DEDUP_TITLE: polars.Expr = polars.col("title").fill_null("").str.strip_chars().str.to_lowercase()
DEDUP_AUTHOR: polars.Expr = (
    polars.col("authors").fill_null("").str.split(";").list.first().str.strip_chars().str.to_lowercase()
)

# %% Pure entry point


@dataclass(frozen=True)
class FilterResult:
    """In-scope deduped works and the count of dropped re-releases."""

    raw_works: polars.DataFrame
    deduped: int


def filter_catalog(catalog: polars.DataFrame) -> FilterResult:
    """Keep in-scope English texts, tag genre, drop re-releases."""
    scoped = catalog.filter(
        (polars.col("type") == "Text") & (polars.col("language") == "en") & IN_SCOPE
    ).with_columns(GENRE.alias("genre"))
    raw_works = (
        scoped.with_columns(DEDUP_TITLE.alias("_k_title"), DEDUP_AUTHOR.alias("_k_author"))
        .sort("gutenberg_id")
        .unique(subset=["_k_title", "_k_author"], keep="first", maintain_order=True)
        .drop("_k_title", "_k_author")
    )
    return FilterResult(raw_works=raw_works, deduped=scoped.height - raw_works.height)


# %% Copyrighted donations - PG header sits above the START marker

COPYRIGHT_MARKER: bytes = b"copyrighted project gutenberg ebook"
COPYRIGHT_SCAN_BYTES: int = 2048  # marker lands by byte ~576


def is_copyrighted(raw_bytes: bytes) -> bool:
    """True when PG's copyrighted-donation header is present."""
    return COPYRIGHT_MARKER in raw_bytes[:COPYRIGHT_SCAN_BYTES].lower()
