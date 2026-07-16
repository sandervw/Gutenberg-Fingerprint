# CLAUDE.md

**IMPORTANT (project override, added 2026-07-08):** The global "keep replies under 150 words" rule is **a soft cap for this project**. This is a learning project: explanations get the room they need. Stay to-the-point (no padding, no restating known facts).

## Implementation docs

`docs\fabric_gutenberg_stylometrics_project.md` documents the project's finished design. Consult it as the reference.

Reference the past project for design choices related to dbt, python, or evidence: `C:\Users\Sander\OneDrive\Documents\Github\Fiction-Fingerprint`

## How we work

- The user is still learning, so **you are also the documentation**: explain what you're doing and why as you go, enough to follow without leaving the editor. dbt/DuckDB basics are known; assume **zero prior Fabric knowledge**.
- **Build piece-by-piece, pause at boundaries.** Batch closely related steps (multiple edits to one model, a run+test cycle), but **stop and check in before moving to a new type of file or a set of commands serving a different purpose** — e.g. switching from dbt work to pipeline work. Don't gate every individual command or file.
- For a **significant or hard-to-reverse design/tech choice**, call out the options and your recommendation before committing to it.
- **Never rely on memory for code/tech specs.** Check the local refs in `docs/reference/`. If they don't cover it, fetch current docs (Context7 / Microsoft Learn MCP / official sources), then update the ref files.
- **Be lean, not clipped.** No filler, no restating known facts, no exhaustive examples — but explanations get full room (see word-cap override above).
- **Never add, stage, or GIT commit.**
- **Checkpoint ritual.** When the user wraps up a session ("done for a while", "add a left-off memory"), overwrite the `project-checkpoint` memory in place.
- **Never add another memory.** `project-checkpoint` is the only memory; overwrite it in place, never create new memory files.

## Deployment

- The Evidence site (`evidence/`) will be published to Cloudflare Pages (URL TBD — record it here at first deploy, Phase 5).
- Styling mirrors the user's other site, **wordleaves.com** (see `evidence/sparse.css` + `evidence/wordleaves.css`: cream/charcoal, copper accent, iA Writer Quattro font).

## Environment

- Windows 11, bash terminal, VS Code. Python 3.14 and `uv` are installed.
- Before suggesting any `uv` command, explain how it differs from plain `python`/`pip`.

---
