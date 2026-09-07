# Conventions de travail — AgentScope

> Ce document est **contraignant** pour tous les membres de l'équipe. Il est court volontairement : ce qui n'est pas écrit ici ne s'invente pas en cours de route, ça se discute et ça s'ajoute par PR.

---

## 0. Pourquoi ces règles

Trois raisons, dans cet ordre :

1. **On travaille à plusieurs en parallèle sur 4 jours.** Sans convention, on passe le jour 4 à résoudre des conflits au lieu de livrer.
2. **Le suivi GitHub est noté** (3 points sur 20) : issues, tableau, revues de PR. Le tableau doit refléter le travail réel, pas être rempli la veille du rendu.
3. **L'architecture est notée 7 points sur 20.** La revue de PR est notre seul filet de sécurité contre la dérive architecturale.

---

## 1. Modèle de branches

**On utilise GitHub Flow, pas Git Flow complet.**

```
main  ──●────●────●────●────●──► (toujours déployable, protégée, taguée v0.1.0)
         \        /     \    /
          ●──●───●       ●──●
       feat/12-import  fix/28-tokens
```

Git Flow (`develop` + `release/*` + `hotfix/*`) est conçu pour des logiciels versionnés avec plusieurs versions en production simultanée. Sur un sprint de 4 jours avec une seule release, `develop` ne serait qu'une copie de `main` qui double les merges et les conflits, sans rien apporter. **Une branche longue en moins = une source de conflits en moins.**

### Règles

| Règle | Détail |
|---|---|
| `main` est protégée | Aucun push direct, jamais. Même pour un typo. |
| `main` est toujours verte | Si la CI casse sur `main`, c'est la priorité absolue de tout le monde. |
| Une branche = une issue | Pas de branche fourre-tout, pas de branche partagée entre deux personnes. |
| Durée de vie < 1 jour | Au-delà, la branche diverge trop. Découpe l'issue. |
| On resynchronise souvent | `git pull --rebase origin main` au moins une fois par jour. |

### Nommage

```
<type>/<numéro-issue>-<slug-court>
```

```
feat/12-import-jsonl
fix/28-token-null-handling
docs/34-adr-ai-adapter
refactor/41-extract-mapping-validator
test/47-idempotence-reimport
chore/52-docker-compose
ci/55-import-linter
```

Types autorisés : `feat` · `fix` · `docs` · `refactor` · `test` · `chore` · `ci` · `perf`

---

## 2. Commits

**Conventional Commits**, en français ou en anglais — mais **une seule langue pour tout le projet** (décision : *français* pour les messages, *anglais* pour le code et les identifiants).

```
<type>(<scope>): <description à l'impératif, minuscule, sans point final>

[corps optionnel : le POURQUOI, pas le QUOI]

Refs #12
```

### Scopes

Ils suivent l'architecture — c'est volontaire, ça rend visible dans `git log` quelle couche bouge :

`domain` · `application` · `infra` · `api` · `db` · `ai` · `docs` · `ci` · `deps`

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
| **Terminé** | Fusionné dans `main` | PR mergée, issue fermée automatiquement |

**On déplace la carte au moment où ça se passe, pas le vendredi.** Le tableau est une trace de travail, pas un livrable rétroactif — et ça se voit.

### Definition of Done

Une issue n'est terminée que si **tout** est vrai :

- [ ] Le code fait ce que l'issue demandait
- [ ] Les tests associés existent et passent
- [ ] La CI est verte (`ruff`, `mypy`, `import-linter`, `pytest`)
- [ ] La doc impactée est à jour (architecture, API, ADR)
- [ ] La PR a été relue et approuvée par **un autre membre**
- [ ] Rien n'est cassé sur `main` après le merge

---

## 4. Pull requests

### Règles

| Règle | Pourquoi |
|---|---|
| **1 approbation obligatoire** avant merge | Exigence du sujet, et vrai filet anti-dérive |
| **Jamais s'auto-approuver ni s'auto-merger** | Même règle pour tout le monde, y compris qui a créé le dépôt |
| **PR liée à une issue** (`Closes #12`) | Sinon l'issue reste ouverte et le tableau ment |
| **CI verte obligatoire** | Non négociable |
| **< 400 lignes modifiées** (indicatif) | Au-delà, la revue devient du survol et ne sert plus à rien |
| **Squash merge uniquement** | Historique `main` linéaire et lisible : 1 issue = 1 commit |
| **Supprimer la branche après merge** | On garde la liste des branches lisible |

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
# Démarrer une tâche
git switch main
git pull origin main
git switch -c feat/12-import-jsonl

