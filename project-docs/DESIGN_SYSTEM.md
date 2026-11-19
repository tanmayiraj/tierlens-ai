# TierLens AI: Design System

**Version:** 0.1 (Prototype)
**Companions:** `PRD.md`, `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `API_SPEC.md`

This document defines how TierLens AI looks and feels: principles, colour, typography, spacing, components, data-visualisation rules, screen layouts, accessibility and ready-to-use CSS tokens.

---

## 1. Design Principles

| Principle | What it means in the UI |
|---|---|
| **Clarity under pressure** | Users may open this during a disruption. The most important fact (what is affected, how soon) is always the most prominent thing on screen |
| **Show the why** | Every risk number, alert and edge can be traced to evidence. Evidence is one click away, never hidden |
| **Risk is the only loud colour** | The interface is calm and neutral. Colour is reserved for risk level and tier, so a red or amber element always means something |
| **Structure over decoration** | The supplier network is the hero. Chrome, borders and shadows stay quiet so the graph reads clearly |
| **Explore, then act** | Every insight leads to a next step: view impact, see alternatives, run a what-if |
| **Honest uncertainty** | Low-confidence or estimated data looks different (dashed, labelled "estimated") and is never presented as certain |

**Tone of voice:** plain, direct and specific. "RubberCore runs out of latex in 5 days" rather than "A potential supply interruption has been detected."

---

## 2. Brand

| Item | Value |
|---|---|
| Product name | **TierLens AI** |
| Metaphor | A lens that brings the hidden tiers into focus |
| Logo concept | Three concentric rings (tiers) with a bright focal dot, inside a rounded square |
| Personality | Trustworthy, analytical, calm, precise |

---

## 3. Colour

### 3.1 Brand and Neutral Palette

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-brand-600` | `#1F4FD8` | `#6C8EF5` | Primary actions, links, selected states |
| `--color-brand-500` | `#3B6AF0` | `#85A2F8` | Hover, focus accents |
| `--color-brand-100` | `#E6EDFF` | `#1B2A5C` | Selected row, subtle highlight |
| `--color-bg` | `#F7F8FA` | `#0F1218` | App background |
| `--color-surface` | `#FFFFFF` | `#171B24` | Cards, panels |
| `--color-surface-raised` | `#FFFFFF` | `#1E2330` | Popovers, modals |
| `--color-border` | `#E3E6EC` | `#2A3040` | Dividers, card outlines |
| `--color-text` | `#141824` | `#ECEFF6` | Primary text |
| `--color-text-muted` | `#5B6478` | `#9AA3B8` | Secondary text, labels |
| `--color-text-faint` | `#8A93A6` | `#6B7489` | Placeholders, hints |

### 3.2 Risk Colours (semantic)

Risk levels match `severity_label` in the API: `low`, `medium`, `high`, `critical`. Each level has a foreground, a soft background and a border so it works for text, badges and graph nodes.

| Level | Score range | Solid | Soft background (light) | Soft background (dark) | Text on soft |
|---|---|---|---|---|---|
| **Low** | 0 to 39 | `#2E9E6B` | `#E4F6EC` | `#14301F` | `#14663F` / `#6FD6A0` |
| **Medium** | 40 to 59 | `#E0A100` | `#FFF4D6` | `#3A2D08` | `#7A5800` / `#F2C94C` |
| **High** | 60 to 79 | `#E8742A` | `#FFE9DA` | `#3D2210` | `#9A4210` / `#F5A26B` |
| **Critical** | 80 to 100 | `#D6303F` | `#FFE1E4` | `#3F1519` | `#A3141F` / `#FF8A94` |

The score ranges above are the single source of truth for mapping `risk_score` to a level in the UI. The backend's `severity_label` should use the same cut-offs.

### 3.3 Status and Utility Colours

| Purpose | Colour |
|---|---|
| Success / approved | `#2E9E6B` |
| Info / pending | `#3B6AF0` |
| Warning / estimated data | `#E0A100` |
| Error / rejected | `#D6303F` |
| Simulated badge | `#7A4DE0` (purple, so simulations are never mistaken for real events) |

### 3.4 Tier Colours (graph identity)

Tier is shown by **ring colour and position**, never by risk colour, so the two signals do not clash.

| Tier | Meaning | Ring / outline colour |
|---|---|---|
| Manufacturer / Line | The company itself | `#141824` (dark) / `#ECEFF6` (dark mode) |
| Tier 1 | Direct suppliers | `#1F4FD8` (blue) |
| Tier 2 | Suppliers of suppliers | `#00A3B4` (teal) |
| Tier 3 | Raw material level | `#8A6DE0` (violet) |
| Tier 4+ | Deeper tiers | `#8A93A6` (grey) |

