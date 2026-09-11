# Contribuer à AgentLen

Le guide de contribution du projet est **[docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md)**. C'est le seul qui fait foi : flux de branches (`develop` → `main`), check requis `CI Passed`, commandes `make`, conventions de commit et de pull request.

Seule la section ci-dessous, sur le suivi de la CI dans le terminal, reste ici pour l'instant. N'ajoutez pas d'autre règle à ce fichier : modifiez `docs/CONTRIBUTING.md`.

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

Branches, commits, pull requests et CI : [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md).
