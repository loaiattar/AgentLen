# AgentLen — Contrat d'API v1

> **Ce document est le contrat avec l'équipe frontend.** Toute évolution passe par une PR sur ce fichier, relue par les deux équipes, **avant** implémentation.
> L'OpenAPI généré par FastAPI est disponible **sans clé** sur `/docs`, `/redoc` et `/openapi.json` et doit rester conforme à ce document (voir [Authentification](#authentification)).

Préfixe : `/api/v1` · Format : JSON · Horodatages : ISO 8601 UTC · Durées : millisecondes

---

## 1. Conventions

### Erreurs

Toutes les erreurs partagent la même enveloppe :

```json
{
  "error": {
    "code": "MAPPING_UNKNOWN_TARGET",
    "message": "Le champ cible 'session.user_email' n'existe pas dans le schéma.",
    "field_path": "entities[0].fields[3].target",
    "details": {}
  }
}
```

| HTTP | Signification |
|---|---|
| `400` | Requête malformée |
| `401` | Clé API manquante ou invalide (`X-API-Key`) |
| `404` | Ressource inexistante |
| `409` | Conflit (fichier déjà importé avec ce mapping) |
| `422` | Validation métier échouée (mapping invalide, format non supporté) |
| `502` | Le fournisseur IA a échoué ou renvoyé une réponse non conforme |
| `504` | L'analyse IA a dépassé son délai total (`ANALYZER_TIMEOUT`, `AI_TOTAL_TIMEOUT_SECONDS`) |

### Authentification

Toutes les routes exigent le header `X-API-Key`, dont la valeur est celle de la variable d'environnement `API_KEY`. Cette clé authentifie **l'application front**, pas une personne : elle est unique et partagée, au niveau de tout le service.

L'authentification **par personne** (compte e-mail/mot de passe, jeton de session) est une couche distincte, ajoutée par-dessus — voir [§10 Authentification utilisateur](#10-authentification-utilisateur-comptes). `X-API-Key` reste exigé sur `/auth/*` comme sur toute autre route.

Exceptions (sans clé) :

- `GET /health` et `GET /api/v1/health` — sonde de vivacité
- `GET /version` et `GET /api/v1/version` — version applicative seule, sans accès à la base
- `GET /docs`, `GET /redoc` et `GET /openapi.json` — documentation interactive et schéma

La documentation est publique par choix : un navigateur qui ouvre `/docs` ne peut pas joindre de header, donc une documentation protégée serait inutilisable ; elle ne décrit que des routes qui exigent toujours la clé, et la clé du front est de toute façon livrée au navigateur. Le schéma déclare les deux mécanismes, sans rien changer à leur application : `ApiKeyAuth` (header `X-API-Key`, exigé partout sauf ci-dessus) et `BearerAuth` (en plus de la clé, sur les routes qui exigent un jeton de session, §10). Chaque opération y documente l'enveloppe d'erreur pour `401`, `500` et, selon la route, `400`, `404`, `409`, `422`, `502` et `504`.

Une clé absente ou invalide renvoie `401` :

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Clé API manquante ou invalide.",
    "field_path": null,
    "details": {}
  }
}
```

Le navigateur n'envoie pas ce header et ne connaît pas la clé : le proxy placé devant l'API l'ajoute à chaque appel `/api` — nginx dans la stack Docker, le proxy Vite avec `npm run dev`, tous deux depuis `API_KEY` (ADR-013). Un client qui appelle l'API directement, sans ce proxy, fournit la clé lui-même. Les origines autorisées pour le CORS sont `ALLOWED_ORIGINS` (liste séparée par des virgules, `http://localhost:5173` en développement).

### Pagination

`?limit=50&offset=0` — réponses enveloppées : `{ "items": [...], "total": 1240, "limit": 50, "offset": 0 }`. `limit` va de 1 à 200.

**Exceptions : tableaux nus bornés.** `GET /data-sources` et `GET /sessions/{id}/timeline` renvoient un tableau JSON, pas l'enveloppe, pour ne pas casser les écrans qui les consomment déjà. Ils restent bornés : mêmes paramètres `limit` (1 à 200, **200 par défaut**) et `offset`, et l'en-tête `X-Total-Count` donne le total avant fenêtrage. Le front sait ainsi qu'une réponse a été tronquée lorsque `X-Total-Count` dépasse la longueur du tableau.

### Identifiants

Les identifiants de chemin (`/files/{id}`, `/sessions/{id}`, `/records/{raw_record_id}`…) et de filtre (`data_source_id`, `agent_id`, `model_id`, `tool_id`, `import_run_id`) sont des entiers de `1` à `2^63 - 1` (BIGINT). Hors de cette plage, la réponse est `400` `MALFORMED_REQUEST`, jamais `500`.

