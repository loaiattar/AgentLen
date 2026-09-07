#!/usr/bin/env bash
# =============================================================================
# install-hooks.sh
#
# One-time setup for every collaborator.
# Registers git-push.sh as the local git `push` alias so that
# `git push` automatically streams CI after every push.
#
# Usage (run once after cloning):
#   bash .github/scripts/install-hooks.sh
# =============================================================================

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
WRAPPER="${REPO_ROOT}/.github/scripts/git-push.sh"

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

# ── Make the wrapper executable ───────────────────────────────────────────────
chmod +x "$WRAPPER"

# ── Register as the local git push alias ─────────────────────────────────────
# Uses --local so it only affects this repo, not the user's global git config.
git config --local alias.push "!bash ${WRAPPER}"

echo ""
echo "  ✅ Done. From now on, \`git push\` in this repo will:"
echo "     1. Push your branch to GitHub"
echo "     2. Automatically stream the CI pipeline in your terminal"
echo ""
echo "  To uninstall: git config --local --unset alias.push"
echo ""
