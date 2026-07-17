# bgmon Design System

## 1. Atmosphere & Identity

bgmon is a calm, high-signal care dashboard: it should make glucose data, alarms, and daily actions easy to read without turning clinical information into visual noise. Its signature is the **floating status header** above a compact single-column dashboard: translucent surfaces, restrained indigo interaction accents, and semantic glucose colors make the current state legible at a glance in light and dark environments.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
|---|---|---:|---:|---|
| App background | `--color-bg` | `#f8fafc` | `#020617` | Page canvas |
| Primary surface | `--color-surface` | `#ffffff` | `#0f172a` | Cards, controls, dialogs |
| Glass surface | `--color-glass-bg` | `rgba(255,255,255,0.8)` | `rgba(15,23,42,0.8)` | Floating header and glass panels |
| Primary text | `--color-text` | `#0f172a` | `#f8fafc` | Titles, values, body copy |
| Muted text | `--color-text-muted` | `#64748b` | `#94a3b8` | Labels, metadata, timestamps |
| Default border | `--color-border-default` | `#e2e8f0` | `#1e293b` | Cards, control outlines, dividers |
| Subtle border | `--color-border-subtle` | `rgba(0,0,0,0.05)` | `rgba(255,255,255,0.05)` | Quiet hover and separation states |
| Glass border | `--color-glass-border` | `rgba(255,255,255,0.3)` | `rgba(255,255,255,0.1)` | Glass panel edge |
| Primary accent | `--color-primary` | `#4f46e5` | `#4f46e5` | Primary action, selected time range, focus context |
| Primary hover | `--color-primary-dark` | `#4338ca` | `#4338ca` | Primary-action hover |
| Primary contrast | `--color-primary-contrast` | `#ffffff` | `#ffffff` | Text/icons on primary accent |
| Success / in range | `--color-success`, `--color-in-range` | `#22c55e` | `#22c55e` | Healthy state, enabled confirmation |
| Warning | `--color-warning` | `#f59e0b` | `#f59e0b` | Caution and attention states |
| Danger / target low / target high | `--color-danger`, `--color-target-low`, `--color-target-high` | `#ef4444` | `#ef4444` | Critical states and destructive actions |
| Low glucose | `--color-low` | `#f97316` | `#f97316` | Low glucose state |
| High glucose | `--color-high` | `#eab308` | `#eab308` | High glucose state |

### Rules

- Semantic glucose colors communicate glucose state only; do not reuse them as generic decoration.
- Indigo is reserved for actions, selection, focus, and system affordances.
- New colors must be added as global tokens in `frontend/src/app.css` before use.
- Existing components contain a few literal semantic colors. Future UI work should prefer the tokens above and may consolidate those literals in a dedicated cleanup, not as incidental refactoring.

## 3. Typography

### Scale

| Level | Size | Weight | Line height | Tracking | Usage |
|---|---:|---:|---:|---:|---|
| Dashboard glucose value | `2rem` / 32px | 800 | 1 | normal | Current SGV in the header |
| Page / modal heading | `2rem` / 32px | 600–700 | 1.2 | normal | Login and major modal headings |
| Section heading | `1.375rem` / 22px | 600 | 1.2 | normal | Card and dialog headings |
| Body | `1rem` / 16px | 400 | 1.5 | normal | Default content |
| Body small | `0.875rem` / 14px | 400 | 1.5 | normal | Supporting content |
| Caption | `0.75rem` / 12px | 500 | 1.4 | `0.02em` | Metadata, timestamps, units |
| Overline / label | `0.8rem` / 12.8px | 500–600 | 1.3 | `0.05em` | Uppercase stat labels and compact control labels |

### Font stack

