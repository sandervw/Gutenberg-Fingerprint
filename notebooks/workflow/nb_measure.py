# Fabric notebook: nb_measure
# Silver Files/corpus/<Author>/<id>-<slug>.md -> silver Tables/dbo/raw_measurements
# + raw_vocab: clean markdown, parse with spaCy (chunked for long novels), run
# every metric, land tidy Delta rows. Cleaning comes from nb_clean; lexicons,
# metrics, and vocab from their notebooks (%run pulls definitions into this session).

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
from deltalake import write_deltalake
from spacy.language import Language
from spacy.tokens import Doc

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
SILVER_LAKEHOUSE: str = f"{ONELAKE}/lh_silver.Lakehouse"
MEASUREMENTS_TABLE: str = f"{SILVER_LAKEHOUSE}/Tables/dbo/raw_measurements"
VOCAB_TABLE: str = f"{SILVER_LAKEHOUSE}/Tables/dbo/raw_vocab"
CORPUS_SUBDIR: str = "Files/corpus"

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

# Disable NER: no metric uses named entities, and skipping it speeds parsing.
nlp = spacy.load("en_core_web_sm", disable=["ner"])

# One parse per work yields its measurement rows and vocab rows; work_id is the
# gutenberg_id filename prefix, matching dim_work's cast of the catalog id.
measurement_rows: list[tuple[str, str, float]] = []
vocab_rows: list[tuple[str, str, int]] = []
sources = sorted(corpus_root.rglob("*.md"))
for done, source in enumerate(sources, start=1):
    work_id = source.name.split("-", 1)[0]
    doc = build_work_doc(nlp, clean_markdown(source.read_text(encoding="utf-8")))
    measurement_rows.extend(measure_metrics(work_id, doc))
    # word_count rides raw_measurements for dim_work; the int model keeps it
    # out of the z-scored fingerprint.
    word_count = sum(1 for token in doc if token.is_alpha)
    measurement_rows.append((work_id, "word_count", float(word_count)))
    vocab_rows.extend(collect_vocab(work_id, doc))
    if done % 50 == 0 or done == len(sources):
        print(f"{done}/{len(sources)} works parsed")

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

# Derived layer: full overwrite keeps both tables corpus-shaped.
write_deltalake(MEASUREMENTS_TABLE, measurements.to_arrow(), mode="overwrite", storage_options=storage_options())
write_deltalake(VOCAB_TABLE, vocab.to_arrow(), mode="overwrite", storage_options=storage_options())
print(
    f"Landed {len(sources)} works; {measurements.height:,} rows into raw_measurements "
    f"({len(METRIC_FUNCTIONS)} metrics); {vocab.height:,} rows into raw_vocab."
)
