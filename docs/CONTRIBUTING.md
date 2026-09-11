# Conventions de travail — AgentLen

> Ce document est **contraignant** pour tous les membres de l'équipe. Il est court volontairement : ce qui n'est pas écrit ici ne s'invente pas en cours de route, ça se discute et ça s'ajoute par PR.
>
> C'est le **seul guide de contribution** du dépôt : `.github/CONTRIBUTING.md` ne fait que renvoyer ici.

---

## 0. Pourquoi ces règles

Trois raisons, dans cet ordre :

1. **On travaille à plusieurs en parallèle sur 4 jours.** Sans convention, on passe le jour 4 à résoudre des conflits au lieu de livrer.
2. **Le suivi GitHub est noté** (3 points sur 20) : issues, tableau, revues de PR. Le tableau doit refléter le travail réel, pas être rempli la veille du rendu.
3. **L'architecture est notée 7 points sur 20.** La revue de PR est notre seul filet de sécurité contre la dérive architecturale.

---

## 1. Modèle de branches

**Tout le travail passe par `develop` ; `main` ne reçoit que les releases.**

```
main     ──●─────────────────────────────●──►  releases, taguées (v0.1.0…)
            \                           /
develop  ────●─────●────────●──────────●───►  branche par défaut, intégration
              \   /          \        /
               ●─●            ●──●───●
     149-fixsecurity-…        198-docs-…
```

`develop` est la branche par défaut du dépôt : chaque branche d'issue en part et y revient par pull request. `main` n'avance que par une PR `develop` → `main`, au moment d'une release (§10).

### Règles

`develop` et `main` sont protégées par le même ruleset GitHub.

| Règle | Détail |
|---|---|
| Aucun push direct sur `develop` ni `main` | Tout passe par une PR : 1 approbation et le check `CI Passed` vert. Un nouveau push annule les approbations déjà données. |
| Ni force-push ni suppression | Refusés sur `develop` et `main`. |
| `develop` est toujours verte | Si la CI casse sur `develop`, c'est la priorité absolue de tout le monde. |
| Une branche = une issue | Pas de branche fourre-tout, pas de branche partagée entre deux personnes. |
| Durée de vie < 1 jour | Au-delà, la branche diverge trop. Découpe l'issue. |
| On resynchronise souvent | Sur `origin/develop`, au moins une fois par jour (§5). |

### Nommage

La branche se crée depuis l'issue : bouton **Create a branch** de GitHub, base `develop`. GitHub la nomme `<numéro-issue>-<titre-de-l-issue>`. Le nommage manuel `<type>/<numéro-issue>-<slug-court>` est aussi en usage. Dans les deux cas, le numéro d'issue figure dans le nom.

```
149-fixsecurity-cle-api-cote-proxy
156-suite-de-tests-fiable
fix/143-operator-validation-target-schema
feat/31-ia-assistant-mapping
```

Types autorisés : `feat` · `fix` · `docs` · `refactor` · `test` · `chore` · `ci` · `perf`

---

## 2. Commits

**Conventional Commits**, messages **en français** ; le code, les identifiants et les commentaires restent en anglais.

```
<type>(<scope>): <description à l'impératif, minuscule, sans point final>

[corps optionnel : le POURQUOI, pas le QUOI]

Refs #12
```

### Scopes

Ils suivent l'architecture — c'est volontaire, ça rend visible dans `git log` quelle couche bouge :

La couche (`domain` · `application` · `infra` · `api` · `db` · `ai`) ou la zone fonctionnelle touchée (`mapping` · `import` · `files` · `auth` · `front/<feature>`), plus `docs` · `ci` · `tests` · `deps`.

`Closes #12`, dans le commit ou la PR, ferme l'issue à la fusion dans `develop`, qui est la branche par défaut.

### Exemples

```
feat(domain): ajoute l'opérateur unit_convert au moteur de transformation

Les traces TraceLab expriment les latences en secondes alors que le modèle
cible stocke des millisecondes. Sans cet opérateur, le mapping devrait
encoder la conversion en dur.

Refs #23
```

```
fix(db): empêche le doublon de session au réimport

La contrainte UNIQUE portait sur external_id seul, ce qui échouait dès que
deux sources utilisaient le même identifiant. Elle porte maintenant sur
(data_source_id, external_id).

Closes #28
```

```
docs(architecture): ADR-006 sur l'interchangeabilité du fournisseur IA
```

### Ce qu'on ne veut pas voir

`update`, `fix bug`, `wip`, `asdf`, `commit du soir`, ou un commit de 40 fichiers touchant 5 couches.

