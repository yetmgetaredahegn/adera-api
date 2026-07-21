# 08 — Design System Guide: from the ADERA design artifacts to shipped UI
*You already have generated design artifacts: wireframes, user-flow + data-flow diagrams, a clickable prototype, and two hi-fi suites — **Paper & Clay** (light: paper background, clay/ochre accents, coffee text) and **Bridge at Dusk** (dark: deep coffee ground, gold accents) — 8 core screens in light plus dark companions, Noto Serif display + Ethiopic accents, eligibility chips and the አደራ trust motif throughout. This doc is the repeatable workflow that turns those HTML design files into the production frontend, and the rules that keep every new screen consistent.*

## 1. The translation workflow (artifact → code, five steps, repeat per screen)
1. **Extract tokens once (§2):** open the design HTML files, copy every color/font/radius/shadow value into `web/src/styles/tokens.css` as CSS variables. From then on, the design files are *reference*, tokens are *truth* — if a hex appears in a component, that's a bug.
2. **Inventory the screen (§4):** name the components it contains against the inventory table; anything new gets a row before it gets code.
3. **Rebuild, don't paste:** design-tool HTML is presentational scaffolding; production components are rebuilt with shadcn primitives + Tailwind classes bound to tokens. Copy *values and spacing rhythm*, never markup.
4. **Check both modes + both scripts:** every component ships light+dark (tokens flip via `.dark` class) and is rendered with Latin and Ethiopic sample text before merge.
5. **Screenshot-test it (§6)** so the design can never silently drift.

## 2. Token extraction — the contract between design and code
Pull the exact values from the design files into this structure (names are final; hexes below are placeholders to overwrite with the real ones from the artifacts):
```css
:root {                       /* Paper & Clay (light) */
  --bg: /* paper */; --surface: /* raised card */; --ink: /* coffee text */;
  --ink-muted: ; --accent: /* clay */; --accent-2: /* ochre */;
  --gold: ; --success: ; --warn: ; --danger: ;
  --chip-eligible-bg: ; --chip-conditional-bg: ; --chip-blocked-bg: ;
  --radius: 12px; --radius-chip: 999px; --shadow-card: ;
}
.dark {                       /* Bridge at Dusk */
  --bg: /* deep coffee */; --surface: ; --ink: /* warm off-white */;
  --accent: /* gold */; /* …mirror every variable… */
}
```
Wire into Tailwind (`tailwind.config.ts → theme.extend.colors: { bg:"var(--bg)", ink:"var(--ink)", accent:"var(--accent)", … }`) so components say `bg-surface text-ink border-accent/20` — never hex. shadcn theming: map the same vars onto its `--background/--foreground/--primary` slots once, and every shadcn component inherits the ADERA feel for free.

## 3. Typography & the Ethiopian voice
Pairing rule from the hi-fi suites: **Noto Serif for display** (page titles, tender titles, the አደራ wordmark moments) + **IBM Plex Sans for UI text** (+ **IBM Plex Mono** for dates/deadlines/money) + **Noto Sans Ethiopic** loaded for all Amharic strings and Ethiopic accents. *(Correction: an earlier draft said Inter; the design bundle — Design System file + README — specifies IBM Plex Sans/Mono, and per §1 the design files win. Exact scale + rules extracted to `docs/agents/DESIGN.md`.)* Load via `next/font` (self-hosted, subset Latin / latin-ext / ethiopic — this is also a performance line item, 07 §8). Scale: display 32/40 · h2 24/32 · body 16/26 · chip/caption 13/18. Rules: Amharic never falls back to a default sans (visual test catches it); numerals in deadlines use tabular figures so countdowns don't jitter.

