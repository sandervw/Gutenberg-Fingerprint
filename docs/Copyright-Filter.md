# Plan: Filter copyrighted PG donations out of bronze

Drop Project Gutenberg's copyrighted donations from the corpus. `pg_catalog.csv` has no rights column; the signal is in the text header `*** This is a COPYRIGHTED Project Gutenberg eBook. Details Below. ***` (line 11, by byte ~576). `text_ingest.py` sniffs each fetched text before writing; matches are skipped and stamped with a terminal `copyrighted` watermark status. A one-time sweep clears the 49 already in bronze.

## `python/helpers/filter.py`

Add a bytes-level predicate:

```python
# %% Copyrighted donations - PG header sits above the START marker

COPYRIGHT_MARKER: bytes = b"copyrighted project gutenberg ebook"
COPYRIGHT_SCAN_BYTES: int = 2048  # marker lands by byte ~576


def is_copyrighted(raw_bytes: bytes) -> bool:
    """True when PG's copyrighted-donation header is present."""
    return COPYRIGHT_MARKER in raw_bytes[:COPYRIGHT_SCAN_BYTES].lower()
```

## `python/workflow/text_ingest.py`

1. Import the helper alongside `storage`:

```python
from python.helpers import filter, storage
```

2. In `download_texts`, after `fetch_text` succeeds, branch before the write. Skip the write, delete any stale file, record `"copyrighted"`, reset the failure streak:

```python
            raw_bytes = fetch_text(gutenberg_id, session)
            if filter.is_copyrighted(raw_bytes):
                (TEXTS_ROOT / f"{gutenberg_id}.txt").unlink(missing_ok=True)
                rows.append((gutenberg_id, row["catalog_row_hash"], None, "copyrighted"))
                consecutive_failures = 0
                continue
            (TEXTS_ROOT / f"{gutenberg_id}.txt").write_bytes(raw_bytes)
            text_hash = hashlib.sha256(raw_bytes).hexdigest()
            rows.append((gutenberg_id, row["catalog_row_hash"], text_hash, "ingested"))
            consecutive_failures = 0
```

3. In `__main__`, compute `failed` from the explicit status and add a stdout `copyrighted` tally:

```python
    processed: pl.DataFrame = download_texts(todo)
    downloaded: int = processed.filter(pl.col("status") == "ingested").height
    failed: int = processed.filter(pl.col("status") == "failed").height
    copyrighted: int = processed.filter(pl.col("status") == "copyrighted").height
```

```python
    print(
        f"texts: {downloaded:,} downloaded, {failed:,} failed, {copyrighted:,} copyrighted"
        f" -> {TEXTS_ROOT} | {deferred:,} left for the next run"
    )
```

`write_audit(...)` stays as-is: same signature, same `bronze.ingest_audit` schema. No change to `pick_downloads` or `update_watermark`.

## One-time cleanup on the box

```bash
ssh box
cd /files/gufime/bronze/texts

# ids of the copyrighted texts (expect 49)
ids=$(grep -rli "copyrighted project gutenberg ebook" . | sed 's#^\./##; s#\.txt$##' | sort -n)
printf '%s\n' "$ids" | wc -l

# remove the bronze files
for id in $ids; do rm -f "$id.txt"; done

# flip their watermark rows
csv=$(printf '%s\n' "$ids" | paste -sd,)
psql -d gufime -c "update bronze.watermark set status='copyrighted', text_hash=null where gutenberg_id in ($csv);"
```

The next nightly run rebuilds silver, gold, and gufime.com from bronze. To purge the site immediately, run `strip → measure → dbt build → evidence build/deploy` on the box after the sweep.

## Docs

- `docs/Project-Outline.md`: add `copyrighted` to the watermark status vocabulary (near lines 43-44); note `text_ingest` skips copyrighted donations. Mark roadmap item #1 "Filtering/Cleansing Improvements" (lines 115-117) done.
- `README.md`: near lines 43-44, note `copyrighted` as a terminal, non-retried status.

## Validation

```bash
# the predicate (duckdb/local, no mirror needed)
uv run python -c "from python.helpers import filter as f; assert f.is_copyrighted(b'junk\n*** This is a COPYRIGHTED Project Gutenberg eBook. Details Below. ***'); assert not f.is_copyrighted(b'*** START OF THE PROJECT GUTENBERG EBOOK ***'); print('ok')"
```

- `bronze.ingest_audit` still writes with the unchanged schema, one row per run.
- After the sweep: `grep -rli "copyrighted project gutenberg ebook" /files/gufime/bronze/texts | wc -l` → `0`; `psql -d gufime -c "select count(*) from bronze.watermark where status='copyrighted';"` → `49`.
- After the next full run: two removed ids return 0 from `gold.mart_work` and 404 on the site.
