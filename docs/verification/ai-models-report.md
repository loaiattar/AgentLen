# Compte rendu de vérification — parcours d'identification et d'import

Exécuté le **2026-09-10** sur la branche `22-docs-produire-ai-models-report…`,
base `develop` @ `90eefec`.

Ce document rend compte du parcours complet **upload → profilage → proposition →
prévisualisation → import** conduit contre un serveur réel : API FastAPI,
PostgreSQL 16, worker d'import, et un fournisseur de modèles interrogé par
l'adaptateur `openai_compatible`. Rien n'est simulé ; tous les chiffres qui
suivent sortent de cette exécution.

> **Ce rapport ne remplit pas encore la case « deux modèles ».** Une seule des
> trois configurations essayées a pu mener le parcours à son terme. Les deux
> autres ont échoué pour des raisons mesurées et reproductibles, documentées en
> §3 : ce sont des résultats de vérification, pas des cases à cocher manquantes.
> Le complément est décrit en §6.

---

## 1. Environnement

| | |
|---|---|
| Machine | Linux 7.2.4, 14 Gio de RAM, **inférence 100 % CPU** (aucun GPU) |
| Fournisseur | Ollama, joint par `AI_PROVIDER=openai_compatible` sur `http://localhost:11434/v1` |
| Base | PostgreSQL 16 en conteneur, migrations `0001` → `0003` appliquées |
| Application | API et worker lancés localement sur le code de la branche |
| Version de prompt | `analysis-v3` |

Deux ajustements ont été nécessaires **avant** de pouvoir lancer quoi que ce
soit. Ils sont décrits en §5 parce qu'ils constituent des constats à part
entière, pas des détails d'installation.

## 2. Fichiers de trace

Deux fichiers JSONL synthétiques, volontairement écrits avec des noms de champs
**différents** du modèle AgentLen pour que le mapping soit un vrai travail
d'identification et non une correspondance de noms.

| Fichier | Enreg. | Octets | Champs feuilles | Rôle |
|---|---|---|---|---|
| `trace_compacte.jsonl` | 40 | 14 070 | 10 | proposition |
| `trace_bis.jsonl` | 40 | 12 006 | 10 | import réel (empreinte différente) |

Les dix champs profilés :

```
$.run_id                            $.llm_calls[].i
$.assistant                         $.llm_calls[].model
$.repo                              $.llm_calls[].prompt_tokens
$.started                           $.llm_calls[].completion_tokens
$.elapsed_seconds
$.result
```

`$.elapsed_seconds` est un piège délibéré : la cible s'appelle `duration_ms`, il
faut donc soit l'opérateur `unit_convert`, soit une ambiguïté signalée.

**Pourquoi un fichier aussi petit.** Ollama sert ces modèles avec une fenêtre de
contexte de 4 096 jetons par défaut. Le prompt d'analyse pour ce profil pèse
déjà ≈ 2 270 jetons ; un profil plus large le fait dépasser la fenêtre, et le
serveur tronque alors le début du prompt — c'est-à-dire les règles et la forme
de réponse. Le fichier a été dimensionné pour que la question posée soit la
qualité du modèle, pas la troncature.

---

## 3. Les trois configurations

### Configuration A — `qwen2.5:7b` ✅ parcours complet

**Bascule :** `AI_PROVIDER=openai_compatible AI_BASE_URL=http://localhost:11434/v1 AI_MODEL=qwen2.5:7b`

| Étape | Résultat | Durée |
|---|---|---|
| 1. Upload | `file_id=2`, 12 006 octets | < 1 s |
| 2. Profilage | 10 champs feuilles détectés | < 1 s |
| 3. Proposition | 2 entités, 3 règles, **valide** | **274,9 s** |
| 4. Ambiguïtés signalées | **aucune** | — |
| 5. Corrections apportées | aucune | — |
| 6. Prévisualisation | échantillon 20 → `session` 20, `model_call` 0, `tool_call` 0, **0 rejet** | < 1 s |
| 7. Import | **40 lus, 40 importés, 0 doublon, 0 rejet** | 1 s |

Le mapping proposé, tel qu'enregistré :

```json
{ "target": "session", "natural_key": ["external_id"],
  "fields": [
    { "target": "external_id", "source": "$.run_id" },
    { "target": "duration_ms", "source": "$.elapsed_seconds",
      "operators": [{ "op": "unit_convert", "from": "s", "to": "ms" }] } ] }
{ "target": "model_call", "natural_key": ["sequence_index"],
  "iterate": "$.llm_calls[]",
  "parent": { "entity": "session", "via": "external_id" },
  "fields": [ { "target": "sequence_index", "source": "$.i" } ] }
```

**Ce que le modèle a réussi.** La structure est juste, et c'est la partie
difficile : il a reconnu qu'une entité imbriquée se tire d'une liste du fichier
(`iterate`), il a rattaché correctement l'enfant au parent (`parent … via
external_id`), il a choisi `external_id` comme clé naturelle, et **il n'est pas
tombé dans le piège des secondes**. La vérification en base le confirme — une
session dont `elapsed_seconds` valait 154 porte `duration_ms = 154000` :

```
 external_id | duration_ms | outcome | agent_id
