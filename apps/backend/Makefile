# Testing commands
.PHONY: test test-unit test-integration test-cov test-watch test-failed test-debug

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-cov:
	uv run pytest --cov=app --cov-report=html --cov-report=term
	open htmlcov/index.html

test-watch:
	uv run pytest-watch

test-failed:
	uv run pytest --lf -v  # Run last failed tests

test-debug:
	uv run pytest -vv --pdb  # Drop into debugger on failure
