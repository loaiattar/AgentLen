# Tokens AgentLen

Ne jamais recopier un hex hors de `frontend/src/app/styles/globals.css`.

Les surfaces, textes, glass, bordures, ombres et overlays ont une valeur light (`:root`) et une valeur dark (`.dark`). Les accents de marque sont identiques dans les deux thèmes.

## Surfaces

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--background` | `#F5F8F9` | `#0D1417` | Fond applicatif |
| `--background-alt` | `#F8FAFA` | `#11191C` | Alternative |
| `--background-bright` | `#FBFDFD` | `#182228` | Zones plus denses |
| `--glass` | `rgb(255 255 255 / 0.55)` | `rgb(24 34 40 / 0.55)` | Surface glass |
| `--glass-strong` | `rgb(255 255 255 / 0.70)` | `rgb(30 42 48 / 0.72)` | Hover / selected / popover |
| `--glass-soft` | `rgb(255 255 255 / 0.45)` | `rgb(24 34 40 / 0.40)` | Inputs |
| `--glass-border` | `rgb(255 255 255 / 0.65)` | `rgb(255 255 255 / 0.12)` | Bordure glass |
| `--border` | `rgb(16 22 24 / 0.12)` | `rgb(245 248 249 / 0.12)` | Séparateurs contenu |
| `--overlay` | `rgb(16 22 24 / 0.28)` | `rgb(0 0 0 / 0.55)` | Modal / drawer |
| `--glass-blur` | `28px` | `28px` | backdrop-filter |

Blanc pur interdit comme fond dominant.

## Texte

Light → texte sombre. Dark → texte clair. Pas de teinte saturée pour le body.

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--foreground` | `#101618` | `#F5F8F9` | Texte primaire |
| `--foreground-muted` | `#3D4A50` | `#C5CED2` | Secondaire |
| `--foreground-subtle` | `#5C6B72` | `#8B969C` | Meta, labels |

## Accents

Inchangés entre light et dark.

| Token | Valeur | Usage |
|---|---|---|
| `--primary-emphasis` | `#00F7FF` | Charts, glow, focus ring — jamais texte de bouton |
| `--primary` | `#008B94` | Fill bouton primary, liens, icônes |
| `--accent-mint` | `#B0FFFA` | Healthy / décoratif |
| `--accent-magenta` | `#FF0087` | IA, charts modèles |
| `--accent-pink` | `#FF7DB0` | Décoratif |
| `--accent-blue` | `#7DB0FF` | Charts secondaires |
| `--success` | `#72F2C5` | Succès |
| `--warning` | `#FFD38A` | Warning |
| `--error` | `#FF4F91` | Erreur / danger |

`#00F7FF` n’est pas une couleur de body text ni de libellé de bouton. Texte sur fill primary (`--primary`) : `--on-dark`.

## Typographie

Inter uniquement. `font-sans`, `font-display` et `font-mono` pointent vers Inter.

| Classe | Taille | Poids |
|---|---|---|
| `text-display` | 56–64px | 400 |
| `text-hero` | 44–52px | 400 |
| `text-page` | 36–40px | 400 |
| `text-section` | 24–28px | 500 |
| `text-kpi` | 36–44px | 400 |
| `text-card` | 15–17px | 500 |
| `text-body` | 14–15px | 400 |
| `text-secondary` | 13px | 400 |
| `text-meta` | 11–12px | 500 |

## Espacements

Base 8px. Échelle : 8 / 16 / 24 / 32 / 48 / 64.

| Token | Valeur |
|---|---|
| `--space-1` | 8px |
| `--space-2` | 16px |
| `--space-3` | 24px |
| `--space-4` | 32px |
| `--space-5` | 48px |
| `--space-6` | 64px |
| `--bento-gutter` | 16px desktop |
| `--bento-gutter-mobile` | 12px |

## Radius

| Token | Usage |
|---|---|
| `--radius-control` / `rounded-md` | Boutons, inputs |
| `--radius` / `rounded-lg` | Menus |
| `--radius-module` / `rounded-xl` | Modules Bento, glass |
| `--radius-pill` | Chips, dots |

## Ombres

Tokens `--elevation-*` dans `:root` / `.dark`, exposés en `shadow-glass`, `shadow-glass-hover`, `shadow-pop`.

| Token | Usage |
|---|---|
| `--shadow-glass` | Modules au repos |
| `--shadow-glass-hover` | Hover module |
| `--shadow-pop` | Dropdown, modal, drawer |

## Motion

| Token | Valeur |
|---|---|
| `--duration-fast` | 140ms |
| `--duration-base` | 220ms |
| `--ease-out` | `cubic-bezier(0.22, 1, 0.36, 1)` |
