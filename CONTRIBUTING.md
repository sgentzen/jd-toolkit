# Contributing to jd-toolkit

Thanks for your interest in contributing! Here's how to get started.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) to manage the development
environment. `uv sync` creates `.venv` and installs the exact versions pinned in
`uv.lock`, which is the same set CI runs against.

```bash
git clone https://github.com/sgentzen/jd-toolkit.git
cd jd-toolkit
uv sync --all-extras
```

If you change anything under `[project.dependencies]` or
`[project.optional-dependencies]`, regenerate the lock and commit it alongside
the change:

```bash
uv lock
```

## Development workflow

1. Create a branch for your change
2. Make your changes
3. Run the checks:

```bash
uv run pytest         # tests
uv run ruff check .   # linting (src/ and tests/)
uv run ruff format .  # formatting
uv run mypy src/      # type checking
```

4. Open a pull request

## Code style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Type hints are required on all public functions (mypy strict mode)
- Docstrings on all public classes and methods

## Adding a new module

1. Create a new file in `src/jd_toolkit/`
2. Implement your job-description text utilities with clear, tested functions
3. Add type hints and docstrings to all public functions and classes
4. Add tests in `tests/`
5. Re-export from `src/jd_toolkit/__init__.py` if appropriate

## Releasing

Maintainers: see [docs/releasing.md](docs/releasing.md). Releases publish to
PyPI from a GitHub Release via Trusted Publishing; pushing a tag alone does not
publish anything.

## Reporting issues

Open an issue at https://github.com/sgentzen/jd-toolkit/issues with:
- What you expected to happen
- What actually happened
- Steps to reproduce
