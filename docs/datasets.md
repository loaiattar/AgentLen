# AgentLen — Provenance des jeux de données

> Ce document répond à l'exigence du sujet : « documentez leur provenance,
> leur version et la façon dont vous les avez sélectionnés ».
>
> Les extraits bruts ne sont **pas versionnés** (`.gitignore` exclut `data/` et
> `*.jsonl`), **sauf l'échantillon TraceLab** `data/samples/tracelab_example_session.jsonl`,
> suivi par git malgré ces règles : c'est le fichier que `make seed` importe
> (`SAMPLE_FILE` dans `interfaces/cli/seed.py`). Ce document suffit à retrouver
> et reproduire les autres.

---

## 1. TraceLab — source principale

| Champ | Valeur |
|---|---|
| **Nom** | TraceLab |
| **Auteur** | SyFI Lab, University of Washington |
| **URL** | https://github.com/uw-syfi/TraceLab |
| **Fichier utilisé** | `example_sessions/sanitized/round_trace.jsonl` |
| **Date de récupération** | 2026-09-08 |
| **Format** | JSONL — un objet JSON par ligne, une session par enregistrement |
| **Taille de l'extrait** | 19 enregistrements (fichier d'exemple public fourni par le projet) |
| **Licence** | MIT — redistribution autorisée ; l'extrait est versionné dans `data/samples/tracelab_example_session.jsonl` |

### Méthode de sélection

Le projet TraceLab fournit un fichier d'exemple sanitisé dans
`example_sessions/sanitized/round_trace.jsonl`. C'est ce fichier qui est utilisé
directement — aucune sélection manuelle, aucune troncature.

Il contient des traces réelles de sessions Claude Code et Codex, anonymisées
par les auteurs du dataset. Les champs sensibles (chemins absolus, noms
d'utilisateurs) ont été remplacés par des placeholders par TraceLab.

### Reproduire l'extrait

Le fichier est déjà dans le dépôt ; ces commandes ne servent qu'à le reconstituer
depuis la source. Le nom de destination est celui qu'attend `make seed`.

```bash
git clone https://github.com/uw-syfi/TraceLab.git
cp TraceLab/example_sessions/sanitized/round_trace.jsonl data/samples/tracelab_example_session.jsonl
```

### Structure d'un enregistrement (champs principaux)

| Champ source | Type | Description |
|---|---|---|
| `session_id` | string | Identifiant unique de la session |
| `agent` | string | Agent utilisé (`claude_code`, `codex_cli`) |
| `start_time` | float | Timestamp Unix de début de session |
| `events` | array | Liste des événements (appels modèle + appels outils) |
| `events[].type` | string | `llm_call` ou `tool_use` |
| `events[].usage.input_tokens` | integer \| null | Tokens en entrée |
| `events[].usage.output_tokens` | integer \| null | Tokens en sortie |
| `events[].latency_s` | float \| null | Durée de l'appel en secondes |

> **Note d'unité :** `latency_s` est en secondes. Le mapping applique
> `unit_convert s→ms` pour aligner avec le modèle interne (durées en ms).

---

## 2. SWE-chat — source secondaire

| Champ | Valeur |
|---|---|
| **Nom** | SWE-chat |
| **Auteur** | SALT-NLP, Stanford |
| **URL** | https://huggingface.co/datasets/SALT-NLP/SWE-chat |
| **Date de récupération** | À compléter lors de l'import réel |
| **Format** | Parquet (disponible via `datasets` HuggingFace) |
| **Taille de l'extrait** | À compléter — sélectionner ≤ 500 sessions |
| **Licence** | Apache 2.0 — redistribution autorisée |

### Méthode de sélection prévue

```python
from datasets import load_dataset
ds = load_dataset("SALT-NLP/SWE-chat", split="train[:500]")
ds.to_parquet("data/samples/swechat_sample.parquet")
```

Critères de sélection : sessions complètes uniquement (champ `status == "complete"`),
limité aux 500 premières pour garder une taille raisonnable.

---

## 3. Trace Commons — source pour tester l'import d'une structure inconnue

| Champ | Valeur |
|---|---|
| **Nom** | Trace Commons |
| **Auteur** | Agent Traces |
| **URL** | https://huggingface.co/datasets/trace-commons/agent-traces |
| **Date de récupération** | À compléter lors de l'import réel |
| **Format** | Formats natifs variés (JSONL, JSON) selon les agents |
| **Taille de l'extrait** | À compléter — sélectionner un sous-ensemble d'un agent inconnu |
| **Licence** | À vérifier par sous-dataset — ne pas redistribuer sans confirmation |

### Rôle dans le projet

Ce dataset sert à **tester l'import d'une structure inconnue** : l'utilisateur
charge un extrait, l'agent IA propose un mapping depuis l'interface, et le
parcours complet (profil → mapping → validation → import) est vérifié sans
modifier le code.

---

## Pourquoi les autres fichiers ne sont pas dans le dépôt

1. **Taille** : les fichiers JSONL et Parquet peuvent dépasser les limites raisonnables de Git.
2. **Licence** : certaines licences interdisent la redistribution des données brutes.
3. **Reproductibilité** : les commandes ci-dessus suffisent à reconstituer les extraits.

L'échantillon TraceLab fait exception : 19 lignes, licence MIT, nécessaire à
`make seed`. Tout autre fichier placé sous `data/` reste ignoré tant qu'il n'est
pas ajouté explicitement (`git add -f`).

Les fixtures de test (`tests/fixtures/**/*.jsonl`) sont exemptées du `.gitignore`
car elles sont petites, sanitisées, et nécessaires à la CI.

---

## Récapitulatif

| Source | Format | Enregistrements | Statut |
|---|---|---|---|
| TraceLab | JSONL | 19 | ✅ Utilisé, mapping documenté |
| SWE-chat | Parquet | ≤ 500 | 🟡 Prévu — import à réaliser |
| Trace Commons | JSONL | À définir | 🟡 Prévu — test structure inconnue |
