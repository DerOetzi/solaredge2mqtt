# Claude Code Instructions

See [AGENTS.md](AGENTS.md) for full project context and conventions — read it before
non-trivial code changes; it is not auto-loaded, this file only points to it.

## Critical rules (violating these is a hard error, not a style nit)

- **No comments in source code** — inline or block. Code must be self-explanatory
  through naming. Docstrings on tests are fine (required, see below); `#` comments
  are not, anywhere in `*.py`.
- All code and docs in **English**.
- Type hints on all functions; built-in generics (`list[str]`, `dict[str, int]`),
  not `typing.List`/`typing.Dict`.
- No wildcard imports; imports at top, grouped stdlib → third-party → local.
- Most specific exception type possible; avoid bare `Exception`/`BaseException`.
- `ruff check` and `pyright` must both be clean before considering work done.
- New code needs tests in `tests/`; minimum coverage 90% (`pytest --cov=solaredge2mqtt`).
- Never commit secrets; sensitive data stays out of logs.
