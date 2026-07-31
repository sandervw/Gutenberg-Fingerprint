# Per-work content-lemma vocabulary for the Jaccard overlap (metric 15).

from __future__ import annotations

from collections import Counter

from spacy.tokens import Doc

# Open-class POS; PROPN excluded (names swamp shared diction)
CONTENT_POS: frozenset[str] = frozenset({"NOUN", "VERB", "ADJ", "ADV"})


def vocab_terms(doc: Doc) -> Counter[str]:
    """Metric 15 (Python half): content-word lemma counts per work."""
    return Counter(
        token.lemma_.lower()
        for token in doc
        if token.is_alpha and not token.is_stop and token.pos_ in CONTENT_POS
    )
