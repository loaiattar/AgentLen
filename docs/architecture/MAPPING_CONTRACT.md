# AgentLen — Contrat de mapping

> C'est **le cœur du projet** : l'artefact qui permet d'intégrer une source inconnue *par configuration*, sans écrire de code ni redéployer.
> Voir aussi : [ARCHITECTURE.md](ARCHITECTURE.md) · [DATA_MODEL.md](DATA_MODEL.md)

---

## 1. Principe

Un **mapping** est un document JSON versionné, stocké en base, qui décrit comment transformer les enregistrements d'un fichier source en entités du modèle AgentLen.

```
Fichier source ──► profilage ──► [IA] proposition ──► validation ──► correction humaine
                                                                          │
                                                                          ▼
                                                              mapping enregistré (versionné)
                                                                          │
                                          moteur de transformation ◄───────┘
                                                     │
                                                     ▼
                                        entités du domaine + rejets expliqués
```

Quatre règles non négociables :

1. **L'IA produit ce document, rien d'autre.** Elle n'écrit jamais en base, ne génère jamais de SQL, ne produit jamais de code.
2. **Le document est validé avant toute application.** Schéma JSON strict + whitelist d'opérateurs + vérification des champs cibles contre le schéma réel de la base.
3. **Le moteur n'exécute que des opérateurs déclarés.** Il n'y a ni `eval`, ni `exec`, ni import dynamique, ni expression arbitraire. Un opérateur inconnu est une **erreur de validation**, jamais une tentative d'exécution.
4. **Une valeur inconnue reste `null`.** Elle ne devient jamais implicitement `0`, `false`, une date ou une clé synthétique. Un changement de type exige un opérateur explicite ; sinon l'entité est rejetée avec `TYPE_MISMATCH`.

---

## 2. Structure d'un mapping

```jsonc
{
  "mapping_version": "1.0",
  "name": "tracelab-jsonl",
  "source_format": "jsonl",              // jsonl | csv | parquet
  "description": "Traces Claude Code et Codex publiées par TraceLab",

  "record": {
    "mode": "per_line",                  // per_line | per_row
    "root": "$"                          // racine de l'enregistrement
  },

  "entities": [
    {
      "target": "session",
      "natural_key": ["external_id"],    // base de l'idempotence
      "fields": [
        { "target": "external_id", "source": "$.session_id", "required": true,
          "operators": [{ "op": "cast", "to": "string" }] },

        { "target": "agent_name", "source": "$.agent",
          "operators": [{ "op": "map_values",
                          "table": { "claude_code": "claude-code", "codex_cli": "codex" },
                          "on_unknown": "passthrough" }] },

        { "target": "started_at", "source": "$.start_time",
          "operators": [{ "op": "parse_datetime", "format": "unix_seconds",
                          "timezone": "UTC" }] },

        { "target": "outcome", "source": "$.outcome", "required": false }
      ]
    },
    {
      "target": "model_call",
      "iterate": "$.llm_calls[]",        // 1 enregistrement -> N lignes (§2.1)
      "parent": { "entity": "session", "via": "external_id" },
      "natural_key": ["sequence_index"],
      "fields": [
        { "target": "sequence_index", "source": "$.index" },
        { "target": "started_at",     "source": "$.started_at",
          "operators": [{ "op": "parse_datetime", "format": "iso8601",
                          "timezone": "UTC" }] },
        { "target": "model_name",     "source": "$.model" },
        { "target": "provider_name",  "source": "$.provider",
          "operators": [{ "op": "default", "value": "unknown" }] },
        { "target": "input_tokens",   "source": "$.usage.input_tokens",
          "operators": [{ "op": "cast", "to": "integer", "on_error": "reject" }] },
        { "target": "output_tokens",  "source": "$.usage.output_tokens",
          "operators": [{ "op": "cast", "to": "integer", "on_error": "reject" }] },
        { "target": "duration_ms",    "source": "$.latency_s",
          "operators": [{ "op": "unit_convert", "from": "s", "to": "ms" }] }
      ]
    },
    {
      "target": "tool_call",
      "iterate": "$.tool_uses[]",
      "parent": { "entity": "session", "via": "external_id" },
      "natural_key": ["sequence_index"],
      "fields": [
        { "target": "sequence_index", "source": "$.index" },
        { "target": "tool_name",      "source": "$.tool_uses[].name", "required": true },
        { "target": "status",         "source": "$.error",
          "operators": [{ "op": "map_values",
                          "table": { "null": "ok" }, "on_unknown": "constant",
                          "constant": "error" }] },
        { "target": "started_at",     "source": "$.started_at",
          "operators": [{ "op": "parse_datetime", "format": "iso8601",
                          "timezone": "UTC" }] }
      ]
    }
  ],

  "unmapped_policy": "keep_raw",   // le brut reste dans raw_record.payload
  "notes": "Le champ 'cache_read_tokens' est absent de cette source : laissé NULL."
}
```

