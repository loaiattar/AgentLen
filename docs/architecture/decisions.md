# AgentLen — Décisions d'architecture (ADR)

> Format court : contexte → décision → conséquences. Une décision par section.
> Une décision se révise par PR ; on ajoute alors une nouvelle ADR qui remplace l'ancienne plutôt que de réécrire l'historique.

---

## ADR-001 — Clean Architecture en quatre couches, vérifiée par la CI

**Statut :** accepté

**Contexte.** Le sujet accorde 7 points sur 20 à l'architecture et prévient : « des dossiers nommés *domain* ou *infrastructure* ne suffisent pas ». Une séparation par convention dérive dès qu'on travaille à plusieurs sous contrainte de temps.

**Décision.** Quatre couches (`domain`, `application`, `infrastructure`, `interfaces`) avec une règle de dépendance stricte, **déclarée dans `pyproject.toml` et vérifiée par `import-linter` dans la CI**. Une PR qui fait importer `sqlalchemy` depuis `domain/` échoue.

**Conséquences.** La séparation devient démontrable, pas déclarative. Coût : quelques conversions entités ↔ modèles de persistance, et une discipline de DI concentrée dans `interfaces/http/dependencies.py`.

---

## ADR-002 — FastAPI pour la couche interface

**Statut :** accepté

**Contexte.** Le frontend est développé par une autre équipe : le backend doit livrer un contrat d'API clair, stable et documenté.

**Décision.** FastAPI. Les schémas Pydantic vivent **exclusivement** dans `interfaces/http/schemas/` et ne descendent jamais dans le domaine.

**Alternatives.** Django+DRF apporte l'admin et les migrations, mais son ORM Active Record pousse à mélanger persistance et métier — coûteux à défendre sur le critère principal. Flask est neutre mais impose de recâbler validation et OpenAPI à la main.

**Conséquences.** OpenAPI généré automatiquement, utilisable immédiatement par l'équipe front. Le domaine reste ignorant du web.

---

## ADR-003 — SQLAlchemy 2.0 en mapping impératif + Alembic

**Statut :** accepté

**Contexte.** Les entités du domaine doivent rester des classes Python pures, mais il faut aussi des requêtes analytiques efficaces et des migrations versionnées.

**Décision.** Tables définies en SQLAlchemy Core dans `infrastructure/persistence/tables.py`, associées aux entités par **mapping impératif** (`registry.map_imperatively`). Alembic pour les migrations. Les lectures du dashboard passent par des read models SQL dédiés, pas par le chargement d'entités.

**Conséquences.** Aucune annotation ORM ne pollue le domaine. Coût : le mapping impératif est moins familier que le déclaratif — il est documenté et concentré dans un seul module.

---

## ADR-004 — PostgreSQL seul, y compris pour la file de jobs

**Statut :** accepté

**Contexte.** Les imports peuvent être longs ; une exécution synchrone expose à des timeouts et prive le front de progression. Les solutions classiques (Celery, RQ, ARQ) exigent Redis.

**Décision.** File de jobs implémentée dans Postgres via `SELECT … FOR UPDATE SKIP LOCKED` sur `import_run`. Un service `worker` distinct dans `docker-compose`.

**Alternatives.** Redis + Celery : plus riche, mais un composant d'infrastructure supplémentaire à installer et documenter, au détriment de la reproductibilité exigée. `BackgroundTasks` FastAPI : ni persistant, ni reprenable après redémarrage.

**Conséquences.** Une seule dépendance d'infrastructure. Les jobs survivent au redémarrage et sont reprenables. Le passage à un broker dédié reste possible : seule l'implémentation du port `JobQueue` change.

---

## ADR-005 — Le LLM produit un document de mapping, jamais du code

**Statut :** accepté

**Contexte.** Le sujet impose : « l'IA propose un mapping ; elle ne modifie pas directement la base » et « sans exécuter librement du code produit par le modèle ». Par ailleurs, les traces contiennent du texte arbitraire — donc potentiellement des tentatives d'injection de prompt.

**Décision.** La seule sortie exploitable du LLM est un document JSON conforme au [contrat de mapping](MAPPING_CONTRACT.md), validé par schéma puis interprété par un moteur à **whitelist d'opérateurs**. Ni `eval`, ni `exec`, ni SQL généré, ni import dynamique. Les contenus de trace sont encadrés comme données dans les prompts.

