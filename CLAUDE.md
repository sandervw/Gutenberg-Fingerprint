# CLAUDE.md

Nightly CDC pipeline over the Project Gutenberg sci-fi/fantasy/horror corpus. Published to Cloudflare Pages at https://gufime.com/.

`README.md` is the architecture. `docs/Project-Outline.md` is the design and the roadmap. `docs/reference/` holds verified tech notes.

## Rules

- **Never add, stage, or commit to git.**
- **All comments, descriptions, and other forms of 'in-code documentation', must be 12 words or fewer. No exceptions.**
- Check `docs/reference/` first for tech specs; if it isn't covered there, fetch current docs (Context7 / Microsoft Learn MCP / official sources), then update the ref file.
- **No verification nagging.** When something ran and passed, it's done. Name the next concrete step instead.
- For a significant or hard-to-reverse design choice, give the options and a recommendation before committing to it.

## Notes

- dbt models must compile on **both** targets: `duckdb` (local dev) and `postgres` (prod).
- Site styling mirrors wordleaves.com (`evidence/sparse.css` + `evidence/wordleaves.css`): cream/charcoal, copper accent, iA Writer Quattro.
- **Environment** Windows 11, Bash/Powershell, VS Code. Python via `uv` (`uv run ...`), Node 24 for Evidence (pinned in `evidence/.node-version`).
- **Box (OVH VPS):** `ssh box` (aliased in `~/.ssh/config`; user `gufime@15.204.82.199`, key `~/.ssh/gufime_rsa`). Files under `/files/gufime/`; bronze texts at `/files/gufime/bronze/texts/`. Postgres via unix socket, peer auth.