### 3.5 Colour Rules
1. **Never rely on colour alone.** Risk always also has a text label or icon (see section 9).
2. Red and orange are only for risk and errors. Never use them decoratively.
3. Text on coloured backgrounds must meet WCAG AA contrast (4.5:1 for normal text, 3:1 for large text).
4. Simulated data always carries the purple "Simulated" badge.

---

## 4. Typography

| Role | Font | Fallback |
|---|---|---|
| Interface and body | **Inter** | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` |
| Numbers, IDs, code, scores | **JetBrains Mono** | `ui-monospace, "SF Mono", Menlo, monospace` |

Use tabular numerals (`font-variant-numeric: tabular-nums`) for all scores, currency and day counts so columns align.

### 4.1 Type Scale

| Token | Size / Line height | Weight | Use |
|---|---|---|---|
| `--text-display` | 32 / 40 | 700 | Dashboard hero numbers |
| `--text-h1` | 24 / 32 | 650 | Page titles |
| `--text-h2` | 20 / 28 | 600 | Section titles |
| `--text-h3` | 16 / 24 | 600 | Card titles |
| `--text-body` | 14 / 22 | 400 | Default text |
| `--text-small` | 12 / 18 | 400 | Captions, table meta |
| `--text-micro` | 11 / 16 | 500 | Badges, graph labels (uppercase, letter-spacing 0.04em) |

Body text at 14px is the default because this is a dense, data-heavy tool. Never go below 11px.

---

## 5. Spacing, Layout and Shape

### 5.1 Spacing Scale (4px base)

`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64`

| Token | Value | Typical use |
|---|---|---|
| `--space-1` | 4px | Icon-to-text gap |
| `--space-2` | 8px | Inside badges, tight stacks |
| `--space-3` | 12px | Form field gaps |
| `--space-4` | 16px | Card padding (compact) |
| `--space-6` | 24px | Card padding (default), section gaps |
| `--space-8` | 32px | Between major blocks |

### 5.2 Radius and Elevation

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | 6px | Inputs, badges |
| `--radius-md` | 10px | Buttons, cards |
| `--radius-lg` | 14px | Modals, large panels |
| `--radius-full` | 999px | Pills, avatars |
| `--shadow-1` | `0 1px 2px rgba(16,24,40,0.06)` | Cards |
| `--shadow-2` | `0 4px 12px rgba(16,24,40,0.10)` | Popovers, dropdowns |
| `--shadow-3` | `0 12px 32px rgba(16,24,40,0.16)` | Modals |

In dark mode, rely on borders and surface tone rather than shadows.

### 5.3 Breakpoints

| Name | Width | Behaviour |
|---|---|---|
| Desktop (primary) | 1280px and above | Full three-zone layout |
| Laptop | 1024 to 1279px | Side panel becomes a slide-over |
| Tablet | 768 to 1023px | Single column, graph full width, panels as bottom sheets |
| Mobile | below 768px | Read-only dashboard and alerts. Graph is view-only |

The prototype is **desktop-first**. Tablet is supported, and mobile is a stretch goal.

---

## 6. Application Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Top bar:  Logo   [ Global search ]        Sim toggle  Alerts  User│
├────────┬─────────────────────────────────────────┬───────────────┤
│        │                                         │               │
│  Side  │              Main canvas                │  Detail panel │
│  nav   │      (graph, tables, simulator)         │  (node, alert │
│ 64/220 │                                         │   evidence)   │
│        │                                         │     360px     │
├────────┴─────────────────────────────────────────┴───────────────┤
│ Status bar: graph built time · nodes · edges · data mode         │
└──────────────────────────────────────────────────────────────────┘
```

| Zone | Size | Notes |
|---|---|---|
| Top bar | 56px high | Global search, "Simulation mode" toggle, alert bell with count |
| Side nav | 64px collapsed, 220px expanded | Dashboard, Upload and Review, Graph Explorer, Alerts, What-If Lab |
| Main canvas | Flexible | Holds the active screen |
| Detail panel | 360px, collapsible | Opens when a node, alert or relationship is selected |
| Status bar | 28px | Small, muted. Shows data freshness and mode |

**Simulation mode:** when on, a purple banner runs under the top bar ("Simulation mode: changes are not saved to live data") and simulated elements carry the purple badge.