> Le nombre de commits n'est pas noté. Leur lisibilité, si — indirectement, via la capacité d'un correcteur à comprendre qui a fait quoi.

---

## 3. Issues et GitHub Projects

**Aucun travail ne commence sans issue.** C'est la règle qui coûte le plus au début et qui sauve le plus à la fin.

### Une issue correcte contient

- [ ] Un **titre à l'impératif** : « Implémenter le profilage Polars des fichiers CSV »
- [ ] Un **responsable** (assignee) — une seule personne
- [ ] Un **résultat attendu vérifiable** : comment sait-on que c'est fini ?
- [ ] Un **label de lot** : `lot-a-domaine`, `lot-b-persistance`, `lot-c-ingestion`, `lot-d-ia`, `lot-e-api`, `lot-f-metriques`
- [ ] Une **estimation grossière** : `taille-s` (< 2 h), `taille-m` (½ journée), `taille-l` (1 journée — à découper si possible)

### Colonnes du tableau

| Colonne | Signification | Condition d'entrée |
|---|---|---|
| **Backlog** | Identifié, pas encore prêt | — |
| **Prêt** | Assez spécifié pour démarrer | Responsable + résultat attendu écrits |
| **En cours** | Quelqu'un travaille dessus | Branche créée · **max 1 issue en cours par personne** |
| **En revue** | PR ouverte | CI verte + PR liée à l'issue |
| **Terminé** | Fusionné dans `develop` | PR mergée, issue fermée automatiquement |

**On déplace la carte au moment où ça se passe, pas le vendredi.** Le tableau est une trace de travail, pas un livrable rétroactif — et ça se voit.

### Definition of Done

Une issue n'est terminée que si **tout** est vrai :

- [ ] Le code fait ce que l'issue demandait
- [ ] Les tests associés existent et passent
- [ ] Le check `CI Passed` est vert (§8)
- [ ] La doc impactée est à jour (architecture, API, ADR)
- [ ] La PR a été relue et approuvée par **un autre membre**
- [ ] Rien n'est cassé sur `develop` après le merge

---

## 4. Pull requests

La PR cible **`develop`** (seule la PR de release cible `main`). Sa description suit le gabarit [`.github/pull_request_template.md`](../.github/pull_request_template.md), prérempli à l'ouverture : ce que fait la PR et pourquoi, `Closes #`, type, couches touchées, comment vérifier, checklist auteur, points d'attention pour le relecteur.

### Règles