**Conséquences.** L'injection de prompt devient sans effet exploitable : au pire le modèle propose un mauvais mapping, que la validation rejette et que l'utilisateur voit avant import. Limite acceptée : certaines transformations exotiques ne seront pas exprimables ; l'application les signale explicitement dans `unmapped_fields` plutôt que d'échouer silencieusement.

---

## ADR-006 — Port `StructureAnalyzer` + registre d'adaptateurs

**Statut :** accepté

**Contexte.** « Le choix du fournisseur, du modèle et de son point d'accès doit se faire par configuration, sans modifier le code métier ni le moteur d'import. Les identifiants de modèles ne doivent pas être codés en dur. »

**Décision.** Un port unique dans `application/ports/`, trois adaptateurs (`anthropic`, `openai`, `fake`) dans `infrastructure/ai/`, résolus par une factory lisant `AI_PROVIDER` / `AI_MODEL` / `AI_BASE_URL`. Chaque adaptateur convertit vers le **même** `MappingProposal`, ensuite validé par l'application.

**Conséquences.** Ajouter un fournisseur = une classe + une ligne de registre. Changer de modèle = une variable d'environnement. Un mapping enregistré reste applicable après changement de fournisseur — vérifié par un test dédié.

---

## ADR-007 — Polars pour la lecture et le profilage

**Statut :** accepté

**Contexte.** Trois formats à lire (JSONL, CSV, Parquet), fichiers potentiellement volumineux, et un profilage statistique à produire pour alimenter l'IA.

**Décision.** Polars, isolé derrière les ports `DataFileReader` et `FileProfiler`.

**Alternatives.** Pandas : plus familier mais nettement moins efficace en mémoire sur les gros JSONL. DuckDB : excellent techniquement, mais le sujet interdit d'utiliser la base DuckDB fournie par TraceLab — l'introduire créerait une ambiguïté inutile au rendu, en plus de faire doublon avec Postgres.

**Conséquences.** Lecture paresseuse et profilage rapide. Polars reste remplaçable : aucun `import polars` hors de `infrastructure/files/`.

---

## ADR-008 — Provenance ancrée sur `raw_record`

**Statut :** accepté

**Contexte.** Il faut conserver les données d'origine, expliquer chaque rejet, et permettre de remonter d'un chiffre du dashboard à sa source.

**Décision.** Le fichier est conservé sur disque avec son SHA-256 ; **chaque enregistrement source est persisté tel quel** dans `raw_record` (JSONB + numéro de ligne), et chaque fait normalisé référence son `raw_record`. Les rejets sont des `import_issue` reliés au `raw_record` fautif.

**Conséquences.** Traçabilité complète et bidirectionnelle, rejets explicables sans relire le fichier. Coût : volume en base — accepté puisque le sujet demande de travailler sur des extraits de taille raisonnable. Une purge des `raw_record` d'imports anciens reste possible ; c'est précisément pourquoi le bilan est figé dans `import_run` (voir [DATA_MODEL.md](DATA_MODEL.md) §5).

---

## ADR-009 — Une valeur absente reste absente

**Statut :** accepté

**Contexte.** « Une donnée indisponible ne doit pas devenir un zéro. Les métriques non comparables entre sources doivent rester séparées ou être signalées. »

**Décision.** `NULL` en base, `None` dans le domaine, `null` dans l'API. Chaque agrégat est accompagné d'un objet `coverage` (présents / total / ratio). Chaque `MetricDefinition` porte un attribut `comparability` ; une métrique `per_source_only` déclenche un `warning` explicite dans la réponse si elle est demandée toutes sources confondues.

**Conséquences.** Le contrat d'API est un peu plus verbeux, et le front doit gérer l'affichage de la couverture — c'est documenté dans [API.md](API.md) §9. En échange, aucun chiffre affiché ne peut être silencieusement faux, ce qui est le critère de justesse du sujet.

---

## ADR-010 — Monolithe modulaire

**Statut :** accepté

**Contexte.** Le sujet le dit explicitement : « Un monolithe modulaire suffit. Aucun microservice n'est demandé. »

