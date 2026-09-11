#!/usr/bin/env bash
# =============================================================================
# install-hooks.sh
#
# One-time setup for every collaborator: checks the GitHub CLI that
# `make push`, `make ci` and `make ci-watch` rely on.
#
# It used to register git-push.sh as a local `push` alias. Git never runs an
# alias that has the name of a built-in command, so that alias did nothing;
# it is removed here where an earlier `make setup` left it.
#
# Usage (run once after cloning):
#   make setup
# =============================================================================

set -euo pipefail

# ── Sanity checks ─────────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
  echo "  ✗ GitHub CLI (gh) is not installed."
  echo "  Install it from: https://cli.github.com"
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo ""
  echo "  ✗ gh CLI not authenticated."
  echo "  Run first: gh auth login"
  echo ""
  exit 1
fi

# ── Remove the alias git always ignored ──────────────────────────────────────
if git config --local --get alias.push &>/dev/null; then
  git config --local --unset alias.push
  echo "  Removed the old \`push\` alias (git never used it)."
fi

echo ""
echo "  ✅ Done. Push with \`make push\` to push your branch and stream its CI run"
echo "     in your terminal. \`git push\` stays plain git."
echo ""
