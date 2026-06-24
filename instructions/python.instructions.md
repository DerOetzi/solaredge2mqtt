---
description: 'Python coding conventions and guidelines'
applyTo: '**/*.py'
---

# Python Coding Conventions

> This file is an additional copy for reference; the Copilot-applied canonical instructions live at
> [`.github/instructions/python.instructions.md`](../.github/instructions/python.instructions.md).
> Project-specific constraints are documented in [AGENTS.md](../AGENTS.md).

## Python Instructions

- Ensure functions have descriptive names and include type hints.
- Use built-in generic types for annotations (`list[str]`, `dict[str, int]`, `tuple[int, ...]`);
  use `typing` only for `Optional`, `Union`, `Any`, `Callable`, `TypeVar`, `Protocol`, etc.
- Break down complex functions into smaller, more manageable functions.
- All imports must be explicit; avoid wildcard imports.
- All imports must be at the top of the file, grouped: standard library → third-party → local.

## General Instructions

- Always prioritize readability and clarity.
- Source code must be self-explanatory; do not use inline or block comments in source files.
- Handle edge cases and write clear exception handling.
- Use always the most specific exceptions; avoid `Exception` or `BaseException` when possible.
- Make usage of libraries obvious from explicit naming and clear APIs.
- Use consistent naming conventions and follow language-specific best practices.
- Write concise, efficient, and idiomatic code.
- Coding: Follow SOLID, Clean Code, DRY, KISS, YAGNI.

## Code Style and Formatting

- Follow **PEP 8**; 4-space indentation; maximum line length **88 characters**.
- Use blank lines to separate functions, classes, and code blocks where appropriate.
- Run `pyright` checks; no type errors. Avoid `# type: ignore` (document reason in docstring
  if unavoidable in test files).
- Use `ruff` for linting; no linting errors.

## Edge Cases and Testing

- Always include test cases for critical paths.
- Account for common edge cases: empty inputs, invalid data types, large datasets.
- Cover edge cases with explicit test names and assertions that describe expected behavior.
- Write unit tests for functions; document them with docstrings explaining the test cases.
- All new code must be covered by unit tests in `tests/`.
