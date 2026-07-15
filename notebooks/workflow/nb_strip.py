# Fabric notebook: nb_strip
# Bronze Files/texts/<id>.txt -> silver Files/corpus/<Author>/<id>-<slug>.md:
# strips PG boilerplate, unwraps paragraphs, emits corpus-style markdown.
# Pure text functions sit above the run cell so scripts/strip_sample.py can import them.

from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
SILVER_LAKEHOUSE: str = f"{ONELAKE}/lh_silver.Lakehouse"
RAW_WORKS_TABLE: str = f"{SILVER_LAKEHOUSE}/Tables/dbo/raw_works"
STRIP_AUDIT_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/strip_audit"

TEXTS_ROOT: Path = Path("/lakehouse/default/Files/texts")  # default lakehouse = lh_bronze
CORPUS_SUBDIR: str = "Files/corpus"

# %% Boilerplate span - modern *** markers, pre-2002 fallbacks

_START = re.compile(r"^\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*$", re.M)
_END = re.compile(r"^\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*$", re.M)
_OLD_START = re.compile(r"^\*END\*THE SMALL PRINT![^\n]*$", re.M)
_OLD_END = re.compile(r"^End of (?:the |this )?Project Gutenberg", re.M | re.I)

def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")

def isolate_body(text: str) -> str:
    """Cut at the EARLIEST end marker of either era: regenerated old files keep
    their ancient 'End of...' line inside the modern *** span."""
    start = _START.search(text) or _OLD_START.search(text)
    if start is None:
        raise ValueError("no start marker")
    body = text[start.end() :]
    ends = [m.start() for m in (_END.search(body), _OLD_END.search(body)) if m]
    if not ends:
        raise ValueError("no end marker")
    return body[: min(ends)]

# %% Dirt - transcriber leavings, contents lists, front-matter repeats

_BRACKET_NOTE = re.compile(r"\[(?:Illustration|Transcriber)[^\]]*\]", re.I | re.S)
_ETEXT_LINE = re.compile(r"(?im)^.*\[e-?text #\d+\].*$\n?")
_CONTENTS = re.compile(
    r"(?i)^(?:table of )?contents\.?$|^list of (?:chapters|illustrations|plates|figures)\.?$"
    r"|^illustrations\.?$"
)
_CREDIT = re.compile(
    r"(?i)^(?:produced by|(?:this )?e-?text (?:was )?prepared by|prepared by"
    r"|transcribed|scanned by|proofread|credits?:)"
)
_FRONT_CUES = re.compile(
    r"(?i)^(?:by\b[^\n]{0,40}|illustrated by\b[^\n]*|with illustrations\b[^\n]*"
    r"|copyright\b[^\n]*|all rights reserved[^\n]*|\[?\d{4}\]?|\([^)\n]*\)"
    r"|(?:a |an )?(?:romance|novel|tale|fantasy|story|poem)s?|[^\n]{0,30}\d{4})$"
)
_FRONT_STRONG = re.compile(
    r"(?i)^(?:translated (?:from|by)|illustrated by|with illustrations|copyright"
    r"|all rights reserved|printed in)|(?:& co(?:mpany)?\.?|publishers?|press|avenue|street)\W*$"
)
_PG_MENTION = re.compile(r"(?i)project gutenberg|\be-?texts?\b")
_BRACKET_BLOCK = re.compile(r"^\[[^\]]*\]$", re.S)
_DEDICATION = re.compile(r"(?i)\bdedicat")
_TAIL = re.compile(r"(?i)^[*_\s]*(?:the\s+)?end[.!]?[*_\s]*$|^finis\.?$")

def split_blocks(text: str) -> list[str]:
    return [b.strip("\n") for b in re.split(r"\n[ \t]*\n", text) if b.strip()]

def drop_contents(blocks: list[str]) -> list[str]:
    out: list[str] = []
    skipping = False
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if _CONTENTS.match(lines[0].strip()):
            skipping = True
            continue
        if skipping and len(lines) >= 3 and all(len(line) <= 65 for line in lines):
            continue
        skipping = False
        out.append(block)
    return out

