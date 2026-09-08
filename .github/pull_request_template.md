<!-- Conventions : docs/CONTRIBUTING.md -->

## Ce que fait cette PR

<!-- 2-3 phrases. Le POURQUOI avant le QUOI. -->

Closes #

## Type

- [ ] `feat` — nouvelle fonctionnalité
- [ ] `fix` — correction
- [ ] `refactor` — sans changement de comportement
- [ ] `test` — tests uniquement
- [ ] `docs` — documentation
- [ ] `chore` / `ci` — outillage

## Couches touchées

- [ ] `domain` &nbsp;&nbsp; - [ ] `application` &nbsp;&nbsp; - [ ] `infrastructure` &nbsp;&nbsp; - [ ] `interfaces` &nbsp;&nbsp; - [ ] `docs`

## Comment vérifier

<!-- Commandes à lancer, route à appeler, ou test à exécuter. -->

```bash
```

## Checklist auteur

- [ ] La CI est verte (`ruff`, `mypy`, `import-linter`, `pytest`)
- [ ] Des tests couvrent le comportement ajouté **et un cas d'échec**
- [ ] La règle de dépendance est respectée (rien de tiers dans `domain/`)
- [ ] Aucun identifiant de modèle IA ni secret en dur
- [ ] Aucune valeur absente transformée en `0`
- [ ] La documentation impactée est à jour (architecture, API, ADR)
- [ ] PR < ~400 lignes modifiées, sinon découpée ou justifiée ci-dessous

## Points d'attention pour le relecteur

<!-- Ce dont tu n'es pas sûr, les compromis assumés, ce qui mérite un regard appuyé. -->
