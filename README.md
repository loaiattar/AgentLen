# AgentLen

AgentLen ingère les traces d'agents de code (Claude Code, Codex, …), les normalise
dans un modèle relationnel commun et les expose dans un tableau de bord.

Un fichier de traces arrive dans un format quelconque ; un **mapping** — écrit à la
main ou proposé par un modèle — décrit comment en extraire sessions, appels de
modèle et appels d'outils. L'import est idempotent : rejouer le même fichier ne
duplique rien.

---

## Prérequis

- **Docker** et **Docker Compose** — c'est tout ce qui est nécessaire.
- Une clé **Anthropic** ou **OpenAI**, uniquement pour la proposition de mapping
  par IA. **Le parcours complet fonctionne sans aucune clé** : `AI_PROVIDER=fake`
  est le défaut et s'appuie sur un adaptateur de test.

Pour développer hors conteneur, il faut Python ≥ 3.12 et Node ≥ 22.22.2.

## Installation

```bash
git clone https://github.com/loaiattar/AgentLen.git
cd AgentLen
cp .env.example .env        # les défauts suffisent pour un essai local
make up                     # construit et démarre db + api + worker + frontend
```

`make up` attend que chaque service soit sain. L'interface répond alors sur
**http://localhost:8080** et l'API sur **http://localhost:8000**.

> Si l'un de ces ports est déjà pris sur votre machine, posez `API_HOST_PORT`,
> `FRONTEND_HOST_PORT` ou `DB_HOST_PORT` dans `.env`. Les conteneurs se parlent
> sur le réseau interne, seules vos URL d'accès changent.

## Parcours principal

### En une commande

```bash
make seed
```

Crée la source `tracelab`, son mapping, et importe le fichier d'exemple livré
avec le dépôt. La commande affiche son propre bilan :

```
Seed terminé : status=succeeded, lus=19, importés=26, doublons=14, rejetés=0.
```

Ouvrez ensuite **http://localhost:8080** : le tableau de bord affiche les
indicateurs calculés sur ces données.

### Le même parcours en HTTP

Les routes de données demandent l'en-tête `X-API-Key`, dont la valeur est celle
d'`API_KEY` dans votre `.env`.

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)
API=http://localhost:8000/api/v1

# 1. Téléverser un fichier de traces
curl -s -H "X-API-Key: $KEY" -F "file=@data/samples/tracelab_example_session.jsonl" \
     "$API/files"

# 2. Profiler le fichier — types, taux de valeurs nulles, exemples par champ
curl -s -H "X-API-Key: $KEY" -X POST "$API/files/1/profile"

# 3. Prévisualiser ce que le mapping produirait, sans rien écrire
curl -s -H "X-API-Key: $KEY" -X POST "$API/imports/preview" \
     -H 'Content-Type: application/json' \
     -d '{"file_id": 1, "mapping_id": 1, "sample_size": 20}'

# 4. Lancer l'import — la réponse est immédiate, le worker traite en fond
curl -s -H "X-API-Key: $KEY" -X POST "$API/imports" \
     -H 'Content-Type: application/json' \
     -d '{"data_source_id": 1, "file_upload_id": 1, "mapping_id": 1}'

# 5. Suivre le run jusqu'à son statut terminal
curl -s -H "X-API-Key: $KEY" "$API/imports/1"

# 6. Lire un indicateur
curl -s -H "X-API-Key: $KEY" "$API/metrics/tools"
```

La dernière commande renvoie, pour chaque outil, son nombre d'appels, son taux
d'erreur et la couverture des données qui les sous-tendent :

```json
{"points": [{"label": "exec_command", "call_count": 3, "error_count": 1,
             "error_ratio": 0.5, "coverage": {"present": 2, "total": 3}}]}
```

Les quatre indicateurs sont `/metrics/activity`, `/metrics/tools`,
`/metrics/models` et `/metrics/quality`. La documentation interactive est sur
**http://localhost:8000/docs**.

## Lancer les tests

```bash
make test        # unitaires + contrat — quelques secondes, aucune base requise
make test-all    # tout : intégration et bout-en-bout sur un vrai PostgreSQL
make lint        # ruff, mypy --strict, import-linter — exactement ce que fait la CI
```

`make test-all` démarre un PostgreSQL jetable via testcontainers. Si Docker n'est
pas disponible, fournissez une base avec `TEST_DATABASE_URL` ; sans l'un ni
l'autre, les tests qui en dépendent sont **sautés explicitement**, jamais
silencieusement.

Le frontend a sa propre suite :

```bash
cd frontend && npm ci && npm test
```

## Changer de modèle IA

Le fournisseur et le modèle viennent entièrement de la configuration — aucun
identifiant de modèle n'est écrit dans le code ([ADR-006](docs/architecture/decisions.md)).

```bash
# Anthropic
AI_PROVIDER=anthropic AI_MODEL=<votre-modèle> ANTHROPIC_API_KEY=<clé> make up

