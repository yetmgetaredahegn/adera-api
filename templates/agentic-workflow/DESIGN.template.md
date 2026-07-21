# DESIGN.md — the implementable design contract for {{PROJECT_NAME}}

Machine-readable distillation of the design source ({{Figma / design bundle / brand
doc}}). **Tokens here are truth** — the design files are visual reference only. If a
value is not in this file, it is not on-system; add it here *before* using it in code.

## 1. Tokens (paste-ready for {{tokens.css / theme file}})

```css
:root {                /* {{light theme name}} */
  --bg: {{hex}};
  --surface: {{hex}};
  --ink: {{hex}};
  --accent: {{hex}};   --accent-hover: {{hex}};
  --success: {{hex}};  --warn: {{hex}};  --danger: {{hex}};
  --border: {{hex}};
  --radius-control: {{px}};  --radius-card: {{px}};  --radius-pill: 999px;
  --shadow-card: {{value}};
}
.dark {                /* {{dark theme name}} — a companion, not an inversion */
  {{mirror every variable}}
}
```

Rule: components reference tokens only — **a raw hex in a component is a bug**.

## 2. Typography

| Role | Font | Weights | Sizes |
|---|---|---|---|
| Display | {{font}} | {{…}} | {{scale}} |
| Body/UI | {{font}} | | |
| Data/mono | {{font}} | | |
{{+ script/locale-specific fonts and their never-fallback rule}}

## 3. Component inventory (build once, reuse; new component = new row FIRST)

| Component | Used on | Contract |
|---|---|---|
| {{Name}} | {{screens}} | {{variants, states, hard constraints — e.g. "exactly N variants, nobody invents another"}} |

## 4. Voice & microcopy rules

- {{plain-language rule with a concrete "say X, never Y" pair}}
- {{honesty/uncertainty rule — how the UI says "unknown"}}
- {{locale/currency/time display rules}}

## 5. Composition rules

1. {{the loudest-color rule / hierarchy rule}}
2. {{spacing grid}}; radii from tokens only.
3. Every component ships {{light+dark / all locales}} before merge.
4. {{accessibility gate — contrast at token level, keyboard, aria}}

## 6. ⛔ Do-not-build list (design ↔ plan deltas)

<!-- Mocks often depict future vision. List every screen/element that must NOT be
     built as drawn, with the authority that forbids it. -->
- {{element}} — {{why, citation}}

## 7. Definition of on-system (checklist for any UI PR)

- [ ] tokens only — zero raw hex
- [ ] all themes + scripts rendered
- [ ] copy passes §4
- [ ] not on the §6 list
- [ ] screenshot test updated for shared components
