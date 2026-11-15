# Glossary

| Term | Meaning |
|---|---|
| **Work** | One Project Gutenberg book, keyed by `gutenberg_id`. |
| **Author** | A catalog author of one or more Works. |
| **Self** | The CEO and chosen comparison authors, flagged `is_self`. |
| **Corpus** | Every in-scope Work with a stripped text. |
| **In scope** | English, `Type = Text`, and science fiction, fantasy, or horror. |
| **Genre** | One of `Sci-Fi`, `Fantasy`, `Horror`, or `Undetermined` when several match. |
| **Flags** | `is_translation`, `is_juvenile`, `is_play`, `is_poetry`. |
| **Metric** | One measured concept, such as Yule's K. There are 15. |
| **Series** | One measured value stream of a Metric. There are 63. |
| **Z-score** | A value's distance from the corpus mean, in standard deviations. Every published number is one. |
| **Excess** | Per Work, the sum of each Metric's z-score beyond ±2. Ranks the Weirdest Works. |
| **Vocabulary overlap** | Jaccard overlap of two Authors' top-N vocabularies. |
| **Watermark** | `bronze.watermark`: per-Work hashes and status driving change detection. |
| **New, Changed, Retry** | Why a Work reprocesses: absent, catalog hash differs, or last attempt failed. |
| **Status** | `ingested`, `failed`, or `copyrighted`. |
| **Gate** | The sensor that launches the downstream job when `new_count`, New plus Changed Works, is above 0. |
| **Bronze, Silver, Gold** | Raw landed data, stripped texts, and the dbt layer. |
| **Reader** | An anonymous visitor to gufime.com. |
| **The box** | The OVH VPS running Postgres, Dagster, and the site build. |
