---
name: handoff
description: Current state, next work, CEO preferences, and gotchas for Gutenberg Fingerprint. Use at the start of every session, and rewrite the State and Next sections before ending one.
---

# Handoff

Current state and next work. Rewrite when stale; never log history.

## State

- **Production** runs `main`: the nightly Dagster pipeline on the box and gufime.com on Cloudflare Pages.
- **Process:** the CTO ships through PRs with reviewer gates. CI checks only changed files until #1 lands.

## Next

1. #1: bring `python/` to simple-code and a core/shell layout; then CI checks the whole repo.
2. #4: fix the Fabric credit in the home page footer.
3. #2: Playwright specs for the site use cases.
4. #3: retry policies for network-bound assets.
5. #5: custom frontend; research brief and CEO sign-off first.

## CEO preferences

- Hands-off: the CTO decides and ships. Bring the CEO only the items `CLAUDE.md` lists, with a recommendation.
- Site styling mirrors wordleaves.com. New visual design needs the CEO's sign-off.
- Close issues rather than open new ones. One batch, one PR.
- Time-box agents to 15 to 30 minutes.
- Docs state the current design only; no decision logs or history.
- The CEO WILL NOT manage secrets or `.env` files. Retrieve, read, and write them yourself.

## Gotchas

- `gh pr merge` is blocked by `.claude/hooks/require_reviews.py` until the review PASS comments name the head commit. Re-review after every push.
- A PR body's `Fixes #a, #b` closes only the first; write `Fixes` before each number.
- Auto-merge is off: `gh pr checks N --watch`, then `gh pr merge N --merge`.
- Every merge to `main` restarts Dagster on the box. Never merge while a run is in progress; check the Dagster UI first.
- Inspect production data over `ssh gufime`; Postgres is `psql gufime` with peer auth.
- `dbt/profiles.yml` holds the laptop's absolute path for the DuckDB target. `dbt parse` ignores it; `dbt build --target duckdb` elsewhere needs it changed.
- A stale or locked `.venv` gives "uv trampoline failed"; recreate it, or set `UV_PROJECT_ENVIRONMENT` to a fresh folder.
- Pin `dbt-core` below 2.0.
- Project Gutenberg politeness: never raise download rates or caps without the CEO.
- An unquoted `: ` in an agent `description` breaks loading; agent file changes need a session restart.
- Python's `write_text` on Windows writes CRLF; pass `newline="\n"` or use Edit.
