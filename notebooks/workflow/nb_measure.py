# Measure: corpus markdown -> raw_measurements + raw_vocab, incremental by watermark.

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import spacy
from spacy.language import Language
from spacy.tokens import Doc

from notebooks.helpers import storage
from notebooks.helpers.nb_clean import clean_markdown
from notebooks.helpers.nb_stylometrics import (
    adjective_density,
    adverb_density,
    archaic_word_rate,
    contraction_rate,
    dialogue_narration_ratio,
    function_word_frequency,
    honore_r,
    mean_parse_tree_depth,
    mean_sentence_length,
    mean_word_length,
    punctuation_frequency,
    sentence_length_stdev,
    sentence_type_mix,
    yules_k,
)
from notebooks.helpers.nb_vocab import vocab_terms

SELF_FOLDER: str = "Sander-VanWilligen"

# Chunk size stays under spaCy's 1M-char limit
MAX_CHUNK_CHARS = 100_000

# Per-work metrics; append new metrics here
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
    """Split below max_chars, breaking only on blank lines."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
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
    """Chunk, parse as a stream, stitch back into one Doc."""
    chunks = chunk_text(clean_text, MAX_CHUNK_CHARS)
    docs = list(nlp.pipe(chunks, batch_size=8))
    return Doc.from_docs(docs)


def measure_metrics(work_id: str, doc: Doc) -> list[tuple[str, str, float]]:
    """Flatten every metric's dict into (work_id, metric, value) rows."""
    rows: list[tuple[str, str, float]] = []
    for metric_fn in METRIC_FUNCTIONS:
        for metric_name, value in metric_fn(doc).items():
            rows.append((work_id, metric_name, float(value)))
    return rows


def collect_vocab(work_id: str, doc: Doc) -> list[tuple[str, str, int]]:
    """One raw_vocab row per distinct content lemma."""
    return [(work_id, term, count) for term, count in vocab_terms(doc).items()]


def source_work_id(source: Path) -> str:
    # Gutenberg filename prefix, or the full stem for self works
    return source.stem if source.parent.name == SELF_FOLDER else source.name.split("-", 1)[0]


# %% Run

if __name__ == "__main__":
    corpus_root = storage.file_path("silver/corpus")
    manifest_path = storage.file_path("bronze/self/_manifest.csv")

    sources = {source_work_id(p): p for p in sorted(corpus_root.rglob("*.md"))}

    # Per-work high-water mark of loaded_at
    try:
        loaded_at_by_id: dict[str, datetime] = dict(
            storage.read_table("raw.raw_measurements", columns=["work_id", "loaded_at"])
            .group_by("work_id")
            .agg(pl.col("loaded_at").max())
            .iter_rows()
        )
    except storage.TableMissing:
        loaded_at_by_id = {}

    changed_at: dict[str, datetime] = {
        str(gid): ts
        for gid, ts in storage.read_table(
            "bronze.watermark", columns=["gutenberg_id", "last_changed"]
        ).iter_rows()
    }

    # Manual works' watermark: the seed manifest's loaded_at stamps
    manual_changed_at: dict[str, datetime] = dict(
        pl.read_csv(manifest_path, schema_overrides={"loaded_at": pl.String})
        .select(
            "work_id",
            pl.col("loaded_at").str.to_datetime("%Y-%m-%d %H:%M:%S").dt.replace_time_zone("UTC"),
        )
        .iter_rows()
    )

    def needs_measure(work_id: str, source: Path) -> bool:
        """Re-parse when unmeasured or the source changed after measuring."""
        if work_id not in loaded_at_by_id:
            return True
        ledger = manual_changed_at if source.parent.name == SELF_FOLDER else changed_at
        changed = ledger.get(work_id)
        return changed is not None and changed > loaded_at_by_id[work_id]

    todo = {wid: p for wid, p in sources.items() if needs_measure(wid, p)}
    stale_ids = sorted(set(loaded_at_by_id) - set(sources))
    print(f"corpus {len(sources)}: {len(todo)} to measure, {len(stale_ids)} stale to drop")

    # NER disabled: no metric uses it, skipping speeds parsing
    nlp = spacy.load("en_core_web_sm", disable=["ner"])

    measurement_rows: list[tuple[str, str, float]] = []
    vocab_rows: list[tuple[str, str, int]] = []
    for done, (work_id, source) in enumerate(todo.items(), start=1):
        doc = build_work_doc(nlp, clean_markdown(source.read_text(encoding="utf-8")))
        measurement_rows.extend(measure_metrics(work_id, doc))
        # word_count rides raw_measurements for dim_work
        word_count = sum(1 for token in doc if token.is_alpha)
        measurement_rows.append((work_id, "word_count", float(word_count)))
        vocab_rows.extend(collect_vocab(work_id, doc))
        if done % 50 == 0 or done == len(todo):
            print(f"{done}/{len(todo)} works parsed")

    # One batch timestamp shared by both tables
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

    def sync_table(name: str, frame: pl.DataFrame) -> None:
        """Swap re-measured works' rows in place, drop stale, keep the rest."""
        if not loaded_at_by_id:  # first fill
            storage.write_table(name, frame, mode="overwrite")
            return
        storage.delete_where(name, "work_id", sorted(set(todo) | set(stale_ids)))
        if frame.height:
            storage.write_table(name, frame, mode="append")

    sync_table("raw.raw_measurements", measurements)
    sync_table("raw.raw_vocab", vocab)
    print(
        f"Measured {len(todo)} of {len(sources)} works ({len(stale_ids)} stale dropped); "
        f"{measurements.height:,} rows into raw_measurements "
        f"({len(METRIC_FUNCTIONS)} metrics); {vocab.height:,} rows into raw_vocab."
    )