- Primary: `Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Mono: system monospace only when a technical identifier genuinely needs it; it is not a primary UI font.

### Rules

- Numeric glucose values use tabular numerals where alignment matters.
- Body copy must not be smaller than 14px except version metadata and similarly non-essential chrome.
- Use sentence case for controls and headings unless the component pattern intentionally uses an uppercase overline.

## 4. Spacing & Layout

### Base unit

All recurring spacing is based on 4px and exposed through the existing tokens in `frontend/src/app.css`.

| Token | Value | Usage |
|---|---:|---|
| `--spacing-xs` | 4px | Icon-label gaps, compact inline groups |
| `--spacing-sm` | 8px | Buttons, compact controls, list rhythm |
| `--spacing-md` | 16px | Standard card padding and dashboard side padding |
| `--spacing-lg` | 24px | Separation between dashboard sections |
| `--spacing-xl` | 32px | Major content separation |

### Layout

- Primary dashboard width: 900px maximum, centered, with 16px horizontal padding.
- General container width: 1200px maximum.
- Dashboard content is a vertical stack; cards own their internal grids.
- Header is sticky and capped to the dashboard width.
- Breakpoints in use: mobile-first; 640px reveals the header wordmark; component grids adapt at their local breakpoints.
- Respect safe-area insets in the sticky mobile header.

### Rules

- Reuse spacing tokens rather than introducing one-off gaps.
- Keep the dashboard readable as a single-column sequence on small screens.
- The time-range control is contextual dashboard navigation, not a standalone tile; it appears only when at least one active tile needs its time range.

## 5. Components

### Surface card

- **Structure:** a semantic content container with `--color-surface`, default border, `--radius`, and subtle shadow.
- **Variants:** standard card, glass card, compact control panel, modal content.
- **Spacing:** `--spacing-md` padding; `--spacing-sm` internal compact rhythm.
- **States:** default, hover for interactive cards, selected, disabled, loading, empty, and error where relevant.
- **Accessibility:** preserve semantic buttons for interactive cards; visible keyboard focus must be retained.
- **Motion:** hover and pressed feedback use transform/opacity/color only, within 100–150ms.

### Floating status header

- **Structure:** sticky header containing a rounded `header-pill`, glucose status, primary actions, and settings.
- **Variants:** compact mobile header and expanded header with wordmark at 640px and above.
- **Spacing:** `--spacing-sm` and `--spacing-md`; no arbitrary header gutters.
- **States:** default, current-glucose pulse on change, interactive SGV hover, unavailable-data fallback.
- **Accessibility:** every icon-only control requires an accessible name; controls remain keyboard reachable.
- **Motion:** glucose change uses the existing transform/text-shadow pulse; respect reduced-motion preferences for new motion.

### Time-range navigation

- **Structure:** range buttons, current window label, and refresh button in a compact surface card.
- **Variants:** visible when graph or logbook is active; hidden when neither requires it; always visible in dashboard edit mode.
- **States:** default, hover, active range, loading refresh, disabled refresh.
- **Accessibility:** use buttons with descriptive titles; active state must not rely only on color.
- **Motion:** no layout animation on show/hide; use a brief opacity/transform transition only if future implementation needs one.

### Dashboard tile

- **Structure:** a top-level dashboard content item wrapping Graph, Logbook, or the statistics grid. The statistics grid exposes each metric card as its own configurable dashboard tile.
- **Variants:** view-active, edit-active, edit-inactive.
- **Spacing:** tiles are separated by `--spacing-lg`.
- **States:**
  - **View-active:** normal interactive child behavior.
  - **Edit-active:** visually selectable with an enabled status badge.
  - **Edit-inactive:** still visible for editing but clearly de-emphasized and marked hidden.
- **Accessibility:** in edit mode the tile wrapper is a keyboard-operable button-like control with an explicit accessible label such as “Diagramm ausblenden”; nested child actions must not accidentally trigger a tile toggle.
- **Motion:** selected state changes use opacity, outline/color, and transform only; no animated dimensions.

### Statistic card tile

- **Structure:** one card inside the statistics grid: Today, Prediction, Time in Range, Streak, Min/Mean/Max, Badges, GMI, or Readings.
- **Variants:** view-active, edit-active, edit-inactive; inactive cards remain visible only while editing.
- **States:** the edit overlay captures the whole card to avoid firing its underlying modal action while a user is changing visibility.
- **Accessibility:** every edit overlay is a labelled button whose pressed state communicates whether that individual metric is active.

### Footer utility action

- **Structure:** version label plus a compact icon button.
- **Variants:** edit trigger and save/finish trigger.
- **States:** default, hover, focus-visible, pressed, edit-active.
- **Accessibility:** SVG-only icon button requires an `aria-label` and a tooltip/title; it must communicate whether activating it enters edit mode or saves and exits it.
- **Motion:** 100–150ms color/opacity feedback only.

### Modal and popover

- **Structure:** overlay plus surfaced content, as implemented by existing dialogs and component popovers.
- **States:** open, closing, loading, error, and destructive confirmation where relevant.
- **Accessibility:** modal overlays need dialog semantics, focus handling, close controls, and an escape path. Popovers need clear dismissal behavior.
- **Depth:** use the established elevated surface and shadow treatment; do not use black modal backgrounds except the dedicated BG alarm modal.

## 6. Motion & Interaction

| Type | Duration | Easing | Usage |
|---|---:|---|---|
| Micro | 100–150ms | ease-out | Button hover/press, tile selection, icon feedback |
| Standard | 150–200ms | ease-in-out | Popover and contextual-panel state changes |
| Data emphasis | 1.5s | ease-out | Existing glucose-change pulse |

### Rules

- Animate only `transform`, `opacity`, `color`, `background-color`, `border-color`, and safe shadow changes; never animate layout dimensions or positional properties.
- Every new interactive control needs hover, focus-visible, active, and disabled behavior where applicable.
- Preserve existing behavior for `prefers-reduced-motion`; new non-essential tile-edit feedback must reduce to an immediate state change for users who request less motion.
- Motion must communicate a state transition. Decorative animation is not part of the system.

## 7. Depth & Surface

### Strategy

The system uses **mixed depth**: thin borders define normal surfaces, small-to-large shadows establish elevation, and the sticky header uses a translucent glass treatment. This combination is deliberate because the dashboard needs both clinical separation and a compact floating control surface.

| Level | Token / treatment | Usage |
|---|---|---|
| Resting | `--shadow-sm` + default border | Cards and time controls |
| Raised | `--shadow-md` | Interactive stat cards and transient panels |
| Floating | `--shadow-lg` + glass surface | Sticky header pill |
| Modal | `--shadow-xl` + surfaced dialog | Modal content and prominent overlays |

### Rules

- Use the `.glass` treatment only for elements that visually float above the dashboard, primarily the header.
- Standard dashboard tiles remain opaque `--color-surface` cards for legibility.
- New interactive tile-edit states may use a primary-tinted outline and surface tint, but must preserve text contrast in both themes.
- Do not add `backdrop-filter` to modal ancestors; it can change the containing block for fixed descendants.

## Known inconsistencies and follow-up discipline

- Several legacy components use raw colors, emoji labels/icons, and local spacing values. Do not expand those patterns in new work.
- This document codifies the existing visual system; systematic cleanup belongs in a dedicated refactor rather than the dashboard-customization feature.
- Any reusable component added by future dashboard customization must be documented in Section 5 before it is reused elsewhere.
