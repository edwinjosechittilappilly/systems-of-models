.PHONY: help sync lint format test test-bench test-live check build hygiene clean

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

sync: ## install the package and dev tools into .venv
	uv sync

lint: ## ruff lint + format check + mypy
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

format: ## apply ruff fixes and formatting
	uv run ruff check --fix .
	uv run ruff format .

test: ## offline tests (no API calls)
	uv run pytest -m "not live"
	uv run som check-schemas

test-bench: ## offline tests for the experiment harness (bench/); replays caches, no API calls
	uv run --group bench pytest -q bench/tests

test-live: ## tests that call real APIs; needs keys in .env
	uv run --env-file .env pytest -m live

check: lint test ## everything CI runs except hygiene and build

hygiene: ## pre-commit hooks on the whole tree (whitespace, JSON/YAML, ruff, gitleaks, actionlint)
	uvx pre-commit run --all-files

build: ## sdist + wheel into dist/
	rm -rf dist
	uv build

clean:
	rm -rf dist .pytest_cache .mypy_cache .ruff_cache
