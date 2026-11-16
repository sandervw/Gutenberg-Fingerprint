# Stylometric metrics: each takes a Doc, returns {metric_name: value}.

from __future__ import annotations

import math
import statistics
from collections import Counter

from spacy.tokens import Doc, Span, Token

from python.core.lexicons import (
    ARCHAIC_WORDS,
    CLOSE_QUOTES,
    CONTRACTION_CLITICS,
    FUNCTION_WORDS,
    OPEN_QUOTES,
    PUNCTUATION_MARKS,
    STRAIGHT_QUOTES,
)

# Dependency labels marking a subordinate clause -> the sentence is "complex".
SUBORDINATE_DEPENDENCIES: frozenset[str] = frozenset(
    {"advcl", "ccomp", "xcomp", "acl", "relcl", "csubj"}
)

# %% Shared helpers


def alpha_word_count(document: Doc) -> int:
    """Count word tokens (is_alpha) - the project-wide "word"."""
    return sum(1 for token in document if token.is_alpha)


def _word_frequencies(document: Doc) -> Counter[str]:
    """Frequency of each case-folded word type ("The"/"the" fold to one)."""
    return Counter(token.lower_ for token in document if token.is_alpha)


# %% Lexical


def mean_word_length(document: Doc) -> dict[str, float]:
    """Metric 1: mean characters per word (is_alpha tokens; len = letters)."""
    lengths = [len(token.text) for token in document if token.is_alpha]
    if not lengths:
        return {"mean_word_length": 0.0}
    return {"mean_word_length": sum(lengths) / len(lengths)}


def yules_characteristic(document: Doc) -> dict[str, float]:
    """Metric 2: Yule's K = length-stable richness (repetition raises K)."""
    counts = _word_frequencies(document)
    total = sum(counts.values())
    if total == 0:
        return {"yules_k": 0.0}
    sum_squares = sum(count * count for count in counts.values())
    characteristic = 10_000 * (sum_squares - total) / (total * total)
    return {"yules_k": characteristic}


def archaic_word_rate(document: Doc) -> dict[str, float]:
    """Metric 3: share of words found in ARCHAIC_WORDS."""
    words = alpha_word_count(document)
    if words == 0:
        return {"archaic_word_rate": 0.0}
    counts = _word_frequencies(document)
    archaic = sum(count for word, count in counts.items() if word in ARCHAIC_WORDS)
    return {"archaic_word_rate": archaic / words}


def honore_statistic(document: Doc) -> dict[str, float]:
    """Metric 4: Honoré's R = hapax-based richness (more hapaxes -> larger R)."""
    counts = _word_frequencies(document)
    total = sum(counts.values())
    vocab_size = len(counts)
    if total == 0 or vocab_size == 0:
        return {"honore_r": 0.0}
    hapaxes = sum(1 for count in counts.values() if count == 1)
    denominator = 1 - (hapaxes / vocab_size)
    if denominator == 0:
        return {"honore_r": 0.0}
    return {"honore_r": 100 * math.log(total) / denominator}


def function_word_frequency(document: Doc) -> dict[str, float]:
    """Metric 5 (multi-value): per-word rate of each FUNCTION_WORDS entry."""
    words = alpha_word_count(document)
    counts = _word_frequencies(document)
    if words == 0:
        return {f"funcword_{word}": 0.0 for word in FUNCTION_WORDS}
    return {f"funcword_{word}": counts.get(word, 0) / words for word in FUNCTION_WORDS}


# %% Syntactic


def mean_sentence_length(document: Doc) -> dict[str, float]:
    """Metric 6: words (is_alpha) per sentence (document.sents)."""
    sentence_count = sum(1 for _ in document.sents)
    if sentence_count == 0:
        return {"mean_sentence_length": 0.0}
    return {"mean_sentence_length": alpha_word_count(document) / sentence_count}


def sentence_length_stdev(document: Doc) -> dict[str, float]:
    """Metric 7: population stdev of sentence length in words - rhythm burstiness."""
    lengths = [sum(1 for token in sentence if token.is_alpha) for sentence in document.sents]
    if len(lengths) < 2:
        return {"sentence_length_stdev": 0.0}
    return {"sentence_length_stdev": statistics.pstdev(lengths)}