-------------+-------------+---------+----------
 bis_000     |      154000 |         |
 bis_001     |       44000 |         |
```

**Ce que le modèle a raté, et c'est l'essentiel.** Trois règles sur dix champs
profilés. `$.assistant`, `$.repo`, `$.started`, `$.result` et les trois champs
d'usage de jetons ne sont mappés nulle part, alors que le schéma cible offre
`agent_name`, `repository_url`, `started_at`, `outcome`, `input_tokens`,
`output_tokens`. Les colonnes correspondantes sont vides en base.

Pire pour l'exploitation : l'entité `model_call` est déclarée mais ne porte que
`sequence_index`, si bien qu'elle **ne produit aucune ligne** — la
prévisualisation l'annonçait déjà (`model_call: 0`) et la base le confirme :

```
session    : 40
model_call :  0
tool_call  :  0
raw_record : 40
```

Et surtout : `unmapped_fields` est renvoyé **vide**. La règle 5 du prompt
demande explicitement de déclarer ce qui n'a pas pu être interprété. Le modèle
laisse sept champs de côté et affirme n'en avoir laissé aucun. Un mapping
*valide* n'est pas un mapping *bon*, et le validateur ne peut pas faire la
différence : c'est exactement pourquoi le parcours impose une validation
humaine avant l'import.

**Fiabilité.** À la température par défaut d'Ollama, la proposition n'aboutit
**qu'environ une fois sur quatre** : sur les tentatives enregistrées, trois
échecs consécutifs puis une réussite, puis à nouveau trois échecs pour une
réussite. Chaque tentative coûte ≈ 3 à 5 minutes sur CPU. Voir §5 pour la cause.

Trace d'un déroulement complet de la boucle (6 tours, 5 outils distincts) :

```
tour 1 : get_target_schema      17 jetons
tour 2 : validate_mapping      183 jetons
tour 3 : preview_import        142 jetons
tour 4 : get_sample_values      23 jetons
tour 5 : get_field_profile      22 jetons
tour 6 : réponse finale        487 jetons
```

### Configuration B — `qwen2.5:3b` ❌ incapable

**Bascule :** `AI_MODEL=qwen2.5:3b`

Le parcours s'arrête à l'étape 3. Le modèle ne produit jamais de document
exploitable : la réponse revient avec `finish_reason: stop`, **aucun appel
d'outil et un contenu vide**, alors que l'usage rapporte 163 jetons de
complétion générés. Autrement dit, le modèle écrit quelque chose que la couche
de compatibilité OpenAI d'Ollama n'arrive pas à interpréter et jette
silencieusement.

Ce n'est pas de la malchance : **à `temperature=0`, l'échec est déterministe**,
identique sur deux tentatives consécutives. Réessayer est inutile.

| Tentative | Durée | Résultat |
|---|---|---|
| 1 | 207 s | 502 — aucun document exploitable |
| 2 | 66 s | idem |
| 3 | 20 s | idem |
| 4-5 (`temperature=0`) | 30 s | idem, à l'identique |

### Configuration C — `qwen2.5:14b` ❌ ne tient pas en mémoire

Le modèle se charge (9,9 Gio) mais le serveur ferme la connexion en cours de
requête : `RemoteProtocolError: Server disconnected without sending a response`.
Avec 14 Gio de RAM dont une partie prise par PostgreSQL, l'API et le worker, il
n'y a pas la place. Aucune mesure exploitable.

---

## 4. Comparaison

Le sujet demande de commenter les différences entre les deux modèles. Sur ce
matériel, la différence utile ne porte pas sur la *qualité* des propositions
mais sur la **capacité à en produire une** :

| | `qwen2.5:3b` | `qwen2.5:7b` | `qwen2.5:14b` |
|---|---|---|---|
| Termine le parcours | jamais | ≈ 1 fois sur 4 | jamais lancé |
| Appelle les outils | non | oui, 5 outils distincts | — |
| Structure (`iterate`/`parent`) | — | correcte | — |
| Piège secondes/ms | — | traité par `unit_convert` | — |
| Couverture des champs | — | 3 / 10 | — |
| Latence par proposition | — | ≈ 275 s | — |

La lecture est nette : **il existe un seuil de taille en dessous duquel le
modèle ne sait pas tenir le contrat d'appel d'outils**, et 3 milliards de
paramètres sont sous ce seuil. Au-dessus, à 7 milliards, la structure devient
correcte mais la couverture reste faible et la reproductibilité mauvaise.

À titre de repère mesuré le même jour sur le même harnais, deux modèles
hébergés (`gpt-4o` et `gpt-4o-mini`, via un point d'accès compatible OpenAI)
avaient produit respectivement **25 règles sur 3 entités** et **3 règles sur
2 entités**, en 2 tours et 13 secondes pour le premier. L'écart de couverture
entre un modèle hébergé de premier plan et `qwen2.5:7b` local est donc d'un
facteur ≈ 8 sur ce même fichier.

---

## 5. Constats de vérification

Cinq problèmes trouvés **en exécutant** le parcours, dont aucun n'apparaissait
en relecture.

### 5.1 `POST /mappings/proposals` est cassé sur `develop` — bloquant

`interfaces/http/routers/ai.py` construit `ProfileFileCommand` sans passer
`format`. Or le stockage écrit des chemins adressés par contenu, **sans
extension**, et `infer_format` lève alors :

```
ValueError: Cannot infer a supported format from path:
  '.../storage/uploads/14/14293aab01d7345a2a95ca56d432aea7…'