---

## 7. Components

### 7.1 Buttons

| Variant | Use | Style |
|---|---|---|
| **Primary** | One main action per view (Run simulation, Approve) | Brand-600 fill, white text |
| **Secondary** | Supporting actions | Surface fill, border, text colour |
| **Ghost** | Low emphasis (Cancel, Reset) | No border, muted text |
| **Danger** | Reject, Delete | Critical fill or outline |

Height: 36px default, 32px compact, 44px large. Radius `--radius-md`. Focus ring: 2px brand-500 with 2px offset. Disabled: 40% opacity, no pointer events.

### 7.2 Risk Badge

A pill showing level plus score.

```
[ ● Critical · 83 ]    [ ● High · 67 ]    [ ● Medium · 48 ]    [ ● Low · 22 ]
```

- Uses the level's soft background and text colour, with a solid dot.
- Includes the word, not only the colour.
- Score in monospace.

### 7.3 Tier Chip

Small outlined chip: `T1`, `T2`, `T3`. Border and text use the tier colour from 3.4.

### 7.4 Status Badges

| Badge | Appearance |
|---|---|
| Approved | Green soft pill with a check icon |
| Pending review | Blue soft pill with a clock icon |
| Rejected | Red soft pill with an x icon |
| Estimated | Amber outline pill, label "Estimated" |
| Simulated | Purple solid pill, label "Simulated" |

### 7.5 Cards

- Surface fill, 1px border, `--radius-md`, `--shadow-1`, 24px padding.
- Header: title (h3) on the left, optional action or badge on the right.
- **Stat card:** label (small, muted) above a large tabular number, with an optional delta or sparkline beneath.

### 7.6 Alert Card

```
┌────────────────────────────────────────────────────────────┐
│ ▍ [● Critical · 83]   GreenLatex Pvt Ltd · Shutdown   [T3] │
│ ▍ Only latex source for RubberCore. Line A and Line B      │
│ ▍ likely to stop in 9 days.                                │
│ ▍ Revenue at risk  ₹18.5 L        First impact  5 days     │
│ ▍ [ View impact ]  [ See alternatives ]        Acknowledge │
└────────────────────────────────────────────────────────────┘
```

- A 4px left edge in the risk solid colour.
- Headline metrics (revenue at risk, first impact) in the largest text after the title.
- Explanation limited to two lines, with "Show full explanation" expanding it.
- Order alerts by `risk_score` descending.

### 7.7 Score Breakdown Bar

A single horizontal stacked bar showing factor contributions, with a legend underneath. This is the visual form of `score_breakdown`.

```
Event severity ███████  24
Criticality    ██████   22
Single-source  █████    20
Buffer gap     ███      12
Regional       █         5
                    Total 83
```

Factor colours are neutral blue-greys (not risk colours) so the bar does not look like a second risk signal.

### 7.8 Evidence Block

```
┌────────────────────────────────────────────────┐
│ 📄 PO_1042.pdf · page 1          Confidence 92% │
│ "GreenLatex to supply 40 MT of natural latex   │
│  to RubberCore monthly."                       │
│                                [ Open document ]│
└────────────────────────────────────────────────┘
```

- Snippet in a quote style with a left rule.
- Confidence shown as a percentage and a thin bar. Below 70% it turns amber and shows "Low confidence".

### 7.9 Tables

- 40px rows, sticky header, zebra striping off (use hover highlight).
- Numeric columns right-aligned, monospace.
- Sortable columns show an arrow. The active sort is bold.
- Row click selects and opens the detail panel.

### 7.10 Forms and Inputs

- 36px height, 6px radius, 1px border, brand focus ring.
- Label above field, helper text below in muted small text.
- Inline validation messages in the error colour with an icon.
- Sliders (for duration, extra days) show the live value in a monospace tooltip and a number input beside them.

### 7.11 Upload Zone

Dashed border drop target, 160px high, with an upload icon and "Drop PDF, TXT or CSV, or browse". After upload, each file shows a row with filename, a progress bar and an extraction status badge (`pending`, `processing`, `done`, `failed`).

### 7.12 Review Queue Row

Shows supplier → buyer, material, confidence, and the evidence snippet inline. Actions: **Approve**, **Edit**, **Reject**. Keyboard shortcuts: `A` approve, `E` edit, `R` reject, `J/K` next/previous.

### 7.13 Modals, Toasts and Banners

