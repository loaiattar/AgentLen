---
name: agentscope-design-system
description: Applique le design system AgentLen (liquid glass, Bento, Inter, light/dark, tokens Tailwind/shadcn) lors du développement frontend. Use when building or restyling AgentLen UI, components/ui, pages, Figma parity, tokens, typography, or liquid glass.
---

# Design system AgentLen

Source de vérité visuelle pour le frontend. Ne pas inventer de couleurs, rayons, ombres ou densités locales.

Références :

- Tokens CSS : `frontend/src/app/styles/globals.css`
- Composants : `frontend/src/components/ui/`
- Détail tokens : [tokens.md](tokens.md)
- API composants : [components.md](components.md)
- Composition des pages : [pages.md](pages.md)
- Doc humaine : `docs/architecture/design-system.md`
- Maquette d’origine : [Figma](https://www.figma.com/design/kHqSTLbPioSwXsh0URi7BB/Untitled?node-id=0-1&m=dev)

## Philosophie

AgentLen est une fenêtre sur le comportement d’agents IA.

- Moins d’UI, plus de clarté
- Moins de texte, plus de hiérarchie
- Moins de boutons, plus d’actions contextuelles
- Moins de bruit, plus d’espace négatif

Le produit doit paraître calme, précis, premium, modulaire. Futuriste mais quiet.

Éviter : SaaS générique, corporate, crowding, cyberpunk, néon excessif, glass excessif, titres gras.

Équilibre visuel : **80%** neutres / **15%** liquid glass / **5%** accents.

## Direction visuelle

- Light **et** dark, via tokens globaux (`:root` / `.dark`) et `ThemeToggle`
- Light : fond lumineux `#F5F8F9`, texte `#101618`
- Dark : fond `#0D1417`, texte `#F5F8F9`
- Halos cyan / mint / blue / magenta / pink très flous
- Modules Bento en liquid glass (blur, bordure, ombre diffuse, refraction)
- Typo unique : Inter 400–500 (titres un peu plus tracking négatif)
- Contraste fort contenu / fond
- Un focus primaire par page, 2–3 secondaires
- Une action primaire visible, au plus une secondaire. Le reste va dans `OverflowMenu`, hover, lien texte
- Branding visible : **AgentLen** (jamais AgentScope)

## Règles d’implémentation

1. Toute valeur visuelle passe par un token (`bg-background`, `text-foreground`, `rounded-xl`, `glass-module`, `gap-bento`). Interdit : hex, rgba, px magiques si un token existe.
2. Les primitives et modules du DS vivent dans `frontend/src/components/ui/`. Pas de styles dupliqués dans les pages.
3. Les pages composent `PageHeader`, `BentoGrid` / `BentoModule`, `Kpi`, `Table`, `FilterBar`, `EmptyState`, `Button`.
4. shadcn/ui : personnaliser le composant dans `components/ui/` via `cva` + tokens. Ne pas wrapper une troisième couche de styles.
5. États obligatoires sur les contrôles : default, hover, active, focus (`ring-primary-emphasis`), disabled, loading, error.
6. Hover module : +clarté, refraction un peu plus visible, `translateY(-2px)`. Pas de scale dramatique.
7. Jamais de bordure néon, jamais de carte glow, jamais `font-bold` sur un titre.
8. Ne pas remplir un grand module Bento. Titre + valeur/visuel + une info support.
9. Une donnée absente reste absente. Jamais `0` à la place d’une valeur manquante.
10. Respecter `prefers-reduced-motion`.
11. Aucune police hors Inter. Aucune couleur de thème locale. `PageHeader` = titre seul, pas de sous-titre.

## Stack

Tailwind v4 (`@theme inline` dans `globals.css`) + shadcn/ui (`components.json`) + `class-variance-authority` + `cn()`.

Classes structurelles :

- `atmosphere` / `atmosphere-motion` — fond
- `glass-surface` — panneau glass statique
- `glass-module` — module Bento interactif (`data-interactive`, `data-state="selected"`)
- `bento-grid` — grille 1 / 6 / 12 colonnes
- `font-display` — Inter, tracking serré (alias de `font-sans`)
- `text-display|hero|page|section|kpi|card|body|secondary|meta`

## Étendre le système

1. Ajouter le token dans `:root` et `.dark` si besoin, puis `@theme inline` de `globals.css`.
2. Créer ou étendre un composant dans `components/ui/` avec `cva`.
3. Documenter la variante dans [components.md](components.md) et `docs/architecture/design-system.md`.
4. Consommer le composant depuis la feature. Ne jamais recopier ses classes.
