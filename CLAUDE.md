# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT:** Whenever possible, keep responses to the user under 150 words.

## Purpose

A learning project for **dbt Core + Fabric**. The domain (stylometric "fingerprints" of Gutenberg authors) is the vehicle; the goal is **production data-engineering operations**: a nightly CDC pipeline (Data Factory orchestration, watermarks, audit trails), incremental dbt models in a Fabric Warehouse, and a self-managing capacity pause/resume bracket (FinOps). The dbt modeling layer carries over from the prior project and is already familiar; the Fabric/pipeline side is the new material — and the resume piece.

## Implementation docs

`docs\fabric_gutenberg_stylometrics_project.md` documents the project's finished design. Consult it as the reference.

Reference the past project for design choices related to dbt, python, or evidence: `C:\Users\Sander\OneDrive\Documents\Github\Fiction-Fingerprint`

## How we work

- The user is still learning, so **you are also the documentation**: explain what you're doing and why as you go, enough to follow without leaving the editor. dbt/DuckDB basics are known; assume **zero prior Fabric knowledge**.
- **Build piece-by-piece, pause at boundaries.** Batch closely related steps (multiple edits to one model, a run+test cycle), but **stop and check in before moving to a new type of file or a set of commands serving a different purpose** — e.g. finishing models and starting tests, or switching from dbt work to pipeline work. Don't gate every individual command or file.
- For a **significant or hard-to-reverse design/tech choice**, call out the options and your recommendation before committing to it. For small, reversible calls, pick a sensible default and note it.
- **Never rely on memory for code/tech specs.** Check the local refs in `docs/reference/` first (`dbt-core.md`, `dbt-duckdb.md`, `duckdb.md`, `evidence.md`, `fabric.md`, `spacy.md`, ...). If they don't cover it, fetch current docs (Context7 / Microsoft Learn MCP / official sources), then update/add the ref file. For Cloudflare, use the installed Cloudflare skills + docs MCP instead of a local ref.
- **Be lean.** Fewest words possible in chat and in prose docs. No extended justification, no restating known facts, no exhaustive examples.
- **Never stage or commit.** Don't run `git add`/`git commit` unless explicitly instructed; the user handles version control.

## Deployment

- The Evidence site (`evidence/`) will be published to Cloudflare Pages (URL TBD — record it here at first deploy, Phase 5).
- Styling mirrors the user's other site, **wordleaves.com** (see `evidence/sparse.css` + `evidence/wordleaves.css`: cream/charcoal, copper accent, iA Writer Quattro font).

## Environment

- Windows 11, bash terminal, VS Code. Python 3.14 and `uv` are installed.
- Before suggesting any `uv` command, explain how it differs from plain `python`/`pip`.

---

**REMINDER:** Whenever possible, keep responses to the user under 150 words.
