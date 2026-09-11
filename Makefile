# =============================================================================
# Makefile — developer shortcuts
# Requires: gh CLI authenticated (gh auth login)
# =============================================================================

# Invoked with -f/--project-directory rather than a bare `docker compose`, so
# relative paths in docker/docker-compose.yml (build context, env_file) always
# resolve against the repo root regardless of the caller's cwd (#60).
COMPOSE = docker compose -f docker/docker-compose.yml --project-directory .

.PHONY: setup push ci ci-watch ci-logs lint format test test-all help \
	up down migrate seed logs

## setup: one-time check of the gh CLI used by push, ci and ci-watch (run after cloning)
setup:
	@bash .github/scripts/install-hooks.sh

## push: push current branch and live-stream the CI run of that commit  →  make push ARGS="-u origin HEAD"
push:
	@bash .github/scripts/git-push.sh $(ARGS)

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
	mypy --strict src/agentlen
	lint-imports

## format: apply formatting and the safe lint fixes
format:
	ruff format .
	ruff check . --fix

## test: unit tests and the contract suite — the SQL half needs a database, and skips without one
test:
	pytest tests/unit tests/contract -q

## test-all: every test, including integration and e2e (needs Docker or TEST_DATABASE_URL)
test-all:
	pytest -q

## up: start db + api + worker + frontend (http://localhost:8080), building images if needed
up:
	@$(COMPOSE) up --build -d

## down: stop the compose stack
down:
	@$(COMPOSE) down

## migrate: apply Alembic migrations inside the running api container
migrate:
	@$(COMPOSE) exec api alembic upgrade head

## seed: create the TraceLab source + mapping and import the sample file (#60)
seed:
	@$(COMPOSE) exec api python -m agentlen.interfaces.cli seed

## logs: follow logs for the whole compose stack
logs:
	@$(COMPOSE) logs -f

## help: list available commands
help:
	@grep -E '^## ' Makefile | sed 's/## /  make /'
