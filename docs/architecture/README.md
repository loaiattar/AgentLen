# Documentation d'architecture — AgentLen (backend)

| Document | Contenu | Public |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Couches, règle de dépendance, schéma des composants, ports et adaptateurs, flux principaux, interchangeabilité IA, sécurité, tests, découpage du travail | Équipe backend, correcteurs |
| [DATA_MODEL.md](DATA_MODEL.md) | Diagramme relationnel, grain de chaque table, justification 3NF et exceptions, stratégie d'idempotence, couche de lecture | Équipe backend, correcteurs |
| [MAPPING_CONTRACT.md](MAPPING_CONTRACT.md) | Format du document de mapping, whitelist d'opérateurs, validation, contrat d'entrée/sortie de l'IA, cycle de vie | Équipe backend, contributeurs externes |
| [API.md](API.md) | **Contrat REST v1** : routes, schémas, conventions d'erreur et de valeurs absentes, drill-down | **Équipe frontend**, backend |
| [decisions.md](decisions.md) | 10 ADR courtes : contexte, décision, alternatives écartées, conséquences | Correcteurs, futurs contributeurs |

## Lecture recommandée

- **Nouveau contributeur backend** : ARCHITECTURE → DATA_MODEL → MAPPING_CONTRACT
- **Équipe frontend** : API (les §1 et §9 d'abord)
- **Correcteur** : decisions → ARCHITECTURE §4 (règle de dépendance) → DATA_MODEL §4-6

## Règles de mise à jour

- Toute évolution du contrat d'API passe par une PR sur `API.md`, relue par le front, **avant** implémentation.
- Toute décision structurante ajoute une ADR ; on ne réécrit pas une ADR acceptée, on en ajoute une qui la remplace.
- Les schémas Mermaid sont versionnés en texte dans les fichiers : pas d'image binaire, pas de source externe.

## Encore à produire (livrables du sujet)

- [ ] `docs/verification/ai-models-report.md` — compte rendu du parcours d'identification et d'import avec les **deux** modèles IA
- [ ] `docs/datasets.md` — provenance, versions, dates de récupération et méthode de sélection des extraits
- [ ] `docs/observations.md` — **trois observations chiffrées** avec sources et filtres permettant de les retrouver
- [ ] Mappings documentés pour **au moins deux sources distinctes**
- [ ] README de prise en main, LICENSE, CONTRIBUTING, notes de version