**Décision.** Un seul déployable applicatif, exécuté sous deux rôles (`api` et `worker`) partageant le même code. La modularité est interne : couches + ports.

**Conséquences.** Un `docker compose up` suffit à tout démarrer. Les frontières internes étant des interfaces explicites, une extraction ultérieure resterait possible — mais elle n'est ni faite, ni prévue, ni nécessaire.

---

## ADR-011 — Le mapping impératif est impossible sur nos entités : traduction explicite

**Statut :** proposé — à trancher en revue (complète [ADR-003](#adr-003--sqlalchemy-20-en-mapping-impératif--alembic))

**Contexte.** ADR-003 prévoit d'associer les entités du domaine aux tables par `registry.map_imperatively()`. À l'implémentation du Lot B, cette approche s'avère **techniquement impossible en l'état** : les entités du Lot A sont des `@dataclass(frozen=True)`, et SQLAlchemy doit poser un attribut `_sa_instance_state` sur chaque instance qu'il persiste ou charge.

Vérifié, pas supposé :

```
map_imperatively : OK
insert           : ECHEC -> FrozenInstanceError: cannot assign to field '_sa_instance_state'
```

`map_imperatively()` accepte la classe sans broncher ; l'échec ne survient qu'au premier `INSERT`. Un mapping impératif « qui compile » ne prouve donc rien.

Deux écarts structurels s'ajoutent au gel des dataclasses :

1. **Forme.** Les entités portent des *noms* (`agent_name`, `model_name`, `tool_name`) là où les tables portent des *références* (`agent_id`, `model_id`, `tool_id`) — c'est précisément la normalisation 3NF de [DATA_MODEL.md](DATA_MODEL.md) §4. `ModelCall` imbrique par ailleurs un `TokenUsage`, alors que la table a des colonnes plates.
2. **Identité.** Le domaine et les ports utilisent des `UUID` ; `DATA_MODEL.md` et le contrat d'API publié utilisent des `BIGINT GENERATED ALWAYS AS IDENTITY` (`{"id": 12}`, `{"tool_id": 4}`). Onze issues frontend dépendent déjà de la forme entière.

**Décision.** Les tables sont écrites en SQLAlchemy Core et **restent conformes à DATA_MODEL.md** (donc au contrat d'API déjà publié). Le module `orm_registry.py` prévu par ADR-003 n'est pas créé. La traduction entité ↔ ligne sera écrite à la main dans les repositories (Data Mapper explicite), au moment où elle sert réellement — issue #45.

**Alternatives écartées.**

- *Dégeler les dataclasses du domaine.* Coût réel : `Deduplicator` s'appuie sur leur hachabilité, et l'immuabilité est un choix délibéré du Lot A. On paierait une régression du domaine pour un confort d'infrastructure — exactement l'inversion que la Clean Architecture cherche à éviter.
- *Passer les tables en UUID.* Aligne le domaine, mais casse le contrat d'API déjà publié et les onze issues frontend en cours.

**Conséquences.** Le domaine reste totalement ignorant de SQLAlchemy — l'objectif d'ADR-003 est donc atteint, plus complètement même qu'avec l'instrumentation, qui aurait modifié les classes du domaine au moment de l'import. Coût : la traduction est écrite à la main plutôt que déduite, soit quelques dizaines de lignes par agrégat, entièrement testables sans base.

**Reste à trancher (issue #45).** Comment réconcilier l'identité `UUID` du domaine avec le `BIGINT` de la base. Recommandation : ajouter une colonne `uuid UNIQUE` aux trois tables de faits — les ports (`get(session_id: UUID)`) restent applicables, le contrat d'API garde ses entiers, et le coût est une migration. Cela suppose une PR sur `DATA_MODEL.md`, qui reste la source de vérité du schéma.

---

## ADR-012 — L'identité persistante appartient à la base, l'UUID est une corrélation de lot

**Statut :** accepté (tranche la question laissée ouverte par [ADR-011](#adr-011--le-mapping-impératif-est-impossible-sur-nos-entités--traduction-explicite))

**Contexte.** ADR-011 laissait ouverte la réconciliation entre l'`UUID` porté par les entités du domaine et le `BIGINT GENERATED ALWAYS AS IDENTITY` des tables, et recommandait d'ajouter une colonne `uuid UNIQUE` aux tables de faits pour que les ports `get(session_id: UUID)` restent applicables.

**Cette recommandation était fausse.** `RecordNormalizer` génère ces identifiants avec `uuid4()`, à chaque normalisation :

```python
id=uuid4(),   # record_normalizer.py, lignes 179, 224, 284
```

Ils sont donc **aléatoires et non reproductibles** : relire le même fichier produit d'autres UUID. Les persister reviendrait à stocker une valeur qui ne désigne rien de stable, et sur laquelle aucune recherche ultérieure ne pourrait s'appuyer. La colonne aurait coûté une migration pour ranger du bruit.

**Décision.** Deux identités distinctes, chacune avec son rôle :

- **L'`UUID` est une corrélation *intra-lot*.** Il sert à un `ModelCall` pour désigner sa `Session` avant que l'une ou l'autre n'ait été écrite. Sa portée est une normalisation ; il ne quitte jamais le processus.
- **Le `BIGINT` est l'identité persistante.** La base l'attribue, l'API l'expose (`{"id": 12}`), les clés étrangères le référencent.

Les ports d'écriture prennent donc des entités et renvoient un `InsertOutcome` portant `assigned: dict[UUID, int]` — la correspondance qui permet de rattacher les enfants au parent qui vient d'être inséré. Les ports de lecture prennent l'identifiant de base : `get(session_id: int)`.

**Conséquences.** Aucune migration, aucune colonne de bruit. Les signatures des ports du Lot A qui annonçaient `UUID` en lecture sont corrigées — elles n'avaient aucune implémentation ni aucun appelant, le coût est nul. En contrepartie, `_to_session()` frappe un nouvel UUID à la lecture : il n'a pas de sens hors d'un lot d'import, et le code qui en dépendrait serait déjà en faute.

**Ce qui reste vrai d'ADR-011.** Le domaine reste ignorant de SQLAlchemy, et la traduction entité ↔ ligne est écrite à la main. C'est cette traduction explicite qui rend la distinction ci-dessus visible plutôt qu'implicite.

---

## ADR-013 — Authentification par API Key et CORS

**Statut :** accepté

**Contexte.** L'API était ouverte sur le réseau local : n'importe quel client pouvait importer des fichiers et lire les traces. Le frontend tourne sur un autre port (Vite, 5173) ; sans CORS le navigateur bloque les appels.

**Décision.** Un middleware FastAPI exige le header `X-API-Key` sur toutes les routes sauf `/health` et `/version`. La clé vient de `API_KEY`. Les origines autorisées viennent de `ALLOWED_ORIGINS` (liste CSV). Comparaison en temps constant (`hmac.compare_digest`) ; la valeur n'est jamais journalisée.

**Alternatives.** JWT / sessions : trop lourd pour un monolithe de sprint, et le front n'a pas d'utilisateurs nommés. Basic Auth : moins pratique à envoyer depuis `fetch` et à documenter dans OpenAPI.

**Conséquences.** Le navigateur ne détient jamais la clé (#149) : toute variable `VITE_*` est inscrite par Vite dans le bundle JavaScript, que n'importe quel visiteur peut lire. C'est le proxy placé devant l'API qui ajoute `X-API-Key` à chaque appel `/api` : nginx dans la stack Docker, depuis la variable `API_KEY` du conteneur `frontend` lue au démarrage (ni l'image ni le bundle ne la contiennent), et le proxy Vite avec `npm run dev`, depuis `API_KEY` sans préfixe `VITE_`. La clé ferme donc l'accès direct à l'API ; derrière le proxy, identifier la personne relève de la session utilisateur. Un oubli de `API_KEY` en production ferme toute l'API (401) et empêche le conteneur `frontend` de démarrer, ce qui est le comportement voulu.

**Amendement (#162).** `/docs`, `/redoc` et `/openapi.json` rejoignent les chemins publics : un navigateur qui ouvre `/docs` ne peut pas joindre de header, et le document ne décrit que des routes qui exigent toujours la clé. Le middleware restant hors du graphe de dépendances de FastAPI, `interfaces/http/openapi.py` déclare la clé et l'enveloppe d'erreur dans le schéma généré, sans rien appliquer. `/version` ne renvoie plus que la version applicative ; les révisions de schéma passent sur `/health/ready`, derrière la clé.