def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def drop_front_matter(blocks: list[str], title: str, author: str) -> list[str]:
    main_title = _squash(re.split(r"[:;\n\r]", title)[0])
    names = [n for n in (_squash(p) for p in author.split(";")) if len(n) >= 4 and n != "unknown"]
    out: list[str] = []
    for i, block in enumerate(blocks):
        if i < 8:
            stripped = block.strip()
            lines = [line.strip(" \t_*") for line in stripped.splitlines() if line.strip()]
            sq = _squash(block)
            line_dirt = len(lines) <= 3 and (
                ((len(sq) >= 4 or sq == main_title) and sq in _squash(title))
                or (len(main_title) >= 4 and main_title in sq)
                or any(n in sq for n in names)
                or all(_FRONT_CUES.match(line) for line in lines)
                or any(_FRONT_STRONG.search(line) for line in lines)
                or bool(_CREDIT.match(lines[0]))
            )
            if (
                _PG_MENTION.search(block)
                or _BRACKET_BLOCK.match(stripped)
                or (len(block) <= 300 and (_DEDICATION.search(block) or line_dirt))
            ):
                continue
        out.append(block)
    return out

# %% Structure - chapter headings, paragraph unwrap

_ROMAN = r"[IVXLCDM]{1,8}"
_HEAD_KW = re.compile(r"(?i)^(?:chapter|book|part|volume|canto|stave|section)\b[^\n]{0,50}$")
_HEAD_WORD = re.compile(
    r"(?i)^(?:prologue|epilogue|introduction|induction|preface|foreword"
    r"|conclusion|appendix|interlude|dedication|author'?s note)\b[^\n]{0,40}$"
)
_HEAD_NUM = re.compile(
    rf"^(?:{_ROMAN}|\d{{1,3}})(?:\.?$|[.:][ \t]+[\"']?[A-Z][^\n]{{0,50}}(?<![.!?,])$)"
)

def _caps_line(line: str) -> bool:
    return (
        line == line.upper()
        and 3 <= len(line) <= 60
        and sum(c.isalpha() for c in line) >= 3
        and not line.endswith((".", "!", "?"))
    )

