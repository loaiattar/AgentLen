# Composants `components/ui`

Importer depuis `@/components/ui/<Name>`. Ne pas dupliquer les classes d’un composant dans une page.

États attendus : default, hover, active, focus, disabled, loading, error.

## Button

```tsx
<Button variant="primary" size="default" loading={false}>
  Label
</Button>
```

Variantes : `primary` (cyan filled), `secondary` (glass), `ghost`, `text`, `ai` (magenta), `danger` (pink).

Sizes : `sm`, `default`, `lg`, `icon`.

Une page = un `primary`. Le reste en `text` / `ghost` / `OverflowMenu`.

## Input / Textarea / Field / SearchField

```tsx
<Field label="Filename" htmlFor="file" error={error}>
  <Input id="file" error={Boolean(error)} />
</Field>
```

Focus : ring cyan. Error : bordure `--error` + message `role="alert"`.

## Badge / StatusDot

Tones Badge : `neutral`, `cyan`, `mint`, `magenta`, `pink`, `blue`, `warning`.

`StatusDot` exige `label` (accessibilité). Tones : `live`, `success`, `warning`, `error`, `muted`, `ai`.

## Kpi

```tsx
<Kpi label="Total sessions" value="24,861" delta="+12.4%" deltaTone="positive" />
```

Rien d’autre dans la carte sauf nécessité.

## Bento

```tsx
<BentoGrid>
  <BentoModule cols={2} rows={2} interactive>
    <BentoTitle>Agent activity</BentoTitle>
  </BentoModule>
</BentoGrid>
```

`cols` : 1, 2, 3, 4, 6. `rows` : 1, 2.

Contenu type : titre + visuel/valeur + une info support.

## Table + OverflowMenu

Une action visible par ligne (`Link` View). Secondaires dans `OverflowMenu`.

## FilterBar / FilterChip

Barre compacte, pas de gros boutons filtres.

## EmptyState / Skeleton / GlassSkeleton

Empty : titre Kanit + une phrase + un CTA.

Loading : skeletons glass + shimmer. Messages IA courts (Inspecting schema, Profiling fields…).

## Chart

`Sparkline`, `AreaChart`, `BarList`, `MixLegend`.

Tons : `cyan`, `blue`, `magenta`, `mint`, `pink`. Lignes fines, axes absents, beaucoup d’espace.

## Timeline / AiPanel

Timeline : `model` magenta, `tool` cyan, `agent` blue, `system` muted, `error` pink. Détails en progressive disclosure (`<details>`).

AiPanel : insights courts, confidence optionnelle, pas un chat générique.

## Overlay

`Modal`, `Drawer`, `Tooltip`, `OverflowMenu` : glass fort + `shadow-pop`.

## Shell

`AtmosphericBackground`, `AppSidebar`, `TopNav`, `MobileNav`, `PageHeader`.

Sidebar active : fond `primary-soft` + filet cyan + texte dark. Pas de gros bloc coloré.
