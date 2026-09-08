# Tokens AgentScope

Ne jamais recopier un hex hors de `frontend/src/app/styles/globals.css`.

## Surfaces

| Token | Valeur | Usage |
|---|---|---|
| `--background` | `#F5F8F9` | Fond applicatif |
| `--background-alt` | `#F8FAFA` | Alternative |
| `--background-bright` | `#FBFDFD` | Zones très claires |
| `--glass` | `rgb(255 255 255 / 0.55)` | Surface glass |
| `--glass-strong` | `rgb(255 255 255 / 0.70)` | Hover / selected / popover |
| `--glass-soft` | `rgb(255 255 255 / 0.45)` | Inputs |
| `--glass-border` | `rgb(255 255 255 / 0.65)` | Bordure glass |
| `--border` | `rgb(30 45 50 / 0.10)` | Séparateurs contenu |
| `--glass-blur` | `28px` | backdrop-filter |

Blanc pur interdit comme fond dominant.

## Texte

| Token | Valeur | Usage |
|---|---|---|
| `--foreground` | `#182228` | Texte primaire |
| `--foreground-muted` | `#526169` | Secondaire |
| `--foreground-subtle` | `#7A878D` | Meta, labels |

## Accents

| Token | Valeur | Usage |
|---|---|---|
| `--primary-emphasis` | `#00F7FF` | Fill bouton primary, charts, glow, focus ring |
| `--primary` | `#008B94` | Liens, icônes, texte accent |
| `--accent-mint` | `#B0FFFA` | Healthy / décoratif |
| `--accent-magenta` | `#FF0087` | IA, charts modèles |
| `--accent-pink` | `#FF7DB0` | Décoratif |
| `--accent-blue` | `#7DB0FF` | Charts secondaires |
| `--success` | `#72F2C5` | Succès |
| `--warning` | `#FFD38A` | Warning |
| `--error` | `#FF4F91` | Erreur / danger |

`#00F7FF` n’est pas une couleur de body text. Texte sur fill cyan : `--foreground`.

## Typographie

- Display : Kanit Italic 300 (parfois 400, rarement 500)
- UI : Manrope 400 / 500 (600 seulement si indispensable)

| Classe | Taille | Police |
|---|---|---|
| `text-display` | 56–64px | Kanit 300 italic |
| `text-hero` | 44–52px | Kanit 300 italic |
| `text-page` | 36–40px | Kanit 300 italic |
| `text-section` | 24–28px | Kanit 400 italic |
| `text-kpi` | 36–44px | Kanit 300 italic |
| `text-card` | 15–17px | Manrope 500 |
| `text-body` | 14–15px | Manrope 400 |
| `text-secondary` | 13px | Manrope 400 |
| `text-meta` | 11–12px | Manrope 500 |

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