```

La route répond 500 avant d'atteindre le modèle. Aucun parcours n'est possible
sans ce correctif ; il a été appliqué localement pour produire ce rapport. Il
est déjà porté par la PR #107 (et, autrement, par #103).

### 5.2 Un hôte local sans clé reste refusé

`AI_PROVIDER=openai_compatible` vers Ollama échoue en `Aucune clé configurée
pour 'openai_compatible'`. Contournement employé ici : renseigner
`AI_API_KEY` avec une valeur factice qu'Ollama ignore. Corrigé par la PR #111.

### 5.3 Le bloc `## OPERATOR STEER` fait échouer `qwen2.5:7b`

Le constat le plus net du parcours. À modèle, fichier et température
identiques :

- **sans** `hint` → la boucle se déroule entièrement, 6 tours, proposition valide ;
- **avec** `hint` → échec au **premier tour**, 179 jetons générés puis jetés par
  la couche de compatibilité, aucun appel d'outil.

Le bloc d'instruction opérateur — pourtant fondé, il sépare structurellement la
donnée de la consigne — suffit à faire sortir ce modèle du format d'appel
d'outils. Sur un modèle local de cette taille, la fonction de reprise décrite
dans `AGENT.md` §7 est donc inutilisable en pratique.

### 5.4 L'adaptateur n'envoie jamais `temperature`

Ollama applique alors sa valeur par défaut (≈ 0,8) : **deux analyses du même
fichier ne donnent pas le même mapping**. Pour un outil dont la sortie décide de
la façon dont des données sont importées, la non-reproductibilité est un
problème en soi — et c'est la cause directe du taux de réussite de 1 sur 4.

Un paramètre `AI_TEMPERATURE` a été ajouté localement pour cette vérification :
à 0, les réponses deviennent strictement identiques d'une exécution à l'autre.
Il n'est envoyé qu'en dialecte OpenAI — **les modèles Claude récents refusent ce
paramètre avec un 400**, il ne doit donc jamais partir vers l'API Anthropic.

### 5.5 Une réponse vide ne se distingue pas d'un silence

Quand la couche de compatibilité jette les jetons produits (§3, configuration
B), l'opérateur lit « Le fournisseur n'a pas renvoyé de document JSON
exploitable » sans aucun moyen de savoir que le modèle *a* répondu et que
163 jetons ont été perdus en route. Distinguer ce cas — `finish_reason: stop`,
contenu vide, aucun appel d'outil, mais `completion_tokens > 0` — rendrait le
diagnostic immédiat.

---

## 6. Ce qui reste à produire

La case « deux configurations avec des modèles distincts » du sujet n'est pas
remplie : une seule configuration a mené le parcours à terme.

Ce qui manque n'est pas du travail d'implémentation mais un modèle de plus
capable de tenir la boucle d'outils. Trois voies, par ordre de coût :

1. **Un point d'accès hébergé compatible OpenAI** (`AI_BASE_URL` + une clé) —
   les deux modèles déjà mesurés sur ce harnais terminent le parcours en
   quelques secondes. C'est la voie la moins chère et la plus rapide.
2. **L'API Anthropic**, qui couvrirait en plus l'adaptateur `anthropic` — jamais
   exercé contre un vrai serveur à ce jour.
3. **Une machine avec plus de mémoire ou un GPU**, qui rendrait `qwen2.5:14b`
   utilisable et rendrait les mesures locales représentatives.

Le harnais est en place : la même commande produit le tableau du §3 pour
n'importe quel modèle accessible.

---

## Annexe — reproduire

```sh
docker compose -f docker/docker-compose.yml up -d db
alembic upgrade head
AI_PROVIDER=openai_compatible \
AI_BASE_URL=http://localhost:11434/v1 \
AI_API_KEY=valeur-factice-ignoree-par-ollama \
AI_MODEL=qwen2.5:7b \
AI_MAX_OUTPUT_TOKENS=1500 AI_TIMEOUT_SECONDS=900 \
  uvicorn agentlen.interfaces.http.app:create_app --factory --port 8010
```

Puis, dans l'ordre : `POST /files`, `POST /files/{id}/profile`,
`POST /mappings/proposals`, `POST /mappings`, `POST /imports/preview`,
`POST /imports`, `GET /imports/{id}`, `GET /imports/{id}/issues`.

Aucune clé d'API, aucune donnée personnelle et aucun contenu de trace réelle ne
figure dans ce document : les deux fichiers utilisés sont synthétiques.