### Valeurs absentes

Une valeur inconnue est **`null`**, jamais `0`. Les agrégats sont accompagnés d'un objet `coverage` :

```json
{ "value": 184203, "unit": "tokens",
  "coverage": { "present": 812, "total": 1000, "ratio": 0.812 } }
```

`ratio` vaut `null` lorsque le périmètre est vide (`total = 0`) : la couverture
est alors inconnue, et non nulle. Le front doit tester ce cas avant de comparer,
puis afficher un indicateur de couverture partielle lorsque `ratio` est non
`null` et `< 1`.

---

## 2. Sources et fichiers

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/data-sources` | Liste des sources avec version et date de récupération |
| `POST` | `/data-sources` | Déclare une nouvelle source |
| `POST` | `/files` | Dépose un fichier (`multipart/form-data`) |
| `GET` | `/files/{id}` | Métadonnées d'un fichier |
| `POST` | `/files/{id}/profile` | Profilage : types, cardinalité, taux de null, exemples |

**`POST /files` → `201`**

```json
{ "id": 12, "original_name": "tracelab_sample.jsonl", "format": "jsonl",
  "size_bytes": 4823110, "content_hash": "9f2c…",
  "already_seen": false, "previous_import_run_ids": [] }
```

`already_seen: true` signale que le même contenu a déjà été déposé — le front doit avertir l'utilisateur avant de relancer un import.

Refus :

- `422 FILE_TOO_LARGE` au-delà de `MAX_UPLOAD_SIZE_MB` (512 Mo par défaut). Le corps est lu au fil de l'envoi : il est refusé avant toute lecture si `Content-Length` annonce plus que la limite, sinon dès que le flux la dépasse. Aucun fichier partiel ne reste sur le disque.
- `422 UNSUPPORTED_FILE_FORMAT` : extension non autorisée ou contenu qui ne correspond à aucun format reconnu.
- `400 MALFORMED_REQUEST` : corps qui n'est pas du `multipart/form-data` ou sans champ `file`.

**`POST /files/{id}/profile` → `200`**

```json
{
  "file_id": 12, "record_count": 12483, "sampled_records": 500,
  "fields": [
    { "path": "$.session_id", "types": ["string"], "null_ratio": 0.0,
      "distinct_ratio": 1.0, "examples": ["a3f2…"] },
    { "path": "$.usage.input_tokens", "types": ["integer", "null"],
      "null_ratio": 0.12, "min": 12, "max": 184203, "examples": [1204] }
  ]
}
```

---

## 3. Agent d'import IA

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/ai/providers` | Fournisseurs et modèles disponibles selon la configuration |
| `POST` | `/mappings/proposals` | Demande une proposition de mapping à l'IA |
| `GET` | `/mappings/proposals/{id}` | État d'une proposition |
| `POST` | `/mappings/proposals/{id}/messages` | Échange conversationnel : correction, question |
| `PATCH` | `/mappings/proposals/{id}` | Correction manuelle directe du document |

**`GET /ai/providers` → `200`** — permet au front de proposer un sélecteur sans rien coder en dur :

```json
{ "active": { "provider": "anthropic", "model": "claude-opus-4-8" },
  "available": [
    { "provider": "anthropic", "configured": true },
    { "provider": "openai",    "configured": true },
    { "provider": "fake",      "configured": true }
  ] }
```

**`POST /mappings/proposals`** — corps : `{ "file_id": 12, "data_source_id": 3, "provider": null, "model": null, "hint": null }`. `provider`/`model` à `null` = configuration active du serveur.

- `provider` doit appartenir au registre (`anthropic`, `fake`, `openai`, `openai_compatible`, les valeurs de `GET /ai/providers`). Sinon : `400` `MALFORMED_REQUEST`, `field_path` `body.provider`, et le message liste les valeurs acceptées. Le refus a lieu avant toute construction d'adaptateur ; ce n'est plus un `502`.
- `model` est un texte libre : chaque hôte publie ses propres identifiants, et le serveur ne peut pas en tenir la liste (ADR-006). Il est borné à 200 caractères, sans espace ni caractère de contrôle. Un identifiant inconnu du fournisseur reste un `502`. `model` est **obligatoire dès que `provider` est renseigné** (`400`, `field_path` `body.model`) : le modèle configuré appartient au fournisseur configuré.
- `AI_BASE_URL` ne s'applique qu'au fournisseur configuré. Un autre fournisseur choisi par requête utilise le point d'accès par défaut de son adaptateur ; la clé d'un fournisseur ne part jamais vers l'hôte d'un autre. Choisir `openai_compatible` quand il n'est pas le fournisseur configuré donne donc un `502` (pas d'hôte).
- Une proposition, comme un raffinement (`POST /mappings/proposals/{id}/messages`), doit se terminer en `AI_TOTAL_TIMEOUT_SECONDS` (défaut `540`, sous les 600 s du proxy nginx), toutes itérations et tentatives comprises. Au-delà, l'analyse est interrompue, rien n'est enregistré, et l'API répond `504` `ANALYZER_TIMEOUT` avec `details.total_timeout_seconds`. Comme pour un `502`, le front peut proposer de relancer.

