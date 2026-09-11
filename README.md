# AgentLen

AgentLen ingère les traces d'agents de code IA (Claude Code, Codex, ...), les normalise dans un modèle relationnel commun, et les expose via un dashboard.

- Contrat API : [`docs/architecture/API.md`](docs/architecture/API.md)
- Architecture : [`docs/architecture/README.md`](docs/architecture/README.md)
- Datasets : [`docs/datasets.md`](docs/datasets.md)
- Conventions de travail : [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- Licence : [`LICENSE`](LICENSE)

---

## Prérequis

Assurez-vous d'avoir installé les outils suivants sur votre machine :

- **Docker** (avec Docker Compose)
- **Python 3.12+** (uniquement pour lancer le backend hors Docker)
- **Node.js >= 22.22.2** et **npm** (uniquement pour lancer le frontend hors Docker)
- **gh CLI** authentifié (facultatif — requis seulement pour `make setup`/`make push`/`make ci`)

---

## Installation et lancement du projet

### 1. Configurer les variables d'environnement

- Dupliquez [`.env.example`](.env.example) en `.env` à la racine du projet.
- Dupliquez [`frontend/.env.example`](frontend/.env.example) en `frontend/.env`.
- Renseignez les valeurs nécessaires (voir les commentaires de chaque fichier).

### 2. Lancer la stack complète via Docker

À la racine du projet :

```bash
make up
```

Cela démarre la base de données Postgres, l'API, le worker d'import et le frontend, en construisant les images si besoin.

- Frontend : http://localhost:8080
- API : http://localhost:8000/api/v1
- Documentation interactive de l'API (Swagger) : http://localhost:8000/docs

Les migrations Alembic sont appliquées automatiquement au démarrage du conteneur `api`. Pour les rejouer manuellement (par exemple après avoir ajouté une migration) :

```bash
make migrate
```

Pour peupler la base avec une source et un mapping d'exemple (TraceLab) :

```bash
make seed
```

### 3. Lancer le backend en local, sans Docker

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell ; .venv/bin/activate sur macOS/Linux
pip install -e ".[dev]"
pytest -q
```

Nécessite une base Postgres accessible (via `docker compose up db` par exemple) et un `DATABASE_URL` valide dans `.env`.

### 4. Lancer le frontend en local, sans Docker

```bash
cd frontend
npm install
npm run dev
```

Le serveur de développement Vite proxifie les appels `/api` vers le backend (voir `frontend/.env.example`).

---

## Scripts utiles

### À la racine du projet (Makefile)

| Commande | Description |
|---|---|
| `make setup` | Installation unique — fait en sorte que `git push` streame la CI automatiquement (à lancer après le clone) |
| `make push` | Push la branche courante et streame la CI en direct |
| `make ci` | Affiche le statut de la CI pour la branche courante |
| `make ci-watch` | Suit en direct le run de CI actif sur la branche courante |
| `make ci-logs RUN=<id>` | Affiche les logs complets d'un run précis |
| `make lint` | Lance tous les contrôles qualité bloquants, comme en CI (`ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`) |
| `make format` | Applique le formatage et les correctifs de lint sûrs |
| `make test` | Tests unitaires et contract (la partie SQL nécessite une base, sinon elle est ignorée) |
| `make test-all` | Tous les tests, y compris intégration et end-to-end (nécessite Docker ou `TEST_DATABASE_URL`) |
| `make up` | Démarre db + api + worker + frontend (http://localhost:8080) |
| `make down` | Arrête la stack Docker Compose |
| `make migrate` | Applique les migrations Alembic dans le conteneur `api` |
| `make seed` | Crée la source TraceLab et son mapping, puis importe le fichier d'exemple |
| `make logs` | Suit les logs de toute la stack Docker Compose |
| `make help` | Liste toutes les commandes disponibles |

### Backend, hors Docker

- `pytest tests/unit tests/contract -q` — tests unitaires et contract
- `pytest -q` — suite complète (intégration et e2e inclus)
- `ruff format .` / `ruff check .` — formatage et lint
- `mypy --strict src/agentlen` — vérification de types
- `lint-imports` — vérifie la règle de dépendance entre couches ([`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md))

### Frontend ([`frontend/package.json`](frontend/package.json))

- `npm run dev` — lance le frontend en mode développement
- `npm run build` — vérifie les types (`tsc -b`) puis génère le dossier `dist` pour le déploiement
- `npm run lint` — lint avec Oxlint
- `npm run test` — tests avec Vitest
- `npm run test:watch` — tests en mode watch
- `npm run test:coverage` — tests avec rapport de couverture
- `npm run preview` — prévisualise le build de production

---

## Documentation

