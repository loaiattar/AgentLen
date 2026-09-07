#!/usr/bin/env bash
# =============================================================================
# ci-status.sh
#
# Shows the CI pipeline status for the branch you are currently on.
#
# Prerequisites:
#   gh CLI authenticated — run once: gh auth login
#
# Usage:
#   bash .github/scripts/ci-status.sh           # latest run on current branch
#   bash .github/scripts/ci-status.sh --watch   # live-stream the active run
# =============================================================================

set -euo pipefail

# ── Auth guard ────────────────────────────────────────────────────────────────
if ! gh auth status &>/dev/null; then
  echo ""
  echo "  ✗ Not authenticated. Run this once: gh auth login"
  echo ""
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
MODE="${1:-}"

case "$MODE" in

  # ── Live-stream the active run on the current branch ──────────────────────
  --watch)
    echo ""
    echo "  Watching CI for branch: ${BRANCH}"
    echo ""
    RUN_ID=$(gh run list --workflow=ci.yml --branch="$BRANCH" --limit=1 \
      --json databaseId --jq '.[0].databaseId')
    if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
      echo "  No CI runs found for branch '${BRANCH}'."
      exit 0
    fi
    gh run watch "$RUN_ID"
    ;;

  # ── Default: show status of the latest run on the current branch ──────────
  *)
    echo ""
    echo "  ── CI Status: ${BRANCH} ── $(date '+%Y-%m-%d %H:%M:%S') ──"
    echo ""
    gh run list --workflow=ci.yml --branch="$BRANCH" --limit=5 \
      --json status,conclusion,displayTitle,updatedAt,databaseId \
      --template \
'{{range .}}  {{if eq .conclusion "success"}}✅{{else if eq .conclusion "failure"}}❌{{else if eq .conclusion "cancelled"}}⚪{{else}}🔄{{end}}  {{.displayTitle | printf "%-50s"}}  {{.conclusion | printf "%-10s"}}  {{.updatedAt}}
{{end}}'
    echo ""
    echo "  Tip: make ci-watch   →  live-stream the active run"
    echo ""
    ;;
esac
