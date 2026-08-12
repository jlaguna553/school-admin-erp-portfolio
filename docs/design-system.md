# Design System — derived from the reference dashboard

Source: design reference supplied 2026-07-26. This document is the contract the
web app implements; update it here first, then in code.

## Layout shell

| Region | Spec |
| --- | --- |
| Sidebar | Fixed, ~200–224px, deep navy, full height, does not scroll with content |
| Sidebar top | Logo mark in a rounded square + wordmark beneath |
| Sidebar nav | Uppercase muted "Menu" section label; icon + label rows; **active** row = lighter translucent fill + left accent bar |
| Sidebar bottom | Logout pinned to the bottom edge |
| Top bar | White, hairline bottom border: page title (left) · search input (center, max ~420px) · notifications + user cluster (right) |
| Canvas | Cool light gray-blue, generous padding, cards float on it |

## Content composition

1. **Page intro** — large bold greeting + muted one-line subtitle.
2. **KPI row** — 4 equal tiles. Each: small medium-weight label, oversized bold
   value, muted delta caption. Collapses 4 → 2 → 1 across breakpoints.
3. **Split grid** — `2fr 1fr`. Wide column: primary chart card. Narrow column:
   stacked secondary cards. Becomes a single column below `lg`.

## Cards

- White surface, ~10px radius, 1px hairline border, shadow near-zero.
- Title is a small-to-medium semibold label, not a heading-sized element.
- Internal padding ~20–24px.

## Color tokens

Semantic names only — components never hardcode hex.

| Token | Light | Role |
| --- | --- | --- |
| `--background` | `#F1F4F8` | App canvas |
| `--card` | `#FFFFFF` | Card / top bar surface |
| `--foreground` | `#111827` | Headings, KPI values |
| `--muted-foreground` | `#6B7280` | Labels, captions, axis text |
| `--border` | `#E5E7EB` | Hairlines, dividers |
| `--primary` | `#1D4ED8` | Chart series, active nav, focus ring |
| `--sidebar` | `#12325B` | Sidebar surface |
| `--sidebar-foreground` | `#E8EEF6` | Sidebar text |
| `--sidebar-accent` | `rgba(255,255,255,.10)` | Active/hover nav fill |

Status: `success` green (completed), `muted` gray (pending), `info` blue (active).
Every token also gets a dark-mode value; the reference only shows light.

## Chart rules (Weekly Activity card)

- Single series, smoothed line, gradient area fade to transparent.
- **No** y-axis line, ticks or labels; four faint horizontal gridlines carry the
  scale. X-axis labels are localized weekday abbreviations (`Intl.DateTimeFormat`),
  with tick thinning disabled so all seven always render.
- Single series ⇒ **no legend**; the card title names the measure.
- Crosshair + tooltip on hover is part of the spec, not an extra.
- A **table view** toggle is required on every chart card, for screen readers,
  print, and anyone who wants the numbers.

### Deviation from the reference, on purpose

The reference labels **every** point. This implementation labels only the
**first, last and maximum**. Printing a number on all seven turns the plot into a
table with a line through it, and the exact values for the rest are one hover
away. This is the one place the chart intentionally departs from the mockup.

### Series colours are validated, not chosen by eye

`--chart-1` is re-stepped per theme rather than inverted, because the light blue
fails the contrast floor on a dark surface:

| Mode | Value | Result |
| --- | --- | --- |
| Light | `#1D4ED8` | passes lightness band, chroma floor, ≥ 3:1 contrast |
| Dark | `#3B82F6` | passes all checks |
| Dark (rejected) | `#1D4ED8` | contrast 2.6:1 — below the 3:1 floor |
| Dark (rejected) | `#60A5FA` | outside the lightness band |

Re-run the check with the `dataviz` skill's validator before changing a series
colour. Status colours (`--success` / `--warning` / `--destructive` / `--info`)
are reserved for state and are never reused as series colours; each ships with an
icon **and** a word, so state never depends on colour alone.

## Typography

Inter (or the closest system sans). Tight tracking on large numbers. Scale:
page title ~30px/bold, KPI value ~30px/bold, card title ~14px/semibold,
body ~14px, caption ~12px.

## Adaptation to the ERP

The reference is a generic workspace app. Mapping:

- Sidebar nav → ERP modules (Dashboard, Students, Academic, Enrollment,
  Schedule, Billing, Reports, Settings) — mirrors the Django bounded contexts.
- KPI tiles → institution metrics (active students, staff, attendance today,
  collection rate).
- Chart → weekly attendance or enrollment trend.
- Meeting list → upcoming academic calendar events.
- Activity table → recent administrative audit entries.
- All labels come from `next-intl` dictionaries; the reference's English strings
  are placeholders, and `es` is the default locale.
