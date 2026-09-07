# AgentScope — Décisions d'architecture (ADR)

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