### 2.1 Notation des chemins

`source`, `iterate` et les `sources` de `coalesce`, `concat` et `hash` s'écrivent **dans la notation que le profileur met dans le `FileProfile`** : l'agent recopie ce qu'il lit, le moteur résout ce que l'agent recopie. Elle est implémentée une seule fois (`domain/services/json_path.py`), partagée par le validateur et le moteur.

| Notation | Sens | Exemple |
|---|---|---|
| `$` | l'enregistrement (sous `iterate`, l'élément parcouru) | `$` |
| `.nom` | membre d'un objet ; `nom` est un identifiant simple `[A-Za-z_][A-Za-z0-9_]*` | `$.usage.input_tokens` |
| `["nom"]` | membre dont le nom n'est pas un identifiant simple ; `\\` et `\"` sont les seuls échappements | `$["a.b"]` |
| `[]` | chaque élément d'une liste | `$.tools[]`, `$.tools[].tool_name` |

- **Dans `iterate`**, chaque élément atteint est une ligne : `$.llm_calls[]` produit une ligne par appel, et `[]` peut se répéter (`$.turns[].tools[]`). Un `iterate` qui ne finit pas par `[]` est lu comme s'il le faisait : `$.llm_calls` vaut `$.llm_calls[]`.
- **Dans `source`**, le chemin désigne une valeur de l'élément parcouru, écrite relativement à lui (`$.name`) ou en répétant le chemin d'`iterate`, comme le profil l'écrit (`$.tool_uses[].name` sous `"iterate": "$.tool_uses[]"`). Tout autre `[]` y est refusé, car un champ ne reçoit qu'une valeur ; une liste entière se garde avec `$.tool_uses`.
- **Refusé à la validation**, avec le code `MAPPING_UNSUPPORTED_PATH`, le `field_path` fautif (`entities[target=model_call].iterate`, `entities[target=session].fields[target=external_id].source`) et la raison : filtre `[?(...)]`, joker `*`, index ou tranche `[0]`, descente récursive `..`, guillemets simples, échappement inconnu, guillemet non fermé, chemin qui ne commence pas par `$`. Aucune expression n'est évaluée.
- **À l'import**, un chemin absent ou `null` donne une valeur absente, et un `iterate` absent zéro ligne, sans issue. Un `iterate` qui rencontre une valeur d'un autre type, par exemple une chaîne là où la liste est attendue, produit l'issue `ITERATE_NOT_A_LIST` (rejet) au lieu de zéro ligne silencieuse.

---

## 3. Whitelist d'opérateurs

**Aucun autre opérateur n'existe.** Chacun est une classe implémentant `Operator` dans le domaine, avec ses propres tests unitaires.

