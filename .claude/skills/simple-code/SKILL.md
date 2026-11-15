---
name: simple-code
description: Guiding principles for writing, refactoring, or reviewing code in any language. Seven simplicity practices plus house rules, with hard checks. Use for every code change.
---

# Simple code

Follow the house rules always. Apply the seven practices with judgment, and respect each "not when" note. [examples-python.md](examples-python.md) and [examples-typescript.md](examples-typescript.md) show a before/after of each practice.

## Workflow

1. Read the relevant practices before writing code.
2. A hook checks every file you edit. Fix every FAIL it reports before moving on.
3. Before finishing, run `python .claude/skills/simple-code/scripts/check_code.py <changed paths>` and get PASS. Then `simplicity-reviewer` reviews the PR (see `CLAUDE.md`).

## House rules (hard pass/fail)

- Every comment, docstring, and doc comment is 12 words or fewer. No exceptions.
- Each public function, class, and exported object has exactly one short doc comment in the language's own form (docstring, `/** */`, `///`, and so on).
- Names use full words. Only `id`, `url`, `api` may be short; `self` and `_` are allowed. No `i`, `e`, `cls`, `df`, `cfg`, `args`, or similar. Framework conventions are not exempt. Import libraries under full names.
- Code files stay under 300 lines where possible; past that, consider splitting (warning).
- User-facing Markdown stays under 700 words where possible; past that, consider splitting (warning).

## Python rules (hard pass/fail, enforced by `ruff.toml`)

- `from __future__ import annotations` is the first import; imports group standard library, third-party, then local.
- Every parameter and return value has a type annotation.
- No mutable defaults, wildcard imports, `%` or `.format()` strings, or `open()` outside `with`.
- Data-only objects are `dataclasses` or `NamedTuple`.
- Every `except` names a specific exception type.

## The seven practices

**1. Push side effects to the edges.** Gather inputs, decide in pure functions, then act on the result. Pass the clock, randomness, and data in as arguments. Pure logic lives in a `core/` folder, where I/O, network, logging, clock reads, and randomness are a hard FAIL. *Not when:* data is too large to load first; stream it instead.

**2. Avoid hasty abstractions.** Tolerate small duplication until the shared pattern is clear. Never add a flag or branch to a shared function for one caller; split it instead. *Not when:* the duplicated code is a rule that must change everywhere at once.

**3. Build deep modules.** Each module hides a lot behind a small interface. Callers should never need to call steps in a set order. Delete pass-through functions. Prefer behaviour that handles edge cases over raising for them. *Not when:* splitting would force two modules to change together.

**4. Keep behaviour local.** A reader should understand a unit by reading it. Call steps directly and in order; avoid registries, import-order effects, mutating decorators, and global state. *Not when:* the indirection is a real plugin point the project needs.

**5. Make state explicit and parse at the boundary.** Replace clusters of booleans or status strings with one enum. Parse raw input once, into typed, immutable objects, at the system edge. *Not when:* a state is unwanted but legal; keep it representable and give it its own value.

**6. Flatten control flow.** Use guard clauses for edge cases, keep nesting to three levels, and name each part of a compound condition. *Not when:* an early return would skip cleanup; use `with`, `using`, `defer`, or `finally`.

**7. Write boring code that fails loudly.** Prefer plain code to clever code. Never swallow exceptions or errors, or fall back silently. Fail with a message that names the bad value. No empty error handlers.

## When rules conflict

House rules beat practices. Between practices, keep the interface small (3) and the sequence of operations visible (4). Extract a function only when it hides real complexity or isolates state.

## Language packs

The checker fully covers Python (with `ruff.toml`) and TypeScript or JavaScript (with `eslint.config.mjs`). Other code files get only the file-length warning, and `simplicity-reviewer` judges the rest. When a project adopts another language, add a pack at kickoff:

1. A linter config in this folder mapping practices 2, 4, 5, 6, and 7 to that language's linter, as `ruff.toml` does.
2. A `scripts/<language>_rules.py` with comment-length, doc-comment, naming, and core-purity checks, shaped like `typescript_rules.py`, dispatched from `check_file` in `check_code.py`.
3. The language's suffixes moved out of `OTHER_CODE_SUFFIXES` in `rules.py`.