| Règle | Pourquoi |
|---|---|
| **1 approbation obligatoire** avant merge | Exigence du sujet, et vrai filet anti-dérive ; imposée par le ruleset |
| **Jamais s'auto-approuver ni s'auto-merger** | Même règle pour tout le monde, y compris qui a créé le dépôt |
| **PR liée à une issue** (`Closes #12`) | Sinon l'issue reste ouverte et le tableau ment |
| **Check `CI Passed` vert obligatoire** | Seul check requis par le ruleset ; il agrège tous les jobs de la CI (§8) |
| **< 400 lignes modifiées** (indicatif) | Au-delà, la revue devient du survol et ne sert plus à rien |
| **Fusion par merge commit** | Pratique du dépôt (« Merge pull request #… ») ; le ruleset accepte aussi squash et rebase |
| **Branche supprimée après merge** | Automatique (réglage du dépôt) : la liste des branches reste lisible |

### Délai de revue

**Une PR ouverte doit être relue dans les 4 heures ouvrées.** Sur un sprint de 4 jours, une PR qui dort une journée bloque tout le monde. Si personne ne répond, on relance directement — ce n'est pas impoli, c'est le fonctionnement attendu.

### Ce qu'on regarde en revue

Dans cet ordre de priorité, parce que c'est l'ordre du barème :

1. **Sens des dépendances.** `domain/` importe-t-il quelque chose qu'il ne devrait pas ? Un use case connaît-il SQLAlchemy ? Si `import-linter` passe mais que ça sent le contournement, on le dit.
2. **Les règles métier sont-elles testables sans base ni IA ?** Si un test a besoin d'une clé API pour tourner, c'est un défaut d'architecture, pas un détail.
3. **Aucun identifiant de modèle en dur.** `"claude-opus-4-8"` dans le code = refus immédiat, ça vient de la configuration.
4. **Aucun secret.** Clé, jeton, mot de passe, URL avec identifiants : refus immédiat.
5. **Une valeur absente n'est jamais devenue un zéro.** `or 0`, `fillna(0)`, `COALESCE(x, 0)` sur une métrique : à justifier ou à corriger.
6. **Les tests couvrent-ils le cas qui échoue**, pas seulement le cas nominal ?
7. Lisibilité, nommage, cohérence avec le code existant.

### Comment on formule une remarque

- Distinguer ce qui bloque de ce qui est un avis. Préfixer les remarques non bloquantes par **`nit:`**.
- Critiquer le code, jamais la personne.
- Une remarque doit être **actionnable** : dire ce qui ne va pas *et* proposer une direction.
- Un désaccord qui dure plus de deux allers-retours en commentaires se règle de vive voix, puis se consigne en commentaire pour laisser la trace.

---

## 5. Synchronisation

```bash
# Démarrer une tâche : branche créée depuis l'issue (Create a branch, base develop)
git fetch origin
git switch 12-importer-jsonl

# … ou créée à la main
git switch develop
git pull origin develop
git switch -c feat/12-import-jsonl

# Se resynchroniser en cours de route (au moins 1×/jour)
git fetch origin
git rebase origin/develop

# Publier (ou `make push`, qui pousse et suit la CI dans le terminal, §8)
git push -u origin feat/12-import-jsonl
```

**Tant que la branche n'est pas relue, on la rebase sur `origin/develop`.** L'historique reste lisible et la PR ne se remplit pas de commits de merge parasites. **Une fois la revue commencée**, on fusionne plutôt `origin/develop` dans la branche (`git merge origin/develop`), ce qui évite de réécrire ce que le relecteur a déjà vu.

**On ne force-push jamais sur une branche relue par quelqu'un d'autre** sans le prévenir. Sur sa propre branche non encore relue, `git push --force-with-lease` (jamais `--force` seul).

**En cas de conflit :** c'est à l'auteur de la branche de le résoudre, pas au relecteur ni au dernier qui merge.

---

## 6. Rythme d'équipe

| Moment | Quoi |
|---|---|
| **Matin, 10 min** | Point debout : ce que j'ai fini, ce que je prends, ce qui me bloque. On met le tableau à jour **pendant** le point. |
| **En continu** | On intègre dès qu'une tranche est fonctionnelle. Pas de « je merge tout vendredi ». |
| **Fin de journée** | Toute branche en cours est poussée, même incomplète (PR en *draft*). Une machine qui plante ne doit pas coûter une journée à l'équipe. |
| **Fin de journée** | `develop` doit être verte et démontrable. |

**Anti-pattern à éviter absolument :** quatre personnes qui travaillent 3 jours en isolation et intègrent le jeudi soir. C'est le scénario d'échec le plus courant sur ce type de sprint.

---

## 7. Structure du dépôt

```
.
├── src/agentlen/            # code applicatif (voir docs/architecture/)
├── tests/{unit,contract,integration,e2e}/
├── frontend/                # interface React + Vite
├── alembic/                 # migrations
├── docker/                  # Dockerfiles, nginx, docker-compose.yml
├── data/samples/            # échantillon TraceLab importé par `make seed`
├── docs/
│   ├── CONTRIBUTING.md      # ce document
│   ├── datasets.md          # provenance des jeux de données
│   ├── architecture/        # architecture, modèle de données, ADR, contrat d'API
│   └── sujet/               # énoncé de référence
├── .github/                 # workflow CI, gabarits d'issue et de PR, scripts de `make setup`/`make ci`
├── Makefile                 # raccourcis (§8)
├── LICENSE                  # MIT
└── README.md
```

**Le code source ne va jamais à la racine.** La documentation ne va jamais ailleurs que dans `docs/`.

---

## 8. Qualité — ce que la CI vérifie à chaque PR

La CI (`.github/workflows/ci.yml`) tourne sur chaque PR et chaque push sur `develop` et `main`. Ses jobs tournent en parallèle ; le job **`CI Passed`** échoue si l'un d'eux n'a pas réussi, y compris s'il a été sauté ou annulé. **C'est le seul check requis** par la protection de `develop` et de `main`.

| Étape | Outil | Bloquant |
|---|---|---|
| Dépendances | `uv lock --check` : `uv.lock` correspond à `pyproject.toml` ; les jobs installent par `uv sync --frozen --extra dev` | oui |
| Format et lint | `ruff format --check .`, `ruff check .` | oui |
| Typage | `mypy --strict src/agentlen` : tout le paquet, `interfaces/` compris | oui |
| **Règle de dépendance** | `lint-imports` (import-linter) | **oui** |
| Tests sans base | `pytest tests/unit tests/contract` | oui |
| Migrations | `alembic upgrade head`, `downgrade base`, `upgrade head` sur Postgres 16 | oui |
| Tests avec base | `pytest tests/integration tests/e2e tests/contract` ; un test sauté fait échouer le job | oui |
| Secrets et modèles | `gitleaks` ; aucun identifiant de modèle IA en dur dans `src/` ni `frontend/src/` | oui |
| Frontend | `npm run lint`, `npm run build`, `npm test` dans `frontend/` | oui |
| Images Docker (`images`) | Construction de `docker/Dockerfile` et `docker/frontend.Dockerfile`, versions de Node et de uv alignées sur la CI | oui |

`import-linter` est notre garde-fou architectural : il fait échouer toute PR où `domain/` importerait `sqlalchemy`, `fastapi`, `polars` ou un SDK IA. **Si tu es tenté de désactiver cette règle, ouvre une discussion — ne la contourne pas.**

### Avant de pousser

Hors conteneur : Python ≥ 3.12 et Node ≥ 22.22.2 (prérequis détaillés dans le [README](../README.md)). Installation : `uv sync --frozen --extra dev` à la racine (versions de `uv.lock`, comme la CI ; `pip install -e ".[dev]"` fonctionne aussi), `npm ci` dans `frontend/`.

```bash
make format    # ruff format . puis ruff check . --fix
make lint      # ruff format --check, ruff check, mypy --strict src/agentlen, lint-imports : comme la CI
make test      # pytest tests/unit tests/contract (la moitié SQL du contrat est sautée sans base)
make test-all  # pytest complet, intégration et e2e compris (Docker ou TEST_DATABASE_URL requis)

cd frontend && npm run lint && npm run build && npm test
```

### Commandes `make`

`make help` les liste toutes. La mise en route (`cp .env.example .env`, dont les valeurs par défaut suffisent en local, puis `make up` et `make seed`) est décrite dans le [README](../README.md) : ce guide ne la répète pas.

| Commande | Effet |
|---|---|
| `make up` / `make down` | Démarre (en construisant les images si besoin) / arrête `db`, `api`, `worker` et `frontend` (http://localhost:8080), via `docker compose -f docker/docker-compose.yml --project-directory .` |
| `make logs` | Suit les logs de la stack |
| `make migrate` | `alembic upgrade head` dans le conteneur `api` (déjà fait à son démarrage) |
| `make seed` | Crée la source TraceLab et son mapping, importe `data/samples/tracelab_example_session.jsonl` |
| `make setup` | Une fois après le clone, `gh auth login` fait : prépare `make push`, `make ci` et `make ci-watch` |
| `make push` | Pousse la branche courante et suit son run de CI dans le terminal |
| `make ci` / `make ci-watch` | État de la CI sur la branche courante / suivi en direct |
| `make ci-logs RUN=<id>` | Logs complets d'un run |

---

## 9. Sécurité — règles absolues

1. **Aucune clé API dans le dépôt.** Jamais, même temporairement, même dans une branche non fusionnée. Un secret poussé une fois est compromis, même après suppression du commit.
2. `.env` est dans `.gitignore`. Seul `.env.example` est versionné, **sans valeurs**.
3. **Aucune donnée sensible** dans les fixtures de test, les captures d'écran ou les issues.
4. **Aucun dataset** n'est ajouté au dépôt sans vérifier ses conditions de redistribution. Par défaut : on documente la référence et la méthode de récupération, on ne copie pas les fichiers. Seule exception à ce jour : l'échantillon TraceLab de `data/samples/` (MIT), voir [datasets.md](datasets.md).
5. Si un secret est poussé par erreur : **le révoquer immédiatement** chez le fournisseur, puis prévenir l'équipe. Le retirer de l'historique vient après — la révocation d'abord.

---

## 10. Releases

- Versionnage sémantique : `v0.1.0` pour la livraison de vendredi.
- Une release est une PR `develop` → `main`, soumise aux mêmes règles (1 approbation, `CI Passed`). Le tag est posé sur `main` uniquement, après cette fusion.
- Les notes de version indiquent **les fonctionnalités livrées et les limites connues**. Les limites connues sont une exigence du sujet : on les écrit honnêtement, elles valorisent le rendu au lieu de le desservir.

---

## 11. En cas de doute

| Situation | Réflexe |
|---|---|
| Je ne sais pas dans quelle couche mettre ce code | Demander en PR *draft* ou sur le canal d'équipe, pas deviner |
| Ma PR grossit trop | La découper, quitte à créer une issue supplémentaire |
| Une règle de ce document me bloque | En discuter et **modifier le document par PR**, pas la contourner en silence |
| Je suis bloqué depuis plus d'une heure | Le dire au point suivant, ou tout de suite si ça bloque quelqu'un d'autre |

---

*Ce document évolue par pull request, comme le reste du projet.*
