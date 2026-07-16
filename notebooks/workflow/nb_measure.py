# Fabric notebook: nb_measure
# Silver Files/corpus/<Author>/<id>-<slug>.md -> silver Tables/dbo/raw_measurements
# + raw_vocab: clean markdown, parse with spaCy (chunked for long novels), run
# every metric, land tidy Delta rows. Cleaning comes from nb_clean; lexicons,
# metrics, and vocab from their notebooks (%run pulls definitions into this session).
# Incremental: only new works, works whose watermark row changed after their rows
# landed, and self works re-parse; replaced rows are swapped in place and works
# gone from the corpus are dropped.

# %% Dependencies - model wheels declare no dependencies, so spacy is explicit
%pip install spacy==3.8.14 https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# %%
%run nb_clean

# %%
%run nb_lexicons

# %%
%run nb_stylometrics

# %%
%run nb_vocab

# %% Imports + constants

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import notebookutils
import polars as pl
import spacy
from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError
from spacy.language import Language
from spacy.tokens import Doc

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
SILVER_LAKEHOUSE: str = f"{ONELAKE}/lh_silver.Lakehouse"
MEASUREMENTS_TABLE: str = f"{SILVER_LAKEHOUSE}/Tables/dbo/raw_measurements"
VOCAB_TABLE: str = f"{SILVER_LAKEHOUSE}/Tables/dbo/raw_vocab"
WATERMARK_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/watermark"
CORPUS_SUBDIR: str = "Files/corpus"
SELF_FOLDER: str = "Sander-VanWilligen"

# Chunk size for parsing long works, kept under spaCy's 1M-char limit.
MAX_CHUNK_CHARS = 100_000

# Per-work metrics; each takes the work Doc and returns {metric_name: value}.
# Append new metrics here as they land.
METRIC_FUNCTIONS = (
    mean_word_length,          # 1
    yules_k,                   # 2
    archaic_word_rate,         # 3
    honore_r,                  # 4
    function_word_frequency,   # 5  (multi-value)
    mean_sentence_length,      # 6
    sentence_length_stdev,     # 7
    mean_parse_tree_depth,     # 8
    sentence_type_mix,         # 9  (multi-value)
    punctuation_frequency,     # 10 (multi-value)
    contraction_rate,          # 11
    dialogue_narration_ratio,  # 12
    adjective_density,         # 13
    adverb_density,            # 14
)

# %% Parsing (clean -> chunk -> parse -> reassemble)


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks below max_chars, breaking only on blank lines.

    Paragraph boundaries keep sentences whole, so per-chunk parses reassemble
    faithfully via Doc.from_docs.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        # Start a new chunk once the running one would exceed the limit.
        if current and size + len(paragraph) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            size = 0
        current.append(paragraph)
        size += len(paragraph) + 2  # +2 for the "\n\n" rejoin
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_work_doc(nlp: Language, clean_text: str) -> Doc:
    """Parse a (possibly long) work into one Doc without hitting spaCy's
    memory wall: chunk, parse as a stream, then stitch back together."""
    chunks = chunk_text(clean_text, MAX_CHUNK_CHARS)
    docs = list(nlp.pipe(chunks, batch_size=8))
    return Doc.from_docs(docs)


def measure_metrics(work_id: str, doc: Doc) -> list[tuple[str, str, float]]:
    """Run every metric over one work's Doc, flattening each {name: value}
    dict into one (work_id, metric, value) row."""
    rows: list[tuple[str, str, float]] = []
    for metric_fn in METRIC_FUNCTIONS:
        for metric_name, value in metric_fn(doc).items():
            rows.append((work_id, metric_name, float(value)))
    return rows


def collect_vocab(work_id: str, doc: Doc) -> list[tuple[str, str, int]]:
    """Turn one work's content-lemma counts into raw_vocab rows, one per
    distinct term. dbt later pools these up to the author for metric 15."""
    return [(work_id, term, count) for term, count in vocab_terms(doc).items()]


# %% Run

def storage_options() -> dict[str, str]:
    return {
        "bearer_token": notebookutils.credentials.getToken("storage"),
        "use_fabric_endpoint": "true",
    }

notebookutils.fs.mount(SILVER_LAKEHOUSE, "/silver")
corpus_root = Path(notebookutils.fs.getMountPath("/silver")) / CORPUS_SUBDIR

# work_id is the gutenberg_id filename prefix, or the full stem (= seed work_id)
# for self works.
def source_work_id(source: Path) -> str:
    return source.stem if source.parent.name == SELF_FOLDER else source.name.split("-", 1)[0]

