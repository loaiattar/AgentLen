# Contributing — Team Workflow

This document describes the end-to-end workflow every team member must follow.

---

## Branch Protection (main)

| Rule | Setting |
|------|---------|
| Required approvals | **1** peer review |
| Required status checks | `Lint`, `Test`, `Build`, `CI Passed` |
| Dismiss stale reviews | ✅ Yes |
| Require code owner review | ✅ Yes (see [CODEOWNERS](CODEOWNERS)) |
| Force pushes | ❌ Blocked |
| Branch deletion | ❌ Blocked |
| Require conversation resolution | ✅ Yes |

---

## Development Workflow

```
1. Create a GitHub Issue on the project board
       └── Assign it to a team member
       └── The issue number becomes part of your branch name

2. Create the feature branch from the issue
       (GitHub can do this automatically via "Create a branch" on the issue page)
       Branch naming convention: <issue-number>-<short-description>
       Example: 1-configure-workflow

3. Fetch and checkout the branch locally
       git fetch origin
       git checkout <branch-name>

4. Make changes, commit with a descriptive message
       git add .
       git commit -m "feat: describe what you did"

5. Push to GitHub
       git push origin <branch-name>

6. Open a Pull Request targeting `main`
       - Fill in the PR description
       - Link the issue (e.g., "Closes #1")
       - CI will run automatically

7. Get 1 peer review + all CI checks green → Merge
```

---

## CI Pipeline

The CI workflow (`.github/workflows/ci.yml`) runs on every PR and push to `main`:

```
Lint → Test → Build → CI Passed (gate)
```

All four checks must be green before a PR can be merged.

---

## First-Time Repository Setup (Admin only)

### 1 — Apply branch protection

```bash
export GITHUB_TOKEN="ghp_your_classic_token_with_repo_scope"
bash .github/scripts/setup-branch-protection.sh
```

### 2 — Add team collaborators

Edit `.github/scripts/add-collaborators.sh` and replace the placeholder
GitHub usernames with your 7 teammates' actual handles, then run:

```bash
export GITHUB_TOKEN="ghp_your_classic_token_with_repo_scope"
bash .github/scripts/add-collaborators.sh
```

Each collaborator will receive a GitHub invitation email granting **Write**
access to the repository.

### 3 — Grant Project Board Write access

GitHub Projects (v2) access is separate from repo access:

1. Go to **github.com → Your profile → Projects** (or the organisation URL).
2. Open the project → **Settings → Manage access**.
3. Add each collaborator with the **Write** role.

---

## Terminal CI Streaming (required setup for everyone)

Run these **two commands once** after cloning the repo:

```bash
# 1. Authenticate the GitHub CLI
gh auth login
# Choose: GitHub.com → HTTPS → Login with a web browser

# 2. Install the push hook (makes `git push` auto-stream CI)
make setup
```

After that, **`git push` does everything automatically**:

```
$ git push

  Pushing branch 'my-feature' ...

  Waiting for CI to start on 'my-feature' ...
  Streaming CI run #42 (Ctrl+C to detach) ...

  ✔ Lint    ✔ Test    ✔ Build    ✔ CI Passed
```

### Other useful commands

| Command | What it does |
|---|---|
| `make ci` | Show CI status for your current branch |
| `make ci-watch` | Live-stream the latest run on your current branch |
| `make push` | Same as `git push` (fallback if setup wasn’t run) |
| `make ci-logs RUN=<id>` | Full logs for a specific run ID |

### Uninstall the hook

```bash
git config --local --unset alias.push
```

---

## Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `chore:` | Maintenance / tooling |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `ci:` | CI/CD changes |
| `refactor:` | Code change with no behaviour change |