| Component | Rules |
|---|---|
| Modal | Centred, max width 560px, overlay at 50% black. Always has a close button and closes on Esc |
| Toast | Bottom-right, auto-dismiss after 5s. Success, info, error variants. Errors stay until dismissed |
| Banner | Full-width under the top bar. Used for simulation mode and LLM-unavailable notices |

### 7.14 Empty, Loading and Error States

| State | Treatment |
|---|---|
| **Empty** | A short line of explanation and one primary action ("No suppliers yet. Load the sample documents.") |
| **Loading** | Skeleton shapes that match the final layout. Graph shows a faint placeholder ring pattern |
| **Extraction in progress** | Progress bar with the current document name |
| **Error** | Plain message, what failed, and a Retry button. Never show raw stack traces |

---

## 8. Supplier Network Graph (Visual Language)

The graph is the core of the product, so its encoding is specified in detail.

### 8.1 Layout
- **Layered, left to right:** Tier 3 on the left, Tier 2, Tier 1, then the manufacturer and its production lines on the right. This matches the direction of material flow.
- Alternative layout toggle: **radial**, with the manufacturer at the centre and tiers as rings outward (the "lens" view).
- Nodes in the same tier are spread vertically with minimal edge crossings. Pan and zoom with mouse or trackpad, plus fit-to-screen and reset buttons.

### 8.2 Node Encoding

| Visual channel | Encodes | Details |
|---|---|---|
| **Fill colour** | Risk level | Soft background of the risk level (section 3.2). Grey if no score yet |
| **Outline colour** | Tier | Tier colours (section 3.4), 2px |
| **Shape** | Node type | Supplier: rounded rectangle. Material: small diamond. Production line: hexagon. Manufacturer: large circle |
| **Size** | Criticality | Bigger node = more downstream lines reached (3 sizes: 32, 40, 52px) |
| **Badge icon** | Flags | Hidden dependency (link-chain icon), single source (one-dot icon), single point of failure (warning triangle) |
| **Label** | Name | Shown at medium zoom and above. Truncated to 22 characters with a tooltip |

### 8.3 Edge Encoding

| State | Style |
|---|---|
| Approved | Solid line, 1.5px, muted grey, arrowhead toward the buyer |
| Pending review | Dashed line, blue |
| Low confidence (< 0.7) | Dashed line, amber |
| Edge width | Scales with `share_pct` (1.5px at low share up to 4px at 70%+) |
| Edge label | Material name on hover or selection. Lead time and share in the tooltip |
| Affected by an event | Solid line in the event's risk colour, with an animated flow along the path (see motion) |

### 8.4 Interaction

| Action | Result |
|---|---|
| Hover node | Tooltip with name, tier, risk badge. Connected edges and neighbours highlight, the rest fade to 25% |
| Click node | Selects it and opens the detail panel (risk breakdown, evidence, reaches) |
| Double-click node | Zooms to its neighbourhood |
| Click edge | Opens the evidence block for that relationship |
| Right-click or menu on node | "Simulate failure here", "Show alternatives", "Trace downstream" |
| Select event or alert | Disrupted node pulses once. The downstream path is highlighted and everything else fades |
| Filters | Tier, region, material, minimum risk, "show pending" toggle |

### 8.5 Legend
A compact, collapsible legend in the bottom-left corner of the graph covering risk fill, tier outline, shapes, edge styles and flag icons. It is open by default on first visit.

### 8.6 Impact Path View
A secondary visual used on the Alerts and What-If screens: a horizontal chain of nodes from the disrupted supplier to the production line, with the days-to-impact written on each link.

```
[GreenLatex T3] ──5d──▶ [RubberCore T2] ──4d──▶ [TyreWorks T1] ──▶ [Line A]
     ✕ shutdown            runs out day 5        runs out day 9      stops day 9
```

### 8.7 What-If Before/After
Two graphs or two impact paths side by side. Left is "Before mitigation" (risk colours), right is "After mitigation". A centre strip shows the improvement ("₹18.5 L protected · 2 lines protected") in the success colour.

---

## 9. Charts and Data Visualisation

| Chart | Where | Style |
|---|---|---|
| Risk distribution | Dashboard | Horizontal stacked bar by level, using risk colours with labels |
| Top risky suppliers | Dashboard | Ranked horizontal bars, with the risk badge at the end |
| Revenue at risk over time | What-If Lab | Line chart across the disruption duration, with a shaded buffer period |
| Tier composition | Dashboard | Small donut using tier colours |
| Score breakdown | Alert detail | Stacked bar (section 7.7) |

