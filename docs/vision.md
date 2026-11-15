# Vision

Gutenberg Fingerprint measures the style of every English science-fiction, fantasy, and horror book in Project Gutenberg and publishes the comparison at [gufime.com](https://gufime.com/). A reader browses which works and authors are most distinctive, and how the CEO's own fiction compares.

**For:** readers and writers curious how genre prose differs.

**Success:** a nightly pipeline that picks up every New or Changed in-scope Work without a human, and a site that is never more than a day stale.

**Principles:**

- Every published number is a z-score against the whole corpus.
- Polite to Project Gutenberg: official feeds, rate-limited, cached.
- Cheap: one ~$5/month box and free tiers.
- Only new or changed works reprocess.

**Out of scope:** non-English works, genres outside the three, and per-reader accounts.