# Se resynchroniser en cours de route (au moins 1×/jour)
git fetch origin
git rebase origin/main

# Publier
git push -u origin feat/12-import-jsonl
```

**On rebase sa branche sur `main`, on ne merge pas `main` dans sa branche.** L'historique reste lisible et les PR ne se remplissent pas de commits de merge parasites.

**On ne force-push jamais sur une branche relue par quelqu'un d'autre** sans le prévenir. Sur sa propre branche non encore relue, `git push --force-with-lease` (jamais `--force` seul).

**En cas de conflit :** c'est à l'auteur de la branche de le résoudre, pas au relecteur ni au dernier qui merge.

---

## 6. Rythme d'équipe

| Moment | Quoi |
|---|---|
| **Matin, 10 min** | Point debout : ce que j'ai fini, ce que je prends, ce qui me bloque. On met le tableau à jour **pendant** le point. |
| **En continu** | On intègre dès qu'une tranche est fonctionnelle. Pas de « je merge tout vendredi ». |
| **Fin de journée** | Toute branche en cours est poussée, même incomplète (PR en *draft*). Une machine qui plante ne doit pas coûter une journée à l'équipe. |
| **Fin de journée** | `main` doit être verte et démontrable. |

**Anti-pattern à éviter absolument :** quatre personnes qui travaillent 3 jours en isolation et intègrent le jeudi soir. C'est le scénario d'échec le plus courant sur ce type de sprint.

---

## 7. Structure du dépôt

```
.
├── src/agentscope/          # code applicatif (voir docs/architecture/)
├── tests/{unit,integration,e2e}/
├── alembic/                 # migrations
├── docker/
├── docs/
│   ├── CONTRIBUTING.md      # ce document
│   ├── architecture/        # architecture, modèle de données, ADR, contrat d'API
│   └── sujet/               # énoncé de référence
├── .github/                 # workflows CI + gabarits d'issue et de PR
├── LICENSE                  # MIT
└── README.md
```

**Le code source ne va jamais à la racine.** La documentation ne va jamais ailleurs que dans `docs/`.

---

## 8. Qualité — ce que la CI vérifie à chaque PR

| Étape | Outil | Bloquant |
|---|---|---|
| Format et lint | `ruff format --check`, `ruff check` | oui |
| Typage | `mypy --strict` sur `domain/` et `application/` | oui |
| **Règle de dépendance** | `import-linter` | **oui** |
| Tests | `pytest` (unit + intégration + e2e) | oui |
| Secrets | scan de secrets | oui |

`import-linter` est notre garde-fou architectural : il fait échouer toute PR où `domain/` importerait `sqlalchemy`, `fastapi`, `polars` ou un SDK IA. **Si tu es tenté de désactiver cette règle, ouvre une discussion — ne la contourne pas.**

### Avant de pousser

```bash
make lint     # ruff + mypy + import-linter
make test     # pytest
```

---

## 9. Sécurité — règles absolues

1. **Aucune clé API dans le dépôt.** Jamais, même temporairement, même dans une branche non fusionnée. Un secret poussé une fois est compromis, même après suppression du commit.
2. `.env` est dans `.gitignore`. Seul `.env.example` est versionné, **sans valeurs**.
3. **Aucune donnée sensible** dans les fixtures de test, les captures d'écran ou les issues.
4. **Aucun dataset** n'est ajouté au dépôt sans vérifier ses conditions de redistribution. Par défaut : on documente la référence et la méthode de récupération, on ne copie pas les fichiers.
5. Si un secret est poussé par erreur : **le révoquer immédiatement** chez le fournisseur, puis prévenir l'équipe. Le retirer de l'historique vient après — la révocation d'abord.

---

## 10. Releases

- Versionnage sémantique : `v0.1.0` pour la livraison de vendredi.
- Un tag est posé sur `main` uniquement, après CI verte.
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
