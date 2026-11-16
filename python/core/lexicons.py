# Tunable reference tables read by the stylometric metrics.

from __future__ import annotations

# Metric 5 - function words tracked individually
FUNCTION_WORDS: tuple[str, ...] = (
    "the", "of", "and", "a", "an", "to", "in", "that", "it", "is",
    "was", "for", "with", "as", "on", "at", "by", "be", "this", "had",
    "not", "but", "from", "or", "which", "they", "you", "his", "her", "their",
    "would", "there", "been", "when", "so", "if", "no", "all", "we", "he",
)

# Metric 3 - archaic / elevated diction (hand-picked, not exhaustive).
ARCHAIC_WORDS: frozenset[str] = frozenset({
    "thou", "thee", "thy", "thine", "ye", "thyself",
    "hath", "doth", "hast", "dost", "wast", "wert", "shalt", "wilt",
    "ere", "oft", "whilst", "amongst", "betwixt", "amidst", "unto", "upon",
    "hither", "thither", "whither", "hence", "thence", "whence", "yonder",
    "nigh", "naught", "aught", "wrought", "clad", "smote", "slew", "bade",
    "mayhap", "perchance", "verily", "forsooth", "anon", "wherefore",
    "methinks", "prithee", "lo", "behold", "nay", "yea", "spake", "wroth",
})

# Metric 10 - subkey -> token strings counted as that mark
PUNCTUATION_MARKS: dict[str, frozenset[str]] = {
    "comma": frozenset({","}),
    "semicolon": frozenset({";"}),
    "colon": frozenset({":"}),
    "period": frozenset({"."}),
    "question": frozenset({"?"}),
    "exclamation": frozenset({"!"}),
    "dash": frozenset({"—", "–", "--"}),
    "ellipsis": frozenset({"…", "..."}),
    "parenthesis": frozenset({"(", ")"}),
}

# Metric 11 - spaCy contraction clitics; "'s" handled in code
CONTRACTION_CLITICS: frozenset[str] = frozenset({
    "n't", "'re", "'ve", "'ll", "'m", "'d",
})

# Metric 12 - double-quote characters bounding dialogue
OPEN_QUOTES: frozenset[str] = frozenset({"“"})
CLOSE_QUOTES: frozenset[str] = frozenset({"”"})
STRAIGHT_QUOTES: frozenset[str] = frozenset({'"'})
