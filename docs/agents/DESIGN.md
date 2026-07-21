# DESIGN.md — the implementable design contract

Machine-readable distillation of the design bundle (`design-reference/`), for any
model building ADERA UI. **Tokens here are truth**; the `.dc.html` files are visual
reference only (open the screenshots, not the HTML, to see intent). If a value is not
in this file, it is not on-system — add it here *before* using it in code.

Source: `ADERA Design System.dc.html` + the bundle README (exact values verified
2026-07-16). Direction A "Paper & Clay" = light; Direction B "Bridge at Dusk" = dark.

## 1. Tokens (paste-ready for `web/src/styles/tokens.css` when the frontend starts)

```css
:root {                              /* Paper & Clay (light) */
  --bg: #FAF6F0;                     /* warm paper */
  --surface: #FFFDFA;                /* raised card */
  --ink: #2B211A;                    /* coffee text */
  --ink-secondary: #5C4F43;         /* umber */
  --ink-tertiary: #8C7A66;
  --accent: #B05A38;                 /* clay (primary) */
  --accent-hover: #8C4225;
  --accent-2: #D9A441;               /* ochre */
  --success: #2F7A55;                /* verified green — trust */
  --border: #EADDCB;
  --border-strong: #D9C9B8;

  /* urgency — the ONLY place these colors may appear (rule 5.2) */
  --urgent-fg: #9A2E1B;  --urgent-bg: #F8E3DC;   /* ≤ 7 days */
  --soon-fg:   #9A6A12;  --soon-bg:   #FBF0DC;   /* ≤ 14 days */
  --open-fg:   #2F7A55;  --open-bg:   #E5F0E9;   /* > 14 days */

  --radius-control: 10px;  --radius-card: 14px;  --radius-pill: 999px;
  --shadow-card: 0 2px 8px rgba(43,33,26,.07);
  --shadow-raised: 0 6px 18px rgba(43,33,26,.14);
}
.dark {                              /* Bridge at Dusk — a COMPANION, not an inversion */
  --bg: #1C1410;                     /* deep coffee */
  --surface: #251B14;
  --ink: #F2E8D8;
  --ink-secondary: #B8A88F;
  --ink-tertiary: #A08F73;
  --accent: #E8B54D;                 /* gold REPLACES clay as accent in dark */
  --accent-hover: #D9A441;
  --success: #5AB280;
  --border: #3B2C1F;
  --border-strong: #3B2C1F;
}
```

Components reference tokens only (`bg-surface text-ink border-border`) — **a raw hex
in a component is a bug** (08 §2). Map the same variables onto shadcn's
`--background/--foreground/--primary` slots once; everything inherits.

## 2. Typography

| Role | Font | Weights | Sizes |
|---|---|---|---|
| Display / tender titles / the አደራ wordmark | **Noto Serif** | 500–800 | 54 hero · 38 section · 26–28 screen title · 19 card title |
| Body & UI | **IBM Plex Sans** | 400–700 | 15–16 body · 13–14 meta |
| Data: dates, deadlines, money, ids | **IBM Plex Mono** | 400–600 | 11–12 labels/eyebrows |
| Amharic / Ethiopic accents | **Noto Sans Ethiopic** | 400/600/700 | wordmark + language toggle; not body copy |

Rules: **one serif moment per screen** (usually the title) — more turns it into a menu ·
deadlines/counts use mono with **tabular figures** so countdowns don't jitter · Amharic
must never fall back to a default sans (screenshot test catches it).

