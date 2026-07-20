.PHONY: test test-unit test-contract test-flow test-integration test-e2e test-pr coverage lint

PYTEST := uv run pytest

test: test-unit test-contract test-flow

test-unit:
	$(PYTEST) tests/unit -q

test-contract:
	$(PYTEST) tests/contracts -q

test-flow:
	$(PYTEST) tests/flows -q

test-integration:
	$(PYTEST) tests/integration -q -m "integration and not quarantine"

test-e2e:
	$(PYTEST) tests/e2e -q

test-pr:
	$(PYTEST) tests/unit tests/contracts tests/flows -q

coverage:
	$(PYTEST) tests/unit tests/contracts tests/flows --cov=forge --cov-branch --cov-report=term-missing --cov-report=xml

lint:
	uv run ruff check src
	uv run ruff format --check src
