# Design system AgentScope

Documentation humaine du design system frontend. Pour l’agent de développement, voir aussi `.cursor/skills/agentscope-design-system/`.

Maquette : [Figma AgentScope](https://www.figma.com/design/kHqSTLbPioSwXsh0URi7BB/Untitled?node-id=0-1&m=dev)

## Intention

AgentScope est une plateforme d’observabilité des traces d’agents IA. L’interface doit rendre des données complexes lisibles sans surcharge.

Principe : moins d’UI, plus de clarté. Light mode, liquid glass, fond lumineux, grille Bento, typographie légère, contraste élevé, faible densité, peu de boutons.

Équilibre : 80 % neutres lumineux / 15 % glass / 5 % accents (cyan surtout, magenta pour l’IA).

## Où vivent les tokens

`frontend/src/app/styles/globals.css` est la **seule** source des hex, rgba, radius, ombres, blur et espacements de grille.

Les composants et pages utilisent :

- utilitaires Tailwind mappés via `@theme inline` (`bg-background`, `text-foreground-muted`, `rounded-xl`, `shadow-glass`)
- classes structurelles (`.atmosphere`, `.glass-surface`, `.glass-module`, `.bento-grid`)

Interdit : `bg-[#…]`, `style={{ color: '#…' }}`, duplication des recettes glass dans une page.

## Tokens principaux

### Couleurs

| Rôle | Token | Valeur |
|---|---|---|
| Fond | `--background` | `#F5F8F9` |
| Texte | `--foreground` | `#182228` |
| Texte secondaire | `--foreground-muted` | `#526169` |
| Texte meta | `--foreground-subtle` | `#7A878D` |
| Cyan UI / liens | `--primary` | `#008B94` |
| Cyan lumineux | `--primary-emphasis` | `#00F7FF` |
| Mint | `--accent-mint` | `#B0FFFA` |
| Magenta IA | `--accent-magenta` | `#FF0087` |
| Pink | `--accent-pink` | `#FF7DB0` |
| Blue charts | `--accent-blue` | `#7DB0FF` |
| Success | `--success` | `#72F2C5` |
| Warning | `--warning` | `#FFD38A` |
| Error | `--error` | `#FF4F91` |
| Bordure contenu | `--border` | `rgb(30 45 50 / 0.10)` |

### Liquid glass

- Fond module : `rgb(255 255 255 / 0.45–0.70)` (`--glass` / `--glass-strong`)
- Blur : `--glass-blur` (28px)
- Bordure : `--glass-border`
- Ombre : `--shadow-glass`
- Refraction : halos cyan / magenta / blue **à l’intérieur** du module, jamais en bordure néon

Hover : surface un peu plus opaque, bordure plus nette, translation `-2px`. Active : légère compression.

### Typographie

- **Kanit Italic 300–400** : titres et KPI (`font-display`, `text-page`, `text-kpi`, `text-section`)
- **Manrope 400–500** : navigation, body, tables, forms (`font-sans`, `text-body`, `text-card`, `text-meta`)

Pas de titres heavy / bold.

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
| `PageHeader`, `AppSidebar`, `TopNav`, `AtmosphericBackground`, `Wordmark`, `PublicHeader` | Shell |

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

Le shell (`AppLayout`) applique le fond atmosphérique, la sidebar glass et la top nav. Les pages features composent le Bento au lieu de cartes locales.

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

## Comment étendre

1. Ajouter le token dans `globals.css` (`:root` + `@theme inline`).
2. Étendre ou créer un composant dans `components/ui/` avec `cva` + `cn()`.
3. Mettre à jour ce document et `.cursor/skills/agentscope-design-system/`.
4. Consommer le composant dans la feature. Si une combinaison de classes se répète trois fois, extraire un composant.

## Accessibilité

Light mode : le texte important reste `#182228`. Le focus est visible (ring cyan). Un statut n’est jamais porté par la seule couleur (`StatusDot` + label, `Badge` textuel). `prefers-reduced-motion` coupe drift et shimmer.