sources = {source_work_id(p): p for p in sorted(corpus_root.rglob("*.md"))}

# Diff against what's already measured: per-work high-water mark of loaded_at.
try:
    loaded_at_by_id: dict[str, datetime] = dict(
        pl.from_arrow(
            DeltaTable(MEASUREMENTS_TABLE, storage_options=storage_options())
            .to_pyarrow_table(columns=["work_id", "loaded_at"])
        )
        .group_by("work_id")
        .agg(pl.col("loaded_at").max())
        .iter_rows()
    )
except TableNotFoundError:
    loaded_at_by_id = {}

changed_at: dict[str, datetime] = {
    str(gid): ts
    for gid, ts in pl.from_arrow(
        DeltaTable(WATERMARK_TABLE, storage_options=storage_options())
        .to_pyarrow_table(columns=["gutenberg_id", "last_changed"])
    ).iter_rows()
}

# A work re-parses when it has no rows yet, its watermark row changed after those
# rows landed, or it's a self work (no watermark entry; seconds to parse).
def needs_measure(work_id: str, source: Path) -> bool:
    if source.parent.name == SELF_FOLDER or work_id not in loaded_at_by_id:
        return True
    last_changed = changed_at.get(work_id)
    return last_changed is not None and last_changed > loaded_at_by_id[work_id]

todo = {wid: p for wid, p in sources.items() if needs_measure(wid, p)}
stale_ids = sorted(set(loaded_at_by_id) - set(sources))
print(f"corpus {len(sources)}: {len(todo)} to measure, {len(stale_ids)} stale to drop")

# Disable NER: no metric uses named entities, and skipping it speeds parsing.
nlp = spacy.load("en_core_web_sm", disable=["ner"])

# One parse per work yields its measurement rows and vocab rows.
measurement_rows: list[tuple[str, str, float]] = []
vocab_rows: list[tuple[str, str, int]] = []
for done, (work_id, source) in enumerate(todo.items(), start=1):
    doc = build_work_doc(nlp, clean_markdown(source.read_text(encoding="utf-8")))
    measurement_rows.extend(measure_metrics(work_id, doc))
    # word_count rides raw_measurements for dim_work; the int model keeps it
    # out of the z-scored fingerprint.
    word_count = sum(1 for token in doc if token.is_alpha)
    measurement_rows.append((work_id, "word_count", float(word_count)))
    vocab_rows.extend(collect_vocab(work_id, doc))
    if done % 50 == 0 or done == len(todo):
        print(f"{done}/{len(todo)} works parsed")

# One batch timestamp shared by both tables, tz-aware so the SQL endpoint
# surfaces the column (naive datetimes land as invisible timestamp_ntz).
loaded_at = datetime.now(timezone.utc)

measurements = pl.DataFrame(
    measurement_rows,
    schema={"work_id": pl.String, "metric": pl.String, "value": pl.Float64},
    orient="row",
).with_columns(loaded_at=pl.lit(loaded_at, dtype=pl.Datetime("us", "UTC")))
vocab = pl.DataFrame(
    vocab_rows,
    schema={"work_id": pl.String, "term": pl.String, "term_count": pl.Int64},
    orient="row",
).with_columns(loaded_at=pl.lit(loaded_at, dtype=pl.Datetime("us", "UTC")))

def sync_table(table_uri: str, frame: pl.DataFrame) -> None:
    """Swap re-measured works' rows in place, drop stale ones, keep the rest."""
    if not loaded_at_by_id:  # first fill
        write_deltalake(table_uri, frame.to_arrow(), mode="overwrite", storage_options=storage_options())
        return
    doomed = sorted(set(todo) | set(stale_ids))
    if doomed:
        id_list = ", ".join(f"'{i}'" for i in doomed)
        DeltaTable(table_uri, storage_options=storage_options()).delete(f"work_id IN ({id_list})")
    if frame.height:
        write_deltalake(table_uri, frame.to_arrow(), mode="append", storage_options=storage_options())

sync_table(MEASUREMENTS_TABLE, measurements)
sync_table(VOCAB_TABLE, vocab)
print(
    f"Measured {len(todo)} of {len(sources)} works ({len(stale_ids)} stale dropped); "
    f"{measurements.height:,} rows into raw_measurements "
    f"({len(METRIC_FUNCTIONS)} metrics); {vocab.height:,} rows into raw_vocab."
)
