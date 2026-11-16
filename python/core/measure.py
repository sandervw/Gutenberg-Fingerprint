# Measure rules: which works to parse, and their metric and vocabulary rows.

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from spacy.language import Language
from spacy.tokens import Doc

from python.core.stylometrics import (
    adjective_density,
    adverb_density,
    alpha_word_count,
    archaic_word_rate,
    contraction_rate,
    dialogue_narration_ratio,
    function_word_frequency,
    honore_statistic,
    mean_parse_tree_depth,
    mean_sentence_length,
    mean_word_length,
    punctuation_frequency,
    sentence_length_stdev,
    sentence_type_mix,
    yules_characteristic,
)
from python.core.vocab import vocab_terms

# Chunk size stays under spaCy's 1M-char limit
MAX_CHUNK_CHARS = 100_000

# Per-work metrics; append new metrics here
METRIC_FUNCTIONS = (
    mean_word_length,          # 1
    yules_characteristic,      # 2
    archaic_word_rate,         # 3
    honore_statistic,          # 4
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

# %% Plan - incremental by per-work watermark


@dataclass(frozen=True)
class MeasureTimes:
    """Per work id: last measured, last catalog change, last manual upload."""

    measured_at: dict[str, datetime]
    catalog_changed_at: dict[str, datetime]
    self_changed_at: dict[str, datetime]


@dataclass(frozen=True)
class MeasurePlan:
    """Works to parse now, and measured works gone from the corpus."""

    todo: dict[str, Path]
    stale_ids: list[str]


def _needs_measure(measured: datetime | None, changed: datetime | None) -> bool:
    """Re-parse when unmeasured or the source changed after measuring."""
    if measured is None:
        return True
    return changed is not None and changed > measured


def plan_measures(
    sources: dict[str, Path], self_ids: frozenset[str], measure_times: MeasureTimes
) -> MeasurePlan:
    """Pick works to parse and measured works to drop."""
    todo: dict[str, Path] = {}
    for work_id, path in sources.items():
        changed_at = measure_times.self_changed_at if work_id in self_ids else measure_times.catalog_changed_at
        if _needs_measure(measure_times.measured_at.get(work_id), changed_at.get(work_id)):
            todo[work_id] = path
    return MeasurePlan(todo=todo, stale_ids=sorted(set(measure_times.measured_at) - set(sources)))


# %% Parse and measure (chunk -> parse -> reassemble)


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


def build_work_document(language_model: Language, clean_text: str) -> Doc:
    """Chunk, parse as a stream, stitch back into one Doc."""
    chunks = chunk_text(clean_text, MAX_CHUNK_CHARS)
    documents = list(language_model.pipe(chunks, batch_size=8))
    return Doc.from_docs(documents)


def measure_metrics(work_id: str, document: Doc) -> list[tuple[str, str, float]]:
    """Every metric series as (work_id, metric, value) rows, then word_count."""
    rows = [
        (work_id, metric_name, float(value))
        for metric_function in METRIC_FUNCTIONS
        for metric_name, value in metric_function(document).items()
    ]
    # word_count rides raw_measurements for dim_work
    rows.append((work_id, "word_count", float(alpha_word_count(document))))
    return rows


def collect_vocab(work_id: str, document: Doc) -> list[tuple[str, str, int]]:
    """One raw_vocab row per distinct content lemma."""
    return [(work_id, term, count) for term, count in vocab_terms(document).items()]
