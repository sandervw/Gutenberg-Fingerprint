# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT:** Whenever possible, keep responses to the user under 150 words.

## Purpose

A learning project for **dbt Core + Fabric**. The domain (stylometric "fingerprints" of  gutenberg authors) is the vehicle; the goal is... {TODO - fill in from project doc}.

## Implementation docs

`docs\fabric_gutenberg_stylometrics_project.md` documents the project's finished design. Consult it as the reference.

Reference the past project for design choices related to dbt, python, or evidence: `C:\Users\Sander\OneDrive\Documents\Github\Fiction-Fingerprint`

## How we work

- The user is still learning, so **you are also the documentation**: explain what you're doing and why as you go, enough to follow without leaving the editor. No need to stop and wait for sign-off before each edit.
- **Just build it.** Batch related steps when it makes sense, then summarize what changed and why. Don't gate every command or file behind a separate approval.
- For a **significant or hard-to-reverse design/tech choice**, call out the options and your recommendation before committing to it. For small, reversible calls, pick a sensible default and note it.
- **Never rely on memory for code/tech specs.** Check the local refs in `docs/reference/` first (`dbt-core.md`, TODO - add fabric, cloudflare). If they don't cover it, fetch current docs (Context7 / official sources), then update/add the ref file. Keep these refs current.
- **Be lean.** Fewest words possible in chat and in prose docs. No extended justification, no restating known facts, no exhaustive examples.
- **Never stage or commit.** Don't run `git add`/`git commit` unless explicitly instructed; the user handles version control.

## Deployment

- The Evidence site (`reports/`) will be published to Cloudflare Pages at **TODO**.
- Styling mirrors the user's other site, **wordleaves.com** (see `reports/sparse.css` + `reports/wordleaves.css`: cream/charcoal, copper accent, iA Writer Quattro font).

## Environment

- Windows 11, bash terminal, VS Code. Python 3.14 and `uv` are installed.
- Before suggesting any `uv` command, explain how it differs from plain `python`/`pip`.

---

**REMINDER:** Whenever possible, keep responses to the user under 150 words.
