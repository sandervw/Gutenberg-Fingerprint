# spaCy reference

Python extractor only.

`spacy` 3.8.x, model `en_core_web_sm` 3.8.0: tagger, parser, sentence segmenter, NER. No word vectors.

## Install

```bash
uv add "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

Pin writes `[tool.uv.sources]` in `pyproject.toml`; `python -m spacy download` is untracked.

## Metric sources

- Sentence length and count: `doc.sents`, `token.is_alpha`
- Adjective/adverb density: `token.pos_` == `ADJ` / `ADV`
- Parse-tree depth: hops from token up to ROOT (own head); sentence depth = deepest token
- Sentence type: complex = child `dep_` in advcl, ccomp, xcomp, acl, relcl, csubj; compound = `conj` joining clause heads, usually with `cc`; simple = neither
- Punctuation: `token.is_punct`
- Yule's K, Honoré's R, function-word frequency, contraction rate, Jaccard: token counting only

## Long texts

Parser/NER take ~1GB temp memory per 100k chars. `nlp()` enforces `nlp.max_length`, default 1,000,000 chars. Split cleaned text into sub-100k-char chunks on blank-line boundaries, parse via `nlp.pipe(chunks, batch_size=8)`, merge with `Doc.from_docs(docs)`, run metrics on the work-level Doc. `from_docs` requires a shared `Vocab`. Small works stay one chunk.