## 4. Component inventory ↔ the 8 hi-fi screens
| Design screen | Components it defines (build once, reuse) |
|---|---|
| Onboarding wizard | `Stepper`, `ChipEditor` (confirmable tags), `WhyWeAsk` footnote |
| Feed | `TenderCard` = urgency `CountdownChip` + title (serif) + buyer + `FitLine` + `EligibilityChips` + actions |
| Tender detail | `FactGrid` w/ `ConfidenceDot`s, `FitPanel`, `EligibilityChips` (expanded, cited), `QAChat`, `SourceLinkOut` |
| "Can we win this?" brief | `BriefCard` sections: verdict banner, requirement list w/ met/unmet icons, effort + facilitator quote block |
| Marketplace | `FacilitatorCard` (vetting `TrustBadge` + what-we-checked expander, price menu, response-time stat), masked-contact notice |
| Engagement/escrow | `EngagementTimeline` (actor-stamped events), `ProofViewer` (stamped-receipt image + accept/dispute), status copy in plain money language |
| Poster KYB + composer | `KybUploader` (doc slots + states), `VerifiedBadge`, structured `TenderComposer` |
| Admin ops | `RunLedgerTable`, `ReviewQueueSplit` (raw vs extracted), `SpendSparkline` |
Signature pattern — **EligibilityChips** — has exactly four variants and nobody invents a fifth: `✅ eligible` / `⚠️ conditional` (with the condition inline) / `⛔ blocked` / `❓ unknown → Ask Counsel`; colors from the chip tokens, expandable to the cited reasoning.

## 5. Design rules that keep future screens on-system
Warm minimalism: color comes from ink+accents on paper, not decoration; no stock imagery — the tender data *is* the interface. Urgency is the loudest color on any screen (nothing else may use `--danger`). One serif moment per screen (usually the title) — more turns it into a menu. Trust surfaces (badges, proofs, citations) always pair icon+text, never icon alone. Plain-language microcopy: "Held until you approve the proof", "The documents don't answer this — closest section is §5.1". Empty states teach ("Your profile is live — first matches arrive with tomorrow's 08:00 digest"). Spacing on the 8-pt grid; radius from tokens only. Dark mode is a *companion*, not an inversion — gold replaces clay as the accent, per the Bridge at Dusk suite.

## 6. Guarding the system (accessibility + regression)
WCAG AA contrast checked when tokens are extracted (fix the token, not per-component) · every interactive element keyboard-reachable with visible focus (`--accent` outline) · countdown chips carry `aria-label` with the full date-time in the viewer's timezone. Regression: Playwright screenshot specs render `TenderCard`, `EligibilityChips`, and `EngagementTimeline` in light+dark × en+am (four shots each) and diff in CI — token drift, Ethiopic fallback, and dark-mode breakage all fail the same cheap test (07 §10).

## Further reading & credible sources
- **Refactoring UI** — refactoringui.com — the single most useful resource for a developer shipping design; its spacing/hierarchy/color chapters explain *why* the token system works.
- **Nielsen Norman Group** — nngroup.com/articles — evidence-based UX patterns; search their pieces on onboarding, empty states, and trust signals when extending §5.
- **WCAG 2.1 quick reference** — w3.org/WAI/WCAG21/quickref — the contrast/keyboard/label requirements §6 enforces.
- **Noto fonts** — fonts.google.com/noto — Noto Serif, Sans, and **Sans Ethiopic** downloads + language coverage; pair with Next's font docs (nextjs.org/docs → optimizing fonts) for subsetting.
- **shadcn/ui theming** — ui.shadcn.com/docs/theming — the CSS-variable slots §2 maps ADERA tokens onto.
- **Inclusive Components (Heydon Pickering)** — inclusive-components.design — accessible build patterns for chips, toggles, and timelines like ours.
- **Material Design 3 — dark theme guidance** — m3.material.io (foundations → color) — vendor-flavored but the clearest articulation of "dark mode is a companion palette, not an inversion," which Bridge at Dusk follows.
- **Playwright visual comparisons** — playwright.dev/docs/test-snapshots — the screenshot-diff mechanics behind §6's regression net.