def _token_depth(token: Token) -> int:
    """Hops from a token up to its sentence ROOT."""
    depth = 0
    while token.head != token:
        token = token.head
        depth += 1
    return depth


def mean_parse_tree_depth(document: Doc) -> dict[str, float]:
    """Metric 8: mean over sentences of the deepest token's distance to ROOT."""
    depths = [
        max((_token_depth(token) for token in sentence), default=0)
        for sentence in document.sents
    ]
    if not depths:
        return {"mean_parse_tree_depth": 0.0}
    return {"mean_parse_tree_depth": sum(depths) / len(depths)}


def _classify_sentence(sentence: Span) -> str:
    """Simple/compound/complex by dependencies; complex > compound > simple."""
    if any(token.dep_ in SUBORDINATE_DEPENDENCIES for token in sentence):
        return "complex"
    coordinated = any(
        token.dep_ == "conj"
        and token.head.dep_ == "ROOT"
        and token.pos_ in {"VERB", "AUX"}
        for token in sentence
    )
    return "compound" if coordinated else "simple"


def sentence_type_mix(document: Doc) -> dict[str, float]:
    """Metric 9 (multi-value): simple/compound/complex shares, keyed senttype_<kind>."""
    counts = {"simple": 0, "compound": 0, "complex": 0}
    for sentence in document.sents:
        counts[_classify_sentence(sentence)] += 1
    total = sum(counts.values())
    if total == 0:
        return {f"senttype_{kind}": 0.0 for kind in counts}
    return {f"senttype_{kind}": count / total for kind, count in counts.items()}


# %% Mechanical


def punctuation_frequency(document: Doc) -> dict[str, float]:
    """Metric 10 (multi-value): per-word rate per PUNCTUATION_MARKS group."""
    words = alpha_word_count(document)
    mark_counts = Counter(token.text for token in document if token.is_punct)
    result: dict[str, float] = {}
    for name, marks in PUNCTUATION_MARKS.items():
        occurrences = sum(mark_counts.get(mark, 0) for mark in marks)
        result[f"punct_{name}"] = occurrences / words if words else 0.0
    return result


def contraction_rate(document: Doc) -> dict[str, float]:
    """Metric 11: contraction clitics per word; possessive 's excluded."""
    words = alpha_word_count(document)
    if words == 0:
        return {"contraction_rate": 0.0}
    contractions = 0
    for token in document:
        clitic = token.text.replace("’", "'").lower()
        if clitic in CONTRACTION_CLITICS:
            contractions += 1
        elif clitic == "'s" and token.tag_ != "POS":
            contractions += 1
    return {"contraction_rate": contractions / words}


# %% Structural


def _quote_state_after(token: Token, *, inside_quote: bool) -> bool:
    """Whether text after this token sits inside double quotes."""
    text = token.text
    if token.is_space:
        return inside_quote and "\n" not in text
    if text in OPEN_QUOTES:
        return True
    if text in CLOSE_QUOTES:
        return False
    if text in STRAIGHT_QUOTES:
        return not inside_quote
    return inside_quote


def dialogue_narration_ratio(document: Doc) -> dict[str, float]:
    """Metric 12: fraction of words inside double quotes; resets each paragraph."""
    total = 0
    dialogue = 0
    inside_quote = False
    for token in document:
        inside_quote = _quote_state_after(token, inside_quote=inside_quote)
        if token.is_alpha:
            total += 1
            if inside_quote:
                dialogue += 1
    if total == 0:
        return {"dialogue_narration_ratio": 0.0}
    return {"dialogue_narration_ratio": dialogue / total}


def adjective_density(document: Doc) -> dict[str, float]:
    """Metric 13: ADJ-tagged tokens as a fraction of all words."""
    word_count = alpha_word_count(document)
    if word_count == 0:
        return {"adjective_density": 0.0}
    adjectives = sum(1 for token in document if token.pos_ == "ADJ")
    return {"adjective_density": adjectives / word_count}


def adverb_density(document: Doc) -> dict[str, float]:
    """Metric 14: ADV-tagged tokens as a fraction of all words."""
    word_count = alpha_word_count(document)
    if word_count == 0:
        return {"adverb_density": 0.0}
    adverbs = sum(1 for token in document if token.pos_ == "ADV")
    return {"adverb_density": adverbs / word_count}