# OpenAI
AI_PROVIDER=openai AI_MODEL=<votre-modèle> OPENAI_API_KEY=<clé> make up

# Tout hôte au dialecte OpenAI — Groq, Mistral, OpenRouter, Ollama…
AI_PROVIDER=openai_compatible AI_MODEL=<votre-modèle> \
  AI_BASE_URL=<url> AI_API_KEY=<clé> make up
```

Sans aucune de ces variables, `AI_PROVIDER=fake` répond sans réseau ni clé : le
reste du produit fonctionne à l'identique.

## Structure du dépôt

| Chemin | Contenu |
|---|---|
| `src/agentlen/domain/` | Modèles et règles métier — n'importe rien d'autre que la bibliothèque standard |
| `src/agentlen/application/` | Cas d'utilisation et ports |
| `src/agentlen/infrastructure/` | Adaptateurs : PostgreSQL, lecture de fichiers, fournisseurs IA |
| `src/agentlen/interfaces/` | API HTTP et CLI |
| `frontend/` | Interface React, TanStack Router et Query |
| `tests/` | `unit`, `contract`, `integration`, `e2e` |
| `docs/` | Architecture, contrat d'API, décisions |

La règle de dépendance est vérifiée automatiquement par `import-linter` : une PR
qui importe SQLAlchemy depuis `domain/` échoue en CI, pas en revue.

**Documentation** — [architecture](docs/architecture/README.md) ·
[contrat d'API](docs/architecture/API.md) ·
[modèle de données](docs/architecture/DATA_MODEL.md) ·
[contrat de mapping](docs/architecture/MAPPING_CONTRACT.md) ·
[décisions (ADR)](docs/architecture/decisions.md) ·
[jeux de données](docs/datasets.md)

## Limites connues

Écrites honnêtement, telles qu'elles sont aujourd'hui.

- **L'indicateur d'activité est vide sur les données du `make seed`.** Il groupe
  les sessions par jour, et le mapping d'exemple ne renseigne pas `started_at` —
  le fichier TraceLab livré ne porte pas d'horodatage exploitable au niveau de la
  session. Les trois autres indicateurs affichent bien les données importées.
- **Les routes de données ne sont protégées que par une clé partagée.** Le
  conteneur frontend ajoute lui-même l'en-tête `X-API-Key` aux appels qu'il
  relaie : quiconque atteint l'interface atteint l'API. L'authentification par
  session utilisateur existe (`/auth/register`, `/auth/login`) mais n'est pas
  encore exigée sur les routes de données.
- **Un fichier téléversé est écrit en entier avant que sa taille soit vérifiée**,
  `MAX_UPLOAD_SIZE_MB` n'intervenant qu'après coup.
- **Les imports volumineux ne sont pas découpés par lot** au-delà de la limite de
  paramètres de PostgreSQL : un lot trop grand fait échouer tout l'import.
- **La proposition de mapping par IA n'est pas déterministe.** Le dry-run existe
  pour ça : rien n'est écrit avant que vous ayez vu ce que le mapping produit.
- **La reprise des jobs d'import bloqués n'est pas implémentée.** Un worker tué
  en plein import laisse le run en `running`.

Chacune de ces limites a son issue ouverte sur le dépôt : [#200](https://github.com/loaiattar/AgentLen/issues/200), [#150](https://github.com/loaiattar/AgentLen/issues/150), [#177](https://github.com/loaiattar/AgentLen/issues/177), [#136](https://github.com/loaiattar/AgentLen/issues/136), [#18](https://github.com/loaiattar/AgentLen/issues/18).

## Contribuer

Les conventions de branche, de commit et de revue sont dans
[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). `make help` liste toutes les
commandes disponibles.

## Licence

MIT — voir [`LICENSE`](LICENSE).
