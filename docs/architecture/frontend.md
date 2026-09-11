# Architecture Frontend

## Sommaire

- [1. Objectif](#1-objectif)
- [2. Stack technique](#2-stack-technique)
- [3. Vue d'ensemble de l'architecture](#3-vue-densemble-de-larchitecture)
- [4. Arborescence du projet](#4-arborescence-du-projet)
- [5. Responsabilités des dossiers](#5-responsabilités-des-dossiers)
- [6. Atomic Design](#6-atomic-design)
- [7. Organisation par feature](#7-organisation-par-feature)
- [8. shadcn/ui](#8-shadcnui)
- [9. API & TanStack Query](#9-api--tanstack-query)
- [10. State management & Zustand](#10-state-management--zustand)
- [11. Routing & TanStack Router](#11-routing--tanstack-router)
- [12. Tailwind CSS](#12-tailwind-css)
- [13. Règles de dépendances](#13-règles-de-dépendances)
- [14. Conventions](#14-conventions)
- [15. Ajouter une nouvelle feature — guide pratique](#15-ajouter-une-nouvelle-feature--guide-pratique)

---

## 1. Objectif

Ce document est l'architecture de référence du frontend. Il décrit comment le code est organisé, quelle est la responsabilité de chaque couche, et quelles règles respecter en ajoutant une nouvelle fonctionnalité. Toute PR qui introduit une nouvelle feature ou un nouveau composant doit respecter les conventions décrites ici.

## 2. Stack technique

| Domaine | Outil | Rôle |
|---|---|---|
| UI | **React** | Rendu et composition de l'interface |
| Langage | **TypeScript** | Typage statique, contrats de données |
| Style | **Tailwind CSS** | Styling utilitaire |
| Composants UI de base | **shadcn/ui** | Bibliothèque de composants headless/personnalisables |
| Données serveur | **TanStack Query** | Appels API, cache, invalidation, états loading/error |
| État client | **Zustand** | Store(s) d'état client global (UI, préférences), hors données serveur |
| Routing | **TanStack Router** | Déclaration des routes, layouts, paramètres d'URL |
| Organisation UI | **Atomic Design** | Structuration des composants (atoms → pages) |

## 3. Vue d'ensemble de l'architecture

Le frontend est découpé en cinq grandes zones de responsabilité :

1. **`app/`** — configuration globale de l'application (router, providers, layouts racine).
2. **Pages & routing** — points d'entrée associés aux URLs, portés par `app/router` et les `pages/` de chaque feature.
3. **`features/`** — logique métier : une feature regroupe tout ce qui est nécessaire à une fonctionnalité (UI spécifique, appels API, hooks, types, store local si besoin).
4. **`components/`** — composants UI génériques organisés en Atomic Design, indépendants de tout métier.
5. **`lib/`, `hooks/` & `store/`** — client API, utilitaires, hooks et état client (Zustand) partagés, transverses à tout le projet.

> État serveur vs état client : les données qui viennent du backend (listes, entités, statuts) sont toujours gérées par **TanStack Query** ([section 9](#9-api--tanstack-query)), jamais dupliquées dans un store Zustand. **Zustand** ne gère que l'état purement client (UI, préférences, état d'un flux multi-étapes) — voir [section 10](#10-state-management--zustand).

### Schéma des dépendances

```text
                     ┌─────────────────────┐
                     │        app/         │
                     │ router / providers   │
                     │      / layouts       │
                     └──────────┬───────────┘
                                │ monte
                                ▼
                     ┌─────────────────────┐
                     │   features/*/pages   │  ◄── points d'entrée de route
                     └──────────┬───────────┘
                                │ utilise
                                ▼
                     ┌─────────────────────┐
                     │  features/* (métier) │
                     │  components/api/hooks│
                     └──────────┬───────────┘
                                │ utilise
                                ▼
                     ┌─────────────────────┐
                     │      components/      │
                     │ atoms/molecules/       │
                     │ organisms/templates    │
                     └──────────┬───────────┘
                                │ utilise
                                ▼
                     ┌─────────────────────┐
                     │  lib/ · hooks/ ·       │
                     │  store/ · types/       │
                     │     (transverse)        │
                     └─────────────────────┘
```

**Lecture du schéma :** les flèches représentent le sens autorisé des dépendances (`import`). Une couche ne peut importer que les couches situées en dessous d'elle. `lib/`, `hooks/`, `store/` (global) et `types/` (partagés) sont au socle : ils ne dépendent de rien d'autre dans `src/` et peuvent être importés par toutes les couches au-dessus. Le détail des règles est donné en [section 13](#13-règles-de-dépendances).

## 4. Arborescence du projet

```text
src/
├── app/
│   ├── router/            # Déclaration des routes, route tree, guards
│   ├── providers/         # QueryClientProvider, ThemeProvider, etc.
│   └── layouts/           # Layouts racine (AppLayout, AuthLayout...)
│
├── components/
│   ├── ui/                 # Design system + primitives shadcn (Button, Bento, Kpi…)
│   ├── atoms/              # Couche Atomic Design optionnelle au-dessus de ui/
│   ├── molecules/          # Combinaisons simples d'atoms
│   ├── organisms/          # Compositions complexes, génériques (non liées à une feature)
│   └── templates/          # Structures de page réutilisables (layout de contenu)
│
├── features/
│   ├── sessions/
│   │   ├── components/     # Composants spécifiques à la feature
│   │   ├── api/             # Fonctions d'appel API + queries/mutations TanStack Query
│   │   ├── hooks/           # Hooks métier spécifiques à la feature
│   │   ├── store/           # Store Zustand local (optionnel, si état client complexe)
│   │   ├── types.ts          # Types métier de la feature
│   │   └── pages/           # Pages associées aux routes de la feature
│   ├── imports/
│   ├── import-assistant/
│   ├── mappings/
│   ├── sources/
│   ├── quality/
│   └── dashboard/
│
├── lib/
│   ├── api/                 # Client HTTP, config de base, intercepteurs, QueryClient
│   └── utils/                # Fonctions utilitaires génériques (formatters, cn, etc.)
│
├── hooks/                    # Hooks génériques transverses (useDebounce, useMediaQuery...)
├── store/                    # Stores Zustand globaux (UI, préférences, session côté client)
├── types/                    # Types globaux partagés (ex: types générés de l'API)
├── assets/                   # Images, fonts, icônes statiques
│
└── main.tsx                  # Point d'entrée de l'application
```

Cette arborescence est la cible : elle peut être adaptée si un besoin réel du projet le justifie, mais toute déviation doit rester cohérente avec les principes définis dans ce document (séparation config / pages / features / UI générique / lib).

## 5. Responsabilités des dossiers

### `app/`

Configuration globale et bootstrap de l'application. Rien de métier n'y vit.

- **`app/router/`** : instanciation du router TanStack Router (`createRouter`), arbre de routes (`routeTree`), route racine (`__root.tsx`).
- **`app/providers/`** : tous les providers React globaux — `QueryClientProvider`, `ThemeProvider`, contexte d'authentification, etc.
- **`app/layouts/`** : layouts appliqués au niveau racine du router (shell applicatif : sidebar, header, zone de contenu).

À éviter dans `app/` : logique métier, appels API directs, composants réutilisables (ils vont dans `components/`).

### `components/`

Composants UI **génériques**, indépendants de tout domaine métier, organisés selon l'Atomic Design (détail en [section 6](#6-atomic-design)).

- Peut contenir des composants shadcn/ui personnalisés.
- Ne doit **jamais** importer depuis `features/`.
- Ne doit contenir aucune logique métier (pas d'appel API, pas de règle propre à une feature).

### `features/`

Toute la logique métier de l'application, découpée par domaine fonctionnel. Voir [section 7](#7-organisation-par-feature).

### `lib/`

Code transverse, technique, sans état métier.

- **`lib/api/`** : configuration du client HTTP (ex. instance `fetch`/`axios` wrapper), configuration du `QueryClient`, gestion des erreurs réseau communes, types de réponse génériques.
- **`lib/utils/`** : fonctions pures et génériques (`cn()` pour Tailwind, formatters de date/nombre, helpers génériques). Aucune fonction spécifique à une feature ne doit s'y trouver.

### `hooks/`

Hooks React **génériques et transverses**, réutilisables dans n'importe quelle feature ou composant (`useDebounce`, `useMediaQuery`, `useLocalStorage`...). Un hook qui encapsule une règle métier (ex. `useImportStatus`) appartient à la feature concernée, pas ici.

### `store/`

Stores **Zustand** globaux, transverses à plusieurs features (ex. état de la sidebar, préférences UI, informations de session côté client). Voir [section 10](#10-state-management--zustand) pour le détail des règles d'usage. Un store propre à une seule feature vit dans `features/<feature>/store/`, pas ici.

### `types/`

Types TypeScript globaux partagés par plusieurs features (types générés depuis l'API/OpenAPI, types utilitaires globaux). Un type utilisé par une seule feature reste dans `features/<feature>/types.ts`.

### `assets/`

Fichiers statiques : images, icônes, polices. Pas de logique.

### `main.tsx`

Point d'entrée : monte `<App />`, applique les providers de `app/providers` et le router de `app/router`. Ne contient pas de logique applicative.

## 6. Atomic Design

Les composants UI sont organisés selon les 5 niveaux de l'Atomic Design :

```text
Atoms → Molecules → Organisms → Templates → Pages
```

Les quatre premiers niveaux (Atoms à Templates) vivent dans `components/`. Le niveau **Pages** vit dans `features/*/pages/` (une page appartient à une feature, pas à `components/`).

### Atoms

Composants UI élémentaires, non composés d'autres composants métier, hautement réutilisables. Les primitives du design system et shadcn/ui vivent dans `components/ui/` (voir [design-system.md](design-system.md)).

Exemples : `Button`, `Input`, `Badge`, `Kpi`, `BentoModule`.

Règles :
- Pas d'appel API, pas de dépendance à une feature.
- Props génériques, pas de vocabulaire métier (`variant`, `size`, pas `importStatus`).

### Molecules

Assemblage simple de plusieurs Atoms formant un élément fonctionnel autonome.

Exemples : `SearchInput` (Input + Icon + Button clear), `FormField` (Label + Input + message d'erreur), `UserCard` (Avatar + texte).

Règles :
- Peut composer plusieurs Atoms.
- Reste générique : ne doit pas encoder une règle métier spécifique à une feature.

### Organisms

Compositions plus complexes de Molecules et/ou Atoms, formant une section autonome d'interface.

Exemples : `DataTable`, `Navigation`, `DashboardCard`.

Règles :
- Un organism **générique** (réutilisable dans plusieurs features) vit dans `components/organisms/`.
- Un organism **spécifique à une feature** (ex. `ImportForm` qui connaît le domaine "imports") vit dans `features/imports/components/`, pas dans `components/organisms/`. Voir [section 7](#7-organisation-par-feature) pour la règle de décision.

### Templates

Structure générale d'une page (arrangement des zones : header, sidebar, contenu, footer) **sans données métier**. Un template définit la mise en page, pas le contenu.

Exemple : `TwoColumnTemplate`, `DashboardTemplate` (zone de filtres + zone de contenu principal, sans savoir ce qui sera affiché dedans).

### Pages

Points d'entrée correspondant à une route de l'application. Une page :
- est associée à une route TanStack Router ;
- assemble un Template + des composants de la feature (et/ou des Organisms génériques) ;
- déclenche les Queries/Mutations nécessaires via les hooks de la feature ;
- vit dans `features/<feature>/pages/`.

## 7. Organisation par feature

Chaque fonctionnalité métier possède son propre dossier sous `features/` :

```text
features/
└── imports/
    ├── components/   # Composants UI spécifiques à "imports"
    ├── api/           # Fonctions d'appel API + queries/mutations de la feature
    ├── hooks/         # Hooks métier (composent souvent les queries/mutations de api/)
    ├── store/          # Store Zustand local (optionnel — état client de la feature)
    ├── types.ts        # Types métier de la feature
    └── pages/          # Pages de la feature (ex: ImportListPage, ImportDetailPage)
```

Un élément reste dans sa feature tant qu'il n'est utilisé que par elle. Il n'est promu vers `components/` que lorsqu'il devient réellement réutilisable ailleurs — jamais de manière anticipée ("on en aura peut-être besoin ailleurs").

### Features du projet

| Feature | Périmètre |
|---|---|
| `imports/` | Import des fichiers source (upload, liste des imports, statut). |
| `import-assistant/` | Agent IA d'aide au mapping : analyse du fichier, conversation avec l'IA, correction, preview du mapping en brouillon. |
| `mappings/` | Mappings persistés et réutilisables, indépendants du flux d'analyse IA. |
| `sessions/` | Détail d'une session (appels modèles, appels outils). |
| `dashboard/` | Indicateurs, visualisations, filtres. |
| `sources/` | Origines des datasets (TraceLab, SWE-chat, etc.). |
| `quality/` | Intégrité des données importées, issues expliquées. |
| `landing/` | Page d'accueil publique. |
| `auth/` | Connexion et inscription (session Bearer, distincte de `X-API-Key`). |
| `system/` | État du serveur affiché par le shell : fournisseur et modèle IA actifs (`GET /ai/providers`), disponibilité de l'API (`GET /health/ready`). Chargé dans `AppLayout`, passé en props à `AppSidebar`. |

#### Cas particulier : `import-assistant/` vs `mappings/`

Ce sont deux features distinctes plutôt qu'une seule, chacune avec sa propre responsabilité :

- `import-assistant/` porte la conversation avec l'IA et le mapping **en brouillon** — un état client, généralement géré par un [store Zustand de feature](#10-state-management--zustand) (`features/import-assistant/store/`).
- `mappings/` porte les mappings **validés/persistés**, consultables et réutilisables indépendamment du flux IA — géré via TanStack Query comme toute donnée serveur.
- La validation d'un mapping dans `import-assistant/` délègue la sauvegarde à l'API de `mappings/` (appel à une mutation exposée par `features/mappings/api/`). Cela matérialise côté frontend la règle métier « l'IA propose, elle ne modifie jamais la base directement ».

> Si cette séparation s'avère artificielle à l'usage (couplage constant entre les deux features), il est acceptable de fusionner en une seule feature avec un sous-dossier `assistant/`, plutôt que de forcer la séparation. Documenter ce choix dans la PR concernée le cas échéant.

#### Pas de feature « analytics » séparée

Le calcul des indicateurs (définition, unité, gestion des valeurs manquantes) est une responsabilité du **domaine backend**, testable indépendamment de l'UI — donc hors périmètre de ce document. `dashboard/` ne fait qu'**afficher** des indicateurs déjà calculés via l'API ; il ne doit jamais recalculer un indicateur côté client.

#### `dashboard/` vs `sessions/`

La vue détaillée d'une session est isolée dans sa propre feature `sessions/`, car elle est consommée à la fois par le drill-down du dashboard et potentiellement par une liste de sessions indépendante — cela évite de dupliquer la logique de récupération (queries) et d'affichage entre les deux features.

Le lien entre `dashboard/` et `sessions/` doit rester un **drill-down en lecture seule** géré par la navigation (le dashboard redirige vers une route de `sessions/` via `useNavigate`/un `Link`), et non un import direct de composants entre les deux features — ce qui respecterait la règle « pas d'import croisé entre features » de la [section 13](#13-règles-de-dépendances).

#### Filtres du dashboard : search params, pas Zustand

Les filtres du dashboard (source, agent, modèle, période) et le drill-down d'un graphique vers `sessions/` doivent passer par les **search params de TanStack Router** ([section 11](#11-routing--tanstack-router)), pas par un store Zustand, afin de rester partageables par lien et navigables (bouton précédent/suivant). Voir la règle de décision de la [section 10](#10-state-management--zustand).

### Comment classer un composant : arbre de décision

1. **Est-ce un composant shadcn/ui ou une primitive du design system (pas de vocabulaire métier) ?** → `components/ui/`.
2. **Est-ce une composition d'UI générique réutilisable par plusieurs features, sans connaissance du métier ?** → `components/organisms/` ou `components/templates/`.
3. **Est-ce utilisé uniquement par une feature, ou porte-t-il une connaissance du métier de cette feature (noms de champs, statuts, règles) ?** → `features/<feature>/components/`.
4. **Est-ce un point d'entrée de route ?** → `features/<feature>/pages/`.

### Distinction récapitulative

| Type | Emplacement | Connaît le métier ? | Réutilisable inter-features ? |
|---|---|---|---|
| Composant Atomic Design générique | `components/{atoms,molecules,organisms,templates}` | Non | Oui |
| Composant spécifique à une feature | `features/<feature>/components/` | Oui | Non (sauf promotion) |
| Page | `features/<feature>/pages/` | Oui | Non |
| Logique métier (hooks, api, types) | `features/<feature>/{hooks,api,types.ts}` | Oui | Non (sauf promotion vers `lib`/`hooks` si générique) |

## 8. shadcn/ui

shadcn/ui n'est pas une dépendance npm classique : les composants sont générés/copiés directement dans le code du projet, ce qui les rend éditables.

- **Emplacement** : les composants générés par la CLI shadcn et les modules du design system vivent dans `components/ui/` (`Button`, `Input`, `Bento`, `Kpi`, `Modal`…). Config : `frontend/components.json`. Voir [design-system.md](design-system.md).
- **Personnalisation** : la personnalisation visuelle passe par les tokens Tailwind/CSS variables (thème) et par les `class-variance-authority` (`cva`) variants déjà générés par shadcn — on édite le composant généré directement plutôt que de le surcharger depuis l'extérieur.
- **Utilisation par les features** : une feature importe les composants shadcn depuis `components/`, elle ne doit jamais copier/dupliquer un composant shadcn dans son propre dossier.
- **Créer un nouveau composant plutôt qu'utiliser shadcn tel quel** : quand le besoin ne correspond à aucun composant du catalogue shadcn, ou quand la composition nécessaire dépasse une simple variante (nouvel Atom/Molecule composé "from scratch", éventuellement à partir de primitives Radix si besoin).
- **Pas de logique métier dans les composants shadcn** : un composant shadcn (ou son wrapper dans `components/`) ne doit recevoir que des props génériques. Toute règle métier (ex. "désactiver le bouton si l'import est en cours") est décidée dans la feature, qui passe le résultat (`disabled={isImporting}`) au composant.

## 9. API & TanStack Query

### Flux attendu

```text
Page / Feature
      ↓
TanStack Query (queries / mutations)
      ↓
API Client (lib/api)
      ↓
Backend
```

### Emplacements

- **Fonctions d'appel API brutes** (`fetch`/wrapper HTTP, pas de React) : `features/<feature>/api/*.ts` pour les endpoints spécifiques à une feature ; `lib/api/` pour le client HTTP partagé (instance de base, gestion des headers, des erreurs, de l'auth). Le client n'envoie pas `X-API-Key` : le proxy (nginx en Docker, Vite en développement) l'ajoute depuis `API_KEY`, pour que la clé ne soit jamais livrée au navigateur ; le client n'ajoute que le jeton de session (`Authorization: Bearer`). Aucune clé ne doit être lue via `import.meta.env` : Vite inscrit toute variable `VITE_*` dans le bundle (voir [API.md](API.md) §1).
- **Queries** : définies avec `queryOptions` (ou hooks `useQuery`) dans `features/<feature>/api/`, ex. `features/imports/api/imports.queries.ts`. Elles encapsulent la clé de cache (`queryKey`) et la fonction d'appel.
- **Mutations** : définies dans `features/<feature>/api/`, ex. `features/imports/api/imports.mutations.ts`, avec gestion de l'invalidation associée dans `onSuccess`.
- Les composants (pages, components de feature) **consomment** ces queries/mutations via des hooks exportés (`useImportsQuery`, `useCreateImportMutation`) — ils n'appellent jamais `fetch` directement.

### États loading / error / success

Les états sont exposés par TanStack Query (`isLoading`, `isError`, `isSuccess`, `data`, `error`) et gérés au niveau de la Page ou du composant de feature qui consomme la query — jamais silencieusement ignorés. Les composants d'UI générique (`components/`) reçoivent ces états déjà résolus sous forme de props (ex. un `DataTable` reçoit `data`, `isLoading`, il n'appelle jamais lui-même une query).

### Cache et invalidation

- Chaque feature définit ses propres `queryKey`s, généralement centralisées dans un objet `imports.keys.ts` ou en tête du fichier `api/` pour éviter les typos et les incohérences.
- Une mutation invalide les queries concernées via `queryClient.invalidateQueries({ queryKey: importsKeys.all })` dans son `onSuccess`.
- La configuration globale du cache (staleTime par défaut, retry, etc.) est centralisée dans `lib/api/query-client.ts` et injectée via `QueryClientProvider` dans `app/providers/`.

### Éviter les appels API directs dans les composants UI

Règle stricte : `fetch`/`axios` n'apparaît **jamais** dans `components/` ni directement dans le JSX d'une page. Toute donnée serveur transite par une query/mutation définie dans `features/<feature>/api/`. Cela garantit que le cache, les états et l'invalidation restent centralisés et testables indépendamment de l'UI.

## 10. State management & Zustand

**Zustand** est utilisé pour l'état **client** : de l'état React (`useState`/`useReducer`) partagé entre plusieurs composants non liés par une relation parent-enfant directe, ou persistant au-delà du cycle de vie d'un composant, sans pour autant être une donnée serveur.

### Quand utiliser Zustand (et quand ne pas l'utiliser)

| Type d'état | Outil | Exemples |
|---|---|---|
| Donnée serveur (vient du backend) | **TanStack Query** | Liste des imports, détail d'une session, statut d'un job |
| État client global, partagé entre plusieurs features/routes | **Zustand** (`store/`) | Sidebar ouverte/fermée, thème choisi, filtres persistants inter-pages, panier/sélection multi-pages |
| État client local à une feature, partagé entre plusieurs composants de cette feature | **Zustand** (`features/<feature>/store/`) | Conversation et mapping en brouillon de `import-assistant/`, sélection multiple dans un tableau, brouillon de formulaire multi-étapes |
| État purement local à un composant | `useState` / `useReducer` | Ouverture d'un menu, valeur d'un champ contrôlé, hover |
| État dérivé de l'URL, partageable par lien | Search params **TanStack Router** | Filtres de liste, pagination, onglet actif, filtres du dashboard (source, agent, modèle, période) — voir [section 11](#11-routing--tanstack-router) |

Règle de décision : avant de créer un store Zustand, se demander si l'état peut rester local (`useState`) ou s'il devrait plutôt vivre dans l'URL (search params, partageable et navigable). Zustand est réservé aux cas où l'état est réellement partagé entre composants distants dans l'arbre et n'a pas vocation à être dans l'URL ni à venir du serveur. **Une donnée qui existe côté backend ne doit jamais être recopiée dans un store Zustand** — elle reste la responsabilité de TanStack Query, y compris pour un cache "optimiste" (géré via `queryClient.setQueryData`, pas via un store parallèle).

### Emplacement et granularité des stores

- **Stores globaux** (utilisés par plusieurs features, ou par `app/`) : `store/<nom>.store.ts` à la racine de `src/`, ex. `store/ui.store.ts`, `store/preferences.store.ts`.
- **Stores de feature** (utilisés uniquement à l'intérieur d'une feature) : `features/<feature>/store/<nom>.store.ts`, ex. `features/import-assistant/store/import-assistant.store.ts` (conversation IA + mapping en brouillon).
- Un store par domaine d'état cohérent (pas un store géant unique type "state global de l'app"). Plusieurs petits stores ciblés sont préférés à un store monolithique, pour limiter les re-renders et garder chaque store lisible.
- Un store de feature ne doit jamais être importé par une autre feature ; s'il devient nécessaire ailleurs, il est promu vers `store/` à la racine (même logique de promotion que pour les composants, [section 7](#7-organisation-par-feature)).

### Implémentation

Un store minimal, typé, avec sélecteurs :

```ts
// store/ui.store.ts
import { create } from 'zustand'

interface UiState {
  isSidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>((set) => ({
  isSidebarOpen: true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setSidebarOpen: (open) => set({ isSidebarOpen: open }),
}))
```

Consommation dans un composant, toujours via un **sélecteur** (jamais en récupérant l'objet complet du store) pour éviter les re-renders inutiles :

```ts
// à éviter : re-render à chaque changement du store, quel que soit le champ
const { isSidebarOpen, toggleSidebar } = useUiStore()

// à privilégier : sélection ciblée du champ nécessaire
const isSidebarOpen = useUiStore((state) => state.isSidebarOpen)
const toggleSidebar = useUiStore((state) => state.toggleSidebar)
```

Pour un store découpé en plusieurs responsabilités, préférer le pattern de **slices** (plusieurs `StateCreator` combinés) plutôt qu'un unique fichier qui grossit indéfiniment.

### Middlewares

- **`devtools`** : activé en développement pour inspecter les mutations de store dans Redux DevTools ; désactivé (ou no-op) en production.
- **`persist`** : utilisé uniquement pour l'état qui doit survivre à un rechargement de page (ex. préférence de thème, sidebar), avec une clé de stockage explicite et versionnée (`{ name: 'ui-store', version: 1 }`). Ne jamais persister de données serveur ni d'informations sensibles (tokens, données utilisateur) dans un store Zustand `persist` — ces données restent gérées par la couche d'authentification/`lib/api`.
- **`immer`** (optionnel) : utile si l'état d'un store devient profondément imbriqué (ex. état d'un wizard multi-étapes avec plusieurs sous-objets), pour simplifier les mises à jour immuables.

### Utilisation par les composants et les features

- Les composants génériques (`components/`) **ne doivent pas** dépendre directement d'un store métier de feature (`features/<feature>/store/`). Ils reçoivent l'état et les actions nécessaires via props, comme pour toute autre logique métier.
- Un composant générique peut en revanche consommer un store **global** (`store/`) s'il s'agit d'un état d'UI transverse assumé comme tel (ex. un composant `Sidebar` générique qui lit `useUiStore`).
- Une Page ou un composant de feature consomme le store de sa propre feature directement via le hook généré par `create()` (`useImportAssistantStore`), sans passer par une couche d'abstraction supplémentaire.
- Comme pour les queries/mutations, aucun composant ne doit accéder à `localStorage`/`sessionStorage` directement pour de l'état partagé : cela passe par un store Zustand avec middleware `persist`.

## 11. Routing & TanStack Router

### Flux attendu

```text
Route
  ↓
Page (features/<feature>/pages)
  ↓
Feature (hooks, api, components)
  ↓
Components (Atomic Design)
```

### Emplacements

- **Déclaration des routes** : dans `app/router/`. Selon le mode de génération choisi (file-based ou code-based), les fichiers de route vivent dans `app/router/routes/` et référencent la Page correspondante depuis la feature. Une route ne contient pas de JSX métier, elle se contente d'importer et de rendre la Page.
- **Layouts** : layouts globaux (shell applicatif) dans `app/layouts/`, montés au niveau des routes racine/pathless via `app/router`. Un layout propre à une feature (ex. un layout à onglets pour "imports") vit dans `features/imports/pages/` ou `features/imports/components/` s'il est réutilisé par plusieurs pages de la feature.
- **Association route ↔ Page** : chaque fichier de route importe la Page correspondante depuis `features/<feature>/pages/` et la rend dans son `component`. La route ne fait qu'orchestrer (paramètres, loaders, guards) ; la Page assemble l'UI.
- **Paramètres d'URL** : typés via le schéma de route TanStack Router (`params.parse` / validation Zod). Lus dans la Page via `Route.useParams()` — jamais via `window.location` ou un parsing manuel.
- **Routes protégées** : la logique d'authentification/autorisation (redirection si non connecté) est centralisée via un `beforeLoad` sur la route racine protégée ou un layout dédié dans `app/router/`, en s'appuyant sur le contexte d'authentification exposé par `app/providers/`.
- **Logique liée au routing** (navigation programmatique, lecture de search params) : dans les hooks fournis par TanStack Router (`useNavigate`, `useSearch`), utilisés au niveau de la Page ou d'un hook de feature — pas dans un composant Atomic Design générique.

## 12. Tailwind CSS

- **Utilisation directe des classes utilitaires** : privilégiée pour tout style local, propre à un composant, non dupliqué ailleurs. C'est le mode par défaut.
- **Créer un composant réutilisable** dès qu'une combinaison de classes se répète à l'identique dans plusieurs endroits, ou dès qu'un pattern visuel a une signification métier/UI stable (ex. "badge de statut"). La règle : dupliquer une combinaison de classes deux fois est acceptable, la dupliquer une troisième fois doit déclencher l'extraction en composant (Atom/Molecule).
- **Responsive** : mobile-first, via les préfixes standards Tailwind (`sm:`, `md:`, `lg:`, `xl:`). Pas de media query CSS custom en dehors de Tailwind sauf cas exceptionnel documenté en commentaire.
- **Thème** : light mode uniquement. Tokens dans `app/styles/globals.css` (`@theme inline` Tailwind v4) : surfaces glass, typographie Kanit/Manrope, Bento, accents. Ne jamais coder une couleur en dur (`#fff`, `bg-[#123456]`) : toujours passer par un token. Détail : [design-system.md](design-system.md).
- **Styles personnalisés** (CSS pur) : limités au strict nécessaire (ex. keyframes d'animation complexes non couvertes par Tailwind), centralisés dans un fichier global (`app/styles/globals.css` ou équivalent), jamais dans des fichiers `.css` dispersés par composant.
- **Quand utiliser Tailwind directement vs créer un composant** :
  - Style ponctuel, non répété → classes Tailwind inline.
  - Pattern répété ≥ 3 fois, ou porteur de sens UI (bouton, badge, carte) → composant Atomic Design.

## 13. Règles de dépendances

Principe général (sens autorisé des imports) :

```text
Pages → Features → Components → UI / lib
```

Règles explicites :

- `components/*` (Atomic Design) **ne doit jamais** importer depuis `features/*`. Les composants génériques ne connaissent aucune feature. Ils peuvent importer un store **global** de `store/` (état d'UI transverse assumé), jamais un store de `features/<feature>/store/`.
- `features/*` peut importer depuis `components/*`, `lib/*`, `hooks/*`, `store/*` (global), `types/*`.
- `features/*` **ne doit pas** importer depuis une autre `features/*` directement (import croisé) — ni ses composants, ni son store. Si deux features doivent partager quelque chose, ce quelque chose doit être remonté dans `components/`, `lib/`, `hooks/`, `store/` ou `types/` selon sa nature.
- `app/*` peut importer depuis `features/*/pages`, `components/*`, `lib/*`, `store/*`. L'inverse n'est jamais vrai (`features/*` n'importe pas `app/*`, à l'exception des providers/contexts exposés volontairement, ex. contexte d'auth).
- `lib/*`, `hooks/*`, `store/*` (génériques/globaux) et `types/*` (globaux) ne dépendent d'aucune autre couche de `src/` — ce sont les couches les plus basses.

**À éviter :**

```text
components/atoms/Button
        ↓
features/imports
```

**Acceptable :**

```text
features/imports
        ↓
components/atoms/Button
```

Ces règles peuvent être renforcées via une règle ESLint de type `import/no-restricted-paths` (ou équivalent) afin d'être vérifiées automatiquement en CI plutôt que reposer uniquement sur la revue de code.

## 14. Conventions

### Nommage des fichiers

- Composants React : `PascalCase.tsx` (`UserCard.tsx`).
- Hooks : `camelCase.ts`, préfixés `use` (`useImportStatus.ts`).
- Fonctions/utilitaires : `camelCase.ts` (`formatDate.ts`).
- Types : `types.ts` par feature, ou `<domaine>.types.ts` si plusieurs fichiers de types dans une même feature.
- Queries/Mutations : `<feature>.queries.ts` / `<feature>.mutations.ts`.
- Stores Zustand : `<domaine>.store.ts` (`ui.store.ts`, `import-assistant.store.ts`).
- Routes (file-based) : suivent la convention TanStack Router (`imports.index.tsx`, `imports.$importId.tsx`).

### Composants React

- Un composant par fichier, export nommé (pas de `export default` sauf pour les fichiers de route qui l'exigent).
- Props typées via une interface `<ComponentName>Props`.
- Pas de logique métier dans un Atom/Molecule/Organism générique.

### Hooks

- Un hook générique et réutilisable → `hooks/`.
- Un hook métier (dépend d'une query/mutation ou d'une règle spécifique à une feature) → `features/<feature>/hooks/`.
- Toujours préfixés `use`, retour typé explicitement si non trivial.

### Fonctions

- Fonctions pures et génériques → `lib/utils/`.
- Fonctions d'accès API → `features/<feature>/api/` ou `lib/api/` pour le client partagé.

### Types TypeScript

- Types globaux partagés inter-features → `types/`.
- Types propres à une feature → `features/<feature>/types.ts`.
- Préférer `interface` pour les objets/props de composants, `type` pour les unions/alias.

### Routes

- Un segment de route = un dossier/fichier clair, aligné sur la structure de `features/`.
- Le nom de la route reflète l'URL, pas le nom interne de la feature si différent.

### Queries / Mutations

- Nommage des hooks : `use<Entité><Action>` — `useImportsQuery`, `useImportQuery(id)`, `useCreateImportMutation`, `useDeleteImportMutation`.
- `queryKey` centralisées dans un objet dédié par feature (`importsKeys`) pour garantir la cohérence des invalidations.

### Stores Zustand

- Hook exporté par le store nommé `use<Domaine>Store` — `useUiStore`, `useImportAssistantStore`.
- Un store expose son état et ses actions dans une seule interface (`<Domaine>State`), pas de logique métier complexe dans les actions : une action modifie l'état, elle n'appelle pas l'API (cela reste le rôle de TanStack Query, éventuellement orchestré depuis un hook de feature qui combine store + mutation).
- Toute consommation d'un store en dehors du fichier qui le définit passe par un sélecteur (`useStore((s) => s.field)`), jamais par une déstructuration de l'état complet.

### Composants Atomic Design

- Chaque dossier (`atoms`, `molecules`, `organisms`, `templates`) expose un point d'entrée clair (fichier par composant, éventuellement un `index.ts` de ré-export si le projet l'adopte).
- Un composant qui grossit et commence à porter du vocabulaire métier doit être déplacé vers la feature concernée plutôt que de rester dans `components/` "par habitude".

## 15. Ajouter une nouvelle feature — guide pratique

1. Créer `features/<nouvelle-feature>/` avec les sous-dossiers `components/`, `api/`, `hooks/`, `pages/`, et un `types.ts`.
2. Définir les fonctions d'appel API et les queries/mutations dans `features/<nouvelle-feature>/api/`.
3. Si la feature a besoin d'un état client partagé entre plusieurs de ses composants (ex. un wizard multi-étapes), créer `features/<nouvelle-feature>/store/` — sinon, ne pas créer de store par anticipation.
4. Construire les Pages dans `features/<nouvelle-feature>/pages/`, en composant des Templates/Organisms génériques de `components/` et des composants spécifiques de `features/<nouvelle-feature>/components/`.
5. Déclarer la ou les routes dans `app/router/`, en les faisant pointer vers les Pages créées.
6. Ne créer un nouvel Atom/Molecule/Organism générique dans `components/` (ou un store dans `store/`) que si le besoin est réellement transverse ; sinon, garder le composant/store dans la feature.
7. Vérifier que le sens des dépendances respecte la [section 13](#13-règles-de-dépendances) avant d'ouvrir la PR.