| Document | Contenu |
|---|---|
| [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) | Couches, règle de dépendance, ports et adaptateurs, flux principaux, sécurité, tests |
| [`docs/architecture/API.md`](docs/architecture/API.md) | Contrat REST v1 : routes, schémas, conventions d'erreur et de valeurs absentes, drill-down |
| [`docs/architecture/DATA_MODEL.md`](docs/architecture/DATA_MODEL.md) | Diagramme relationnel, grain de chaque table, stratégie d'idempotence |
| [`docs/architecture/MAPPING_CONTRACT.md`](docs/architecture/MAPPING_CONTRACT.md) | Format du document de mapping, whitelist d'opérateurs, validation |
| [`docs/architecture/AGENT.md`](docs/architecture/AGENT.md) | Boucle agentique IA, tools disponibles, politique de contexte |
| [`docs/architecture/frontend.md`](docs/architecture/frontend.md) | Architecture frontend (stack, features, routing) |
| [`docs/architecture/design-system.md`](docs/architecture/design-system.md) | Tokens, composants `components/ui/` |
| [`docs/architecture/decisions.md`](docs/architecture/decisions.md) | ADR : contexte, décision, alternatives écartées, conséquences |
| [`docs/datasets.md`](docs/datasets.md) | Provenance, versions et méthode de sélection des jeux de données |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Modèle de branches, conventions de commit, revue de PR |

---

## Endpoints de l'API backend

Toutes les routes sont préfixées par `/api/v1` (voir [`src/agentlen/interfaces/http/app.py`](src/agentlen/interfaces/http/app.py)). `/health`, `/health/ready` et `/version` restent aussi disponibles sans préfixe pour les sondes d'orchestrateur. Contrat complet, schémas et codes d'erreur : [`docs/architecture/API.md`](docs/architecture/API.md).

### Service — [`routers/service.py`](src/agentlen/interfaces/http/routers/service.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Liveness — le process est en vie |
| GET | `/health/ready` | Readiness — dépendances joignables et schéma à jour |
| GET | `/version` | Version de l'application |

### Auth — [`routers/auth.py`](src/agentlen/interfaces/http/routers/auth.py)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Crée un compte avec un e-mail et un mot de passe |
| POST | `/api/v1/auth/login` | Échange un couple e-mail/mot de passe contre un jeton de session |
| POST | `/api/v1/auth/logout` | Invalide le jeton de session courant |
| GET | `/api/v1/auth/me` | Utilisateur authentifié pour le jeton de session courant |

### Data sources — [`routers/data_sources.py`](src/agentlen/interfaces/http/routers/data_sources.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/data-sources` | Liste les sources de données déclarées |
| POST | `/api/v1/data-sources` | Déclare une nouvelle source de données |

### Files — [`routers/files.py`](src/agentlen/interfaces/http/routers/files.py)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/files` | Dépose un fichier (`multipart/form-data`) |
| GET | `/api/v1/files/{file_id}` | Métadonnées d'un fichier |
| POST | `/api/v1/files/{file_id}/profile` | Profile un fichier stocké : types, cardinalité, ratio de nulls, exemples |

### Mappings — [`routers/mappings.py`](src/agentlen/interfaces/http/routers/mappings.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/mappings` | Liste les mappings, filtrable par source et statut |
| POST | `/api/v1/mappings` | Enregistre un mapping — validé avant écriture |
| POST | `/api/v1/mappings/validate` | Valide un document sans l'enregistrer |
| GET | `/api/v1/mappings/{mapping_id}` | Document complet d'un mapping |
| PUT | `/api/v1/mappings/{mapping_id}` | Crée la version N+1 — l'ancienne version passe à `superseded` |

### Imports — [`routers/imports.py`](src/agentlen/interfaces/http/routers/imports.py)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/imports/preview` | Dry-run : transforme un échantillon, n'écrit rien |
| POST | `/api/v1/imports` | Lance un import (asynchrone — statut via `GET /imports/{id}`) |
| GET | `/api/v1/imports` | Historique des imports, plus récents en premier |
| GET | `/api/v1/imports/{import_run_id}` | Statut et rapport complet d'un import |
| GET | `/api/v1/imports/{import_run_id}/issues` | Rejets, doublons et avertissements, paginés |

### AI mapping — [`routers/ai.py`](src/agentlen/interfaces/http/routers/ai.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/ai/providers` | Fournisseurs IA disponibles et leur statut |
| POST | `/api/v1/mappings/proposals` | Génère une proposition de mapping par l'agent IA |
| GET | `/api/v1/mappings/proposals/{proposal_id}` | Relit une proposition existante |
| POST | `/api/v1/mappings/proposals/{proposal_id}/messages` | Affine une proposition via un message (boucle agentique) |
| PATCH | `/api/v1/mappings/proposals/{proposal_id}` | Corrige manuellement une proposition |

### Exploration — [`routers/exploration.py`](src/agentlen/interfaces/http/routers/exploration.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/sessions` | Liste des sessions, paginée et filtrable |
| GET | `/api/v1/sessions/{id}` | Détail d'une session avec ses appels |
| GET | `/api/v1/sessions/{id}/timeline` | Événements ordonnés d'une session |
| GET | `/api/v1/records/{raw_record_id}` | Enregistrement brut source d'une entité |

### Metrics — [`routers/metrics.py`](src/agentlen/interfaces/http/routers/metrics.py)

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/metrics/definitions` | Comment chaque indicateur est calculé, et sa politique sur les données manquantes |
| GET | `/api/v1/metrics/overview` | Les quatre indicateurs clés, chacun avec sa couverture |
| GET | `/api/v1/metrics/activity` | Sessions et tokens par jour et par source |
| GET | `/api/v1/metrics/tools` | Volume d'appels et taux d'erreur par outil |
| GET | `/api/v1/metrics/models` | Volume d'appels et tokens par modèle et fournisseur |
| GET | `/api/v1/metrics/quality` | Ce que chaque import a reçu et rejeté |