| Opérateur | Paramètres | Effet |
|---|---|---|
| `cast` | `to` ∈ `string · integer · float · boolean`, `on_error` ∈ `reject · null` | Conversion typée |
| `parse_datetime` | `format` (ISO8601, `unix_seconds`, `unix_millis`, ou motif `strptime`), `timezone` | Produit un instant UTC |
| `default` | `value` | Valeur si la source est absente ou `null` |
| `coalesce` | `sources: [chemin, …]` | Premier chemin non nul (sources incohérentes entre versions) |
| `unit_convert` | `from`, `to` (`s`→`ms`, `min`→`ms`, `ns`→`ms`, `KB`→`B`…) | Conversion d'unité déclarée ; les unités cibles entières (`ms`, `B`) produisent un entier |
| `map_values` | `table`, `on_unknown` ∈ `passthrough · null · reject · constant` | Table de correspondance fermée |
| `trim`, `lower`, `upper` | — | Normalisation de chaîne |
| `regex_extract` | `pattern`, `group` | Extraction bornée (motif compilé, **timeout imposé**) |
| `concat` | `sources`, `separator` | Concaténation de chemins |
| `hash` | `algorithm: sha256`, `sources` | Clé naturelle synthétique ; renvoie `null` si toutes les sources sont absentes |
| `json_passthrough` | `max_bytes` | Conserve un sous-arbre JSON tel quel (colonnes JSONB) |

`split_rows` est réservé mais refusé tant qu'il n'existe pas dans le moteur ; une cardinalité multiple se déclare avec `entity.iterate`.

**Rejeté à la validation :** tout opérateur hors de cette liste, tout paramètre non déclaré, tout champ `target` inconnu du schéma, toute expression libre. `regex_extract` n'accepte que des motifs compilables avec une longueur bornée, pour écarter le *catastrophic backtracking*.

---

## 4. Validation

`MappingValidator` (domaine, sans I/O) applique quatre niveaux :