Réponse `200` :

```json
{
  "proposal_id": 41,
  "analyzer": { "provider": "anthropic", "model": "claude-opus-4-8",
                "prompt_version": "v3" },
  "mapping": { /* document — voir MAPPING_CONTRACT.md */ },
  "validation": { "valid": true, "errors": [] },
  "rationale": [
    { "target": "session.external_id", "source": "$.session_id",
      "confidence": "high", "explanation": "Unique sur 100 % des enregistrements." }
  ],
  "ambiguities": [
    { "field": "$.duration",
      "question": "Secondes ou millisecondes ?",
      "options": ["unit_convert s→ms", "aucune conversion"] }
  ],
  "unmapped_fields": [
    { "path": "$.internal.debug_flags",
      "reason": "Aucun équivalent dans le modèle cible." }
  ]
}
```

> `validation.valid` peut être `false` : la proposition est alors **quand même renvoyée**, avec ses erreurs localisées, pour que l'utilisateur la corrige. On n'échoue pas silencieusement.

---

## 4. Mappings

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/mappings` | Liste, filtrable par source et statut |
| `POST` | `/mappings` | Enregistre un mapping (validé avant écriture) |
| `GET` | `/mappings/{id}` | Document complet |
| `PUT` | `/mappings/{id}` | Crée une **nouvelle version** (l'ancienne passe `superseded`) |
| `POST` | `/mappings/validate` | Valide un document sans l'enregistrer |

`POST /mappings` renvoie `422` avec la liste complète des erreurs si le document est invalide — jamais un enregistrement partiel.

---

## 5. Imports

| Méthode | Chemin | Description |
|---|---|---|
| `POST` | `/imports/preview` | **Dry-run** : transforme N enregistrements, n'écrit rien |
| `POST` | `/imports` | Lance un import (asynchrone) |
| `GET` | `/imports` | Historique des imports |
| `GET` | `/imports/{id}` | Statut et bilan |
| `GET` | `/imports/{id}/issues` | Rejets, doublons et avertissements, paginés |

**`POST /imports/preview` → `200`**

```json
{
  "sampled": 20,
  "would_import": { "session": 20, "model_call": 143, "tool_call": 271 },
  "would_reject": 2,
  "entities": [ { "target": "session", "rows": [ { "external_id": "a3f2…" } ] } ],
  "issues": [
    { "line_number": 42, "severity": "rejected", "code": "CAST_FAILED",
      "field_path": "$.usage.input_tokens",
      "message": "Impossible de convertir \"n/a\" en entier." }
  ]
}
```

**`POST /imports` → `202`** : `{ "import_run_id": 88, "status": "pending" }`.
Le front interroge ensuite `GET /imports/{id}` (intervalle suggéré : 1 s).

**`GET /imports/{id}` → `200`**

```json
{
  "id": 88, "status": "partial",
  "data_source": { "id": 3, "slug": "tracelab" },
  "file": { "id": 12, "original_name": "tracelab_sample.jsonl" },
  "mapping": { "id": 7, "name": "tracelab-jsonl", "version": 2 },
  "report": {
    "records_read": 12483, "records_imported": 12310,
    "records_duplicate": 150, "records_rejected": 23,
    "fields_missing": { "model_call.cache_read_tokens": 12483 }
  },
  "started_at": "2026-09-07T09:12:03Z", "finished_at": "2026-09-07T09:12:41Z"
}
```

`fields_missing` alimente directement la vue « qualité des données » du dashboard.

**`GET /imports/{id}/issues?severity=rejected` → `200`**

```json
{
  "items": [
    { "line_number": 42, "raw_record_id": 51234, "severity": "rejected",
      "code": "CAST_FAILED", "field_path": "$.usage.input_tokens",
      "message": "Impossible de convertir \"n/a\" en entier." }
  ],
  "total": 23, "limit": 50, "offset": 0
}
```

`line_number` est lu sur le `raw_record` auquel l'issue est reliée ; `raw_record_id` ouvre l'enregistrement source brut sur `GET /records/{raw_record_id}` (§6). Les deux valent `null` pour une issue qui ne concerne aucune ligne précise (ex. `ALREADY_IMPORTED`, émise par lot).

---

## 6. Exploration

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/sessions` | Liste filtrable — **cible du drill-down** |
| `GET` | `/sessions/{id}` | Vue détaillée : chronologie des appels modèles et outils |
| `GET` | `/sessions/{id}/timeline` | Événements ordonnés |
| `GET` | `/records/{raw_record_id}` | **Enregistrement source brut** d'un fait normalisé |