**Rules**
1. Label values directly where possible rather than relying on a legend.
2. Start bar charts at zero.
3. Use at most four colours per chart.
4. Provide a data table alternative for every chart (toggle "View as table").
5. Colour-blind-safe: pair colour with text labels or patterns (stripes for medium, dots for high, cross-hatch for critical in print and in the accessibility mode).

---

## 10. Screen Specifications

### 10.1 Dashboard
- **Top row:** four stat cards. Open alerts (with critical count), Hidden dependencies, Single-source materials, Revenue at risk.
- **Middle:** mini graph preview (read-only, click to open the explorer) beside the "Top risky suppliers" list.
- **Bottom:** latest alerts (three cards) and the dependency list.

### 10.2 Upload and Review
- Upload zone at the top, document list beneath with extraction status.
- Review queue below as a table of pending relationships, lowest confidence first, with inline evidence.
- Primary action at the bottom: **Build supplier map** (calls graph rebuild).

### 10.3 Graph Explorer
- Full-bleed graph canvas with a filter bar on top, a legend bottom-left, zoom controls bottom-right.
- Detail panel on the right opens on selection with tabs: **Overview**, **Risk**, **Evidence**, **Reach**.

### 10.4 Alerts
- Left: ranked alert list with filter chips (severity, status).
- Right: selected alert with the headline, the impact path view, score breakdown, evidence blocks and the buttons **View in graph**, **See alternatives**, **Simulate response**.

### 10.5 What-If Lab
- Left column (320px): scenario builder with supplier picker, duration slider, mitigation toggles (alternate supplier, safety stock, reroute, expedite).
- Right: before/after comparison (section 8.7), the revenue-at-risk chart and a notes list from the simulation.
- Primary action: **Run simulation**. Secondary: **Save scenario**.

---

## 11. Motion

| Interaction | Animation | Duration / easing |
|---|---|---|
| Panel open or close | Slide and fade | 200ms, ease-out |
| Hover highlight in graph | Opacity change | 120ms |
| Selecting an alert | Disrupted node pulses once, path draws in from origin to line | 600ms total |
| Impact flow | Dashed line "marching" toward the buyer along affected edges | Continuous, 1.2s loop, stops when the alert is deselected |
| Number changes (stats, scores) | Count up | 400ms, ease-out |
| Toast | Slide up and fade | 180ms |

**Rules:** keep motion purposeful (it shows direction of impact, not decoration). Respect `prefers-reduced-motion` by replacing animation with instant state changes and a static highlighted path.

---

## 12. Iconography

- Library: **Lucide** (consistent 1.5px stroke, 16 or 20px).
- Suggested icons: `network` (graph), `alert-triangle` (alerts), `flask-conical` (what-if), `file-up` (upload), `shield-check` (approved), `clock` (pending), `link-2` (hidden dependency), `factory` (supplier), `package` (material), `git-branch` (alternatives).
- Icons accompany text labels in navigation and badges. Icon-only buttons need a tooltip and an `aria-label`.

---

## 13. Accessibility

| Area | Requirement |
|---|---|
| Contrast | WCAG 2.1 AA minimum for all text and meaningful graphics |
| Colour independence | Risk is always conveyed by text and icon as well as colour (badges, node flags) |
| Keyboard | Every control reachable by Tab. Graph nodes navigable with arrow keys. `Enter` opens details, `Esc` closes panels |
| Focus | Visible 2px focus ring on all interactive elements, never removed |
| Screen readers | Graph has an equivalent **list view** (nodes with their connections) toggled by a "View as list" button. Charts have table alternatives. Alerts use `role="alert"` for new critical items |
| Motion | `prefers-reduced-motion` honoured |
| Touch targets | Minimum 36px (44px on touch devices) |
| Text scaling | Layout works with browser zoom to 200% |
| Language | Plain, short sentences. Define jargon ("Tier 2 = supplier of your supplier") in tooltips |

---

## 14. Dark Mode

- Follows system preference with a manual toggle in the user menu.
- All colours come from tokens (section 15), so switching is a variable swap.
- Graph background in dark mode is `#0F1218` with a faint dot grid. Node soft fills use the dark soft backgrounds from 3.2.
- Avoid pure black and pure white. Use the tokens.

---

## 15. CSS Design Tokens