| Niveau | Vérifie | Exemple d'erreur |
|---|---|---|
| **Syntaxique** | Conformité au JSON Schema du mapping, notation des chemins (§2.1) | `entities[1].fields[0].target` manquant ; `MAPPING_UNSUPPORTED_PATH: Path '$.events[0]' is not supported` |
| **Sémantique** | Champs cibles existants, types compatibles, opérateurs whitelistés et paramètres valides | `MAPPING_UNKNOWN_TARGET: 'session.user_email' n'existe pas dans le schéma` ; `MAPPING_UNKNOWN_OPERATOR`, `INVALID_OPERATOR_PARAM` |
| **Structurel** | `natural_key` présente, complète et produite par les champs déclarés (ou `sequence_index` implicite d'une itération), `parent` résoluble, pas de cycle ; un appel non itéré déclare son `sequence_index` | `MAPPING_MISSING_NATURAL_KEY`, `MAPPING_INVALID_NATURAL_KEY: 'session_external_id' n'est pas produit`, `MAPPING_MISSING_SEQUENCE_INDEX` |
| **Exécution à blanc** | Application sur un échantillon réel | `CAST_FAILED ligne 42, $.usage.input_tokens = "n/a"` |

Une erreur retourne **toujours** : un `code` stable, le `field_path` fautif, et un message explicatif. C'est le test d'acceptation « un mapping invalide est refusé avec une explication ».

---

## 5. Ce que l'IA reçoit et ce qu'elle rend

### Entrée (jamais le fichier entier)

```jsonc
{
  "file_profile": {
    "format": "jsonl",
    "record_count": 12483,
    "fields": [
      { "path": "$.session_id", "types": ["string"], "null_ratio": 0.0,
        "distinct_ratio": 1.0, "examples": ["a3f2…", "b91c…"] },
      { "path": "$.usage.input_tokens", "types": ["integer","null"],
        "null_ratio": 0.12, "min": 12, "max": 184203, "examples": [1204, 8891] }
    ]
  },
  "sample_records": [ /* N enregistrements passés par le SampleSanitizer */ ],
  "target_schema": { /* description des entités et champs cibles */ },
  "allowed_operators": [ /* la whitelist, transmise explicitement */ ]
}
```

Le `SampleSanitizer` s'exécute avant tout appel : troncature des valeurs longues, masquage des motifs sensibles (clés API, jetons, e-mails, chemins absolus), limitation du nombre d'enregistrements. **Les statistiques du profil sont calculées par Polars, jamais estimées par le modèle.**

### Sortie

```jsonc
{
  "mapping": { /* le document décrit en §2 */ },
  "rationale": [
    { "target": "session.external_id", "source": "$.session_id",
      "confidence": "high",
      "explanation": "Chaîne unique sur 100 % des enregistrements, granularité session." }
  ],
  "ambiguities": [
    { "field": "$.duration",
      "question": "Secondes ou millisecondes ? Les valeurs (0.4–320) suggèrent des secondes.",
      "options": ["unit_convert s→ms", "unit_convert ms→ms"] }
  ],
  "unmapped_fields": [
    { "path": "$.internal.debug_flags",
      "reason": "Aucun équivalent dans le modèle cible ; conservé dans raw_record." }
  ]
}
```

`ambiguities` et `unmapped_fields` sont **obligatoires** dans le contrat : ils remplissent l'exigence « l'application doit expliquer ce qu'elle ne sait pas interpréter ». Un adaptateur qui n'en renvoie pas est considéré comme incomplet.

---

## 6. Cycle de vie d'un mapping

```
draft ──► validated ──► active ──► superseded
   │                       │
   └──► rejected           └──► archived
```

- Un mapping est **versionné** : modifier un mapping actif crée une nouvelle version. `import_run.mapping_id` référence la version exacte utilisée, donc un import passé reste explicable même après évolution du mapping.
- Un mapping est **réutilisable** : un nouveau fichier de la même source réutilise le mapping existant sans repasser par l'IA.
- Un mapping est **portable entre modèles** : le document ne contient aucune référence au fournisseur qui l'a produit. Le descripteur du modèle est conservé à part, dans `mapping_proposal`, à des fins de traçabilité uniquement.

---

## 7. Séquence de transformation

Pour chaque enregistrement source, le moteur :

1. extrait la racine (`record.root`) ;
2. persiste le `raw_record` (payload intact + hash) ;
3. pour chaque entité : résout `iterate` s'il existe (§2.1 ; un `iterate` qui ne désigne pas une liste produit `ITERATE_NOT_A_LIST`), puis pour chaque champ applique les opérateurs **dans l'ordre déclaré** ;
4. sur échec : produit un `ImportIssue` avec code, chemin et message ; l'entité est rejetée, mais **le reste de l'enregistrement continue d'être traité** (un import partiel expliqué vaut mieux qu'un échec global) ;
5. calcule la clé naturelle, insère avec `ON CONFLICT DO NOTHING` ;
6. incrémente les compteurs du bilan.

Le moteur est **pur** : il prend un mapping et un dictionnaire, il rend des entités ou des issues. Aucune I/O, aucune base, aucun réseau — donc entièrement testable unitairement, comme l'exige le sujet.

**Noms de référentiels.** Un nom d'agent, de fournisseur, de modèle ou d'outil est résolu et stocké comme texte. Un nombre JSON devient son texte (`123` → `"123"`) ; une chaîne vide ou faite d'espaces est un nom absent ; un booléen ou une structure est rejeté (`TYPE_MISMATCH` par le moteur, `REFERENCE_NAME_INVALID` par le normaliseur si la valeur lui parvient malgré tout). Un appel d'outil sans nom utilisable ne peut pas pointer vers une ligne `tool` : il est rejeté avec `REFERENCE_NAME_INVALID`. À l'import, un nom qui n'a pas pu être résolu produit `REFERENCE_UNRESOLVED`, avec le `field_path` du nom et la ligne source : rejet pour un appel d'outil, qui n'est pas enregistré ; avertissement pour une session ou un appel de modèle, enregistrés sans ce lien. Aucun appel n'est écarté sans issue.