Filtres communs à `/sessions` et à toutes les routes de métriques :

`data_source_id` · `agent_id` · `model_id` · `tool_id` · `import_run_id` · `date_from` · `date_to` · `status`

> **Contrat de drill-down.** Toute réponse de graphique inclut, pour chaque point, un objet `filters` directement rejouable sur `GET /sessions`. Le front n'a aucune logique de traduction à écrire, et le backend n'a aucun état à conserver.

---

## 7. Métriques et dashboard

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/metrics/definitions` | **Définition de chaque indicateur** : calcul, unité, périmètre, valeurs manquantes |
| `GET` | `/metrics/overview` | Les indicateurs de tête (≥ 4) |
| `GET` | `/metrics/activity` | Série temporelle |
| `GET` | `/metrics/tools` | Répartition et taux d'erreur par outil |
| `GET` | `/metrics/models` | Volumétrie par modèle et fournisseur |
| `GET` | `/metrics/quality` | Qualité des données importées |

**`GET /metrics/definitions` → `200`** — répond à l'exigence « chaque indicateur doit avoir une définition accessible » :

```json
{
  "definitions": [
    {
      "key": "total_output_tokens",
      "label": "Tokens produits",
      "unit": "tokens",
      "formula": "SUM(model_call.output_tokens)",
      "scope": "Appels modèles des sessions retenues par les filtres actifs",
      "missing_policy": "Les appels sans information de tokens sont exclus du numérateur et signalés par le champ coverage. Une absence n'est jamais comptée comme zéro.",
      "comparability": "cross_source"
    },
    {
      "key": "cache_read_ratio",
      "label": "Part de lecture de cache",
      "unit": "ratio",
      "formula": "SUM(cache_read_tokens) / NULLIF(SUM(input_tokens), 0)",
      "scope": "Sources fournissant les métriques de cache",
      "missing_policy": "Renvoie null si aucune donnée de cache n'est disponible.",
      "comparability": "per_source_only"
    }
  ]
}
```

**`GET /metrics/overview` → `200`**

```json
{
  "filters_applied": { "data_source_id": 3, "date_from": "2026-08-01" },
  "metrics": [
    { "key": "session_count", "value": 1240, "unit": "sessions",
      "coverage": { "present": 1240, "total": 1240, "ratio": 1.0 } },
    { "key": "total_output_tokens", "value": 8412903, "unit": "tokens",
      "coverage": { "present": 1090, "total": 1240, "ratio": 0.879 } },
    { "key": "cache_read_ratio", "value": null, "unit": "ratio",
      "coverage": { "present": 0, "total": 1240, "ratio": 0.0 },
      "warning": "Indicateur non disponible pour cette source." },
    { "key": "tool_error_rate", "value": null, "unit": "ratio",
      "coverage": { "present": 0, "total": 0, "ratio": null },
      "warning": "Aucun appel d'outil sur ce périmètre." }
  ]
}
```

**`GET /metrics/tools` → `200`** — chaque point porte ses filtres de drill-down :

```json
{
  "points": [
    { "label": "Bash", "tool_id": 4, "call_count": 3820,
      "error_count": 210, "error_ratio": 0.055,
      "filters": { "tool_id": 4, "data_source_id": 3 } }
  ]
}
```

**`GET /metrics/activity` → `200`** : un point par jour (UTC) et par source. Une session est placée au jour de son `started_at`, et une session sans date n'y figure pas. Quand le périmètre en contient, `warnings` le dit, pour qu'une série vide ne se lise pas comme « aucune activité » :

```json
{
  "points": [],
  "filters_applied": {},
  "warnings": [
    "2 session(s) sur 2 sans date de début, absente(s) de cette série : ni la source ni les appels de ces sessions ne portent d'horodatage mappé."
  ]
}
```

`warnings` existe sur les quatre routes de graphique, et le front l'affiche. Il signale aujourd'hui les métriques de cache non comparables entre sources (`/metrics/models`) et les sessions sans date (`/metrics/activity`).

---

## 8. Service

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/health` | Vivacité |
| `GET` | `/health/ready` | Base accessible, migrations à jour, worker actif ; révisions `alembic_revision` (appliquée) et `alembic_head` (livrée). Protégée par la clé |
| `GET` | `/version` | Version applicative seule (`{"version": "0.1.0"}`) : publique, sans accès à la base ni révision de schéma |