> ⚠️ Discrepancy resolved: docs 07 §8 / 08 §3 said "Inter"; the design bundle
> (Design System file + README) specifies **IBM Plex Sans/Mono**. The design files win
> (08 §2's own rule). Docs have been annotated.

## 3. Component inventory (build once, reuse; new component = new row FIRST)

| Component | Used on | Contract |
|---|---|---|
| `TenderCard` | Feed | `CountdownChip` + serif title + buyer + `FitLine` + `EligibilityChips` + save/dismiss |
| `CountdownChip` | everywhere | urgency tokens only; `aria-label` = full datetime in viewer TZ; shows user-local **and** EAT ("Closes in 2d 14h — 10:00 your time / 20:00 EAT") |
| `EligibilityChips` | card + detail | **exactly 4 variants, nobody invents a fifth:** `✅ eligible` · `⚠️ conditional` (condition inline) · `⛔ blocked` · `❓ unknown → Ask Counsel`; expandable to cited reasoning |
| `FactGrid` + `ConfidenceDot` | Tender detail | every AI-extracted fact shows its confidence; one-tap error report |
| `FitPanel` | detail | the grounded "why this fits you" ≤3 sentences |
| `QAChat` | detail | SSE streaming; citations as chips; "the documents don't answer this — closest is §5.1" is a kind state, never a red error |
| `BriefCard` | Win Brief | verdict banner · met/unmet requirement list · effort + facilitator quote |
| `FacilitatorCard` + `TrustBadge` | marketplace | vetting badge + "what we checked" expander · fixed prices · response-time stat · masked contacts |
| `EngagementTimeline` + `ProofViewer` | engagement | actor-stamped events; stamped-receipt image + accept/dispute. **NO escrow balance UI — see §6** |
| `KybUploader` + `VerifiedBadge` | poster flow | doc slots with states; badge = icon+text, never icon alone |
| `Stepper` + `ChipEditor` + `WhyWeAsk` | onboarding | confirmable tag chips; median <3 min is a tested number |
| `RunLedgerTable`, `ReviewQueueSplit`, `SpendSparkline` | admin | raw-vs-extracted side-by-side; corrections write golden labels |

## 4. Voice & microcopy (product law, not style preference)

- Plain language always: **"Why this fits you"**, never "RAG"; **"Held until you
  approve the proof"**, never "escrow milestone capture" (master plan §15).
- Every AI claim is cited: source link-out, confidence dot, "what we checked" expander.
- `unknown` is said plainly and routes to a facilitator — never guessed (NFR-LEGAL-1).
- Every deadline: user-local time + EAT alongside, countdown + explicit datetime.
- Money renders in the org's currency with the other as hint (FR-9.6); English
  default, Amharic toggle prominent (ADR-018).
- Empty states teach ("Your profile is live — first matches arrive with tomorrow's
  08:00 digest"). Trust surfaces always pair icon **+ text**.

## 5. Composition rules

1. Warm minimalism: color comes from ink + accents on paper — no stock imagery; the
   tender data *is* the interface.
2. **Urgency is the loudest color on any screen**; nothing else may use the urgent
   red tokens.
3. Spacing on the 8-pt grid; radii from tokens only.
4. Dark mode is a companion palette (gold accent), not an inversion filter.
5. Every component ships light+dark × Latin+Ethiopic before merge, with a Playwright
   screenshot diff (07 §10, 08 §6).
6. WCAG AA contrast is checked at the **token** level (fix the token, not per-component);
   all interactive elements keyboard-reachable with a visible `--accent` outline.

## 6. ⛔ Design ↔ Plan deltas (mocks that must NOT be built as drawn)

The hi-fi mocks depict Phase-5 vision. Authoritative list:
`design-reference/README.md` → "Design ↔ Plan deltas". The ones that bite UI work:

1. **No escrow / "funds held by ADERA" UI** — launch holds no client funds
   (FR-15.2, ADR-020, regulatory §6). Build the engagement timeline + proof
   accept/dispute; do NOT build balances, releases, or "pay into escrow" CTAs.
2. Platform fee is **10%** (not the 15–20% in flow diagrams).
3. Posting price is free-beta → ~ETB 2,500+VAT (not "$19 featured").
4. Proof = stamped receipt photo/scan + metadata (FR-15.6). GPS is NOT ratified
   (privacy — needs an ADR first).

## 7. Definition of on-system (checklist for any UI PR)

- [ ] tokens only — zero raw hex/px radii in components
- [ ] light + dark rendered; dark uses gold accent
- [ ] Latin + Ethiopic sample text rendered; no font fallback
- [ ] urgency colors only on urgency chips
- [ ] one serif moment per screen
- [ ] AI claims carry citation/confidence affordances
- [ ] copy passes §4 (plain language, no forbidden terms)
- [ ] not on the §6 do-not-build list
- [ ] screenshot spec added/updated for shared components
