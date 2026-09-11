# Pages AgentLen

Chaque écran a un focus primaire et au plus une action primaire visible.

Responsive : desktop = composition Bento 12 col. Tablet = 6 col. Mobile = 1 col, réordonné par importance (pas un simple stack desktop).

## Overview `/overview`

2×2 Agent activity · 2×1 Total sessions · 1×1 Error rate · 1×1 Data quality · 3×2 Token consumption · 1×2 Model mix · 2×2 Tool usage · 2×1 Avg duration · 2×1 Recent activity.

## Landing `/`

Hero + aperçu dashboard glass · Bento capacités · Import → Normalize → Explore · assistant IA. CTAs : Get started (`/register`), Sign in (`/login`).

## Auth `/login` · `/register`

Un module glass, champs nécessaires seulement, erreurs inline, loading, lien de bascule.

## Sessions `/sessions`

Bento résumé (sessions, models, duration) puis table. Filtres légers.

## Session detail `/sessions/$sessionId`

Bento duration / tokens / tools / errors / model-agent, puis timeline full-width.

## Imports `/imports`

2×2 New import (CTA) · completed / duplicates / rejected · historique table.

## Mapping studio `/import-assistant`

Trois zones : Dataset | Mapping | AiPanel. CTA unique : Accept mapping.

## Data quality `/quality`

2×2 score d’intégrité, modules support, explorer d’issues. Valeurs manquantes ≠ 0.

## Data sources `/sources`

Un module par source : nom, statut, last import, records, sessions.

## Mapping library `/mappings`

Table + View + overflow.

## Shell global

Sidebar : Overview, Sessions, Imports, Data Sources, Mappings, Data Quality. Bas : provider, model, status, workspace.

Top : search, dataset, période, `ThemeToggle`, profil.
