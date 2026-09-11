#!/usr/bin/env bash
# =============================================================================
# git-push.sh
#
# Pushes the current branch, then live-streams the CI run of the pushed commit.
#
# Usage:
#   make push                          # arguments go to `git push` via ARGS
#   make push ARGS="-u origin HEAD"    # first push of a new branch
# =============================================================================

set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT=$(git rev-parse HEAD)

# ── 1. Push (pass all original arguments straight through) ────────────────────
echo ""
echo "  Pushing branch '${BRANCH}' ..."
echo ""
git push "$@"

# ── 2. Auth guard ─────────────────────────────────────────────────────────────
if ! gh auth status &>/dev/null; then
  echo ""
  echo "  ✗ gh CLI not authenticated — cannot stream CI."
  echo "  Run once: gh auth login"
  echo ""
  exit 0
fi

# ── 3. Wait for GitHub to register the run of this commit (up to 30 s) ───────
# Filtered on the commit, not "latest run on the branch": for the first seconds
# after a push that is still the previous commit's run.
echo ""
echo "  Waiting for CI to start on commit ${COMMIT:0:7} ..."

TIMEOUT=30
ELAPSED=0
RUN_ID=""

while [[ $ELAPSED -lt $TIMEOUT ]]; do
  RUN_ID=$(gh run list --workflow=ci.yml --branch="$BRANCH" --limit=20 \
    --json databaseId,headSha \
    --jq "map(select(.headSha == \"${COMMIT}\")) | .[0].databaseId" 2>/dev/null || true)

  [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]] && break

  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "  No CI run for commit ${COMMIT:0:7} after ${TIMEOUT}s."
  echo "  CI runs on pull requests and on main/develop — is a PR open for '${BRANCH}'?"
  exit 0
fi

# ── 4. Live-stream the run ────────────────────────────────────────────────────
echo "  Streaming CI run #${RUN_ID} (Ctrl+C to detach) ..."
echo ""
gh run watch "$RUN_ID"
