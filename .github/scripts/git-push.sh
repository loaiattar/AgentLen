#!/usr/bin/env bash
# =============================================================================
# git-push.sh
#
# Drop-in wrapper for `git push`.
# Pushes the current branch, then immediately live-streams the CI run.
#
# Installed automatically by: bash .github/scripts/install-hooks.sh
# After installation, `git push` calls this script transparently.
# =============================================================================

set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)

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

# ── 3. Wait for GitHub to register the new run (up to 30 s) ──────────────────
echo ""
echo "  Waiting for CI to start on '${BRANCH}' ..."

TIMEOUT=30
ELAPSED=0
RUN_ID=""

while [[ $ELAPSED -lt $TIMEOUT ]]; do
  RUN_ID=$(gh run list --workflow=ci.yml --branch="$BRANCH" --limit=1 \
    --json databaseId,createdAt --jq '.[0].databaseId' 2>/dev/null || true)

  [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]] && break

  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "  CI run not detected after ${TIMEOUT}s — check GitHub Actions manually."
  exit 0
fi

# ── 4. Live-stream the run ────────────────────────────────────────────────────
echo "  Streaming CI run #${RUN_ID} (Ctrl+C to detach) ..."
echo ""
gh run watch "$RUN_ID"
