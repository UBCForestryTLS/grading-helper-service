# Design Decisions

---

## UV Package Manager

We use [UV](https://docs.astral.sh/uv/) for dependency management instead of pip or Poetry.

**Why?** UV is 10-100x faster (written in Rust), provides a lock file for reproducibility, and handles venv + dependencies in one tool. Backed by Astral (creators of Ruff).

---

## Ruff

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting instead of flake8, pylint, isort, or black.

**Why?** Ruff replaces multiple tools in one, is 10-100x faster (written in Rust), and provides consistent linting + formatting. Also from Astral, so pairs well with UV.

---

