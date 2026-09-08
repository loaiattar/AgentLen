# =============================================================================
# Makefile — developer shortcuts
# Requires: gh CLI authenticated (gh auth login)
# =============================================================================

.PHONY: setup push ci ci-watch ci-logs help

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

## help: list available commands
help:
	@grep -E '^## ' Makefile | sed 's/## /  make /'
