# =============================================================================
# Makefile — developer shortcuts
# Requires: gh CLI authenticated (gh auth login)
# =============================================================================

.PHONY: setup push ci ci-watch ci-logs lint format test test-all help

## setup: one-time install — makes `git push` auto-stream CI (run after cloning)
setup:
	@bash .github/scripts/install-hooks.sh

## push: push current branch and live-stream CI (fallback if setup wasn't run)
push:
	@bash .github/scripts/git-push.sh

## ci: show CI status for your current branch
ci:
	@bash .github/scripts/ci-status.sh

## ci-watch: live-stream the active pipeline run on your current branch
ci-watch:
	@bash .github/scripts/ci-status.sh --watch

## ci-logs: view full logs for a specific run  →  make ci-logs RUN=<id>
ci-logs:
	@gh run view $(RUN) --log

## lint: run every blocking quality gate, exactly as CI does
lint:
	ruff format --check .
	ruff check .
	mypy --strict src/agentlen/domain src/agentlen/application src/agentlen/infrastructure/ai
	lint-imports

## format: apply formatting and the safe lint fixes
format:
	ruff format .
	ruff check . --fix

## test: unit tests only — no database, no Docker, no API key
test:
	pytest tests/unit -q

## test-all: every test, including integration and e2e (needs Docker)
test-all:
	pytest -q

## help: list available commands
help:
	@grep -E '^## ' Makefile | sed 's/## /  make /'
