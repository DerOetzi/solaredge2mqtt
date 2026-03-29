---
description: 'Python coding conventions and guidelines'
applyTo: '**/*.py'
---

# Python Coding Conventions

## Python Instructions
- Ensure functions have descriptive names and include type hints.
- Use the `typing` module for type annotations (e.g., `List[str]`, `Dict[str, int]`).
- Break down complex functions into smaller, more manageable functions.
- All imports must be explicit; avoid wildcard imports
- All imports have to be at the top of the file, grouped by standard library, third-party, and local imports

## General Instructions

- Always prioritize readability and clarity.
- For algorithm-related code, make the approach clear through structure, naming, and small focused functions.
- Source code must be self-explanatory; do not use inline or block comments in source files.
- Handle edge cases and write clear exception handling.
- use always most significant exceptions. Avoid using generic exceptions like `Exception` or `BaseException` when possible.
- Make usage of libraries or external dependencies obvious from explicit naming and clear APIs.
- Use consistent naming conventions and follow language-specific best practices.
- Write concise, efficient, and idiomatic code that is also easily understandable.
- Coding: Follow SOLID, Clean Code, DRY, KISS, YAGNI.

## Code Style and Formatting

- Follow the **PEP 8** style guide for Python.
- Maintain proper indentation (use 4 spaces for each level of indentation).
- Ensure lines do not exceed 88 characters.
- Use blank lines to separate functions, classes, and code blocks where appropriate.
- Run pyright checks and ensure no type errors are present. Avoid ignore pragmas; if unavoidable in test files, document the reason in the test docstring.
- Use ruff for linting and ensure no linting errors are present.

## Edge Cases and Testing

- Always include test cases for critical paths of the application.
- Account for common edge cases like empty inputs, invalid data types, and large datasets.
- Cover edge cases with explicit test names and assertions that describe expected behavior.
- Write unit tests for functions and document them with docstrings explaining the test cases.
- All new code must be covered by unit tests located in the `tests/` directory.
