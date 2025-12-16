.PHONY: test test-cov lint format docs-serve docs-build

test:
	uv run pytest

test-cov:
	uv run pytest --cov --cov-report=html

lint:
	uv run ruff check src

format:
	uv run ruff format src

docs-serve:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build