---

## 9. Points d'attention pour l'équipe frontend

1. **Les imports sont asynchrones.** `POST /imports` renvoie `202` ; l'état s'obtient par polling sur `GET /imports/{id}`.
2. **`null` n'est pas `0`.** Un indicateur `null` signifie *non disponible* et doit s'afficher comme tel, pas comme une valeur nulle. Distinguer les deux couvertures possibles : `coverage.ratio = 0` signifie *mesuré, et aucune donnée ne porte cet indicateur* ; `coverage.ratio = null` (avec `total = 0`) signifie *rien à mesurer dans ce périmètre*, la couverture elle-même est inconnue.
3. **`comparability: per_source_only`** interdit l'agrégation multi-sources. L'API renvoie un `warning` que le front doit rendre visible.
4. **Le drill-down est fourni clé en main** via l'objet `filters` de chaque point.
5. **Le front n'appelle jamais un fournisseur IA directement.** Aucune clé de fournisseur IA ne quitte le serveur, aucune n'est livrée au navigateur. La clé `X-API-Key` d'AgentLen est distincte, et n'est pas livrée au navigateur non plus : le proxy du front l'ajoute à chaque appel (§1).
6. **Toujours proposer la prévisualisation avant l'import.** `POST /imports/preview` n'écrit rien et sert de garde-fou avant validation.
7. **Chaque requête authentifiée porte `X-API-Key`.** Seuls `/health`, `/version` et la documentation (`/docs`, `/redoc`, `/openapi.json`) en sont exemptés. Le code du front ne l'ajoute jamais : c'est le proxy (nginx ou Vite) qui s'en charge.

---

## 10. Authentification utilisateur (comptes)

Couche distincte de `X-API-Key` (§1) : ces routes identifient **une personne**, pas l'application. Toutes exigent quand même `X-API-Key`, comme le reste de l'API.

| Méthode | Chemin | Description |
|---|---|---|
| `POST` | `/auth/register` | Crée un compte (e-mail + mot de passe) |
| `POST` | `/auth/login` | Échange e-mail + mot de passe contre un jeton de session |
| `POST` | `/auth/logout` | Invalide le jeton de session courant |
| `GET` | `/auth/me` | Le compte associé au jeton de session courant |

**`POST /auth/register` → `201`**

```json
{ "id": 1, "email": "alice@example.com", "created_at": "2026-09-10T12:00:00Z" }
```

Ni `password` ni son hash n'apparaissent jamais dans une réponse. `409` si l'e-mail est déjà utilisé, `422` (`INVALID_EMAIL` / `WEAK_PASSWORD`) si l'e-mail ou le mot de passe échoue à la validation.

**Longueurs maximales (`/auth/register` et `/auth/login`).** `email` : 254 caractères. `password` : 72 octets en UTF-8, la limite de bcrypt (un caractère accentué en compte deux). Au-delà, la requête est refusée avant tout traitement par `400` `MALFORMED_REQUEST`, avec `field_path` à `body.email` ou `body.password`, et non par `422` : ces routes répondent sans session, et une valeur non bornée permettrait à n'importe qui d'occuper le serveur.

**`POST /auth/login` → `200`**

```json
{ "token": "opaque-random-string",
  "user": { "id": 1, "email": "alice@example.com", "created_at": "2026-09-10T12:00:00Z" } }
```

`401` (`INVALID_CREDENTIALS`) pour un mot de passe incorrect **ou** un compte inexistant — volontairement la même erreur dans les deux cas, pour ne pas laisser deviner quels e-mails ont un compte.

Le jeton est un **jeton de session opaque stocké en base** (`user_session`), pas un JWT : la révocation au logout est un simple `DELETE`, sans clé de signature à gérer. Il se présente en `Authorization: Bearer <token>` sur toute route protégée.

**`POST /auth/logout` → `204`.** Idempotent : appeler la route sans jeton, ou avec un jeton déjà invalidé, renvoie aussi `204`.

**`GET /auth/me` → `200`** avec le même corps que la partie `user` de `/auth/login`, ou `401` (`UNAUTHENTICATED`) si le jeton est absent, inconnu ou expiré (30 jours).
