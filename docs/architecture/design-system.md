# Design system AgentLen

Documentation humaine du design system frontend. Pour l’agent de développement, voir aussi `.cursor/skills/agentscope-design-system/`.

Maquette d’origine : [Figma](https://www.figma.com/design/kHqSTLbPioSwXsh0URi7BB/Untitled?node-id=0-1&m=dev)

## Intention

AgentLen est une plateforme d’observabilité des traces d’agents IA. L’interface doit rendre des données complexes lisibles sans surcharge.

Principe : moins d’UI, plus de clarté. Liquid glass, grille Bento, typographie Inter unique, contraste élevé, faible densité, peu de boutons.

Équilibre : 80 % neutres / 15 % glass / 5 % accents (cyan surtout, magenta pour l’IA).

Light theme → texte sombre sur fond lumineux. Dark theme → texte clair sur fond profond. Les accents de marque restent les mêmes dans les deux thèmes.

## Où vivent les tokens

`frontend/src/app/styles/globals.css` est la **seule** source des hex, rgba, radius, ombres, blur et espacements de grille. Les valeurs qui changent avec le thème sont définies dans `:root` (light) et `.dark` (dark).

Les composants et pages utilisent :

- utilitaires Tailwind mappés via `@theme inline` (`bg-background`, `text-foreground-muted`, `rounded-xl`, `shadow-glass`)
- classes structurelles (`.atmosphere`, `.glass-surface`, `.glass-module`, `.bento-grid`)

Interdit : `bg-[#…]`, `style={{ color: '#…' }}`, duplication des recettes glass dans une page, police autre qu’Inter, override de thème page par page.

## Thèmes

Le thème est global : `ThemeProvider` pose la classe `dark` sur `html` et persiste le choix (`agentlen-theme`). `ThemeToggle` dans `TopNav` et `PublicHeader` bascule Light / Dark.

Ne pas brancher de couleurs de thème dans une feature. Un composant qui utilise `text-foreground`, `bg-glass`, `border-border` fonctionne dans les deux thèmes.

## Tokens principaux

### Couleurs

Les accents sont identiques dans les deux thèmes.

| Rôle | Token | Light | Dark |
|---|---|---|---|
| Fond | `--background` | `#F5F8F9` | `#0D1417` |
| Texte | `--foreground` | `#101618` | `#F5F8F9` |
| Texte secondaire | `--foreground-muted` | `#3D4A50` | `#C5CED2` |
| Texte meta | `--foreground-subtle` | `#5C6B72` | `#8B969C` |
| Cyan UI / liens | `--primary` | `#008B94` | `#008B94` |
| Cyan lumineux | `--primary-emphasis` | `#00F7FF` | `#00F7FF` |
| Mint | `--accent-mint` | `#B0FFFA` | `#B0FFFA` |
| Magenta IA | `--accent-magenta` | `#FF0087` | `#FF0087` |
| Pink | `--accent-pink` | `#FF7DB0` | `#FF7DB0` |
| Blue charts | `--accent-blue` | `#7DB0FF` | `#7DB0FF` |
| Success | `--success` | `#72F2C5` | `#72F2C5` |
| Warning | `--warning` | `#FFD38A` | `#FFD38A` |
| Error | `--error` | `#FF4F91` | `#FF4F91` |
| Overlay | `--overlay` | `rgb(16 22 24 / 0.28)` | `rgb(0 0 0 / 0.55)` |

`#00F7FF` n’est pas une couleur de body text ni de libellé de bouton.

### Liquid glass

- Light : blancs semi-transparents (`--glass` / `--glass-strong`)
- Dark : surfaces `#182228` semi-transparentes, bordure claire faible
- Blur : `--glass-blur` (28px)
- Refraction : halos cyan / magenta / blue **à l’intérieur** du module, jamais en bordure néon

Hover : surface un peu plus opaque, bordure plus nette, translation `-2px`. Active : légère compression.

### Typographie

**Inter uniquement** (300–600), titres, body, navigation, boutons, formulaires, tableaux, métriques, labels, messages système. `font-display`, `font-sans` et `font-mono` pointent tous vers Inter.

Pas de titres heavy / bold. Pas de Kanit, Manrope, ni d’italic de display.

### Espacement et radius

Échelle 8 / 16 / 24 / 32 / 48 / 64. Gutter Bento 16px (12px mobile). Modules `rounded-xl`. Contrôles `rounded-md`.

## Composants

Tous les composants du design system sont dans `frontend/src/components/ui/`.

| Composant | Rôle |
|---|---|
| `Button` | primary / secondary glass / ghost / text / ai / danger + loading |
| `Input`, `Textarea`, `Field`, `SearchField` | Formulaires, focus cyan, error |
| `Badge`, `StatusDot` | Statuts, sans décoration excessive |
| `Kpi` | Indicateur minimal (label, valeur, delta) |
| `BentoGrid`, `BentoModule`, `BentoTitle` | Grille et modules glass |
| `Table` | Listes denses, hover de ligne |
| `FilterBar`, `FilterChip` | Filtres légers |
| `OverflowMenu` | Actions secondaires |
| `EmptyState`, `Skeleton` | États vides et loading glass |
| `Chart` | Sparkline, area, barres, mix |
| `Timeline` | Session detail |
| `AiPanel` | Insights mapping, pas un chat |
| `Modal`, `Drawer`, `Tooltip` | Overlays glass |
| `PageHeader`, `AppSidebar`, `TopNav`, `AtmosphericBackground`, `Wordmark`, `PublicHeader`, `ThemeToggle` | Shell et branding |

`PageHeader` n’affiche que le titre principal (plus de kicker ni de sous-titre).

shadcn/ui : `frontend/components.json` pointe vers `src/components/ui` et `src/app/styles/globals.css`. Un nouveau primitive shadcn est généré dans ce dossier, puis recâblé sur les tokens (pas de palette shadcn par défaut).

## États

Chaque contrôle interactif doit couvrir :

- **default**
- **hover**
- **active**
- **focus** — outline / ring cyan `--primary-emphasis`
- **disabled** — opacifié, non cliquable
- **loading** — spinner, `data-loading`, interaction bloquée
- **error** — `data-error`, bordure `--error`, message `role="alert"`

## Pages existantes

Le shell (`AppLayout`) applique le fond atmosphérique, la sidebar glass, la top nav et le basculeur de thème. Les pages features composent le Bento au lieu de cartes locales.

| Route | Page |
|---|---|
| `/` | Landing publique |
| `/login` · `/register` | Authentification |
| `/overview` | Overview Bento |
| `/sessions` | Explorer + table |
| `/sessions/$sessionId` | Timeline |
| `/imports` | Nouvel import + historique |
| `/imports/$importId` | Détail import |
| `/import-assistant` | Mapping studio 3 zones |
| `/sources` | Sources |
| `/mappings` | Library |
| `/quality` | Intégrité des données |

Le wordmark visible est **AgentLen**. Aucune mention AgentScope dans l’interface.

## Comment étendre

1. Ajouter le token dans `globals.css` (`:root`, `.dark` si le token change avec le thème, puis `@theme inline`).
2. Étendre ou créer un composant dans `components/ui/` avec `cva` + `cn()`.
3. Mettre à jour ce document et `.cursor/skills/agentscope-design-system/`.
4. Consommer le composant dans la feature. Si une combinaison de classes se répète trois fois, extraire un composant.

## Accessibilité

Light : texte important `#101618`. Dark : texte important `#F5F8F9`. Le focus est visible (ring cyan). Un statut n’est jamais porté par la seule couleur (`StatusDot` + label, `Badge` textuel). `prefers-reduced-motion` coupe drift et shimmer. `color-scheme` suit le thème pour les contrôles natifs.