def is_heading(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 2 or any(len(line) > 60 for line in lines):
        return False
    first = lines[0]
    return bool(
        _HEAD_KW.match(first) or _HEAD_WORD.match(first)
        or _HEAD_NUM.match(first) or _caps_line(first)
    )

def unwrap(block: str) -> str:
    # Indented continuation means verse: keep its shape
    lines = block.splitlines()
    if any(line[:1] in (" ", "\t") for line in lines[1:]):
        return "\n".join(line.rstrip() for line in lines)
    return " ".join(line.strip() for line in lines)

def render_blocks(blocks: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if not is_heading(block):
            out.append(unwrap(block))
            i += 1
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        nxt = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
        if len(lines) == 2:
            out.append(f"## {lines[0].rstrip('.:')}: {lines[1]}")
        elif (  # standalone subtitle block rides along: "CHAPTER I" + "The Castle"
            nxt and "\n" not in nxt and len(nxt) <= 60 and not is_heading(nxt)
            and i + 2 < len(blocks) and len(blocks[i + 2]) > 150
        ):
            out.append(f"## {lines[0].rstrip('.:')}: {nxt}")
            i += 1
        else:
            out.append(f"## {lines[0]}")
        i += 1
    return "\n\n".join(out) + "\n"

_EMPHASIS = re.compile(r"_([^_\n]{1,300}?)_")

# %% Single-quote dialogue -> curly double (flagged books only)

_DIALECT = re.compile(r"(?i)^(?:tis|twas|em|e|im|er|un|ere|ave|ow)\b")

def has_single_dialogue(body: str) -> bool:
    singles = len(re.findall(r"(?:^|[\s(—-])'\w", body))
    return singles >= 30 and singles > 3 * (body.count('"') + body.count("“"))

def convert_single_dialogue(par: str) -> str:
    """Pair-scan straight singles: open after whitespace, close after punctuation.
    Dialect apostrophes ('em, 'im) skip; an unpaired span dies at the paragraph break."""
    chars, inside = list(par), False
    for m in re.finditer(r"'", par):
        i = m.start()
        prev = par[i - 1] if i else " "
        nxt = par[i + 1] if i + 1 < len(par) else " "
        opens = prev in " \t\n(—-_" and (nxt.isalpha() or nxt == "_")
        if not inside and opens and not _DIALECT.match(par[i + 1 :]):
            chars[i], inside = "“", True
        elif inside and (prev in ".,!?;:—-_)" or (prev.isalpha() and i == len(par) - 1)):
            chars[i], inside = "”", False
    return "".join(chars)

# %% Naming - display author/title, folder and file slugs

_PAREN = re.compile(r"\([^)]*\)")
_ROLE = re.compile(r"\[[^\]]*\]")  # catalog role tags: [Illustrator], [Translator], ...
_DATE_PART = re.compile(r"\d{4}|^[\d? –-]+$|\bcent(?:ury)?\b", re.I)

def display_author(catalog_authors: str) -> str:
    """'Smith, Clark Ashton, 1893-1961' -> 'Clark Ashton Smith'; role tags dropped unless all entries are tagged."""
    entries = [e.strip() for e in catalog_authors.split(";") if e.strip()]
    names: list[str] = []
    for entry in [e for e in entries if not _ROLE.search(e)] or entries:
        parts = [p.strip() for p in _ROLE.sub("", _PAREN.sub("", entry)).split(",")]
        parts = [p for p in parts if p and not _DATE_PART.search(p)]
        if parts:
            names.append(" ".join(parts[1:] + parts[:1]) if len(parts) > 1 else parts[0])
    return "; ".join(names) or "Unknown"

def _asciify(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

def author_folder(display: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", _asciify(display.split(";")[0])).strip("-") or "Unknown"

def display_title(title: str) -> str:
    return re.sub(r"\s*[\r\n]+\s*", ": ", title.strip())

def title_slug(title: str) -> str:
    head = re.split(r"[:;\n\r]", title)[0]
    return re.sub(r"[^a-z0-9]+", "-", _asciify(head).lower()).strip("-")[:60] or "untitled"

def to_markdown(raw: bytes, title: str, author: str) -> str:
    text = decode(raw).replace("\r\n", "\n").replace("\r", "\n")
    body = _ETEXT_LINE.sub("", _BRACKET_NOTE.sub("", isolate_body(text)))
    blocks = drop_front_matter(drop_contents(split_blocks(body)), title, author)
    while blocks and _TAIL.match(blocks[-1].strip()):
        blocks.pop()
    body_md = render_blocks(blocks)
    if has_single_dialogue(body_md):
        body_md = "\n\n".join(convert_single_dialogue(p) for p in body_md.split("\n\n"))
    header = f"# {display_title(title)}\n\n*{author}*\n\n---\n\n"
    return _EMPHASIS.sub(r"*\1*", header + body_md)

# %% Run

if __name__ == "__main__":  # Jupyter sets __main__, so this runs in Fabric but not on import
    import notebookutils
    import polars as pl
    from deltalake import DeltaTable, write_deltalake

    def storage_options() -> dict[str, str]:
        return {
            "bearer_token": notebookutils.credentials.getToken("storage"),
            "use_fabric_endpoint": "true",
        }

    run_ts = datetime.now(timezone.utc)
    notebookutils.fs.mount(SILVER_LAKEHOUSE, "/silver")
    corpus_root = Path(notebookutils.fs.getMountPath("/silver")) / CORPUS_SUBDIR

    roster = pl.from_arrow(
        DeltaTable(RAW_WORKS_TABLE, storage_options=storage_options()).to_pyarrow_table()
    ).select("gutenberg_id", "title", "authors")

    if corpus_root.exists():
        shutil.rmtree(corpus_root)  # derived layer: full rebuild keeps it roster-shaped
    corpus_root.mkdir(parents=True)

    stripped = failed = missing = 0
    for row in roster.sort("gutenberg_id").iter_rows(named=True):
        src = TEXTS_ROOT / f"{row['gutenberg_id']}.txt"
        if not src.exists():
            missing += 1
            continue
        author = display_author(row["authors"] or "")
        title = row["title"] or ""
        try:
            md = to_markdown(src.read_bytes(), title, author)
        except ValueError as exc:
            print(f"{row['gutenberg_id']}: {exc}")
            failed += 1
            continue
        dest = corpus_root / author_folder(author) / f"{row['gutenberg_id']}-{title_slug(title)}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8", newline="\n")
        stripped += 1

    audit = pl.DataFrame(
        [(run_ts, roster.height, stripped, failed, missing)],
        schema={
            "run_ts": pl.Datetime("us", "UTC"), "roster_size": pl.Int64,
            "stripped": pl.Int64, "failed": pl.Int64, "missing_text": pl.Int64,
        },
        orient="row",
    )
    write_deltalake(STRIP_AUDIT_TABLE, audit.to_arrow(), mode="append", storage_options=storage_options())
    print(f"corpus: {stripped:,} written, {failed:,} failed, {missing:,} missing -> lh_silver/{CORPUS_SUBDIR}")