```css
:root {
  /* Brand */
  --color-brand-600: #1F4FD8;
  --color-brand-500: #3B6AF0;
  --color-brand-100: #E6EDFF;

  /* Neutrals */
  --color-bg: #F7F8FA;
  --color-surface: #FFFFFF;
  --color-surface-raised: #FFFFFF;
  --color-border: #E3E6EC;
  --color-text: #141824;
  --color-text-muted: #5B6478;
  --color-text-faint: #8A93A6;

  /* Risk */
  --risk-low: #2E9E6B;       --risk-low-bg: #E4F6EC;      --risk-low-text: #14663F;
  --risk-medium: #E0A100;    --risk-medium-bg: #FFF4D6;   --risk-medium-text: #7A5800;
  --risk-high: #E8742A;      --risk-high-bg: #FFE9DA;     --risk-high-text: #9A4210;
  --risk-critical: #D6303F;  --risk-critical-bg: #FFE1E4; --risk-critical-text: #A3141F;

  /* Status */
  --status-success: #2E9E6B;
  --status-info: #3B6AF0;
  --status-warning: #E0A100;
  --status-error: #D6303F;
  --status-simulated: #7A4DE0;

  /* Tiers */
  --tier-0: #141824;
  --tier-1: #1F4FD8;
  --tier-2: #00A3B4;
  --tier-3: #8A6DE0;
  --tier-4: #8A93A6;

  /* Type */
  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
  --text-display: 32px;
  --text-h1: 24px;
  --text-h2: 20px;
  --text-h3: 16px;
  --text-body: 14px;
  --text-small: 12px;
  --text-micro: 11px;

  /* Space */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* Shape */
  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px; --radius-full: 999px;
  --shadow-1: 0 1px 2px rgba(16, 24, 40, 0.06);
  --shadow-2: 0 4px 12px rgba(16, 24, 40, 0.10);
  --shadow-3: 0 12px 32px rgba(16, 24, 40, 0.16);

  /* Motion */
  --motion-fast: 120ms;
  --motion-base: 200ms;
  --motion-slow: 400ms;
  --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-brand-600: #6C8EF5;
    --color-brand-500: #85A2F8;
    --color-brand-100: #1B2A5C;
    --color-bg: #0F1218;
    --color-surface: #171B24;
    --color-surface-raised: #1E2330;
    --color-border: #2A3040;
    --color-text: #ECEFF6;
    --color-text-muted: #9AA3B8;
    --color-text-faint: #6B7489;

    --risk-low-bg: #14301F;      --risk-low-text: #6FD6A0;
    --risk-medium-bg: #3A2D08;   --risk-medium-text: #F2C94C;
    --risk-high-bg: #3D2210;     --risk-high-text: #F5A26B;
    --risk-critical-bg: #3F1519; --risk-critical-text: #FF8A94;

    --tier-0: #ECEFF6;
    --shadow-1: none; --shadow-2: none; --shadow-3: none;
  }
}

:root[data-theme="dark"] {
  /* Same dark values as above, so the manual toggle works too */
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```

---

## 16. Component Naming (for the React codebase)

```
frontend/src/components/
├── layout/       AppShell, TopBar, SideNav, DetailPanel, StatusBar, SimulationBanner
├── ui/           Button, Badge, RiskBadge, TierChip, StatusBadge, Card, StatCard,
│                 Table, Input, Slider, Modal, Toast, Tabs, EmptyState, Skeleton
├── graph/        GraphCanvas, GraphLegend, GraphControls, NodeTooltip, ImpactPath
├── alerts/       AlertCard, AlertList, ScoreBreakdown, EvidenceBlock
├── review/       UploadZone, DocumentList, ReviewRow
└── simulate/     ScenarioBuilder, BeforeAfter, MitigationToggle, RevenueChart
```

---

## 17. Do and Don't

| Do | Don't |
|---|---|
| Use risk colours only for risk | Use red or orange as decoration |
| Pair every colour signal with text or an icon | Show risk as colour alone |
| Show evidence next to every claim | Show a score with no way to see why |
| Label estimated and simulated data clearly | Let simulated results look like live events |
| Keep the graph readable (fade the unrelated) | Show every label and edge at once |
| Lead alerts with impact in days and money | Lead with technical jargon |
| Respect reduced motion | Animate for decoration |

---

## 18. Demo Polish Checklist

- [ ] Sample data loads in one click from the empty state
- [ ] Selecting a Tier 3 event highlights the full path to the production line
- [ ] Score breakdown visible on every alert
- [ ] Before/after panel shows a clear improvement with a number
- [ ] Legend visible on the graph's first load
- [ ] Simulation mode banner and purple badges present
- [ ] Dark mode checked on all five screens
- [ ] Keyboard-only walkthrough of the main demo flow works
