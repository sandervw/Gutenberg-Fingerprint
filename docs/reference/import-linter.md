# Import Linter reference

Verified against import-linter 2.16.

- Config lives in `pyproject.toml` under `[tool.importlinter]`; contracts are `[[tool.importlinter.contracts]]` tables.
- `root_package = "python"` works for this repo's namespace package. Run from the repo root so `python` is importable.
- `include_external_packages = true` lets a `forbidden` contract list external and standard-library modules such as `requests` or `subprocess`. External packages are not analyzed, so imports made inside them do not count.
- A `forbidden` contract also catches indirect imports: `core -> storage -> duckdb` breaks it.
- Run: `uv run --frozen lint-imports`. A non-zero exit means a contract is broken.
